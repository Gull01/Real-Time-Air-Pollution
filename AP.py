"""Real-Time Air Pollution Monitor.

Run locally with:  streamlit run AP.py
"""
from __future__ import annotations

import math
import os

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

from airmon import sources as src
from airmon import ui
from airmon.aqi import (BANDS, EXTRA_VARS, POLLUTANTS, WAQI_TO_KEY, band_for, haversine_km,
                        is_num, pollutant_name, rgba_for, who_color)

st.set_page_config(page_title="Real-Time Air Pollution Monitor", page_icon=":material/air:",
                   layout="wide", initial_sidebar_state="auto")
load_dotenv()


def secret(name: str) -> str | None:
    """Streamlit Cloud secrets first, then environment / .env."""
    try:
        if name in st.secrets:
            return str(st.secrets[name]).strip() or None
    except Exception:
        pass
    v = os.getenv(name)
    return v.strip() if v else None


WAQI_TOKEN = secret("AQICN_API_TOKEN") or secret("WAQI_TOKEN")
OPENAQ_KEY = secret("OPENAQ_API_KEY")
STATION_MAX_KM = 40  # beyond this a "nearest station" no longer represents the place

QUICK = {
    "Islamabad": (33.7215, 73.0433, "Pakistan"), "Lahore": (31.5204, 74.3587, "Pakistan"),
    "Karachi": (24.8607, 67.0011, "Pakistan"), "Delhi": (28.6139, 77.2090, "India"),
    "Dhaka": (23.8103, 90.4125, "Bangladesh"), "Beijing": (39.9042, 116.4074, "China"),
    "Jakarta": (-6.2088, 106.8456, "Indonesia"), "Cairo": (30.0444, 31.2357, "Egypt"),
    "Dubai": (25.2048, 55.2708, "United Arab Emirates"), "London": (51.5072, -0.1276, "United Kingdom"),
    "New York": (40.7128, -74.0060, "United States"), "Los Angeles": (34.0522, -118.2437, "United States"),
    "Mexico City": (19.4326, -99.1332, "Mexico"), "São Paulo": (-23.5505, -46.6333, "Brazil"),
}


def quick_loc(name: str) -> dict:
    lat, lon, country = QUICK[name]
    return dict(kind="place", name=name, label=f"{name}, {country}", lat=lat, lon=lon, uid=None)


VAR_LABELS = {"us_aqi": "Air Quality Index (AQI)", **{k: pollutant_name(k) for k in POLLUTANTS},
              "dust": "Desert dust", "uv_index": "UV index (sunburn risk)"}
VAR_SHORT = {"us_aqi": "Overall AQI", **{k: v["plain"] for k, v in POLLUTANTS.items()},
             "dust": "Desert dust", "uv_index": "UV"}


# --------------------------------------------------------------------------- state + callbacks

def init_state() -> None:
    st.session_state.setdefault("loc", quick_loc("Islamabad"))
    st.session_state.setdefault("_results", [])


def set_loc(loc: dict) -> None:
    st.session_state.loc = loc


def _on_pick() -> None:
    idx = st.session_state.get("pick")
    res = st.session_state.get("_results") or []
    if idx is not None and idx < len(res):
        set_loc(res[idx])
        st.session_state.query = ""
        st.session_state.pick = None


def _on_quick() -> None:
    name = st.session_state.get("quick")
    if name:
        set_loc(quick_loc(name))
        st.session_state.quick = None


def parse_coords(q: str):
    try:
        a, b = [float(x) for x in q.replace(";", ",").split(",")[:2]]
    except ValueError:
        return None
    return (a, b) if -90 <= a <= 90 and -180 <= b <= 180 else None


# --------------------------------------------------------------------------- sidebar

def sidebar() -> int:
    with st.sidebar:
        st.markdown("#### Find a location")
        q = st.text_input("Search", key="query", label_visibility="collapsed",
                          placeholder="City, town, station or  lat, lon")
        q = (q or "").strip()
        results, errors = [], []
        if len(q) >= 2:
            c = parse_coords(q)
            if c:
                results.append(dict(kind="point", name=f"{c[0]:.3f}, {c[1]:.3f}",
                                    label=f"Point {c[0]:.3f}, {c[1]:.3f}", lat=c[0], lon=c[1], uid=None))
            else:
                try:
                    results += src.geocode(q)
                except src.SourceError as e:
                    errors.append(f"Place search unavailable ({e})")
                if WAQI_TOKEN:
                    try:
                        results += src.waqi_search(WAQI_TOKEN, q)[:15]
                    except src.SourceError as e:
                        errors.append(f"Monitor search unavailable ({e})")
        st.session_state._results = results

        if results:
            def fmt(i: int) -> str:
                r = results[i]
                if r["kind"] == "station":
                    a = f"  ·  AQI {int(r['aqi'])}" if is_num(r.get("aqi")) else ""
                    return f"Monitor: {r['label']}{a}"
                if r["kind"] == "point":
                    return r["label"]
                return f"Place: {r['label']}"
            st.selectbox("Matches", range(len(results)), index=None, format_func=fmt, key="pick",
                         on_change=_on_pick, placeholder=f"{len(results)} matches, pick one")
        elif len(q) >= 2 and not errors:
            st.caption("No matches. Try another spelling or type coordinates like 31.52, 74.35.")
        for e in errors:
            st.caption(e)

        st.pills("Quick picks", list(QUICK), key="quick", on_change=_on_quick, selection_mode="single")

        st.divider()
        st.markdown("#### Settings")
        past_days = st.slider("Past days to show", 1, 30, 7, key="past_days",
                              help="How far back the charts on the Past & forecast tab go.")
        if st.button("Refresh live data", icon=":material/refresh:", width="stretch"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.markdown("#### Data sources")
        ui.source_chips([
            ("Air monitors (WAQI)", bool(WAQI_TOKEN), "Live readings from official air monitors, via aqicn.org"),
            ("Satellite estimates (CAMS)", True, "Estimates for any place on Earth from satellite and weather data"),
            ("Weather", True, "Wind, temperature and humidity from Open-Meteo"),
            ("Extra sensors (OpenAQ)", bool(OPENAQ_KEY), "More government, research and low cost sensors"),
        ])
        if not WAQI_TOKEN:
            st.markdown('<div class="note">Add <code>AQICN_API_TOKEN</code> to secrets to show live '
                        'air monitors. Free token: aqicn.org/data-platform/token</div>', unsafe_allow_html=True)
    return past_days


# --------------------------------------------------------------------------- data

def load_location(loc: dict, past_days: int) -> dict:
    out: dict = dict(model=None, wx={}, station=None, errors={})
    try:
        out["model"] = src.model_air(loc["lat"], loc["lon"], past_days, 5)
    except src.SourceError as e:
        out["errors"]["Satellite estimates"] = str(e)
    try:
        out["wx"] = src.weather_now(loc["lat"], loc["lon"])
    except src.SourceError as e:
        out["errors"]["Weather"] = str(e)
    if WAQI_TOKEN:
        target = f"@{loc['uid']}" if loc.get("uid") else nearest_monitor(loc)
        if target is None:
            return out
        try:
            s = src.waqi_feed(WAQI_TOKEN, target)
            s["km"] = (haversine_km(loc["lat"], loc["lon"], s["lat"], s["lon"])
                       if is_num(s["lat"]) else float("nan"))
            out["station"] = s
        except src.SourceError as e:
            out["errors"]["WAQI"] = str(e)
    return out


def nearest_monitor(loc: dict, max_km: float = 100) -> str | None:
    """Find the closest WAQI monitor ourselves. WAQI's own geo lookup sometimes
    returns a station hundreds of km away (e.g. Delhi for Islamabad)."""
    s, w, n, e = _bounds(loc["lat"], loc["lon"], 1.0)
    try:
        df = src.waqi_bounds(WAQI_TOKEN, round(s, 2), round(w, 2), round(n, 2), round(e, 2))
    except src.SourceError:
        return None
    if df.empty:
        return None
    df = df.assign(km=[haversine_km(loc["lat"], loc["lon"], a, b) for a, b in zip(df["lat"], df["lon"])])
    df = df[(df["km"] <= max_km) & (pd.to_numeric(df["uid"], errors="coerce") > 0)].sort_values("km")
    return f"@{int(df.iloc[0]['uid'])}" if not df.empty else None


def model_now(model: dict | None) -> pd.Timestamp:
    if model and model["current"].get("time"):
        return pd.Timestamp(model["current"]["time"])
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h")


def dominant_from_model(cur: dict) -> str:
    best, label = -1.0, ""
    for k, meta in POLLUTANTS.items():
        v = cur.get(meta["aqi_key"])
        if is_num(v) and v > best:
            best, label = v, pollutant_name(k)
    return label




# --------------------------------------------------------------------------- tab: now

def tab_now(loc: dict, data: dict) -> None:
    model, stn, wx = data["model"], data["station"], data["wx"]
    cur = model["current"] if model else {}
    model_aqi = cur.get("us_aqi")
    use_station = bool(stn and is_num(stn["aqi"]) and
                       (loc.get("kind") == "station" or (is_num(stn["km"]) and stn["km"] <= STATION_MAX_KM)))

    if use_station:
        aqi = stn["aqi"]
        eyebrow = "Measured by a nearby air monitor"
        dkey = WAQI_TO_KEY.get(stn["dominant"], "")
        dom = pollutant_name(dkey) if dkey else stn["dominant"].upper()
        when = pd.to_datetime(stn["time"], errors="coerce")
        when_s = when.strftime("%d %b, %H:%M") if not pd.isna(when) else "recently"
        sub = f"Monitor: {stn['name']}  ·  updated {when_s}"
        if loc.get("kind") != "station" and is_num(stn["km"]):
            sub += f"  ·  {stn['km']:.0f} km away"
        second = (f"Satellite estimate for the area: <b>{int(model_aqi)}</b>" if is_num(model_aqi) else "")
    else:
        aqi = model_aqi
        eyebrow = "Estimated from satellite and weather data"
        dom = dominant_from_model(cur)
        t = cur.get("time", "")
        sub = f"{loc.get('label', loc['name'])}  ·  {loc['lat']:.3f}, {loc['lon']:.3f}"
        if t:
            sub += f"  ·  {pd.Timestamp(t).strftime('%d %b, %H:%M')} {model['tz_abbr'] if model else ''}"
        if stn and is_num(stn["aqi"]) and is_num(stn["km"]):
            second = f"Nearest air monitor ({stn['km']:.0f} km away): <b>{int(stn['aqi'])}</b>"
        elif WAQI_TOKEN:
            second = "No air monitor within 40 km, so this is an estimate"
        else:
            second = "Live monitor data is switched off"

    ui.hero(loc["name"], sub, aqi, eyebrow, second, dom)

    ui.section("What to do today")
    ui.actions(aqi)

    ui.section("What's in the air")
    ui.pollutant_cards(cur, stn["iaqi"] if (stn and use_station) else {})
    st.markdown('<div class="note">Each number is how much of that pollutant is in the air, in micrograms per cubic '
                'metre (µg/m³). The bar compares it with the World Health Organization safe limit. '
                'Hover over a card to see where it comes from.</div>',
                unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        ui.section("Next 5 days (worst AQI each day)")
        if model and not model["hourly"].empty:
            h = model["hourly"]
            now = model_now(model)
            fut = h[h["time"] >= now.normalize()].copy()
            fut["date"] = fut["time"].dt.date
            daily = fut.groupby("date")["us_aqi"].max().head(5)
            days = []
            for i, (d, v) in enumerate(daily.items()):
                lbl = "Today" if i == 0 else pd.Timestamp(d).strftime("%a %d")
                days.append(dict(label=lbl, aqi=v))
            ui.outlook(days)
        else:
            st.info("Forecast unavailable right now.")
    with right:
        ui.section("Weather")
        ui.weather(wx or {})
        ws = wx.get("wind_speed_10m") if wx else None
        if is_num(ws):
            msg = ("Calm air lets pollution build up near the ground." if ws < 6 else
                   "A light breeze is moving air around." if ws < 20 else
                   "Strong wind is mixing and diluting pollution.")
            st.markdown(f'<div class="note" style="margin-top:.5rem">{msg}</div>', unsafe_allow_html=True)

    if use_station and stn.get("attributions"):
        names = ", ".join(ui.esc(a["name"]) for a in stn["attributions"][:4]
                          if a.get("name") and "world air quality index" not in a["name"].lower())
        credit = f"{names}, shared via the World Air Quality Index project" if names else \
            "World Air Quality Index project"
        st.markdown(f'<div class="note" style="margin-top:1.2rem">Monitor data: {credit}.</div>',
                    unsafe_allow_html=True)


# --------------------------------------------------------------------------- tab: trends

def tab_trends(loc: dict, data: dict, past_days: int) -> None:
    model = data["model"]
    if not model or model["hourly"].empty:
        st.info("Model history is unavailable right now.")
        return
    h = model["hourly"]
    now = model_now(model)

    var = st.segmented_control("Show", list(VAR_SHORT), format_func=VAR_SHORT.get,
                               default="pm2_5", key="trend_var", required=True)
    meta = POLLUTANTS.get(var, {})
    unit = meta.get("unit") or EXTRA_VARS.get(var, {}).get("unit", "")
    who = meta.get("who")

    fig = go.Figure()
    if var == "us_aqi":
        for b in BANDS:
            fig.add_hrect(y0=b.lo, y1=min(b.hi, 500), fillcolor=b.color, opacity=.07, line_width=0)
    past = h[h["time"] <= now]
    fut = h[h["time"] >= now]
    fig.add_scatter(x=past["time"], y=past[var], name="Past days", mode="lines",
                    line=dict(color="#4493F8", width=2), fill="tozeroy", fillcolor="rgba(68,147,248,.10)")
    fig.add_scatter(x=fut["time"], y=fut[var], name="Forecast", mode="lines",
                    line=dict(color="#F2C94C", width=2, dash="dot"))
    fig.add_shape(type="line", x0=now, x1=now, yref="paper", y0=0, y1=1,
                  line=dict(color="#8B949E", width=1, dash="dash"))
    fig.add_annotation(x=now, y=1, yref="paper", text="now", showarrow=False, yshift=8,
                       font=dict(color="#8B949E", size=11))
    if who:
        fig.add_hline(y=who, line=dict(color="#EB5757", width=1, dash="dash"),
                      annotation_text="Safe limit (WHO)",
                      annotation_font_color="#EB5757", annotation_position="top left")
    fig.update_yaxes(title=f"{VAR_LABELS[var]} {('(' + unit + ')') if unit else ''}")
    ui.section(f"{VAR_LABELS[var]}: past {past_days} days and next 5 days")
    st.plotly_chart(ui.style_fig(fig, 380), width="stretch", config={"displaylogo": False})

    c1, c2 = st.columns(2, gap="large")
    with c1:
        ui.section("Average for each day")
        d = h.copy()
        d["date"] = d["time"].dt.normalize()
        cols = [var] + ([meta["aqi_key"]] if meta.get("aqi_key") else [])
        daily = d.groupby("date")[cols].mean().reset_index()
        if var == "us_aqi":
            colors = [band_for(v).color for v in daily[var]]
        elif meta.get("aqi_key"):
            colors = [band_for(v).color for v in daily[meta["aqi_key"]]]
        else:
            colors = "#4493F8"
        fig2 = go.Figure(go.Bar(x=daily["date"], y=daily[var], marker_color=colors,
                                hovertemplate="%{x|%a %d %b}<br>%{y:.1f}<extra></extra>"))
        fig2.add_shape(type="line", x0=now.normalize(), x1=now.normalize(), yref="paper", y0=0, y1=1,
                       line=dict(color="#8B949E", width=1, dash="dash"))
        if who:
            fig2.add_hline(y=who, line=dict(color="#EB5757", width=1, dash="dash"))
        st.plotly_chart(ui.style_fig(fig2, 300, legend=False), width="stretch", config={"displaylogo": False})
        if who and not past.empty:
            above = (past.set_index("time")[var].resample("D").mean() > who).sum()
            st.markdown(f'<div class="note">On {above} of the last {past["time"].dt.date.nunique()} days the '
                        f'air was above the safe limit.</div>', unsafe_allow_html=True)
    with c2:
        ui.section("Which hours are worst")
        p = past.copy()
        if not p.empty:
            p["date"] = p["time"].dt.strftime("%a %d")
            p["hour"] = p["time"].dt.hour
            order = list(dict.fromkeys(p["date"]))
            piv = p.pivot_table(index="date", columns="hour", values=var, aggfunc="mean").reindex(order)
            fig3 = go.Figure(go.Heatmap(
                z=piv.values, x=[f"{c:02d}" for c in piv.columns], y=piv.index,
                colorscale=[[0, "#0F2A3D"], [.35, "#4493F8"], [.6, "#F2C94C"], [.8, "#F2994A"], [1, "#EB5757"]],
                hovertemplate="%{y} %{x}:00<br>%{z:.1f}<extra></extra>", colorbar=dict(thickness=10)))
            fig3.update_xaxes(title="Hour of the day")
            st.plotly_chart(ui.style_fig(fig3, 300, legend=False), width="stretch",
                            config={"displaylogo": False})
            st.markdown('<div class="note">Each row is a day, each column an hour. Blue is cleaner, red is '
                        'dirtier. Hours that turn red every day are the ones to avoid outside.</div>', unsafe_allow_html=True)

    stn = data["station"]
    if stn is not None and not stn["forecast"].empty:
        ui.section(f"Forecast from the nearby monitor ({stn['name']})")
        fc = stn["forecast"]
        fc = fc[fc["pollutant"].isin(["pm25", "pm10", "o3"])].copy()
        if not fc.empty:
            fc["day"] = pd.to_datetime(fc["day"])
            fig4 = go.Figure()
            palette = {"pm25": "#4493F8", "pm10": "#F2C94C", "o3": "#A66CFF"}
            for pol, g in fc.groupby("pollutant"):
                fig4.add_scatter(
                    x=g["day"], y=g["avg"], name=pollutant_name(WAQI_TO_KEY[pol]), mode="lines+markers",
                    line=dict(color=palette.get(pol), width=2),
                    error_y=dict(type="data", symmetric=False, array=g["max"] - g["avg"],
                                 arrayminus=g["avg"] - g["min"], thickness=1, width=3))
            fig4.update_yaxes(title="AQI (line: average, bar: low to high)")
            st.plotly_chart(ui.style_fig(fig4, 300), width="stretch", config={"displaylogo": False})

    st.download_button("Download hourly data (CSV)", h.to_csv(index=False).encode(),
                       file_name=f"air_quality_{loc['name'].replace(' ', '_').lower()}.csv",
                       mime="text/csv", icon=":material/download:")


# --------------------------------------------------------------------------- tab: map

def _bounds(lat: float, lon: float, span: float) -> tuple[float, float, float, float]:
    wspan = span * 1.5
    return (max(lat - span, -85), max(lon - wspan, -180), min(lat + span, 85), min(lon + wspan, 180))


def tab_map(loc: dict) -> None:
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.4], vertical_alignment="bottom")
    extent = c1.segmented_control("Show", ["Around this place", "Whole world"], default="Around this place",
                                  key="map_extent", required=True)
    world = extent == "Whole world"
    show_st = c2.toggle("Air monitors", value=bool(WAQI_TOKEN), disabled=not WAQI_TOKEN, key="map_st")
    show_model = c3.toggle("Show estimates", value=True, disabled=world, key="map_model",
                           help="Coloured squares show estimated air quality where there is no monitor.")
    size = c4.select_slider("Map size", ["City", "Region", "Country", "Wide"], value="Region",
                            disabled=world, key="map_size")
    span = {"City": 1.0, "Region": 3.0, "Country": 6.0, "Wide": 10.0}[size]

    south, west, north, east = (-85.0, -180.0, 85.0, 180.0) if world else _bounds(loc["lat"], loc["lon"], span)
    layers = []
    stations = pd.DataFrame()

    if show_model and not world:
        try:
            grid = src.model_grid(round(south, 2), round(west, 2), round(north, 2), round(east, 2), 14)
            if not grid.empty:
                grid = grid.assign(
                    name="Estimate for this area", aqi=grid["us_aqi"].round().astype(int),
                    extra=grid["pm2_5"].map(lambda v: f"Fine dust {v:.0f} µg/m³" if is_num(v) else ""),
                    fill=grid["us_aqi"].map(lambda v: rgba_for(v, 95)))
                layers.append(pdk.Layer("PolygonLayer", id="model",
                                        data=grid[["polygon", "name", "aqi", "extra", "fill"]],
                                        get_polygon="polygon", get_fill_color="fill", stroked=False,
                                        pickable=True, auto_highlight=True))
        except src.SourceError as e:
            st.caption(f"Model layer unavailable ({e}).")

    if show_st and WAQI_TOKEN:
        try:
            stations = src.waqi_bounds(WAQI_TOKEN, round(south, 2), round(west, 2), round(north, 2), round(east, 2))
        except src.SourceError as e:
            st.caption(f"Monitor layer unavailable ({e}).")
        if not stations.empty:
            sd = stations.copy()
            sd["aqi"] = sd["aqi"].round().astype(int)
            sd["extra"] = sd["updated"].fillna("").map(lambda t: f"Updated {str(t)[:16].replace('T', ' ')}" if t else "Air monitor")
            sd["fill"] = sd["aqi"].map(lambda v: rgba_for(v, 235))
            sd["uid"] = sd["uid"].astype(str)
            layers.append(pdk.Layer("ScatterplotLayer", id="stations",
                                    data=sd[["name", "lat", "lon", "aqi", "uid", "extra", "fill"]],
                                    get_position="[lon, lat]", get_fill_color="fill",
                                    get_line_color=[13, 17, 23, 255], stroked=True, line_width_min_pixels=1,
                                    get_radius=20_000 if world else 3_000,
                                    radius_min_pixels=3 if world else 5, radius_max_pixels=14,
                                    pickable=True, auto_highlight=True))

    here = pd.DataFrame([dict(lat=loc["lat"], lon=loc["lon"], name=loc["name"], aqi="", extra="Selected location")])
    layers.append(pdk.Layer("ScatterplotLayer", id="here", data=here, get_position="[lon, lat]",
                            filled=False, stroked=True, get_line_color=[255, 255, 255, 255],
                            line_width_min_pixels=2, radius_min_pixels=11, get_radius=1))

    zoom = 1.2 if world else max(1.5, min(9.0, math.log2(360 / (span * 3)) + 0.4))
    deck = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        initial_view_state=pdk.ViewState(latitude=20 if world else loc["lat"],
                                         longitude=0 if world else loc["lon"], zoom=zoom),
        layers=layers,
        tooltip={"html": "<b>{name}</b><br/>AQI <b>{aqi}</b><br/><span style='opacity:.75'>{extra}</span>",
                 "style": {"backgroundColor": "#1C2128", "color": "#E6EDF3", "fontSize": "12px",
                           "border": "1px solid #30363D", "borderRadius": "8px"}},
    )
    event = st.pydeck_chart(deck, height=560, on_select="rerun", selection_mode="single-object", key="aq_map")
    ui.legend()

    picked = None
    try:
        picked = (event.selection.get("objects") or {}).get("stations")
    except AttributeError:
        pass
    if picked:
        o = picked[0]
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.markdown(f"**{o['name']}**  ·  AQI {o['aqi']}  ·  {band_for(o['aqi']).label}")
        if b.button("Show this monitor", type="primary", width="stretch", icon=":material/arrow_forward:"):
            set_loc(dict(kind="station", uid=o["uid"], name=o["name"], label=o["name"],
                         lat=float(o["lat"]), lon=float(o["lon"])))
            st.rerun()
    else:
        st.caption("Click a dot to open that air monitor. The coloured squares are estimates for areas without a monitor.")

    if not stations.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Monitors on map", f"{len(stations):,}", border=True)
        m2.metric("Typical AQI", f"{stations['aqi'].median():.0f}", border=True)
        worst = stations.loc[stations["aqi"].idxmax()]
        m3.metric("Worst reading", f"{worst['aqi']:.0f}", border=True, help=str(worst["name"]))
        m4.metric("Monitors above 100", f"{(stations['aqi'] > 100).mean() * 100:.0f}%", border=True)


# --------------------------------------------------------------------------- tab: nearby

def _aqi_style(v):
    b = band_for(v)
    return f"background-color:{b.color}; color:{b.ink}; font-weight:600" if b.lo >= 0 else ""


def tab_nearby(loc: dict) -> None:
    ui.section("Official air monitors nearby")
    if not WAQI_TOKEN:
        st.info("Add an `AQICN_API_TOKEN` secret to list air monitors. A free token takes a minute: "
                "https://aqicn.org/data-platform/token/")
    else:
        try:
            s, w, n, e = _bounds(loc["lat"], loc["lon"], 1.0)
            df = src.waqi_bounds(WAQI_TOKEN, round(s, 2), round(w, 2), round(n, 2), round(e, 2))
        except src.SourceError as err:
            df = pd.DataFrame()
            st.warning(f"Could not load stations ({err}).")
        if df.empty:
            st.caption("No air monitors within about 100 km. The satellite estimate on the first tab still works here.")
        else:
            df["km"] = [haversine_km(loc["lat"], loc["lon"], a, b) for a, b in zip(df["lat"], df["lon"])]
            df = df.sort_values("km").head(30)
            show = pd.DataFrame({
                "Monitor": df["name"], "Distance (km)": df["km"].round(1), "AQI": df["aqi"].round(),
                "Air quality": df["aqi"].map(lambda v: band_for(v).label),
                "Updated": df["updated"].fillna("").astype(str).str[:16].str.replace("T", " "),
            })
            st.dataframe(show.style.map(_aqi_style, subset=["AQI"]).format({"AQI": "{:.0f}",
                                                                                "Distance (km)": "{:.1f}"}),
                         hide_index=True, width="stretch", height=min(420, 38 + 35 * len(show)))

    ui.section("More sensors within 25 km (OpenAQ)")
    if not OPENAQ_KEY:
        st.info("OpenAQ adds thousands of government and research monitors (and many low cost sensors) that "
                "WAQI does not carry. Add a free `OPENAQ_API_KEY` secret to switch it on: "
                "https://explore.openaq.org/register")
        return
    try:
        oq = src.openaq_nearby(OPENAQ_KEY, loc["lat"], loc["lon"])
    except src.SourceError as err:
        st.warning(f"OpenAQ unavailable ({err}).")
        return
    if oq.empty:
        st.caption("No OpenAQ locations reported within 25 km.")
        return
    now = pd.Timestamp.now(tz="UTC")
    oq["age_h"] = (now - oq["utc"]).dt.total_seconds() / 3600
    fresh_only = st.toggle("Only readings from the last 24 hours", value=True, key="oq_fresh")
    if fresh_only:
        oq = oq[oq["age_h"] <= 24]
    if oq.empty:
        st.caption("No fresh readings. Switch the toggle off to see older ones.")
        return
    oq["col"] = oq["parameter"] + " (" + oq["unit"] + ")"
    piv = oq.pivot_table(index=["station", "provider", "km"], columns="col", values="value", aggfunc="last")
    age = oq.groupby(["station", "provider", "km"])["age_h"].min().rename("Last reading (h ago)")
    tbl = piv.join(age).reset_index().sort_values("km")
    tbl = tbl.rename(columns={"station": "Sensor", "provider": "Run by", "km": "Distance (km)"})
    st.dataframe(tbl.round(1), hide_index=True, width="stretch")
    st.caption("Raw concentrations as reported by each provider. Data via OpenAQ (openaq.org).")


# --------------------------------------------------------------------------- tab: compare

def tab_compare(loc: dict) -> None:
    opts = list(QUICK)
    if loc["name"] not in opts:
        opts = [loc["name"]] + opts
    default = list(dict.fromkeys([loc["name"], "Lahore", "Delhi", "Beijing", "London"]))[:5]
    cities = st.multiselect("Cities (type any city to add it)", opts, default=default, accept_new_options=True,
                            max_selections=8, key="cmp_cities")
    c2, c3 = st.columns([3, 1], vertical_alignment="bottom")
    var = c2.segmented_control("Show", ["pm2_5", "us_aqi", "pm10", "nitrogen_dioxide", "ozone"],
                               format_func=VAR_SHORT.get, default="pm2_5", key="cmp_var", required=True)
    days = c3.number_input("Past days", 1, 30, 7, key="cmp_days")
    if not cities:
        st.info("Pick at least one city.")
        return

    points, names, missing = [], [], []
    for c in cities:
        if c in QUICK:
            points.append(QUICK[c][:2]); names.append(c)
        elif c == loc["name"]:
            points.append((loc["lat"], loc["lon"])); names.append(c)
        else:
            try:
                g = src.geocode(c, 1)
            except src.SourceError:
                g = []
            if g:
                points.append((g[0]["lat"], g[0]["lon"])); names.append(g[0]["name"])
            else:
                missing.append(c)
    if missing:
        st.caption("Could not find: " + ", ".join(missing))
    if not points:
        return
    try:
        frames = src.model_multi(tuple((round(a, 3), round(b, 3)) for a, b in points), var, int(days), 2)
    except src.SourceError as e:
        st.warning(f"Comparison data unavailable ({e}).")
        return

    now = pd.Timestamp.now(tz="UTC").tz_localize(None).floor("h")
    who = POLLUTANTS.get(var, {}).get("who")
    palette = ["#4493F8", "#F2C94C", "#A66CFF", "#3FBF6F", "#F2994A", "#EB5757", "#9AA8BD", "#FF8FC7"]
    fig = go.Figure()
    rows = []
    for i, (name, f) in enumerate(zip(names, frames)):
        if f.empty or var not in f:
            continue
        fig.add_scatter(x=f["time"], y=f[var], name=name, mode="lines",
                        line=dict(color=palette[i % len(palette)], width=2))
        past = f[f["time"] <= now]
        cur_v = past[var].dropna().iloc[-1] if not past[var].dropna().empty else float("nan")
        rows.append({"City": name, "Now": cur_v, "Average": past[var].mean(), "Worst": past[var].max(),
                     **({"Hours above safe limit": int((past[var] > who).sum())} if who else {})})
    fig.add_shape(type="line", x0=now, x1=now, yref="paper", y0=0, y1=1,
                  line=dict(color="#8B949E", width=1, dash="dash"))
    if who:
        fig.add_hline(y=who, line=dict(color="#EB5757", width=1, dash="dash"),
                      annotation_text="Safe limit (WHO)", annotation_font_color="#EB5757")
    fig.update_xaxes(title="Time (UTC)")
    ui.section(f"{VAR_LABELS[var]}: past {days} days and next 2 days")
    st.plotly_chart(ui.style_fig(fig, 400), width="stretch", config={"displaylogo": False})

    if rows:
        t = pd.DataFrame(rows).sort_values("Now", ascending=True)
        colors = [band_for(v).color if var == "us_aqi" else who_color(v, who) for v in t["Now"]]
        c1, c2 = st.columns([1, 1], gap="large")
        with c1:
            ui.section("Worst air right now")
            fig2 = go.Figure(go.Bar(x=t["Now"], y=t["City"], orientation="h", marker_color=colors,
                                    text=t["Now"].round(0), textposition="outside",
                                    hovertemplate="%{y}: %{x:.1f}<extra></extra>"))
            st.plotly_chart(ui.style_fig(fig2, 60 + 42 * len(t), legend=False), width="stretch",
                            config={"displaylogo": False})
        with c2:
            ui.section("Summary")
            st.dataframe(t.sort_values("Now", ascending=False).round(1), hide_index=True, width="stretch")


# --------------------------------------------------------------------------- tab: about

def tab_about() -> None:
    st.markdown("""
#### What is the Air Quality Index (AQI)?
A single number from 0 to 500 that tells you how clean or polluted the air is. **Lower is better.**
Anything up to 50 is good, and above 150 the air is bad for everyone. The colours below are used
everywhere in this app.
""")
    ui.legend()
    st.markdown("""
#### Where do the numbers come from?
* **Air monitors.** Official measuring stations run by governments and embassies, shared by the
  World Air Quality Index project (aqicn.org). These are real measurements, updated every hour.
* **Satellite estimates.** Europe's Copernicus service (CAMS) combines satellite pictures with weather
  data to estimate the air everywhere on Earth, including places with no monitor. It also forecasts
  the next 5 days.
* **Weather.** Wind, temperature and humidity from Open-Meteo. Wind blows pollution away; still,
  calm air lets it build up.
* **Extra sensors (optional).** OpenAQ adds more government, research and low cost sensors.

#### Measured or estimated?
If an air monitor is within 40 km, the big number on the first tab is a real measurement.
If not, it is a satellite estimate. Estimates are good for the general picture but can miss a busy
road or a local fire, so a nearby monitor is always more accurate.

#### What is the "safe limit"?
The World Health Organization's recommended maximum for each pollutant over a day. Being above it
now and then is common in big cities; being far above it day after day is what harms health.

#### What do PM2.5, PM10 and the others mean?
| Short name | In plain words | Where it comes from |
|---|---|---|
| PM2.5 | Fine dust | Traffic, factories, burning crops or rubbish. The most harmful. |
| PM10 | Dust | Roads, building sites, pollen |
| NO₂ | Traffic fumes | Car and truck exhaust |
| O₃ | Smog (ozone) | Sunlight reacting with pollution on hot days |
| SO₂ | Factory smoke | Coal and oil burning, brick kilns |
| CO | Carbon monoxide | Engines, generators, stoves |
""")
    with st.expander("For developers: running it yourself"):
        st.markdown("""
Put your keys in `.streamlit/secrets.toml` (or a `.env` file, or Streamlit Cloud secrets):

```toml
AQICN_API_TOKEN = "your_waqi_token"
OPENAQ_API_KEY = "your_openaq_key"   # optional
```
""")


# --------------------------------------------------------------------------- main

def main() -> None:
    ui.inject_css()
    init_state()
    past_days = sidebar()
    loc = st.session_state.loc

    with st.spinner(f"Loading air quality for {loc['name']}..."):
        data = load_location(loc, past_days)
    now = model_now(data["model"])
    tz = data["model"]["tz_abbr"] if data["model"] else "UTC"
    ui.topbar(f"{now.strftime('%a %d %b, %H:%M')} {tz}")

    for name, err in data["errors"].items():
        st.toast(f"{name}: {err}", icon=":material/warning:")

    tabs = st.tabs([":material/air: Right now", ":material/map: Map", ":material/monitoring: Past & forecast",
                    ":material/sensors: Nearby monitors", ":material/compare_arrows: Compare cities",
                    ":material/info: How it works"])
    with tabs[0]:
        tab_now(loc, data)
    with tabs[1]:
        tab_map(loc)
    with tabs[2]:
        tab_trends(loc, data, past_days)
    with tabs[3]:
        tab_nearby(loc)
    with tabs[4]:
        tab_compare(loc)
    with tabs[5]:
        tab_about()


if __name__ == "__main__":
    main()
