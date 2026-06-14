#!/usr/bin/env python3
"""Free API integrations for WeatherIndex.

No-key APIs are used directly. Free-tier APIs that require keys are enabled
only when their environment variables are present, so local and GitHub Actions
builds remain reliable without secrets.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


USER_AGENT = "WeatherIndex/1.0 (https://weatherindex.xyz)"


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
    params = urllib.parse.urlencode({"unitGroup": "metric", "include": "days,current", "key": key, "contentType": "json"})
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
    params = urllib.parse.urlencode({"lat": lat, "lon": lon, "key": key, "include": "minutely"})
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
    # Nominatim asks clients to keep requests modest. This helper is not used in
    # bulk generation; it exists for diagnostics and one-off enrichment.
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


def collect_weather(city: dict[str, Any]) -> dict[str, Any]:
    """Collect weather data with multi-provider fallback metadata."""
    lat = float(city["lat"])
    lon = float(city["lon"])
    api_status: list[dict[str, str]] = []

    forecast = open_meteo_forecast(lat, lon)
    api_status.append({"source": forecast.source, "ok": str(forecast.ok).lower(), "error": forecast.error})
    if not forecast.ok:
        for fallback in (
            openweather_current(lat, lon),
            visual_crossing_timeline(city["name"]),
            seven_timer_forecast(lat, lon),
            wttr_current(city["name"]),
            weatherbit_current(lat, lon),
        ):
            api_status.append({"source": fallback.source, "ok": str(fallback.ok).lower(), "error": fallback.error})
            if fallback.ok:
                forecast = fallback
                break

    air = open_meteo_air_quality(lat, lon)
    api_status.append({"source": air.source, "ok": str(air.ok).lower(), "error": air.error})

    marine = open_meteo_marine(lat, lon)
    api_status.append({"source": marine.source, "ok": str(marine.ok).lower(), "error": marine.error})

    return {
        "forecast": forecast.data if forecast.ok else None,
        "forecast_source": forecast.source if forecast.ok else "",
        "air_quality": air.data if air.ok else None,
        "marine": marine.data if marine.ok else None,
        "api_status": api_status,
    }
