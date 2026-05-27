"""
Gaussian Plume Dispersion Model — Pasquill-Gifford with Briggs (1973) sigma equations.

Reference: Turner, D.B. (1994). Workbook of Atmospheric Dispersion Estimates.
           Slade, D.H. (1968). Meteorology and Atomic Energy.
           Briggs, G.A. (1973). Diffusion Estimation for Small Emissions.

Coordinate system:
  - x: downwind distance (m), origin at source
  - y: crosswind distance (m), positive to right of downwind direction
  - z: vertical distance (m), positive upward

Gaussian ground-level equation (reflecting plume at ground, z=0):
  C(x,y) = Q / (π·σy·σz·u) · exp(-y²/2σy²) · exp(-H²/2σz²)

  where H = effective release height (m), Q = emission rate (g/s),
  u = mean wind speed (m/s) at release height.

Units: Q in g/s → C in g/m³ → converted to ppm by caller.
"""

import math
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Briggs (1973) open-country dispersion coefficients
# σy = ay·x·(1 + by·x)^cy
# σz = az·x·(1 + bz·x)^cz
# ─────────────────────────────────────────────────────────────────────────────

SIGMA_COEFFS = {
    #        ay,     by,     cy,    az,     bz,     cz
    "A": (0.22,  0.0001, -0.5,  0.20,   0,      1.0),
    "B": (0.16,  0.0001, -0.5,  0.12,   0,      1.0),
    "C": (0.11,  0.0001, -0.5,  0.08,   0.0002,-0.5),
    "D": (0.08,  0.0001, -0.5,  0.06,   0.0015,-0.5),
    "E": (0.06,  0.0001, -0.5,  0.03,   0.0003,-1.0),
    "F": (0.04,  0.0001, -0.5,  0.016,  0.0003,-1.0),
}

# Maximum σz cap (mixing height proxy) — above this, vertical mixing is complete
MIXING_HEIGHT = {
    "A": 1500,
    "B": 1200,
    "C": 900,
    "D": 700,
    "E": 500,
    "F": 300,
}

MOLAR_VOLUME_25C = 24.45  # L/mol at 25°C, 1 atm


def sigma_y(x_m: float, stability: str) -> float:
    """
    Horizontal (crosswind) Gaussian dispersion coefficient (m).
    Briggs (1973) open-country formula.
    x_m: downwind distance in metres (must be > 0).
    """
    ay, by, cy, *_ = SIGMA_COEFFS[stability]
    return ay * x_m * (1.0 + by * x_m) ** cy


def sigma_z(x_m: float, stability: str) -> float:
    """
    Vertical Gaussian dispersion coefficient (m), capped at mixing height.
    """
    _, _, _, az, bz, cz = SIGMA_COEFFS[stability]
    if bz == 0:
        sz = az * x_m
    else:
        sz = az * x_m * (1.0 + bz * x_m) ** cz
    return min(sz, MIXING_HEIGHT[stability])


def ground_concentration(
    x_m: float,
    y_m: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float = 0.0,
) -> float:
    """
    Ground-level (z=0) concentration using the Gaussian plume model.

    Args:
        x_m:       Downwind distance (m). Must be > 0.
        y_m:       Crosswind distance (m).
        Q_gs:      Emission rate (g/s).
        u_ms:      Wind speed (m/s) at release height. Minimum 0.5 m/s.
        stability: Pasquill-Gifford stability class ('A'–'F').
        H_m:       Effective release height (m).

    Returns:
        Concentration in g/m³.
    """
    if x_m <= 0:
        return 0.0
    u = max(u_ms, 0.5)  # avoid division by zero
    sy = sigma_y(x_m, stability)
    sz = sigma_z(x_m, stability)
    if sy <= 0 or sz <= 0:
        return 0.0
    cross = math.exp(-0.5 * (y_m / sy) ** 2)
    vert  = math.exp(-0.5 * (H_m / sz) ** 2)  # ground reflection assumed
    return (Q_gs / (math.pi * sy * sz * u)) * cross * vert


def centerline_concentration(
    x_m: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float = 0.0,
) -> float:
    """Maximum concentration at downwind distance x (at y=0, z=0)."""
    return ground_concentration(x_m, 0.0, Q_gs, u_ms, stability, H_m)


def gm3_to_ppm(conc_gm3: float, mw: float) -> float:
    """Convert g/m³ to ppm (v/v) at 25°C, 1 atm."""
    # ppm = (g/m³) / MW [g/mol] * molar_volume [L/mol] * 1000 [L→m³] / 1e6
    # simplifies to: ppm = conc_gm3 * 24.45 / MW * 1000
    return conc_gm3 * MOLAR_VOLUME_25C * 1000.0 / mw


def ppm_to_gm3(conc_ppm: float, mw: float) -> float:
    """Convert ppm to g/m³."""
    return conc_ppm * mw / (MOLAR_VOLUME_25C * 1000.0)


def find_max_downwind(
    threshold_gm3: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float = 0.0,
    x_max_search: float = 150_000,
) -> float:
    """
    Find the maximum downwind distance (m) where centerline concentration
    >= threshold_gm3. Returns 0 if threshold is never met.

    Uses binary search between x_min and x_max_search.
    """
    # First check: is threshold ever met? (at very small x)
    x_start = max(H_m * 2 + 1.0, 10.0)
    c_start = centerline_concentration(x_start, Q_gs, u_ms, stability, H_m)
    if c_start < threshold_gm3:
        return 0.0

    # Binary search for x where C drops below threshold
    lo, hi = x_start, x_max_search
    for _ in range(60):  # 60 iterations → sub-metre precision
        mid = 0.5 * (lo + hi)
        c_mid = centerline_concentration(mid, Q_gs, u_ms, stability, H_m)
        if c_mid >= threshold_gm3:
            lo = mid
        else:
            hi = mid
    return hi


def plume_half_width(
    x_m: float,
    threshold_gm3: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float = 0.0,
) -> float:
    """
    Half-width of plume at downwind distance x (m) where concentration >= threshold.
    Returns 0 if centerline concentration at x is below threshold.
    """
    c_center = centerline_concentration(x_m, Q_gs, u_ms, stability, H_m)
    if c_center <= threshold_gm3:
        return 0.0
    sy = sigma_y(x_m, stability)
    ratio = c_center / threshold_gm3
    if ratio <= 1.0:
        return 0.0
    return sy * math.sqrt(2.0 * math.log(ratio))


def compute_plume_polygon(
    threshold_gm3: float,
    Q_gs: float,
    u_ms: float,
    stability: str,
    H_m: float = 0.0,
    n_points: int = 120,
    x_max_clip: Optional[float] = None,
) -> list[tuple[float, float]]:
    """
    Compute plume boundary polygon in plume coordinates (x, y) in metres.

    Returns a list of (x, y) points forming a closed polygon.
    The polygon traces the right side (y > 0) from source outward, then the
    left side (y < 0) back to source.
    Returns empty list if release is below threshold.

    x_max_clip: if provided, clip polygon to this downwind distance (m).
                Used by the animation endpoint to show plume at a given time.
    """
    x_max = find_max_downwind(threshold_gm3, Q_gs, u_ms, stability, H_m)
    if x_max <= 0:
        return []
    if x_max_clip is not None and x_max_clip < x_max:
        x_max = max(x_max_clip, 5.0)

    # Find x_min (very close to source; plume width very narrow there)
    x_start = max(H_m * 2 + 1.0, 5.0)

    # Sample x from x_start to x_max
    xs = [x_start + (x_max - x_start) * i / (n_points - 1) for i in range(n_points)]

    right_side: list[tuple[float, float]] = []
    left_side:  list[tuple[float, float]] = []

    for x in xs:
        hw = plume_half_width(x, threshold_gm3, Q_gs, u_ms, stability, H_m)
        if hw > 0:
            right_side.append((x,  hw))
            left_side.append( (x, -hw))

    if not right_side:
        return []

    # Close the polygon: source → right side → tip → left side reversed → source
    polygon = [(x_start, 0.0)] + right_side + list(reversed(left_side)) + [(x_start, 0.0)]
    return polygon


def plume_to_latlon(
    polygon_xy: list[tuple[float, float]],
    source_lat: float,
    source_lon: float,
    wind_from_deg: float,
) -> list[tuple[float, float]]:
    """
    Convert plume polygon from local plume coordinates (x=downwind, y=crosswind)
    to geographic coordinates (lat, lon).

    wind_from_deg: meteorological wind direction (degrees FROM which wind blows).
                   0° = wind from North, 90° = wind from East, etc.
                   Plume travels 180° opposite (TO direction).

    Returns list of (lat, lon) tuples.
    """
    # Plume travels toward: wind_from + 180° (mod 360)
    plume_to_deg = (wind_from_deg + 180.0) % 360.0

    # Convert to math angle (CCW from East)
    # Geographic: 0°=N, 90°=E → Math: 0°=E, 90°=N
    # math_angle = 90 - plume_to_deg (geographic to math)
    plume_to_rad = math.radians(90.0 - plume_to_deg)

    lat0_rad = math.radians(source_lat)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(lat0_rad)

    result = []
    for (x, y) in polygon_xy:
        # x is along plume_to direction, y is 90° clockwise from plume_to
        # In math frame:
        #   downwind unit vector: (cos(plume_to_rad), sin(plume_to_rad))
        #   crosswind unit vector (right): (sin(plume_to_rad), -cos(plume_to_rad))
        dx_m = x * math.cos(plume_to_rad) + y * math.sin(plume_to_rad)
        dy_m = x * math.sin(plume_to_rad) - y * math.cos(plume_to_rad)

        lat = source_lat + dy_m / m_per_deg_lat
        lon = source_lon + dx_m / m_per_deg_lon
        result.append((lat, lon))

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stability class determination
# Based on Turner (1994) / Pasquill (1961) criteria
# ─────────────────────────────────────────────────────────────────────────────

def determine_stability_class(
    wind_speed_ms: float,
    is_daytime: bool,
    cloud_cover_fraction: float = 0.5,
    solar_elevation_deg: float = 45.0,
) -> str:
    """
    Determine Pasquill-Gifford stability class.

    Args:
        wind_speed_ms:         Surface wind speed (m/s).
        is_daytime:            True between civil dawn and civil dusk.
        cloud_cover_fraction:  0–1 (0 = clear, 1 = overcast).
        solar_elevation_deg:   Solar elevation angle (degrees above horizon).

    Returns:
        Stability class string ('A'–'F').

    Turner (1994) Table 3-1 lookup simplified to deterministic rules.
    """
    u = wind_speed_ms

    if is_daytime:
        # Insolation category from solar elevation and cloud cover
        # Strong: elevation > 60° and cloud < 0.5
        # Slight: elevation < 25° OR cloud > 0.75
        effective_sky = cloud_cover_fraction
        if solar_elevation_deg > 60 and effective_sky < 0.4:
            insolation = "strong"
        elif solar_elevation_deg > 35 and effective_sky < 0.7:
            insolation = "moderate"
        else:
            insolation = "slight"

        if insolation == "strong":
            if u < 2:   return "A"
            if u < 3:   return "A"   # A-B → A
            if u < 5:   return "B"
            if u < 6:   return "C"
            return "C"
        elif insolation == "moderate":
            if u < 2:   return "A"   # A-B → A
            if u < 3:   return "B"
            if u < 5:   return "B"   # B-C → B
            if u < 6:   return "C"   # C-D → C
            return "D"
        else:  # slight
            if u < 2:   return "B"
            if u < 3:   return "C"
            if u < 5:   return "C"
            if u < 6:   return "D"
            return "D"
    else:
        # Nighttime: stability depends on cloud cover and wind
        if cloud_cover_fraction >= 0.875:   # ≥7/8 cloud — essentially D
            return "D"
        if cloud_cover_fraction >= 0.5:     # 4-7/8 cloud
            if u < 3:   return "E"
            return "D"
        else:                               # <4/8 cloud — clear night
            if u < 3:   return "F"
            if u < 5:   return "E"
            return "D"


def compute_all_contours(
    Q_gs: float,
    u_ms: float,
    stability: str,
    mw: float,
    thresholds: dict,          # {"low": {"value": ppm, ...}, "medium": ..., "high": ...}
    source_lat: float,
    source_lon: float,
    wind_from_deg: float,
    H_m: float = 0.0,
    x_max_clip: Optional[float] = None,
) -> dict:
    """
    Compute plume contour polygons for all threshold levels.

    Returns dict:
    {
      "low":    {"latlon": [(lat,lon),...], "label": "AEGL-1", "color": "#FFFF00",
                 "max_downwind_m": float, "max_width_m": float},
      "medium": {...},
      "high":   {...},
      "centerline_distances": {"low": m, "medium": m, "high": m},
    }
    """
    result = {}
    for level, info in thresholds.items():
        ppm_val = info.get("value")
        if ppm_val is None or ppm_val <= 0:
            continue
        threshold_gm3 = ppm_to_gm3(ppm_val, mw)
        polygon_xy = compute_plume_polygon(threshold_gm3, Q_gs, u_ms, stability, H_m, x_max_clip=x_max_clip)
        if not polygon_xy:
            result[level] = {
                "latlon": [],
                "label": info["label"],
                "color": info["color"],
                "max_downwind_m": 0,
                "max_width_m": 0,
                "threshold_ppm": ppm_val,
            }
            continue

        # Stats
        xs = [p[0] for p in polygon_xy]
        ys = [abs(p[1]) for p in polygon_xy]
        max_x = max(xs)
        max_y = max(ys) if ys else 0

        latlon = plume_to_latlon(polygon_xy, source_lat, source_lon, wind_from_deg)
        result[level] = {
            "latlon": latlon,
            "label": info["label"],
            "color": info["color"],
            "max_downwind_m": max_x,
            "max_width_m": max_y * 2,
            "threshold_ppm": ppm_val,
        }

    return result
