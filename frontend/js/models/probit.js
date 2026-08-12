/*
 * Probit casualty estimation — Ten Berge (1986) / TNO Green Book fallback.
 * Faithful port of backend/probit.py; cross-validated in test_model_port.py.
 *
 * This model's OUTPUT is rounded numbers (integer casualties, percentages), so
 * the port replicates Python's round-half-to-even rather than JS's round-half-up
 * — otherwise a .5 boundary would report a different casualty count than the
 * server. See pyround below.
 */
(function (root, factory) {
  const mod = factory();
  if (typeof module === 'object' && module.exports) module.exports = mod;
  else { root.WMDModels = root.WMDModels || {}; root.WMDModels.probit = mod; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* Python's round(): round half to EVEN, unlike JS Math.round (half up).
   * A tie is only a tie when the scaled value is EXACTLY N.5 — a value like
   * 267.4999999… (how 2.675 actually stores) is below the tie and rounds down,
   * which is exactly what Python does. Do not use an epsilon here. */
  function pyround(x, ndigits) {
    ndigits = ndigits || 0;
    const m = Math.pow(10, ndigits);
    const y = x * m;
    const floor = Math.floor(y);
    const frac = y - floor;
    let r;
    if (frac < 0.5) r = floor;
    else if (frac > 0.5) r = floor + 1;
    else r = (floor % 2 === 0) ? floor : floor + 1;
    return r / m;
  }

  const _AS_P = 0.2316419, _AS_B1 = 0.319381530, _AS_B2 = -0.356563782,
        _AS_B3 = 1.781477937, _AS_B4 = -1.821255978, _AS_B5 = 1.330274429;

  function _norm_cdf(z) {
    if (z <= -8.0) return 0.0;
    if (z >= 8.0) return 1.0;
    const abs_z = Math.abs(z);
    const t = 1.0 / (1.0 + _AS_P * abs_z);
    const poly = t * (_AS_B1 + t * (_AS_B2 + t * (_AS_B3 + t * (_AS_B4 + t * _AS_B5))));
    const phi = 1.0 - (1.0 / Math.sqrt(2.0 * Math.PI)) * Math.exp(-0.5 * abs_z * abs_z) * poly;
    return z >= 0.0 ? phi : 1.0 - phi;
  }

  function probit_to_fraction(Y) { return _norm_cdf(Y - 5.0); }

  const CHEM_PROBIT = {
    cl2:     { a: -8.29,  b: 0.92,  n: 2.0 },
    nh3:     { a: -15.6,  b: 1.0,   n: 1.5 },
    hcn:     { a: -29.42, b: 3.008, n: 1.0 },
    so2:     { a: -19.2,  b: 2.4,   n: 1.0 },
    h2s:     { a: -31.42, b: 3.008, n: 1.0 },
    cg:      { a: -19.27, b: 3.686, n: 1.0 },
    no2:     { a: -13.79, b: 1.4,   n: 2.0 },
    default: { a: -10.0,  b: 1.0,   n: 1.0 },
  };

  const ZONE_FRACTIONS = {
    high: [0.50, 0.25, 0.15], medium: [0.10, 0.30, 0.25], low: [0.02, 0.08, 0.20],
    erpg3: [0.50, 0.25, 0.15], idlh: [0.35, 0.30, 0.20], erpg2: [0.05, 0.25, 0.30], erpg1: [0.01, 0.05, 0.15],
    lfl: [0.45, 0.30, 0.15], half_lfl: [0.05, 0.10, 0.20],
    severe: [0.50, 0.30, 0.15], moderate: [0.20, 0.30, 0.30], light: [0.05, 0.10, 0.40],
    catastrophic: [0.80, 0.15, 0.04], severe_struct: [0.50, 0.30, 0.15], moderate_struct: [0.20, 0.30, 0.30],
    light_struct: [0.05, 0.10, 0.40], glass: [0.01, 0.03, 0.15],
    extreme: [0.90, 0.08, 0.02], worker: [0.05, 0.15, 0.30], pag: [0.00, 0.02, 0.05],
    fireball: [0.95, 0.04, 0.01], lethal: [0.60, 0.25, 0.10], pain: [0.00, 0.05, 0.30],
    co_idlh: [0.30, 0.40, 0.20], co_high: [0.05, 0.20, 0.40], co_osha: [0.00, 0.05, 0.20],
    hazardous: [0.10, 0.25, 0.40], very_unhealthy: [0.01, 0.10, 0.40], unhealthy: [0.00, 0.02, 0.20],
    usg: [0.00, 0.00, 0.05], high_rad: [0.50, 0.30, 0.15],
  };

  function _probit_lethality(threshold_ppm, exposure_min, coeffs) {
    if (threshold_ppm <= 0 || exposure_min <= 0) return 0.0;
    const ct = Math.pow(threshold_ppm, coeffs.n) * exposure_min;
    if (ct <= 0) return 0.0;
    const pr = coeffs.a + coeffs.b * Math.log(ct);
    return Math.max(0.0, Math.min(1.0, probit_to_fraction(pr)));
  }

  function compute_probit_zones(zones, exposure_min, gas_id) {
    let coeffs = null, use_probit = false;
    if (gas_id != null) { coeffs = CHEM_PROBIT[gas_id] || CHEM_PROBIT.default; use_probit = true; }
    const method = use_probit ? 'Probit (Ten Berge)' : 'Zone-based estimate (TNO Green Book)';

    let total_fat = 0, total_ser = 0, total_min = 0;
    const enriched_zones = [];

    for (const zone of zones) {
      const level = zone.level || '';
      const pop = parseFloat(zone.pop_estimate || 0);
      const threshold_ppm = zone.threshold_ppm;
      let lethality, serious, minor;

      if (use_probit && threshold_ppm != null && threshold_ppm > 0) {
        lethality = _probit_lethality(threshold_ppm, exposure_min, coeffs);
        const ct_full = Math.pow(threshold_ppm, coeffs.n) * exposure_min;
        const ct_serious = ct_full * 0.35;
        let frac_serious_cum = 0.0;
        if (ct_serious > 0) {
          const pr_s = coeffs.a + coeffs.b * Math.log(ct_serious);
          frac_serious_cum = Math.max(0.0, Math.min(1.0, probit_to_fraction(pr_s)));
        }
        serious = Math.max(0.0, frac_serious_cum - lethality);
        const survivor = Math.max(0.0, 1.0 - lethality - serious);
        minor = Math.min(0.5, 0.4 * survivor);
      } else {
        let fracs = ZONE_FRACTIONS[level];
        if (fracs == null) fracs = ZONE_FRACTIONS[level.split('_')[0]] || [0.01, 0.05, 0.10];
        lethality = fracs[0]; serious = fracs[1]; minor = fracs[2];
      }

      const fatalities = pyround(pop * lethality);
      const serious_injuries = pyround(pop * serious);
      const minor_injuries = pyround(pop * minor);
      total_fat += fatalities; total_ser += serious_injuries; total_min += minor_injuries;

      const enriched = Object.assign({}, zone);
      enriched.lethality_pct = pyround(lethality * 100.0, 1);
      enriched.serious_pct = pyround(serious * 100.0, 1);
      enriched.minor_pct = pyround(minor * 100.0, 1);
      enriched.fatalities = fatalities;
      enriched.serious_injuries = serious_injuries;
      enriched.minor_injuries = minor_injuries;
      enriched_zones.push(enriched);
    }

    return {
      zones: enriched_zones,
      totals: { fatalities: total_fat, serious_injuries: total_ser, minor_injuries: total_min,
                total_casualties: total_fat + total_ser + total_min },
      exposure_min, method,
      note: 'Estimates assume uniform distribution and no warning/evacuation time. ' +
            'Actual casualties depend on shelter, evacuation actions, and time to escape.',
    };
  }

  return { pyround, probit_to_fraction, CHEM_PROBIT, ZONE_FRACTIONS, compute_probit_zones };
});
