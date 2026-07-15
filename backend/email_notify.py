"""
Brevo (formerly Sendinblue) transactional email notifications.

Config is read from the settings table at send time (admin-configurable via
the admin panel). Falls back to env vars if DB values are not set.

  email_brevo_key   — Brevo API key
  email_notify_to   — address that receives admin notifications
  email_notify_from — verified sender address in your Brevo account
"""

import os
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Env-var fallbacks (still honoured if DB values aren't set)
_ENV_API_KEY     = os.environ.get("BREVO_API_KEY", "")
_ENV_NOTIFY_TO   = os.environ.get("NOTIFY_EMAIL", "")
_ENV_NOTIFY_FROM = os.environ.get("NOTIFY_FROM", "")

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def _get_config() -> tuple:
    """Return (api_key, notify_to, notify_from) from DB, falling back to env vars."""
    try:
        from db import get_setting
        api_key     = get_setting("email_brevo_key")  or _ENV_API_KEY
        notify_to   = get_setting("email_notify_to")  or _ENV_NOTIFY_TO
        notify_from = get_setting("email_notify_from") or _ENV_NOTIFY_FROM
    except Exception:
        api_key, notify_to, notify_from = _ENV_API_KEY, _ENV_NOTIFY_TO, _ENV_NOTIFY_FROM
    return api_key, notify_to, notify_from


def _send(payload: dict, api_key: str) -> None:
    """Blocking Brevo call — always run in a daemon thread."""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                BREVO_SEND_URL,
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code not in (200, 201, 202):
            logger.warning("Brevo API returned %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("email_notify: send failed — %s", exc)


def send_test(to_email: str) -> bool:
    """Send a test email. Returns True if dispatched (not necessarily delivered)."""
    api_key, _, notify_from = _get_config()
    if not api_key or not notify_from:
        return False

    payload = {
        "sender":  {"name": "WMD Plotter", "email": notify_from},
        "to":      [{"email": to_email}],
        "subject": "[WMD Plotter] Test Email — Configuration OK",
        "htmlContent": """
<div style="font-family:'Courier New',monospace;background:#0d1117;color:#c9d1d9;padding:24px">
  <div style="max-width:480px;margin:0 auto;background:#161b22;border:1px solid #21262d;
              border-radius:10px;overflow:hidden">
    <div style="background:#0a0f14;padding:18px 24px;border-bottom:1px solid #21262d">
      <h1 style="margin:0;font-size:15px;font-weight:800;color:#00ff88">
        ✓ Email Configuration Working
      </h1>
      <p style="margin:4px 0 0;font-size:11px;color:#8b949e">
        WMD Plotter · WHITWERX
      </p>
    </div>
    <div style="padding:24px;font-size:13px;line-height:1.7">
      Your Brevo email settings are configured correctly.<br>
      Access request notifications and approval emails will be delivered.
    </div>
  </div>
</div>""",
    }
    t = threading.Thread(target=_send, args=(payload, api_key), daemon=True)
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
    api_key, _, notify_from = _get_config()
    if not api_key or not notify_from:
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
    <h1>✓ Access Approved — WMD Plotter</h1>
    <p>WHITWERX · Model Display (WMD) · CBRN Planning System</p>
  </div>
  <div class="body">
    <p>Hi {display_name},</p>
    <p>Your access request has been reviewed and <strong style="color:#00ff88">approved</strong>.
       You can now sign in using your username and the password you created when you submitted your request.</p>
    <p><strong>Username:</strong> {username}</p>
    <a class="btn" href="https://wmdplotter.whitwerx.net/login">Sign In →</a>
    <div class="footer">
      WMD Plotter is restricted to authorized personnel only.<br>
      If you did not request this account, contact Dave@WHITWERX.net.
    </div>
  </div>
</div>
</body>
</html>"""

    payload = {
        "sender":  {"name": "WHITWERX WMD Plotter", "email": notify_from},
        "to":      [{"email": to_email, "name": display_name}],
        "subject": "Your WMD Plotter access has been approved",
        "htmlContent": html,
    }
    t = threading.Thread(target=_send, args=(payload, api_key), daemon=True)
    t.start()


def notify_access_request(
    display_name: str,
    username: str,
    access_reason: str,
    email: Optional[str],
) -> None:
    """Fire-and-forget notification to admin when a new access request is submitted."""
    api_key, notify_to, notify_from = _get_config()
    if not api_key or not notify_to or not notify_from:
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
    <h1>⚠ New Access Request — WMD Plotter</h1>
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
      <a class="btn" href="https://wmdplotter.whitwerx.net/admin/users">Review in Admin Panel →</a>
    </div>
    <div class="ts">Submitted {ts}</div>
  </div>
</div>
</body>
</html>"""

    payload = {
        "sender":  {"name": "WMD Plotter", "email": notify_from},
        "to":      [{"email": notify_to}],
        "subject": f"[WMD Plotter] Access Request — {display_name}",
        "htmlContent": html,
    }
    t = threading.Thread(target=_send, args=(payload, api_key), daemon=True)
    t.start()
