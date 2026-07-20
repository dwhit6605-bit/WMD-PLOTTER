"""
Transactional notifications for WMD Plotter.

EMAIL — sent via SMTP (Brevo relay, SendGrid, Gmail App Passwords, etc.)
  DB settings: smtp_host, smtp_port, smtp_username, smtp_password,
               email_notify_to (comma-separated), email_notify_from

SMS — sent via Brevo transactional SMS REST API
  DB settings: sms_brevo_key, sms_notify_phone

All settings are configurable from Admin → User Management.
"""

import os
import logging
import smtplib
import threading
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BREVO_SMS_URL = "https://api.brevo.com/v3/transactionalSMS/sms"


# ── Config readers ────────────────────────────────────────────────────────────

def _get_smtp_config() -> dict:
    try:
        from db import get_setting
        return {
            "host":        get_setting("smtp_host")     or os.environ.get("SMTP_HOST", ""),
            "port":        int(get_setting("smtp_port") or os.environ.get("SMTP_PORT", "587")),
            "username":    get_setting("smtp_username") or os.environ.get("SMTP_USERNAME", ""),
            "password":    get_setting("smtp_password") or os.environ.get("SMTP_PASSWORD", ""),
            "notify_to":   get_setting("email_notify_to")  or os.environ.get("NOTIFY_EMAIL", ""),
            "notify_from": get_setting("email_notify_from") or os.environ.get("NOTIFY_FROM", ""),
        }
    except Exception:
        return {
            "host":        os.environ.get("SMTP_HOST", ""),
            "port":        int(os.environ.get("SMTP_PORT", "587")),
            "username":    os.environ.get("SMTP_USERNAME", ""),
            "password":    os.environ.get("SMTP_PASSWORD", ""),
            "notify_to":   os.environ.get("NOTIFY_EMAIL", ""),
            "notify_from": os.environ.get("NOTIFY_FROM", ""),
        }


def _get_sms_config() -> tuple:
    """Return (api_key, notify_phone)."""
    try:
        from db import get_setting
        api_key = get_setting("sms_brevo_key") or os.environ.get("BREVO_API_KEY", "")
        # NOTIFY_PHONE fallback added for symmetry with the API key above: it was
        # DB-only, so setting BREVO_API_KEY in .env looked like a complete SMS
        # setup while the destination number was silently empty.
        phone   = get_setting("sms_notify_phone") or os.environ.get("NOTIFY_PHONE", "")
    except Exception:
        api_key = os.environ.get("BREVO_API_KEY", "")
        phone   = os.environ.get("NOTIFY_PHONE", "")
    return api_key, phone


def _site_url() -> str:
    """Public base URL for links in outgoing messages.

    Was hardcoded to wmdplotter.whitwerx.net, which is not the deployed domain —
    every link in every notification was dead. Note this is deliberately NOT
    WMD_PUBLIC_URL: that one is http:// on purpose so ATAK (which does not trust
    Let's Encrypt) can fetch data packages, and we want https:// in email.
    """
    try:
        from db import get_setting
        configured = get_setting("site_url")
    except Exception:
        configured = None
    return (configured or os.environ.get("PUBLIC_BASE_URL") or "https://wmd.whitwerx.net").rstrip("/")


# ── Delivery outcome tracking ────────────────────────────────────────────────
# Every send is fire-and-forget on a daemon thread, so a failure never reaches
# the caller — the enrollment endpoint returns 201 whether or not the admin was
# actually notified. Persisting the last outcome is what makes "it's not
# working" diagnosable from the admin UI instead of only from journalctl.

_ERR_KEY = "notify_last_error"
_OK_KEY  = "notify_last_ok"


def _record(ok: bool, detail: str) -> None:
    try:
        from db import set_setting
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if ok:
            set_setting(_OK_KEY, f"{stamp} — {detail}")
            set_setting(_ERR_KEY, "")
        else:
            set_setting(_ERR_KEY, f"{stamp} — {detail}")
    except Exception:
        pass


def smtp_problem(cfg: Optional[dict] = None) -> Optional[str]:
    """Why SMTP cannot send, or None if the config looks complete.

    Shared by the test button and the real notification path so the two can no
    longer disagree about what counts as configured — previously the test
    checked notify_from while the real path checked notify_to, so a passing test
    did not imply a working enrollment email.
    """
    cfg = cfg or _get_smtp_config()
    missing = [label for label, key in (
        ("SMTP host",            "host"),
        ("SMTP username",        "username"),
        ("SMTP password/key",    "password"),
        ("From address",         "notify_from"),
    ) if not cfg.get(key)]
    return ("Not configured: " + ", ".join(missing)) if missing else None


# ── SMTP send ─────────────────────────────────────────────────────────────────

def _send_smtp(to_addresses: list, subject: str, html: str, cfg: dict) -> None:
    """Blocking SMTP send — always run in a daemon thread."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg["notify_from"]
        msg["To"]      = ", ".join(to_addresses)
        msg.attach(MIMEText(html, "html", "utf-8"))

        port = int(cfg["port"])
        # Port 465 is implicit TLS — the connection is encrypted from the first
        # byte, so STARTTLS is a protocol error there. Only 587 (and 25) begin
        # in the clear and upgrade. Previously every port took the STARTTLS
        # path, so configuring Brevo's 465 endpoint could never work.
        if port == 465:
            server_ctx = smtplib.SMTP_SSL(cfg["host"], port, timeout=20)
        else:
            server_ctx = smtplib.SMTP(cfg["host"], port, timeout=20)

        with server_ctx as server:
            server.ehlo()
            if port != 465:
                server.starttls()
                server.ehlo()
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["notify_from"], to_addresses, msg.as_string())

        _record(True, f"email to {', '.join(to_addresses)}")
        logger.info("email_notify: sent '%s' to %s", subject, ", ".join(to_addresses))

    except smtplib.SMTPAuthenticationError as exc:
        # Overwhelmingly the most common Brevo failure: the SMTP login is the
        # Brevo *SMTP key*, not the account password, and the username is the
        # login email — not the sender address.
        _record(False, f"SMTP auth rejected ({exc.smtp_code}). Use your Brevo SMTP key "
                       f"as the password, and your Brevo login email as the username.")
        logger.warning("email_notify: SMTP auth failed — %s", exc)
    except smtplib.SMTPSenderRefused as exc:
        _record(False, f"Sender {cfg['notify_from']} refused ({exc.smtp_code}). "
                       f"Verify this address as a sender in Brevo first.")
        logger.warning("email_notify: sender refused — %s", exc)
    except smtplib.SMTPRecipientsRefused as exc:
        _record(False, f"Recipient refused: {exc.recipients}")
        logger.warning("email_notify: recipients refused — %s", exc)
    except Exception as exc:
        _record(False, f"{type(exc).__name__}: {exc}")
        logger.warning("email_notify: SMTP send failed — %s", exc)


# ── SMS send ──────────────────────────────────────────────────────────────────

def _send_sms(payload: dict, api_key: str) -> None:
    """Blocking Brevo SMS call — always run in a daemon thread."""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                BREVO_SMS_URL,
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code in (200, 201, 202):
            _record(True, f"SMS to {payload.get('recipient')}")
        else:
            # Brevo's body explains the reason (unverified sender, no SMS
            # credits, bad number format — it wants E.164 like +15551234567).
            _record(False, f"Brevo SMS HTTP {r.status_code}: {r.text[:180]}")
            logger.warning("Brevo SMS returned %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        _record(False, f"SMS {type(exc).__name__}: {exc}")
        logger.warning("email_notify: SMS send failed — %s", exc)


# ── Public API ────────────────────────────────────────────────────────────────

def send_test(to_email: str) -> bool:
    """Send a test email. Returns True if dispatched."""
    cfg = _get_smtp_config()
    if smtp_problem(cfg):
        return False

    html = """
<div style="font-family:'Courier New',monospace;background:#0d1117;color:#c9d1d9;padding:24px">
  <div style="max-width:480px;margin:0 auto;background:#161b22;border:1px solid #21262d;
              border-radius:10px;overflow:hidden">
    <div style="background:#0a0f14;padding:18px 24px;border-bottom:1px solid #21262d">
      <h1 style="margin:0;font-size:15px;font-weight:800;color:#00ff88">
        &#10003; Email Configuration Working
      </h1>
      <p style="margin:4px 0 0;font-size:11px;color:#8b949e">WMD Plotter &middot; WHITWERX</p>
    </div>
    <div style="padding:24px;font-size:13px;line-height:1.7">
      Your SMTP settings are configured correctly.<br>
      Access request notifications and approval emails will be delivered.
    </div>
  </div>
</div>"""

    t = threading.Thread(
        target=_send_smtp,
        args=([to_email], "[WMD Plotter] Test Email — Configuration OK", html, cfg),
        daemon=True,
    )
    t.start()
    return True


def send_test_sms(to_phone: str) -> bool:
    """Send a test SMS. Returns True if dispatched."""
    api_key, _ = _get_sms_config()
    if not api_key or not to_phone:
        return False
    payload = {
        "sender":    "WMDPlotter",
        "recipient": to_phone,
        "content":   "[WMD Plotter] Test SMS — configuration OK. Access request alerts will be sent to this number.",
    }
    t = threading.Thread(target=_send_sms, args=(payload, api_key), daemon=True)
    t.start()
    return True


def notify_access_approved(
    display_name: str,
    username: str,
    to_email: Optional[str],
) -> None:
    """Fire-and-forget email to the requester when an admin approves their account."""
    if not to_email:
        return
    cfg = _get_smtp_config()
    problem = smtp_problem(cfg)
    if problem:
        _record(False, f"approval email to {to_email} not sent — {problem}")
        return

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/>
<style>
  body{{font-family:'Courier New',monospace;background:#0d1117;color:#c9d1d9;margin:0;padding:24px}}
  .card{{max-width:480px;margin:0 auto;background:#161b22;border:1px solid #21262d;border-radius:10px;overflow:hidden}}
  .hdr{{background:#0a0f14;padding:18px 24px;border-bottom:1px solid #21262d}}
  .hdr h1{{margin:0;font-size:15px;font-weight:800;letter-spacing:.08em;color:#00ff88}}
  .hdr p{{margin:4px 0 0;font-size:11px;color:#8b949e}}
  .body{{padding:24px}}
  .body p{{font-size:13px;color:#c9d1d9;line-height:1.7;margin:0 0 16px}}
  .btn{{display:inline-block;padding:12px 28px;background:#00ff88;color:#000;
        font-family:'Courier New',monospace;font-size:12px;font-weight:700;
        letter-spacing:1px;text-decoration:none;border-radius:7px;text-transform:uppercase}}
  .footer{{font-size:10px;color:#8b949e;margin-top:20px;padding-top:14px;border-top:1px solid #21262d}}
</style>
</head>
<body>
<div class="card">
  <div class="hdr">
    <h1>&#10003; Access Approved &mdash; WMD Plotter</h1>
    <p>WHITWERX &middot; Model Display (WMD) &middot; CBRN Planning System</p>
  </div>
  <div class="body">
    <p>Hi {display_name},</p>
    <p>Your access request has been reviewed and <strong style="color:#00ff88">approved</strong>.
       You can now sign in using your username and the password you created when you submitted your request.</p>
    <p><strong>Username:</strong> {username}</p>
    <a class="btn" href="{_site_url()}/login">Sign In &rarr;</a>
    <div class="footer">
      WMD Plotter is restricted to authorized personnel only.<br>
      If you did not request this account, contact Dave@WHITWERX.net.
    </div>
  </div>
</div>
</body>
</html>"""

    t = threading.Thread(
        target=_send_smtp,
        args=([to_email], "Your WMD Plotter access has been approved", html, cfg),
        daemon=True,
    )
    t.start()


def notify_access_request(
    display_name: str,
    username: str,
    access_reason: str,
    email: Optional[str],
) -> None:
    """Fire-and-forget notification to admin(s) when a new access request is submitted."""
    cfg = _get_smtp_config()
    problem = smtp_problem(cfg)
    if problem:
        _record(False, f"access request from @{username} — {problem}")
        logger.warning("email_notify: access-request email skipped — %s", problem)
        return
    if not cfg["notify_to"]:
        _record(False, f"access request from @{username} — no recipient set (Notify TO is empty)")
        logger.warning("email_notify: access-request email skipped — no notify_to")
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    email_line = email or "<em>not provided</em>"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/>
<style>
  body{{font-family:'Courier New',monospace;background:#0d1117;color:#c9d1d9;margin:0;padding:24px}}
  .card{{max-width:520px;margin:0 auto;background:#161b22;border:1px solid #21262d;border-radius:10px;overflow:hidden}}
  .hdr{{background:#0a0f14;padding:18px 24px;border-bottom:1px solid #21262d}}
  .hdr h1{{margin:0;font-size:15px;font-weight:800;letter-spacing:.08em;color:#c9d1d9}}
  .hdr p{{margin:4px 0 0;font-size:11px;color:#8b949e}}
  .body{{padding:24px}}
  .row{{margin-bottom:14px}}
  .lbl{{font-size:10px;font-weight:700;letter-spacing:.08em;color:#8b949e;text-transform:uppercase;margin-bottom:4px}}
  .val{{font-size:13px;color:#c9d1d9;line-height:1.5}}
  .reason{{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:10px 12px;font-size:12px;color:#c9d1d9;line-height:1.6}}
  .btn{{display:inline-block;margin-top:6px;padding:11px 24px;background:#00ff88;color:#000;
        font-family:'Courier New',monospace;font-size:12px;font-weight:700;letter-spacing:1px;
        text-decoration:none;border-radius:7px;text-transform:uppercase}}
  .ts{{font-size:10px;color:#8b949e;margin-top:20px;padding-top:14px;border-top:1px solid #21262d}}
</style>
</head>
<body>
<div class="card">
  <div class="hdr">
    <h1>&#9888; New Access Request &mdash; WMD Plotter</h1>
    <p>A user has requested access and is awaiting your approval.</p>
  </div>
  <div class="body">
    <div class="row"><div class="lbl">Full Name</div><div class="val">{display_name}</div></div>
    <div class="row"><div class="lbl">Username</div><div class="val">@{username}</div></div>
    <div class="row"><div class="lbl">Email</div><div class="val">{email_line}</div></div>
    <div class="row">
      <div class="lbl">Agency / Reason for Access</div>
      <div class="reason">{access_reason}</div>
    </div>
    <div class="row" style="margin-top:20px">
      <a class="btn" href="{_site_url()}/admin/users">Review in Admin Panel &rarr;</a>
    </div>
    <div class="ts">Submitted {ts}</div>
  </div>
</div>
</body>
</html>"""

    notify_to_list = [a.strip() for a in cfg["notify_to"].split(",") if a.strip()]
    t = threading.Thread(
        target=_send_smtp,
        args=(notify_to_list, f"[WMD Plotter] Access Request — {display_name}", html, cfg),
        daemon=True,
    )
    t.start()


def notify_access_request_sms(
    display_name: str,
    username: str,
    access_reason: str,
    to_phone: Optional[str],
) -> None:
    """Fire-and-forget SMS to admin when a new access request is submitted."""
    api_key, fallback_phone = _get_sms_config()
    to_phone = to_phone or fallback_phone
    if not to_phone:
        _record(False, f"access request from @{username} — SMS skipped, no notify phone set")
        logger.warning("email_notify: SMS skipped — no notify phone configured")
        return
    if not api_key:
        _record(False, f"access request from @{username} — SMS skipped, no Brevo API key set")
        logger.warning("email_notify: SMS skipped — no Brevo API key configured")
        return
    host = _site_url().split("://", 1)[-1]
    content = (
        f"[WMD Plotter] New access request from {display_name} (@{username}). "
        f"Review at {host}/admin/users"
    )
    payload = {
        "sender":    "WMDPlotter",
        "recipient": to_phone,
        "content":   content,
    }
    t = threading.Thread(target=_send_sms, args=(payload, api_key), daemon=True)
    t.start()
