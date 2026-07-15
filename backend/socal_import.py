"""
Southern California open-source facility & infrastructure import.

Data sources:
  HIFLD (ArcGIS REST) — hospitals, petroleum refineries, water treatment,
                         chemical storage, power plants
  EPA TRI (efservice)  — toxic-chemical-handling facilities (SIC 28/29/33/49)
                         across SoCal counties

Called by POST /api/admin/facilities/import/socal
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# SoCal bounding box (WGS-84)
XMIN, YMIN, XMAX, YMAX = -120.5, 32.5, -114.0, 34.9

SOCAL_COUNTIES = [
    "LOS ANGELES", "ORANGE", "SAN DIEGO",
    "RIVERSIDE", "SAN BERNARDINO", "VENTURA", "IMPERIAL",
]

# HIFLD feature service layers — failed layers are silently skipped
HIFLD_LAYERS = [
    {
        "label": "Hospitals (HIFLD)",
        "url": (
            "https://services1.arcgis.com/0MSEUqKaxRlEPj5g"
            "/arcgis/rest/services/Hospitals2/FeatureServer/0/query"
        ),
        "fac_type":   "hospital",
        "name_field": "NAME",
        "note_fields": ["BEDS", "TRAUMA", "TYPE"],
    },
    {
        "label": "Petroleum Refineries (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Petroleum_Refineries/FeatureServer/0/query"
        ),
        "fac_type":   "refinery",
        "name_field": "NAME",
        "note_fields": ["OPERATOR", "NAICS_CODE", "CAPACITY"],
    },
    {
        "label": "Water Treatment Plants (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Water_Treatment_Plants_US/FeatureServer/0/query"
        ),
        "fac_type":   "water",
        "name_field": "NAME",
        "note_fields": ["OWNER_TYPE", "CAPACITY"],
    },
    {
        "label": "Chemical Storage Facilities (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Chemical_Storage_Facilities/FeatureServer/0/query"
        ),
        "fac_type":   "chemical",
        "name_field": "NAME",
        "note_fields": ["NAICS_CODE"],
    },
    {
        "label": "Power Plants (EIA/HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Power_Plants/FeatureServer/0/query"
        ),
        "fac_type":   "industrial",
        "name_field": "Plant_Name",
        "note_fields": ["PrimSource", "Total_MW", "Utility_Na"],
    },
    {
        "label": "Urgent Care (HIFLD)",
        "url": (
            "https://services1.arcgis.com/wQnFk5ouCfPzTlPw"
            "/arcgis/rest/services/Urgent_Care_Facilities/FeatureServer/0/query"
        ),
        "fac_type":   "hospital",
        "name_field": "NAME",
        "note_fields": [],
    },
    {
        "label": "Public Schools (HIFLD)",
        "url": (
            "https://services1.arcgis.com/cRvLdSPAsRupRo7I"
            "/arcgis/rest/services/Public_Schools_/FeatureServer/0/query"
        ),
        "fac_type":   "school",
        "name_field": "NAME",
        "note_fields": ["ENROLLMENT", "LEVEL_"],
    },
    {
        "label": "Natural Gas Compressor Stations (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Natural_Gas_Compressor_Stations/FeatureServer/0/query"
        ),
        "fac_type":   "industrial",
        "name_field": "NAME",
        "note_fields": ["OPERATOR"],
    },
]

# TRI SIC 2-digit prefixes considered CBRN-relevant
TRI_SIC_PREFIXES = {"28", "29", "33", "49"}

EPA_TRI_URL = "https://data.epa.gov/efservice/tri_facility/state_abbr/=CA/county_name/={county}/rows/0:500/JSON"


# ── HIFLD fetch ───────────────────────────────────────────────────────────────

def _build_notes(attrs: dict, fields: list) -> str:
    parts = []
    for f in fields:
        v = attrs.get(f)
        if v is not None and str(v).strip() and str(v) != "-9999":
            parts.append(f"{f}: {v}")
    return " · ".join(parts)


async def _fetch_hifld_layer(client: httpx.AsyncClient, layer: dict) -> list[dict]:
    params = {
        "where":             "1=1",
        "geometry":          f"{XMIN},{YMIN},{XMAX},{YMAX}",
        "geometryType":      "esriGeometryEnvelope",
        "spatialRel":        "esriSpatialRelIntersects",
        "inSR":              "4326",
        "outSR":             "4326",
        "outFields":         "*",
        "resultRecordCount": "1000",
        "returnGeometry":    "true",
        "f":                 "json",
    }
    r = await client.get(layer["url"], params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    results = []
    for feat in data.get("features", []):
        attrs = feat.get("attributes") or {}
        geom  = feat.get("geometry")  or {}
        lon   = geom.get("x")
        lat   = geom.get("y")
        if lat is None or lon is None:
            continue
        if not (XMIN <= lon <= XMAX and YMIN <= lat <= YMAX):
            continue

        name_field = layer["name_field"]
        name = str(attrs.get(name_field) or attrs.get("NAME") or "Unknown").strip()
        if not name or name.upper() in ("NONE", "NULL", "UNKNOWN", "N/A"):
            continue

        notes = _build_notes(attrs, layer.get("note_fields", []))
        results.append({
            "name":     name,
            "fac_type": layer["fac_type"],
            "lat":      round(float(lat), 6),
            "lon":      round(float(lon), 6),
            "notes":    f"[{layer['label']}] {notes}".strip(" ·"),
        })
    return results


# ── EPA TRI fetch ─────────────────────────────────────────────────────────────

async def _fetch_tri_county(client: httpx.AsyncClient, county: str) -> list[dict]:
    url = EPA_TRI_URL.format(county=county.replace(" ", "%20"))
    r = await client.get(url, timeout=30)
    r.raise_for_status()

    raw = r.json()
    # efservice returns a list of dicts with uppercase column names
    results = []
    for row in raw:
        # Filter to CBRN-relevant SIC codes
        sic = str(row.get("PRIMARY_SIC") or row.get("primary_sic") or "").strip()
        if sic[:2] not in TRI_SIC_PREFIXES:
            continue

        try:
            lat = float(row.get("LATITUDE")  or row.get("latitude")  or 0)
            lon = float(row.get("LONGITUDE") or row.get("longitude") or 0)
        except (TypeError, ValueError):
            continue
        if not lat or not lon:
            continue
        if not (XMIN <= lon <= XMAX and YMIN <= lat <= YMAX):
            continue

        name = str(row.get("FACILITY_NAME") or row.get("facility_name") or "").strip()
        if not name:
            continue

        city    = str(row.get("CITY") or row.get("city") or "").strip().title()
        sic_str = sic

        # Map SIC to facility type
        if sic[:2] == "29":
            fac_type = "refinery"
        elif sic[:2] == "28":
            fac_type = "chemical"
        elif sic[:2] == "33":
            fac_type = "industrial"
        elif sic[:2] == "49":
            fac_type = "industrial"
        else:
            fac_type = "industrial"

        results.append({
            "name":     name,
            "fac_type": fac_type,
            "lat":      round(lat, 6),
            "lon":      round(lon, 6),
            "notes":    f"[EPA TRI] SIC {sic_str} · {city}, CA",
        })
    return results


# ── Deduplication ─────────────────────────────────────────────────────────────

def _dedupe(candidates: list[dict], existing_names: set) -> list[dict]:
    """Remove candidates whose name already exists (case-insensitive) and internal dupes."""
    seen: set = set()
    out = []
    for c in candidates:
        key = c["name"].upper().strip()
        if key in existing_names or key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ── Main entry point ──────────────────────────────────────────────────────────

async def import_socal_facilities(created_by_id: int) -> dict:
    """
    Fetch SoCal facilities from all sources and insert into the DB.
    Returns {added, skipped, sources}.
    """
    from db import create_facility, list_facilities

    # Snapshot existing facility names so we don't duplicate
    existing = {f["name"].upper().strip() for f in list_facilities()}

    candidates: list[dict] = []
    source_counts: dict[str, int] = {}
    errors: list[str] = []

    async with httpx.AsyncClient() as client:
        # HIFLD layers
        for layer in HIFLD_LAYERS:
            try:
                items = await _fetch_hifld_layer(client, layer)
                source_counts[layer["label"]] = len(items)
                candidates.extend(items)
                logger.info("HIFLD %s: %d records", layer["label"], len(items))
            except Exception as exc:
                errors.append(f"{layer['label']}: {exc}")
                logger.warning("HIFLD layer failed — %s: %s", layer["label"], exc)

        # EPA TRI by county
        tri_total = 0
        for county in SOCAL_COUNTIES:
            try:
                items = await _fetch_tri_county(client, county)
                tri_total += len(items)
                candidates.extend(items)
            except Exception as exc:
                errors.append(f"EPA TRI {county}: {exc}")
                logger.warning("EPA TRI county failed — %s: %s", county, exc)
        if tri_total:
            source_counts["EPA TRI (SIC 28/29/33/49)"] = tri_total

    to_add = _dedupe(candidates, existing)

    added = 0
    for fac in to_add:
        try:
            create_facility(
                fac["name"], fac["fac_type"], fac["lat"], fac["lon"],
                None, None, 0.0, fac["notes"], created_by_id,
            )
            added += 1
        except Exception as exc:
            logger.warning("create_facility failed: %s", exc)

    return {
        "added":   added,
        "skipped": len(candidates) - added,
        "sources": source_counts,
        "errors":  errors,
    }
