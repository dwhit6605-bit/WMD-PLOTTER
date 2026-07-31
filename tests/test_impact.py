"""
Impact assessment — what falls inside the active hazard zones.

Drives a real plume through the HTTP API, seeds facilities at known positions,
and checks /api/impact assigns each to the right zone. HIFLD is left off so the
suite has no external network dependency; the endpoint's own error handling for
a HIFLD failure is covered separately by leaving include_infra on with no anchor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import Results, isolated_db, clear_env

isolated_db()
import db
import impact
import main
clear_env()
from fastapi.testclient import TestClient
from auth import hash_password

client = TestClient(main.app)
r = Results("Impact assessment")

db.create_user("op", hash_password("password123"), role="user")
cookies = client.post("/auth/login", json={"username": "op", "password": "password123"}).cookies

# A plume at a known origin. West wind (from 270) pushes the footprint east.
ORIGIN = {"lat": 34.05, "lon": -118.25}
PLUME = {**ORIGIN, "chemical_id": "chlorine", "release_rate_kg_min": 5.0,
         "wind_speed_ms": 3.0, "wind_dir_from_deg": 270, "stability": "F"}


# ── Before any model: nothing to assess ─────────────────────────────────────
r.section("no model yet")
resp = client.post("/api/impact", json={"include_infra": False}, cookies=cookies)
r.check("endpoint responds", resp.status_code == 200, f"{resp.status_code}: {resp.text[:120]}")
r.check("reports nothing modelled", resp.json()["total"] == 0 and "note" in resp.json(),
        str(resp.json())[:160])


# ── Run the plume, then read back the zone geometry we will test against ────
r.section("with an active plume")
run = client.post("/api/plume", json=PLUME, cookies=cookies)
r.check("plume runs", run.status_code == 200, f"{run.status_code}: {run.text[:160]}")

# Pull the actual computed zones so the fixtures are placed relative to reality,
# not guessed coordinates that might fall outside the footprint.
zones = impact.extract_zones(main._overlays({"id": [u["id"] for u in db.list_users()
                                                       if u["username"] == "op"][0]}))
r.check("at least one zone was produced", len(zones) >= 1, f"{len(zones)} zones")

# A point guaranteed inside: the vertex-centroid of the innermost zone, computed
# from the real returned geometry. The source itself is NOT reliable — it sits on
# the upwind boundary of the footprint, where a point is ambiguous by design.
inner_ring = zones[0]["ring"]
inside_pt = {"lat": sum(p[0] for p in inner_ring) / len(inner_ring),
             "lon": sum(p[1] for p in inner_ring) / len(inner_ring)}
r.check("the chosen test point is genuinely inside the innermost zone",
        impact.point_in_ring(inside_pt["lat"], inside_pt["lon"], inner_ring))
# A point guaranteed outside: far away.
outside_pt = {"lat": 40.0, "lon": -74.0}

uid = [u["id"] for u in db.list_users() if u["username"] == "op"][0]
db.create_facility("Downtown Hospital", "hospital", inside_pt["lat"], inside_pt["lon"],
                   None, None, 0.0, "", uid)
db.create_facility("Far Refinery", "refinery", outside_pt["lat"], outside_pt["lon"],
                   None, None, 0.0, "", uid)

resp = client.post("/api/impact", json={"include_infra": False}, cookies=cookies)
r.check("impact responds 200", resp.status_code == 200, f"{resp.status_code}")
data = resp.json()

r.check("the in-zone facility is counted", data["total"] >= 1, str(data)[:200])
r.check("the far facility is NOT counted",
        not any(p["name"] == "Far Refinery"
                for z in data["zones"] for p in z["points"]),
        "far refinery leaked into a zone")
r.check("the in-zone facility is listed",
        any(p["name"] == "Downtown Hospital"
            for z in data["zones"] for p in z["points"]))
r.check("it is categorised by facility type",
        data["by_category"].get("hospital", 0) >= 1, str(data["by_category"]))
r.check("distance from source is reported",
        any("distance_m" in p for z in data["zones"] for p in z["points"]))
r.check("candidates_checked reflects both facilities", data["candidates_checked"] == 2,
        str(data.get("candidates_checked")))
r.check("far facility shows as unaffected", data["unaffected"] >= 1, str(data["unaffected"]))


# ── Per-user isolation carries through ──────────────────────────────────────
r.section("isolation")
db.create_user("other", hash_password("password123"), role="user")
other = client.post("/auth/login", json={"username": "other", "password": "password123"}).cookies
resp = client.post("/api/impact", json={"include_infra": False}, cookies=other)
r.check("a user with no model of their own sees no zones",
        resp.json()["total"] == 0, str(resp.json())[:160])


# ── Requires a session ──────────────────────────────────────────────────────
r.section("auth")
anon = TestClient(main.app)
r.check("impact requires a session", anon.post("/api/impact", json={}).status_code == 401,
        f"{anon.post('/api/impact', json={}).status_code}")

sys.exit(r.report())
