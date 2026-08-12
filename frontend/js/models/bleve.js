/*
 * BLEVE fireball thermal model — Roberts (1982).
 * Faithful port of backend/bleve.py; cross-validated in tests/test_model_port.py.
 * Loads in the browser (window.WMDModels.bleve) and Node (module.exports).
 */
(function (root, factory) {
  const mod = factory();
  if (typeof module === 'object' && module.exports) module.exports = mod;
  else { root.WMDModels = root.WMDModels || {}; root.WMDModels.bleve = mod; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const FUELS = [
    { id: 'propane',   name: 'Propane (LPG)',            sep: 200, notes: 'Most common BLEVE fuel · pressurized tank' },
    { id: 'lpg',       name: 'LPG (butane/propane mix)', sep: 185, notes: 'Mixed liquefied petroleum gas' },
    { id: 'lng',       name: 'LNG (Liquefied Nat. Gas)', sep: 220, notes: 'Methane — very high SEP' },
    { id: 'gasoline',  name: 'Gasoline',                 sep: 130, notes: 'Automotive fuel tank / tanker' },
    { id: 'ethylene',  name: 'Ethylene',                 sep: 170, notes: 'Industrial petrochemical' },
    { id: 'hydrogen',  name: 'Hydrogen',                 sep: 110, notes: 'Fuel cell / cryogenic storage' },
    { id: 'ammonia',   name: 'Ammonia',                  sep: 90,  notes: 'Refrigerant / agricultural · toxic' },
    { id: 'methanol',  name: 'Methanol',                 sep: 120, notes: 'Solvent / racing fuel' },
    { id: 'acetylene', name: 'Acetylene',                sep: 200, notes: 'Welding gas · shock-sensitive' },
    { id: 'generic',   name: 'Generic BLEVE (unknown)',  sep: 150, notes: 'Conservative default' },
  ];

  const THERMAL_ZONES = [
    { level: 'fireball', label: 'Fireball Zone',                          q_kwm2: null, color: '#8B0000', desc: 'Within the fireball — certain fatality · do not enter' },
    { level: 'lethal',   label: 'Lethal Thermal Radiation (37.5 kW/m²)',  q_kwm2: 37.5, color: '#CC0000', desc: '1% lethality in 10 s · severe burns · immediate evacuation' },
    { level: 'severe',   label: 'Severe Burns (12.5 kW/m²)',              q_kwm2: 12.5, color: '#FF6600', desc: '3rd-degree burns in 10 s · serious casualties' },
    { level: 'moderate', label: 'Significant Burns (4.0 kW/m²)',          q_kwm2: 4.0,  color: '#FFD700', desc: '1st-degree burns in 10 s · shelter or evacuate immediately' },
    { level: 'pain',     label: 'Pain / Discomfort (1.6 kW/m²)',          q_kwm2: 1.6,  color: '#E8E8A0', desc: 'Pain in 5–10 s · laceration risk from glass · evacuation recommended' },
  ];

  const TRANSMISSIVITY = 0.75;

  function fireball_params(mass_kg) {
    const r_f = 3.24 * Math.pow(mass_kg, 0.325);
    const t_f = mass_kg < 30000 ? 1.07 * Math.pow(mass_kg, 0.26) : 0.23 * Math.pow(mass_kg, 0.444);
    const h_f = 0.75 * (2.0 * r_f);
    return { radius_m: r_f, duration_s: t_f, center_height_m: h_f };
  }

  function thermal_flux(D_m, r_f, h_f, sep) {
    if (D_m <= 0) return 1e9;
    const r_slant = Math.sqrt(Math.pow(D_m, 2) + Math.pow(h_f, 2));
    return sep * Math.pow(r_f / r_slant, 2) * TRANSMISSIVITY;
  }

  function distance_for_flux(q_target, r_f, h_f, sep) {
    if (thermal_flux(r_f, r_f, h_f, sep) < q_target) return null;
    let d_lo = r_f, d_hi = 100000.0;
    if (thermal_flux(d_hi, r_f, h_f, sep) > q_target) return null;
    for (let i = 0; i < 80; i++) {
      const d_mid = (d_lo + d_hi) / 2;
      const q = thermal_flux(d_mid, r_f, h_f, sep);
      if (Math.abs(q - q_target) / q_target < 1e-6) break;
      if (q > q_target) d_lo = d_mid; else d_hi = d_mid;
    }
    return (d_lo + d_hi) / 2;
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

  function compute_bleve_zones(lat, lon, mass_kg, fuel_id) {
    fuel_id = fuel_id || 'propane';
    const fuel = FUELS.find((f) => f.id === fuel_id) || FUELS[FUELS.length - 1];
    const sep = fuel.sep;
    const fb = fireball_params(mass_kg);
    const r_f = fb.radius_m, h_f = fb.center_height_m, t_f = fb.duration_s;

    const features = [], stats = {};
    const fbZone = THERMAL_ZONES[0];
    features.push({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [_circle_coords(lat, lon, r_f)] },
      properties: { type: 'bleve_zone', level: 'fireball', label: fbZone.label, color: fbZone.color,
                    q_kwm2: null, radius_m: r1(r_f), radius_km: r3(r_f / 1000), desc: fbZone.desc },
    });
    stats.fireball = { label: fbZone.label, color: fbZone.color, q_kwm2: null,
                       radius_m: r1(r_f), radius_km: r3(r_f / 1000), desc: fbZone.desc };

    for (let i = 1; i < THERMAL_ZONES.length; i++) {
      const zone = THERMAL_ZONES[i];
      const D = distance_for_flux(zone.q_kwm2, r_f, h_f, sep);
      if (D == null || D < r_f) continue;
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [_circle_coords(lat, lon, D)] },
        properties: { type: 'bleve_zone', level: zone.level, label: zone.label, color: zone.color,
                      q_kwm2: zone.q_kwm2, radius_m: r1(D), radius_km: r3(D / 1000), desc: zone.desc },
      });
      stats[zone.level] = { label: zone.label, color: zone.color, q_kwm2: zone.q_kwm2,
                            radius_m: r1(D), radius_km: r3(D / 1000), desc: zone.desc };
    }
    features.push({
      type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: { type: 'bleve_source', mass_kg: mass_kg, fuel: fuel.name },
    });
    return {
      geojson: { type: 'FeatureCollection', features }, stats,
      fireball: { radius_m: r1(r_f), radius_km: r3(r_f / 1000), duration_s: r1(t_f),
                  center_height_m: r1(h_f), sep_kwm2: sep },
      fuel_id, fuel_name: fuel.name, mass_kg,
    };
  }

  return { FUELS, THERMAL_ZONES, TRANSMISSIVITY,
           fireball_params, thermal_flux, distance_for_flux, compute_bleve_zones };
});
