"""Data source clients.

* WAQI / AQICN       ground stations, real time AQI, station search, map tiles, daily forecast
                     (needs a free token: https://aqicn.org/data-platform/token/)
* Open-Meteo AQ      CAMS atmospheric model, any point on Earth, hourly history (up to 92 days)
                     and 5 day forecast, no key needed
* Open-Meteo weather current weather for context (wind disperses pollution), no key
* Open-Meteo geocode place search for any city, town or village, no key
* OpenAQ v3          open government and research station measurements (optional free key)

Every public function is cached and raises SourceError on failure, so the UI can
degrade gracefully instead of crashing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .aqi import haversine_km, to_num

WAQI_URL = "https://api.waqi.info"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WX_URL = "https://api.open-meteo.com/v1/forecast"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPENAQ_URL = "https://api.openaq.org/v3"

HEADERS = {"User-Agent": "RealTimeAirPollution/2.0 (+https://github.com/Gull01/Real-Time-Air-Pollution)"}

AQ_VARS = [
    "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide",
    "dust", "aerosol_optical_depth", "uv_index", "us_aqi", "european_aqi",
    "us_aqi_pm2_5", "us_aqi_pm10", "us_aqi_nitrogen_dioxide", "us_aqi_ozone",
    "us_aqi_sulphur_dioxide", "us_aqi_carbon_monoxide",
]
WX_VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m",
           "precipitation", "surface_pressure", "is_day"]


class SourceError(RuntimeError):
    pass


@st.cache_resource(show_spinner=False)
def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s


def _get(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 20):
    try:
        r = _session().get(url, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise SourceError(f"Network error: {e.__class__.__name__}") from e
    if r.status_code == 401 or r.status_code == 403:
        raise SourceError("The API key was rejected (check your token).")
    if r.status_code == 429:
        raise SourceError("Rate limit reached. Try again in a minute.")
    if not r.ok:
        raise SourceError(f"HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as e:
        raise SourceError("Unexpected (non JSON) response") from e


# --------------------------------------------------------------------------- search

@st.cache_data(ttl=86_400, show_spinner=False)
def geocode(query: str, count: int = 8) -> list[dict]:
    data = _get(GEO_URL, {"name": query, "count": count, "language": "en", "format": "json"})
    out = []
    for r in data.get("results") or []:
        parts = []
        for p in (r.get("name"), r.get("admin1"), r.get("country")):
            if p and p not in parts:
                parts.append(p)
        out.append(dict(kind="place", name=r.get("name", query), label=", ".join(parts),
                        lat=float(r["latitude"]), lon=float(r["longitude"]),
                        country=r.get("country_code", ""), population=r.get("population")))
    return out


@st.cache_data(ttl=600, show_spinner=False)
def waqi_search(token: str, keyword: str) -> list[dict]:
    data = _get(f"{WAQI_URL}/search/", {"token": token, "keyword": keyword})
    if data.get("status") != "ok":
        raise SourceError(str(data.get("data") or "WAQI search failed"))
    out = []
    for r in data.get("data") or []:
        stn = r.get("station") or {}
        geo = stn.get("geo") or [None, None]
        if geo[0] is None:
            continue
        t = r.get("time") or {}
        out.append(dict(kind="station", uid=r.get("uid"), name=stn.get("name", "Station"),
                        label=stn.get("name", "Station"), lat=float(geo[0]), lon=float(geo[1]),
                        aqi=to_num(r.get("aqi")), time=t.get("stime") if isinstance(t, dict) else None))
    return out


# --------------------------------------------------------------------------- WAQI stations

@st.cache_data(ttl=600, show_spinner=False)
def waqi_feed(token: str, target: str) -> dict:
    """target is '@<uid>', 'geo:<lat>;<lon>' or a city slug."""
    data = _get(f"{WAQI_URL}/feed/{target}/", {"token": token})
    if data.get("status") != "ok" or not isinstance(data.get("data"), dict):
        raise SourceError(str(data.get("data") or "No station data"))
    d = data["data"]
    city = d.get("city") or {}
    geo = city.get("geo") or [None, None]
    t = d.get("time") or {}
    iaqi = {k: to_num((v or {}).get("v")) for k, v in (d.get("iaqi") or {}).items()}
    fc_rows = []
    for pol, days in ((d.get("forecast") or {}).get("daily") or {}).items():
        for day in days or []:
            fc_rows.append(dict(pollutant=pol, day=day.get("day"), avg=to_num(day.get("avg")),
                                min=to_num(day.get("min")), max=to_num(day.get("max"))))
    return dict(
        uid=d.get("idx"), aqi=to_num(d.get("aqi")), dominant=d.get("dominentpol") or "",
        name=city.get("name") or "Station", url=city.get("url"),
        lat=to_num(geo[0]) if geo else float("nan"), lon=to_num(geo[1]) if geo else float("nan"),
        time=t.get("iso") or t.get("s"), iaqi=iaqi,
        forecast=pd.DataFrame(fc_rows),
        attributions=[dict(name=a.get("name"), url=a.get("url")) for a in d.get("attributions") or []],
    )


@st.cache_data(ttl=900, show_spinner=False)
def waqi_bounds(token: str, south: float, west: float, north: float, east: float) -> pd.DataFrame:
    data = _get(f"{WAQI_URL}/map/bounds/",
                {"token": token, "latlng": f"{south},{west},{north},{east}", "networks": "all"})
    if data.get("status") != "ok":
        raise SourceError(str(data.get("data") or "WAQI map query failed"))
    rows = []
    for s in data.get("data") or []:
        stn = s.get("station")
        name, when = "", None
        if isinstance(stn, dict):
            name, when = stn.get("name", ""), stn.get("time")
        elif isinstance(stn, str):
            name = stn
        rows.append(dict(name=name or f"Station {s.get('uid')}", lat=to_num(s.get("lat")),
                         lon=to_num(s.get("lon")), aqi=to_num(s.get("aqi")), uid=s.get("uid"),
                         updated=when))
    df = pd.DataFrame(rows, columns=["name", "lat", "lon", "aqi", "uid", "updated"])
    return df.dropna(subset=["lat", "lon", "aqi"]).reset_index(drop=True)


# --------------------------------------------------------------------------- Open-Meteo model

def _hourly_frame(block: dict) -> pd.DataFrame:
    h = block.get("hourly") or {}
    if not h.get("time"):
        return pd.DataFrame()
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"])
    return df


@st.cache_data(ttl=1_800, show_spinner=False)
def model_air(lat: float, lon: float, past_days: int = 7, forecast_days: int = 5) -> dict:
    data = _get(AQ_URL, {
        "latitude": round(lat, 3), "longitude": round(lon, 3),
        "current": ",".join(AQ_VARS), "hourly": ",".join(AQ_VARS),
        "past_days": int(past_days), "forecast_days": int(forecast_days), "timezone": "auto",
    })
    if data.get("error"):
        raise SourceError(str(data.get("reason")))
    return dict(current=data.get("current") or {}, hourly=_hourly_frame(data),
                units=data.get("hourly_units") or {}, tz=data.get("timezone", "UTC"),
                tz_abbr=data.get("timezone_abbreviation", ""),
                lat=data.get("latitude", lat), lon=data.get("longitude", lon))


@st.cache_data(ttl=1_800, show_spinner=False)
def weather_now(lat: float, lon: float) -> dict:
    data = _get(WX_URL, {"latitude": round(lat, 3), "longitude": round(lon, 3),
                         "current": ",".join(WX_VARS), "wind_speed_unit": "kmh", "timezone": "auto"})
    if data.get("error"):
        raise SourceError(str(data.get("reason")))
    return data.get("current") or {}


@st.cache_data(ttl=1_800, show_spinner=False)
def model_multi(points: tuple[tuple[float, float], ...], variable: str,
                past_days: int = 7, forecast_days: int = 3) -> list[pd.DataFrame]:
    """One request for many locations (Open-Meteo accepts comma separated coordinates)."""
    data = _get(AQ_URL, {
        "latitude": ",".join(f"{p[0]:.3f}" for p in points),
        "longitude": ",".join(f"{p[1]:.3f}" for p in points),
        "hourly": variable, "past_days": int(past_days), "forecast_days": int(forecast_days),
        "timezone": "GMT",
    })
    blocks = data if isinstance(data, list) else [data]
    return [_hourly_frame(b) for b in blocks]


@st.cache_data(ttl=3_600, show_spinner=False)
def model_grid(south: float, west: float, north: float, east: float, n: int = 12) -> pd.DataFrame:
    """Current modelled US AQI and PM2.5 on an n x n grid of cells (fills gaps between stations)."""
    south, north = max(south, -80.0), min(north, 80.0)
    lats = np.linspace(south, north, n + 1)
    lons = np.linspace(west, east, n + 1)
    dlat, dlon = lats[1] - lats[0], lons[1] - lons[0]
    centres = [((la + dlat / 2), ((lo + dlon / 2 + 180) % 360) - 180)
               for la in lats[:-1] for lo in lons[:-1]]
    data = _get(AQ_URL, {
        "latitude": ",".join(f"{c[0]:.3f}" for c in centres),
        "longitude": ",".join(f"{c[1]:.3f}" for c in centres),
        "current": "us_aqi,pm2_5", "timezone": "GMT",
    }, timeout=30)
    blocks = data if isinstance(data, list) else [data]
    rows = []
    for (la, lo), b in zip(centres, blocks):
        cur = b.get("current") or {}
        h_lat, h_lon = dlat / 2, dlon / 2
        rows.append(dict(
            lat=la, lon=lo, us_aqi=to_num(cur.get("us_aqi")), pm2_5=to_num(cur.get("pm2_5")),
            polygon=[[lo - h_lon, la - h_lat], [lo + h_lon, la - h_lat],
                     [lo + h_lon, la + h_lat], [lo - h_lon, la + h_lat]],
        ))
    return pd.DataFrame(rows).dropna(subset=["us_aqi"])


# --------------------------------------------------------------------------- OpenAQ

@st.cache_data(ttl=900, show_spinner=False)
def openaq_nearby(key: str, lat: float, lon: float, radius_m: int = 25_000, limit: int = 10) -> pd.DataFrame:
    hdr = {"X-API-Key": key}
    locs = _get(f"{OPENAQ_URL}/locations",
                {"coordinates": f"{lat:.4f},{lon:.4f}", "radius": radius_m, "limit": 50},
                headers=hdr).get("results") or []
    for loc in locs:
        c = loc.get("coordinates") or {}
        loc["_km"] = haversine_km(lat, lon, c.get("latitude", lat), c.get("longitude", lon))
    locs.sort(key=lambda x: x["_km"])
    rows = []
    for loc in locs[:limit]:
        sensors = {s.get("id"): (s.get("parameter") or {}) for s in loc.get("sensors") or []}
        try:
            latest = _get(f"{OPENAQ_URL}/locations/{loc['id']}/latest", headers=hdr).get("results") or []
        except SourceError:
            continue
        c = loc.get("coordinates") or {}
        for m in latest:
            p = sensors.get(m.get("sensorsId"), {})
            rows.append(dict(
                station=loc.get("name") or f"Location {loc.get('id')}",
                provider=(loc.get("provider") or {}).get("name", ""),
                km=round(loc["_km"], 1), lat=c.get("latitude"), lon=c.get("longitude"),
                parameter=p.get("displayName") or p.get("name") or "?",
                key=p.get("name", ""), value=to_num(m.get("value")), unit=p.get("units", ""),
                utc=(m.get("datetime") or {}).get("utc"),
            ))
    df = pd.DataFrame(rows)
    if not df.empty:
        df["utc"] = pd.to_datetime(df["utc"], utc=True, errors="coerce")
    return df
