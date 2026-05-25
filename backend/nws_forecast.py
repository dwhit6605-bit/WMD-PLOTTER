"""
NOAA National Weather Service Gridpoint hourly forecast.

Two-step fetch:
  1. /points/{lat},{lon}  → returns gridpoint metadata including forecastHourly URL
  2. forecastHourly URL   → returns next 156 hourly periods

No API key required. US coverage only — raises HTTPStatusError for
non-US locations. Caller should catch and fall back to Open-Meteo.

Reference: https://www.weather.gov/documentation/services-web-api
"""

import httpx

# Cardinal/intercardinal → degrees FROM which wind blows (meteorological)
_DIR_DEG: dict[str, float] = {
    "N":   360, "NNE":  22, "NE":  45, "ENE":  67,
    "E":    90, "ESE": 112, "SE": 135, "SSE": 157,
    "S":   180, "SSW": 202, "SW": 225, "WSW": 247,
    "W":   270, "WNW": 292, "NW": 315, "NNW": 337,
    "VRB":   0,
}

_HEADERS = {
    "User-Agent": "WMD-Plotter/2.2 (open-source emergency planning tool)",
    "Accept":     "application/geo+json",
}


def _parse_wind_mph(speed_str: str) -> float:
    """Parse '10 mph' or '10 to 15 mph' → float mph."""
    try:
        return float(speed_str.strip().split()[0])
    except (ValueError, IndexError):
        return 0.0


def _stability_from_nws(is_daytime: bool, short_forecast: str) -> str:
    """
    Rough Pasquill-Gifford stability proxy from NWS forecast text.
    Daytime: A–D  /  Nighttime: D–F
    """
    fc = short_forecast.lower()
    if is_daytime:
        if any(w in fc for w in ("sunny", "clear", "fair")):
            return "B"
        if any(w in fc for w in ("partly", "few clouds", "isolated")):
            return "C"
        if any(w in fc for w in ("mostly cloudy", "overcast", "cloudy", "rain", "snow", "fog")):
            return "D"
        return "C"
    else:
        if any(w in fc for w in ("clear", "fair")):
            return "F"
        if any(w in fc for w in ("partly", "few clouds")):
            return "E"
        return "D"


async def fetch_nws_forecast(lat: float, lon: float) -> list[dict]:
    """
    Return next 24 hourly forecast periods for a US lat/lon.
    Each dict contains wind_speed_ms, wind_dir_from_deg, stability_class, etc.

    Raises httpx.HTTPStatusError for non-US coordinates.
    """
    async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
        r1 = await client.get(
            f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
        )
        r1.raise_for_status()
        hourly_url = r1.json()["properties"]["forecastHourly"]

        r2 = await client.get(hourly_url)
        r2.raise_for_status()
        periods = r2.json()["properties"]["periods"]

    result: list[dict] = []
    for p in periods[:24]:
        ws_mph    = _parse_wind_mph(p.get("windSpeed", "0 mph"))
        ws_ms     = round(ws_mph * 0.44704, 2)
        wd_label  = (p.get("windDirection") or "N").upper()
        wd_deg    = _DIR_DEG.get(wd_label, 0)
        is_day    = p.get("isDaytime", True)
        short_fc  = p.get("shortForecast", "")
        stability = _stability_from_nws(is_day, short_fc)

        result.append({
            "startTime":         p["startTime"],
            "wind_speed_ms":     ws_ms,
            "wind_speed_mph":    round(ws_mph, 1),
            "wind_dir_from_deg": wd_deg,
            "wind_dir_label":    wd_label,
            "stability_class":   stability,
            "stability_desc":    f"{stability} — NWS forecast proxy",
            "source":            "NWS Forecast",
            "temp_f":            p.get("temperature", 0),
            "cloud_cover_pct":   0,
            "short_forecast":    short_fc,
            "is_daytime":        is_day,
        })

    return result
