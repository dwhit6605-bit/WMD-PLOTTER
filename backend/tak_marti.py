"""
TAK Server Marti REST API — data package push.

POSTs a KML-wrapped TAK Data Package (.zip) to the TAK server's enterprise
sync endpoint.  The server then distributes a download notification (type
b-f-t-r) to all connected ATAK/WinTAK/iTAK clients, which auto-import it.

Endpoint: POST https://{host}:8443/Marti/sync/missionupload
Auth:     SSL client certificate (same P12 as CoT TCP push), or none for
          servers that allow anonymous uploads.

Advantages over raw TCP CoT:
  - Uses standard HTTPS — no raw socket management
  - One upload distributes to all connected clients regardless of group
  - Server validates and stores the package; clients can re-download
"""

import os
import base64
import tempfile
from typing import Optional

import httpx

from kml_gen import build_combined_kml
from tak_dp import build_tak_data_package


def _pem_tempfiles(cert_p12_b64: str, cert_pass: str) -> tuple[str, str]:
    """Extract PEM cert + key from base64 P12 into temp files. Caller must delete."""
    try:
        from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
        from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    except ImportError:
        raise RuntimeError("'cryptography' package required — run: pip install cryptography")

    p12_bytes  = base64.b64decode(cert_p12_b64)
    passphrase = cert_pass.encode() if cert_pass else None
    privkey, cert, _ = load_key_and_certificates(p12_bytes, passphrase)

    cert_pem = cert.public_bytes(Encoding.PEM)
    key_pem  = privkey.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf:
        cf.write(cert_pem)
        cert_path = cf.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as kf:
        kf.write(key_pem)
        key_path = kf.name

    return cert_path, key_path


async def push_via_marti(config: dict, overlay_state: dict) -> dict:
    """
    Generate a TAK Data Package from overlay_state and POST it to the Marti
    enterprise sync endpoint.

    config keys:
      host        — TAK server hostname
      marti_port  — Marti HTTPS port (default 8443)
      cert_p12    — base64-encoded P12 client cert (optional)
      cert_pass   — P12 passphrase (optional)

    Returns {"success": bool, "url": str|None, "error": str|None}
    """
    host       = (config.get("host") or "").strip()
    marti_port = int(config.get("marti_port") or 8443)
    cert_p12   = config.get("cert_p12")
    cert_pass  = config.get("cert_pass") or ""

    if not host:
        return {"success": False, "url": None, "error": "TAK server host not configured"}

    export_state = {k: v for k, v in overlay_state.items() if v}
    if not export_state:
        return {"success": False, "url": None,
                "error": "No active overlays — run a model first"}

    active    = list(export_state.keys())
    kml_bytes = build_combined_kml(export_state).encode("utf-8")
    zip_bytes, filename = build_tak_data_package(kml_bytes, active)

    url = f"https://{host}:{marti_port}/Marti/sync/missionupload"

    params = {"name": filename.replace(".zip", ""), "creatorUid": "WMD-PLOTTER"}
    files  = {"assetfile": (filename, zip_bytes, "application/zip")}

    cert_path = key_path = None
    try:
        # Attempt 1: no client cert — Marti's missionupload often allows this,
        # and the Marti port (8443) uses a different trust store than CoT (8089).
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.post(url, files=files, params=params)

        if resp.status_code in (200, 201):
            return {"success": True, "url": resp.text.strip(), "error": None,
                    "zones": len(active)}

        # Attempt 2: retry with client cert if server returned 401/403
        if resp.status_code in (401, 403) and cert_p12:
            cert_path, key_path = _pem_tempfiles(cert_p12, cert_pass)
            async with httpx.AsyncClient(
                verify=False, timeout=30.0, cert=(cert_path, key_path)
            ) as client:
                resp = await client.post(url, files=files, params=params)

            if resp.status_code in (200, 201):
                return {"success": True, "url": resp.text.strip(), "error": None,
                        "zones": len(active)}

        return {
            "success": False, "url": None,
            "error": f"Marti HTTP {resp.status_code}: {resp.text[:300]}",
        }

    except Exception as exc:
        return {"success": False, "url": None, "error": str(exc)}

    finally:
        for path in (cert_path, key_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
