#!/usr/bin/env python3
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
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = ["city", "wiki", "alert", "data"]
LANGS = [
    {"code": "en", "flag": "🇺🇸", "name": "English", "native": "Weather", "dir": "ltr"},
    {"code": "es", "flag": "🇪🇸", "name": "Español", "native": "Clima", "dir": "ltr"},
    {"code": "fr", "flag": "🇫🇷", "name": "Français", "native": "Météo", "dir": "ltr"},
    {"code": "de", "flag": "🇩🇪", "name": "Deutsch", "native": "Wetter", "dir": "ltr"},
    {"code": "ja", "flag": "🇯🇵", "name": "日本語", "native": "天気", "dir": "ltr"},
    {"code": "ru", "flag": "🇷🇺", "name": "Русский", "native": "Погода", "dir": "ltr"},
    {"code": "kr", "flag": "🇰🇷", "name": "한국어", "native": "날씨", "dir": "ltr"},
    {"code": "ar", "flag": "🇸🇦", "name": "العربية", "native": "الطقس", "dir": "rtl"},
]

T = {
    "en": {
        "brand": "GlobalWeather", "tagline": "Real-time forecasts for 100+ cities worldwide",
        "search": "Search city...", "locate": "Locate Me", "hot": "Hot Cities",
        "features": "Built for global weather checks", "global": "Global Coverage",
        "realtime": "Real-time Updates", "static": "Static & Fast",
        "city_weather": "{city} Weather", "feels": "Feels Like", "humidity": "Humidity",
        "wind": "Wind", "pressure": "Pressure", "visibility": "Visibility",
        "hourly": "24-Hour Forecast", "daily": "7-Day Forecast", "life": "Life Index",
        "travel": "Travel Weather", "knowledge": "Weather Knowledge",
        "alert": "Severe Weather Alert", "view": "View Weather", "read": "Read",
        "language": "Language", "select_language": "Select Your Language",
        "results": "Search Results", "no_results": "No cities found. Try another search.",
        "updated": "Last updated", "data": "Data: Open-Meteo with offline fallback",
    },
    "es": {"brand": "GlobalWeather", "tagline": "Pronósticos en tiempo real para 100+ ciudades", "search": "Buscar ciudad...", "locate": "Ubicarme", "hot": "Ciudades populares", "features": "Clima global al instante", "global": "Cobertura global", "realtime": "Actualizaciones reales", "static": "Estático y rápido", "city_weather": "Clima en {city}", "feels": "Sensación", "humidity": "Humedad", "wind": "Viento", "pressure": "Presión", "visibility": "Visibilidad", "hourly": "Pronóstico 24 horas", "daily": "Pronóstico 7 días", "life": "Índice de vida", "travel": "Clima de viaje", "knowledge": "Conocimiento meteorológico", "alert": "Alerta meteorológica", "view": "Ver clima", "read": "Leer", "language": "Idioma", "select_language": "Selecciona tu idioma", "results": "Resultados", "no_results": "No se encontraron ciudades.", "updated": "Actualizado", "data": "Datos: Open-Meteo con respaldo offline"},
    "fr": {"brand": "GlobalWeather", "tagline": "Prévisions en temps réel pour plus de 100 villes", "search": "Rechercher une ville...", "locate": "Me localiser", "hot": "Villes populaires", "features": "Météo mondiale claire", "global": "Couverture mondiale", "realtime": "Mises à jour réelles", "static": "Statique et rapide", "city_weather": "Météo à {city}", "feels": "Ressenti", "humidity": "Humidité", "wind": "Vent", "pressure": "Pression", "visibility": "Visibilité", "hourly": "Prévision 24 h", "daily": "Prévision 7 jours", "life": "Indices de vie", "travel": "Météo voyage", "knowledge": "Culture météo", "alert": "Alerte météo", "view": "Voir", "read": "Lire", "language": "Langue", "select_language": "Choisissez votre langue", "results": "Résultats", "no_results": "Aucune ville trouvée.", "updated": "Mis à jour", "data": "Données: Open-Meteo avec secours offline"},
    "de": {"brand": "GlobalWeather", "tagline": "Echtzeitprognosen für über 100 Städte", "search": "Stadt suchen...", "locate": "Standort", "hot": "Beliebte Städte", "features": "Wetter weltweit", "global": "Globale Abdeckung", "realtime": "Aktuelle Updates", "static": "Statisch & schnell", "city_weather": "Wetter in {city}", "feels": "Gefühlt", "humidity": "Feuchte", "wind": "Wind", "pressure": "Druck", "visibility": "Sicht", "hourly": "24-Stunden-Prognose", "daily": "7-Tage-Prognose", "life": "Lebensindex", "travel": "Reisewetter", "knowledge": "Wetterwissen", "alert": "Unwetterwarnung", "view": "Wetter ansehen", "read": "Lesen", "language": "Sprache", "select_language": "Sprache wählen", "results": "Suchergebnisse", "no_results": "Keine Städte gefunden.", "updated": "Aktualisiert", "data": "Daten: Open-Meteo mit Offline-Fallback"},
    "ja": {"brand": "GlobalWeather", "tagline": "世界100都市以上のリアルタイム予報", "search": "都市を検索...", "locate": "現在地", "hot": "人気都市", "features": "世界の天気を高速表示", "global": "世界対応", "realtime": "リアルタイム更新", "static": "静的で高速", "city_weather": "{city}の天気", "feels": "体感", "humidity": "湿度", "wind": "風速", "pressure": "気圧", "visibility": "視程", "hourly": "24時間予報", "daily": "7日間予報", "life": "生活指数", "travel": "旅行天気", "knowledge": "天気知識", "alert": "気象警報", "view": "天気を見る", "read": "読む", "language": "言語", "select_language": "言語を選択", "results": "検索結果", "no_results": "都市が見つかりません。", "updated": "更新", "data": "データ: Open-Meteo / オフライン予備"},
    "ru": {"brand": "GlobalWeather", "tagline": "Прогнозы в реальном времени для 100+ городов", "search": "Найти город...", "locate": "Моё место", "hot": "Популярные города", "features": "Погода по всему миру", "global": "Глобальный охват", "realtime": "Живые обновления", "static": "Статично и быстро", "city_weather": "Погода: {city}", "feels": "Ощущается", "humidity": "Влажность", "wind": "Ветер", "pressure": "Давление", "visibility": "Видимость", "hourly": "Прогноз на 24 часа", "daily": "Прогноз на 7 дней", "life": "Индексы", "travel": "Погода в поездке", "knowledge": "Знания о погоде", "alert": "Штормовое предупреждение", "view": "Смотреть", "read": "Читать", "language": "Язык", "select_language": "Выберите язык", "results": "Результаты поиска", "no_results": "Города не найдены.", "updated": "Обновлено", "data": "Данные: Open-Meteo и офлайн-резерв"},
    "kr": {"brand": "GlobalWeather", "tagline": "전 세계 100개 이상 도시 실시간 예보", "search": "도시 검색...", "locate": "내 위치", "hot": "인기 도시", "features": "빠른 글로벌 날씨", "global": "전 세계 커버", "realtime": "실시간 업데이트", "static": "정적·고속", "city_weather": "{city} 날씨", "feels": "체감", "humidity": "습도", "wind": "바람", "pressure": "기압", "visibility": "가시거리", "hourly": "24시간 예보", "daily": "7일 예보", "life": "생활 지수", "travel": "여행 날씨", "knowledge": "날씨 지식", "alert": "기상 경보", "view": "날씨 보기", "read": "읽기", "language": "언어", "select_language": "언어 선택", "results": "검색 결과", "no_results": "도시를 찾을 수 없습니다.", "updated": "업데이트", "data": "데이터: Open-Meteo 및 오프라인 예비"},
    "ar": {"brand": "GlobalWeather", "tagline": "توقعات فورية لأكثر من 100 مدينة حول العالم", "search": "ابحث عن مدينة...", "locate": "موقعي", "hot": "مدن رائجة", "features": "طقس عالمي سريع", "global": "تغطية عالمية", "realtime": "تحديثات فورية", "static": "ثابت وسريع", "city_weather": "طقس {city}", "feels": "المحسوسة", "humidity": "الرطوبة", "wind": "الرياح", "pressure": "الضغط", "visibility": "الرؤية", "hourly": "توقعات 24 ساعة", "daily": "توقعات 7 أيام", "life": "مؤشرات الحياة", "travel": "طقس السفر", "knowledge": "معرفة الطقس", "alert": "تنبيه طقس شديد", "view": "عرض الطقس", "read": "اقرأ", "language": "اللغة", "select_language": "اختر لغتك", "results": "نتائج البحث", "no_results": "لم يتم العثور على مدن.", "updated": "آخر تحديث", "data": "البيانات: Open-Meteo مع بديل دون اتصال"},
}

WEATHER = {
    0: ("Clear Sky", "sunny", "☀️"), 1: ("Mainly Clear", "clear_day", "🌤️"), 2: ("Partly Cloudy", "partly_cloudy_day", "⛅"),
    3: ("Overcast", "cloud", "☁️"), 45: ("Fog", "foggy", "🌫️"), 51: ("Drizzle", "rainy_light", "🌦️"),
    61: ("Rain", "rainy", "🌧️"), 63: ("Rain", "rainy", "🌧️"), 80: ("Showers", "rainy", "🌧️"),
    95: ("Thunderstorm", "thunderstorm", "⛈️"),
}

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


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def cities() -> list[dict]:
    result = []
    for row in CITY_ROWS.splitlines():
        name, country, lat, lon, emoji, tz, base = row.split("|")
        result.append({
            "name": name, "country": country, "lat": float(lat), "lon": float(lon),
            "emoji": emoji, "timezone": tz, "base_temp": int(base), "slug": slug(name),
        })
    return result


def weather_for(city: dict) -> dict:
    live = fetch_open_meteo(city)
    if live:
        return live
    rnd = random.Random(city["slug"])
    code = rnd.choice([0, 1, 2, 3, 61])
    now = city["base_temp"] + rnd.randint(-2, 2)
    hourly = [{"time": f"{h:02d}:00", "temp": now + int(math.sin(h / 3) * 3), "code": rnd.choice([0, 1, 2, 3, 61])} for h in range(24)]
    daily = []
    for i in range(7):
        high = city["base_temp"] + rnd.randint(-3, 4)
        daily.append({"day": ["Today", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][i], "high": high, "low": high - rnd.randint(5, 10), "code": rnd.choice([0, 1, 2, 3, 61]), "rain": rnd.randint(0, 55), "wind": rnd.randint(6, 28)})
    return {"temp": now, "apparent": now + 2, "humidity": rnd.randint(35, 82), "wind": rnd.randint(5, 32), "pressure": rnd.randint(1002, 1024), "visibility": rnd.randint(8, 18), "code": code, "hourly": hourly, "daily": daily, "source": "offline-model"}


def fetch_open_meteo(city: dict) -> dict | None:
    if os.environ.get("OFFLINE_BUILD") == "1":
        return None
    params = urllib.parse.urlencode({
        "latitude": city["lat"], "longitude": city["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,pressure_msl,visibility",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": "7",
    })
    try:
        with urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=12) as res:
            raw = json.loads(res.read().decode("utf-8"))
        cur = raw["current"]
        hourly = [{"time": t[-5:], "temp": round(temp), "code": int(code)} for t, temp, code in zip(raw["hourly"]["time"][:24], raw["hourly"]["temperature_2m"][:24], raw["hourly"]["weather_code"][:24])]
        daily = [{"day": ["Today", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][i], "high": round(hi), "low": round(lo), "code": int(code), "rain": int(rain or 0), "wind": 12 + i * 2} for i, (hi, lo, code, rain) in enumerate(zip(raw["daily"]["temperature_2m_max"], raw["daily"]["temperature_2m_min"], raw["daily"]["weather_code"], raw["daily"].get("precipitation_probability_max", [0] * 7)))]
        return {"temp": round(cur["temperature_2m"]), "apparent": round(cur["apparent_temperature"]), "humidity": int(cur["relative_humidity_2m"]), "wind": round(cur["wind_speed_10m"]), "pressure": round(cur["pressure_msl"]), "visibility": round((cur.get("visibility") or 10000) / 1000), "code": int(cur["weather_code"]), "hourly": hourly, "daily": daily, "source": "open-meteo"}
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
        return None


def wx(code: int) -> tuple[str, str, str]:
    return WEATHER.get(code, WEATHER[2])


def page(title: str, body: str, lang: dict, path_prefix: str = ".") -> str:
    tr = T[lang["code"]]
    return f"""<!doctype html>
<html lang="{lang['code']}" dir="{lang['dir']}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{tr['tagline']}">
  <link rel="stylesheet" href="{path_prefix}/assets/css/styles.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&family=Material+Symbols+Outlined:wght@300;400;600&display=swap" rel="stylesheet">
</head>
<body>
  <nav class="topbar">
    <a class="brand" href="{path_prefix}/index.html"><span class="material-symbols-outlined">routine</span>{tr['brand']}</a>
    <div class="nav-search"><span class="material-symbols-outlined">search</span><input data-search-input placeholder="{tr['search']}"></div>
    <div class="nav-actions">
      <a class="icon-link" href="{path_prefix}/lang.html" title="{tr['language']}"><span class="material-symbols-outlined">language</span></a>
      <button class="icon-link" data-locate title="{tr['locate']}"><span class="material-symbols-outlined">my_location</span></button>
    </div>
  </nav>
  <main>{body}</main>
  <footer class="footer">{tr['updated']}: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · {tr['data']} · GitHub Pages</footer>
  <script src="{path_prefix}/assets/js/app.js"></script>
</body>
</html>"""


def home(lang: dict, city_data: list[dict], prefix: str = ".") -> str:
    tr = T[lang["code"]]
    hot = "".join(city_card(c, lang, prefix) for c in city_data[:12])
    lang_links = "".join(f'<a class="lang-chip" href="{prefix}/{l["code"]}/index.html">{l["flag"]} {l["code"].upper()}</a>' for l in LANGS)
    body = f"""
<section class="hero">
  <div>
    <p class="eyebrow">Open-Meteo · Static SSG · 100+ Cities</p>
    <h1>{tr['brand']}</h1>
    <p class="lead">{tr['tagline']}</p>
    <div class="hero-search"><span class="material-symbols-outlined">search</span><input data-search-input placeholder="{tr['search']}"><button data-locate><span class="material-symbols-outlined">my_location</span>{tr['locate']}</button></div>
    <div class="language-row">{lang_links}</div>
  </div>
  <div class="hero-panel">
    <span class="sky-icon">🌤️</span>
    <strong>{city_data[0]['weather']['temp']}°C</strong>
    <span>{city_data[0]['name']}, {city_data[0]['country']}</span>
  </div>
</section>
<section class="section"><div class="section-head"><h2>{tr['hot']}</h2><a href="{prefix}/search.html">Search all</a></div><div class="city-grid">{hot}</div></section>
<section class="feature-band">
  <article><span>🌍</span><h3>{tr['global']}</h3><p>Pre-rendered city pages across every region and major time zone.</p></article>
  <article><span>🔄</span><h3>{tr['realtime']}</h3><p>GitHub Actions can refresh Open-Meteo data every three hours.</p></article>
  <article><span>⚡</span><h3>{tr['static']}</h3><p>Static HTML keeps first paint fast and hosting cost at zero.</p></article>
</section>"""
    return page(f"{tr['brand']} - Global Forecasts", body, lang, prefix)


def city_card(c: dict, lang: dict, prefix: str) -> str:
    label, icon, emoji = wx(c["weather"]["code"])
    return f"""<a class="city-card {weather_class(c['weather']['code'])}" href="{prefix}/city/{c['slug']}.html">
  <span class="city-emoji">{c['emoji']}</span><strong>{c['name']}</strong><small>{c['country']}</small>
  <span class="city-temp">{c['weather']['temp']}°C {emoji}</span><em>{label}</em>
</a>"""


def city_page(lang: dict, c: dict, all_cities: list[dict], prefix: str = "..") -> str:
    tr = T[lang["code"]]
    w = c["weather"]
    label, icon, emoji = wx(w["code"])
    hourly = "".join(f'<div class="hour {"current" if i == 0 else ""}"><b>{ "Now" if i == 0 else h["time"]}</b><span>{wx(h["code"])[2]}</span><strong>{h["temp"]}°</strong></div>' for i, h in enumerate(w["hourly"]))
    daily = "".join(f'<details class="day-row"><summary><span>{d["day"]}</span><b>{wx(d["code"])[2]}</b><strong>{d["high"]}° / {d["low"]}°</strong><em>{wx(d["code"])[0]}</em></summary><p>Wind {d["wind"]} km/h · Humidity {w["humidity"]}% · Rain {d["rain"]}% · Sunrise 06:12 · Sunset 18:47</p></details>' for d in w["daily"])
    life = "".join(f'<article class="mini"><span>{a}</span><b>{b}</b><small>{v}</small></article>' for a, b, v in [("👕", "Clothing", "Light"), ("☀️", "UV Index", "Medium"), ("🚗", "Car Wash", "Good"), ("🏃", "Sports", "Ideal"), ("💊", "Cold Risk", "Low"), ("🧴", "Skin Care", "Hydrate")])
    travel = "".join(f'<tr><td>{x["name"]}</td><td>{x["weather"]["temp"]}°C</td><td>{wx(x["weather"]["code"])[2]} {wx(x["weather"]["code"])[0]}</td><td>Apr-Oct</td></tr>' for x in all_cities[60:64])
    body = f"""
<section class="city-hero {weather_class(w['code'])}">
  <div><p class="eyebrow">{c['timezone']} · {w['source']}</p><h1>{tr['city_weather'].format(city=c['name'])}</h1><div class="temp-line"><span>{emoji}</span><strong>{w['temp']}°C</strong></div><p class="lead">{label}</p><div class="badges"><span>AQI: Excellent 🟢</span><span>UV: Medium 🟡</span><span>Rain: {w['daily'][0]['rain']}% 🔵</span></div></div>
  <div class="metric-grid">
    <article><small>{tr['feels']}</small><b>{w['apparent']}°C</b></article><article><small>{tr['humidity']}</small><b>{w['humidity']}%</b></article><article><small>{tr['wind']}</small><b>{w['wind']} km/h</b></article>
    <article><small>{tr['pressure']}</small><b>{w['pressure']} hPa</b></article><article><small>{tr['visibility']}</small><b>{w['visibility']} km</b></article><article><small>Clock</small><b data-clock>{datetime.now().strftime('%H:%M')}</b></article>
  </div>
</section>
<section class="section"><h2>{tr['hourly']}</h2><div class="hour-strip">{hourly}</div></section>
<section class="section two-col"><div><h2>{tr['daily']}</h2><div class="forecast-list">{daily}</div></div><aside class="alert-card"><h2>⚠️ {tr['alert']}</h2><p>Typhoon Warning - Category 3. Strong winds and heavy rain may affect coastal travel.</p><a href="{prefix}/alert/tokyo-typhoon.html">View Details →</a></aside></section>
<section class="section"><h2>{tr['life']}</h2><div class="mini-grid">{life}</div></section>
<section class="section two-col"><div class="table-card"><h2>{tr['travel']}</h2><table><tbody>{travel}</tbody></table></div><div><h2>{tr['knowledge']}</h2><div class="knowledge-grid">{wiki_cards(prefix, tr)}</div></div></section>"""
    return page(f"{c['name']} Weather - GlobalWeather", body, lang, prefix)


def weather_class(code: int) -> str:
    if code in (0, 1):
        return "sunny"
    if code in (61, 63, 80, 95):
        return "rainy"
    return "cloudy"


def wiki_cards(prefix: str, tr: dict) -> str:
    cards = [("🌀", "Typhoon Naming Rules", "typhoon-naming"), ("🌡️", "El Niño Phenomenon", "el-nino"), ("📈", "Climate Change Data", "climate-change")]
    return "".join(f'<a class="wiki-card" href="{prefix}/wiki/{slug}.html"><span>{emoji}</span><b>{title}</b><small>{tr["read"]} →</small></a>' for emoji, title, slug in cards)


def lang_page(lang: dict, prefix: str = ".") -> str:
    tr = T[lang["code"]]
    cards = "".join(f'<a class="language-card" href="{prefix}/{l["code"]}/index.html"><span>{l["flag"]}</span><b>{l["name"]}</b><small>{l["native"]}</small></a>' for l in LANGS)
    return page(f"{tr['select_language']} - GlobalWeather", f'<section class="section narrow"><h1>{tr["select_language"]}</h1><p class="lead">Selecciona tu idioma · Choisissez votre langue · Sprache wählen · 言語を選択</p><div class="language-grid">{cards}</div></section>', lang, prefix)


def search_page(lang: dict, all_cities: list[dict], prefix: str = ".") -> str:
    tr = T[lang["code"]]
    rows = "".join(f'<article class="result-card" data-city="{c["name"].lower()} {c["country"].lower()}"><div><span>{c["emoji"]}</span><b>{c["name"]}</b><small>{c["country"]}</small></div><strong>{c["weather"]["temp"]}°C {wx(c["weather"]["code"])[2]}</strong><a href="{prefix}/city/{c["slug"]}.html">{tr["view"]}</a></article>' for c in all_cities)
    body = f'<section class="section narrow"><h1>{tr["results"]}</h1><div class="page-search"><span class="material-symbols-outlined">search</span><input data-results-search placeholder="{tr["search"]}"></div><p class="result-count"></p><div class="results-list">{rows}</div><p class="empty-state">{tr["no_results"]}</p></section>'
    return page(f"{tr['results']} - GlobalWeather", body, lang, prefix)


def wiki_page(lang: dict, topic: str, prefix: str = "..") -> str:
    titles = {"typhoon-naming": ("🌀", "Typhoon Naming Rules", "How tropical cyclones get their names"), "el-nino": ("🌡️", "El Niño Phenomenon", "Why Pacific ocean temperatures reshape global weather"), "climate-change": ("📈", "Climate Change Data 2026", "Reading long-term signals without losing daily context")}
    emoji, title, subtitle = titles[topic]
    body = f"""<article class="article">
<nav class="breadcrumb"><a href="{prefix}/index.html">Home</a> › <span>Weather Knowledge</span> › <b>{title}</b></nav>
<span class="article-emoji">{emoji}</span><h1>{title}</h1><p class="lead">{subtitle}</p>
<p>Weather is local at the moment you feel it, but global in the systems that create it. This guide explains the topic in practical language for travelers, planners, and curious readers.</p>
<blockquote>Reliable weather communication depends on clear naming, consistent data, and calm presentation during high-impact events.</blockquote>
<h2>Key Points</h2><ul><li>Official agencies coordinate terminology so alerts can be shared across borders.</li><li>Forecast data should be refreshed frequently, but static pages keep access fast during traffic spikes.</li><li>Historical climate signals help explain trends; daily forecasts still require local observation.</li></ul>
<h2>Related Reading</h2><div class="knowledge-grid">{wiki_cards(prefix, T[lang["code"]])}</div>
</article>"""
    return page(f"{title} - GlobalWeather", body, lang, prefix)


def alert_page(lang: dict, prefix: str = "..") -> str:
    body = f"""<section class="section narrow">
<nav class="breadcrumb"><a href="{prefix}/index.html">Home</a> › Alerts › <b>Typhoon Warning</b></nav>
<article class="alert-detail"><p class="eyebrow">⚠️ SEVERE WEATHER ALERT</p><h1>Typhoon Warning - Category 3</h1><h2>Tokyo, Japan</h2>
<div class="timeline"><p><b>Effective Period</b><br>Jun 15, 2026 08:00 — Jun 16, 2026 20:00</p><p>Maximum wind speed: 150 km/h · Impact area: Kanto region · Advice: avoid unnecessary travel, secure loose objects, and monitor official instructions.</p></div>
<div class="button-row"><button data-share>Share</button><a href="{prefix}/city/tokyo.html">Back to Tokyo Weather</a></div></article></section>"""
    return page("Typhoon Warning - GlobalWeather", body, lang, prefix)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    clean()
    all_cities = cities()
    for c in all_cities:
        c["weather"] = weather_for(c)
    write(ROOT / "data/cities.json", json.dumps(all_cities, ensure_ascii=False, indent=2))
    write(ROOT / "index.html", home(LANGS[0], all_cities, "."))
    write(ROOT / "lang.html", lang_page(LANGS[0], "."))
    write(ROOT / "search.html", search_page(LANGS[0], all_cities, "."))
    for topic in ["typhoon-naming", "el-nino", "climate-change"]:
        write(ROOT / "wiki" / f"{topic}.html", wiki_page(LANGS[0], topic, ".."))
    write(ROOT / "alert" / "tokyo-typhoon.html", alert_page(LANGS[0], ".."))
    for c in all_cities:
        write(ROOT / "city" / f"{c['slug']}.html", city_page(LANGS[0], c, all_cities, ".."))
    for lang in LANGS:
        base = ROOT / lang["code"]
        write(base / "index.html", home(lang, all_cities, ".."))
        write(base / "lang.html", lang_page(lang, ".."))
        write(base / "search.html", search_page(lang, all_cities, ".."))
        write(base / "alert" / "tokyo-typhoon.html", alert_page(lang, "../.."))
        for topic in ["typhoon-naming", "el-nino", "climate-change"]:
            write(base / "wiki" / f"{topic}.html", wiki_page(lang, topic, "../.."))
        for c in all_cities:
            write(base / "city" / f"{c['slug']}.html", city_page(lang, c, all_cities, "../.."))
    urls = ["https://wolf0x0x.github.io/weatherindex/"]
    urls += [f"https://wolf0x0x.github.io/weatherindex/city/{c['slug']}.html" for c in all_cities]
    urls += [f"https://wolf0x0x.github.io/weatherindex/{l['code']}/city/{c['slug']}.html" for l in LANGS for c in all_cities]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n"
    write(ROOT / "sitemap.xml", sitemap)
    write(ROOT / "robots.txt", "User-agent: *\nAllow: /\nSitemap: https://wolf0x0x.github.io/weatherindex/sitemap.xml\n")
    print(f"Generated {len(all_cities)} cities across {len(LANGS)} languages")


if __name__ == "__main__":
    build()
