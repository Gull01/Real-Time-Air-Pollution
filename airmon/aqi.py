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
         "Air quality is satisfactory and poses little or no risk.",
         "A great day to be outside."),
    Band(51, 100, "Moderate", "#F2C94C", "#2B2100",
         "Acceptable for most people. Unusually sensitive people may notice effects.",
         "Unusually sensitive people should consider shorter or lighter outdoor activity."),
    Band(101, 150, "Unhealthy for sensitive groups", "#F2994A", "#2E1500",
         "People with heart or lung disease, older adults and children may be affected.",
         "Sensitive groups should reduce long or heavy outdoor exertion. Everyone else is usually fine."),
    Band(151, 200, "Unhealthy", "#EB5757", "#2B0303",
         "Everyone may begin to experience health effects.",
         "Sensitive groups should avoid long outdoor exertion and everyone else should cut it back. "
         "A well fitted N95 or KN95 mask helps outdoors."),
    Band(201, 300, "Very unhealthy", "#A66CFF", "#16052E",
         "Health alert: the risk of health effects is raised for everyone.",
         "Avoid outdoor exertion, keep windows closed and run an air purifier if you have one."),
    Band(301, 100000, "Hazardous", "#B4234A", "#FFFFFF",
         "Health warning of emergency conditions. Everyone is likely to be affected.",
         "Stay indoors with filtered air and avoid all outdoor activity."),
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
    "pm2_5": dict(label="PM2.5", name="Fine particles", unit="µg/m³", waqi="pm25", who=15,
                  aqi_key="us_aqi_pm2_5",
                  about="Particles under 2.5 µm. Reach deep into the lungs and bloodstream. Main drivers: "
                        "traffic, industry, crop and waste burning, dust."),
    "pm10": dict(label="PM10", name="Coarse particles", unit="µg/m³", waqi="pm10", who=45,
                 aqi_key="us_aqi_pm10",
                 about="Particles under 10 µm, such as road and construction dust, pollen and sea salt."),
    "nitrogen_dioxide": dict(label="NO₂", name="Nitrogen dioxide", unit="µg/m³", waqi="no2", who=25,
                             aqi_key="us_aqi_nitrogen_dioxide",
                             about="Mostly from vehicle exhaust and power plants. Irritates airways."),
    "ozone": dict(label="O₃", name="Ozone", unit="µg/m³", waqi="o3", who=100,
                  aqi_key="us_aqi_ozone",
                  about="Formed by sunlight acting on NOx and VOCs. Peaks on hot sunny afternoons."),
    "sulphur_dioxide": dict(label="SO₂", name="Sulphur dioxide", unit="µg/m³", waqi="so2", who=40,
                            aqi_key="us_aqi_sulphur_dioxide",
                            about="From burning sulphur rich coal and oil, smelters and volcanoes."),
    "carbon_monoxide": dict(label="CO", name="Carbon monoxide", unit="µg/m³", waqi="co", who=4000,
                            aqi_key="us_aqi_carbon_monoxide",
                            about="Colourless gas from incomplete combustion, mainly traffic and stoves."),
}

EXTRA_VARS: dict[str, dict] = {
    "dust": dict(label="Dust", unit="µg/m³"),
    "aerosol_optical_depth": dict(label="Aerosol optical depth", unit=""),
    "uv_index": dict(label="UV index", unit=""),
}

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
