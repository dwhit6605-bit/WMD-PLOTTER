/*
 * Cross-validation driver: reads test cases as JSON on stdin, evaluates each
 * against the JS model port, writes results as JSON on stdout. Paired with
 * test_model_port.py, which supplies the same cases to the Python original and
 * compares. Kept dumb on purpose — all the assertion logic lives in Python.
 */
const path = require('path');
const dispersion = require(path.join(__dirname, '..', 'frontend', 'js', 'models', 'dispersion.js'));

const DISPATCH = {
  sigma_y:                   (a) => dispersion.sigma_y(a.x, a.stability),
  sigma_z:                   (a) => dispersion.sigma_z(a.x, a.stability),
  centerline_concentration:  (a) => dispersion.centerline_concentration(a.x, a.Q, a.u, a.stability, a.H),
  ground_concentration:      (a) => dispersion.ground_concentration(a.x, a.y, a.Q, a.u, a.stability, a.H),
  gm3_to_ppm:                (a) => dispersion.gm3_to_ppm(a.c, a.mw),
  ppm_to_gm3:                (a) => dispersion.ppm_to_gm3(a.c, a.mw),
  find_max_downwind:         (a) => dispersion.find_max_downwind(a.threshold, a.Q, a.u, a.stability, a.H),
  plume_half_width:          (a) => dispersion.plume_half_width(a.x, a.threshold, a.Q, a.u, a.stability, a.H),
  determine_stability_class: (a) => dispersion.determine_stability_class(a.u, a.day, a.cloud, a.solar),
  compute_all_contours:      (a) => dispersion.compute_all_contours(
                                      a.Q, a.u, a.stability, a.mw, a.thresholds,
                                      a.lat, a.lon, a.wind_from, a.H),
};

let raw = '';
process.stdin.on('data', (d) => { raw += d; });
process.stdin.on('end', () => {
  const cases = JSON.parse(raw);
  const out = cases.map((c) => {
    try {
      return { ok: true, value: DISPATCH[c.fn](c.args) };
    } catch (e) {
      return { ok: false, error: String(e && e.message || e) };
    }
  });
  process.stdout.write(JSON.stringify(out));
});
