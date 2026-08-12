"""
Cross-validate the JavaScript model port against the Python original.

The offline Android app runs the models in JavaScript. Those ports must produce
the same numbers as the Python that has been in the field — a plume that differs
between the server and the phone is worse than useless. This drives both
implementations over the same input grid and asserts they agree to within
floating-point tolerance.

Keystone coverage: dispersion.py <-> frontend/js/models/dispersion.js. The
remaining models follow the same harness as they are ported.

Runs the JS via `node`. Skips (does not fail) if node is unavailable, so the
Python-only test environments still pass.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import Results, add_backend_to_path

add_backend_to_path()
import dispersion as py

DRIVER = Path(__file__).resolve().parent / "model_port_driver.js"

# How closely JS must match Python. Both are IEEE-754 doubles running the same
# operations, so agreement is near-exact; 1e-9 relative leaves room only for
# last-bit differences between `**` and Math.pow.
RTOL = 1e-9
ATOL = 1e-12


def _run_js(cases):
    node = shutil.which("node")
    if not node:
        return None
    proc = subprocess.run([node, str(DRIVER)], input=json.dumps(cases),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"node driver failed: {proc.stderr[:400]}")
    return json.loads(proc.stdout)


def _close(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a == b
    return abs(a - b) <= max(ATOL, RTOL * max(abs(a), abs(b)))


def main():
    r = Results("Model port — dispersion.py <-> dispersion.js")

    if shutil.which("node") is None:
        print("SKIP — node not available; cannot cross-validate the JS port.")
        return 0

    # ── Build a grid of scalar cases and their Python reference values ───────
    stabilities = ["A", "B", "C", "D", "E", "F"]
    cases, refs = [], []

    def add(fn, args, ref):
        cases.append({"fn": fn, "args": args})
        refs.append(ref)

    for s in stabilities:
        for x in [10, 100, 500, 1000, 5000, 25000, 100000]:
            add("sigma_y", {"x": x, "stability": s}, py.sigma_y(x, s))
            add("sigma_z", {"x": x, "stability": s}, py.sigma_z(x, s))
            for Q in [1.0, 50.0, 1000.0]:
                for u in [0.3, 1.0, 3.0, 8.0]:
                    for H in [0.0, 10.0, 50.0]:
                        add("centerline_concentration",
                            {"x": x, "Q": Q, "u": u, "stability": s, "H": H},
                            py.centerline_concentration(x, Q, u, s, H))
                        add("ground_concentration",
                            {"x": x, "y": 37.0, "Q": Q, "u": u, "stability": s, "H": H},
                            py.ground_concentration(x, 37.0, Q, u, s, H))

    for mw in [17.03, 70.9, 46.01, 64.07]:
        for c in [1e-6, 1e-3, 0.5, 12.0]:
            add("gm3_to_ppm", {"c": c, "mw": mw}, py.gm3_to_ppm(c, mw))
            add("ppm_to_gm3", {"c": c, "mw": mw}, py.ppm_to_gm3(c, mw))

    for s in stabilities:
        for thr in [1e-6, 1e-4, 1e-2, 0.1]:
            for Q in [10.0, 500.0]:
                for u in [1.0, 5.0]:
                    add("find_max_downwind",
                        {"threshold": thr, "Q": Q, "u": u, "stability": s, "H": 0.0},
                        py.find_max_downwind(thr, Q, u, s, 0.0))
                    add("plume_half_width",
                        {"x": 1200.0, "threshold": thr, "Q": Q, "u": u, "stability": s, "H": 0.0},
                        py.plume_half_width(1200.0, thr, Q, u, s, 0.0))

    # Stability classifier over its whole decision tree.
    for u in [1.0, 2.5, 4.0, 5.5, 9.0]:
        for day in [True, False]:
            for cloud in [0.0, 0.5, 0.9]:
                for solar in [10.0, 45.0, 70.0]:
                    add("determine_stability_class",
                        {"u": u, "day": day, "cloud": cloud, "solar": solar},
                        py.determine_stability_class(u, day, cloud, solar))

    js = _run_js(cases)
    r.check("node produced a result for every case", js is not None and len(js) == len(cases),
            f"{len(js) if js else 0} vs {len(cases)}")

    # ── Compare scalars ──────────────────────────────────────────────────────
    mismatches = []
    for c, ref, got in zip(cases, refs, js):
        if not got.get("ok"):
            mismatches.append((c["fn"], c["args"], ref, "JS ERROR: " + got.get("error", "")))
            continue
        if not _close(ref, got["value"]):
            mismatches.append((c["fn"], c["args"], ref, got["value"]))

    r.check(f"all {len(cases)} scalar cases match Python within {RTOL:g}",
            not mismatches, f"{len(mismatches)} mismatch(es)")
    for fn, args, ref, got in mismatches[:8]:
        print(f"     MISMATCH {fn}{args}: py={ref} js={got}")

    # ── Compare a full plume contour set, vertex by vertex ───────────────────
    r.section("full contour geometry")
    thresholds = {
        "low":    {"value": 0.5,  "label": "AEGL-1", "color": "#FFFF00"},
        "medium": {"value": 2.0,  "label": "AEGL-2", "color": "#FF8C00"},
        "high":   {"value": 20.0, "label": "AEGL-3", "color": "#FF0000"},
    }
    contour_args = {"Q": 50.0, "u": 3.0, "stability": "D", "mw": 70.9,
                    "thresholds": thresholds, "lat": 34.05, "lon": -118.25,
                    "wind_from": 270.0, "H": 0.0}
    py_contours = py.compute_all_contours(
        contour_args["Q"], contour_args["u"], contour_args["stability"],
        contour_args["mw"], thresholds, contour_args["lat"], contour_args["lon"],
        contour_args["wind_from"], contour_args["H"])
    js_contours = _run_js([{"fn": "compute_all_contours", "args": contour_args}])[0]["value"]

    r.check("same set of contour levels",
            set(py_contours.keys()) == set(js_contours.keys()),
            f"py={sorted(py_contours)} js={sorted(js_contours)}")

    worst = 0.0
    vertex_ok = True
    for level in py_contours:
        pl = py_contours[level]["latlon"]
        jl = js_contours[level]["latlon"]
        if len(pl) != len(jl):
            vertex_ok = False
            print(f"     {level}: vertex count differs py={len(pl)} js={len(jl)}")
            continue
        for (plat, plon), (jlat, jlon) in zip(pl, jl):
            worst = max(worst, abs(plat - jlat), abs(plon - jlon))
            if not (_close(plat, jlat) and _close(plon, jlon)):
                vertex_ok = False
    r.check("every contour vertex matches Python", vertex_ok, f"worst delta {worst:.2e} deg")

    for level in py_contours:
        r.check(f"{level}: downwind distance matches",
                _close(py_contours[level]["max_downwind_m"], js_contours[level]["max_downwind_m"]),
                f"py={py_contours[level]['max_downwind_m']} js={js_contours[level]['max_downwind_m']}")

    print(f"\n(worst geographic disagreement across all vertices: {worst:.2e} degrees)")
    return r.report()


if __name__ == "__main__":
    sys.exit(main())
