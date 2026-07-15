"""
Southern California open-source facility & infrastructure import.

Data sources:
  HIFLD (ArcGIS REST) — hospitals, petroleum refineries, water treatment,
                         chemical storage, power plants, schools
  EPA ECHO (web services) — chemical (SIC 28) and petroleum (SIC 29)
                             facilities within 150 mi of SoCal center

All external requests run in parallel via asyncio.gather so the whole
import completes in the time of the slowest single response (~10s).

Called by POST /api/admin/facilities/import/socal
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# SoCal bounding box (WGS-84)
XMIN, YMIN, XMAX, YMAX = -120.5, 32.5, -114.0, 34.9

# Center of SoCal for radius-based queries (ECHO API)
SOCAL_LAT, SOCAL_LON = 33.9, -117.7  # approx centroid of LA/OC/IE/SD
SOCAL_RADIUS_MI = 150                  # covers LA→San Diego + IE + Ventura

# HIFLD feature service layers — failed layers are silently skipped
HIFLD_LAYERS = [
    {
        "label": "Hospitals (HIFLD)",
        "url": (
            "https://services1.arcgis.com/0MSEUqKaxRlEPj5g"
            "/arcgis/rest/services/Hospitals2/FeatureServer/0/query"
        ),
        "fac_type":    "hospital",
        "name_field":  "NAME",
        "note_fields": ["BEDS", "TRAUMA", "TYPE"],
    },
    {
        "label": "Petroleum Refineries (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Petroleum_Refineries/FeatureServer/0/query"
        ),
        "fac_type":    "refinery",
        "name_field":  "NAME",
        "note_fields": ["OPERATOR", "NAICS_CODE"],
    },
    {
        "label": "Water Treatment Plants (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Water_Treatment_Plants_US/FeatureServer/0/query"
        ),
        "fac_type":    "water",
        "name_field":  "NAME",
        "note_fields": ["OWNER_TYPE", "CAPACITY"],
    },
    {
        "label": "Chemical Storage Facilities (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Chemical_Storage_Facilities/FeatureServer/0/query"
        ),
        "fac_type":    "chemical",
        "name_field":  "NAME",
        "note_fields": ["NAICS_CODE"],
    },
    {
        "label": "Power Plants (HIFLD/EIA)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Power_Plants/FeatureServer/0/query"
        ),
        "fac_type":    "industrial",
        "name_field":  "Plant_Name",
        "note_fields": ["PrimSource", "Total_MW", "Utility_Na"],
    },
    {
        "label": "Natural Gas Compressor Stations (HIFLD)",
        "url": (
            "https://services1.arcgis.com/Hp6G80Pky0om7QvQ"
            "/arcgis/rest/services/Natural_Gas_Compressor_Stations/FeatureServer/0/query"
        ),
        "fac_type":    "industrial",
        "name_field":  "NAME",
        "note_fields": ["OPERATOR"],
    },
    {
        "label": "Urgent Care Facilities (HIFLD)",
        "url": (
            "https://services1.arcgis.com/wQnFk5ouCfPzTlPw"
            "/arcgis/rest/services/Urgent_Care_Facilities/FeatureServer/0/query"
        ),
        "fac_type":    "hospital",
        "name_field":  "NAME",
        "note_fields": [],
    },
    {
        "label": "Public Schools (HIFLD)",
        "url": (
            "https://services1.arcgis.com/cRvLdSPAsRupRo7I"
            "/arcgis/rest/services/Public_Schools_/FeatureServer/0/query"
        ),
        "fac_type":    "school",
        "name_field":  "NAME",
        "note_fields": ["ENROLLMENT", "LEVEL_"],
    },
]

# EPA ECHO — SIC 2-digit prefixes to pull separately (radius-based, CA only)
ECHO_SIC_GROUPS = [
    ("28", "chemical",    "Chemicals (SIC 28)"),
    ("29", "refinery",    "Petroleum (SIC 29)"),
    ("33", "industrial",  "Primary Metals (SIC 33)"),
    ("49", "industrial",  "Utilities (SIC 49)"),
]

ECHO_SEARCH_URL = "https://echo.epa.gov/tools/web-services/facility-search-data/search"


# ── HIFLD fetch ───────────────────────────────────────────────────────────────

def _build_notes(attrs: dict, fields: list) -> str:
    parts = []
    for f in fields:
        v = attrs.get(f)
        if v is not None and str(v).strip() and str(v) not in ("-9999", "None", ""):
            parts.append(f"{f}: {v}")
    return " · ".join(parts)


async def _fetch_hifld_layer(client: httpx.AsyncClient, layer: dict) -> tuple:
    """Returns (label, records_list) or raises on error."""
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
    r = await client.get(layer["url"], params=params, timeout=12)
    r.raise_for_status()
    data = r.json()

    if "error" in data:
        raise ValueError(data["error"].get("message", "ArcGIS error"))

    records = []
    for feat in data.get("features", []):
        attrs = feat.get("attributes") or {}
        geom  = feat.get("geometry")  or {}
        lon   = geom.get("x")
        lat   = geom.get("y")
        if lat is None or lon is None:
            continue
        if not (XMIN <= lon <= XMAX and YMIN <= lat <= YMAX):
            continue

        name = str(
            attrs.get(layer["name_field"]) or attrs.get("NAME") or ""
        ).strip()
        if not name or name.upper() in ("NONE", "NULL", "N/A", "UNKNOWN", "-"):
            continue

        notes = _build_notes(attrs, layer.get("note_fields", []))
        records.append({
            "name":     name,
            "fac_type": layer["fac_type"],
            "lat":      round(float(lat), 6),
            "lon":      round(float(lon), 6),
            "notes":    f"[{layer['label']}]{' ' + notes if notes else ''}",
        })
    return layer["label"], records


# ── EPA ECHO fetch ────────────────────────────────────────────────────────────

async def _fetch_echo(
    client: httpx.AsyncClient,
    sic2: str,
    fac_type: str,
    label: str,
) -> tuple:
    """Returns (label, records_list) or raises on error."""
    params = {
        "output":       "JSON",
        "p_lat":        str(SOCAL_LAT),
        "p_lon":        str(SOCAL_LON),
        "p_radius":     str(SOCAL_RADIUS_MI),
        "p_st":         "CA",
        "p_sic2":       sic2,
        "responseset":  "500",
    }
    r = await client.get(ECHO_SEARCH_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    facilities = (
        data.get("Results", {}).get("Facilities") or
        data.get("results", {}).get("facilities") or
        []
    )

    records = []
    for fac in facilities:
        name = str(fac.get("FacilityName") or fac.get("facility_name") or "").strip()
        if not name:
            continue

        try:
            lat = float(fac.get("Latitude83") or fac.get("Latitude82") or fac.get("latitude") or 0)
            lon = float(fac.get("Longitude83") or fac.get("Longitude82") or fac.get("longitude") or 0)
        except (TypeError, ValueError):
            continue
        if not lat or not lon:
            continue
        if not (XMIN <= lon <= XMAX and YMIN <= lat <= YMAX):
            continue

        city = str(fac.get("FacilityCity") or fac.get("city") or "").strip().title()
        sic  = str(fac.get("PrimarySICCode") or fac.get("sic") or sic2).strip()
        records.append({
            "name":     name,
            "fac_type": fac_type,
            "lat":      round(lat, 6),
            "lon":      round(lon, 6),
            "notes":    f"[EPA ECHO {label}] SIC {sic} · {city}, CA",
        })
    return label, records


# ── Deduplication ─────────────────────────────────────────────────────────────

def _dedupe(candidates: list, existing_names: set) -> list:
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
    Fetch SoCal facilities from all sources in parallel and insert into the DB.
    Returns {added, skipped, sources, errors}.
    """
    from db import create_facility, list_facilities

    existing = {f["name"].upper().strip() for f in list_facilities()}

    candidates = []
    source_counts: dict = {}
    errors = []

    async with httpx.AsyncClient() as client:
        # ── Fire all requests in parallel ─────────────────────────────────────
        hifld_coros = [_fetch_hifld_layer(client, layer) for layer in HIFLD_LAYERS]
        echo_coros  = [_fetch_echo(client, sic, ft, lbl) for sic, ft, lbl in ECHO_SIC_GROUPS]

        results = await asyncio.gather(
            *hifld_coros, *echo_coros,
            return_exceptions=True,
        )

        for res in results:
            if isinstance(res, Exception):
                errors.append(str(res))
                logger.debug("socal_import: source failed — %s", res)
            else:
                label, records = res
                if records:
                    source_counts[label] = len(records)
                    candidates.extend(records)

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
        "errors":  [e for e in errors if e],  # omit blank
    }
