"""US EPA AQI bands, pollutant metadata and small helpers shared by the app."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    lo: int
    hi: int
    label: str
    color: str
    ink: str  # readable text color on top of `color`
    summary: str
    advice: str

    @property
    def rgb(self) -> list[int]:
        h = self.color.lstrip("#")
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# Colors keep the familiar EPA meaning but are tuned to sit well on a dark UI.
BANDS: list[Band] = [
    Band(0, 50, "Good", "#3FBF6F", "#06210F",
         "The air is clean.",
         "A great day to be outside."),
    Band(51, 100, "Moderate", "#F2C94C", "#2B2100",
         "The air is okay for most people.",
         "If you are very sensitive to pollution, take it a bit easy outdoors."),
    Band(101, 150, "Unhealthy for sensitive people", "#F2994A", "#2E1500",
         "Not good for children, older people, and anyone with asthma, heart or lung problems.",
         "If that is you, keep outdoor activity short and light. Everyone else is usually fine."),
    Band(151, 200, "Unhealthy", "#EB5757", "#2B0303",
         "The air is bad for everyone.",
         "Spend less time outside, skip outdoor exercise, and wear an N95 mask if you go out."),
    Band(201, 300, "Very unhealthy", "#A66CFF", "#16052E",
         "The air is very bad. Everyone is at risk.",
         "Stay indoors as much as you can, keep windows shut, and use an air purifier if you have one."),
    Band(301, 100000, "Hazardous", "#B4234A", "#FFFFFF",
         "Emergency level. The air is dangerous to breathe.",
         "Stay indoors with windows shut and avoid all outdoor activity."),
]

NO_DATA = Band(-1, -1, "No data", "#5B6B82", "#FFFFFF", "No reading available.", "")


def is_num(x) -> bool:
    try:
        return x is not None and not math.isnan(float(x))
    except (TypeError, ValueError):
        return False


def to_num(x):
    """Convert API values like '57', '-', None to float or NaN."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def band_for(aqi) -> Band:
    if not is_num(aqi):
        return NO_DATA
    v = round(float(aqi))
    for b in BANDS:
        if b.lo <= v <= b.hi:
            return b
    return BANDS[-1] if v > 0 else BANDS[0]


def rgba_for(aqi, alpha: int = 200) -> list[int]:
    return band_for(aqi).rgb + [alpha]


def who_color(value, who) -> str:
    """Colour a concentration by how many times it exceeds the WHO guideline."""
    if not (is_num(value) and who):
        return "#5EC8F2"
    r = float(value) / who
    for lim, idx in ((1, 0), (2, 1), (4, 2), (8, 3)):
        if r <= lim:
            return BANDS[idx].color
    return BANDS[4].color


# Keys match Open-Meteo variable names. `waqi` is the WAQI iaqi key, `who` is the
# WHO 2021 short term guideline (24 h, ozone 8 h) in the same unit.
POLLUTANTS: dict[str, dict] = {
    "pm2_5": dict(label="PM2.5", plain="Fine dust", name="Fine particles", unit="µg/m³", waqi="pm25", who=15,
                  aqi_key="us_aqi_pm2_5",
                  about="Tiny particles from traffic, factories, and burning crops or rubbish. Small enough to "
                        "get deep into your lungs. Usually the most harmful pollutant."),
    "pm10": dict(label="PM10", plain="Dust", name="Coarse particles", unit="µg/m³", waqi="pm10", who=45,
                 aqi_key="us_aqi_pm10",
                 about="Bigger dust from roads, building sites and pollen. Irritates the nose, throat and eyes."),
    "nitrogen_dioxide": dict(label="NO₂", plain="Traffic fumes", name="Nitrogen dioxide", unit="µg/m³",
                             waqi="no2", who=25, aqi_key="us_aqi_nitrogen_dioxide",
                             about="Gas mostly from car and truck exhaust. Irritates the airways."),
    "ozone": dict(label="O₃", plain="Smog", name="Ozone", unit="µg/m³", waqi="o3", who=100,
                  aqi_key="us_aqi_ozone",
                  about="Ozone forms when sunlight hits pollution. Highest on hot, sunny afternoons."),
    "sulphur_dioxide": dict(label="SO₂", plain="Factory smoke", name="Sulphur dioxide", unit="µg/m³",
                            waqi="so2", who=40, aqi_key="us_aqi_sulphur_dioxide",
                            about="Gas from burning coal and oil in power plants, factories and brick kilns."),
    "carbon_monoxide": dict(label="CO", plain="Carbon monoxide", name="Carbon monoxide", unit="µg/m³",
                            waqi="co", who=4000, aqi_key="us_aqi_carbon_monoxide",
                            about="Invisible gas from engines, generators and stoves. Most dangerous in closed rooms."),
}

EXTRA_VARS: dict[str, dict] = {
    "dust": dict(label="Desert dust", unit="µg/m³"),
    "uv_index": dict(label="UV index", unit=""),
}


def pollutant_name(key: str) -> str:
    m = POLLUTANTS.get(key)
    return f"{m['plain']} ({m['label']})" if m else key


# Simple "what should I do" advice per AQI band: (title, [status per band], [colour level per band])
_ACTIONS = [
    ("Outdoor exercise", ["Go for it", "Fine for most", "Keep it light", "Avoid it", "Avoid it", "Avoid it"],
     [0, 0, 1, 2, 3, 3]),
    ("Windows", ["Open them", "Open them", "Close if sensitive", "Keep closed", "Keep closed", "Keep closed"],
     [0, 0, 1, 2, 3, 3]),
    ("Mask outside", ["Not needed", "Not needed", "If sensitive", "Wear an N95", "Wear an N95", "Wear an N95"],
     [0, 0, 1, 2, 3, 3]),
    ("Kids, elderly, asthma", ["All fine", "Mostly fine", "Limit time outside", "Stay indoors", "Stay indoors",
                               "Stay indoors"], [0, 1, 2, 3, 3, 3]),
]


def actions_for(aqi) -> list[tuple[str, str, str]]:
    b = band_for(aqi)
    if b.lo < 0:
        return []
    i = BANDS.index(b)
    return [(t, st[i], BANDS[lv[i]].color) for t, st, lv in _ACTIONS]


WAQI_TO_KEY = {v["waqi"]: k for k, v in POLLUTANTS.items()}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def compass(deg) -> str:
    if not is_num(deg):
        return ""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((float(deg) % 360) / 22.5 + 0.5) % 16]
