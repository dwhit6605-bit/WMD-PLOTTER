/*
 * Fire / Smoke — Heskestad (1984) flame height + Gaussian dispersion.
 * Faithful port of backend/fire_smoke.py; cross-validated in test_model_port.py.
 * Depends on the dispersion module (sigma_y/sigma_z/plume_to_latlon).
 */
(function (root, factory) {
  let dispersion;
  if (typeof module === 'object' && module.exports) {
    dispersion = require('./dispersion.js');
    module.exports = factory(dispersion);
  } else {
    root.WMDModels = root.WMDModels || {};
    dispersion = root.WMDModels.dispersion;
    root.WMDModels.fire_smoke = factory(dispersion);
  }
})(typeof self !== 'undefined' ? self : this, function (dispersion) {
  'use strict';

  const FIRE_TYPES = {
    vehicle:          { name: 'Vehicle / Car Fire',              hrr_mw: 8.0,   pm25_ef: 60.0, co_ef: 150.0, fuel_ef_kg_s: 0.3,  desc: 'Single passenger vehicle fully involved.' },
    structure_small:  { name: 'Small Structure Fire',           hrr_mw: 30.0,  pm25_ef: 25.0, co_ef: 100.0, fuel_ef_kg_s: 1.0,  desc: 'Single-story residential structure.' },
    structure_large:  { name: 'Large Structure Fire',           hrr_mw: 200.0, pm25_ef: 40.0, co_ef: 120.0, fuel_ef_kg_s: 6.0,  desc: 'Multi-story or commercial building, fully involved.' },
    wildland_low:     { name: 'Wildland Fire (Low Intensity)',  hrr_mw: 50.0,  pm25_ef: 12.0, co_ef: 80.0,  fuel_ef_kg_s: 2.0,  desc: 'Ground fire with moderate fuel loading.' },
    wildland_high:    { name: 'Wildland Fire (High Intensity)', hrr_mw: 500.0, pm25_ef: 15.0, co_ef: 100.0, fuel_ef_kg_s: 20.0, desc: 'Crown fire or extreme fuel conditions.' },
    hazmat_fire:      { name: 'Hazmat / Industrial Fire',       hrr_mw: 100.0, pm25_ef: 80.0, co_ef: 200.0, fuel_ef_kg_s: 3.0,  desc: 'Chemical storage or industrial fire; highly toxic smoke.' },
    warehouse:        { name: 'Warehouse / Storage Fire',       hrr_mw: 400.0, pm25_ef: 50.0, co_ef: 150.0, fuel_ef_kg_s: 12.0, desc: 'Large warehouse or distribution centre, fully involved.' },
  };

  const PM25_THRESHOLDS = [
    { id: 'hazardous',      label: 'Hazardous PM2.5 (>500 µg/m³)',                ugm3: 500.0, color: '#7E0023' },
    { id: 'very_unhealthy', label: 'Very Unhealthy PM2.5 (250–500 µg/m³)',        ugm3: 250.0, color: '#8F3F97' },
    { id: 'unhealthy',      label: 'Unhealthy PM2.5 (150–250 µg/m³)',             ugm3: 150.0, color: '#FF0000' },
    { id: 'usg',            label: 'Unhealthy — Sensitive Groups (55–150 µg/m³)', ugm3: 55.0,  color: '#FF7E00' },
    { id: 'moderate',       label: 'Moderate PM2.5 (35–55 µg/m³)',                ugm3: 35.0,  color: '#FFFF00' },
  ];
  const CO_THRESHOLDS = [
    { id: 'co_idlh', label: 'CO — IDLH (1200 ppm)',            ppm: 1200.0, color: '#CC0000' },
    { id: 'co_high', label: 'CO — Dangerous Levels (200 ppm)', ppm: 200.0,  color: '#FF8800' },
    { id: 'co_osha', label: 'CO — OSHA TWA (50 ppm)',          ppm: 50.0,   color: '#FFCC00' },
  ];
  const _MW_CO = 28.01, _MOLAR_VOL_25C = 24.45;

  const r1 = (x) => Math.round(x * 10) / 10;
  const r2 = (x) => Math.round(x * 100) / 100;
  const r3 = (x) => Math.round(x * 1000) / 1000;

  function _heskestad_flame_height(hrr_mw) { return 0.235 * Math.pow(hrr_mw * 1000.0, 0.4); }

  function _fc(x_m, Q_gs, u_ms, stability, H_eff) {
    if (x_m <= 0) return 0.0;
    const u = Math.max(u_ms, 0.5);
    const sy = dispersion.sigma_y(x_m, stability);
    const sz = dispersion.sigma_z(x_m, stability);
    if (sy <= 0 || sz <= 0) return 0.0;
    return (Q_gs / (Math.PI * sy * sz * u)) * Math.exp(-0.5 * Math.pow(H_eff / sz, 2));
  }

  function _ff(threshold_gm3, Q_gs, u_ms, stability, H_eff, x_max_search) {
    x_max_search = x_max_search || 100000;
    const n_scan = 300;
    const x_near = Math.max(H_eff * 0.1 + 1.0, 5.0);
    const log_lo = Math.log10(x_near), log_hi = Math.log10(x_max_search);
    const xs = [], concs = [];
    for (let i = 0; i < n_scan; i++) {
      const x = Math.pow(10, log_lo + (log_hi - log_lo) * i / (n_scan - 1));
      xs.push(x); concs.push(_fc(x, Q_gs, u_ms, stability, H_eff));
    }
    const c_max = Math.max.apply(null, concs);
    if (c_max < threshold_gm3) return 0.0;
    const x_peak = xs[concs.indexOf(c_max)];
    let lo = x_peak, hi = x_max_search;
    for (let i = 0; i < 60; i++) {
      const mid = 0.5 * (lo + hi);
      if (_fc(mid, Q_gs, u_ms, stability, H_eff) >= threshold_gm3) lo = mid; else hi = mid;
    }
    return hi;
  }

  function _fhw(x_m, threshold_gm3, Q_gs, u_ms, stability, H_eff) {
    const c = _fc(x_m, Q_gs, u_ms, stability, H_eff);
    if (c <= threshold_gm3) return 0.0;
    const sy = dispersion.sigma_y(x_m, stability);
    const ratio = c / threshold_gm3;
    return ratio > 1 ? sy * Math.sqrt(2.0 * Math.log(ratio)) : 0.0;
  }

  function _fpoly(threshold_gm3, Q_gs, u_ms, stability, H_eff, n_points) {
    n_points = n_points || 120;
    const x_max = _ff(threshold_gm3, Q_gs, u_ms, stability, H_eff);
    if (x_max <= 0) return [];
    const x_start = Math.max(H_eff * 0.1 + 1.0, 5.0);
    const right = [], left = [];
    for (let i = 0; i < n_points; i++) {
      const x = x_start + (x_max - x_start) * i / (n_points - 1);
      const hw = _fhw(x, threshold_gm3, Q_gs, u_ms, stability, H_eff);
      if (hw > 0) { right.push([x, hw]); left.push([x, -hw]); }
    }
    if (!right.length) return [];
    const x_near = right[0][0];
    return [[x_near, 0.0]].concat(right, left.slice().reverse(), [[x_near, 0.0]]);
  }

  function _polyStats(polygon_xy, lat, lon, wind_dir_from_deg) {
    if (!polygon_xy.length) return { max_down: 0.0, max_width: 0.0, coords: [], has: false };
    const xs = polygon_xy.map((p) => p[0]);
    const ys = polygon_xy.map((p) => Math.abs(p[1]));
    const latlon = dispersion.plume_to_latlon(polygon_xy, lat, lon, wind_dir_from_deg);
    return {
      max_down: Math.max.apply(null, xs),
      max_width: ys.length ? Math.max.apply(null, ys) * 2 : 0.0,
      coords: [latlon.map((pt) => [pt[1], pt[0]])], has: true,
    };
  }

  function compute_fire_smoke_zones(lat, lon, fire_type_id, wind_speed_ms, wind_dir_from_deg, stability_class, h_stack) {
    h_stack = h_stack || 0.0;
    const fire = FIRE_TYPES[fire_type_id];
    if (!fire) throw new Error('Unknown fire_type_id: ' + fire_type_id);
    const hrr_mw = fire.hrr_mw;
    const H_flame = _heskestad_flame_height(hrr_mw);
    const H_eff = h_stack + H_flame;
    const Q_pm25_gs = fire.fuel_ef_kg_s * fire.pm25_ef;
    const Q_co_gs = fire.fuel_ef_kg_s * fire.co_ef;

    const features = [], pm25_stats = [], co_stats = [];

    for (let i = PM25_THRESHOLDS.length - 1; i >= 0; i--) {
      const t = PM25_THRESHOLDS[i];
      const s = _polyStats(_fpoly(t.ugm3 * 1e-6, Q_pm25_gs, wind_speed_ms, stability_class, H_eff), lat, lon, wind_dir_from_deg);
      features.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: s.coords },
        properties: { type: 'smoke_pm25', level: t.id, label: t.label, color: t.color,
          threshold_ugm3: t.ugm3, max_downwind_km: r3(s.max_down / 1000), max_width_km: r3(s.max_width / 1000) } });
      pm25_stats.unshift({ pollutant: 'PM2.5', level: t.id, label: t.label, color: t.color,
        threshold_ugm3: t.ugm3, max_downwind_km: r3(s.max_down / 1000), max_width_km: r3(s.max_width / 1000), has_contour: s.has });
    }
    for (let i = CO_THRESHOLDS.length - 1; i >= 0; i--) {
      const t = CO_THRESHOLDS[i];
      const gm3 = t.ppm * _MW_CO / (_MOLAR_VOL_25C * 1000.0);
      const s = _polyStats(_fpoly(gm3, Q_co_gs, wind_speed_ms, stability_class, H_eff), lat, lon, wind_dir_from_deg);
      features.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: s.coords },
        properties: { type: 'smoke_co', level: t.id, label: t.label, color: t.color,
          threshold_ppm: t.ppm, max_downwind_km: r3(s.max_down / 1000), max_width_km: r3(s.max_width / 1000) } });
      co_stats.unshift({ pollutant: 'CO', level: t.id, label: t.label, color: t.color,
        threshold_ppm: t.ppm, max_downwind_km: r3(s.max_down / 1000), max_width_km: r3(s.max_width / 1000), has_contour: s.has });
    }

    const fire_info = { id: fire_type_id }; for (const k in fire) fire_info[k] = fire[k];
    return {
      geojson: { type: 'FeatureCollection', features },
      stats: pm25_stats.concat(co_stats), fire: fire_info,
      model: { type: 'Heskestad (1984) flame ht + Gaussian (P-G)', hrr_mw,
        flame_height_m: r1(H_flame), h_stack_m: h_stack, H_eff_m: r1(H_eff),
        Q_pm25_gs: r2(Q_pm25_gs), Q_co_gs: r2(Q_co_gs), stability_class,
        wind_speed_ms, wind_dir_from_deg },
    };
  }

  return { FIRE_TYPES, PM25_THRESHOLDS, CO_THRESHOLDS, compute_fire_smoke_zones };
});
