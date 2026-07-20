"""
Per-user isolation of model results and export URLs.

Overlay state was once a single module-level dict shared by every request, and
the export URLs were a single global cache on a constant public path. Two people
using the site at once overwrote each other, and anyone who knew the URL could
download the most recent package or overlay set from any organization.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import Results, isolated_db, clear_env

isolated_db()
import db
import main
clear_env()
from fastapi.testclient import TestClient
from auth import hash_password

client = TestClient(main.app)
# A separate client keeps its own cookie jar — TestClient persists cookies, so
# reusing `client` for "anonymous" requests silently sends the last login's.
anon = TestClient(main.app)
r = Results("Per-user isolation")

for name in ("alice", "bob"):
    db.create_user(name, hash_password("password123"), role="user")


def login(name):
    return client.post("/auth/login", json={"username": name, "password": "password123"}).cookies


ca, cb = login("alice"), login("bob")

PLUME = {"lat": 34.05, "lon": -118.25, "chemical_id": "chlorine",
         "release_rate_kg_min": 1.0, "wind_speed_ms": 3.0,
         "wind_dir_from_deg": 270, "stability": "D"}
BLAST = {"lat": 40.71, "lon": -74.01, "weight_kg": 500.0, "explosive_id": "tnt"}


# ── Concurrent users ─────────────────────────────────────────────────────────
r.section("concurrent users do not collide")
resp_a = client.post("/api/plume", json=PLUME, cookies=ca)
r.check("alice's plume runs", resp_a.status_code == 200, f"{resp_a.status_code}: {resp_a.text[:120]}")
resp_b = client.post("/api/blast", json=BLAST, cookies=cb)
r.check("bob's blast runs", resp_b.status_code == 200, f"{resp_b.status_code}: {resp_b.text[:120]}")

overlays_a = client.get("/api/health", cookies=ca).json()["active_overlays"]
overlays_b = client.get("/api/health", cookies=cb).json()["active_overlays"]
r.check("alice sees her plume", overlays_a.get("plume") is True, str(overlays_a))
r.check("alice does NOT see bob's blast", overlays_a.get("blast") is False, str(overlays_a))
r.check("bob sees his blast", overlays_b.get("blast") is True, str(overlays_b))
r.check("bob does NOT see alice's plume", overlays_b.get("plume") is False, str(overlays_b))


# ── Exports ──────────────────────────────────────────────────────────────────
r.section("exports contain only your own work")
export_a = client.get("/kml/download", cookies=ca)
export_b = client.get("/kml/download", cookies=cb)
r.check("alice's export succeeds", export_a.status_code == 200, f"{export_a.status_code}")
r.check("bob's export succeeds", export_b.status_code == 200, f"{export_b.status_code}")
r.check("alice's export has her chemical", "Chlorine" in export_a.text, export_a.text[:200])
r.check("alice's export lacks bob's blast",
        "Overpressure" not in export_a.text and "TNT" not in export_a.text)


# ── Google Earth feed tokens ─────────────────────────────────────────────────
r.section("Google Earth feed is per user")
r.check("network.kml requires a session", anon.get("/kml/network.kml").status_code == 401)
network = client.get("/kml/network.kml", cookies=ca)
r.check("a signed-in user gets a network link", network.status_code == 200, f"{network.status_code}")

match = re.search(r"/kml/live/([^<\s]+)\.kml", network.text)
r.check("the link embeds a feed token", match is not None, network.text[:200])
if match:
    token = match.group(1)
    feed = anon.get(f"/kml/live/{token}.kml")
    r.check("the feed works with no cookie (Google Earth cannot send one)",
            feed.status_code == 200, f"{feed.status_code}")
    r.check("the feed returns alice's data", "Chlorine" in feed.text, feed.text[:200])
    r.check("the feed excludes bob's blast", "Overpressure" not in feed.text)
    forged = token.split(".")[0] + ".0000000000000000000000000000dead"
    r.check("a forged token is rejected", anon.get(f"/kml/live/{forged}.kml").status_code == 404)
r.check("the old public /kml/live.kml no longer serves data",
        anon.get("/kml/live.kml").status_code == 410)


# ── Clearing ─────────────────────────────────────────────────────────────────
r.section("clearing is per user")
client.delete("/api/overlay", cookies=ca)
after_a = client.get("/api/health", cookies=ca).json()["active_overlays"]
after_b = client.get("/api/health", cookies=cb).json()["active_overlays"]
r.check("alice's overlays are cleared", not any(after_a.values()), str(after_a))
r.check("bob's overlays survive", after_b.get("blast") is True, str(after_b))


# ── TAK package tokens ───────────────────────────────────────────────────────
r.section("TAK package download tokens")
t1 = main._kmz_put(b"PACKAGE-ONE", "one.kmz")
t2 = main._kmz_put(b"PACKAGE-TWO", "two.kmz")
r.check("tokens are distinct", t1 != t2)
r.check("tokens are long enough to be unguessable", len(t1) >= 32, f"len={len(t1)}")

first = anon.get(f"/kml/pkg/{t1}.kmz")
r.check("a token downloads its own package",
        first.status_code == 200 and first.content == b"PACKAGE-ONE", f"{first.status_code}")
r.check("each token gets its own package, not a shared global",
        anon.get(f"/kml/pkg/{t2}.kmz").content == b"PACKAGE-TWO")
r.check("download needs no auth (ATAK cannot send cookies)", first.status_code == 200)
r.check("an unknown token 404s", anon.get("/kml/pkg/not-a-real-token.kmz").status_code == 404)
r.check("the old public /kml/live.kmz no longer serves data",
        anon.get("/kml/live.kmz").status_code == 410)


# ── Expiry and bounds ────────────────────────────────────────────────────────
r.section("expiry and memory bounds")
original_ttl = main._KMZ_TTL_SECONDS
main._KMZ_TTL_SECONDS = -1                     # expired on insert
stale = main._kmz_put(b"STALE", "stale.kmz")
r.check("an expired token stops working", anon.get(f"/kml/pkg/{stale}.kmz").status_code == 404)
main._KMZ_TTL_SECONDS = original_ttl

for i in range(main._KMZ_MAX_ENTRIES + 10):
    main._kmz_put(b"x", f"{i}.kmz")
r.check("the package store stays bounded",
        len(main._kmz_store) <= main._KMZ_MAX_ENTRIES, f"{len(main._kmz_store)} entries")

for i in range(main._OVERLAY_MAX_USERS + 5):
    main._overlays({"id": 10_000 + i})
r.check("the overlay store stays bounded",
        len(main._overlay_store) <= main._OVERLAY_MAX_USERS, f"{len(main._overlay_store)} entries")

sys.exit(r.report())
