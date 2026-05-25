"""
HIFLD Open Data — DHS Homeland Infrastructure Foundation-Level Data.

Queries ArcGIS REST FeatureServices for US critical infrastructure within
a bounding box derived from (lat, lon, radius_km). No API key required.

Failed individual layers are silently skipped; partial results are returned.

Reference: https://hifld-geoplatform.opendata.arcgis.com/
"""

import math

import httpx

_BASE = "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services"

_LAYERS: list[dict] = [
    {
        "service":    "Hospitals/FeatureServer/0",
        "type":       "hospital",
        "name_field": "NAME",
        "extra":      ["BEDS", "TRAUMA", "TYPE"],
    },
    {
        "service":    "Fire_Stations/FeatureServer/0",
        "type":       "fire_station",
        "name_field": "NAME",
        "extra":      [],
    },
    {
        "service":    "EMS_Stations/FeatureServer/0",
        "type":       "ems",
        "name_field": "NAME",
        "extra":      [],
    },
    {
        "service":    "Public_Schools/FeatureServer/0",
        "type":       "school",
        "name_field": "NAME",
        "extra":      ["ENROLLMENT"],
    },
    {
        "service":    "Power_Plants/FeatureServer/0",
        "type":       "power_plant",
        "name_field": "NAME",
        "extra":      ["PRIMFUEL", "INSTCAP"],
    },
    {
        "service":    "Urgent_Care_Facilities/FeatureServer/0",
        "type":       "urgent_care",
        "name_field": "NAME",
        "extra":      [],
    },
    {
        "service":    "Nursing_Homes/FeatureServer/0",
        "type":       "nursing_home",
        "name_field": "NAME",
        "extra":      ["BEDS"],
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
    url = f"{_BASE}/{layer['service']}/query"
    out_fields = list({layer["name_field"], "NAME"} | set(layer.get("extra", [])))
    params = {
        "where":             "1=1",
        "geometry":          f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}",
        "geometryType":      "esriGeometryEnvelope",
        "spatialRel":        "esriSpatialRelIntersects",
        "inSR":              "4326",
        "outSR":             "4326",
        "outFields":         ",".join(out_fields),
        "resultRecordCount": "500",
        "returnGeometry":    "true",
        "f":                 "json",
    }
    resp = await client.get(url, params=params, timeout=15)
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
        name  = str(attrs.get(layer["name_field"]) or attrs.get("NAME") or "Unknown")
        extra = {k: attrs[k] for k in layer.get("extra", []) if attrs.get(k) is not None}
        items.append({
            "type":   layer["type"],
            "name":   name,
            "lat":    round(feat_lat, 6),
            "lon":    round(feat_lon, 6),
            "distKm": round(_haversine_km(lat, lon, feat_lat, feat_lon), 3),
            "source": "HIFLD",
            **extra,
        })
    return items


async def fetch_hifld_infra(lat: float, lon: float, radius_km: float = 5.0) -> list[dict]:
    """
    Return critical infrastructure from all HIFLD layers within radius_km.
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
