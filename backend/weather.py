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


async def fetch_asos_weather(lat: float, lon: float) -> dict:
    """
    Fetch the latest ASOS/AWOS surface observation from the nearest NWS
    observation station.  Uses api.weather.gov (US only, no key required).

    Returns a dict compatible with the wx-data schema used by the frontend.
    Raises ValueError if no station with valid wind data is found.
    Raises httpx.HTTPError / Exception on network errors.
    """
    import math as _math

    def _haversine_km(la1, lo1, la2, lo2):
        R = 6371.0
        dlat = _math.radians(la2 - la1)
        dlon = _math.radians(lo2 - lo1)
        a = _math.sin(dlat/2)**2 + _math.cos(_math.radians(la1)) * \
            _math.cos(_math.radians(la2)) * _math.sin(dlon/2)**2
        return R * 2 * _math.asin(_math.sqrt(max(0, min(1, a))))

    def _metar_cloud_fraction(layers: list) -> float:
        """METAR cloud layers → 0-1 cover fraction."""
        cover_map = {"FEW": 0.18, "SCT": 0.44, "BKN": 0.75, "OVC": 1.0}
        return max((cover_map.get(lyr.get("amount", ""), 0.0) for lyr in layers), default=0.0)

    NWS_HDR = {"User-Agent": "WMD-Plotter/2.4 (emergency-planning; noreply@whitwerx.com)"}

    async with httpx.AsyncClient(timeout=12.0) as client:
        # Step 1 — grid-point lookup gives us the nearest observation stations URL
        r = await client.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", headers=NWS_HDR)
        r.raise_for_status()
        stations_url = r.json()["properties"]["observationStations"]

        # Step 2 — list nearby stations (up to 10, sorted by distance by NWS)
        r2 = await client.get(stations_url + "?limit=10", headers=NWS_HDR)
        r2.raise_for_status()
        stations = r2.json().get("features", [])

        # Step 3 — walk stations until one has a valid wind observation
        for feat in stations[:6]:
            sp = feat["properties"]
            sid  = sp.get("stationIdentifier", "")
            name = sp.get("name", sid)
            coords = feat.get("geometry", {}).get("coordinates", [None, None])
            slon, slat = coords[0], coords[1]
            dist_km = _haversine_km(lat, lon, slat, slon) if (slat and slon) else 0.0

            try:
                r3 = await client.get(
                    f"https://api.weather.gov/stations/{sid}/observations/latest",
                    headers=NWS_HDR,
                    timeout=8.0,
                )
                if r3.status_code != 200:
                    continue
                obs = r3.json()["properties"]
            except Exception:
                continue

            wspd_raw = obs.get("windSpeed",     {}).get("value")
            wdir_raw = obs.get("windDirection",  {}).get("value")
            if wspd_raw is None:          # no valid wind obs → try next
                continue

            wspd_ms  = round(float(wspd_raw), 2)
            wspd_mph = round(wspd_ms * 2.237, 1)
            wdir     = round(float(wdir_raw), 0) if wdir_raw is not None else 0.0
            wdir_lbl = _deg_to_cardinal(wdir) if wdir_raw is not None else "VAR"

            gust_raw  = obs.get("windGust", {}).get("value")
            gust_ms   = round(float(gust_raw), 1)  if gust_raw else None
            gust_mph  = round(float(gust_raw) * 2.237, 1) if gust_raw else None

            temp_raw  = obs.get("temperature",  {}).get("value")   # °C
            temp_c    = round(float(temp_raw), 1)  if temp_raw is not None else None
            temp_f    = round(temp_c * 9/5 + 32, 1) if temp_c is not None else None

            cloud_layers   = obs.get("cloudLayers", [])
            cloud_fraction = _metar_cloud_fraction(cloud_layers)
            cloud_pct      = round(cloud_fraction * 100)

            raw_metar  = obs.get("rawMessage", "")
            obs_time   = obs.get("timestamp",  "")

            from dispersion import determine_stability_class
            solar_el   = _estimate_solar_elevation(lat, lon)
            is_day     = solar_el > 0
            stability  = determine_stability_class(wspd_ms, is_day, cloud_fraction, solar_el)

            return {
                "station_id":        sid,
                "station_name":      name,
                "distance_km":       round(dist_km, 1),
                "obs_time_utc":      obs_time,
                "wind_speed_ms":     wspd_ms,
                "wind_speed_mph":    wspd_mph,
                "wind_gust_ms":      gust_ms,
                "wind_gust_mph":     gust_mph,
                "wind_dir_from_deg": wdir,
                "wind_dir_label":    wdir_lbl,
                "temp_f":            temp_f,
                "temp_c":            temp_c,
                "cloud_cover_pct":   cloud_pct,
                "raw_metar":         raw_metar,
                "stability_class":   stability,
                "stability_desc":    _stability_description(stability),
                "source":            f"ASOS/AWOS — {sid}",
                # NWS compat fields expected by frontend wxData schema
                "wind_gusts_ms":     gust_ms,
                "wind_gusts_mph":    gust_mph,
                "is_day":            is_day,
                "solar_elevation_deg": round(solar_el, 1),
                "weather_code":      0,
                "weather_desc":      f"ASOS obs — {sid}",
                "humidity_pct":      None,
            }

    raise ValueError("No nearby ASOS station returned valid wind data")


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
