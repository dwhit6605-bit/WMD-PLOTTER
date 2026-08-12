/*
 * Dense Gas Dispersion — modified Pasquill-Gifford (reduced σz for heavy gas).
 * Faithful port of backend/dense_gas.py; cross-validated in test_model_port.py.
 * Depends on the dispersion module (sigma_y/sigma_z/ppm_to_gm3/plume_to_latlon).
 */
(function (root, factory) {
  let dispersion;
  if (typeof module === 'object' && module.exports) {
    dispersion = require('./dispersion.js');
    module.exports = factory(dispersion);
  } else {
    root.WMDModels = root.WMDModels || {};
    dispersion = root.WMDModels.dispersion;
    root.WMDModels.dense_gas = factory(dispersion);
  }
})(typeof self !== 'undefined' ? self : this, function (dispersion) {
  'use strict';

  const AIR_DENSITY = 1.29;

  const DENSE_GAS_DB = {
    cl2: { id: 'cl2', name: 'Chlorine', formula: 'Cl₂', un: '1017', mw: 70.9, density_kg_m3: 2.93, flammable: false,
      notes: 'Heavier-than-air; pools in low-lying areas and basements.',
      warning: 'Gas sinks into basements, trenches, and low areas — evacuate below-grade spaces first.',
      thresholds: [
        { id: 'erpg3', label: 'ERPG-3 / Life-Threatening',     ppm: 20.0, color: '#FF1100' },
        { id: 'idlh',  label: 'IDLH / Immediately Dangerous',  ppm: 10.0, color: '#FF5500' },
        { id: 'erpg2', label: 'ERPG-2 / Irreversible Effects', ppm: 3.0,  color: '#FF8C00' },
        { id: 'erpg1', label: 'ERPG-1 / Mild Effects',         ppm: 1.0,  color: '#FFD700' } ] },
    so2: { id: 'so2', name: 'Sulfur Dioxide', formula: 'SO₂', un: '1079', mw: 64.1, density_kg_m3: 2.62, flammable: false,
      notes: 'Heavier-than-air; sharp acidic odor. Industrial accident and volcanic hazard.',
      thresholds: [
        { id: 'erpg3', label: 'ERPG-3 / Life-Threatening',     ppm: 15.0,  color: '#FF1100' },
        { id: 'idlh',  label: 'IDLH / Immediately Dangerous',  ppm: 100.0, color: '#FF5500' },
        { id: 'erpg2', label: 'ERPG-2 / Irreversible Effects', ppm: 3.0,   color: '#FF8C00' },
        { id: 'erpg1', label: 'ERPG-1 / Mild Effects',         ppm: 0.3,   color: '#FFD700' } ] },
    h2s: { id: 'h2s', name: 'Hydrogen Sulfide', formula: 'H₂S', un: '1053', mw: 34.1, density_kg_m3: 1.42, flammable: true,
      notes: 'Slightly heavier than air; flammable. Common in oil & gas, sewage, and confined spaces.',
      warning: 'Olfactory fatigue — cannot rely on smell at high concentrations.',
      thresholds: [
        { id: 'erpg3', label: 'ERPG-3 / Life-Threatening',     ppm: 50.0, color: '#FF1100' },
        { id: 'idlh',  label: 'IDLH / Immediately Dangerous',  ppm: 50.0, color: '#FF5500' },
        { id: 'erpg2', label: 'ERPG-2 / Irreversible Effects', ppm: 50.0, color: '#FF8C00' },
        { id: 'erpg1', label: 'ERPG-1 / Mild Effects',         ppm: 0.1,  color: '#FFD700' } ] },
    cg: { id: 'cg', name: 'Phosgene (CG)', formula: 'COCl₂', un: '1076', mw: 98.9, density_kg_m3: 4.09, flammable: false,
      notes: 'Chemical warfare agent precursor and industrial chemical. Very heavy gas.',
      warning: 'CWA precursor — pulmonary edema onset delayed 4–24 hours after exposure.',
      thresholds: [
        { id: 'erpg3', label: 'ERPG-3 / Life-Threatening',     ppm: 1.5, color: '#FF1100' },
        { id: 'idlh',  label: 'IDLH / Immediately Dangerous',  ppm: 2.0, color: '#FF5500' },
        { id: 'erpg2', label: 'ERPG-2 / Irreversible Effects', ppm: 0.5, color: '#FF8C00' },
        { id: 'erpg1', label: 'ERPG-1 / Mild Effects',         ppm: 0.1, color: '#FFD700' } ] },
    no2: { id: 'no2', name: 'Nitrogen Dioxide', formula: 'NO₂', un: '1067', mw: 46.0, density_kg_m3: 1.88, flammable: false,
      notes: 'Heavier than air; reddish-brown. Produced by combustion and industrial processes.',
      thresholds: [
        { id: 'erpg3', label: 'ERPG-3 / Life-Threatening',     ppm: 25.0, color: '#FF1100' },
        { id: 'idlh',  label: 'IDLH / Immediately Dangerous',  ppm: 20.0, color: '#FF5500' },
        { id: 'erpg2', label: 'ERPG-2 / Irreversible Effects', ppm: 15.0, color: '#FF8C00' },
        { id: 'erpg1', label: 'ERPG-1 / Mild Effects',         ppm: 1.0,  color: '#FFD700' } ] },
    propane_v: { id: 'propane_v', name: 'Propane Vapor Cloud', formula: 'C₃H₈', un: '1978', mw: 44.1, density_kg_m3: 1.83, flammable: true,
      notes: 'Heavier than air; accumulates at grade. Explosion hazard — ignition source avoidance critical.',
      thresholds: [
        { id: 'lfl',      label: 'LFL — Explosion Hazard (>2.1% v/v)', ppm: 21000.0, color: '#FF4400' },
        { id: 'half_lfl', label: '½ LFL — Caution Zone',              ppm: 10500.0, color: '#FFAA00' } ] },
    butane_v: { id: 'butane_v', name: 'Butane Vapor Cloud', formula: 'C₄H₁₀', un: '1011', mw: 58.1, density_kg_m3: 2.42, flammable: true,
      notes: 'Heavier than air; settles in low areas. Explosion and asphyxiation hazard.',
      thresholds: [
        { id: 'lfl',      label: 'LFL — Explosion Hazard (>1.8% v/v)', ppm: 18000.0, color: '#FF4400' },
        { id: 'half_lfl', label: '½ LFL — Caution Zone',              ppm: 9000.0,  color: '#FFAA00' } ] },
  };

  const r3 = (x) => Math.round(x * 1000) / 1000;
  const r4 = (x) => Math.round(x * 10000) / 10000;

  function _dz(x_m, stability, density_ratio) {
    return dispersion.sigma_z(x_m, stability) / Math.sqrt(density_ratio);
  }
  function _dc(x_m, Q_gs, u_ms, stability, H_m, density_ratio) {
    if (x_m <= 0) return 0.0;
    const u = Math.max(u_ms, 0.5);
    const sy = dispersion.sigma_y(x_m, stability);
    const sz = _dz(x_m, stability, density_ratio);
    if (sy <= 0 || sz <= 0) return 0.0;
    const vert = Math.exp(-0.5 * Math.pow(H_m / sz, 2));
    return (Q_gs / (Math.PI * sy * sz * u)) * vert;
  }
  function _dfind(threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio, x_max) {
    x_max = x_max || 200000;
    const x_start = Math.max(H_m * 2 + 1.0, 10.0);
    if (_dc(x_start, Q_gs, u_ms, stability, H_m, density_ratio) < threshold_gm3) return 0.0;
    let lo = x_start, hi = x_max;
    for (let i = 0; i < 60; i++) {
      const mid = 0.5 * (lo + hi);
      if (_dc(mid, Q_gs, u_ms, stability, H_m, density_ratio) >= threshold_gm3) lo = mid; else hi = mid;
    }
    return hi;
  }
  function _dhw(x_m, threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio) {
    const c = _dc(x_m, Q_gs, u_ms, stability, H_m, density_ratio);
    if (c <= threshold_gm3) return 0.0;
    const sy = dispersion.sigma_y(x_m, stability);
    const ratio = c / threshold_gm3;
    if (ratio <= 1.0) return 0.0;
    return sy * Math.sqrt(2.0 * Math.log(ratio));
  }
  function _dpoly(threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio, n_points) {
    n_points = n_points || 120;
    const x_max = _dfind(threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio);
    if (x_max <= 0) return [];
    const x_start = Math.max(H_m * 2 + 1.0, 5.0);
    const right = [], left = [];
    for (let i = 0; i < n_points; i++) {
      const x = x_start + (x_max - x_start) * i / (n_points - 1);
      const hw = _dhw(x, threshold_gm3, Q_gs, u_ms, stability, H_m, density_ratio);
      if (hw > 0) { right.push([x, hw]); left.push([x, -hw]); }
    }
    if (!right.length) return [];
    return [[x_start, 0.0]].concat(right, left.slice().reverse(), [[x_start, 0.0]]);
  }

  function get_dense_gas(gas_id) { return DENSE_GAS_DB[gas_id] || null; }

  function compute_dense_gas_zones(lat, lon, gas_id, release_rate_kg_min, release_height_m,
                                   wind_speed_ms, wind_dir_from_deg, stability_class) {
    const gas = DENSE_GAS_DB[gas_id];
    if (!gas) throw new Error('Unknown gas_id: ' + gas_id);
    const density_ratio = gas.density_kg_m3 / AIR_DENSITY;
    const Q_gs = release_rate_kg_min * 1000.0 / 60.0;

    const features = [], stats = [];
    for (let i = gas.thresholds.length - 1; i >= 0; i--) {   // largest zone first
      const t = gas.thresholds[i];
      const threshold_gm3 = dispersion.ppm_to_gm3(t.ppm, gas.mw);
      const polygon_xy = _dpoly(threshold_gm3, Q_gs, wind_speed_ms, stability_class, release_height_m, density_ratio);
      let max_down = 0.0, max_width = 0.0, coordinates = [], has = false;
      if (polygon_xy.length) {
        const xs = polygon_xy.map((p) => p[0]);
        const ys = polygon_xy.map((p) => Math.abs(p[1]));
        max_down = Math.max.apply(null, xs);
        max_width = ys.length ? Math.max.apply(null, ys) * 2 : 0.0;
        const latlon = dispersion.plume_to_latlon(polygon_xy, lat, lon, wind_dir_from_deg);
        coordinates = [latlon.map((pt) => [pt[1], pt[0]])];
        has = true;
      }
      const max_down_km = r3(max_down / 1000.0), max_width_km = r3(max_width / 1000.0);
      features.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates },
        properties: { type: 'dense_gas_contour', level: t.id, label: t.label, color: t.color,
          threshold_ppm: t.ppm, max_downwind_km: max_down_km, max_width_km: max_width_km } });
      stats.push({ level: t.id, label: t.label, color: t.color, threshold_ppm: t.ppm,
        max_downwind_km: max_down_km, max_width_km: max_width_km, has_contour: has });
    }
    stats.reverse();

    const gas_info = {}; for (const k in gas) if (k !== 'thresholds') gas_info[k] = gas[k];
    return {
      geojson: { type: 'FeatureCollection', features }, stats, gas: gas_info,
      model: { type: 'dense_gas_modified_pg', density_ratio: r4(density_ratio),
        dense_factor: r4(Math.sqrt(density_ratio)), stability_class,
        wind_speed_ms, wind_dir_from_deg, Q_gs: r4(Q_gs) },
    };
  }

  return { AIR_DENSITY, DENSE_GAS_DB, get_dense_gas, compute_dense_gas_zones };
});
