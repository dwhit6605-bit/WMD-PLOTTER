/*
 * Line Source plume — superposition of N Gaussian point sources over a grid.
 * Faithful port of backend/line_source.py; cross-validated in test_model_port.py.
 *
 * The Python uses numpy for the concentration grid; this replaces it with plain
 * nested loops in the SAME accumulation order (source-by-source), so the summed
 * grid is bit-identical. The convex hull (Graham scan) is already pure Python
 * and ports directly; its 1-metre dedup uses Python round-half-to-even.
 *
 * Depends on the dispersion module (sigma_y/sigma_z/ppm_to_gm3/find_max_downwind).
 */
(function (root, factory) {
  let dispersion;
  if (typeof module === 'object' && module.exports) {
    dispersion = require('./dispersion.js');
    module.exports = factory(dispersion);
  } else {
    root.WMDModels = root.WMDModels || {};
    dispersion = root.WMDModels.dispersion;
    root.WMDModels.line_source = factory(dispersion);
  }
})(typeof self !== 'undefined' ? self : this, function (dispersion) {
  'use strict';

  // Python round(x, 0): round half to even. Ties are exact-.5 only (no epsilon).
  function pyround0(x) {
    const floor = Math.floor(x);
    const frac = x - floor;
    if (frac < 0.5) return floor;
    if (frac > 0.5) return floor + 1;
    return (floor % 2 === 0) ? floor : floor + 1;
  }

  function interpolate_path(lat1, lon1, lat2, lon2, n) {
    const out = [];
    for (let i = 0; i < n; i++) {
      out.push([lat1 + i / (n - 1) * (lat2 - lat1), lon1 + i / (n - 1) * (lon2 - lon1)]);
    }
    return out;
  }

  function _convex_hull(pts) {
    // Deduplicate at 1-metre resolution (round to even, like Python).
    const seen = new Map();
    for (const [x, y] of pts) {
      const rx = pyround0(x), ry = pyround0(y);
      seen.set(rx + ',' + ry, [rx, ry]);
    }
    let uniq = Array.from(seen.values());
    if (uniq.length < 3) return uniq.length ? uniq.concat([uniq[0]]) : [];

    // pivot: lowest y, then lowest x
    let pivot = uniq[0];
    for (const p of uniq) if (p[1] < pivot[1] || (p[1] === pivot[1] && p[0] < pivot[0])) pivot = p;

    const key = (p) => {
      const ang = Math.atan2(p[1] - pivot[1], p[0] - pivot[0]);
      const d2 = Math.pow(p[0] - pivot[0], 2) + Math.pow(p[1] - pivot[1], 2);
      return [ang, d2];
    };
    const sorted = uniq.slice().sort((A, B) => {
      const ka = key(A), kb = key(B);
      return ka[0] !== kb[0] ? ka[0] - kb[0] : ka[1] - kb[1];
    });

    const hull = [pivot];
    for (const p of sorted) {
      while (hull.length > 1) {
        const o = hull[hull.length - 2], a = hull[hull.length - 1], b = p;
        const cross = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
        if (cross <= 0) hull.pop(); else break;
      }
      hull.push(p);
    }
    hull.push(hull[0]);
    return hull;
  }

  function compute_line_source_contours(src_lats, src_lons, Q_gs, u_ms, stability, mw,
                                        thresholds, wind_from_deg, H_m, grid_n) {
    H_m = H_m || 0.0;
    grid_n = grid_n || 160;
    const n = src_lats.length;
    if (n < 1) return {};

    const Q_each = Q_gs / n;
    const u = Math.max(u_ms, 0.5);

    const ref_lat = src_lats.reduce((a, b) => a + b, 0) / n;
    const ref_lon = src_lons.reduce((a, b) => a + b, 0) / n;
    const m_lat = 111320.0;
    const m_lon = 111320.0 * Math.cos(Math.PI / 180 * ref_lat);

    const src_xy = [];
    for (let i = 0; i < n; i++) src_xy.push([(src_lons[i] - ref_lon) * m_lon, (src_lats[i] - ref_lat) * m_lat]);

    const plume_dir = Math.PI / 180 * (90.0 - (wind_from_deg + 180.0) % 360.0);
    const wx = Math.cos(plume_dir), wy = Math.sin(plume_dir);
    const cx = wy, cy = -wx;

    let max_xd = 100.0;
    for (const level in thresholds) {
      const v = thresholds[level].value;
      if (v && v > 0) {
        const xd = dispersion.find_max_downwind(dispersion.ppm_to_gm3(v, mw), Q_gs, u, stability, H_m);
        if (xd > max_xd) max_xd = xd;
      }
    }

    const ex = src_xy.map((p) => p[0]), ey = src_xy.map((p) => p[1]);
    const exmin = Math.min.apply(null, ex), exmax = Math.max.apply(null, ex);
    const eymin = Math.min.apply(null, ey), eymax = Math.max.apply(null, ey);
    const pad = Math.max(max_xd * 0.25, 500.0);
    const cw_pad = max_xd * 0.45;
    const gx_lo = exmin - pad + Math.min(0.0, max_xd * wx) - cw_pad * Math.abs(cx);
    const gx_hi = exmax + pad + Math.max(0.0, max_xd * wx) + cw_pad * Math.abs(cx);
    const gy_lo = eymin - pad + Math.min(0.0, max_xd * wy) - cw_pad * Math.abs(cy);
    const gy_hi = eymax + pad + Math.max(0.0, max_xd * wy) + cw_pad * Math.abs(cy);

    // linspace, matching np.linspace(a,b,grid_n)
    const xlin = new Array(grid_n), ylin = new Array(grid_n);
    for (let i = 0; i < grid_n; i++) {
      xlin[i] = gx_lo + (gx_hi - gx_lo) * i / (grid_n - 1);
      ylin[i] = gy_lo + (gy_hi - gy_lo) * i / (grid_n - 1);
    }

    // total[r][c] = Σ over sources; GX[r][c]=xlin[c], GY[r][c]=ylin[r] (indexing='xy')
    const total = [];
    for (let r = 0; r < grid_n; r++) total.push(new Float64Array(grid_n));

    const coeff = dispersion.SIGMA_COEFFS[stability];
    const mix = dispersion.MIXING_HEIGHT[stability];
    const ay = coeff[0], by = coeff[1], cy_ = coeff[2], az = coeff[3], bz = coeff[4], cz = coeff[5];
    const sigY = (x) => ay * x * Math.pow(1.0 + by * x, cy_);
    const sigZ = (x) => Math.min(bz === 0 ? az * x : az * x * Math.pow(1.0 + bz * x, cz), mix);

    for (const s of src_xy) {
      const sxx = s[0], syy = s[1];
      for (let r = 0; r < grid_n; r++) {
        const GY = ylin[r];
        const trow = total[r];
        for (let c = 0; c < grid_n; c++) {
          const GX = xlin[c];
          const xd = (GX - sxx) * wx + (GY - syy) * wy;
          const yc = (GX - sxx) * cx + (GY - syy) * cy;
          const ok = xd > 0.1;
          const xd_s = ok ? xd : 1.0;
          const s_y = sigY(xd_s), s_z = sigZ(xd_s);
          if (ok) {
            trow[c] += Q_each / (Math.PI * s_y * s_z * u)
              * Math.exp(-0.5 * Math.pow(yc / s_y, 2))
              * Math.exp(-0.5 * Math.pow(H_m / s_z, 2));
          }
        }
      }
    }

    const result = {};
    let src_dmin = Infinity;
    for (const s of src_xy) { const d = s[0] * wx + s[1] * wy; if (d < src_dmin) src_dmin = d; }

    for (const level in thresholds) {
      const info = thresholds[level];
      const ppm = info.value;
      if (!ppm || ppm <= 0) continue;
      const thr = dispersion.ppm_to_gm3(ppm, mw);

      const pts_m = [];
      for (let r = 0; r < grid_n; r++) {
        const trow = total[r];
        for (let c = 0; c < grid_n; c++) {
          if (trow[c] >= thr) pts_m.push([xlin[c], ylin[r]]);
        }
      }
      if (!pts_m.length) {
        result[level] = { latlon: [], label: info.label, color: info.color,
          max_downwind_m: 0, max_width_m: 0, threshold_ppm: ppm };
        continue;
      }
      const hull = _convex_hull(pts_m);
      const latlon = hull.map(([ex_, ey_]) => [ref_lat + ey_ / m_lat, ref_lon + ex_ / m_lon]);
      let dmax = -Infinity, cmax = 0;
      for (const [ex_, ey_] of pts_m) {
        const dv = ex_ * wx + ey_ * wy;
        const cv = Math.abs(ex_ * cx + ey_ * cy);
        if (dv > dmax) dmax = dv;
        if (cv > cmax) cmax = cv;
      }
      result[level] = { latlon, label: info.label, color: info.color,
        max_downwind_m: Math.max(dmax - src_dmin, 0), max_width_m: cmax * 2, threshold_ppm: ppm };
    }
    return result;
  }

  return { interpolate_path, _convex_hull, compute_line_source_contours };
});
