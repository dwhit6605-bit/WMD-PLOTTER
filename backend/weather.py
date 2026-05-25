"""
Weather client for WMD Plotter — Open-Meteo API (keyless).

Fetches current conditions and determines Pasquill-Gifford stability class.
API docs: https://open-meteo.com/en/docs
"""

import math
import httpx
from datetime import datetime, timezone
from typing import Optional


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Current-hour variables to request
CURRENT_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "weather_code",
    "is_day",
]


async def fetch_weather(lat: float, lon: float) -> dict:
    """
    Fetch current weather from Open-Meteo for a given lat/lon.
    Returns a dict with processed weather data and stability class.
    Raises httpx.HTTPError on network failures.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(CURRENT_VARS),
        "wind_speed_unit": "ms",     # m/s instead of km/h
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})

    wind_speed_ms  = float(current.get("wind_speed_10m", 3.0) or 3.0)
    wind_dir_from  = float(current.get("wind_direction_10m", 270.0) or 270.0)
    wind_gusts_ms  = float(current.get("wind_gusts_10m", wind_speed_ms) or wind_speed_ms)
    cloud_cover_pct = float(current.get("cloud_cover", 50.0) or 50.0)
    temp_f         = float(current.get("temperature_2m", 70.0) or 70.0)
    humidity_pct   = float(current.get("relative_humidity_2m", 60.0) or 60.0)
    is_day         = bool(current.get("is_day", 1))
    weather_code   = int(current.get("weather_code", 0) or 0)

    cloud_cover_fraction = cloud_cover_pct / 100.0

    # Estimate solar elevation from UTC time and latitude (rough)
    solar_el = _estimate_solar_elevation(lat, lon)

    # Determine Pasquill-Gifford stability class
    from dispersion import determine_stability_class
    stability = determine_stability_class(
        wind_speed_ms=wind_speed_ms,
        is_daytime=is_day,
        cloud_cover_fraction=cloud_cover_fraction,
        solar_elevation_deg=solar_el,
    )

    # Wind direction label
    wind_dir_label = _deg_to_cardinal(wind_dir_from)

    return {
        "wind_speed_ms": round(wind_speed_ms, 1),
        "wind_speed_mph": round(wind_speed_ms * 2.237, 1),
        "wind_dir_from_deg": round(wind_dir_from, 0),
        "wind_dir_label": wind_dir_label,
        "wind_gusts_ms": round(wind_gusts_ms, 1),
        "wind_gusts_mph": round(wind_gusts_ms * 2.237, 1),
        "cloud_cover_pct": round(cloud_cover_pct, 0),
        "temp_f": round(temp_f, 1),
        "temp_c": round((temp_f - 32) * 5 / 9, 1),
        "humidity_pct": round(humidity_pct, 0),
        "is_day": is_day,
        "weather_code": weather_code,
        "weather_desc": _wmo_code_to_desc(weather_code),
        "solar_elevation_deg": round(solar_el, 1),
        "stability_class": stability,
        "stability_desc": _stability_description(stability),
        "source": "Open-Meteo",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _estimate_solar_elevation(lat: float, lon: float) -> float:
    """
    Rough estimate of current solar elevation angle in degrees.
    Accurate to ±2–3° for short-range planning purposes.
    """
    now_utc = datetime.now(timezone.utc)
    day_of_year = now_utc.timetuple().tm_yday
    hour_utc = now_utc.hour + now_utc.minute / 60.0

    # Solar hour angle (15° per hour, noon = 0)
    solar_noon_utc = 12.0 - lon / 15.0
    hour_angle_deg = (hour_utc - solar_noon_utc) * 15.0

    # Solar declination (Spencer, 1971)
    B = math.radians(360 / 365.0 * (day_of_year - 81))
    declination_deg = 23.45 * math.sin(B)

    lat_r  = math.radians(lat)
    dec_r  = math.radians(declination_deg)
    ha_r   = math.radians(hour_angle_deg)

    sin_el = (
        math.sin(lat_r) * math.sin(dec_r)
        + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)
    )
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_el))))


def _deg_to_cardinal(deg: float) -> str:
    """Convert degrees (from) to 16-point cardinal direction string."""
    dirs = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    idx = int((deg + 11.25) / 22.5) % 16
    return dirs[idx]


def _stability_description(cls: str) -> str:
    return {
        "A": "A — Extremely Unstable (strong convection)",
        "B": "B — Moderately Unstable",
        "C": "C — Slightly Unstable",
        "D": "D — Neutral (overcast / strong wind)",
        "E": "E — Slightly Stable (clear night)",
        "F": "F — Moderately Stable (calm clear night)",
    }.get(cls, cls)


def _wmo_code_to_desc(code: int) -> str:
    """WMO weather interpretation code → human description."""
    lookup = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Icy fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Thunderstorm w/ slight hail", 99: "Thunderstorm w/ heavy hail",
    }
    return lookup.get(code, f"WMO code {code}")
