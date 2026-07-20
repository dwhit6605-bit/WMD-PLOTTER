"""
Shared test scaffolding.

Deliberately dependency-free: these run with the same interpreter that runs the
app (`/opt/wmd-plotter/.venv/bin/python` on the server, your venv locally), so
there is nothing extra to install and they can be run on the box that is
actually misbehaving.

SAFETY: every suite must call `isolated_db()` before importing `main`. It points
db.DB_PATH at a fresh temporary file, so a test run can never read or write the
real users.db. Import order matters — `main` reads DB_PATH at import time.
"""

import os
import re
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

# ── Locating the app ─────────────────────────────────────────────────────────

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
BACKEND   = REPO_ROOT / "backend"


def add_backend_to_path() -> None:
    """Make `import main`, `import db`, … resolve to this checkout."""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def isolated_db():
    """Point the app at a throwaway database and initialise it.

    Returns the temp path. Call this BEFORE importing main.
    """
    add_backend_to_path()
    import db
    db.DB_PATH = Path(tempfile.mkdtemp(prefix="wmd-test-")) / "test.db"
    db.init_db()
    return db.DB_PATH


def clear_env():
    """Drop notification env vars before importing main.

    main.py calls load_dotenv(backend/.env). On a developer machine that file
    supplies NOTIFY_FROM, BREVO_API_KEY and friends, which satisfy the
    environment fallbacks in _get_smtp_config and mask what the test actually
    configured in the database. Without this, results depend on whether the
    machine happens to have a .env — which is how a real bug once hid.
    """
    for key in ("NOTIFY_FROM", "NOTIFY_EMAIL", "NOTIFY_PHONE", "BREVO_API_KEY",
                "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
                "PUBLIC_BASE_URL", "WMD_PUBLIC_URL"):
        os.environ.pop(key, None)


# ── Result tracking ──────────────────────────────────────────────────────────

class Results:
    """Collects checks and prints a pass/fail line for each."""

    def __init__(self, title: str):
        self.title = title
        self.items = []
        print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")

    def section(self, name: str) -> None:
        print(f"\n--- {name} ---")

    def check(self, name: str, condition, detail: str = "") -> bool:
        ok = bool(condition)
        self.items.append((name, ok))
        suffix = f"   [{detail}]" if detail and not ok else ""
        print(("PASS  " if ok else "FAIL  ") + name + suffix)
        return ok

    def report(self) -> int:
        """Print a summary and return an exit code."""
        failed = [n for n, ok in self.items if not ok]
        print(f"\n{len(self.items) - len(failed)}/{len(self.items)} passed")
        for name in failed:
            print("  FAILED:", name)
        return 1 if failed else 0


# ── Fake SMTP server ─────────────────────────────────────────────────────────

class FakeSMTP(threading.Thread):
    """A minimal SMTP server that captures messages instead of delivering them.

    Enough of the protocol for smtplib to complete a send. Speaks plaintext, so
    suites using it also patch smtplib.SMTP.starttls to a no-op — see
    `patch_smtp_plaintext`.
    """

    daemon = True

    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.received = []      # [{"to": [...], "raw": "..."}]

    def start(self):            # type: ignore[override]
        super().start()
        time.sleep(0.4)         # let the socket bind before tests fire
        return self

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.port))
        srv.listen(5)
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        stream = conn.makefile("rwb")
        send = lambda s: conn.sendall((s + "\r\n").encode())
        send("220 localhost ESMTP")
        in_data, body, rcpt = False, [], []
        while True:
            line = stream.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").rstrip("\r\n")
            if in_data:
                if text == ".":
                    self.received.append({"to": list(rcpt), "raw": "\n".join(body)})
                    body, rcpt, in_data = [], [], False
                    send("250 OK")
                else:
                    body.append(text)
                continue
            upper = text.upper()
            if upper.startswith(("EHLO", "HELO")):
                conn.sendall(b"250-localhost\r\n250 AUTH PLAIN LOGIN\r\n")
            elif upper.startswith("AUTH"):
                send("235 OK")
            elif upper.startswith("MAIL"):
                send("250 OK")
            elif upper.startswith("RCPT"):
                rcpt.append(text.split("<", 1)[-1].rstrip(">"))
                send("250 OK")
            elif upper.startswith("DATA"):
                send("354 go ahead")
                in_data = True
            elif upper.startswith("QUIT"):
                send("221 bye")
                break
            else:
                send("250 OK")
        conn.close()

    # ── convenience ──
    def wait(self, count: int = 1, timeout: float = 5.0) -> bool:
        """Block until `count` messages have arrived. Sends are async."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.received) >= count:
                return True
            time.sleep(0.05)
        return False

    def settle(self, pause: float = 0.6) -> None:
        """Let in-flight sends land, then reset.

        Sends run on daemon threads, so a message from a previous step can
        arrive after a naive clear() and be misattributed to the next one.
        """
        time.sleep(pause)
        self.received.clear()

    @property
    def last(self):
        return self.received[-1] if self.received else None


def patch_smtp_plaintext(email_notify_module) -> None:
    """Make the app skip STARTTLS, since FakeSMTP speaks plaintext."""
    import smtplib

    class PlainSMTP(smtplib.SMTP):
        def starttls(self, *a, **k):
            return None

    email_notify_module.smtplib.SMTP = PlainSMTP


def configure_smtp(db_module, port: int, **overrides) -> None:
    """Point the app's notification settings at a local FakeSMTP."""
    settings = {
        "smtp_host": "127.0.0.1",
        "smtp_port": str(port),
        "smtp_username": "tester@example.com",
        "smtp_password": "k" * 24,
        "email_notify_to": "admin@example.gov",
        "email_notify_from": "noreply@whitwerx.net",
        "site_url": "https://wmd.whitwerx.net",
    }
    settings.update(overrides)
    for key, value in settings.items():
        db_module.set_setting(key, value)


# ── Message parsing ──────────────────────────────────────────────────────────

def body_text(raw: str) -> str:
    """Decode a captured message's payload.

    MIMEText(..., 'utf-8') base64-encodes the body, so matching strings against
    the raw wire format silently finds nothing and every assertion passes.
    """
    import email as email_mod
    msg = email_mod.message_from_string(raw)
    parts = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_maintype() == "multipart":
            continue
        try:
            parts.append(part.get_payload(decode=True).decode("utf-8", "replace"))
        except Exception:
            pass
    return "\n".join(parts)


def find_link(raw: str, pattern: str):
    """First regex group matching `pattern` in a decoded message body."""
    match = re.search(pattern, body_text(raw))
    return match.group(1) if match else None
