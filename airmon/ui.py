"""Styling and small HTML components. Everything visual that is not a chart lives here."""
from __future__ import annotations

import html
import math

import plotly.graph_objects as go
import streamlit as st

from .aqi import BANDS, POLLUTANTS, actions_for, band_for, compass, is_num, who_color

CSS = """
<style>
:root{
  --bg:#FFFFFF; --panel:#F1F4F8; --panel-2:#E8EDF3; --line:#D5DCE4;
  --text:#1F2328; --muted:#5B6573; --accent:#0969DA;
  --mono:'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --display:'Inter', system-ui, sans-serif;
}
.block-container{padding-top:2.2rem; padding-bottom:4rem; max-width:1320px;}
[data-testid="stHeader"]{background:transparent;}

/* top bar */
.topbar{display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; flex-wrap:wrap;
  margin-bottom:1.1rem;}
.brand{font-family:var(--display); font-weight:700; font-size:1.55rem; letter-spacing:-.01em; line-height:1.1;}
.brand span{color:inherit;}
.tagline{color:var(--muted); font-size:.9rem; margin-top:.25rem;}
.livepill{display:inline-flex; align-items:center; gap:.45rem; font-size:.78rem; color:var(--muted);
  border:1px solid var(--line); border-radius:6px; padding:.3rem .7rem; background:var(--panel);}
.livepill i{width:7px; height:7px; border-radius:50%; background:#3FBF6F;}

/* hero */
.hero{position:relative; overflow:hidden; display:grid; grid-template-columns:minmax(0,1fr) minmax(170px,240px);
  gap:1.5rem;
  background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--band);
  border-radius:8px; padding:1.5rem 1.7rem;}
.eyebrow{font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:600;}
.place{font-family:var(--display); font-size:2rem; font-weight:700; line-height:1.05; margin:.35rem 0 .3rem;
  letter-spacing:-.02em;}
.sub{color:var(--muted); font-size:.88rem;}
.verdict{margin-top:1rem; font-size:1.02rem; max-width:62ch;}
.verdict b{color:color-mix(in srgb, var(--band) 72%, #000);}
.advice{margin-top:.45rem; color:var(--muted); font-size:.92rem; max-width:62ch;}
.dial{position:relative; z-index:1; min-width:170px; text-align:center; align-self:center;
  background:var(--band); color:var(--ink); border-radius:6px; padding:1rem 1.2rem .9rem;}
.dial .num{font-family:var(--display); font-size:3.3rem; font-variant-numeric:tabular-nums; font-weight:700; line-height:1;}
.dial .lbl{font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700; opacity:.8;}
.dial .cat{font-weight:600; font-size:.9rem; margin-top:.35rem;}
.second{margin-top:.6rem; font-size:.8rem; color:var(--muted); text-align:center;}
.scale{display:flex; height:6px; border-radius:2px; overflow:hidden; margin-top:1.2rem; position:relative;}
.scale div{flex:1;}
.scale-wrap{position:relative; max-width:520px;}
.marker{position:absolute; top:12px; width:2px; height:20px; background:var(--text);}
.marker:after{content:attr(data-v); position:absolute; top:20px; left:-14px; font-size:.7rem; color:var(--text);
  font-family:var(--mono);}
.ticks{display:flex; justify-content:space-between; font-size:.66rem; color:var(--muted); margin-top:.35rem;
  font-family:var(--mono); max-width:520px;}

/* pollutant cards */
.grid{display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:.75rem; margin:1rem 0 .4rem;}
.card{background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:.9rem 1rem;
  border-top:3px solid var(--band);}
.card .k{display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:0 .4rem;
  color:var(--muted); font-size:.78rem;}

.card .k b{color:var(--text); font-family:var(--display); font-size:1rem;}
.card .v{font-family:var(--display); font-size:1.75rem; font-weight:600; margin-top:.35rem; line-height:1.1;}
.card .v small{font-size:.75rem; color:var(--muted); font-weight:500; margin-left:.25rem;}
.chip{display:inline-block; font-size:.7rem; font-weight:600; padding:.12rem .5rem;
  background:var(--band); color:var(--ink); margin-top:.45rem; border-radius:4px;}
.who{font-size:.74rem; color:var(--muted); margin-top:.45rem;}
.who b{color:var(--text); font-weight:600;}
.bar{height:4px; background:var(--line); border-radius:4px; margin-top:.35rem; overflow:hidden;}
.bar div{height:100%;}

/* what to do */
.acts{display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:.6rem;}
.act{background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--c); border-radius:8px;
  padding:.7rem .9rem;}
.act span{display:block; font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.07em;}
.act b{font-family:var(--display); font-size:1.08rem; color:color-mix(in srgb, var(--c) 72%, #000); font-weight:600;}

/* outlook */
.outlook{display:grid; grid-template-columns:repeat(auto-fit, minmax(92px, 1fr)); gap:.55rem;}
.day{background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:.7rem .6rem;
  text-align:center;}
.day .d{font-size:.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em;}
.day .n{font-family:var(--display); font-size:1.5rem; font-weight:700; color:color-mix(in srgb, var(--band) 72%, #000); margin:.15rem 0;}
.day .c{font-size:.7rem; color:var(--muted); line-height:1.2;}

/* weather */
.wx{display:grid; grid-template-columns:repeat(2, 1fr); gap:.6rem;}
.wx div{background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:.7rem .85rem;}
.wx span{display:block; font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em;}
.wx b{font-family:var(--display); font-size:1.25rem; font-weight:600;}
.arrow{display:inline-block; margin-left:.35rem; color:var(--accent);}

/* legend + misc */
.legend{display:flex; flex-wrap:wrap; gap:.4rem .9rem; font-size:.78rem; color:var(--muted); margin:.4rem 0;}
.legend i{display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:.35rem;
  vertical-align:-1px;}
.src{display:inline-flex; align-items:center; gap:.4rem; font-size:.76rem; border:1px solid var(--line);
  border-radius:6px; padding:.2rem .6rem; margin:.15rem .25rem .15rem 0; color:var(--muted);}
.src i{width:7px; height:7px; border-radius:50%;}
.note{font-size:.8rem; color:var(--muted);}
.section{font-family:var(--display); font-weight:600; font-size:1.1rem; margin:1.4rem 0 .5rem;}
[data-testid="stSidebar"] .note{font-size:.76rem;}
@media (max-width: 720px){
  .hero{grid-template-columns:1fr; padding:1.2rem;}
  .place{font-size:1.8rem;}
  .dial{justify-self:start;}
}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def topbar(updated: str) -> None:
    st.markdown(
        f"""<div class="topbar">
  <div><div class="brand">Real-Time <span>Air Pollution</span> Monitor</div>
  <div class="tagline">See how clean the air is anywhere in the world, right now and for the next few days.</div></div>
  <div class="livepill"><i></i>Live · {esc(updated)}</div>
</div>""", unsafe_allow_html=True)


def _scale_html(aqi) -> str:
    segs = "".join(f'<div style="background:{b.color}"></div>' for b in BANDS)
    marker = ""
    if is_num(aqi):
        # piecewise position so each band gets equal width
        v = float(aqi)
        idx = next((i for i, b in enumerate(BANDS) if v <= b.hi), len(BANDS) - 1)
        b = BANDS[idx]
        hi = min(b.hi, 500)
        frac = 0 if hi == b.lo else min(max((v - b.lo) / (hi - b.lo), 0), 1)
        pos = (idx + frac) / len(BANDS) * 100
        marker = f'<div class="marker" style="left:{pos:.1f}%" data-v="{int(round(v))}"></div>'
    ticks = "".join(f"<span>{t}</span>" for t in (0, 50, 100, 150, 200, 300, "500"))
    return f'<div class="scale-wrap"><div class="scale">{segs}</div>{marker}</div><div class="ticks">{ticks}</div>'


def hero(name: str, sub: str, aqi, source_line: str, second_line: str, dominant: str = "") -> None:
    b = band_for(aqi)
    num = int(round(aqi)) if is_num(aqi) else "--"
    dom = f" Main cause: <b>{esc(dominant)}</b>." if dominant else ""
    st.markdown(f"""
<div class="hero" style="--band:{b.color}; --ink:{b.ink}">
  <div>
    <div class="eyebrow">{esc(source_line)}</div>
    <div class="place">{esc(name)}</div>
    <div class="sub">{esc(sub)}</div>
    <div class="verdict"><b>{esc(b.label)}.</b> {esc(b.summary)}{dom}</div>
    <div class="advice">{esc(b.advice)}</div>
    {_scale_html(aqi)}
  </div>
  <div>
    <div class="dial"><div class="lbl">Air Quality Index</div><div class="num">{num}</div><div class="cat">{esc(b.label)}</div></div>
    <div class="second">0 to 50 is good. The higher, the worse.</div><div class="second">{second_line}</div>
  </div>
</div>""", unsafe_allow_html=True)


def pollutant_cards(current: dict, station_iaqi: dict) -> None:
    cards = []
    for key, meta in POLLUTANTS.items():
        conc = current.get(key)
        sub = current.get(meta["aqi_key"])
        b = band_for(sub if is_num(sub) else station_iaqi.get(meta["waqi"]))
        if is_num(conc):
            val = f"{conc:,.0f}" if conc >= 100 else f"{conc:,.1f}"
        else:
            val = "--"
        ratio_html = ""
        if is_num(conc) and meta.get("who"):
            r = conc / meta["who"]
            w = min(r, 3) / 3 * 100
            txt = "Within the safe limit" if r <= 1 else f"<b>{r:.1f}×</b> the safe limit"
            ratio_html = (f'<div class="who">{txt}</div>'
                          f'<div class="bar"><div style="width:{w:.0f}%; background:{who_color(conc, meta["who"])}"></div></div>')
        chip = f'<span class="chip">{esc(b.label)}</span>' if b.lo >= 0 else ""
        cards.append(f"""<div class="card" style="--band:{b.color}; --ink:{b.ink}" title="{esc(meta['about'])}">
  <div class="k"><b>{esc(meta['plain'])}</b><span>{esc(meta['label'])}</span></div>
  <div class="v">{val}<small>{esc(meta['unit'])}</small></div>
  {chip}{ratio_html}
</div>""")
    st.markdown(f'<div class="grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def actions(aqi) -> None:
    rows = actions_for(aqi)
    if not rows:
        return
    tiles = "".join(f'<div class="act" style="--c:{c}"><span>{esc(t)}</span><b>{esc(v)}</b></div>'
                    for t, v, c in rows)
    st.markdown(f'<div class="acts">{tiles}</div>', unsafe_allow_html=True)


def outlook(days: list[dict]) -> None:
    tiles = []
    for d in days:
        b = band_for(d["aqi"])
        n = int(round(d["aqi"])) if is_num(d["aqi"]) else "--"
        tiles.append(f'<div class="day" style="--band:{b.color}"><div class="d">{esc(d["label"])}</div>'
                     f'<div class="n">{n}</div><div class="c">{esc(b.label)}</div></div>')
    st.markdown(f'<div class="outlook">{"".join(tiles)}</div>', unsafe_allow_html=True)


def weather(wx: dict) -> None:
    def f(v, fmt):
        return fmt.format(v) if is_num(v) else "--"
    wd = wx.get("wind_direction_10m")
    # arrow points where the wind blows *to*
    arrow = (f'<span class="arrow" style="transform:rotate({(float(wd) + 180) % 360:.0f}deg)">↑</span>'
             if is_num(wd) else "")
    st.markdown(f"""<div class="wx">
<div><span>Temperature</span><b>{f(wx.get('temperature_2m'), '{:.0f}')}°C</b></div>
<div><span>Humidity</span><b>{f(wx.get('relative_humidity_2m'), '{:.0f}')}%</b></div>
<div><span>Wind</span><b>{f(wx.get('wind_speed_10m'), '{:.0f}')} km/h {compass(wd)}</b>{arrow}</div>
<div><span>Pressure</span><b>{f(wx.get('surface_pressure'), '{:.0f}')} hPa</b></div>
</div>""", unsafe_allow_html=True)


def legend() -> None:
    items = "".join(
        f'<span><i style="background:{b.color}"></i>'
        f'{f"{b.lo} to {b.hi}" if b.hi < 1000 else f"{b.lo}+"} {esc(b.label)}</span>'
        for b in BANDS)
    st.markdown(f'<div class="legend">{items}</div>', unsafe_allow_html=True)


def source_chips(items: list[tuple[str, bool, str]]) -> None:
    out = []
    for name, ok, hint in items:
        col = "#3FBF6F" if ok else "#5B6B82"
        out.append(f'<span class="src" title="{esc(hint)}"><i style="background:{col}"></i>{esc(name)}</span>')
    st.markdown("".join(out), unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="section">{esc(title)}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 360, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color="#424A53", size=12),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D5DCE4", font_color="#1F2328"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)") if legend else None,
        showlegend=legend,
    )
    fig.update_xaxes(gridcolor="rgba(31,35,40,.09)", zeroline=False, linecolor="#D5DCE4")
    fig.update_yaxes(gridcolor="rgba(31,35,40,.09)", zeroline=False, linecolor="#D5DCE4")
    return fig


def fmt_age(minutes: float) -> str:
    if not is_num(minutes):
        return ""
    m = float(minutes)
    if m < 90:
        return f"{max(int(m), 0)} min ago"
    if m < 48 * 60:
        return f"{m / 60:.0f} h ago"
    return f"{m / 1440:.0f} days ago"


def nan_to_none(x):
    return None if (isinstance(x, float) and math.isnan(x)) else x
