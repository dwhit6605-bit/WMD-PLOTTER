"""
NIFC / WFIGS active wildfire perimeter data.

Queries the Wildland Fire Interagency Geospatial Services (WFIGS) REST API
for current active fire perimeters. Returns GeoJSON polygons with incident
name, acreage, behavior, and centroid coordinates.

No API key required. Returns all current US perimeters when no bbox given.

Reference: https://data-nifc.opendata.arcgis.com/
"""

import math

import httpx

_WFIGS_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services"
    "/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query"
)

_OUT_FIELDS = (
    "IncidentName,GISAcres,PerimeterCategory,"
    "PolygonDateTime,attr_FireBehaviorGeneral,attr_IncidentTypeCategory"
)


def _bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat   # west, south, east, north


def _ring_centroid(ring: list) -> tuple[float, float]:
    """Return (lat, lon) centroid of a GeoJSON coordinate ring [[lon,lat],...]."""
    if not ring:
        return 0.0, 0.0
    return (
        sum(c[1] for c in ring) / len(ring),
        sum(c[0] for c in ring) / len(ring),
    )


async def fetch_nifc_perimeters(
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 500,
) -> dict:
    """
    Return GeoJSON FeatureCollection of active wildfire perimeters,
    sorted by acreage descending (largest fires first).

    If lat/lon provided, filters by bounding box of radius_km.
    If lat/lon are None, returns all current US perimeters.
    """
    params: dict = {
        "where":          "1=1",
        "outFields":      _OUT_FIELDS,
        "returnGeometry": "true",
        "outSR":          "4326",
        "f":              "geojson",
    }

    if lat is not None and lon is not None:
        w, s, e, n = _bbox(lat, lon, radius_km)
        params.update({
            "geometry":     f"{w:.4f},{s:.4f},{e:.4f},{n:.4f}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel":   "esriSpatialRelIntersects",
            "inSR":         "4326",
        })

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_WFIGS_URL, params=params)
        resp.raise_for_status()
        raw = resp.json()

    features: list[dict] = []
    for feat in raw.get("features", []):
        props = feat.get("properties") or {}
        geom  = feat.get("geometry")  or {}
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue

        coords = geom["coordinates"]
        ring   = coords[0] if geom["type"] == "Polygon" else coords[0][0]
        cent_lat, cent_lon = _ring_centroid(ring)

        acres = props.get("GISAcres") or 0
        try:
            acres = round(float(acres), 1)
        except (TypeError, ValueError):
            acres = 0

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "type":          "nifc_perimeter",
                "name":          props.get("IncidentName")          or "Unknown Fire",
                "acres":         acres,
                "category":      props.get("PerimeterCategory")     or "",
                "updated":       props.get("PolygonDateTime")       or "",
                "behavior":      props.get("attr_FireBehaviorGeneral")   or "",
                "incident_type": props.get("attr_IncidentTypeCategory")  or "",
                "centroid_lat":  round(cent_lat, 5),
                "centroid_lon":  round(cent_lon, 5),
            },
        })

    features.sort(key=lambda f: f["properties"]["acres"], reverse=True)

    return {
        "type":     "FeatureCollection",
        "features": features,
        "count":    len(features),
        "source":   "NIFC / WFIGS Interagency Perimeters Current",
    }
