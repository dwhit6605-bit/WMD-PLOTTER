"""
Dense Gas Dispersion Model — Modified Pasquill-Gifford for heavier-than-air gases.

Physics basis:
  Dense gases resist vertical mixing due to negative buoyancy ("pancaking" effect).
  We model this by reducing σ_z by sqrt(density_ratio), where:
    density_ratio = ρ_gas / ρ_air

  This is conservative and appropriate for emergency planning.  Standard
  Gaussian lateral spread (σ_y) is retained; only vertical spread is reduced.

Reference: Hanna, S.R. & Drivas, P.J. (1987). Guidelines for Use of Vapor Cloud
           Dispersion Models. CCPS/AIChE.
           Ten Berge, W.F. et al. (1986). Concentration–time mortality relationship
           for irritant and systemically acting vapors and gases.

Units throughout: Q in g/s, concentrations in g/m³, distances in m.
"""

import math
from dispersion import (
    sigma_y as pg_sigma_y,
    sigma_z as pg_sigma_z,
    ppm_to_gm3,
    plume_to_latlon,
)

AIR_DENSITY = 1.29  # kg/m³ at 0°C, 1 atm (standard)

# ─────────────────────────────────────────────────────────────────────────────
# Gas database
# Each entry: id, name, formula, un (str), mw (g/mol), density_kg_m3,
#             thresholds (list of dicts), notes, flammable (bool),
#             warning (optional str)
# Thresholds ordered most-severe to least-severe (largest zone last rendered,
# smallest zone on top).
# ─────────────────────────────────────────────────────────────────────────────

DENSE_GAS_DB = {
    "cl2": {
        "id": "cl2",
        "name": "Chlorine",
        "formula": "Cl₂",
        "un": "1017",
        "mw": 70.9,
        "density_kg_m3": 2.93,
        "flammable": False,
        "notes": "Heavier-than-air; pools in low-lying areas and basements.",
        "warning": "Gas sinks into basements, trenches, and low areas — evacuate below-grade spaces first.",
        "thresholds": [
            {"id": "erpg3",  "label": "ERPG-3 / Life-Threatening",    "ppm": 20.0,  "color": "#FF1100"},
            {"id": "idlh",   "label": "IDLH / Immediately Dangerous", "ppm": 10.0,  "color": "#FF5500"},
            {"id": "erpg2",  "label": "ERPG-2 / Irreversible Effects", "ppm": 3.0,   "color": "#FF8C00"},
            {"id": "erpg1",  "label": "ERPG-1 / Mild Effects",        "ppm": 1.0,   "color": "#FFD700"},
        ],
    },
    "so2": {
        "id": "so2",
        "name": "Sulfur Dioxide",
        "formula": "SO₂",
        "un": "1079",
        "mw": 64.1,
        "density_kg_m3": 2.62,
        "flammable": False,
        "notes": "Heavier-than-air; sharp acidic odor. Industrial accident and volcanic hazard.",
        "thresholds": [
            {"id": "erpg3",  "label": "ERPG-3 / Life-Threatening",    "ppm": 15.0,  "color": "#FF1100"},
            {"id": "idlh",   "label": "IDLH / Immediately Dangerous", "ppm": 100.0, "color": "#FF5500"},
            {"id": "erpg2",  "label": "ERPG-2 / Irreversible Effects", "ppm": 3.0,   "color": "#FF8C00"},
            {"id": "erpg1",  "label": "ERPG-1 / Mild Effects",        "ppm": 0.3,   "color": "#FFD700"},
        ],
    },
    "h2s": {
        "id": "h2s",
        "name": "Hydrogen Sulfide",
        "formula": "H₂S",
        "un": "1053",
        "mw": 34.1,
        "density_kg_m3": 1.42,
        "flammable": True,
        "notes": "Slightly heavier than air; flammable. Common in oil & gas, sewage, and confined spaces.",
        "warning": "Olfactory fatigue — cannot rely on smell at high concentrations.",
        "thresholds": [
            {"id": "erpg3",  "label": "ERPG-3 / Life-Threatening",    "ppm": 50.0,  "color": "#FF1100"},
            {"id": "idlh",   "label": "IDLH / Immediately Dangerous", "ppm": 50.0,  "color": "#FF5500"},
            {"id": "erpg2",  "label": "ERPG-2 / Irreversible Effects", "ppm": 50.0,  "color": "#FF8C00"},
            {"id": "erpg1",  "label": "ERPG-1 / Mild Effects",        "ppm": 0.1,   "color": "#FFD700"},
        ],
    },
    "cg": {
        "id": "cg",
        "name": "Phosgene (CG)",
        "formula": "COCl₂",
        "un": "1076",
        "mw": 98.9,
        "density_kg_m3": 4.09,
        "flammable": False,
        "notes": "Chemical warfare agent precursor and industrial chemical. Very heavy gas.",
        "warning": "CWA precursor — pulmonary edema onset delayed 4–24 hours after exposure.",
        "thresholds": [
            {"id": "erpg3",  "label": "ERPG-3 / Life-Threatening",    "ppm": 1.5,   "color": "#FF1100"},
            {"id": "idlh",   "label": "IDLH / Immediately Dangerous", "ppm": 2.0,   "color": "#FF5500"},
            {"id": "erpg2",  "label": "ERPG-2 / Irreversible Effects", "ppm": 0.5,   "color": "#FF8C00"},
            {"id": "erpg1",  "label": "ERPG-1 / Mild Effects",        "ppm": 0.1,   "color": "#FFD700"},
        ],
    },
    "no2": {
        "id": "no2",
        "name": "Nitrogen Dioxide",
        "formula": "NO₂",
        "un": "1067",
        "mw": 46.0,
        "density_kg_m3": 1.88,
        "flammable": False,
        "notes": "Heavier than air; reddish-brown. Produced by combustion and industrial processes.",
        "thresholds": [
            {"id": "erpg3",  "label": "ERPG-3 / Life-Threatening",    "ppm": 25.0,  "color": "#FF1100"},
            {"id": "idlh",   "label": "IDLH / Immediately Dangerous", "ppm": 20.0,  "color": "#FF5500"},
            {"id": "erpg2",  "label": "ERPG-2 / Irreversible Effects", "ppm": 15.0,  "color": "#FF8C00"},
            {"id": "erpg1",  "label": "ERPG-1 / Mild Effects",        "ppm": 1.0,   "color": "#FFD700"},
        ],
    },
    "propane_v": {
        "id": "propane_v",
        "name": "Propane Vapor Cloud",
        "formula": "C₃H₈",
        "un": "1978",
        "mw": 44.1,
        "density_kg_m3": 1.83,
        "flammable": True,
        "notes": "Heavier than air; accumulates at grade. Explosion hazard — ignition source avoidance critical.",
        "thresholds": [
            {"id": "lfl",      "label": "LFL — Explosion Hazard (>2.1% v/v)", "ppm": 21000.0, "color": "#FF4400"},
            {"id": "half_lfl", "label": "½ LFL — Caution Zone",           "ppm": 10500.0, "color": "#FFAA00"},
        ],
    },
    "butane_v": {
        "id": "butane_v",
        "name": "Butane Vapor Cloud",
        "formula": "C₄H₁₀",
        "un": "1011",
        "mw": 58.1,
        "density_kg_m3": 2.42,
        "flammable": True,
        "notes": "Heavier than air; settles in low areas. Explosion and asphyxiation hazard.",
        "thresholds": [
            {"id": "lfl",      "label": "LFL — Explosion Hazard (>1.8% v/v)", "ppm": 18000.0, "color": "#FF4400"},
            {"id": "half_lfl", "label": "½ LFL — Caution Zone",           "ppm": 9000.0,  "color": "#FFAA00"},
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal dispersion helpers — dense-gas modified σ_z
# ─────────────────────────────────────────────────────────────────────────────

def _dz(x_m: float, stability: str, density_ratio: float) -> float:
    """
    Modified σ_z for dense gas: pg_sigma_z / sqrt(density_ratio).

    Dense gases have negative buoyancy that suppresses vertical mixing.
    Dividing by sqrt(density_ratio) reduces σ_z, which increases downwind
    ground-level concentrations — a conservative planning approach.
    """
    return pg_sigma_z(x_m, stability) / math.sqrt(density_ratio)


def _dc(
    x_m: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float,
    density_ratio: float,
) -> float:
    """
    Ground-level centreline concentration (g/m³) using dense-gas modified σ_z.

    Gaussian formula: C = Q / (π·σy·σz·u) · exp(-H²/2σz²)
    where σz is replaced by the dense-gas modified value.
    """
    if x_m <= 0:
        return 0.0
    u = max(u_ms, 0.5)
    sy = pg_sigma_y(x_m, stability)
    sz = _dz(x_m, stability, density_ratio)
    if sy <= 0 or sz <= 0:
        return 0.0
    vert = math.exp(-0.5 * (H_m / sz) ** 2)
    return (Q_gs / (math.pi * sy * sz * u)) * vert


def _dfind(
    threshold_gm3: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float,
    density_ratio: float,
    x_max: float = 200_000,
) -> float:
    """
    Binary search for maximum downwind extent (m) where centreline
    concentration >= threshold_gm3.  Returns 0 if threshold never met.
    Uses 60 iterations for sub-metre precision.
    """
    x_start = max(H_m * 2 + 1.0, 10.0)
    c_start = _dc(x_start, Q_gs, u_ms, stability, H_m, density_ratio)
    if c_start < threshold_gm3:
        return 0.0

    lo, hi = x_start, x_max
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        c_mid = _dc(mid, Q_gs, u_ms, stability, H_m, density_ratio)
        if c_mid >= threshold_gm3:
            lo = mid
        else:
            hi = mid
    return hi


def _dhw(
    x_m: float,
    threshold_gm3: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float,
    density_ratio: float,
) -> float:
    """
    Plume half-width (m) at downwind distance x where concentration >= threshold.
    Returns 0 if centreline concentration is below threshold.
    """
    c_center = _dc(x_m, Q_gs, u_ms, stability, H_m, density_ratio)
    if c_center <= threshold_gm3:
        return 0.0
    sy = pg_sigma_y(x_m, stability)
    ratio = c_center / threshold_gm3
    if ratio <= 1.0:
        return 0.0
    return sy * math.sqrt(2.0 * math.log(ratio))


def _dpoly(
    threshold_gm3: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float,
    density_ratio: float,
    n_points: int = 120,
) -> list[tuple[float, float]]:
    """
    Plume boundary polygon in local plume coordinates (x, y) in metres.

    Mirrors the pattern of dispersion.compute_plume_polygon but uses the
    dense-gas modified σ_z.  Returns a closed polygon list or [] if the
    threshold is never exceeded.
    """
    x_max = _dfind(threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio)
    if x_max <= 0:
        return []

    x_start = max(H_m * 2 + 1.0, 5.0)
    xs = [x_start + (x_max - x_start) * i / (n_points - 1) for i in range(n_points)]

    right_side: list[tuple[float, float]] = []
    left_side:  list[tuple[float, float]] = []

    for x in xs:
        hw = _dhw(x, threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio)
        if hw > 0:
            right_side.append((x,  hw))
            left_side.append( (x, -hw))

    if not right_side:
        return []

    polygon = [(x_start, 0.0)] + right_side + list(reversed(left_side)) + [(x_start, 0.0)]
    return polygon


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_dense_gas(gas_id: str) -> dict | None:
    """Return the DENSE_GAS_DB entry for gas_id, or None if not found."""
    return DENSE_GAS_DB.get(gas_id)


def list_dense_gases() -> list[dict]:
    """Return a list of all gas entries (all fields included)."""
    return [{"id": k, **v} for k, v in DENSE_GAS_DB.items()]


def compute_dense_gas_zones(
    lat: float,
    lon: float,
    gas_id: str,
    release_rate_kg_min: float,
    release_height_m: float,
    wind_speed_ms: float,
    wind_dir_from_deg: float,
    stability_class: str,
) -> dict:
    """
    Compute dense-gas dispersion hazard zones for a given release.

    Args:
        lat, lon:              Source location (decimal degrees).
        gas_id:                Key into DENSE_GAS_DB (e.g. "cl2").
        release_rate_kg_min:   Mass release rate (kg/minute).
        release_height_m:      Effective release height above ground (m).
        wind_speed_ms:         Mean wind speed at release height (m/s).
        wind_dir_from_deg:     Meteorological wind direction (degrees FROM which
                               wind blows; 0=N, 90=E).
        stability_class:       Pasquill-Gifford class ('A'–'F').

    Returns:
        {
            "geojson": GeoJSON FeatureCollection,
            "stats":   list of per-threshold dicts,
            "gas":     gas metadata (no thresholds list),
            "model":   run parameters and derived values,
        }
    """
    gas = DENSE_GAS_DB.get(gas_id)
    if gas is None:
        raise ValueError(f"Unknown gas_id: {gas_id!r}. "
                         f"Available: {list(DENSE_GAS_DB.keys())}")

    density_ratio = gas["density_kg_m3"] / AIR_DENSITY
    Q_gs = release_rate_kg_min * 1000.0 / 60.0  # kg/min → g/s

    features = []
    stats = []

    # Iterate in reversed order so the largest (least-severe) zone is
    # added to GeoJSON first — it renders underneath smaller zones.
    for threshold in reversed(gas["thresholds"]):
        level        = threshold["id"]
        label        = threshold["label"]
        color        = threshold["color"]
        threshold_ppm = threshold["ppm"]

        threshold_gm3 = ppm_to_gm3(threshold_ppm, gas["mw"])

        polygon_xy = _dpoly(
            threshold_gm3, Q_gs, wind_speed_ms, stability_class,
            release_height_m, density_ratio,
        )

        if polygon_xy:
            xs = [p[0] for p in polygon_xy]
            ys = [abs(p[1]) for p in polygon_xy]
            max_downwind_m = max(xs)
            max_width_m    = max(ys) * 2 if ys else 0.0

            latlon = plume_to_latlon(polygon_xy, lat, lon, wind_dir_from_deg)
            # GeoJSON coordinates: [lon, lat]
            coordinates = [[[pt[1], pt[0]] for pt in latlon]]
            has_contour = True
        else:
            max_downwind_m = 0.0
            max_width_m    = 0.0
            coordinates    = []
            has_contour    = False

        max_downwind_km = round(max_downwind_m / 1000.0, 3)
        max_width_km    = round(max_width_m    / 1000.0, 3)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coordinates,
            },
            "properties": {
                "type":             "dense_gas_contour",
                "level":            level,
                "label":            label,
                "color":            color,
                "threshold_ppm":    threshold_ppm,
                "max_downwind_km":  max_downwind_km,
                "max_width_km":     max_width_km,
            },
        }
        features.append(feature)

        stats.append({
            "level":           level,
            "label":           label,
            "color":           color,
            "threshold_ppm":   threshold_ppm,
            "max_downwind_km": max_downwind_km,
            "max_width_km":    max_width_km,
            "has_contour":     has_contour,
        })

    # Stats returned in original threshold order (most-severe first)
    stats.reverse()

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Gas metadata — exclude the thresholds list (returned separately in stats)
    gas_info = {k: v for k, v in gas.items() if k != "thresholds"}

    model_info = {
        "type":             "dense_gas_modified_pg",
        "density_ratio":    round(density_ratio, 4),
        "dense_factor":     round(math.sqrt(density_ratio), 4),
        "stability_class":  stability_class,
        "wind_speed_ms":    wind_speed_ms,
        "wind_dir_from_deg": wind_dir_from_deg,
        "Q_gs":             round(Q_gs, 4),
    }

    return {
        "geojson": geojson,
        "stats":   stats,
        "gas":     gas_info,
        "model":   model_info,
    }
