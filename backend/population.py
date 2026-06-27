"""
Population impact estimator — US Census Bureau APIs.

Data sources (all free, no key required for Geocoder/TIGER; ACS requires free API key):
  Census Geocoder  : lat/lon → state + county FIPS  (no key needed)
  Census ACS 5-yr  : county total population (2023 5-year estimates, requires CENSUS_API_KEY)
  TIGER WMS REST   : county land area (AREALAND in m², no key needed)

Set CENSUS_API_KEY in .env to enable live ACS population data.
Free key: https://api.census.gov/data/key_signup.html

Uniform-density assumption: zone_population = density × zone_area_km²
Accuracy: ±50–500% depending on urban/rural character of county.
"""

import os
import math
import httpx

CENSUS_API_KEY  = os.environ.get("CENSUS_API_KEY", "")
CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
CENSUS_ACS      = "https://api.census.gov/data/2023/acs/acs5"
TIGER_WMS       = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/82/query"


async def _get_county_fips(lat: float, lon: float) -> dict:
    params = {"x": lon, "y": lat, "benchmark": "2020", "vintage": "2020", "format": "json"}
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        r = await c.get(CENSUS_GEOCODER, params=params)
    if r.status_code != 200:
        raise ValueError(f"Census Geocoder returned {r.status_code}")
    data = r.json()
    counties = data["result"]["geographies"].get("Counties", [])
    if not counties:
        raise ValueError("Location not covered by US Census data (outside USA?)")
    co = counties[0]
    return {
        "state_fips":  co["STATE"],
        "county_fips": co["COUNTY"],
        "county_name": co["NAME"],
        "geoid":       co["STATE"] + co["COUNTY"],
    }


async def _get_county_population(state_fips: str, county_fips: str) -> int:
    if not CENSUS_API_KEY:
        raise ValueError("CENSUS_API_KEY not set — skipping ACS lookup")
    params = {
        "get": "B01003_001E",
        "for": f"county:{county_fips}",
        "in":  f"state:{state_fips}",
        "key": CENSUS_API_KEY,
    }
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as c:
        r = await c.get(CENSUS_ACS, params=params)
    if r.status_code != 200:
        raise ValueError(f"Census ACS returned {r.status_code}")
    data = r.json()
    if len(data) < 2:
        raise ValueError("No ACS population data returned")
    return int(data[1][0])


async def _get_county_area_km2(geoid: str) -> float:
    params = {
        "where":          f"GEOID='{geoid}'",
        "outFields":      "AREALAND",
        "returnGeometry": "false",
        "f":              "json",
    }
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        r = await c.get(TIGER_WMS, params=params)
    if r.status_code != 200:
        raise ValueError(f"TIGER WMS returned {r.status_code}")
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        raise ValueError("County area not found in TIGER WMS")
    return int(feats[0]["attributes"]["AREALAND"]) / 1_000_000.0  # m² → km²


def _polygon_area_km2(latlon: list) -> float:
    """Shoelace formula for approximate polygon area on the ellipsoid (km²)."""
    if len(latlon) < 3:
        return 0.0
    avg_lat = sum(p[0] for p in latlon) / len(latlon)
    m_lat = 111_320.0
    m_lon = 111_320.0 * math.cos(math.radians(avg_lat))
    n = len(latlon)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = latlon[i][1] * m_lon, latlon[i][0] * m_lat
        x2, y2 = latlon[j][1] * m_lon, latlon[j][0] * m_lat
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 1_000_000.0


async def estimate_population_impact(
    incident_lat: float,
    incident_lon: float,
    zones: list[dict],   # [{"level": str, "label": str, "color": str, "latlon": [[lat,lon],...]}]
) -> dict:
    """
    Estimate exposed population per zone.
    Falls back to a heuristic density if Census APIs fail or CENSUS_API_KEY is not set.
    """
    fips = {"county_name": "Unknown", "geoid": ""}
    fallback = True
    fallback_reason = "Census unavailable"
    pop = 0
    area = 0.0

    try:
        fips = await _get_county_fips(incident_lat, incident_lon)

        # Try to get real area from TIGER (no key needed)
        try:
            area = await _get_county_area_km2(fips["geoid"])
        except Exception as e:
            raise ValueError(f"TIGER area lookup failed: {e}")

        # Try to get real population from ACS (key required)
        pop = await _get_county_population(fips["state_fips"], fips["county_fips"])

        density = pop / area if area > 0 else 100.0
        source  = f"US Census ACS 2023 · {fips['county_name']}"
        fallback = False
        fallback_reason = None

    except ValueError as e:
        msg = str(e)
        if "CENSUS_API_KEY not set" in msg:
            fallback_reason = "No CENSUS_API_KEY — add free key to .env for real data"
        elif "outside USA" in msg:
            fallback_reason = "Location outside USA — Census data not available"
        else:
            fallback_reason = f"Census API error: {msg}"
        density = 100.0
        source  = f"Fallback estimate ({fallback_reason}) — 100 people/km²"
    except Exception as e:
        fallback_reason = f"Unexpected error: {e}"
        density = 100.0
        source  = f"Fallback estimate — 100 people/km²"

    zone_results = []
    for z in zones:
        latlon   = z.get("latlon", [])
        area_km2 = _polygon_area_km2(latlon)
        pop_est  = int(density * area_km2)
        zone_results.append({
            "level":        z.get("level", ""),
            "label":        z.get("label", z.get("level", "")),
            "color":        z.get("color", "#888"),
            "area_km2":     round(area_km2, 3),
            "pop_estimate": pop_est,
        })

    return {
        "county_name":          fips.get("county_name", "Unknown"),
        "county_population":    pop,
        "county_area_km2":      round(area, 1),
        "pop_density_per_km2":  round(density, 1),
        "zones":                zone_results,
        "data_source":          source,
        "is_fallback":          fallback,
        "fallback_reason":      fallback_reason,
        "accuracy_note":        (
            "Uniform county density — actual may vary ±50–500% by land use. "
            "Urban cores will be underestimated; rural periphery overestimated."
        ),
    }
