#!/usr/bin/env python3
"""Free API integrations for WeatherIndex.

No-key APIs are used directly. Optional free-tier providers are enabled when
matching environment variables are present. All provider responses stay raw here;
the static generator decides which schemas can safely power production pages.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

SITE_URL = os.environ.get("SITE_URL", "https://weatherindex.xyz").rstrip("/")
USER_AGENT = os.environ.get("WEATHERINDEX_USER_AGENT", f"WeatherIndex/1.0 ({SITE_URL})")


@dataclass
class ApiResult:
    source: str
    data: dict[str, Any] | list[Any] | None
    ok: bool
    error: str = ""


def _get_json(url: str, *, timeout: int = 12, headers: dict[str, str] | None = None) -> ApiResult:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return ApiResult(url, json.loads(res.read().decode("utf-8")), True)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return ApiResult(url, None, False, str(exc))


def open_meteo_forecast(lat: float, lon: float) -> ApiResult:
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,pressure_msl,visibility",
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "timezone": "auto",
            "forecast_days": "7",
        }
    )
    result = _get_json(f"https://api.open-meteo.com/v1/forecast?{params}")
    result.source = "open-meteo"
    return result


def open_meteo_air_quality(lat: float, lon: float) -> ApiResult:
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "european_aqi,us_aqi,pm10,pm2_5,uv_index",
            "timezone": "auto",
        }
    )
    result = _get_json(f"https://air-quality-api.open-meteo.com/v1/air-quality?{params}")
    result.source = "open-meteo-air-quality"
    return result


def open_meteo_marine(lat: float, lon: float) -> ApiResult:
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "wave_height,wave_direction,wave_period",
            "timezone": "auto",
        }
    )
    result = _get_json(f"https://marine-api.open-meteo.com/v1/marine?{params}")
    result.source = "open-meteo-marine"
    return result


def openweather_current(lat: float, lon: float) -> ApiResult:
    key = os.environ.get("OPENWEATHER_KEY") or os.environ.get("OPENWEATHER_API_KEY")
    if not key:
        return ApiResult("openweather", None, False, "OPENWEATHER_KEY not configured")
    params = urllib.parse.urlencode({"lat": lat, "lon": lon, "appid": key, "units": "metric"})
    result = _get_json(f"https://api.openweathermap.org/data/2.5/weather?{params}")
    result.source = "openweather"
    return result


def visual_crossing_timeline(city_name: str) -> ApiResult:
    key = os.environ.get("VISUALCROSSING_KEY") or os.environ.get("VISUAL_CROSSING_KEY")
    if not key:
        return ApiResult("visual-crossing", None, False, "VISUALCROSSING_KEY not configured")
    location = urllib.parse.quote(city_name)
    params = urllib.parse.urlencode({"unitGroup": "metric", "include": "days,current,hours", "key": key, "contentType": "json"})
    result = _get_json(f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}?{params}")
    result.source = "visual-crossing"
    return result


def seven_timer_forecast(lat: float, lon: float) -> ApiResult:
    params = urllib.parse.urlencode({"lon": lon, "lat": lat, "product": "civil", "output": "json"})
    result = _get_json(f"https://www.7timer.info/bin/api.pl?{params}")
    result.source = "7timer"
    return result


def wttr_current(city_name: str) -> ApiResult:
    city = urllib.parse.quote(city_name)
    result = _get_json(f"https://wttr.in/{city}?format=j1")
    result.source = "wttr.in"
    return result


def weatherbit_current(lat: float, lon: float) -> ApiResult:
    key = os.environ.get("WEATHERBIT_KEY") or os.environ.get("WEATHERBIT_API_KEY")
    if not key:
        return ApiResult("weatherbit", None, False, "WEATHERBIT_KEY not configured")
    params = urllib.parse.urlencode({"lat": lat, "lon": lon, "key": key})
    result = _get_json(f"https://api.weatherbit.io/v2.0/current?{params}")
    result.source = "weatherbit"
    return result


def ip_location() -> ApiResult:
    for name, url in [
        ("ipapi.co", "https://ipapi.co/json/"),
        ("ipinfo.io", "https://ipinfo.io/json"),
        ("ipwho.is", "https://ipwho.is/"),
        ("iplocate.io", "https://iplocate.io/api/lookup/"),
    ]:
        result = _get_json(url, timeout=8)
        result.source = name
        if result.ok:
            return result
    return ApiResult("ip-location", None, False, "all IP location providers failed")


def world_time(timezone: str) -> ApiResult:
    tz = urllib.parse.quote(timezone, safe="/")
    result = _get_json(f"https://worldtimeapi.org/api/timezone/{tz}", timeout=8)
    result.source = "worldtimeapi"
    return result


def nominatim_search(query: str) -> ApiResult:
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 5})
    time.sleep(1)
    result = _get_json(f"https://nominatim.openstreetmap.org/search?{params}", headers={"Accept-Language": "en"})
    result.source = "nominatim"
    return result


def buttondown_subscribe_endpoint() -> dict[str, str]:
    slug = os.environ.get("BUTTONDOWN_NEWSLETTER")
    return {
        "provider": "buttondown",
        "enabled": "true" if slug else "false",
        "endpoint": f"https://buttondown.email/api/emails/{slug}" if slug else "",
    }


def _record(api_status: list[dict[str, str]], result: ApiResult) -> None:
    api_status.append({"source": result.source, "ok": str(result.ok).lower(), "error": result.error})


def collect_weather(city: dict[str, Any]) -> dict[str, Any]:
    """Collect weather data with complete provider status and safe fallback metadata."""
    lat = float(city["lat"])
    lon = float(city["lon"])
    api_status: list[dict[str, str]] = []
    forecast_candidates: list[dict[str, Any]] = []

    providers: list[Callable[[], ApiResult]] = [
        lambda: open_meteo_forecast(lat, lon),
        lambda: visual_crossing_timeline(city["name"]),
        lambda: seven_timer_forecast(lat, lon),
        lambda: wttr_current(city["name"]),
        lambda: openweather_current(lat, lon),
        lambda: weatherbit_current(lat, lon),
    ]
    full_forecast_sources = {"open-meteo", "visual-crossing", "7timer", "wttr.in"}
    for provider in providers:
        result = provider()
        _record(api_status, result)
        if result.ok and isinstance(result.data, dict):
            forecast_candidates.append({"source": result.source, "data": result.data})
            if result.source in full_forecast_sources:
                break

    air = open_meteo_air_quality(lat, lon)
    _record(api_status, air)

    marine = open_meteo_marine(lat, lon)
    _record(api_status, marine)

    return {
        "forecast_candidates": forecast_candidates,
        "air_quality": air.data if air.ok else None,
        "marine": marine.data if marine.ok else None,
        "api_status": api_status,
    }
