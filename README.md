# GlobalWeather

GlobalWeather is a fully static, multilingual weather aggregation site for GitHub Pages.

## Features

- 100+ city weather pages generated as static HTML
- 8 language directories: English, Spanish, French, German, Japanese, Russian, Korean, Arabic
- Search, IP location, language selection, alert detail pages, and weather wiki pages
- Open-Meteo fetch on build with deterministic offline fallback for local reliability
- Sitemap, robots.txt, and GitHub Actions scheduled refresh every 3 hours

## Local Build

```bash
python3 scripts/build.py
python3 -m http.server 8080
```

Open `http://localhost:8080`.

Set `OFFLINE_BUILD=1` to skip network calls during local testing.
