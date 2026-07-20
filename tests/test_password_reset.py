"""
Self-service password reset.

The flow itself, plus the properties that make it safe to expose without a
session: no account enumeration, only the token hash stored, single use, short
lived, superseded by newer requests, and rate limited.
"""

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import (Results, FakeSMTP, isolated_db, clear_env, configure_smtp,
                     patch_smtp_plaintext, body_text, find_link)

PORT = 2528

DB_PATH = isolated_db()
import db
import email_notify
from fastapi.testclient import TestClient

smtp = FakeSMTP(PORT).start()
configure_smtp(db, PORT)
patch_smtp_plaintext(email_notify)

import main
clear_env()
from auth import hash_password, verify_password

client = TestClient(main.app)
anon = TestClient(main.app)
r = Results("Password reset")

db.create_user("dana", hash_password("oldpassword1"), role="user", email="dana@county.gov")
db.create_user("noemail", hash_password("oldpassword1"), role="user")

TOKEN_RE = r"/reset-password\?token=([A-Za-z0-9_\-]+)"


def reset_state(pause=0.6):
    """Let in-flight mail land, clear the inbox, and reset the rate limiter.

    The limiter is per client address and would otherwise be exhausted partway
    through the suite, making later sections fail for the wrong reason.
    """
    smtp.settle(pause)
    main._reset_hits.clear()


def request_link(identifier="dana"):
    reset_state()
    client.post("/auth/forgot-password", json={"identifier": identifier})
    if not smtp.wait():
        return None
    return find_link(smtp.last["raw"], TOKEN_RE)


# ── Happy path ───────────────────────────────────────────────────────────────
r.section("happy path")
reset_state()
resp = client.post("/auth/forgot-password", json={"identifier": "dana"})
r.check("request is accepted", resp.status_code == 200, f"{resp.status_code}")
r.check("an email is dispatched", smtp.wait(), "no mail")
r.check("sent to the account's address", smtp.last["to"] == ["dana@county.gov"],
        str(smtp.last["to"]))

token = find_link(smtp.last["raw"], TOKEN_RE)
r.check("the email carries a reset link", token is not None, body_text(smtp.last["raw"])[:200])
r.check("the link uses the configured site url",
        "https://wmd.whitwerx.net/reset-password" in body_text(smtp.last["raw"]))
r.check("the token validates before use",
        client.get(f"/auth/reset-password/check?token={token}").json()["valid"] is True)

resp = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnewpass9"})
r.check("the reset succeeds", resp.status_code == 200, f"{resp.status_code}: {resp.text[:120]}")

row = db.get_user_by_username("dana")
r.check("the new password works", verify_password("brandnewpass9", row["password_hash"]))
r.check("the old password does not", not verify_password("oldpassword1", row["password_hash"]))
r.check("the user can sign in with it",
        client.post("/auth/login",
                    json={"username": "dana", "password": "brandnewpass9"}).status_code == 200)


# ── Single use ───────────────────────────────────────────────────────────────
r.section("single use")
resp = client.post("/auth/reset-password", json={"token": token, "new_password": "attacker123"})
r.check("the same token cannot be replayed", resp.status_code == 400, f"{resp.status_code}")
r.check("it no longer validates",
        client.get(f"/auth/reset-password/check?token={token}").json()["valid"] is False)
r.check("the password is unchanged by the replay",
        verify_password("brandnewpass9", db.get_user_by_username("dana")["password_hash"]))


# ── Storage ──────────────────────────────────────────────────────────────────
r.section("only the hash is stored")
rows = sqlite3.connect(DB_PATH).execute("SELECT token_hash FROM password_resets").fetchall()
r.check("the raw token is never stored", all(token not in row[0] for row in rows),
        "token found in the database")
r.check("stored values are sha256 digests", all(len(row[0]) == 64 for row in rows), str(rows[:1]))


# ── Enumeration ──────────────────────────────────────────────────────────────
r.section("no account enumeration")
real    = client.post("/auth/forgot-password", json={"identifier": "dana"})
missing = client.post("/auth/forgot-password", json={"identifier": "no-such-user-xyz"})
noemail = client.post("/auth/forgot-password", json={"identifier": "noemail"})
r.check("identical status for real, unknown and emailless accounts",
        real.status_code == missing.status_code == noemail.status_code == 200)
r.check("identical body too", real.text == missing.text == noemail.text,
        f"{real.text} | {missing.text} | {noemail.text}")

reset_state()
client.post("/auth/forgot-password", json={"identifier": "noemail"})
time.sleep(0.6)
r.check("no mail for an account with no email address", len(smtp.received) == 0,
        f"{len(smtp.received)} sent")

reset_state()
client.post("/auth/forgot-password", json={"identifier": "DANA@COUNTY.GOV"})
r.check("can request by email address, case-insensitively", smtp.wait(), "no mail")


# ── Supersede ────────────────────────────────────────────────────────────────
r.section("a newer link retires the older one")
first = request_link()
second = request_link()
r.check("two requests give different tokens", first != second)
r.check("the older link is retired",
        client.get(f"/auth/reset-password/check?token={first}").json()["valid"] is False)
r.check("the newest link still works",
        client.get(f"/auth/reset-password/check?token={second}").json()["valid"] is True)


# ── Expiry and bad input ─────────────────────────────────────────────────────
r.section("expiry and malformed input")
original_ttl = main._RESET_TTL_MINUTES
main._RESET_TTL_MINUTES = -1
stale = request_link()
r.check("an expired link is refused",
        client.post("/auth/reset-password",
                    json={"token": stale, "new_password": "whatever12"}).status_code == 400)
main._RESET_TTL_MINUTES = original_ttl

for bad in ["", "x", "../../etc/passwd", "a" * 600]:
    resp = client.post("/auth/reset-password", json={"token": bad, "new_password": "whatever12"})
    label = repr(bad[:12]) if bad else "empty"
    r.check(f"garbage token rejected ({label})", resp.status_code in (400, 422), f"{resp.status_code}")

r.check("a too-short new password is rejected",
        client.post("/auth/reset-password",
                    json={"token": second, "new_password": "short"}).status_code == 422)


# ── Rate limiting ────────────────────────────────────────────────────────────
r.section("rate limiting")
reset_state()
for _ in range(main._RESET_RATE_MAX + 4):
    client.post("/auth/forgot-password", json={"identifier": "dana"})
time.sleep(0.6)
r.check("mail is rate limited per client address",
        len(smtp.received) <= main._RESET_RATE_MAX,
        f"{len(smtp.received)} emails for {main._RESET_RATE_MAX + 4} requests")


# ── Reachable without a session ──────────────────────────────────────────────
r.section("works without a session")
r.check("the reset page loads", anon.get("/reset-password").status_code == 200)
r.check("the request endpoint is reachable",
        anon.post("/auth/forgot-password", json={"identifier": "x"}).status_code == 200)
r.check("the login page links to it", "/reset-password" in anon.get("/login").text)

sys.exit(r.report())
