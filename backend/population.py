"""
Population impact estimator — US Census Bureau APIs.

Data sources (all free, no key required for basic use):
  Census Geocoder  : lat/lon → state + county FIPS
  Census ACS 5-yr  : county total population (2022 5-year estimates)
  TIGER WMS REST   : county land area (AREALAND in m²)

Uniform-density assumption: zone_population = density × zone_area_km²
Accuracy: ±50–500% depending on urban/rural character of county.
"""

import math
import httpx

CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
CENSUS_ACS      = "https://api.census.gov/data/2022/acs/acs5"
TIGER_WMS       = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/86/query"


async def _get_county_fips(lat: float, lon: float) -> dict:
    params = {"x": lon, "y": lat, "benchmark": "2020", "vintage": "2020", "format": "json"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(CENSUS_GEOCODER, params=params)
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
    params = {
        "get": "B01003_001E",
        "for": f"county:{county_fips}",
        "in":  f"state:{state_fips}",
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(CENSUS_ACS, params=params)
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
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(TIGER_WMS, params=params)
        data = r.json()
    feats = data.get("features", [])
    if not feats:
        raise ValueError("County area not found in TIGER WMS")
    return feats[0]["attributes"]["AREALAND"] / 1_000_000.0  # m² → km²


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
    Falls back to a heuristic density if Census APIs fail.
    """
    try:
        fips   = await _get_county_fips(incident_lat, incident_lon)
        pop    = await _get_county_population(fips["state_fips"], fips["county_fips"])
        area   = await _get_county_area_km2(fips["geoid"])
        density = pop / area if area > 0 else 100.0
        source  = f"US Census ACS 2022 · {fips['county_name']}"
        fallback = False
    except Exception:
        density  = 100.0   # generic suburban fallback (people/km²)
        pop      = 0
        area     = 0.0
        source   = "Fallback estimate (Census unavailable) — 100 people/km²"
        fips     = {"county_name": "Unknown", "geoid": ""}
        fallback = True

    zone_results = []
    for z in zones:
        latlon    = z.get("latlon", [])
        area_km2  = _polygon_area_km2(latlon)
        pop_est   = int(density * area_km2)
        zone_results.append({
            "level":       z.get("level", ""),
            "label":       z.get("label", z.get("level", "")),
            "color":       z.get("color", "#888"),
            "area_km2":    round(area_km2, 3),
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
        "accuracy_note":        (
            "Uniform county density — actual may vary ±50–500% by land use. "
            "Urban cores will be underestimated; rural periphery overestimated."
        ),
    }
