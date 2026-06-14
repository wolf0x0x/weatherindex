#!/usr/bin/env python3
"""WeatherIndex static site generator."""
from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api_clients import collect_weather

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
DIST_DIR = ROOT / "dist"
GENERATED_DIRS = ["city", "wiki", "alert", "data"]
GENERATED_ROOT_FILES = ["index.html", "lang.html", "search.html", "sitemap.xml", "robots.txt"]

LANGS = [
    {"code": "en", "flag": "🇺🇸", "name": "English", "native": "Weather", "dir": "ltr"},
    {"code": "zh", "flag": "🇨🇳", "name": "中文", "native": "天气", "dir": "ltr"},
    {"code": "es", "flag": "🇪🇸", "name": "Español", "native": "Clima", "dir": "ltr"},
    {"code": "fr", "flag": "🇫🇷", "name": "Français", "native": "Météo", "dir": "ltr"},
    {"code": "de", "flag": "🇩🇪", "name": "Deutsch", "native": "Wetter", "dir": "ltr"},
    {"code": "ja", "flag": "🇯🇵", "name": "日本語", "native": "天気", "dir": "ltr"},
    {"code": "ru", "flag": "🇷🇺", "name": "Русский", "native": "Погода", "dir": "ltr"},
    {"code": "kr", "flag": "🇰🇷", "name": "한국어", "native": "날씨", "dir": "ltr"},
    {"code": "ar", "flag": "🇸🇦", "name": "العربية", "native": "الطقس", "dir": "rtl"},
]

CONFIG = {
    "site_url": os.environ.get("SITE_URL", "https://weatherindex.xyz").rstrip("/"),
    "ads_client": os.environ.get("ADS_CLIENT", os.environ.get("GOOGLE_ADSENSE_CLIENT", "ca-pub-8695398658548679")),
    "ads_top_slot": os.environ.get("ADS_TOP_SLOT", ""),
    "ads_bottom_slot": os.environ.get("ADS_BOTTOM_SLOT", ""),
    "ga_id": os.environ.get("GA_ID", os.environ.get("GOOGLE_ANALYTICS_ID", "G-SQCD1J9Y0H")),
}

WMO_ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️", 61: "🌦️", 63: "🌧️", 65: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "❄️", 80: "🌦️", 81: "🌧️", 82: "⛈️", 95: "⛈️",
}
ICON_CODE = {"clear-day": 0, "clear-night": 0, "partly-cloudy-day": 2, "partly-cloudy-night": 2, "cloudy": 3, "rain": 63, "snow": 73, "fog": 45, "wind": 3, "thunder-rain": 95, "thunder-showers-day": 95}
SEVEN_CODE = {"clear": 0, "pcloudy": 2, "mcloudy": 2, "cloudy": 3, "humid": 3, "lightrain": 61, "oshower": 80, "ishower": 80, "lightsnow": 71, "rain": 63, "snow": 73, "rainsnow": 73, "tsrain": 95, "ts": 95, "fog": 45}


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_translations() -> dict:
    return load_json(ROOT / "translations.json")


def cities() -> list[dict]:
    rows = load_json(ROOT / "config" / "city-seeds.json")
    result = []
    for row in rows:
        item = dict(row)
        item["slug"] = item.get("slug") or slug(item["name"])
        result.append(item)
    return result


def load_last_known_weather() -> dict[str, dict]:
    for path in (ROOT / "data" / "cities.json", ROOT / "config" / "last-known-cities.json"):
        if not path.exists():
            continue
        try:
            rows = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        return {row.get("slug"): row.get("weather") for row in rows if row.get("slug") and row.get("weather")}
    return {}


def stale_weather(city: dict, previous: dict, error: Exception) -> dict:
    cached = json.loads(json.dumps(previous))
    cached["source"] = f"stale-{cached.get('source', 'live-cache')}"
    cached.setdefault("api_status", [])
    cached["api_status"] = cached["api_status"] + [{"source": "last-known-cache", "ok": "false", "error": str(error)}]
    return cached


def num(value: Any, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def rounded(value: Any, default: int | None = None) -> int | None:
    parsed = num(value)
    return default if parsed is None else round(parsed)


def weather_icon(code: Any) -> str:
    return WMO_ICONS.get(int(code or 0), "🌤️")


def weather_text(code: int, trans: dict, lang_code: str) -> str:
    return trans["weather_codes"].get(str(code), {}).get(lang_code) or trans["weather_codes"].get(str(code), {}).get("en") or "Partly Cloudy"


def hourly_from_open_meteo(raw: dict) -> list[dict]:
    hourly = raw.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    codes = hourly.get("weather_code") or [0] * len(times)
    start_idx = 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    for idx, value in enumerate(times):
        if value >= now:
            start_idx = idx
            break
    return [
        {"time": times[i].split("T")[-1][:5], "temperature": rounded(temps[i], 0), "weather_code": int(codes[i] or 0), "is_current": i == start_idx}
        for i in range(start_idx, min(start_idx + 24, len(times), len(temps)))
    ]


def normalize_open_meteo(raw: dict, bundle: dict) -> dict | None:
    try:
        cur = raw["current"]
        daily = raw["daily"]
        air_current = (bundle.get("air_quality") or {}).get("current") or {}
        marine_current = (bundle.get("marine") or {}).get("current") or {}
        return {
            "current": {
                "temperature_2m": rounded(cur["temperature_2m"]),
                "relative_humidity_2m": rounded(cur.get("relative_humidity_2m")),
                "apparent_temperature": rounded(cur.get("apparent_temperature", cur["temperature_2m"])),
                "weather_code": int(cur.get("weather_code") or 0),
                "wind_speed_10m": rounded(cur.get("wind_speed_10m"), 0),
                "pressure_msl": rounded(cur.get("pressure_msl")),
                "visibility": rounded((num(cur.get("visibility"), 0) or 0) / 1000),
            },
            "air_quality": normalize_air(air_current),
            "marine": normalize_marine(marine_current),
            "hourly": hourly_from_open_meteo(raw),
            "daily": {
                "time": daily["time"][:7],
                "temperature_2m_max": [rounded(x) for x in daily["temperature_2m_max"][:7]],
                "temperature_2m_min": [rounded(x) for x in daily["temperature_2m_min"][:7]],
                "weather_code": [int(x or 0) for x in daily["weather_code"][:7]],
                "precipitation_probability_max": [int(x or 0) for x in daily.get("precipitation_probability_max", [0] * len(daily["time"]))[:7]],
            },
            "source": "open-meteo",
        }
    except (KeyError, TypeError, ValueError):
        return None


def normalize_visual_crossing(raw: dict, bundle: dict) -> dict | None:
    try:
        cur = raw["currentConditions"]
        days = raw["days"][:7]
        code = ICON_CODE.get(str(cur.get("icon", "")).lower(), 2)
        hourly = []
        for day in days:
            for hour in day.get("hours", []):
                if len(hourly) >= 24:
                    break
                hourly.append({"time": str(hour.get("datetime", ""))[:5], "temperature": rounded(hour.get("temp")), "weather_code": ICON_CODE.get(str(hour.get("icon", "")).lower(), code), "is_current": not hourly})
        return {
            "current": {"temperature_2m": rounded(cur["temp"]), "relative_humidity_2m": rounded(cur.get("humidity")), "apparent_temperature": rounded(cur.get("feelslike", cur["temp"])), "weather_code": code, "wind_speed_10m": rounded(cur.get("windspeed"), 0), "pressure_msl": rounded(cur.get("pressure")), "visibility": rounded(cur.get("visibility"))},
            "air_quality": normalize_air((bundle.get("air_quality") or {}).get("current") or {}),
            "marine": normalize_marine((bundle.get("marine") or {}).get("current") or {}),
            "hourly": hourly,
            "daily": {"time": [d["datetime"] for d in days], "temperature_2m_max": [rounded(d.get("tempmax")) for d in days], "temperature_2m_min": [rounded(d.get("tempmin")) for d in days], "weather_code": [ICON_CODE.get(str(d.get("icon", "")).lower(), 2) for d in days], "precipitation_probability_max": [rounded(d.get("precipprob"), 0) for d in days]},
            "source": "visual-crossing",
        }
    except (KeyError, TypeError, ValueError):
        return None


def normalize_wttr(raw: dict, bundle: dict) -> dict | None:
    try:
        cur = raw["current_condition"][0]
        days = raw["weather"][:7]
        code = int(cur.get("weatherCode") or 2)
        hourly = []
        for day in days:
            for hour in day.get("hourly", []):
                if len(hourly) >= 24:
                    break
                t = int(hour.get("time") or 0)
                hourly.append({"time": f"{t // 100:02d}:00", "temperature": rounded(hour.get("tempC")), "weather_code": int(hour.get("weatherCode") or code), "is_current": not hourly})
        return {
            "current": {"temperature_2m": rounded(cur["temp_C"]), "relative_humidity_2m": rounded(cur.get("humidity")), "apparent_temperature": rounded(cur.get("FeelsLikeC", cur["temp_C"])), "weather_code": code, "wind_speed_10m": rounded(cur.get("windspeedKmph"), 0), "pressure_msl": rounded(cur.get("pressure")), "visibility": rounded(cur.get("visibility"))},
            "air_quality": normalize_air((bundle.get("air_quality") or {}).get("current") or {}),
            "marine": normalize_marine((bundle.get("marine") or {}).get("current") or {}),
            "hourly": hourly,
            "daily": {"time": [d["date"] for d in days], "temperature_2m_max": [rounded(d.get("maxtempC")) for d in days], "temperature_2m_min": [rounded(d.get("mintempC")) for d in days], "weather_code": [int((d.get("hourly") or [{}])[0].get("weatherCode") or code) for d in days], "precipitation_probability_max": [rounded(max(num(h.get("chanceofrain"), 0) or 0 for h in d.get("hourly", [{}])), 0) for d in days]},
            "source": "wttr.in",
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def normalize_7timer(raw: dict, bundle: dict) -> dict | None:
    try:
        series = raw["dataseries"]
        if not series:
            return None
        first = series[0]
        now = datetime.now(timezone.utc)
        hourly = []
        daily_groups: dict[str, list[dict]] = {}
        for item in series:
            hours = int(item.get("timepoint") or 0)
            when = now + timedelta(hours=hours)
            code = SEVEN_CODE.get(str(item.get("weather", "")).lower(), 2)
            temp = rounded(item.get("temp2m"))
            hourly.append({"time": when.strftime("%H:00"), "temperature": temp, "weather_code": code, "is_current": not hourly})
            daily_groups.setdefault(when.strftime("%Y-%m-%d"), []).append({"temp": temp, "code": code})
            if len(hourly) >= 24:
                break
        days = list(daily_groups.items())[:7]
        return {
            "current": {"temperature_2m": rounded(first["temp2m"]), "relative_humidity_2m": None, "apparent_temperature": rounded(first["temp2m"]), "weather_code": SEVEN_CODE.get(str(first.get("weather", "")).lower(), 2), "wind_speed_10m": None, "pressure_msl": None, "visibility": None},
            "air_quality": normalize_air((bundle.get("air_quality") or {}).get("current") or {}),
            "marine": normalize_marine((bundle.get("marine") or {}).get("current") or {}),
            "hourly": hourly,
            "daily": {"time": [d for d, _ in days], "temperature_2m_max": [max(x["temp"] for x in vals) for _, vals in days], "temperature_2m_min": [min(x["temp"] for x in vals) for _, vals in days], "weather_code": [vals[0]["code"] for _, vals in days], "precipitation_probability_max": [0 for _ in days]},
            "source": "7timer",
        }
    except (KeyError, TypeError, ValueError):
        return None


def normalize_air(raw: dict) -> dict:
    return {"available": bool(raw), "us_aqi": rounded(raw.get("us_aqi")) if raw else None, "pm2_5": num(raw.get("pm2_5")) if raw else None, "pm10": num(raw.get("pm10")) if raw else None, "uv_index": num(raw.get("uv_index")) if raw else None}


def normalize_marine(raw: dict) -> dict:
    return {"available": bool(raw), "wave_height": num(raw.get("wave_height"), 0) if raw else None, "wave_period": num(raw.get("wave_period"), 0) if raw else None}


def synthetic_weather(city: dict, reason: str) -> dict:
    if os.environ.get("ALLOW_SYNTHETIC_WEATHER") != "1":
        raise RuntimeError(f"No live weather provider produced usable data for {city['name']}: {reason}")
    temp = int(city.get("base_temp", 20))
    today = datetime.now(timezone.utc)
    return {"current": {"temperature_2m": temp, "relative_humidity_2m": None, "apparent_temperature": temp, "weather_code": 2, "wind_speed_10m": None, "pressure_msl": None, "visibility": None}, "air_quality": {"available": False, "us_aqi": None, "pm2_5": None, "pm10": None, "uv_index": None}, "marine": {"available": False, "wave_height": None, "wave_period": None}, "hourly": [], "daily": {"time": [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)], "temperature_2m_max": [temp] * 7, "temperature_2m_min": [temp] * 7, "weather_code": [2] * 7, "precipitation_probability_max": [0] * 7}, "source": "synthetic-build-fallback", "api_status": [{"source": "synthetic-build-fallback", "ok": "false", "error": reason}]}


def weather_for(city: dict) -> dict:
    if os.environ.get("OFFLINE_BUILD") == "1":
        return synthetic_weather(city, "OFFLINE_BUILD requested")
    bundle = collect_weather(city)
    normalizers = {"open-meteo": normalize_open_meteo, "visual-crossing": normalize_visual_crossing, "wttr.in": normalize_wttr, "7timer": normalize_7timer}
    errors = []
    for candidate in bundle.get("forecast_candidates", []):
        source = candidate.get("source")
        normalizer = normalizers.get(source)
        if not normalizer:
            errors.append(f"{source}: current-only provider cannot render forecast page")
            continue
        normalized = normalizer(candidate.get("data") or {}, bundle)
        if normalized and len(normalized["daily"].get("time", [])) >= 1:
            normalized["api_status"] = bundle.get("api_status", [])
            return normalized
        errors.append(f"{source}: schema normalization failed")
    return synthetic_weather(city, "; ".join(errors) or "all providers failed")


def clothing_index(temp: float, trans: dict, lang_code: str) -> str:
    labels = trans["indices"]["clothing"].get(lang_code) or trans["indices"]["clothing"]["en"]
    if temp < 10:
        return labels[0]
    if temp < 22:
        return labels[1]
    return labels[2]


def uv_index(code: int, trans: dict, lang_code: str) -> str:
    labels = trans["indices"]["uv"].get(lang_code) or trans["indices"]["uv"]["en"]
    if code in (0, 1):
        return labels[0]
    if code in (2, 3):
        return labels[1]
    return labels[2]


def t(trans: dict, lang: str, key: str) -> str:
    return trans["ui"].get(key, {}).get(lang) or trans["ui"].get(key, {}).get("en") or key


def travel_destinations(city: dict, all_cities: list[dict], trans: dict, lang_code: str) -> list[dict]:
    cur = city["weather"]["current"]
    def score(dest: dict) -> tuple[float, str]:
        w = dest["weather"]["current"]
        temp = w["temperature_2m"] or 0
        comfort = abs(temp - 23)
        wind = w.get("wind_speed_10m") or 12
        aqi = dest["weather"].get("air_quality", {}).get("us_aqi") or 50
        return (comfort + wind / 12 + aqi / 75, dest["name"])
    picks = sorted([c for c in all_cities if c["slug"] != city["slug"]], key=score)[:4]
    result = []
    for dest in picks:
        dest_temp = dest["weather"]["current"]["temperature_2m"]
        cur_temp = cur["temperature_2m"]
        diff = dest_temp - cur_temp
        if abs(diff) <= 3:
            diff_text = t(trans, lang_code, "similar")
        elif diff > 0:
            diff_text = f"+{diff}°C {t(trans, lang_code, 'warmer')}"
        else:
            diff_text = f"{diff}°C {t(trans, lang_code, 'cooler')}"
        result.append({"name": f"{dest['name']}, {dest['country']}", "emoji": weather_icon(dest["weather"]["current"].get("weather_code")), "temp": dest_temp, "diff": diff_text, "rating": t(trans, lang_code, "great") if score(dest)[0] <= 7 else t(trans, lang_code, "fair")})
    return result


def alerts_data(all_cities: list[dict], trans: dict, lang_code: str = "en") -> list[dict]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    alerts: list[dict] = []
    for c in all_cities:
        cur = c["weather"]["current"]
        wind = cur.get("wind_speed_10m")
        temp = cur.get("temperature_2m")
        if wind is not None and wind > 30:
            text = f"High Wind Signal: sustained forecast wind speeds reached {wind} km/h. {t(trans, lang_code, 'official_alert_note')}"
            alerts.append({"city": f"{c['name']}, {c['country']}", "slug": c["slug"], "time": now, "text": text, "icon": "💨", "border": "border-red-500", "source": c["weather"].get("source", "")})
        elif temp is not None and temp > 38:
            text = f"Extreme Heat Signal: forecast temperature reached {temp}°C. {t(trans, lang_code, 'official_alert_note')}"
            alerts.append({"city": f"{c['name']}, {c['country']}", "slug": c["slug"], "time": now, "text": text, "icon": "🌡️", "border": "border-orange-500", "source": c["weather"].get("source", "")})
        elif temp is not None and temp < -10:
            text = f"Severe Cold Signal: forecast temperature dropped to {temp}°C. {t(trans, lang_code, 'official_alert_note')}"
            alerts.append({"city": f"{c['name']}, {c['country']}", "slug": c["slug"], "time": now, "text": text, "icon": "❄️", "border": "border-blue-500", "source": c["weather"].get("source", "")})
    return alerts


def wiki_articles(trans: dict, lang_code: str) -> list[dict]:
    config_path = ROOT / "config" / "wiki-articles.json"
    if config_path.exists():
        articles = load_json(config_path).get("articles", [])
    else:
        articles = [
            {"slug": "typhoon-naming", "emoji": "🌀", "asset": "assets/wiki/typhoon-naming.svg", "asset_source": "Generated fallback", "last_reviewed": "", "title": {"en": "Typhoon Naming Rules", "zh": "台风命名规则"}, "description": {"en": "How tropical cyclones get names from regional lists.", "zh": "热带气旋如何来自区域命名清单。"}, "content": {"en": "<p>Typhoon names keep warning communication clear.</p>", "zh": "<p>台风命名让预警沟通更清晰。</p>"}},
            {"slug": "el-nino", "emoji": "🌡️", "asset": "assets/wiki/el-nino.svg", "asset_source": "Generated fallback", "last_reviewed": "", "title": {"en": "El Niño Phenomenon", "zh": "厄尔尼诺现象"}, "description": {"en": "How Pacific warming shifts weather risks.", "zh": "太平洋偏暖如何改变天气风险。"}, "content": {"en": "<p>El Niño changes seasonal weather probabilities.</p>", "zh": "<p>厄尔尼诺会改变季节性天气概率。</p>"}},
            {"slug": "climate-change", "emoji": "📈", "asset": "assets/wiki/climate-change.svg", "asset_source": "Generated fallback", "last_reviewed": "", "title": {"en": "Climate Change Data", "zh": "气候变化数据"}, "description": {"en": "Climate context for weather planning.", "zh": "用于天气规划的气候背景。"}, "content": {"en": "<p>Climate data helps interpret long-term risk.</p>", "zh": "<p>气候数据帮助理解长期风险。</p>"}},
        ]
    normalized = []
    for article in articles:
        normalized.append({
            **article,
            "title": article.get("title", {}).get(lang_code) or article.get("title", {}).get("en") or article.get("slug", ""),
            "description": article.get("description", {}).get(lang_code) or article.get("description", {}).get("en") or "",
            "content": article.get("content", {}).get(lang_code) or article.get("content", {}).get("en") or "",
        })
    return normalized


def render(template_name: str, context: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html", "xml"]))
    env.globals["weather_code_text"] = lambda code: weather_text(code, context["trans"], context["lang_code"])
    env.globals["weather_icon"] = weather_icon
    template = env.get_template(template_name)
    return template.render(**context)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8")


def clean() -> None:
    for item in GENERATED_DIRS + [l["code"] for l in LANGS]:
        target = ROOT / item
        if target.exists():
            shutil.rmtree(target)
    for f in GENERATED_ROOT_FILES:
        p = ROOT / f
        if p.exists():
            p.unlink()


def sync_dist() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)
    for item in ["assets", "city", "wiki", "alert", "data"] + [l["code"] for l in LANGS]:
        src = ROOT / item
        if src.exists():
            shutil.copytree(src, DIST_DIR / item, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    for f in ["index.html", "lang.html", "search.html", "sitemap.xml", "robots.txt", "CNAME", "ads.txt", "site.webmanifest"]:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, DIST_DIR / f)


def common_context(trans: dict, lang: dict, prefix: str, updated: str, page_path: str = "") -> dict:
    code = lang["code"]
    home_href = f"{prefix}/index.html" if code == "en" else f"{prefix}/{code}/index.html"
    return {"lang_code": code, "lang": lang, "languages": LANGS, "trans": trans, "prefix": prefix, "base_url": CONFIG["site_url"], "ga_id": CONFIG["ga_id"], "ads_client": CONFIG["ads_client"], "ads_top_slot": CONFIG["ads_top_slot"], "ads_bottom_slot": CONFIG["ads_bottom_slot"], "updated": updated, "page_path": page_path, "home_href": home_href}


def city_public(c: dict, trans: dict, lang: str) -> dict:
    cur = c["weather"]["current"]
    return {**c, "weather": {"temp": cur["temperature_2m"], "emoji": weather_icon(cur.get("weather_code")), "text": weather_text(cur.get("weather_code") or 0, trans, lang)}}


def build() -> None:
    trans = load_translations()
    previous_weather = load_last_known_weather()
    clean()
    all_cities = cities()
    with ThreadPoolExecutor(max_workers=int(os.environ.get("WEATHER_FETCH_WORKERS", "8"))) as executor:
        future_to_city = {executor.submit(weather_for, c): c for c in all_cities}
        for future in as_completed(future_to_city):
            c = future_to_city[future]
            try:
                c["weather"] = future.result()
            except RuntimeError as exc:
                cached = previous_weather.get(c["slug"])
                if not cached:
                    raise
                c["weather"] = stale_weather(c, cached, exc)

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dynamic_alerts = alerts_data(all_cities, trans, "en")
    hero = city_public(all_cities[0], trans, "en")
    hot = all_cities[:12]

    write(ROOT / "data" / "cities.json", json.dumps(all_cities, ensure_ascii=False, indent=2))
    write(ROOT / "data" / "api-status.json", json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "providers": ["Open-Meteo Forecast", "Open-Meteo Air Quality", "Open-Meteo Marine", "Visual Crossing (optional VISUALCROSSING_KEY)", "7Timer", "wttr.in", "OpenWeatherMap current (optional OPENWEATHER_KEY)", "Weatherbit current (optional WEATHERBIT_KEY)", "Nominatim browser search", "ipapi.co", "ipinfo.io", "IPWho.is", "IPLocate", "WorldTimeAPI", "Buttondown (optional BUTTONDOWN_NEWSLETTER)"], "cities": [{"city": c["name"], "source": c["weather"].get("source"), "status": c["weather"].get("api_status", [])} for c in all_cities]}, ensure_ascii=False, indent=2))
    write(ROOT / "data" / "alerts.json", json.dumps({"alerts": dynamic_alerts, "notice": "Forecast-derived signals only; not official government alerts."}, ensure_ascii=False, indent=2))

    root_ctx = {**common_context(trans, LANGS[0], ".", updated), "hero_live": {"temp": hero["weather"]["temp"], "name": hero["name"], "country": hero["country"], "emoji": hero["weather"]["emoji"]}, "hot_cities": [city_public(c, trans, "en") for c in hot], "cities": all_cities}
    write(ROOT / "index.html", render("index.html", {**root_ctx, "page_path": ""}))
    write(ROOT / "lang.html", render("lang.html", {**root_ctx, "page_path": "lang.html"}))
    write(ROOT / "search.html", render("search.html", {**root_ctx, "page_path": "search.html"}))
    root_sub = {**root_ctx, "prefix": "..", "home_href": "../index.html"}
    root_articles = wiki_articles(trans, "en")
    for article in root_articles:
        related = [a for a in root_articles if a["slug"] != article["slug"]]
        write(ROOT / "wiki" / f"{article['slug']}.html", render("wiki.html", {**root_sub, "page_path": f"wiki/{article['slug']}.html", "title": article["title"], "description": article["description"], "content": article["content"], "image": article.get("asset"), "asset_source": article.get("asset_source"), "last_reviewed": article.get("last_reviewed"), "related": related}))
    write(ROOT / "alert" / "index.html", render("alert.html", {**root_sub, "page_path": "alert/index.html", "alerts": dynamic_alerts}))
    for c in all_cities:
        cur = c["weather"]["current"]
        ctx = {**root_sub, "page_path": f"city/{c['slug']}.html", "city": c, "weather": c["weather"], "current_weather_text": weather_text(cur.get("weather_code") or 0, trans, "en"), "life_indices": {"clothing": clothing_index(cur["temperature_2m"], trans, "en"), "uv": uv_index(cur.get("weather_code") or 0, trans, "en")}, "travel_destinations": travel_destinations(c, all_cities, trans, "en"), "wiki_articles": root_articles}
        write(ROOT / "city" / f"{c['slug']}.html", render("city.html", ctx))

    for lang in LANGS:
        code = lang["code"]
        base = ROOT / code
        base_ctx = {**common_context(trans, lang, "..", updated), "hero_live": {"temp": hero["weather"]["temp"], "name": hero["name"], "country": hero["country"], "emoji": hero["weather"]["emoji"]}, "hot_cities": [city_public(c, trans, code) for c in hot], "cities": all_cities}
        write(base / "index.html", render("index.html", {**base_ctx, "page_path": ""}))
        write(base / "lang.html", render("lang.html", {**base_ctx, "page_path": "lang.html"}))
        write(base / "search.html", render("search.html", {**base_ctx, "page_path": "search.html"}))
        lang_sub = {**base_ctx, "prefix": "../..", "home_href": f"../../{code}/index.html"}
        articles = wiki_articles(trans, code)
        for article in articles:
            related = [a for a in articles if a["slug"] != article["slug"]]
            write(base / "wiki" / f"{article['slug']}.html", render("wiki.html", {**lang_sub, "page_path": f"wiki/{article['slug']}.html", "title": article["title"], "description": article["description"], "content": article["content"], "image": article.get("asset"), "asset_source": article.get("asset_source"), "last_reviewed": article.get("last_reviewed"), "related": related}))
        write(base / "alert" / "index.html", render("alert.html", {**lang_sub, "page_path": "alert/index.html", "alerts": alerts_data(all_cities, trans, code)}))
        for c in all_cities:
            cur = c["weather"]["current"]
            ctx = {**lang_sub, "page_path": f"city/{c['slug']}.html", "city": c, "weather": c["weather"], "current_weather_text": weather_text(cur.get("weather_code") or 0, trans, code), "life_indices": {"clothing": clothing_index(cur["temperature_2m"], trans, code), "uv": uv_index(cur.get("weather_code") or 0, trans, code)}, "travel_destinations": travel_destinations(c, all_cities, trans, code), "wiki_articles": articles}
            write(base / "city" / f"{c['slug']}.html", render("city.html", ctx))

    urls = [f"{CONFIG['site_url']}/", f"{CONFIG['site_url']}/lang.html", f"{CONFIG['site_url']}/search.html", f"{CONFIG['site_url']}/alert/index.html"]
    urls += [f"{CONFIG['site_url']}/city/{c['slug']}.html" for c in all_cities]
    urls += [f"{CONFIG['site_url']}/wiki/{a['slug']}.html" for a in root_articles]
    for lang in LANGS:
        urls += [f"{CONFIG['site_url']}/{lang['code']}/index.html", f"{CONFIG['site_url']}/{lang['code']}/lang.html", f"{CONFIG['site_url']}/{lang['code']}/search.html", f"{CONFIG['site_url']}/{lang['code']}/alert/index.html"]
        urls += [f"{CONFIG['site_url']}/{lang['code']}/city/{c['slug']}.html" for c in all_cities]
        urls += [f"{CONFIG['site_url']}/{lang['code']}/wiki/{a['slug']}.html" for a in root_articles]
    write(ROOT / "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write(ROOT / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {CONFIG['site_url']}/sitemap.xml\n")
    write(ROOT / "CNAME", "weatherindex.xyz\n")
    sync_dist()
    print(f"Generated {len(all_cities)} cities across {len(LANGS)} languages into root and dist")


if __name__ == "__main__":
    build()
