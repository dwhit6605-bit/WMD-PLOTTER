"""
Access-request notifications (Brevo/SMTP).

Regression cover for a set of failures that made enrollment alerts vanish
silently: a From address that was not an email address, a dead link domain, a
test button that validated different fields than the real path, and errors that
only ever reached the log.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (Results, FakeSMTP, isolated_db, clear_env, configure_smtp,
                     patch_smtp_plaintext, body_text)

PORT = 2526

isolated_db()
import db
import email_notify
from fastapi.testclient import TestClient

smtp = FakeSMTP(PORT).start()
configure_smtp(db, PORT)
patch_smtp_plaintext(email_notify)

import main
clear_env()
client = TestClient(main.app)
r = Results("Notifications — access request delivery")


# ── Delivery ─────────────────────────────────────────────────────────────────
r.section("delivery")
smtp.settle()
resp = client.post("/auth/request-access", json={
    "username": "newmedic", "password": "password123",
    "display_name": "Sam Rivera", "access_reason": "County HazMat Team",
    "email": "sam@county.gov",
})
r.check("enrollment endpoint returns 201", resp.status_code == 201,
        f"{resp.status_code}: {resp.text[:120]}")
r.check("notification email is actually delivered", smtp.wait(), "nothing reached SMTP")

if smtp.last:
    text = body_text(smtp.last["raw"])
    r.check("names the requester", "Sam Rivera" in text, text[:150])
    r.check("includes the access reason", "County HazMat" in text)
    r.check("link points at the configured site",
            "https://wmd.whitwerx.net/admin/users" in text,
            [p for p in text.split('"') if "whitwerx" in p][:2])
    r.check("no dead wmdplotter.whitwerx.net domain", "wmdplotter.whitwerx.net" not in text)

r.check("success is recorded for the admin UI", bool(db.get_setting("notify_last_ok")),
        repr(db.get_setting("notify_last_ok")))
r.check("no error recorded on success", not db.get_setting("notify_last_error"))


# ── Failures are visible ─────────────────────────────────────────────────────
r.section("failure visibility")
db.set_setting("smtp_port", "9")          # nothing listening
smtp.settle()
client.post("/auth/request-access", json={
    "username": "newmedic2", "password": "password123",
    "display_name": "Alex Kim", "access_reason": "Test",
})
for _ in range(50):
    if db.get_setting("notify_last_error"):
        break
    time.sleep(0.1)
err = db.get_setting("notify_last_error") or ""
r.check("a delivery failure is recorded, not swallowed", bool(err), repr(err))
db.set_setting("smtp_port", str(PORT))


# ── Config validation ────────────────────────────────────────────────────────
r.section("configuration validation")
db.set_setting("email_notify_from", "")
problem = email_notify.smtp_problem()
r.check("missing From is reported", bool(problem and "From" in problem), str(problem))
r.check("test button agrees with the real path",
        email_notify.send_test("x@y.com") is False and problem is not None)

# The live bug: the SMTP relay hostname pasted into the From field.
db.set_setting("email_notify_from", "smtp-relay.brevo.com")
problem = email_notify.smtp_problem()
r.check("a hostname in the From field is rejected before sending",
        bool(problem and "not an email address" in problem), str(problem))
r.check("and the test button refuses too", email_notify.send_test("x@y.com") is False)

db.set_setting("email_notify_from", "noreply@whitwerx.net")
r.check("a valid From clears the problem", email_notify.smtp_problem() is None,
        str(email_notify.smtp_problem()))

sys.exit(r.report())
