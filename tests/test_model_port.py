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
import blast as py_blast
import bleve as py_bleve
import radiation as py_rad

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

    # ── Blast: Brode overpressure + bisection solver ────────────────────────
    for Z in [0.05, 0.2, 0.4, 0.5, 0.6, 1.0, 5.0, 20.0, 100.0, 500.0]:
        add("overpressure_kPa", {"Z": Z}, py_blast.overpressure_kPa(Z))
    for zone in py_blast.DAMAGE_ZONES:
        add("scaled_distance_for_pressure", {"target_kPa": zone["kPa"]},
            py_blast._scaled_distance_for_pressure(zone["kPa"]))

    # ── BLEVE: thermal flux + distance solver ───────────────────────────────
    for mass in [500.0, 5000.0, 29999.0, 30000.0, 80000.0]:
        fb = py_bleve.fireball_params(mass)
        for D in [fb["radius_m"], 200.0, 1000.0, 5000.0]:
            add("thermal_flux",
                {"D": D, "r_f": fb["radius_m"], "h_f": fb["center_height_m"], "sep": 200},
                py_bleve._thermal_flux(D, fb["radius_m"], fb["center_height_m"], 200))
        for q in [37.5, 12.5, 4.0, 1.6]:
            add("distance_for_flux",
                {"q": q, "r_f": fb["radius_m"], "h_f": fb["center_height_m"], "sep": 200},
                py_bleve._distance_for_flux(q, fb["radius_m"], fb["center_height_m"], 200))

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

    # ── Blast: full zone geometry (circle rings) ────────────────────────────
    r.section("blast zone geometry")
    for eid, w in [("tnt", 500.0), ("c4", 100.0), ("anfo", 2000.0)]:
        py_out = py_blast.compute_blast_zones(34.05, -118.25, w, eid)
        js_out = _run_js([{"fn": "compute_blast_zones",
                           "args": {"lat": 34.05, "lon": -118.25, "weight_kg": w, "explosive_id": eid}}])[0]["value"]
        pf = py_out["geojson"]["features"]
        jf = js_out["geojson"]["features"]
        same = len(pf) == len(jf) and _coords_match(pf, jf)
        r.check(f"{eid} {w}kg: same zones and identical ring geometry", same,
                f"py {len(pf)} feats / js {len(jf)} feats")
        r.check(f"{eid} {w}kg: W_tnt matches", _close(py_out["W_tnt_kg"], js_out["W_tnt_kg"]),
                f"py={py_out['W_tnt_kg']} js={js_out['W_tnt_kg']}")

    # ── BLEVE: fireball params + zone geometry ──────────────────────────────
    r.section("bleve fireball + geometry")
    for fuel, mass in [("propane", 40000.0), ("lng", 5000.0), ("gasoline", 20000.0)]:
        py_out = py_bleve.compute_bleve_zones(34.05, -118.25, mass, fuel)
        js_out = _run_js([{"fn": "compute_bleve_zones",
                           "args": {"lat": 34.05, "lon": -118.25, "mass": mass, "fuel_id": fuel}}])[0]["value"]
        r.check(f"{fuel} {mass}kg: fireball radius matches",
                _close(py_out["fireball"]["radius_m"], js_out["fireball"]["radius_m"]),
                f"py={py_out['fireball']['radius_m']} js={js_out['fireball']['radius_m']}")
        r.check(f"{fuel} {mass}kg: duration matches",
                _close(py_out["fireball"]["duration_s"], js_out["fireball"]["duration_s"]))
        pf, jf = py_out["geojson"]["features"], js_out["geojson"]["features"]
        r.check(f"{fuel} {mass}kg: identical zone ring geometry",
                len(pf) == len(jf) and _coords_match(pf, jf),
                f"py {len(pf)} feats / js {len(jf)} feats")

    # ── Radiation: dose contours (reuses the plume geometry, Ci units) ──────
    r.section("radiation dose contours")
    for rid in ["cs137", "co60", "sr90"]:
        rad = py_rad.get_radionuclide(rid)
        rargs = {"Q": 0.5, "u": 3.0, "stability": "D", "dcf": rad["dcf_cloud"],
                 "lat": 34.05, "lon": -118.25, "wind_from": 270.0, "H": 0.0}
        py_c = py_rad.compute_radiation_contours(
            rargs["Q"], rargs["u"], rargs["stability"], rargs["dcf"],
            rargs["lat"], rargs["lon"], rargs["wind_from"], rargs["H"])
        js_c = _run_js([{"fn": "compute_radiation_contours", "args": rargs}])[0]["value"]
        ok = set(py_c) == set(js_c)
        vworst = 0.0
        for level in py_c:
            pl, jl = py_c[level]["latlon"], js_c[level]["latlon"]
            if len(pl) != len(jl):
                ok = False
                continue
            for (a1, b1), (a2, b2) in zip(pl, jl):
                vworst = max(vworst, abs(a1 - a2), abs(b1 - b2))
                if not (_close(a1, a2) and _close(b1, b2)):
                    ok = False
        r.check(f"{rid}: dose contours match Python (worst {vworst:.1e} deg)", ok)

    return r.report()


def _coords_match(py_features, js_features):
    """Compare two GeoJSON feature lists by geometry coordinates at full precision.

    Only geometry is compared, not properties: properties carry display values
    rounded with Python's banker's rounding, which differs from JS in the last
    ulp. The ring/point coordinates are unrounded, so they must agree exactly.
    """
    for pf, jf in zip(py_features, js_features):
        pg, jg = pf["geometry"], jf["geometry"]
        if pg["type"] != jg["type"]:
            return False
        if pg["type"] == "Point":
            if not all(_close(a, b) for a, b in zip(pg["coordinates"], jg["coordinates"])):
                return False
        else:  # Polygon
            pring, jring = pg["coordinates"][0], jg["coordinates"][0]
            if len(pring) != len(jring):
                return False
            for (px, pyy), (jx, jy) in zip(pring, jring):
                if not (_close(px, jx) and _close(pyy, jy)):
                    return False
    return True


if __name__ == "__main__":
    sys.exit(main())
