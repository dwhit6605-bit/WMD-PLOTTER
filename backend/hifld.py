"""
Critical Infrastructure — public ArcGIS REST sources.

Queries public ArcGIS FeatureServer / MapServer services for US critical
infrastructure within a bounding box derived from (lat, lon, radius_km).
No API key required.

Sources:
  Hospitals      — ArcGIS Online public (HIFLD Hospitals2)
  Fire Stations  — USGS National Structures MapServer layer 16
  EMS Stations   — USGS National Structures MapServer layer 15
  Public Schools — ArcGIS Online public (HIFLD Public Schools)
  Urgent Care    — ArcGIS Online public (HIFLD Urgent Care Facilities)

Failed individual layers are silently skipped; partial results are returned.

Reference: https://hifld-geoplatform.opendata.arcgis.com/
           https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer
"""

import math

import httpx

_LAYERS: list[dict] = [
    {
        "url":        (
            "https://services1.arcgis.com/0MSEUqKaxRlEPj5g"
            "/arcgis/rest/services/Hospitals2/FeatureServer/0/query"
        ),
        "type":       "hospital",
        "name_field": "NAME",
        "extra":      ["BEDS", "TRAUMA", "TYPE"],
    },
    {
        "url":        (
            "https://carto.nationalmap.gov/arcgis/rest/services"
            "/structures/MapServer/16/query"
        ),
        "type":       "fire_station",
        "name_field": "name",
        "extra":      [],
    },
    {
        "url":        (
            "https://carto.nationalmap.gov/arcgis/rest/services"
            "/structures/MapServer/15/query"
        ),
        "type":       "ems",
        "name_field": "name",
        "extra":      [],
    },
    {
        "url":        (
            "https://services1.arcgis.com/cRvLdSPAsRupRo7I"
            "/arcgis/rest/services/Public_Schools_/FeatureServer/0/query"
        ),
        "type":       "school",
        "name_field": "NAME",
        "extra":      ["ENROLLMENT"],
    },
    {
        "url":        (
            "https://services1.arcgis.com/wQnFk5ouCfPzTlPw"
            "/arcgis/rest/services/Urgent_Care_Facilities/FeatureServer/0/query"
        ),
        "type":       "urgent_care",
        "name_field": "NAME",
        "extra":      [],
    },
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def _bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat   # west, south, east, north


async def _query_layer(
    client: httpx.AsyncClient,
    layer: dict,
    lat: float,
    lon: float,
    radius_km: float,
) -> list[dict]:
    w, s, e, n = _bbox(lat, lon, radius_km)

    name_field = layer["name_field"]
    extra      = layer.get("extra", [])
    # Build deduplicated field list; always include the name field + NAME fallback
    field_set  = {name_field, "NAME"} | set(extra)
    out_fields = ",".join(sorted(field_set))

    params = {
        "where":             "1=1",
        "geometry":          f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}",
        "geometryType":      "esriGeometryEnvelope",
        "spatialRel":        "esriSpatialRelIntersects",
        "inSR":              "4326",
        "outSR":             "4326",
        "outFields":         out_fields,
        "resultRecordCount": "500",
        "returnGeometry":    "true",
        "f":                 "json",
    }

    resp = await client.get(layer["url"], params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items: list[dict] = []
    for feat in data.get("features", []):
        attrs    = feat.get("attributes") or {}
        geom     = feat.get("geometry")  or {}
        feat_lon = geom.get("x")
        feat_lat = geom.get("y")
        if feat_lat is None or feat_lon is None:
            continue

        # Name: try layer-specific field first, then "NAME" uppercase fallback
        name = (
            str(attrs.get(name_field) or attrs.get("NAME") or "Unknown").strip()
            or "Unknown"
        )

        extra_data = {k: attrs[k] for k in extra if attrs.get(k) is not None}
        items.append({
            "type":   layer["type"],
            "name":   name,
            "lat":    round(feat_lat, 6),
            "lon":    round(feat_lon, 6),
            "distKm": round(_haversine_km(lat, lon, feat_lat, feat_lon), 3),
            "source": "HIFLD",
            **extra_data,
        })
    return items


async def fetch_hifld_infra(lat: float, lon: float, radius_km: float = 5.0) -> list[dict]:
    """
    Return critical infrastructure from all layers within radius_km.
    Results sorted by distance. Failed layers are skipped silently.
    """
    all_items: list[dict] = []
    async with httpx.AsyncClient() as client:
        for layer in _LAYERS:
            try:
                items = await _query_layer(client, layer, lat, lon, radius_km)
                all_items.extend(items)
            except Exception:
                continue
    all_items.sort(key=lambda x: x["distKm"])
    return all_items
