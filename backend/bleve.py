"""
BLEVE (Boiling Liquid Expanding Vapor Explosion) Fireball Model.

References:
  Roberts, A.F. (1982). Thermal radiation hazards from releases of LPG fires and BLEVE.
    Fire Safety Journal, 4(3), 197-212.
  SFPE Handbook of Fire Protection Engineering (5th Ed), Section 3.
  TNO Yellow Book (2005). Methods for the Calculation of Physical Effects.

Fireball parameters (Roberts 1982):
  r_f = 3.24 × M^0.325         [m] — fireball radius (M = fuel mass in kg)
  t_f = 1.07 × M^0.26          [s] — duration (M < 30,000 kg)
  t_f = 0.23 × M^0.444         [s] — duration (M ≥ 30,000 kg)
  H_f = 0.75 × (2 × r_f)       [m] — fireball center height above ground

Ground-level thermal flux at horizontal distance D (m) from center:
  r_slant = √(D² + H_f²)
  q = SEP × (r_f / r_slant)² × τ_a    [kW/m²]
  τ_a = 0.75 (nominal atmospheric transmissivity)
"""

import math
from typing import Optional

FUELS: list[dict] = [
    {"id": "propane",   "name": "Propane (LPG)",             "sep": 200, "notes": "Most common BLEVE fuel · pressurized tank"},
    {"id": "lpg",       "name": "LPG (butane/propane mix)",  "sep": 185, "notes": "Mixed liquefied petroleum gas"},
    {"id": "lng",       "name": "LNG (Liquefied Nat. Gas)",  "sep": 220, "notes": "Methane — very high SEP"},
    {"id": "gasoline",  "name": "Gasoline",                  "sep": 130, "notes": "Automotive fuel tank / tanker"},
    {"id": "ethylene",  "name": "Ethylene",                  "sep": 170, "notes": "Industrial petrochemical"},
    {"id": "hydrogen",  "name": "Hydrogen",                  "sep": 110, "notes": "Fuel cell / cryogenic storage"},
    {"id": "ammonia",   "name": "Ammonia",                   "sep": 90,  "notes": "Refrigerant / agricultural · toxic"},
    {"id": "methanol",  "name": "Methanol",                  "sep": 120, "notes": "Solvent / racing fuel"},
    {"id": "acetylene", "name": "Acetylene",                 "sep": 200, "notes": "Welding gas · shock-sensitive"},
    {"id": "generic",   "name": "Generic BLEVE (unknown)",   "sep": 150, "notes": "Conservative default"},
]

THERMAL_ZONES: list[dict] = [
    {
        "level": "fireball",
        "label": "Fireball Zone",
        "q_kwm2": None,
        "color": "#8B0000",
        "desc": "Within the fireball — certain fatality · do not enter",
    },
    {
        "level": "lethal",
        "label": "Lethal Thermal Radiation (37.5 kW/m²)",
        "q_kwm2": 37.5,
        "color": "#CC0000",
        "desc": "1% lethality in 10 s · severe burns · immediate evacuation",
    },
    {
        "level": "severe",
        "label": "Severe Burns (12.5 kW/m²)",
        "q_kwm2": 12.5,
        "color": "#FF6600",
        "desc": "3rd-degree burns in 10 s · serious casualties",
    },
    {
        "level": "moderate",
        "label": "Significant Burns (4.0 kW/m²)",
        "q_kwm2": 4.0,
        "color": "#FFD700",
        "desc": "1st-degree burns in 10 s · shelter or evacuate immediately",
    },
    {
        "level": "pain",
        "label": "Pain / Discomfort (1.6 kW/m²)",
        "q_kwm2": 1.6,
        "color": "#E8E8A0",
        "desc": "Pain in 5–10 s · laceration risk from glass · evacuation recommended",
    },
]

TRANSMISSIVITY = 0.75


def fireball_params(mass_kg: float) -> dict:
    r_f = 3.24 * mass_kg ** 0.325
    t_f = 1.07 * mass_kg ** 0.26 if mass_kg < 30_000 else 0.23 * mass_kg ** 0.444
    h_f = 0.75 * (2.0 * r_f)
    return {"radius_m": r_f, "duration_s": t_f, "center_height_m": h_f}


def _thermal_flux(D_m: float, r_f: float, h_f: float, sep: float) -> float:
    if D_m <= 0:
        return 1e9
    r_slant = math.sqrt(D_m ** 2 + h_f ** 2)
    return sep * (r_f / r_slant) ** 2 * TRANSMISSIVITY


def _distance_for_flux(q_target: float, r_f: float, h_f: float, sep: float) -> Optional[float]:
    """Binary search: find ground distance D where thermal flux == q_target."""
    if _thermal_flux(r_f, r_f, h_f, sep) < q_target:
        return None
    d_lo, d_hi = r_f, 100_000.0
    if _thermal_flux(d_hi, r_f, h_f, sep) > q_target:
        return None
    for _ in range(80):
        d_mid = (d_lo + d_hi) / 2
        q = _thermal_flux(d_mid, r_f, h_f, sep)
        if abs(q - q_target) / q_target < 1e-6:
            break
        if q > q_target:
            d_lo = d_mid
        else:
            d_hi = d_mid
    return (d_lo + d_hi) / 2


def _circle_coords(lat: float, lon: float, radius_m: float, segments: int = 72) -> list:
    pts = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        dlat = (radius_m * math.cos(angle)) / 111_320
        dlon = (radius_m * math.sin(angle)) / (111_320 * math.cos(math.radians(lat)))
        pts.append([lon + dlon, lat + dlat])
    return pts


def compute_bleve_zones(lat: float, lon: float, mass_kg: float, fuel_id: str = "propane") -> dict:
    """
    Compute BLEVE thermal damage zones.
    Returns GeoJSON FeatureCollection + per-zone stats + fireball parameters.
    """
    fuel = next((f for f in FUELS if f["id"] == fuel_id), FUELS[-1])
    sep = fuel["sep"]
    fb = fireball_params(mass_kg)
    r_f, h_f, t_f = fb["radius_m"], fb["center_height_m"], fb["duration_s"]

    features: list[dict] = []
    stats: dict = {}

    # Fireball zone (the fireball itself)
    fb_zone = THERMAL_ZONES[0]
    features.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [_circle_coords(lat, lon, r_f)]},
        "properties": {
            "type": "bleve_zone",
            "level": "fireball",
            "label": fb_zone["label"],
            "color": fb_zone["color"],
            "q_kwm2": None,
            "radius_m": round(r_f, 1),
            "radius_km": round(r_f / 1000, 3),
            "desc": fb_zone["desc"],
        },
    })
    stats["fireball"] = {
        "label": fb_zone["label"],
        "color": fb_zone["color"],
        "q_kwm2": None,
        "radius_m": round(r_f, 1),
        "radius_km": round(r_f / 1000, 3),
        "desc": fb_zone["desc"],
    }

    # Thermal radiation zones
    for zone in THERMAL_ZONES[1:]:
        D = _distance_for_flux(zone["q_kwm2"], r_f, h_f, sep)
        if D is None or D < r_f:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_circle_coords(lat, lon, D)]},
            "properties": {
                "type": "bleve_zone",
                "level": zone["level"],
                "label": zone["label"],
                "color": zone["color"],
                "q_kwm2": zone["q_kwm2"],
                "radius_m": round(D, 1),
                "radius_km": round(D / 1000, 3),
                "desc": zone["desc"],
            },
        })
        stats[zone["level"]] = {
            "label": zone["label"],
            "color": zone["color"],
            "q_kwm2": zone["q_kwm2"],
            "radius_m": round(D, 1),
            "radius_km": round(D / 1000, 3),
            "desc": zone["desc"],
        }

    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"type": "bleve_source", "mass_kg": mass_kg, "fuel": fuel["name"]},
    })

    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "stats": stats,
        "fireball": {
            "radius_m": round(r_f, 1),
            "radius_km": round(r_f / 1000, 3),
            "duration_s": round(t_f, 1),
            "center_height_m": round(h_f, 1),
            "sep_kwm2": sep,
        },
        "fuel_id": fuel_id,
        "fuel_name": fuel["name"],
        "mass_kg": mass_kg,
    }
