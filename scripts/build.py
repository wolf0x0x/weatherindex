#!/usr/bin/env python3
"""WeatherIndex static site generator.

Reads data/translations.json and templates/*.html, fetches Open-Meteo live data
with an offline fallback model, and emits a multi-language static site ready for
GitHub Pages.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api_clients import collect_weather

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
OUT_DIRS = ["city", "wiki", "alert", "data"]

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

CITY_ROWS = """
Tokyo|Japan|35.6762|139.6503|🗼|Asia/Tokyo|26
New York|USA|40.7128|-74.0060|🗽|America/New_York|22
Paris|France|48.8566|2.3522|🏛️|Europe/Paris|20
Beijing|China|39.9042|116.4074|🏯|Asia/Shanghai|28
London|United Kingdom|51.5074|-0.1278|🎡|Europe/London|18
Shanghai|China|31.2304|121.4737|🌆|Asia/Shanghai|29
Sydney|Australia|-33.8688|151.2093|🌉|Australia/Sydney|19
Dubai|UAE|25.2048|55.2708|🏙️|Asia/Dubai|38
Singapore|Singapore|1.3521|103.8198|🌿|Asia/Singapore|31
Seoul|South Korea|37.5665|126.9780|🏙️|Asia/Seoul|25
Bangkok|Thailand|13.7563|100.5018|🛕|Asia/Bangkok|34
Hong Kong|China|22.3193|114.1694|🌃|Asia/Hong_Kong|30
Los Angeles|USA|34.0522|-118.2437|🌴|America/Los_Angeles|24
San Francisco|USA|37.7749|-122.4194|🌁|America/Los_Angeles|17
Toronto|Canada|43.6532|-79.3832|🍁|America/Toronto|21
Vancouver|Canada|49.2827|-123.1207|⛰️|America/Vancouver|16
Mexico City|Mexico|19.4326|-99.1332|🌵|America/Mexico_City|23
São Paulo|Brazil|-23.5558|-46.6396|🌇|America/Sao_Paulo|22
Rio de Janeiro|Brazil|-22.9068|-43.1729|🏖️|America/Sao_Paulo|27
Buenos Aires|Argentina|-34.6037|-58.3816|💃|America/Argentina/Buenos_Aires|18
Santiago|Chile|-33.4489|-70.6693|🏔️|America/Santiago|17
Lima|Peru|-12.0464|-77.0428|🌊|America/Lima|20
Bogotá|Colombia|4.7110|-74.0721|⛰️|America/Bogota|15
Madrid|Spain|40.4168|-3.7038|🏰|Europe/Madrid|27
Barcelona|Spain|41.3851|2.1734|🎨|Europe/Madrid|26
Rome|Italy|41.9028|12.4964|🏟️|Europe/Rome|28
Milan|Italy|45.4642|9.1900|🛍️|Europe/Rome|25
Berlin|Germany|52.5200|13.4050|🧭|Europe/Berlin|19
Munich|Germany|48.1351|11.5820|⛪|Europe/Berlin|18
Amsterdam|Netherlands|52.3676|4.9041|🚲|Europe/Amsterdam|17
Brussels|Belgium|50.8503|4.3517|🏛️|Europe/Brussels|18
Zurich|Switzerland|47.3769|8.5417|🏔️|Europe/Zurich|16
Vienna|Austria|48.2082|16.3738|🎼|Europe/Vienna|21
Prague|Czech Republic|50.0755|14.4378|🏰|Europe/Prague|20
Warsaw|Poland|52.2297|21.0122|🏙️|Europe/Warsaw|19
Stockholm|Sweden|59.3293|18.0686|🌲|Europe/Stockholm|14
Oslo|Norway|59.9139|10.7522|⛵|Europe/Oslo|13
Copenhagen|Denmark|55.6761|12.5683|🚲|Europe/Copenhagen|16
Helsinki|Finland|60.1699|24.9384|❄️|Europe/Helsinki|12
Dublin|Ireland|53.3498|-6.2603|☘️|Europe/Dublin|15
Lisbon|Portugal|38.7223|-9.1393|🌉|Europe/Lisbon|24
Athens|Greece|37.9838|23.7275|🏛️|Europe/Athens|31
Istanbul|Turkey|41.0082|28.9784|🕌|Europe/Istanbul|26
Moscow|Russia|55.7558|37.6173|🧅|Europe/Moscow|16
Saint Petersburg|Russia|59.9311|30.3609|🎭|Europe/Moscow|14
Cairo|Egypt|30.0444|31.2357|🐪|Africa/Cairo|35
Cape Town|South Africa|-33.9249|18.4241|⛰️|Africa/Johannesburg|18
Johannesburg|South Africa|-26.2041|28.0473|🌇|Africa/Johannesburg|20
Nairobi|Kenya|-1.2921|36.8219|🦒|Africa/Nairobi|22
Lagos|Nigeria|6.5244|3.3792|🌊|Africa/Lagos|29
Casablanca|Morocco|33.5731|-7.5898|🕌|Africa/Casablanca|24
Riyadh|Saudi Arabia|24.7136|46.6753|🏜️|Asia/Riyadh|40
Doha|Qatar|25.2854|51.5310|🌇|Asia/Qatar|39
Tel Aviv|Israel|32.0853|34.7818|🏖️|Asia/Jerusalem|29
Mumbai|India|19.0760|72.8777|🚉|Asia/Kolkata|32
Delhi|India|28.7041|77.1025|🕌|Asia/Kolkata|36
Bengaluru|India|12.9716|77.5946|🌳|Asia/Kolkata|27
Kathmandu|Nepal|27.7172|85.3240|🏔️|Asia/Kathmandu|21
Colombo|Sri Lanka|6.9271|79.8612|🌴|Asia/Colombo|30
Karachi|Pakistan|24.8607|67.0011|🌊|Asia/Karachi|34
Dhaka|Bangladesh|23.8103|90.4125|🚲|Asia/Dhaka|31
Jakarta|Indonesia|-6.2088|106.8456|🌴|Asia/Jakarta|31
Bali|Indonesia|-8.3405|115.0920|🏝️|Asia/Makassar|29
Kuala Lumpur|Malaysia|3.1390|101.6869|🏙️|Asia/Kuala_Lumpur|31
Manila|Philippines|14.5995|120.9842|🌊|Asia/Manila|32
Hanoi|Vietnam|21.0278|105.8342|🌾|Asia/Bangkok|30
Ho Chi Minh City|Vietnam|10.8231|106.6297|🛵|Asia/Ho_Chi_Minh|33
Taipei|Taiwan|25.0330|121.5654|🏙️|Asia/Taipei|29
Osaka|Japan|34.6937|135.5023|🏯|Asia/Tokyo|25
Kyoto|Japan|35.0116|135.7681|⛩️|Asia/Tokyo|24
Melbourne|Australia|-37.8136|144.9631|☕|Australia/Melbourne|16
Brisbane|Australia|-27.4698|153.0251|🌞|Australia/Brisbane|23
Auckland|New Zealand|-36.8485|174.7633|⛵|Pacific/Auckland|15
Honolulu|USA|21.3069|-157.8583|🏝️|Pacific/Honolulu|28
Anchorage|USA|61.2181|-149.9003|🗻|America/Anchorage|9
Chicago|USA|41.8781|-87.6298|🌬️|America/Chicago|21
Miami|USA|25.7617|-80.1918|🏖️|America/New_York|30
Seattle|USA|47.6062|-122.3321|☕|America/Los_Angeles|16
Boston|USA|42.3601|-71.0589|🎓|America/New_York|19
Washington DC|USA|38.9072|-77.0369|🏛️|America/New_York|24
Las Vegas|USA|36.1699|-115.1398|🎰|America/Los_Angeles|35
Denver|USA|39.7392|-104.9903|🏔️|America/Denver|23
Dallas|USA|32.7767|-96.7970|🤠|America/Chicago|32
Houston|USA|29.7604|-95.3698|🚀|America/Chicago|33
Phoenix|USA|33.4484|-112.0740|🌵|America/Phoenix|38
Orlando|USA|28.5383|-81.3792|🎢|America/New_York|31
Montreal|Canada|45.5017|-73.5673|🍁|America/Toronto|18
Quebec City|Canada|46.8139|-71.2080|🏰|America/Toronto|16
Calgary|Canada|51.0447|-114.0719|🏔️|America/Edmonton|14
Reykjavik|Iceland|64.1466|-21.9426|🌋|Atlantic/Reykjavik|8
Edinburgh|United Kingdom|55.9533|-3.1883|🏰|Europe/London|13
Manchester|United Kingdom|53.4808|-2.2426|⚽|Europe/London|15
Nice|France|43.7102|7.2620|🌊|Europe/Paris|25
Lyon|France|45.7640|4.8357|🍽️|Europe/Paris|24
Venice|Italy|45.4408|12.3155|🚤|Europe/Rome|26
Florence|Italy|43.7696|11.2558|🎨|Europe/Rome|27
Budapest|Hungary|47.4979|19.0402|♨️|Europe/Budapest|22
Bucharest|Romania|44.4268|26.1025|🏛️|Europe/Bucharest|24
Belgrade|Serbia|44.7866|20.4489|🌉|Europe/Belgrade|25
Zagreb|Croatia|45.8150|15.9819|🏰|Europe/Zagreb|22
Sofia|Bulgaria|42.6977|23.3219|⛰️|Europe/Sofia|23
Tallinn|Estonia|59.4370|24.7536|🏰|Europe/Tallinn|13
Vilnius|Lithuania|54.6872|25.2797|⛪|Europe/Vilnius|15
Riga|Latvia|56.9496|24.1052|🌲|Europe/Riga|14
""".strip()

ADS_CLIENT = "ca-pub-8695398658548679"
GA_ID = "G-SQCD1J9Y0H"
BASE_URL = "https://weatherindex.xyz"


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def load_translations() -> dict:
    with open(ROOT / "translations.json", encoding="utf-8") as fh:
        return json.load(fh)


def cities() -> list[dict]:
    result = []
    for row in CITY_ROWS.splitlines():
        name, country, lat, lon, emoji, tz, base = row.split("|")
        result.append(
            {
                "name": name,
                "country": country,
                "lat": float(lat),
                "lon": float(lon),
                "emoji": emoji,
                "timezone": tz,
                "base_temp": int(base),
                "slug": slug(name),
            }
        )
    return result


def fetch_open_meteo(city: dict) -> dict | None:
    if os.environ.get("OFFLINE_BUILD") == "1":
        return None
    bundle = collect_weather(city)
    raw = bundle.get("forecast")
    if not raw or bundle.get("forecast_source") != "open-meteo":
        return None

    try:
        cur = raw["current"]
        daily = raw["daily"]
        air_current = (bundle.get("air_quality") or {}).get("current") or {}
        marine_current = (bundle.get("marine") or {}).get("current") or {}
        return {
            "current": {
                "temperature_2m": round(cur["temperature_2m"]),
                "relative_humidity_2m": int(cur["relative_humidity_2m"]),
                "apparent_temperature": round(cur["apparent_temperature"]),
                "weather_code": int(cur["weather_code"]),
                "wind_speed_10m": round(cur["wind_speed_10m"]),
                "pressure_msl": round(cur.get("pressure_msl", 1013)),
                "visibility": round((cur.get("visibility") or 10000) / 1000),
            },
            "air_quality": {
                "us_aqi": int(air_current.get("us_aqi") or 25),
                "pm2_5": round(float(air_current.get("pm2_5") or 8), 1),
                "pm10": round(float(air_current.get("pm10") or 16), 1),
                "uv_index": round(float(air_current.get("uv_index") or 4), 1),
            },
            "marine": {
                "wave_height": round(float(marine_current.get("wave_height") or 0), 1),
                "wave_period": round(float(marine_current.get("wave_period") or 0), 1),
            },
            "daily": {
                "time": [t for t in daily["time"]],
                "temperature_2m_max": [round(x) for x in daily["temperature_2m_max"]],
                "temperature_2m_min": [round(x) for x in daily["temperature_2m_min"]],
                "weather_code": [int(x) for x in daily["weather_code"]],
                "precipitation_probability_max": [
                    int(x) for x in daily.get("precipitation_probability_max", [0] * len(daily["time"]))
                ],
            },
            "source": "open-meteo",
            "api_status": bundle.get("api_status", []),
        }
    except (KeyError, TypeError, ValueError):
        return None


def offline_weather(city: dict) -> dict:
    rnd = random.Random(city["slug"] + datetime.now(timezone.utc).strftime("%Y%m%d%H"))
    code = rnd.choice([0, 1, 2, 3, 61])
    now = city["base_temp"] + rnd.randint(-2, 2)
    days = []
    for i in range(7):
        high = city["base_temp"] + rnd.randint(-3, 4)
        days.append(
            {
                "date": (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d"),
                "high": high,
                "low": high - rnd.randint(5, 10),
                "code": rnd.choice([0, 1, 2, 3, 61]),
            }
        )
    return {
        "current": {
            "temperature_2m": now,
            "relative_humidity_2m": rnd.randint(35, 82),
            "apparent_temperature": now + 2,
            "weather_code": code,
            "wind_speed_10m": rnd.randint(5, 32),
            "pressure_msl": rnd.randint(1002, 1024),
            "visibility": rnd.randint(8, 18),
        },
        "air_quality": {
            "us_aqi": rnd.randint(12, 58),
            "pm2_5": round(rnd.uniform(4, 18), 1),
            "pm10": round(rnd.uniform(10, 35), 1),
            "uv_index": rnd.randint(2, 8),
        },
        "marine": {
            "wave_height": 0,
            "wave_period": 0,
        },
        "daily": {
            "time": [d["date"] for d in days],
            "temperature_2m_max": [d["high"] for d in days],
            "temperature_2m_min": [d["low"] for d in days],
            "weather_code": [d["code"] for d in days],
            "precipitation_probability_max": [rnd.randint(0, 55) for _ in days],
        },
        "source": "offline-model",
        "api_status": [{"source": "offline-model", "ok": "true", "error": ""}],
    }


def weather_for(city: dict) -> dict:
    return fetch_open_meteo(city) or offline_weather(city)


def weather_text(code: int, trans: dict, lang_code: str) -> str:
    return trans["weather_codes"].get(str(code), {}).get(lang_code) or trans["weather_codes"].get(str(code), {}).get("en") or "Partly Cloudy"


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


def travel_destinations(city: dict, all_cities: list[dict]) -> list[dict]:
    rnd = random.Random(city["slug"])
    picks = rnd.sample([c for c in all_cities if c["slug"] != city["slug"]], min(4, len(all_cities) - 1))
    result = []
    for dest in picks:
        dest_temp = dest["weather"]["current"]["temperature_2m"]
        cur_temp = city["weather"]["current"]["temperature_2m"]
        diff = dest_temp - cur_temp
        if abs(diff) <= 3:
            diff_text = "Similar"
        elif diff > 0:
            diff_text = f"+{diff}°C warmer"
        else:
            diff_text = f"{diff}°C cooler"
        result.append(
            {
                "name": f"{dest['name']}, {dest['country']}",
                "emoji": dest["emoji"],
                "temp": dest_temp,
                "diff": diff_text,
                "rating": "Great" if abs(diff) <= 5 else "Fair",
            }
        )
    return result


def alerts_data() -> list[dict]:
    return [
        {
            "city": "Tokyo, Japan",
            "time": "2026-06-11 08:00 UTC",
            "text": "Typhoon Warning - Category 3. Strong winds and heavy rain may affect coastal travel.",
            "icon": "🌀",
            "border": "border-red-500",
        },
        {
            "city": "Delhi, India",
            "time": "2026-06-11 06:00 UTC",
            "text": "Heat wave advisory: temperatures expected to exceed 42°C. Avoid outdoor activity during peak hours.",
            "icon": "🌡️",
            "border": "border-orange-500",
        },
    ]


def wiki_articles() -> list[dict]:
    return [
        {
            "slug": "typhoon-naming",
            "title": "How are typhoons named?",
            "description": "Learn how tropical cyclones get their names from the WMO naming matrix.",
            "emoji": "🌀",
            "content": """
<p>Weather is local at the moment you feel it, but global in the systems that create it. Tropical cyclone names are maintained by regional committees under the World Meteorological Organization so that warnings can be shared clearly across borders and languages.</p>
<h2>Why names matter</h2>
<ul><li>Short, familiar names reduce confusion when multiple storms exist at the same time.</li><li>Each basin uses its own rotating lists, with names retired after particularly deadly or costly events.</li><li>Static, pre-rendered pages keep emergency information fast even during traffic spikes.</li></ul>
<blockquote>Reliable weather communication depends on clear naming, consistent data, and calm presentation during high-impact events.</blockquote>
<h2>Key takeaways</h2>
<ul><li>Names are assigned alphabetically as storms form.</li><li>Forecast data should be refreshed frequently; static pages keep access fast.</li><li>Historical climate signals help explain trends, but daily forecasts still require local observation.</li></ul>
""",
        },
        {
            "slug": "el-nino",
            "title": "What is El Niño?",
            "description": "Why Pacific sea-surface temperature anomalies reshape global weather patterns.",
            "emoji": "🌡️",
            "content": """
<p>El Niño is a warming of the central and eastern tropical Pacific Ocean. It shifts rainfall patterns, influences monsoons, and can raise global average temperatures for months at a time.</p>
<h2>How it affects weather</h2>
<ul><li>Wetter-than-average winters in the southern United States and drier conditions in Australia and Indonesia.</li><li>Weaker Indian monsoon rains in many El Niño years.</li><li>Warmer global mean temperatures due to heat release from the Pacific.</li></ul>
<h2>What to watch</h2>
<ul><li>Sea-surface temperature anomalies in the Niño 3.4 region.</li><li>Atmospheric response, including weaker trade winds and shifting jet streams.</li><li>Local forecasts, because global patterns do not determine every daily outcome.</li></ul>
""",
        },
        {
            "slug": "climate-change",
            "title": "2026 Climate Outlook",
            "description": "A practical look at greenhouse effects on major cities worldwide.",
            "emoji": "📈",
            "content": """
<p>Long-term climate signals show warming, more intense rainfall in some regions, and deeper droughts in others. For travelers and planners, the key is to combine long-term awareness with daily local forecasts.</p>
<h2>What the data shows</h2>
<ul><li>Global average temperatures continue to rise relative to the 20th-century baseline.</li><li>Heat waves are becoming more frequent in many mid-latitude cities.</li><li>Extreme precipitation events are intensifying where moisture is available.</li></ul>
<h2>Practical tips</h2>
<ul><li>Check forecasts close to departure, not just seasonal averages.</li><li>Pack for temperature swings, especially in continental climates.</li><li>Follow official warnings during severe weather rather than relying on general trends.</li></ul>
""",
        },
    ]


def render(template_name: str, context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["weather_code_text"] = lambda code: weather_text(code, context["trans"], context["lang_code"])
    template = env.get_template(template_name)
    return template.render(**context)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
    path.write_text(cleaned, encoding="utf-8")


def clean() -> None:
    for item in OUT_DIRS + [l["code"] for l in LANGS]:
        target = ROOT / item
        if target.exists():
            shutil.rmtree(target)
    for f in ["index.html", "lang.html", "search.html", "sitemap.xml", "robots.txt"]:
        p = ROOT / f
        if p.exists():
            p.unlink()


def build() -> None:
    trans = load_translations()
    clean()
    all_cities = cities()
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_city = {executor.submit(weather_for, c): c for c in all_cities}
        for future in as_completed(future_to_city):
            c = future_to_city[future]
            c["weather"] = future.result()

    # Shared data files
    write(ROOT / "data" / "cities.json", json.dumps(all_cities, ensure_ascii=False, indent=2))
    write(
        ROOT / "data" / "api-status.json",
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "providers": [
                    "Open-Meteo Forecast",
                    "Open-Meteo Air Quality",
                    "Open-Meteo Marine",
                    "OpenWeatherMap (optional OPENWEATHER_KEY)",
                    "Visual Crossing (optional VISUALCROSSING_KEY)",
                    "7Timer",
                    "wttr.in",
                    "Weatherbit (optional WEATHERBIT_KEY)",
                    "ipapi.co",
                    "ipinfo.io",
                    "IPWho.is",
                    "IPLocate",
                    "WorldTimeAPI",
                    "Nominatim",
                    "Buttondown (optional BUTTONDOWN_NEWSLETTER)",
                ],
                "cities": [{"city": c["name"], "status": c["weather"].get("api_status", [])} for c in all_cities],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    write(
        ROOT / "data" / "alerts.json",
        json.dumps({"alerts": alerts_data()}, ensure_ascii=False, indent=2),
    )

    hot_cities = all_cities[:12]
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wiki_list = wiki_articles()

    # Root (default English) pages
    root_context = {
        "lang_code": "en",
        "lang": LANGS[0],
        "languages": LANGS,
        "trans": trans,
        "prefix": ".",
        "ga_id": GA_ID,
        "ads_client": ADS_CLIENT,
        "updated": updated,
        "hot_cities": [{**c, "weather": {"temp": c["weather"]["current"]["temperature_2m"], "emoji": "🌤️", "text": weather_text(c["weather"]["current"]["weather_code"], trans, "en")}} for c in hot_cities],
        "cities": all_cities,
    }
    write(ROOT / "index.html", render("index.html", {**root_context, "page_path": ""}))
    write(ROOT / "lang.html", render("lang.html", {**root_context, "page_path": "lang.html"}))
    write(ROOT / "search.html", render("search.html", {**root_context, "page_path": "search.html"}))

    root_sub_context = {**root_context, "prefix": ".."}

    for article in wiki_list:
        related = [a for a in wiki_list if a["slug"] != article["slug"]]
        ctx = {
            **root_sub_context,
            "page_path": f"wiki/{article['slug']}.html",
            "title": article["title"],
            "description": article["description"],
            "content": article["content"],
            "related": related,
        }
        write(ROOT / "wiki" / f"{article['slug']}.html", render("wiki.html", ctx))

    write(
        ROOT / "alert" / "tokyo-typhoon.html",
        render("alert.html", {**root_sub_context, "page_path": "alert/tokyo-typhoon.html", "alerts": alerts_data()}),
    )

    for c in all_cities:
        ctx = {
            **root_sub_context,
            "page_path": f"city/{c['slug']}.html",
            "city": c,
            "weather": c["weather"],
            "current_weather_text": weather_text(c["weather"]["current"]["weather_code"], trans, "en"),
            "life_indices": {
                "clothing": clothing_index(c["weather"]["current"]["temperature_2m"], trans, "en"),
                "uv": uv_index(c["weather"]["current"]["weather_code"], trans, "en"),
            },
            "travel_destinations": travel_destinations(c, all_cities),
        }
        write(ROOT / "city" / f"{c['slug']}.html", render("city.html", ctx))

    # Per-language pages
    for lang in LANGS:
        code = lang["code"]
        base_ctx = {
            "lang_code": code,
            "lang": lang,
            "languages": LANGS,
            "trans": trans,
            "prefix": "..",
            "ga_id": GA_ID,
            "ads_client": ADS_CLIENT,
            "updated": updated,
            "hot_cities": [{**c, "weather": {"temp": c["weather"]["current"]["temperature_2m"], "emoji": "🌤️", "text": weather_text(c["weather"]["current"]["weather_code"], trans, code)}} for c in hot_cities],
            "cities": all_cities,
        }
        base = ROOT / code
        write(base / "index.html", render("index.html", {**base_ctx, "page_path": ""}))
        write(base / "lang.html", render("lang.html", {**base_ctx, "page_path": "lang.html"}))
        write(base / "search.html", render("search.html", {**base_ctx, "page_path": "search.html"}))

        lang_sub_context = {**base_ctx, "prefix": "../.."}

        for article in wiki_list:
            related = [a for a in wiki_list if a["slug"] != article["slug"]]
            ctx = {
                **lang_sub_context,
                "page_path": f"wiki/{article['slug']}.html",
                "title": article["title"],
                "description": article["description"],
                "content": article["content"],
                "related": related,
            }
            write(base / "wiki" / f"{article['slug']}.html", render("wiki.html", ctx))

        write(
            base / "alert" / "tokyo-typhoon.html",
            render("alert.html", {**lang_sub_context, "page_path": "alert/tokyo-typhoon.html", "alerts": alerts_data()}),
        )

        for c in all_cities:
            ctx = {
                **lang_sub_context,
                "page_path": f"city/{c['slug']}.html",
                "city": c,
                "weather": c["weather"],
                "current_weather_text": weather_text(c["weather"]["current"]["weather_code"], trans, code),
                "life_indices": {
                    "clothing": clothing_index(c["weather"]["current"]["temperature_2m"], trans, code),
                    "uv": uv_index(c["weather"]["current"]["weather_code"], trans, code),
                },
                "travel_destinations": travel_destinations(c, all_cities),
            }
            write(base / "city" / f"{c['slug']}.html", render("city.html", ctx))

    # Sitemap and robots
    urls = [f"{BASE_URL}/", f"{BASE_URL}/lang.html", f"{BASE_URL}/search.html"]
    urls += [f"{BASE_URL}/city/{c['slug']}.html" for c in all_cities]
    urls += [f"{BASE_URL}/wiki/{a['slug']}.html" for a in wiki_list]
    urls.append(f"{BASE_URL}/alert/tokyo-typhoon.html")
    for lang in LANGS:
        urls.append(f"{BASE_URL}/{lang['code']}/index.html")
        urls.append(f"{BASE_URL}/{lang['code']}/lang.html")
        urls.append(f"{BASE_URL}/{lang['code']}/search.html")
        urls += [f"{BASE_URL}/{lang['code']}/city/{c['slug']}.html" for c in all_cities]
        urls += [f"{BASE_URL}/{lang['code']}/wiki/{a['slug']}.html" for a in wiki_list]
        urls.append(f"{BASE_URL}/{lang['code']}/alert/tokyo-typhoon.html")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
        + "</urlset>\n"
    )
    write(ROOT / "sitemap.xml", sitemap)
    write(
        ROOT / "robots.txt",
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n",
    )
    write(ROOT / "CNAME", "weatherindex.xyz\n")

    print(f"Generated {len(all_cities)} cities across {len(LANGS)} languages")


if __name__ == "__main__":
    build()
