"""
Account approval.

Approving an account emails the user at the address they enrolled with, and the
endpoint reports whether anyone was actually contacted — approving someone with
no email on file, or while SMTP is broken, must not look like success.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (Results, FakeSMTP, isolated_db, clear_env, configure_smtp,
                     patch_smtp_plaintext, body_text)

PORT = 2527

isolated_db()
import db
import email_notify
from fastapi.testclient import TestClient

smtp = FakeSMTP(PORT).start()
configure_smtp(db, PORT)
patch_smtp_plaintext(email_notify)

import main
clear_env()
from auth import hash_password

client = TestClient(main.app)
r = Results("Account approval")

db.create_user("admin", hash_password("password123"), role="admin")
admin_cookies = client.post("/auth/login",
                            json={"username": "admin", "password": "password123"}).cookies


# ── Approving a user who has an email ────────────────────────────────────────
r.section("approval notifies the user")
client.post("/auth/request-access", json={
    "username": "medic7", "password": "password123", "display_name": "Dana Cruz",
    "access_reason": "County HazMat", "email": "dana@county.gov",
})
smtp.wait()
smtp.settle()          # drop the admin alert; we want the approval mail

uid = [u["id"] for u in db.list_users() if u["username"] == "medic7"][0]
resp = client.post(f"/api/admin/users/{uid}/approve", cookies=admin_cookies)
r.check("approve returns 200", resp.status_code == 200, f"{resp.status_code}: {resp.text[:120]}")

payload = resp.json()
r.check("reports that mail was sent", payload.get("email_sent") is True, str(payload))
r.check("reports the destination", payload.get("email") == "dana@county.gov", str(payload))
r.check("approval email is delivered", smtp.wait(), "nothing reached SMTP")

if smtp.last:
    r.check("sent to the enrollment address", "dana@county.gov" in smtp.last["to"],
            str(smtp.last["to"]))
    text = body_text(smtp.last["raw"])
    r.check("addresses them by name", "Dana Cruz" in text)
    r.check("includes their username", "medic7" in text)
    r.check("sign-in link uses the live domain",
            "https://wmd.whitwerx.net/login" in text,
            [p for p in text.split('"') if "whitwerx" in p][:2])
    r.check("no dead wmdplotter domain", "wmdplotter.whitwerx.net" not in text)

r.check("the account is now active",
        [u for u in db.list_users() if u["username"] == "medic7"][0]["status"] == "active")


# ── Approving a user with no email is reported honestly ──────────────────────
r.section("nothing silently unnotified")
db.create_user("noemail", hash_password("password123"), role="user", status="pending")
uid2 = [u["id"] for u in db.list_users() if u["username"] == "noemail"][0]
smtp.settle()

resp = client.post(f"/api/admin/users/{uid2}/approve", cookies=admin_cookies)
payload = resp.json()
r.check("approval still succeeds", resp.status_code == 200 and payload.get("ok"))
r.check("but reports that nobody was emailed", payload.get("email_sent") is False, str(payload))
r.check("and no phantom email is sent", len(smtp.received) == 0, f"{len(smtp.received)} sent")
r.check("the skip is recorded for the admin",
        "no email on file" in (db.get_setting("notify_last_error") or ""),
        repr(db.get_setting("notify_last_error")))

sys.exit(r.report())
