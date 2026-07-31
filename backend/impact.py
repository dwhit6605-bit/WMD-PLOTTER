"""
Impact assessment — what falls inside the hazard zones.

Given the computed hazard contours and a set of points of interest (the facility
library, HIFLD infrastructure), work out which points sit inside which zone and
assign each to the most severe zone that contains it.

Pure Python, no dependencies. All geometry is in [lat, lon] degrees; distances
are haversine metres. Contours are treated as planar polygons in lat/lon, which
is fine at the scale of a dispersion footprint (kilometres) and matches how the
contours were generated in the first place.
"""

import math
from typing import Optional

EARTH_RADIUS_M = 6_371_000.0


# ── Geometry ─────────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def point_in_ring(lat: float, lon: float, ring: list) -> bool:
    """Ray casting. `ring` is [[lat, lon], ...]; first/last need not repeat.

    A point exactly on an edge is not guaranteed either way — acceptable here,
    since a facility on the precise boundary of a modelled contour is already
    inside the uncertainty of the model.
    """
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = ring[i][0], ring[i][1]      # lat, lon
        yj, xj = ring[j][0], ring[j][1]
        # Does a horizontal ray at `lat` cross edge (i, j)?
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def ring_area_deg2(ring: list) -> float:
    """Shoelace area in degrees². Used only to rank zones by size, so absolute
    units do not matter — a smaller polygon is the more severe (inner) zone."""
    n = len(ring)
    if n < 3:
        return 0.0
    area = 0.0
    j = n - 1
    for i in range(n):
        yi, xi = ring[i][0], ring[i][1]
        yj, xj = ring[j][0], ring[j][1]
        area += (xj + xi) * (yj - yi)
        j = i
    return abs(area) / 2.0


# ── Zone extraction ──────────────────────────────────────────────────────────

def extract_zones(overlays: dict) -> list:
    """Flatten the caller's overlay state into a ranked list of hazard zones.

    Each overlay tool stores `contours` as {level: {latlon, label, color, ...}}.
    Returns one entry per contour that has a polygon, ordered most-severe first
    (smallest area). Ranking by area means a point is naturally assigned to the
    innermost zone it falls in, which is the conservative choice for a warning.
    """
    zones = []
    for tool, state in (overlays or {}).items():
        if not isinstance(state, dict):
            continue
        contours = state.get("contours")
        if not isinstance(contours, dict):
            continue
        src_lat = state.get("source_lat")
        src_lon = state.get("source_lon")
        for level, info in contours.items():
            if not isinstance(info, dict):
                continue
            ring = info.get("latlon") or []
            if len(ring) < 3:
                continue
            zones.append({
                "tool": tool,
                "level": level,
                "label": info.get("label") or level,
                "color": info.get("color") or "#888888",
                "ring": ring,
                "area": ring_area_deg2(ring),
                "source_lat": src_lat,
                "source_lon": src_lon,
            })
    # Smallest (innermost / most severe) first.
    zones.sort(key=lambda z: z["area"])
    return zones


# ── Assessment ───────────────────────────────────────────────────────────────

def assess(zones: list, points: list) -> dict:
    """Assign each point to the most severe zone that contains it.

    `points` is [{lat, lon, name, category, kind, ...}]. Every key other than
    lat/lon/name is passed through untouched, so callers can carry whatever
    metadata they like (facility type, HIFLD layer, source id).

    Returns a structure the UI can render directly:
        {
          "zones": [ {level, label, color, tool, count,
                      by_category: {hospital: 2, ...},
                      points: [ {..., distance_m} ] }, ... ],
          "total": int,
          "by_category": {hospital: 3, school: 5, ...},
          "unaffected": int,     # candidates checked but in no zone
        }
    Zones with nothing in them are omitted, so the UI only shows what matters.
    """
    # zones are already most-severe-first; assign to the first that contains.
    buckets = {id(z): [] for z in zones}
    total_by_category: dict = {}
    hit = 0

    for pt in points:
        lat, lon = pt.get("lat"), pt.get("lon")
        if lat is None or lon is None:
            continue
        for z in zones:
            if point_in_ring(lat, lon, z["ring"]):
                enriched = dict(pt)
                if z["source_lat"] is not None and z["source_lon"] is not None:
                    enriched["distance_m"] = round(
                        haversine_m(z["source_lat"], z["source_lon"], lat, lon), 1
                    )
                buckets[id(z)].append(enriched)
                cat = pt.get("category") or pt.get("kind") or "other"
                total_by_category[cat] = total_by_category.get(cat, 0) + 1
                hit += 1
                break

    out_zones = []
    for z in zones:
        pts = buckets[id(z)]
        if not pts:
            continue
        by_cat: dict = {}
        for p in pts:
            cat = p.get("category") or p.get("kind") or "other"
            by_cat[cat] = by_cat.get(cat, 0) + 1
        pts.sort(key=lambda p: p.get("distance_m", 0.0))
        out_zones.append({
            "tool": z["tool"],
            "level": z["level"],
            "label": z["label"],
            "color": z["color"],
            "count": len(pts),
            "by_category": by_cat,
            "points": pts,
        })

    return {
        "zones": out_zones,
        "total": hit,
        "by_category": total_by_category,
        "unaffected": len(points) - hit,
    }
