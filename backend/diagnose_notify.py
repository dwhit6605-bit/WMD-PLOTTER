#!/usr/bin/env python3
"""
Diagnose Brevo email/SMS notification delivery.

Run this ON THE VPS, where the real settings live. Use the service's
virtualenv interpreter, not system python3 — the app's dependencies are
installed there (see ExecStart in the wmd-plotter systemd unit):

    cd /opt/wmd-plotter/backend && /opt/wmd-plotter/.venv/bin/python diagnose_notify.py

It reports what is configured, connects to the SMTP server and shows the real
handshake, and optionally sends a live test message. Secrets are never printed —
only whether they are set and how long they are.

    --send        actually send a test email to the configured Notify TO
    --send-sms    actually send a test SMS to the configured Notify Phone
"""

import argparse
import os
import smtplib
import ssl
import sys

sys.path.insert(0, "/opt/wmd-plotter/backend")
sys.path.insert(0, ".")

try:
    from db import get_setting
    import email_notify as en
except ModuleNotFoundError as exc:
    # Almost always means this was run with system python3 instead of the
    # service's virtualenv, where the app's dependencies actually live.
    venv = "/opt/wmd-plotter/.venv/bin/python"
    print(f"\nMissing dependency: {exc.name}\n")
    if os.path.exists(venv):
        print("You are running system python3, which does not have the app's")
        print("dependencies. Use the service's interpreter instead:\n")
        print(f"    cd /opt/wmd-plotter/backend && {venv} diagnose_notify.py\n")
    else:
        print("Run this with the same interpreter the service uses. Find it with:\n")
        print("    systemctl show -p ExecStart --value wmd-plotter\n")
    sys.exit(1)
except Exception as exc:  # pragma: no cover
    print(f"Could not import the app modules: {exc}")
    print("Run this from the backend directory (cd /opt/wmd-plotter/backend).")
    sys.exit(1)


G, R, Y, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[0m"
ok   = lambda s: print(f"  {G}OK{X}    {s}")
bad  = lambda s: print(f"  {R}FAIL{X}  {s}")
warn = lambda s: print(f"  {Y}WARN{X}  {s}")
info = lambda s: print(f"        {s}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="send a live test email")
    ap.add_argument("--send-sms", action="store_true", help="send a live test SMS")
    args = ap.parse_args()

    print(f"\n{B}WMD Plotter — notification diagnostics{X}\n")

    # ── 1. Configuration ────────────────────────────────────────────────────
    print(f"{B}1. Configuration{X}")
    cfg = en._get_smtp_config()

    for label, key in (("SMTP host", "host"), ("SMTP port", "port"),
                       ("SMTP username", "username"), ("From address", "notify_from"),
                       ("Notify TO", "notify_to")):
        val = cfg.get(key)
        if not val:
            bad(f"{label:16} <not set>")
        elif key in ("notify_from", "notify_to") and "@" not in str(val):
            # A hostname here (e.g. the SMTP relay) is rejected at MAIL FROM
            # with a 501 — surface it before a send is even attempted.
            bad(f"{label:16} {val}")
            info(f"{'':16} ^ not an email address — this field is a mailbox, not a host")
        else:
            ok(f"{label:16} {val}")

    pw = cfg.get("password") or ""
    (ok if pw else bad)(f"{'SMTP password':16} {'<set, %d chars>' % len(pw) if pw else '<not set>'}")

    problem = en.smtp_problem(cfg)
    print()
    if problem:
        bad(problem)
        info("Nothing will be sent until these are filled in.")
    else:
        ok("All required email fields are present.")

    if not cfg.get("notify_to"):
        print()
        bad("Notify TO is empty — access-request alerts have nowhere to go.")
        info("This alone stops enrollment notifications, even if everything else is right.")

    # ── 2. Brevo-specific sanity checks ────────────────────────────────────
    print(f"\n{B}2. Brevo specifics{X}")
    host = (cfg.get("host") or "").lower()
    port = str(cfg.get("port") or "")

    if "brevo" in host or "sendinblue" in host:
        ok(f"Host looks like Brevo ({cfg['host']})")
    elif host:
        warn(f"Host is {cfg['host']} — Brevo's relay is smtp-relay.brevo.com")

    if port == "587":
        ok("Port 587 (STARTTLS) — the usual choice")
    elif port == "465":
        ok("Port 465 (implicit TLS) — supported")
    elif port:
        warn(f"Port {port} is unusual for Brevo; use 587 or 465")

    user = cfg.get("username") or ""
    if user and "@" not in user:
        warn("SMTP username is normally your Brevo LOGIN EMAIL, not an account name")
    if user and cfg.get("notify_from") and user == cfg["notify_from"]:
        info("Username equals the From address — fine only if that IS your Brevo login.")
    if pw and len(pw) < 20:
        warn("Password looks short for a Brevo SMTP key — make sure it is the "
             "SMTP key (Brevo > SMTP & API > SMTP), not your account password.")

    # ── 3. Live connection ──────────────────────────────────────────────────
    print(f"\n{B}3. SMTP connection{X}")
    if problem:
        warn("Skipped — configuration incomplete.")
    else:
        try:
            p = int(cfg["port"])
            if p == 465:
                srv = smtplib.SMTP_SSL(cfg["host"], p, timeout=20,
                                       context=ssl.create_default_context())
            else:
                srv = smtplib.SMTP(cfg["host"], p, timeout=20)
            with srv as server:
                server.ehlo()
                ok(f"Connected to {cfg['host']}:{p}")
                if p != 465:
                    server.starttls()
                    server.ehlo()
                    ok("STARTTLS negotiated")
                try:
                    server.login(cfg["username"], cfg["password"])
                    ok("Authentication accepted")
                except smtplib.SMTPAuthenticationError as e:
                    bad(f"Authentication REJECTED — {e.smtp_code} {e.smtp_error}")
                    info("Use the Brevo SMTP key as the password and your Brevo")
                    info("login email as the username. Account password will not work.")
                    return 1
        except Exception as e:
            bad(f"Could not connect: {type(e).__name__}: {e}")
            info("Check the VPS can reach the host on that port (outbound 587/465).")
            return 1

    # ── 4. Last recorded outcome ───────────────────────────────────────────
    print(f"\n{B}4. Last delivery outcome{X}")
    last_err = get_setting("notify_last_error") or ""
    last_ok  = get_setting("notify_last_ok") or ""
    if last_err:
        bad(f"Last error: {last_err}")
    if last_ok:
        ok(f"Last success: {last_ok}")
    if not last_err and not last_ok:
        info("Nothing recorded yet — no notification has been attempted since")
        info("this tracking was added. Submit an access request to generate one.")

    # ── 5. Optional live sends ─────────────────────────────────────────────
    if args.send:
        print(f"\n{B}5. Live test email{X}")
        to = (cfg.get("notify_to") or "").split(",")[0].strip()
        if not to:
            bad("No Notify TO configured.")
        else:
            en._send_smtp([to], "[WMD Plotter] Diagnostic test",
                          "<p>Diagnostic test from diagnose_notify.py</p>", cfg)
            err = get_setting("notify_last_error") or ""
            if err:
                bad(f"Send failed: {err}")
            else:
                ok(f"Sent to {to} — check the inbox (and spam).")

    if args.send_sms:
        print(f"\n{B}6. Live test SMS{X}")
        key, phone = en._get_sms_config()
        if not key:
            bad("No Brevo SMS API key configured.")
        elif not phone:
            bad("No Notify Phone configured.")
        else:
            if not phone.startswith("+"):
                warn(f"Phone {phone} is not E.164 — Brevo wants e.g. +15551234567")
            en._send_sms({"sender": "WMDPlotter", "recipient": phone,
                          "content": "[WMD Plotter] Diagnostic test SMS."}, key)
            err = get_setting("notify_last_error") or ""
            if err:
                bad(f"Send failed: {err}")
            else:
                ok(f"Sent to {phone}")

    print()
    if not args.send and not args.send_sms:
        info("Re-run with --send (and/or --send-sms) to attempt a real delivery.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
