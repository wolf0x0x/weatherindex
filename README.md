# GlobalWeather

GlobalWeather is a fully static, multilingual weather aggregation site for GitHub Pages.

## Features

- 100+ city weather pages generated as static HTML
- 9 language directories: English, Chinese, Spanish, French, German, Japanese, Russian, Korean, Arabic
- Search, IP location, language selection, alert detail pages, and weather wiki pages
- Open-Meteo fetch on build with deterministic offline fallback for local reliability
- Free API integrations for weather, air quality, marine data, IP location, time zone, geocoding, and newsletter forms
- Sitemap, robots.txt, and GitHub Actions scheduled refresh every 3 hours
- Google Analytics, AdSense bootstrap, ads.txt, responsive ad placements, CNAME, and icon/manifest files

## Local Build

```bash
python3 scripts/build.py
python3 -m http.server 8080
```

Open `http://localhost:8080`.

Set `OFFLINE_BUILD=1` to skip network calls during local testing.

## API Integrations

No-key APIs work out of the box: Open-Meteo Forecast, Open-Meteo Air Quality, Open-Meteo Marine, 7Timer, wttr.in, ipapi.co, ipinfo.io, IPWho.is, IPLocate, WorldTimeAPI, and Nominatim.

Optional free-tier APIs are enabled with environment variables:

- `OPENWEATHER_KEY`
- `VISUALCROSSING_KEY`
- `WEATHERBIT_KEY`
- `BUTTONDOWN_NEWSLETTER`

Custom domain support is configured with `CNAME` for `weatherindex.xyz`.
