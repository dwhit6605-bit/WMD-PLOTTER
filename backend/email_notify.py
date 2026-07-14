"""
Brevo (formerly Sendinblue) transactional email notifications.

Required env vars in backend/.env:
  BREVO_API_KEY   — API key from Brevo Settings → API Keys
  NOTIFY_EMAIL    — address that receives admin notifications
  NOTIFY_FROM     — verified sender address in your Brevo account
"""

import os
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
NOTIFY_EMAIL  = os.environ.get("NOTIFY_EMAIL", "")
NOTIFY_FROM   = os.environ.get("NOTIFY_FROM", "")

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def _send(payload: dict) -> None:
    """Blocking Brevo call — always run in a daemon thread."""
    if not BREVO_API_KEY:
        logger.debug("email_notify: BREVO_API_KEY not set, skipping")
        return
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                BREVO_SEND_URL,
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code not in (200, 201, 202):
            logger.warning("Brevo API returned %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("email_notify: failed to send — %s", exc)


def notify_access_request(
    display_name: str,
    username: str,
    access_reason: str,
    email: Optional[str],
) -> None:
    """
    Fire-and-forget notification when a new user submits an access request.
    Never raises — email failure must never block user registration.
    """
    if not BREVO_API_KEY or not NOTIFY_EMAIL or not NOTIFY_FROM:
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    email_line = email or "<em>not provided</em>"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  body   {{ font-family: 'Courier New', monospace; background:#0d1117; color:#c9d1d9; margin:0; padding:24px; }}
  .card  {{ max-width:520px; margin:0 auto; background:#161b22; border:1px solid #21262d;
            border-radius:10px; overflow:hidden; }}
  .hdr   {{ background:#0a0f14; padding:18px 24px; border-bottom:1px solid #21262d; }}
  .hdr h1{{ margin:0; font-size:15px; font-weight:800; letter-spacing:.08em; color:#c9d1d9; }}
  .hdr p {{ margin:4px 0 0; font-size:11px; color:#8b949e; }}
  .body  {{ padding:24px; }}
  .row   {{ margin-bottom:14px; }}
  .lbl   {{ font-size:10px; font-weight:700; letter-spacing:.08em; color:#8b949e;
            text-transform:uppercase; margin-bottom:4px; }}
  .val   {{ font-size:13px; color:#c9d1d9; line-height:1.5; }}
  .reason{{ background:#0d1117; border:1px solid #21262d; border-radius:6px;
            padding:10px 12px; font-size:12px; color:#c9d1d9; line-height:1.6; }}
  .btn   {{ display:inline-block; margin-top:6px; padding:11px 24px;
            background:#00ff88; color:#000; font-family:'Courier New',monospace;
            font-size:12px; font-weight:700; letter-spacing:1px; text-decoration:none;
            border-radius:7px; text-transform:uppercase; }}
  .ts    {{ font-size:10px; color:#8b949e; margin-top:20px; padding-top:14px;
            border-top:1px solid #21262d; }}
</style>
</head>
<body>
<div class="card">
  <div class="hdr">
    <h1>⚠ New Access Request — WMD Plotter</h1>
    <p>A user has requested access and is awaiting your approval.</p>
  </div>
  <div class="body">
    <div class="row">
      <div class="lbl">Full Name</div>
      <div class="val">{display_name}</div>
    </div>
    <div class="row">
      <div class="lbl">Username</div>
      <div class="val">@{username}</div>
    </div>
    <div class="row">
      <div class="lbl">Email</div>
      <div class="val">{email_line}</div>
    </div>
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
</html>
"""

    payload = {
        "sender":  {"name": "WMD Plotter", "email": NOTIFY_FROM},
        "to":      [{"email": NOTIFY_EMAIL}],
        "subject": f"[WMD Plotter] Access Request — {display_name}",
        "htmlContent": html,
    }

    t = threading.Thread(target=_send, args=(payload,), daemon=True)
    t.start()
