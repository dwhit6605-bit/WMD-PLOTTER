"""
Blast Overpressure Model — Hopkinson-Cranz scaling with Brode (1955) equations.

References:
  Brode, H.L. (1955). Numerical Solutions of Spherical Blast Waves.
  Journal of Applied Physics, 26(6).
  UFC 3-340-02 (2008). Structures to Resist the Effects of Accidental Explosions.

Scaled distance:  Z = R / W^(1/3)   [m / kg^(1/3)]
Peak overpressure via Brode (two-regime):
  Near field  (Z < 0.5): Pso = 6.7/Z^3 + 1          (atm)
  Far field   (Z ≥ 0.5): Pso = 0.975/Z + 1.455/Z^2
                              + 5.85/Z^3 - 0.019      (atm)
1 atm = 101.325 kPa = 14.696 psi
"""

import math
from typing import Optional

# ── Explosive database (TNT mass equivalency factors) ─────────────────────────
EXPLOSIVES: list[dict] = [
    {"id": "tnt",        "name": "TNT",                         "factor": 1.00},
    {"id": "c4",         "name": "C-4 / RDX",                   "factor": 1.37},
    {"id": "petn",       "name": "PETN",                        "factor": 1.27},
    {"id": "semtex",     "name": "Semtex-H",                    "factor": 1.28},
    {"id": "anfo",       "name": "ANFO",                        "factor": 0.82},
    {"id": "an",         "name": "Ammonium Nitrate (pure)",      "factor": 0.42},
    {"id": "tatp",       "name": "TATP",                        "factor": 0.88},
    {"id": "black_pwd",  "name": "Black Powder",                "factor": 0.55},
    {"id": "gasoline",   "name": "Gasoline VCE (vapor cloud)",  "factor": 0.03},
    {"id": "propane",    "name": "Propane VCE (vapor cloud)",   "factor": 0.04},
]

# ── Damage zones (overpressure thresholds) ────────────────────────────────────
DAMAGE_ZONES: list[dict] = [
    {
        "level":  "fireball",
        "label":  "Fireball / Crater Zone",
        "psi":    20.0,
        "kPa":    137.9,
        "color":  "#6A0000",
        "desc":   "Complete destruction · extreme casualties",
    },
    {
        "level":  "severe",
        "label":  "Severe Structural Damage",
        "psi":    10.0,
        "kPa":    68.95,
        "color":  "#CC0000",
        "desc":   "Reinforced concrete heavily damaged · severe casualties",
    },
    {
        "level":  "moderate",
        "label":  "Moderate Structural Damage",
        "psi":    5.0,
        "kPa":    34.47,
        "color":  "#FF6600",
        "desc":   "Most structures collapse · serious injuries",
    },
    {
        "level":  "light",
        "label":  "Light Damage / Injuries",
        "psi":    1.0,
        "kPa":    6.895,
        "color":  "#FFD700",
        "desc":   "Doors/walls damaged · minor-to-moderate injuries",
    },
    {
        "level":  "glass",
        "label":  "Window Breakage / Hazard Zone",
        "psi":    0.5,
        "kPa":    3.447,
        "color":  "#FFFACD",
        "desc":   "Glass shatters · laceration risk",
    },
]

ATM_TO_KPA = 101.325


# ── Brode overpressure model ──────────────────────────────────────────────────

def overpressure_kPa(Z: float) -> float:
    """Peak side-on overpressure (kPa) from scaled distance Z (m/kg^1/3)."""
    if Z <= 0:
        return 1e9
    if Z < 0.5:
        P_atm = 6.7 / Z**3 + 1.0
    else:
        P_atm = 0.975 / Z + 1.455 / Z**2 + 5.85 / Z**3 - 0.019
    return max(P_atm, 0.0) * ATM_TO_KPA


def _scaled_distance_for_pressure(target_kPa: float) -> Optional[float]:
    """Bisection solver: find Z such that overpressure_kPa(Z) == target_kPa."""
    z_lo, z_hi = 0.01, 2000.0
    if overpressure_kPa(z_lo) < target_kPa:
        return None  # even at minimum Z, pressure too low — shouldn't happen
    if overpressure_kPa(z_hi) > target_kPa:
        return None  # even at maximum Z, pressure still above target
    for _ in range(80):
        z_mid = (z_lo + z_hi) / 2
        p = overpressure_kPa(z_mid)
        if abs(p - target_kPa) / target_kPa < 1e-7:
            break
        if p > target_kPa:
            z_lo = z_mid
        else:
            z_hi = z_mid
    return (z_lo + z_hi) / 2


# ── GeoJSON circle generator ──────────────────────────────────────────────────

def _circle_coords(lat: float, lon: float, radius_m: float, segments: int = 72) -> list:
    """Return a closed GeoJSON ring [[lon,lat],...] for a circle."""
    pts = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        dlat = (radius_m * math.cos(angle)) / 111_320
        dlon = (radius_m * math.sin(angle)) / (111_320 * math.cos(math.radians(lat)))
        pts.append([lon + dlon, lat + dlat])
    return pts


# ── Public API ────────────────────────────────────────────────────────────────

def compute_blast_zones(
    lat: float,
    lon: float,
    weight_kg: float,
    explosive_id: str = "tnt",
) -> dict:
    """
    Compute blast damage zones.
    Returns a dict with GeoJSON FeatureCollection and per-zone stats.
    """
    factor = next(
        (e["factor"] for e in EXPLOSIVES if e["id"] == explosive_id), 1.0
    )
    W_tnt = weight_kg * factor
    W_cbrt = W_tnt ** (1.0 / 3.0)

    features: list[dict] = []
    stats: dict = {}

    # Render outermost (lowest pressure) first so innermost is on top
    for zone in reversed(DAMAGE_ZONES):
        Z = _scaled_distance_for_pressure(zone["kPa"])
        if Z is None:
            continue
        radius_m = Z * W_cbrt
        if radius_m < 0.1:
            continue

        coords = _circle_coords(lat, lon, radius_m)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "type":      "blast_zone",
                "level":     zone["level"],
                "label":     zone["label"],
                "color":     zone["color"],
                "psi":       zone["psi"],
                "kPa":       zone["kPa"],
                "desc":      zone["desc"],
                "radius_m":  round(radius_m, 1),
                "radius_km": round(radius_m / 1000, 3),
            },
        })
        stats[zone["level"]] = {
            "label":     zone["level"],
            "full_label": zone["label"],
            "psi":       zone["psi"],
            "kPa":       zone["kPa"],
            "color":     zone["color"],
            "desc":      zone["desc"],
            "radius_m":  round(radius_m, 1),
            "radius_km": round(radius_m / 1000, 3),
        }

    # Detonation point marker
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"type": "blast_source", "weight_kg": weight_kg, "W_tnt_kg": round(W_tnt, 2)},
    })

    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "stats": stats,
        "W_tnt_kg": round(W_tnt, 2),
        "explosive_id": explosive_id,
        "weight_kg": weight_kg,
    }
