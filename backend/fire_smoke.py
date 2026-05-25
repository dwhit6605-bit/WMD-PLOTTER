"""
Fire / Smoke Plume Model — Heskestad (1984) flame height + Gaussian dispersion.

Physics:
  Combustion creates a buoyant smoke column whose effective source height is
  approximated by the Heskestad (1984) mean flame height formula:
    H_f = 0.235 · Q_kW^0.4   (simplified point-source form, metres)

  Smoke dispersion is then computed with standard Gaussian (P-G) using
  H_eff = h_stack + H_f as the fixed effective release height. This approach
  is consistent with CAMEO/ALOHA fire-smoke methodology and gives realistic
  ground-level concentrations for emergency planning purposes.

  Note: The Briggs (1975) buoyant-rise formula applies to concentrated
  industrial stack sources, and at fire-scale HRRs (8–500 MW) it predicts
  plume heights of 160–800+ m that never return to ground level within
  planning distances. Heskestad flame height gives operationally meaningful
  results for all fire types.

References:
  Heskestad, G. (1984). Engineering relations for fire plumes. Fire Safety J.
    7(1), 25-32. DOI: 10.1016/0379-7112(84)90005-6
  Turner, D.B. (1994). Workbook of Atmospheric Dispersion Estimates.
  EPA CAMEO/ALOHA Technical Documentation (2019).
"""

import math
from dispersion import (
    sigma_y,
    sigma_z,
    plume_to_latlon,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fire-type database
# pm25_ef and co_ef are emission factors in g/kg of fuel consumed.
# fuel_ef_kg_s is typical fuel consumption rate (kg/s) at full involvement.
# ─────────────────────────────────────────────────────────────────────────────

FIRE_TYPES = {
    "vehicle": {
        "name": "Vehicle / Car Fire",
        "hrr_mw": 8.0,
        "pm25_ef": 60.0,
        "co_ef": 150.0,
        "fuel_ef_kg_s": 0.3,
        "desc": "Single passenger vehicle fully involved.",
    },
    "structure_small": {
        "name": "Small Structure Fire",
        "hrr_mw": 30.0,
        "pm25_ef": 25.0,
        "co_ef": 100.0,
        "fuel_ef_kg_s": 1.0,
        "desc": "Single-story residential structure.",
    },
    "structure_large": {
        "name": "Large Structure Fire",
        "hrr_mw": 200.0,
        "pm25_ef": 40.0,
        "co_ef": 120.0,
        "fuel_ef_kg_s": 6.0,
        "desc": "Multi-story or commercial building, fully involved.",
    },
    "wildland_low": {
        "name": "Wildland Fire (Low Intensity)",
        "hrr_mw": 50.0,
        "pm25_ef": 12.0,
        "co_ef": 80.0,
        "fuel_ef_kg_s": 2.0,
        "desc": "Ground fire with moderate fuel loading.",
    },
    "wildland_high": {
        "name": "Wildland Fire (High Intensity)",
        "hrr_mw": 500.0,
        "pm25_ef": 15.0,
        "co_ef": 100.0,
        "fuel_ef_kg_s": 20.0,
        "desc": "Crown fire or extreme fuel conditions.",
    },
    "hazmat_fire": {
        "name": "Hazmat / Industrial Fire",
        "hrr_mw": 100.0,
        "pm25_ef": 80.0,
        "co_ef": 200.0,
        "fuel_ef_kg_s": 3.0,
        "desc": "Chemical storage or industrial fire; highly toxic smoke.",
    },
    "warehouse": {
        "name": "Warehouse / Storage Fire",
        "hrr_mw": 400.0,
        "pm25_ef": 50.0,
        "co_ef": 150.0,
        "fuel_ef_kg_s": 12.0,
        "desc": "Large warehouse or distribution centre, fully involved.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# PM2.5 and CO thresholds
# ─────────────────────────────────────────────────────────────────────────────

PM25_THRESHOLDS = [
    {"id": "hazardous",      "label": "Hazardous PM2.5 (>500 µg/m³)",                  "ugm3": 500.0, "color": "#7E0023"},
    {"id": "very_unhealthy", "label": "Very Unhealthy PM2.5 (250–500 µg/m³)",          "ugm3": 250.0, "color": "#8F3F97"},
    {"id": "unhealthy",      "label": "Unhealthy PM2.5 (150–250 µg/m³)",               "ugm3": 150.0, "color": "#FF0000"},
    {"id": "usg",            "label": "Unhealthy — Sensitive Groups (55–150 µg/m³)",   "ugm3": 55.0,  "color": "#FF7E00"},
    {"id": "moderate",       "label": "Moderate PM2.5 (35–55 µg/m³)",                  "ugm3": 35.0,  "color": "#FFFF00"},
]

CO_THRESHOLDS = [
    {"id": "co_idlh", "label": "CO — IDLH (1200 ppm)",            "ppm": 1200.0, "color": "#CC0000"},
    {"id": "co_high", "label": "CO — Dangerous Levels (200 ppm)", "ppm": 200.0,  "color": "#FF8800"},
    {"id": "co_osha", "label": "CO — OSHA TWA (50 ppm)",          "ppm": 50.0,   "color": "#FFCC00"},
]

_MW_CO         = 28.01    # g/mol, CO
_MOLAR_VOL_25C = 24.45    # L/mol at 25°C, 1 atm


# ─────────────────────────────────────────────────────────────────────────────
# Heskestad (1984) flame height
# ─────────────────────────────────────────────────────────────────────────────

def _heskestad_flame_height(hrr_mw: float) -> float:
    """
    Mean flame height (m) from Heskestad (1984) simplified point-source formula.
    H_f = 0.235 · Q_kW^0.4   (m), Q in kW.
    """
    return 0.235 * (hrr_mw * 1000.0) ** 0.4


def _effective_height(hrr_mw: float, h_stack: float) -> float:
    """Total effective source height (m): stack + flame."""
    return h_stack + _heskestad_flame_height(hrr_mw)


# ─────────────────────────────────────────────────────────────────────────────
# Gaussian helpers for elevated source
#
# dispersion.find_max_downwind checks concentration at x_start (near source).
# For elevated sources the concentration there is near zero (σz << H_eff), so
# it returns 0 immediately.  The true peak occurs at x where σz ≈ H/√2, which
# may be hundreds to thousands of metres downwind.  We must scan for the peak
# before binary-searching for the downwind extent.
# ─────────────────────────────────────────────────────────────────────────────

def _fc(x_m: float, Q_gs: float, u_ms: float, stability: str, H_eff: float) -> float:
    """Ground-level centreline concentration (g/m³) for a fixed-height source."""
    if x_m <= 0:
        return 0.0
    u  = max(u_ms, 0.5)
    sy = sigma_y(x_m, stability)
    sz = sigma_z(x_m, stability)
    if sy <= 0 or sz <= 0:
        return 0.0
    return (Q_gs / (math.pi * sy * sz * u)) * math.exp(-0.5 * (H_eff / sz) ** 2)


def _ff(threshold_gm3: float, Q_gs: float, u_ms: float, stability: str,
        H_eff: float, x_max_search: float = 100_000) -> float:
    """
    Maximum downwind extent (m) where centreline concentration >= threshold.

    Uses log-space scanning so the near-source region (where the elevated
    plume first touches the ground) is sampled with adequate density.
    The concentration peak for an elevated source occurs at x where
    σz ≈ H/√2 — which can be very close to the source and is easily
    missed by a linear scan with a large step size.

    Returns 0 if threshold is never met.
    """
    n_scan  = 300
    x_near  = max(H_eff * 0.1 + 1.0, 5.0)
    log_lo  = math.log10(x_near)
    log_hi  = math.log10(x_max_search)
    xs      = [10 ** (log_lo + (log_hi - log_lo) * i / (n_scan - 1)) for i in range(n_scan)]
    concs   = [_fc(x, Q_gs, u_ms, stability, H_eff) for x in xs]
    c_max   = max(concs)

    if c_max < threshold_gm3:
        return 0.0

    x_peak = xs[concs.index(c_max)]

    lo, hi = x_peak, x_max_search
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _fc(mid, Q_gs, u_ms, stability, H_eff) >= threshold_gm3:
            lo = mid
        else:
            hi = mid
    return hi


def _fhw(x_m: float, threshold_gm3: float, Q_gs: float, u_ms: float,
         stability: str, H_eff: float) -> float:
    """Half-width (m) at downwind distance x."""
    c = _fc(x_m, Q_gs, u_ms, stability, H_eff)
    if c <= threshold_gm3:
        return 0.0
    sy = sigma_y(x_m, stability)
    ratio = c / threshold_gm3
    return sy * math.sqrt(2.0 * math.log(ratio)) if ratio > 1 else 0.0


def _fpoly(threshold_gm3: float, Q_gs: float, u_ms: float, stability: str,
           H_eff: float, n_points: int = 120) -> list[tuple[float, float]]:
    """Plume boundary polygon in local (x, y) metres."""
    x_max = _ff(threshold_gm3, Q_gs, u_ms, stability, H_eff)
    if x_max <= 0:
        return []

    x_start = max(H_eff * 0.1 + 1.0, 5.0)
    xs      = [x_start + (x_max - x_start) * i / (n_points - 1) for i in range(n_points)]

    right_side: list[tuple[float, float]] = []
    left_side:  list[tuple[float, float]] = []

    for x in xs:
        hw = _fhw(x, threshold_gm3, Q_gs, u_ms, stability, H_eff)
        if hw > 0:
            right_side.append((x,  hw))
            left_side.append( (x, -hw))

    if not right_side:
        return []

    x_near = right_side[0][0]
    return [(x_near, 0.0)] + right_side + list(reversed(left_side)) + [(x_near, 0.0)]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def list_fire_types() -> list[dict]:
    """Return all fire type entries."""
    return [{"id": k, **v} for k, v in FIRE_TYPES.items()]


def compute_fire_smoke_zones(
    lat: float,
    lon: float,
    fire_type_id: str,
    wind_speed_ms: float,
    wind_dir_from_deg: float,
    stability_class: str,
    h_stack: float = 0.0,
) -> dict:
    """
    Compute fire/smoke hazard zones (PM2.5 and CO plumes).

    Uses Heskestad (1984) flame height as the effective release height and
    standard Pasquill-Gifford Gaussian dispersion.

    Args:
        lat, lon:           Source location (decimal degrees).
        fire_type_id:       Key into FIRE_TYPES.
        wind_speed_ms:      Mean wind speed (m/s).
        wind_dir_from_deg:  Meteorological wind direction (FROM which wind blows).
        stability_class:    Pasquill-Gifford class ('A'–'F').
        h_stack:            Additional stack / crane height (m) above ground.

    Returns:
        {"geojson": FeatureCollection, "stats": list, "fire": dict, "model": dict}
    """
    fire = FIRE_TYPES.get(fire_type_id)
    if fire is None:
        raise ValueError(f"Unknown fire_type_id: {fire_type_id!r}. "
                         f"Available: {list(FIRE_TYPES.keys())}")

    hrr_mw    = fire["hrr_mw"]
    H_flame   = _heskestad_flame_height(hrr_mw)
    H_eff     = h_stack + H_flame

    Q_pm25_gs = fire["fuel_ef_kg_s"] * fire["pm25_ef"]   # g/s PM2.5
    Q_co_gs   = fire["fuel_ef_kg_s"] * fire["co_ef"]     # g/s CO

    features:   list[dict] = []
    pm25_stats: list[dict] = []
    co_stats:   list[dict] = []

    # ── PM2.5 zones ───────────────────────────────────────────────────────────
    for threshold in reversed(PM25_THRESHOLDS):   # largest zone first in GeoJSON
        threshold_gm3 = threshold["ugm3"] * 1e-6  # µg/m³ → g/m³

        polygon_xy = _fpoly(threshold_gm3, Q_pm25_gs, wind_speed_ms, stability_class, H_eff)

        if polygon_xy:
            xs = [p[0] for p in polygon_xy]
            ys = [abs(p[1]) for p in polygon_xy]
            max_down_m  = max(xs)
            max_width_m = max(ys) * 2 if ys else 0.0
            latlon      = plume_to_latlon(polygon_xy, lat, lon, wind_dir_from_deg)
            coords      = [[[pt[1], pt[0]] for pt in latlon]]
            has_contour = True
        else:
            max_down_m = max_width_m = 0.0
            coords = []
            has_contour = False

        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "properties": {
                "type":            "smoke_pm25",
                "level":           threshold["id"],
                "label":           threshold["label"],
                "color":           threshold["color"],
                "threshold_ugm3":  threshold["ugm3"],
                "max_downwind_km": round(max_down_m  / 1000, 3),
                "max_width_km":    round(max_width_m / 1000, 3),
            },
        })
        pm25_stats.insert(0, {
            "pollutant":       "PM2.5",
            "level":           threshold["id"],
            "label":           threshold["label"],
            "color":           threshold["color"],
            "threshold_ugm3":  threshold["ugm3"],
            "max_downwind_km": round(max_down_m  / 1000, 3),
            "max_width_km":    round(max_width_m / 1000, 3),
            "has_contour":     has_contour,
        })

    # ── CO zones ─────────────────────────────────────────────────────────────
    for threshold in reversed(CO_THRESHOLDS):
        threshold_gm3 = threshold["ppm"] * _MW_CO / (_MOLAR_VOL_25C * 1000.0)

        polygon_xy = _fpoly(threshold_gm3, Q_co_gs, wind_speed_ms, stability_class, H_eff)

        if polygon_xy:
            xs = [p[0] for p in polygon_xy]
            ys = [abs(p[1]) for p in polygon_xy]
            max_down_m  = max(xs)
            max_width_m = max(ys) * 2 if ys else 0.0
            latlon      = plume_to_latlon(polygon_xy, lat, lon, wind_dir_from_deg)
            coords      = [[[pt[1], pt[0]] for pt in latlon]]
            has_contour = True
        else:
            max_down_m = max_width_m = 0.0
            coords = []
            has_contour = False

        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "properties": {
                "type":            "smoke_co",
                "level":           threshold["id"],
                "label":           threshold["label"],
                "color":           threshold["color"],
                "threshold_ppm":   threshold["ppm"],
                "max_downwind_km": round(max_down_m  / 1000, 3),
                "max_width_km":    round(max_width_m / 1000, 3),
            },
        })
        co_stats.insert(0, {
            "pollutant":       "CO",
            "level":           threshold["id"],
            "label":           threshold["label"],
            "color":           threshold["color"],
            "threshold_ppm":   threshold["ppm"],
            "max_downwind_km": round(max_down_m  / 1000, 3),
            "max_width_km":    round(max_width_m / 1000, 3),
            "has_contour":     has_contour,
        })

    fire_info = {"id": fire_type_id, **fire}

    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "stats":   pm25_stats + co_stats,
        "fire":    fire_info,
        "model": {
            "type":              "Heskestad (1984) flame ht + Gaussian (P-G)",
            "hrr_mw":            hrr_mw,
            "flame_height_m":    round(H_flame, 1),
            "h_stack_m":         h_stack,
            "H_eff_m":           round(H_eff, 1),
            "Q_pm25_gs":         round(Q_pm25_gs, 2),
            "Q_co_gs":           round(Q_co_gs,   2),
            "stability_class":   stability_class,
            "wind_speed_ms":     wind_speed_ms,
            "wind_dir_from_deg": wind_dir_from_deg,
        },
    }
