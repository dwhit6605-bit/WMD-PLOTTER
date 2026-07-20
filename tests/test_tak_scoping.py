"""
Per-organization TAK server scoping.

TAK pushes carry operational incident data to a specific agency's server, so
resolution must never cross organizations. Covers the original bug (an org with
no profile silently inheriting the site admin's server) and the two holes found
alongside it (profile_id overrides ignoring ownership, and org membership read
from a week-old token).
"""

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
r = Results("TAK — per-organization scoping")


def login(username, password="password123"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.cookies


# ── Fixtures: two agencies, each with its own server, plus a global one ──────
org_a = db.create_org("Riverside County Fire")
org_b = db.create_org("Kern County HazMat")

for name, role in [("siteadmin", "admin"), ("adminA", "org_admin"), ("userA", "user"),
                   ("adminB", "org_admin"), ("userB", "user"), ("orphan", "user")]:
    db.create_user(name, hash_password("password123"), role=role)

ids = {u["username"]: u["id"] for u in db.list_users()}
db.set_user_org(ids["adminA"], org_a["id"]); db.set_user_org(ids["userA"], org_a["id"])
db.set_user_org(ids["adminB"], org_b["id"]); db.set_user_org(ids["userB"], org_b["id"])

gid = db.upsert_tak_profile("Global",    "tak-global.example.mil",    8089, 8443, True, "GLOBAL", org_id=None)
aid = db.upsert_tak_profile("Riverside", "tak-riverside.example.gov", 8089, 8443, True, "RIV",    org_id=org_a["id"])
bid = db.upsert_tak_profile("Kern",      "tak-kern.example.gov",      8089, 8443, True, "KERN",   org_id=org_b["id"])
for pid in (gid, aid, bid):
    db.set_active_tak_profile(pid)


# ── Resolution ───────────────────────────────────────────────────────────────
r.section("each org resolves to its own server")
for who, expected in [("userA", "tak-riverside.example.gov"), ("adminA", "tak-riverside.example.gov"),
                      ("userB", "tak-kern.example.gov"),      ("adminB", "tak-kern.example.gov"),
                      ("siteadmin", "tak-global.example.mil")]:
    got = client.get("/api/tak-status", cookies=login(who)).json().get("host")
    r.check(f"{who:10} -> {expected}", got == expected, f"got {got}")


# ── No fallback to the admin's server ────────────────────────────────────────
r.section("no cross-scope fallback")
db.delete_tak_profile(aid)
status = client.get("/api/tak-status", cookies=login("userA")).json()
r.check("an org with no profile is NOT given the global server",
        status.get("host") != "tak-global.example.mil", f"leaked: {status.get('host')}")
r.check("it reports not-configured", status.get("configured") is False, str(status))
r.check("and explains why", "organization" in (status.get("reason") or "").lower(),
        str(status.get("reason")))
r.check("the other org is unaffected",
        client.get("/api/tak-status", cookies=login("userB")).json().get("host")
        == "tak-kern.example.gov")

aid = db.upsert_tak_profile("Riverside", "tak-riverside.example.gov", 8089, 8443, True, "RIV",
                            org_id=org_a["id"])
db.set_active_tak_profile(aid)

status = client.get("/api/tak-status", cookies=login("orphan")).json()
r.check("a user with no org does NOT get the global server",
        status.get("host") != "tak-global.example.mil", f"leaked: {status.get('host')}")
r.check("they are told they have no organization",
        "not assigned to an organization" in (status.get("reason") or ""),
        str(status.get("reason")))


# ── Listing isolation ────────────────────────────────────────────────────────
r.section("listing isolation")
list_a = client.get("/api/admin/tak-profiles", cookies=login("adminA")).json()["profiles"]
list_b = client.get("/api/admin/tak-profiles", cookies=login("adminB")).json()["profiles"]
r.check("adminA sees only their own", [p["name"] for p in list_a] == ["Riverside"],
        str([p["name"] for p in list_a]))
r.check("adminB sees only their own", [p["name"] for p in list_b] == ["Kern"],
        str([p["name"] for p in list_b]))
r.check("neither sees the global profile", not any(p["name"] == "Global" for p in list_a))
r.check("the site admin sees all three",
        len(client.get("/api/admin/tak-profiles", cookies=login("siteadmin")).json()["profiles"]) == 3)


# ── Cross-org modification ───────────────────────────────────────────────────
r.section("cross-org modification refused")
ca = login("adminA")
r.check("cannot activate another org's profile",
        client.post(f"/api/admin/tak-profiles/{bid}/activate", cookies=ca).status_code == 403)
r.check("cannot delete another org's profile",
        client.delete(f"/api/admin/tak-profiles/{bid}", cookies=ca).status_code == 403)
r.check("cannot edit another org's profile",
        client.put(f"/api/admin/tak-profiles/{bid}", cookies=ca,
                   json={"name": "hijack", "host": "evil.example.com"}).status_code == 403)
r.check("cannot touch the global profile",
        client.put(f"/api/admin/tak-profiles/{gid}", cookies=ca,
                   json={"name": "hijack", "host": "evil.example.com"}).status_code == 403)
r.check("the target profile is intact",
        db.get_tak_profile(bid)["host"] == "tak-kern.example.gov",
        db.get_tak_profile(bid)["host"])


# ── Activation is scoped ─────────────────────────────────────────────────────
r.section("activation does not disturb other orgs")
backup = db.upsert_tak_profile("Riverside Backup", "tak-riv2.example.gov", 8089, 8443, True,
                               "RIV2", org_id=org_a["id"])
db.set_active_tak_profile(backup)
r.check("org A switched to its backup",
        client.get("/api/tak-status", cookies=login("userA")).json()["host"] == "tak-riv2.example.gov")
r.check("org B unchanged",
        client.get("/api/tak-status", cookies=login("userB")).json()["host"] == "tak-kern.example.gov")
r.check("global unchanged",
        client.get("/api/tak-status", cookies=login("siteadmin")).json()["host"] == "tak-global.example.mil")


# ── Stale token ──────────────────────────────────────────────────────────────
r.section("org moves take effect immediately")
stale_cookies = login("userA")                      # minted while in org A
r.check("before the move, resolves to org A",
        client.get("/api/tak-status", cookies=stale_cookies).json()["host"] == "tak-riv2.example.gov")
db.set_user_org(ids["userA"], org_b["id"])          # moved; their token is unchanged
after = client.get("/api/tak-status", cookies=stale_cookies).json()["host"]
r.check("an already-issued token follows the NEW org", after == "tak-kern.example.gov",
        f"got {after} — reading org from the JWT would give tak-riv2.example.gov")
db.set_user_org(ids["userA"], org_a["id"])


# ── profile_id override ──────────────────────────────────────────────────────
r.section("profile_id override cannot escape scope")
cu = login("userA")
r.check("cannot target another org's profile by id",
        client.post("/api/tak-test-point", cookies=cu,
                    json={"lat": 34.0, "lon": -118.0, "profile_id": bid}).status_code == 403)
r.check("cannot target the admin's global profile by id",
        client.post("/api/tak-test-point", cookies=cu,
                    json={"lat": 34.0, "lon": -118.0, "profile_id": gid}).status_code == 403)
r.check("a user with no org cannot target the admin's profile",
        client.post("/api/tak-test-point", cookies=login("orphan"),
                    json={"lat": 34.0, "lon": -118.0, "profile_id": gid}).status_code == 403)

sys.exit(r.report())
