/*
 * Gaussian Plume Dispersion — Pasquill-Gifford with Briggs (1973) sigmas.
 *
 * A faithful JavaScript port of backend/dispersion.py, for on-device model
 * creation when the app is offline. It must produce the same numbers as the
 * Python; tests/test_model_port.py cross-validates the two against each other.
 * Any change here has to be mirrored there (and re-validated), not diverged.
 *
 * Works in both the browser (attaches to window.WMDModels.dispersion) and Node
 * (module.exports), so the same file serves the app and the test harness.
 */
(function (root, factory) {
  const mod = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = mod;                       // Node (test harness)
  } else {
    root.WMDModels = root.WMDModels || {};
    root.WMDModels.dispersion = mod;            // browser (offline app)
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Briggs (1973) open-country dispersion coefficients: [ay, by, cy, az, bz, cz]
  const SIGMA_COEFFS = {
    A: [0.22, 0.0001, -0.5, 0.20, 0,      1.0],
    B: [0.16, 0.0001, -0.5, 0.12, 0,      1.0],
    C: [0.11, 0.0001, -0.5, 0.08, 0.0002, -0.5],
    D: [0.08, 0.0001, -0.5, 0.06, 0.0015, -0.5],
    E: [0.06, 0.0001, -0.5, 0.03, 0.0003, -1.0],
    F: [0.04, 0.0001, -0.5, 0.016, 0.0003, -1.0],
  };

  // Mixing-height proxy: σz is capped here (complete vertical mixing above it).
  const MIXING_HEIGHT = { A: 1500, B: 1200, C: 900, D: 700, E: 500, F: 300 };

  const MOLAR_VOLUME_25C = 24.45;   // L/mol at 25°C, 1 atm

  function sigma_y(x_m, stability) {
    const [ay, by, cy] = SIGMA_COEFFS[stability];
    return ay * x_m * Math.pow(1.0 + by * x_m, cy);
  }

  function sigma_z(x_m, stability) {
    const c = SIGMA_COEFFS[stability];
    const az = c[3], bz = c[4], cz = c[5];
    const sz = bz === 0 ? az * x_m : az * x_m * Math.pow(1.0 + bz * x_m, cz);
    return Math.min(sz, MIXING_HEIGHT[stability]);
  }

  function ground_concentration(x_m, y_m, Q_gs, u_ms, stability, H_m) {
    H_m = H_m || 0.0;
    if (x_m <= 0) return 0.0;
    const u = Math.max(u_ms, 0.5);
    const sy = sigma_y(x_m, stability);
    const sz = sigma_z(x_m, stability);
    if (sy <= 0 || sz <= 0) return 0.0;
    const cross = Math.exp(-0.5 * Math.pow(y_m / sy, 2));
    const vert = Math.exp(-0.5 * Math.pow(H_m / sz, 2));   // ground reflection
    return (Q_gs / (Math.PI * sy * sz * u)) * cross * vert;
  }

  function centerline_concentration(x_m, Q_gs, u_ms, stability, H_m) {
    return ground_concentration(x_m, 0.0, Q_gs, u_ms, stability, H_m || 0.0);
  }

  function gm3_to_ppm(conc_gm3, mw) {
    return conc_gm3 * MOLAR_VOLUME_25C * 1000.0 / mw;
  }

  function ppm_to_gm3(conc_ppm, mw) {
    return conc_ppm * mw / (MOLAR_VOLUME_25C * 1000.0);
  }

  function find_max_downwind(threshold_gm3, Q_gs, u_ms, stability, H_m, x_max_search) {
    H_m = H_m || 0.0;
    x_max_search = x_max_search || 150000;
    const x_start = Math.max(H_m * 2 + 1.0, 10.0);
    const c_start = centerline_concentration(x_start, Q_gs, u_ms, stability, H_m);
    if (c_start < threshold_gm3) return 0.0;

    let lo = x_start, hi = x_max_search;
    for (let i = 0; i < 60; i++) {              // 60 iterations → sub-metre
      const mid = 0.5 * (lo + hi);
      const c_mid = centerline_concentration(mid, Q_gs, u_ms, stability, H_m);
      if (c_mid >= threshold_gm3) lo = mid; else hi = mid;
    }
    return hi;
  }

  function plume_half_width(x_m, threshold_gm3, Q_gs, u_ms, stability, H_m) {
    H_m = H_m || 0.0;
    const c_center = centerline_concentration(x_m, Q_gs, u_ms, stability, H_m);
    if (c_center <= threshold_gm3) return 0.0;
    const sy = sigma_y(x_m, stability);
    const ratio = c_center / threshold_gm3;
    if (ratio <= 1.0) return 0.0;
    return sy * Math.sqrt(2.0 * Math.log(ratio));
  }

  function compute_plume_polygon(threshold_gm3, Q_gs, u_ms, stability, H_m, n_points, x_max_clip) {
    H_m = H_m || 0.0;
    n_points = n_points || 120;
    let x_max = find_max_downwind(threshold_gm3, Q_gs, u_ms, stability, H_m);
    if (x_max <= 0) return [];
    if (x_max_clip != null && x_max_clip < x_max) x_max = Math.max(x_max_clip, 5.0);

    const x_start = Math.max(H_m * 2 + 1.0, 5.0);
    const xs = [];
    for (let i = 0; i < n_points; i++) {
      xs.push(x_start + (x_max - x_start) * i / (n_points - 1));
    }

    const right = [], left = [];
    for (const x of xs) {
      const hw = plume_half_width(x, threshold_gm3, Q_gs, u_ms, stability, H_m);
      if (hw > 0) { right.push([x, hw]); left.push([x, -hw]); }
    }
    if (right.length === 0) return [];

    return [[x_start, 0.0]].concat(right, left.slice().reverse(), [[x_start, 0.0]]);
  }

  function plume_to_latlon(polygon_xy, source_lat, source_lon, wind_from_deg) {
    const plume_to_deg = (wind_from_deg + 180.0) % 360.0;
    const plume_to_rad = (Math.PI / 180.0) * (90.0 - plume_to_deg);

    const lat0_rad = (Math.PI / 180.0) * source_lat;
    const m_per_deg_lat = 111320.0;
    const m_per_deg_lon = 111320.0 * Math.cos(lat0_rad);

    const out = [];
    for (const p of polygon_xy) {
      const x = p[0], y = p[1];
      const dx_m = x * Math.cos(plume_to_rad) + y * Math.sin(plume_to_rad);
      const dy_m = x * Math.sin(plume_to_rad) - y * Math.cos(plume_to_rad);
      out.push([source_lat + dy_m / m_per_deg_lat, source_lon + dx_m / m_per_deg_lon]);
    }
    return out;
  }

  function determine_stability_class(wind_speed_ms, is_daytime, cloud_cover_fraction, solar_elevation_deg) {
    cloud_cover_fraction = cloud_cover_fraction == null ? 0.5 : cloud_cover_fraction;
    solar_elevation_deg = solar_elevation_deg == null ? 45.0 : solar_elevation_deg;
    const u = wind_speed_ms;

    if (is_daytime) {
      let insolation;
      const sky = cloud_cover_fraction;
      if (solar_elevation_deg > 60 && sky < 0.4) insolation = 'strong';
      else if (solar_elevation_deg > 35 && sky < 0.7) insolation = 'moderate';
      else insolation = 'slight';

      if (insolation === 'strong') {
        if (u < 2) return 'A';
        if (u < 3) return 'A';
        if (u < 5) return 'B';
        if (u < 6) return 'C';
        return 'C';
      } else if (insolation === 'moderate') {
        if (u < 2) return 'A';
        if (u < 3) return 'B';
        if (u < 5) return 'B';
        if (u < 6) return 'C';
        return 'D';
      } else {
        if (u < 2) return 'B';
        if (u < 3) return 'C';
        if (u < 5) return 'C';
        if (u < 6) return 'D';
        return 'D';
      }
    } else {
      if (cloud_cover_fraction >= 0.875) return 'D';
      if (cloud_cover_fraction >= 0.5) {
        if (u < 3) return 'E';
        return 'D';
      }
      if (u < 3) return 'F';
      if (u < 5) return 'E';
      return 'D';
    }
  }

  function compute_all_contours(Q_gs, u_ms, stability, mw, thresholds, source_lat, source_lon, wind_from_deg, H_m, x_max_clip) {
    H_m = H_m || 0.0;
    const result = {};
    for (const level of Object.keys(thresholds)) {
      const info = thresholds[level];
      const ppm_val = info.value;
      if (ppm_val == null || ppm_val <= 0) continue;
      const threshold_gm3 = ppm_to_gm3(ppm_val, mw);
      const polygon_xy = compute_plume_polygon(threshold_gm3, Q_gs, u_ms, stability, H_m, 120, x_max_clip);
      if (!polygon_xy.length) {
        result[level] = { latlon: [], label: info.label, color: info.color,
                          max_downwind_m: 0, max_width_m: 0, threshold_ppm: ppm_val };
        continue;
      }
      const xs = polygon_xy.map(p => p[0]);
      const ys = polygon_xy.map(p => Math.abs(p[1]));
      const max_x = Math.max.apply(null, xs);
      const max_y = ys.length ? Math.max.apply(null, ys) : 0;
      result[level] = {
        latlon: plume_to_latlon(polygon_xy, source_lat, source_lon, wind_from_deg),
        label: info.label, color: info.color,
        max_downwind_m: max_x, max_width_m: max_y * 2, threshold_ppm: ppm_val,
      };
    }
    return result;
  }

  return {
    SIGMA_COEFFS, MIXING_HEIGHT, MOLAR_VOLUME_25C,
    sigma_y, sigma_z, ground_concentration, centerline_concentration,
    gm3_to_ppm, ppm_to_gm3, find_max_downwind, plume_half_width,
    compute_plume_polygon, plume_to_latlon, determine_stability_class,
    compute_all_contours,
  };
});
