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
      host            — TAK server hostname
      marti_port      — Marti HTTPS port (default 8443)
      marti_cert_p12  — base64-encoded admin.p12 (from /opt/tak/certs/files/admin.p12)
      marti_cert_pass — passphrase for admin.p12 (default: atakatak)

    Returns {"success": bool, "url": str|None, "error": str|None}
    """
    host       = (config.get("host") or "").strip()
    marti_port = int(config.get("marti_port") or 8443)

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

    params         = {"name": filename.replace(".zip", ""), "creatorUid": "WMD-PLOTTER"}
    files          = {"assetfile": (filename, zip_bytes, "application/zip")}
    marti_cert_p12 = config.get("marti_cert_p12")
    marti_cert_pass = config.get("marti_cert_pass") or ""

    def _make_ctx(cert_p12_b64: str = None, passphrase: str = "") -> tuple:
        """Return (ssl_context, [temp_paths]) using TLS 1.2 to avoid TLS 1.3 cert alerts."""
        import ssl as _ssl
        ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode    = _ssl.CERT_NONE
        try:
            ctx.maximum_version = _ssl.TLSVersion.TLSv1_2
        except AttributeError:
            pass
        temps = []
        if cert_p12_b64:
            cp, kp = _pem_tempfiles(cert_p12_b64, passphrase)
            ctx.load_cert_chain(cp, kp)
            temps = [cp, kp]
        return ctx, temps

    all_temps = []
    try:
        # Attempt 1: Marti admin cert (admin.p12) — correct auth for port 8443
        if marti_cert_p12:
            ctx, temps = _make_ctx(marti_cert_p12, marti_cert_pass)
            all_temps += temps
            async with httpx.AsyncClient(verify=ctx, timeout=30.0) as client:
                resp = await client.post(url, files=files, params=params)
            if resp.status_code in (200, 201):
                return {"success": True, "url": resp.text.strip(), "error": None,
                        "zones": len(active)}
            if resp.status_code not in (401, 403):
                return {"success": False, "url": None,
                        "error": f"Marti HTTP {resp.status_code}: {resp.text[:200]}"}

        # Attempt 2: anonymous (some servers allow unauthenticated missionupload)
        ctx, _ = _make_ctx()
        async with httpx.AsyncClient(verify=ctx, timeout=30.0) as client:
            resp = await client.post(url, files=files, params=params)
        if resp.status_code in (200, 201):
            return {"success": True, "url": resp.text.strip(), "error": None,
                    "zones": len(active)}

        if resp.status_code in (401, 403):
            return {
                "success": False, "url": None,
                "error": (
                    "Marti HTTP 403 — upload admin.p12 from your TAK server "
                    "(/opt/tak/certs/files/admin.p12) in the admin panel under "
                    "'Marti API Certificate'. Default passphrase is 'atakatak'."
                ),
            }
        return {"success": False, "url": None,
                "error": f"Marti HTTP {resp.status_code}: {resp.text[:200]}"}

    except Exception as exc:
        return {"success": False, "url": None, "error": str(exc)}

    finally:
        for path in all_temps:
            try:
                os.unlink(path)
            except OSError:
                pass
