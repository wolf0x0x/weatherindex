#!/usr/bin/env python3
"""Daily WeatherIndex maintenance.

Runs scheduled data/API health checks, refreshes weather-wiki article metadata,
downloads required article assets, and writes a machine-readable maintenance
report for GitHub Actions and published diagnostics.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
ASSET_DIR = ROOT / "assets" / "wiki"
DATA_DIR = ROOT / "data"

# Public-domain / freely reusable sources. Download URLs are intentionally kept
# in config output so the site has a traceable asset provenance.
WIKI_ARTICLE_SEEDS = [
    {
        "slug": "typhoon-naming",
        "emoji": "🌀",
        "asset": "assets/wiki/typhoon-naming.svg",
        "asset_url": "https://upload.wikimedia.org/wikipedia/commons/4/49/Hurricane_warning_icon.svg",
        "asset_source": "Wikimedia Commons hurricane symbol",
        "title": {"en": "Typhoon Naming Rules", "zh": "台风命名规则"},
        "description": {
            "en": "How tropical cyclones are named, retired, and communicated across regions.",
            "zh": "了解热带气旋如何命名、退役以及跨区域传播预警信息。",
        },
        "content": {
            "en": "<p>Typhoon names are maintained by regional meteorological committees so warnings stay clear across countries and languages.</p><h2>Core rules</h2><ul><li>Names come from rotating regional lists, not from a single country.</li><li>Names may be retired after storms cause severe loss or exceptional impact.</li><li>Forecast users should pair name-based alerts with local official warnings and live weather data.</li></ul><h2>Why it matters</h2><p>Consistent naming helps emergency managers, media, and travelers distinguish active storms quickly when multiple systems exist at the same time.</p>",
            "zh": "<p>台风名称通常由区域气象委员会维护，目的是让跨国家、跨语言的预警沟通更清晰。</p><h2>核心规则</h2><ul><li>名称来自轮换区域清单，并非由单一国家决定。</li><li>造成重大损失或特殊影响的名称可能被退役。</li><li>用户应把台风名称信息与当地官方预警和实时天气数据结合使用。</li></ul><h2>为什么重要</h2><p>稳定的命名体系能帮助应急部门、媒体和旅行者在多个风暴同时存在时快速区分风险。</p>",
        },
    },
    {
        "slug": "el-nino",
        "emoji": "🌡️",
        "asset": "assets/wiki/el-nino.png",
        "asset_url": "https://upload.wikimedia.org/wikipedia/commons/b/b7/El_Nino_regional_impacts.png",
        "asset_source": "Wikimedia Commons El Niño schematic",
        "title": {"en": "El Niño Phenomenon", "zh": "厄尔尼诺现象"},
        "description": {
            "en": "How Pacific sea-surface warming changes rainfall, monsoon, and seasonal weather risks.",
            "zh": "太平洋海温异常偏暖如何影响降雨、季风与季节性天气风险。",
        },
        "content": {
            "en": "<p>El Niño is a recurring warming of the central and eastern tropical Pacific. It changes atmospheric circulation and can shift weather risks far beyond the Pacific basin.</p><h2>Signals to track</h2><ul><li>Sea-surface temperature anomalies in the Niño 3.4 region.</li><li>Trade wind weakening and convection moving eastward.</li><li>Regional rainfall and temperature departures from seasonal normals.</li></ul><h2>Planning note</h2><p>El Niño shapes seasonal probabilities; day-to-day decisions still require local forecasts.</p>",
            "zh": "<p>厄尔尼诺是中东太平洋热带海域周期性偏暖现象，会改变大气环流，并把天气风险影响扩展到太平洋以外地区。</p><h2>重点观测信号</h2><ul><li>Niño 3.4 区域海表温度距平。</li><li>信风减弱以及对流区东移。</li><li>各地区降雨和气温相对季节常年的偏离。</li></ul><h2>使用提示</h2><p>厄尔尼诺影响的是季节概率，日常出行仍需查看本地实时预报。</p>",
        },
    },
    {
        "slug": "climate-change",
        "emoji": "📈",
        "asset": "assets/wiki/climate-change.svg",
        "asset_url": "https://upload.wikimedia.org/wikipedia/commons/f/f8/Global_Temperature_Anomaly.svg",
        "asset_source": "Wikimedia Commons global temperature anomaly chart",
        "title": {"en": "Climate Change Data", "zh": "气候变化数据"},
        "description": {
            "en": "A practical weather-data lens on warming, heavy rainfall, drought, and urban risk.",
            "zh": "从天气数据角度理解升温、强降雨、干旱与城市风险。",
        },
        "content": {
            "en": "<p>Climate change data combines long-term observations with near-real-time weather monitoring. WeatherIndex treats climate context as background information, while city pages remain driven by live forecast APIs.</p><h2>Data points to watch</h2><ul><li>Temperature anomalies against a historical baseline.</li><li>Frequency and duration of heat waves in major cities.</li><li>Extreme rainfall intensity and drought persistence.</li></ul><h2>How to use it</h2><p>Use climate data for trend awareness and risk planning, then use local forecasts for daily decisions.</p>",
            "zh": "<p>气候变化数据把长期观测与近实时天气监测结合起来。WeatherIndex 将气候内容作为背景知识，城市页面仍以实时预报 API 为核心。</p><h2>重点数据</h2><ul><li>相对历史基准的气温距平。</li><li>主要城市热浪的频率和持续时间。</li><li>极端降雨强度与干旱持续性。</li></ul><h2>如何使用</h2><p>气候数据适合趋势认知和风险规划，日常决策仍应查看本地预报。</p>",
        },
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fallback_svg(slug: str, emoji: str, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" role="img" aria-label="{title}">
  <defs><linearGradient id="sky" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#0ea5e9"/><stop offset="0.55" stop-color="#22c55e"/><stop offset="1" stop-color="#f8fafc"/></linearGradient></defs>
  <rect width="1200" height="630" fill="url(#sky)"/>
  <circle cx="235" cy="178" r="98" fill="#fef08a" opacity="0.96"/>
  <circle cx="880" cy="300" r="170" fill="#ffffff" opacity="0.26"/>
  <circle cx="760" cy="330" r="118" fill="#ffffff" opacity="0.22"/>
  <text x="600" y="330" text-anchor="middle" font-size="154" font-family="Arial, sans-serif">{emoji}</text>
  <path d="M0 505 C160 455 270 545 430 493 C600 438 710 538 900 490 C1035 455 1125 480 1200 450 L1200 630 L0 630 Z" fill="#0369a1" opacity="0.26"/>
  <metadata>Generated fallback asset for {slug}</metadata>
</svg>"""


def download_asset(article: dict[str, Any]) -> dict[str, str]:
    target = ROOT / article["asset"]
    target.parent.mkdir(parents=True, exist_ok=True)
    url = article["asset_url"]
    result = {"slug": article["slug"], "path": article["asset"], "url": url, "status": "downloaded", "error": ""}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WeatherIndexBot/1.0 (https://weatherindex.xyz)"})
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = response.read()
        if len(payload) < 200:
            raise ValueError("asset payload too small")
        target.write_bytes(payload)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        target.write_text(fallback_svg(article["slug"], article["emoji"], article["title"]["en"]), encoding="utf-8")
        result["status"] = "fallback-generated"
        result["error"] = str(exc)
    return result


def prepare_wiki_assets() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    refreshed = []
    assets = []
    reviewed = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for item in WIKI_ARTICLE_SEEDS:
        article = dict(item)
        article["last_reviewed"] = reviewed
        refreshed.append(article)
        assets.append(download_asset(article))
    payload = {"generated_at": now_iso(), "articles": refreshed}
    write_json(CONFIG_DIR / "wiki-articles.json", payload)
    return {"articles": len(refreshed), "assets": assets}


def audit_static_inputs() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    city_path = CONFIG_DIR / "city-seeds.json"
    wiki_path = CONFIG_DIR / "wiki-articles.json"
    checks.append({"name": "city-seeds", "ok": str(city_path.exists()).lower(), "detail": str(city_path)})
    checks.append({"name": "wiki-articles", "ok": str(wiki_path.exists()).lower(), "detail": str(wiki_path)})
    if city_path.exists():
        rows = json.loads(city_path.read_text(encoding="utf-8"))
        checks.append({"name": "city-count", "ok": str(len(rows) >= 100).lower(), "detail": str(len(rows))})
        missing = [row.get("name", "") for row in rows if not all(k in row for k in ("name", "country", "lat", "lon", "timezone", "slug"))]
        checks.append({"name": "city-required-fields", "ok": str(not missing).lower(), "detail": ", ".join(missing[:5])})
    if wiki_path.exists():
        payload = json.loads(wiki_path.read_text(encoding="utf-8"))
        articles = payload.get("articles", [])
        expected = {"typhoon-naming", "el-nino", "climate-change"}
        found = {a.get("slug") for a in articles}
        checks.append({"name": "wiki-required-topics", "ok": str(expected <= found).lower(), "detail": ", ".join(sorted(found))})
        for article in articles:
            asset = ROOT / article.get("asset", "")
            checks.append({"name": f"asset:{article.get('slug')}", "ok": str(asset.exists() and asset.stat().st_size > 200).lower(), "detail": str(asset)})
    return checks


def audit_api_samples() -> list[dict[str, str]]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from api_clients import open_meteo_air_quality, open_meteo_forecast, open_meteo_marine

    sample_points = [
        ("Tokyo", 35.6762, 139.6503),
        ("London", 51.5074, -0.1278),
        ("New York", 40.7128, -74.0060),
        ("Sydney", -33.8688, 151.2093),
        ("Sao Paulo", -23.5558, -46.6396),
    ]
    results: list[dict[str, str]] = []
    for name, lat, lon in sample_points:
        forecast = open_meteo_forecast(lat, lon)
        results.append({"name": f"open-meteo:{name}", "ok": str(forecast.ok).lower(), "detail": forecast.error})
    aq = open_meteo_air_quality(35.6762, 139.6503)
    marine = open_meteo_marine(35.6762, 139.6503)
    results.append({"name": "open-meteo-air-quality:Tokyo", "ok": str(aq.ok).lower(), "detail": aq.error})
    results.append({"name": "open-meteo-marine:Tokyo", "ok": str(marine.ok).lower(), "detail": marine.error})
    return results


def refresh_last_known_cache() -> dict[str, Any]:
    current_path = DATA_DIR / "cities.json"
    cache_path = CONFIG_DIR / "last-known-cities.json"
    if not current_path.exists():
        return {"updated": False, "reason": "data/cities.json missing"}
    rows = json.loads(current_path.read_text(encoding="utf-8"))
    existing = []
    if cache_path.exists():
        existing = json.loads(cache_path.read_text(encoding="utf-8"))
    by_slug = {row.get("slug"): row for row in existing if row.get("slug")}
    live_count = 0
    for row in rows:
        source = (row.get("weather") or {}).get("source", "")
        if source and not source.startswith("stale-") and not source.startswith("synthetic"):
            by_slug[row["slug"]] = row
            live_count += 1
    merged = [by_slug.get(row.get("slug"), row) for row in rows]
    write_json(cache_path, merged)
    return {"updated": True, "live_entries": live_count, "total": len(rows)}


def audit_generated_data() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    status_path = DATA_DIR / "api-status.json"
    cities_path = DATA_DIR / "cities.json"
    if not status_path.exists() or not cities_path.exists():
        return [{"name": "generated-data", "ok": "false", "detail": "data files missing"}]
    status = json.loads(status_path.read_text(encoding="utf-8"))
    cities = json.loads(cities_path.read_text(encoding="utf-8"))
    stale = [c for c in status.get("cities", []) if str(c.get("source", "")).startswith("stale-")]
    live = [c for c in status.get("cities", []) if c.get("source") and not str(c.get("source", "")).startswith("stale-")]
    checks.append({"name": "generated-city-count", "ok": str(len(cities) >= 100).lower(), "detail": str(len(cities))})
    live_ratio = len(live) / max(1, len(cities))
    severity = "ok" if live_ratio >= 0.8 else "warning" if live_ratio >= 0.5 else "critical"
    checks.append({"name": "live-weather-coverage", "ok": str(live_ratio >= 0.5).lower(), "severity": severity, "detail": f"live={len(live)} stale={len(stale)} ratio={live_ratio:.2f}"})
    missing_daily = [c.get("name", c.get("slug", "")) for c in cities if len(((c.get("weather") or {}).get("daily") or {}).get("time", [])) < 1]
    checks.append({"name": "daily-forecast-present", "ok": str(not missing_daily).lower(), "detail": ", ".join(missing_daily[:5])})
    return checks


def write_report(stage: str, payload: dict[str, Any]) -> int:
    all_checks = payload.get("input_checks", []) + payload.get("api_checks", []) + payload.get("generated_checks", [])
    failing = [check for check in all_checks if check.get("ok") != "true"]
    warnings = [check for check in all_checks if check.get("severity") == "warning"]
    report = {"stage": stage, "generated_at": now_iso(), "issue_count": len(failing), "warning_count": len(warnings), "issues": failing, "warnings": warnings, **payload}
    write_json(DATA_DIR / "maintenance-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Asset source outages can be healed with generated fallbacks, so they are
    # recorded but not treated as a deployment blocker. API and data failures are.
    blockers = [issue for issue in failing if not issue.get("name", "").startswith("asset:")]
    return 1 if blockers else 0


def prepare() -> int:
    assets = prepare_wiki_assets()
    input_checks = audit_static_inputs()
    api_checks = audit_api_samples()
    return write_report("prepare", {"asset_refresh": assets, "input_checks": input_checks, "api_checks": api_checks})


def audit() -> int:
    cache = refresh_last_known_cache()
    input_checks = audit_static_inputs()
    generated_checks = audit_generated_data()
    return write_report("audit", {"cache_refresh": cache, "input_checks": input_checks, "generated_checks": generated_checks})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", help="refresh wiki content/assets and run pre-build API checks")
    parser.add_argument("--audit", action="store_true", help="audit generated data after build and refresh last-known cache")
    args = parser.parse_args()
    if args.prepare:
        return prepare()
    if args.audit:
        return audit()
    pre = prepare()
    return pre or audit()


if __name__ == "__main__":
    raise SystemExit(main())
