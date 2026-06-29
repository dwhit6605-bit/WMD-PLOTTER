"""
Line Source Gaussian Plume — superposition of N point sources.
Models a moving/extended release (truck, train, pipeline) as N simultaneous
point sources each releasing Q/N g/s at equally spaced positions along a path.

The constant leak rate Q g/s is divided equally among N discrete sources,
which approximates a continuous line source in the limit N → ∞.

Reference: Pasquill & Smith (1983), Slade (1968).
"""
import math
import numpy as np
from dispersion import SIGMA_COEFFS, MIXING_HEIGHT, ppm_to_gm3, find_max_downwind


# ── Vectorized dispersion coefficients ───────────────────────────────────────

def _sig_y(x: np.ndarray, st: str) -> np.ndarray:
    a, b, c, *_ = SIGMA_COEFFS[st]
    return a * x * (1.0 + b * x) ** c


def _sig_z(x: np.ndarray, st: str) -> np.ndarray:
    _, _, _, a, b, c = SIGMA_COEFFS[st]
    s = a * x if b == 0.0 else a * x * (1.0 + b * x) ** c
    return np.minimum(s, float(MIXING_HEIGHT[st]))


# ── Path interpolation ────────────────────────────────────────────────────────

def interpolate_path(lat1: float, lon1: float,
                     lat2: float, lon2: float, n: int) -> list:
    """Return n equally-spaced (lat, lon) points between two endpoints."""
    return [
        (lat1 + i / (n - 1) * (lat2 - lat1),
         lon1 + i / (n - 1) * (lon2 - lon1))
        for i in range(n)
    ]


# ── Convex hull (Graham scan, pure Python) ────────────────────────────────────

def _convex_hull(pts: list) -> list:
    """
    Graham scan convex hull.  pts: list of (x, y).
    Returns a closed polygon (last point == first point).
    """
    # Deduplicate at 1-metre resolution
    pts = list({(round(x, 0), round(y, 0)) for x, y in pts})
    if len(pts) < 3:
        return pts + [pts[0]] if pts else []

    pivot = min(pts, key=lambda p: (p[1], p[0]))

    def _key(p):
        ang = math.atan2(p[1] - pivot[1], p[0] - pivot[0])
        d2  = (p[0] - pivot[0]) ** 2 + (p[1] - pivot[1]) ** 2
        return (ang, d2)

    hull = [pivot]
    for p in sorted(pts, key=_key):
        while len(hull) > 1:
            o, a, b = hull[-2], hull[-1], p
            cross = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append(p)

    hull.append(hull[0])
    return hull


# ── Main computation ──────────────────────────────────────────────────────────

def compute_line_source_contours(
    src_lats: list,
    src_lons: list,
    Q_gs: float,
    u_ms: float,
    stability: str,
    mw: float,
    thresholds: dict,
    wind_from_deg: float,
    H_m: float = 0.0,
    grid_n: int = 160,
) -> dict:
    """
    Compute line source hazard contours by superimposing N Gaussian plumes.

    Each of the N source points releases Q/N g/s simultaneously (constant
    total leak rate Q_gs regardless of path length or segment count).

    Args:
        src_lats / src_lons:  Equally-spaced source points along release path.
        Q_gs:                 Total constant leak rate (g/s).
        u_ms:                 Wind speed (m/s).
        stability:            Pasquill-Gifford class ('A'–'F').
        mw:                   Molecular weight (g/mol).
        thresholds:           Same dict as compute_all_contours() expects.
        wind_from_deg:        Meteorological wind direction (FROM, degrees).
        H_m:                  Release height (m); 0 for ground, > 0 for aerial.
        grid_n:               Concentration grid resolution (grid_n × grid_n).

    Returns:
        Dict matching the format of dispersion.compute_all_contours().
    """
    n = len(src_lats)
    if n < 1:
        return {}

    Q_each = Q_gs / n
    u = max(u_ms, 0.5)

    # Local Cartesian coordinate system (East / North, metres)
    ref_lat = sum(src_lats) / n
    ref_lon = sum(src_lons) / n
    m_lat = 111_320.0
    m_lon = 111_320.0 * math.cos(math.radians(ref_lat))

    src_xy = [
        ((lo - ref_lon) * m_lon, (la - ref_lat) * m_lat)
        for la, lo in zip(src_lats, src_lons)
    ]

    # Wind geometry
    plume_dir = math.radians(90.0 - (wind_from_deg + 180.0) % 360.0)
    wx, wy = math.cos(plume_dir), math.sin(plume_dir)   # downwind unit vector (E, N)
    cx, cy = wy, -wx                                      # crosswind (90° CW)

    # Use total Q to size the grid (conservative upper bound on plume reach)
    max_xd = 100.0
    for info in thresholds.values():
        v = info.get("value")
        if v and v > 0:
            xd = find_max_downwind(ppm_to_gm3(v, mw), Q_gs, u, stability, H_m)
            if xd > max_xd:
                max_xd = xd

    # Grid bounding box in local metres
    ex_vals = [p[0] for p in src_xy]
    ey_vals = [p[1] for p in src_xy]
    pad = max(max_xd * 0.25, 500.0)
    cw_pad = max_xd * 0.45

    gx_lo = min(ex_vals) - pad + min(0.0, max_xd * wx) - cw_pad * abs(cx)
    gx_hi = max(ex_vals) + pad + max(0.0, max_xd * wx) + cw_pad * abs(cx)
    gy_lo = min(ey_vals) - pad + min(0.0, max_xd * wy) - cw_pad * abs(cy)
    gy_hi = max(ey_vals) + pad + max(0.0, max_xd * wy) + cw_pad * abs(cy)

    GX, GY = np.meshgrid(
        np.linspace(gx_lo, gx_hi, grid_n),
        np.linspace(gy_lo, gy_hi, grid_n),
    )

    # Sum concentration contributions from all N source points
    total = np.zeros((grid_n, grid_n), dtype=np.float64)
    for src_x, src_y in src_xy:
        xd   = (GX - src_x) * wx + (GY - src_y) * wy    # downwind distance
        yc   = (GX - src_x) * cx + (GY - src_y) * cy    # crosswind distance
        ok   = xd > 0.1
        xd_s = np.where(ok, xd, 1.0)                      # safe denominator

        s_y  = _sig_y(xd_s, stability)
        s_z  = _sig_z(xd_s, stability)

        conc = np.where(
            ok,
            Q_each / (math.pi * s_y * s_z * u)
            * np.exp(-0.5 * (yc  / s_y) ** 2)
            * np.exp(-0.5 * (H_m / s_z) ** 2),
            0.0,
        )
        total += conc

    # Build per-threshold contours
    result = {}
    src_dmin = min(sx * wx + sy * wy for sx, sy in src_xy)

    for level, info in thresholds.items():
        ppm = info.get("value")
        if not ppm or ppm <= 0:
            continue
        thr = ppm_to_gm3(ppm, mw)
        mask = total >= thr

        if not mask.any():
            result[level] = {
                "latlon": [], "label": info["label"], "color": info["color"],
                "max_downwind_m": 0, "max_width_m": 0, "threshold_ppm": ppm,
            }
            continue

        rows, cols = np.where(mask)
        pts_m = [(float(GX[r, c]), float(GY[r, c])) for r, c in zip(rows, cols)]
        hull  = _convex_hull(pts_m)

        latlon = [
            (ref_lat + ey / m_lat, ref_lon + ex / m_lon)
            for ex, ey in hull
        ]

        # Stats: extent along downwind and crosswind axes
        dvals = [ex * wx + ey * wy for ex, ey in pts_m]
        cvals = [abs(ex * cx + ey * cy) for ex, ey in pts_m]

        result[level] = {
            "latlon":         latlon,
            "label":          info["label"],
            "color":          info["color"],
            "max_downwind_m": max(max(dvals) - src_dmin, 0) if dvals else 0,
            "max_width_m":    max(cvals, default=0) * 2,
            "threshold_ppm":  ppm,
        }

    return result
