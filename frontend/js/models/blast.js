/*
 * Blast Overpressure — Hopkinson-Cranz scaling with Brode (1955).
 * Faithful port of backend/blast.py; cross-validated in tests/test_model_port.py.
 * Loads in the browser (window.WMDModels.blast) and Node (module.exports).
 */
(function (root, factory) {
  const mod = factory();
  if (typeof module === 'object' && module.exports) module.exports = mod;
  else { root.WMDModels = root.WMDModels || {}; root.WMDModels.blast = mod; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const EXPLOSIVES = [
    { id: 'tnt',       name: 'TNT',                        factor: 1.00 },
    { id: 'c4',        name: 'C-4 / RDX',                  factor: 1.37 },
    { id: 'petn',      name: 'PETN',                       factor: 1.27 },
    { id: 'semtex',    name: 'Semtex-H',                   factor: 1.28 },
    { id: 'anfo',      name: 'ANFO',                       factor: 0.82 },
    { id: 'an',        name: 'Ammonium Nitrate (pure)',    factor: 0.42 },
    { id: 'tatp',      name: 'TATP',                       factor: 0.88 },
    { id: 'black_pwd', name: 'Black Powder',               factor: 0.55 },
    { id: 'gasoline',  name: 'Gasoline VCE (vapor cloud)', factor: 0.03 },
    { id: 'propane',   name: 'Propane VCE (vapor cloud)',  factor: 0.04 },
  ];

  const DAMAGE_ZONES = [
    { level: 'fireball', label: 'Fireball / Crater Zone',        psi: 20.0, kPa: 137.9,  color: '#6A0000', desc: 'Complete destruction · extreme casualties' },
    { level: 'severe',   label: 'Severe Structural Damage',      psi: 10.0, kPa: 68.95,  color: '#CC0000', desc: 'Reinforced concrete heavily damaged · severe casualties' },
    { level: 'moderate', label: 'Moderate Structural Damage',    psi: 5.0,  kPa: 34.47,  color: '#FF6600', desc: 'Most structures collapse · serious injuries' },
    { level: 'light',    label: 'Light Damage / Injuries',       psi: 1.0,  kPa: 6.895,  color: '#FFD700', desc: 'Doors/walls damaged · minor-to-moderate injuries' },
    { level: 'glass',    label: 'Window Breakage / Hazard Zone', psi: 0.5,  kPa: 3.447,  color: '#FFFACD', desc: 'Glass shatters · laceration risk' },
  ];

  const ATM_TO_KPA = 101.325;

  function overpressure_kPa(Z) {
    if (Z <= 0) return 1e9;
    let P_atm;
    if (Z < 0.5) P_atm = 6.7 / Math.pow(Z, 3) + 1.0;
    else P_atm = 0.975 / Z + 1.455 / Math.pow(Z, 2) + 5.85 / Math.pow(Z, 3) - 0.019;
    return Math.max(P_atm, 0.0) * ATM_TO_KPA;
  }

  function scaled_distance_for_pressure(target_kPa) {
    let z_lo = 0.01, z_hi = 2000.0;
    if (overpressure_kPa(z_lo) < target_kPa) return null;
    if (overpressure_kPa(z_hi) > target_kPa) return null;
    for (let i = 0; i < 80; i++) {
      const z_mid = (z_lo + z_hi) / 2;
      const p = overpressure_kPa(z_mid);
      if (Math.abs(p - target_kPa) / target_kPa < 1e-7) break;
      if (p > target_kPa) z_lo = z_mid; else z_hi = z_mid;
    }
    return (z_lo + z_hi) / 2;
  }

  function _circle_coords(lat, lon, radius_m, segments) {
    segments = segments || 72;
    const pts = [];
    for (let i = 0; i <= segments; i++) {
      const angle = 2 * Math.PI * i / segments;
      const dlat = (radius_m * Math.cos(angle)) / 111320;
      const dlon = (radius_m * Math.sin(angle)) / (111320 * Math.cos(Math.PI / 180 * lat));
      pts.push([lon + dlon, lat + dlat]);
    }
    return pts;
  }

  const r1 = (x) => Math.round(x * 10) / 10;
  const r3 = (x) => Math.round(x * 1000) / 1000;
  const r2 = (x) => Math.round(x * 100) / 100;

  function compute_blast_zones(lat, lon, weight_kg, explosive_id) {
    explosive_id = explosive_id || 'tnt';
    const e = EXPLOSIVES.find((x) => x.id === explosive_id);
    const factor = e ? e.factor : 1.0;
    const W_tnt = weight_kg * factor;
    const W_cbrt = Math.pow(W_tnt, 1.0 / 3.0);

    const features = [], stats = {};
    for (let i = DAMAGE_ZONES.length - 1; i >= 0; i--) {   // outermost first
      const zone = DAMAGE_ZONES[i];
      const Z = scaled_distance_for_pressure(zone.kPa);
      if (Z == null) continue;
      const radius_m = Z * W_cbrt;
      if (radius_m < 0.1) continue;
      const coords = _circle_coords(lat, lon, radius_m);
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [coords] },
        properties: {
          type: 'blast_zone', level: zone.level, label: zone.label, color: zone.color,
          psi: zone.psi, kPa: zone.kPa, desc: zone.desc,
          radius_m: r1(radius_m), radius_km: r3(radius_m / 1000),
        },
      });
      stats[zone.level] = {
        label: zone.level, full_label: zone.label, psi: zone.psi, kPa: zone.kPa,
        color: zone.color, desc: zone.desc, radius_m: r1(radius_m), radius_km: r3(radius_m / 1000),
      };
    }
    features.push({
      type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: { type: 'blast_source', weight_kg: weight_kg, W_tnt_kg: r2(W_tnt) },
    });
    return {
      geojson: { type: 'FeatureCollection', features },
      stats, W_tnt_kg: r2(W_tnt), explosive_id, weight_kg,
    };
  }

  return { EXPLOSIVES, DAMAGE_ZONES, ATM_TO_KPA,
           overpressure_kPa, scaled_distance_for_pressure, compute_blast_zones };
});
