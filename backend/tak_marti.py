"""
TAK Server Marti REST API — data package push.

Methodology mirrors TAKPhotoSpotter (confirmed working):
  1. Upload KML zip to /Marti/sync/missionupload with correct params
     (filename, keyword=missionpackage, tool=public, creatorUid)
  2. Extract content URL from response body
  3. Compute SHA-256 of zip bytes
  4. Fetch all connected clients from /Marti/api/contacts/all
  5. POST a b-f-t-r file-transfer CoT to /Marti/api/cot for each client
     — this is what actually triggers ATAK to download the package

Auth: device cert (same P12 used for TCP CoT on port 8089).
      Falls back to marti_cert_p12 (admin.p12) if device cert not set.
"""

import hashlib
import json
import os
import base64
import ssl
import tempfile
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from kml_gen import build_combined_kml
from tak_dp import build_tak_data_package


def _make_ssl_ctx(cert_b64: Optional[str], cert_pass: str = "") -> tuple[ssl.SSLContext, list[str]]:
    """
    Build an SSLContext. Returns (ctx, [temp_paths_to_cleanup]).
    Forces TLS 1.2 to avoid TLS 1.3 certificate-required alert on port 8443.
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


def _build_file_transfer_cot(
    pkg_uid: str,
    zip_filename: str,
    content_url: str,
    sha256: str,
    size: int,
    contact_uid: str,
) -> str:
    now = datetime.now(timezone.utc)
    stale = now + timedelta(hours=1)
    def fmt(dt): return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        f"<event version='2.0' uid='{pkg_uid}-{contact_uid}' type='b-f-t-r' "
        f"time='{fmt(now)}' start='{fmt(now)}' stale='{fmt(stale)}' how='h-g-i-g-o'>\n"
        "  <point lat='0.0' lon='0.0' hae='0.0' ce='9999999.0' le='9999999.0'/>\n"
        "  <detail>\n"
        f"    <fileshare filename='{zip_filename}' senderUrl='{content_url}' "
        f"senderUid='WMD-PLOTTER' senderCallsign='WMD PLOTTER' "
        f"sha256='{sha256}' sizeInBytes='{size}' name='{zip_filename}'/>\n"
        f"    <marti><dest uid='{contact_uid}'/></marti>\n"
        "  </detail>\n"
        "</event>"
    )


async def push_via_marti(config: dict, overlay_state: dict) -> dict:
    """
    Upload a KML data package to Marti, then send a b-f-t-r file-transfer
    notification CoT to every connected client so they auto-download it.

    config keys used:
      host            — TAK server hostname
      marti_port      — Marti HTTPS port (default 8443)
      cert_p12        — base64 device cert (preferred — same cert used for TCP CoT)
      cert_pass       — device cert passphrase
      marti_cert_p12  — base64 admin.p12 (fallback if device cert absent)
      marti_cert_pass — admin.p12 passphrase (default: atakatak)
    """
    host       = (config.get("host") or "").strip()
    marti_port = int(config.get("marti_port") or 8443)

    if not host:
        return {"success": False, "url": None, "error": "TAK server host not configured"}

    export_state = {k: v for k, v in overlay_state.items() if v}
    if not export_state:
        return {"success": False, "url": None, "error": "No active overlays — run a model first"}

    active = list(export_state.keys())
    kml_bytes = build_combined_kml(export_state).encode("utf-8")
    zip_bytes, zip_filename, pkg_uid = build_tak_data_package(kml_bytes, active)

    sha256 = hashlib.sha256(zip_bytes).hexdigest()

    # Prefer device cert; fall back to admin/marti cert
    cert_b64  = config.get("cert_p12") or config.get("marti_cert_p12")
    cert_pass = (config.get("cert_pass") or "") if config.get("cert_p12") else (config.get("marti_cert_pass") or "atakatak")

    if not cert_b64:
        return {
            "success": False, "url": None,
            "error": (
                "No certificate configured. Upload your TAK device cert (.p12 or .pem) "
                "in the admin panel under 'TAK Push Certificate'."
            ),
        }

    ctx, temps = _make_ssl_ctx(cert_b64, cert_pass)
    try:
        filename_enc = urllib.parse.quote(zip_filename)
        upload_url = (
            f"https://{host}:{marti_port}/Marti/sync/missionupload"
            f"?filename={filename_enc}&keyword=missionpackage&tool=public&creatorUid=WMD-PLOTTER"
        )

        # Step 1: Upload the ZIP
        async with httpx.AsyncClient(verify=ctx, timeout=30.0) as client:
            resp = await client.post(
                upload_url,
                files={"assetfile": (zip_filename, zip_bytes, "application/x-zip-compressed")},
            )

        if resp.status_code not in (200, 201):
            return {
                "success": False, "url": None,
                "error": f"Marti upload HTTP {resp.status_code}: {resp.text[:300]}",
            }

        content_url = resp.text.strip()

        # Step 2: Fetch connected clients
        contacts_url = f"https://{host}:{marti_port}/Marti/api/contacts/all"
        contacts: list[dict] = []
        try:
            async with httpx.AsyncClient(verify=ctx, timeout=10.0) as client:
                cr = await client.get(contacts_url, headers={"Accept": "application/json"})
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
                "success": True, "url": content_url,
                "error": None, "zones": len(active), "notified": 0,
                "note": "Package uploaded but no connected clients found — they will see it next time they connect.",
            }

        # Step 3: POST b-f-t-r CoT to each client via /Marti/api/cot
        # TAK Server accepts CoT via HTTP — same cert, same port 8443
        cot_url = f"https://{host}:{marti_port}/Marti/api/cot"
        notified = 0
        errors = []
        for contact in contacts:
            cot = _build_file_transfer_cot(
                pkg_uid=pkg_uid,
                zip_filename=zip_filename,
                content_url=content_url,
                sha256=sha256,
                size=len(zip_bytes),
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
