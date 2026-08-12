/*
 * Radiological Dispersal — Gaussian plume + EPA FGR-12 cloudshine DCF.
 * Faithful port of backend/radiation.py; cross-validated in tests/test_model_port.py.
 *
 * Depends on the dispersion module (same Gaussian math, Ci instead of g). Pulls
 * it from window.WMDModels.dispersion in the browser and require() in Node.
 */
(function (root, factory) {
  let dispersion;
  if (typeof module === 'object' && module.exports) {
    dispersion = require('./dispersion.js');
    module.exports = factory(dispersion);
  } else {
    root.WMDModels = root.WMDModels || {};
    dispersion = root.WMDModels.dispersion;   // must be loaded first
    root.WMDModels.radiation = factory(dispersion);
  }
})(typeof self !== 'undefined' ? self : this, function (dispersion) {
  'use strict';

  const RADIONUCLIDES = [
    { id: 'cs137', name: 'Cesium-137',      symbol: 'Cs-137', dcf_cloud: 2940,  half_life: '30.2 yr',  type: 'gamma',         notes: 'Most common RDD isotope · 662 keV gamma' },
    { id: 'co60',  name: 'Cobalt-60',       symbol: 'Co-60',  dcf_cloud: 14400, half_life: '5.27 yr',  type: 'gamma',         notes: 'High-energy gamma (1.17 + 1.33 MeV) · industrial sterilization' },
    { id: 'ir192', name: 'Iridium-192',     symbol: 'Ir-192', dcf_cloud: 5180,  half_life: '73.8 d',   type: 'gamma',         notes: 'Industrial radiography source · 0.37 MeV avg' },
    { id: 'i131',  name: 'Iodine-131',      symbol: 'I-131',  dcf_cloud: 1120,  half_life: '8.02 d',   type: 'gamma',         notes: 'Thyroid uptake concern · 364 keV gamma · nuclear fallout' },
    { id: 'am241', name: 'Americium-241',   symbol: 'Am-241', dcf_cloud: 140,   half_life: '432 yr',   type: 'alpha/gamma',   notes: 'Smoke detector source · 60 keV gamma · primarily alpha emitter' },
    { id: 'sr90',  name: 'Strontium-90',    symbol: 'Sr-90',  dcf_cloud: 13,    half_life: '28.8 yr',  type: 'beta',          notes: 'Pure beta emitter · very low cloudshine · bone seeker' },
    { id: 'ra226', name: 'Radium-226',      symbol: 'Ra-226', dcf_cloud: 2770,  half_life: '1600 yr',  type: 'gamma',         notes: 'Legacy medical/industrial · 186 keV gamma + daughters' },
    { id: 'pu239', name: 'Plutonium-239',   symbol: 'Pu-239', dcf_cloud: 7,     half_life: '24100 yr', type: 'alpha',         notes: 'Weapons material · alpha emitter · very low cloudshine' },
    { id: 'u235',  name: 'Uranium-235',     symbol: 'U-235',  dcf_cloud: 613,   half_life: '703 My',   type: 'gamma',         notes: 'Weapons-grade uranium · 185 keV gamma' },
    { id: 'cf252', name: 'Californium-252', symbol: 'Cf-252', dcf_cloud: 799,   half_life: '2.65 yr',  type: 'neutron/gamma', notes: 'Neutron emitter · well-logging / startup sources' },
  ];

  const DOSE_ZONES = [
    { level: 'pag',     label: 'PAG Evacuation Zone',    dose_msvhr: 0.1,   color: '#FFD700', desc: '0.1 mSv/hr — EPA Protective Action Guide: general population evacuation' },
    { level: 'worker',  label: 'Emergency Worker Limit', dose_msvhr: 1.0,   color: '#FF8C00', desc: '1 mSv/hr — Controlled access · emergency responder threshold' },
    { level: 'high',    label: 'High Radiation Zone',    dose_msvhr: 10.0,  color: '#FF4500', desc: '10 mSv/hr — NRC high radiation area · immediate evacuation' },
    { level: 'extreme', label: 'Extreme Hazard Zone',    dose_msvhr: 100.0, color: '#9B2DC8', desc: '100 mSv/hr — Very high radiation · lethal over hours' },
  ];

  function get_radionuclide(rad_id) {
    return RADIONUCLIDES.find((r) => r.id === rad_id) || null;
  }

  function compute_radiation_contours(Q_ci_s, u_ms, stability, dcf_cloud, source_lat, source_lon, wind_from_deg, H_m) {
    H_m = H_m || 0.0;
    const result = {};
    for (const zone of DOSE_ZONES) {
      const threshold_ci_m3 = zone.dose_msvhr / dcf_cloud;
      const polygon_xy = dispersion.compute_plume_polygon(threshold_ci_m3, Q_ci_s, u_ms, stability, H_m);
      if (!polygon_xy.length) {
        result[zone.level] = { latlon: [], label: zone.label, color: zone.color,
                               dose_msvhr: zone.dose_msvhr, desc: zone.desc,
                               max_downwind_m: 0, max_width_m: 0 };
        continue;
      }
      const xs = polygon_xy.map((p) => p[0]);
      const ys = polygon_xy.map((p) => Math.abs(p[1]));
      const max_x = Math.max.apply(null, xs);
      const max_y = ys.length ? Math.max.apply(null, ys) : 0;
      result[zone.level] = {
        latlon: dispersion.plume_to_latlon(polygon_xy, source_lat, source_lon, wind_from_deg),
        label: zone.label, color: zone.color, dose_msvhr: zone.dose_msvhr, desc: zone.desc,
        max_downwind_m: max_x, max_width_m: max_y * 2,
      };
    }
    return result;
  }

  return { RADIONUCLIDES, DOSE_ZONES, get_radionuclide, compute_radiation_contours };
});
