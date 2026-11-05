# Real-Time Air Pollution Monitor

A Streamlit dashboard for live air quality anywhere on Earth. It combines official ground stations, open sensor networks and the Copernicus (CAMS) atmospheric model, so you get a reading even where there is no monitor nearby.

## What it does

* **Search anything.** Type a city, town, village, monitoring station or raw coordinates (`31.52, 74.35`). Place search covers the whole world, and station search hits the WAQI network directly.
* **Right now.** The Air Quality Index in plain words, a simple "what to do today" row (exercise, windows, mask, kids), and pollutant cards (PM2.5, PM10, NO₂, O₃, SO₂, CO) compared against WHO 2021 guidelines, a 5 day outlook and current weather.
* **Map.** Ground stations coloured by AQI category on a dark basemap, plus a CAMS model grid that fills the gaps between stations. Switch between the area around your location and the whole world, and click any station to open it.
* **Past and forecast.** Up to 30 days of hourly history and a 5 day forecast for any pollutant, daily averages against the WHO line, an hour by day heatmap that shows the daily rhythm, and the WAQI station forecast. Everything downloads as CSV.
* **Nearby monitors.** All WAQI stations within about 100 km sorted by distance, plus OpenAQ monitors within 25 km if you add a key.
* **Compare cities.** Put up to 8 cities side by side on one chart, ranked by current levels, with hours spent above the WHO guideline.

## Data sources

| Source | Coverage | Key |
|---|---|---|
| [WAQI / AQICN](https://aqicn.org/api/) | 12,000+ official ground stations, real time AQI, daily forecast | Free token |
| [Open-Meteo Air Quality](https://open-meteo.com/en/docs/air-quality-api) (CAMS) | Any point on Earth, hourly, 92 days back and 5 days ahead | None |
| [Open-Meteo Weather](https://open-meteo.com/en/docs) | Wind, temperature, humidity, pressure | None |
| [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api) | Place search worldwide | None |
| [OpenAQ v3](https://docs.openaq.org/) | Government, research and low cost sensors | Free key (optional) |

When a WAQI station lies within 40 km, the headline uses the measured value. Otherwise it falls back to the model. The app still works with no keys at all, running on the model only.

## Getting started

```bash
git clone https://github.com/Gull01/Real-Time-Air-Pollution.git
cd Real-Time-Air-Pollution
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then paste your keys in
streamlit run AP.py
```

On Windows you can instead double-click `run_local.bat`: it creates a virtual environment, installs the requirements, asks for your keys once and opens the app.

A `.env` file with the same names (`AQICN_API_TOKEN`, `OPENAQ_API_KEY`) works too.

### Deploying on Streamlit Community Cloud

Point the app at `AP.py` and paste the contents of `secrets.toml` into **App settings > Secrets**.

## Project layout

```
AP.py                 Streamlit app: layout, tabs and charts
airmon/sources.py     API clients with caching, retries and graceful errors
airmon/aqi.py         US EPA AQI bands, pollutant metadata, WHO guidelines
airmon/ui.py          Theme CSS and HTML components
.streamlit/config.toml  Dark theme and fonts
```

## Built with

Python, Streamlit, Plotly, pydeck, pandas.

## License

MIT License

Copyright (c) 2026 Gul Nawaz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
