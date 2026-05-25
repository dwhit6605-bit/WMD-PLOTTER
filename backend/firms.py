"""
NASA FIRMS (Fire Information for Resource Management System).

Fetches VIIRS S-NPP NRT fire hotspots via the FIRMS Area API (CSV).
FRP (Fire Radiative Power, MW) and confidence are the key fields.

API key: free at https://firms.modaps.eosdis.nasa.gov/api/area/
Set FIRMS_MAP_KEY environment variable. Falls back to DEMO_KEY which is
severely rate-limited (≈10 req/IP/day) and suitable only for testing.

Units: FRP in MW, coordinates in WGS-84.
"""

import csv
import io
import math
import os

import httpx

FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "DEMO_KEY")
_SOURCE = "VIIRS_SNPP_NRT"
_BASE   = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def _bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat   # west, south, east, north


async def fetch_firms_hotspots(
    lat: float,
    lon: float,
    radius_km: float = 200,
    days: int = 1,
) -> dict:
    """
    Return GeoJSON FeatureCollection of VIIRS fire hotspots within radius_km
    of (lat, lon) for the past `days` days.

    Feature properties:
      type        "firms_hotspot"
      frp         Fire Radiative Power (MW)
      confidence  "l" low / "n" nominal / "h" high
      acq_date    YYYY-MM-DD acquisition date (UTC)
      acq_time    HHMM acquisition time (UTC)
      daynight    "D" daytime / "N" nighttime
    """
    w, s, e, n = _bbox(lat, lon, radius_km)
    url = f"{_BASE}/{FIRMS_MAP_KEY}/{_SOURCE}/{w:.4f},{s:.4f},{e:.4f},{n:.4f}/{days}"

    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    text = resp.text.strip()

    # FIRMS returns XML error page when key is invalid / rate-limited
    if not text or text.startswith("<?xml") or text.startswith("<html"):
        return {
            "type": "FeatureCollection", "features": [], "count": 0,
            "using_demo_key": FIRMS_MAP_KEY == "DEMO_KEY",
            "source": f"NASA FIRMS {_SOURCE}",
        }

    features: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            feat_lat = float(row["latitude"])
            feat_lon = float(row["longitude"])
            frp      = float(row.get("frp") or 0)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [feat_lon, feat_lat]},
                "properties": {
                    "type":       "firms_hotspot",
                    "frp":        round(frp, 2),
                    "confidence": row.get("confidence", "n"),
                    "acq_date":   row.get("acq_date", ""),
                    "acq_time":   row.get("acq_time", ""),
                    "daynight":   row.get("daynight", ""),
                },
            })
        except (ValueError, KeyError):
            continue

    return {
        "type":           "FeatureCollection",
        "features":       features,
        "count":          len(features),
        "using_demo_key": FIRMS_MAP_KEY == "DEMO_KEY",
        "source":         f"NASA FIRMS {_SOURCE} · {days}d window",
    }
