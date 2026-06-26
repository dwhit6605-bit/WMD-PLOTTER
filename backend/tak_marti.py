"""
TAK Server Marti REST API — KMZ push.

Flow (mirrors TAKPhotoSpotter photo upload, confirmed working):
  1. Build KMZ (ZIP containing doc.kml)
  2. POST to /Marti/sync/upload?name=<filename>.kmz
     — server returns JSON with "Hash" field
  3. Build content URL: https://{host}:8443/Marti/sync/content?hash={hash}
  4. Fetch connected clients from /Marti/api/contacts/all
  5. POST b-f-t-r file-transfer CoT to /Marti/api/cot for each client
     — ATAK auto-downloads and imports the KMZ on receipt

Auth: device cert (same P12 used for TCP CoT on port 8089).
"""

import hashlib
import io
import json
import os
import re
import base64
import ssl
import tempfile
import zipfile
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from kml_gen import build_combined_kml


def _make_ssl_ctx(cert_b64: Optional[str], cert_pass: str = "") -> tuple[ssl.SSLContext, list[str]]:
    """
    Build an SSLContext from a PEM or P12 cert.
    Forces TLS 1.2 to avoid TLS 1.3 certificate-required alert on port 8443.
    Returns (ctx, [temp_paths_to_cleanup]).
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    except AttributeError:
        pass

    if not cert_b64:
        return ctx, []

    raw = base64.b64decode(cert_b64)
    temps: list[str] = []

    if raw.lstrip().startswith(b"-----BEGIN"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
            f.write(raw)
            temps.append(f.name)
        ctx.load_cert_chain(temps[0])
    else:
        try:
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
            from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
        except ImportError:
            raise RuntimeError("'cryptography' package required — run: pip install cryptography")

        pw = cert_pass.encode() if cert_pass else None
        privkey, cert, _ = load_key_and_certificates(raw, pw)
        cert_pem = cert.public_bytes(Encoding.PEM)
        key_pem = privkey.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf:
            cf.write(cert_pem)
            temps.append(cf.name)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as kf:
            kf.write(key_pem)
            temps.append(kf.name)
        ctx.load_cert_chain(temps[0], temps[1])

    return ctx, temps


def _build_kmz(kml_bytes: bytes) -> bytes:
    """Wrap KML bytes in a KMZ (ZIP containing doc.kml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_bytes)
    buf.seek(0)
    return buf.read()


def _build_file_transfer_cot(
    kmz_filename: str,
    content_url: str,
    sha256: str,
    size: int,
    contact_uid: str,
) -> str:
    now = datetime.now(timezone.utc)
    stale = now + timedelta(hours=1)
    pkg_uid = f"wmd-{int(now.timestamp())}"
    def fmt(dt): return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        f"<event version='2.0' uid='{pkg_uid}-{contact_uid}' type='b-f-t-r' "
        f"time='{fmt(now)}' start='{fmt(now)}' stale='{fmt(stale)}' how='h-g-i-g-o'>\n"
        "  <point lat='0.0' lon='0.0' hae='0.0' ce='9999999.0' le='9999999.0'/>\n"
        "  <detail>\n"
        f"    <fileshare filename='{kmz_filename}' senderUrl='{content_url}' "
        f"senderUid='WMD-PLOTTER' senderCallsign='WMD PLOTTER' "
        f"sha256='{sha256}' sizeInBytes='{size}' name='{kmz_filename}'/>\n"
        f"    <marti><dest uid='{contact_uid}'/></marti>\n"
        "  </detail>\n"
        "</event>"
    )


async def push_cot_http(config: dict, overlay_state: dict) -> dict:
    """
    Push overlay CoT events via POST /Marti/api/cot (HTTP) using the device cert.
    Same endpoint as the working test marker — bypasses TCP socket issues and
    /Marti/sync/upload 403 errors entirely.
    """
    from tak_push import _build_events

    host       = (config.get("host") or "").strip()
    marti_port = int(config.get("marti_port") or 8443)

    if not host:
        return {"success": False, "sent": 0, "error": "TAK server host not configured"}

    export_state = {k: v for k, v in overlay_state.items() if v}
    if not export_state:
        return {"success": False, "sent": 0, "error": "No active overlays — run a model first"}

    # Prefer admin cert for Marti REST API; fall back to device cert
    if config.get("admin_cert_p12"):
        cert_b64  = config["admin_cert_p12"]
        cert_pass = config.get("admin_cert_pass") or ""
    elif config.get("cert_p12"):
        cert_b64  = config["cert_p12"]
        cert_pass = config.get("cert_pass") or ""
    else:
        return {"success": False, "sent": 0,
                "error": "No certificate configured — upload your TAK device or admin cert in the admin panel."}

    events = _build_events(export_state)
    if not events:
        return {"success": False, "sent": 0, "error": "No CoT events built from overlay state"}

    ctx, temps = _make_ssl_ctx(cert_b64, cert_pass)
    cot_url = f"https://{host}:{marti_port}/Marti/api/cot"
    sent = 0
    errors = []

    try:
        for cot_xml in events:
            try:
                async with httpx.AsyncClient(verify=ctx, timeout=10.0) as client:
                    r = await client.post(
                        cot_url,
                        content=cot_xml.encode("utf-8"),
                        headers={
                            "Content-Type": "application/octet-stream",
                            "X-Content-Type": "application/xml",
                        },
                    )
                if r.status_code in (200, 201, 204):
                    sent += 1
                else:
                    errors.append(f"HTTP {r.status_code}: {r.text[:100]}")
            except Exception as e:
                errors.append(str(e))
    finally:
        for path in temps:
            try:
                os.unlink(path)
            except OSError:
                pass

    if sent == 0:
        return {"success": False, "sent": 0, "error": errors[0] if errors else "All events failed"}
    return {
        "success": True,
        "sent": sent,
        "total": len(events),
        "error": "; ".join(errors) if errors else None,
    }


async def push_via_marti(config: dict, overlay_state: dict) -> dict:
    """
    Build a KMZ from overlay state, upload to Marti, and notify all connected
    clients with a b-f-t-r CoT so they auto-download and import it.

    config keys: host, marti_port, cert_p12, cert_pass
    """
    host       = (config.get("host") or "").strip()
    marti_port = int(config.get("marti_port") or 8443)

    if not host:
        return {"success": False, "url": None, "error": "TAK server host not configured"}

    export_state = {k: v for k, v in overlay_state.items() if v}
    if not export_state:
        return {"success": False, "url": None, "error": "No active overlays — run a model first"}

    active    = list(export_state.keys())
    kml_bytes = build_combined_kml(export_state).encode("utf-8")
    kmz_bytes = _build_kmz(kml_bytes)
    sha256    = hashlib.sha256(kmz_bytes).hexdigest()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tool_tag = "_".join(active)
    kmz_filename = f"WMD_PLOTTER_{tool_tag}_{ts}.kmz"

    # Prefer admin cert for Marti REST API; fall back to device cert
    if config.get("admin_cert_p12"):
        cert_b64  = config["admin_cert_p12"]
        cert_pass = config.get("admin_cert_pass") or ""
    elif config.get("cert_p12"):
        cert_b64  = config["cert_p12"]
        cert_pass = config.get("cert_pass") or ""
    else:
        return {
            "success": False, "url": None,
            "error": "No certificate configured — upload your TAK device or admin cert in the admin panel.",
        }

    ctx, temps = _make_ssl_ctx(cert_b64, cert_pass)
    try:
        # Step 1: Upload KMZ to /Marti/sync/upload (same endpoint as photo upload)
        name_enc   = urllib.parse.quote(kmz_filename)
        upload_url = f"https://{host}:{marti_port}/Marti/sync/upload?name={name_enc}"

        async with httpx.AsyncClient(verify=ctx, timeout=30.0) as client:
            resp = await client.post(
                upload_url,
                content=kmz_bytes,
                headers={
                    "Content-Type": "application/vnd.google-earth.kmz",
                    "Content-Disposition": f'attachment; filename="{kmz_filename}"',
                },
            )

        if resp.status_code not in (200, 201):
            return {
                "success": False, "url": None,
                "error": f"KMZ upload HTTP {resp.status_code}: {resp.text[:300]}",
            }

        # Server returns JSON with "Hash" field — build content URL from it
        body_text = resp.text.strip()
        hash_match = re.search(r'"Hash"\s*:\s*"([a-fA-F0-9]+)"', body_text)
        if hash_match:
            server_hash = hash_match.group(1)
            content_url = f"https://{host}:{marti_port}/Marti/sync/content?hash={server_hash}"
        else:
            # Some server versions return the URL directly
            content_url = body_text if body_text.startswith("http") else \
                f"https://{host}:{marti_port}/Marti/sync/content?hash={sha256}"

        # Step 2: Fetch connected clients
        contacts: list[dict] = []
        try:
            async with httpx.AsyncClient(verify=ctx, timeout=10.0) as client:
                cr = await client.get(
                    f"https://{host}:{marti_port}/Marti/api/contacts/all",
                    headers={"Accept": "application/json"},
                )
            if cr.status_code == 200:
                data = cr.json()
                contacts = [
                    {"uid": c.get("uid", "").strip(), "callsign": c.get("callsign", "").strip()}
                    for c in (data if isinstance(data, list) else [])
                    if c.get("uid", "").strip()
                ]
        except Exception:
            pass

        if not contacts:
            return {
                "success": True, "url": content_url, "error": None,
                "zones": len(active), "notified": 0,
                "note": "KMZ uploaded but no connected clients found to notify.",
            }

        # Step 3: POST b-f-t-r CoT to each client via /Marti/api/cot
        cot_url  = f"https://{host}:{marti_port}/Marti/api/cot"
        notified = 0
        errors   = []
        for contact in contacts:
            cot = _build_file_transfer_cot(
                kmz_filename=kmz_filename,
                content_url=content_url,
                sha256=sha256,
                size=len(kmz_bytes),
                contact_uid=contact["uid"],
            )
            try:
                async with httpx.AsyncClient(verify=ctx, timeout=10.0) as client:
                    nr = await client.post(
                        cot_url,
                        content=cot.encode("utf-8"),
                        headers={
                            "Content-Type": "application/octet-stream",
                            "X-Content-Type": "application/xml",
                        },
                    )
                if nr.status_code in (200, 201, 204):
                    notified += 1
                else:
                    errors.append(f"{contact.get('callsign') or contact['uid']}: HTTP {nr.status_code}")
            except Exception as e:
                errors.append(f"{contact.get('callsign') or contact['uid']}: {e}")

        return {
            "success": True,
            "url": content_url,
            "error": "; ".join(errors) if errors else None,
            "zones": len(active),
            "notified": notified,
            "contacts": len(contacts),
        }

    finally:
        for path in temps:
            try:
                os.unlink(path)
            except OSError:
                pass
