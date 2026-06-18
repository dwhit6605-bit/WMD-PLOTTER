"""
TAK Server CoT streaming.
Sends individual CoT <event> XML elements over TCP (plain or SSL/TLS).

Compatible with:
  - Official TAK Server: port 8087 (TCP) or 8089 (SSL + client cert)
  - FreeTAKServer:       port 8087 (TCP) or 8088 (SSL)
"""

import socket
import ssl
import base64
import tempfile
import os
from typing import Optional

from tak_dp import _polygon_cot_event


def _build_events(overlay_state: dict, tools: Optional[list] = None) -> list[str]:
    """Build individual CoT <event> XML strings (no <events> wrapper)."""
    events = []
    for tool, state in overlay_state.items():
        if tools and tool not in tools:
            continue
        if not state:
            continue
        src_lat = state.get("source_lat", 0.0)
        src_lon = state.get("source_lon", 0.0)

        # Zones-based tools (blast, bleve, erg, dense_gas, fire_smoke, population)
        # Each zone entry has "lonlat" in [lon, lat] order
        for i, z in enumerate(state.get("zones", [])):
            lonlat = z.get("lonlat") or z.get("coords", [])
            if not lonlat:
                continue
            label = z.get("label") or z.get("level", tool)
            color = z.get("color", "#888888")
            uid   = f"wmd-{tool}-{z.get('level', 'z')}-{i}"
            xml   = _polygon_cot_event(uid, label, color, lonlat, src_lat, src_lon)
            events.append(f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}')

        # Contours-based tools (plume, radiation)
        # contours is a dict keyed by level; "latlon" is in [lat, lon] order — flip for CoT
        for i, (level, info) in enumerate(state.get("contours", {}).items()):
            latlon = info.get("latlon", [])
            if not latlon:
                continue
            lonlat = [[pt[1], pt[0]] for pt in latlon]
            label  = info.get("label", f"{tool} {level}")
            color  = info.get("color", "#888888")
            uid    = f"wmd-{tool}-{level}-{i}"
            xml    = _polygon_cot_event(uid, label, color, lonlat, src_lat, src_lon)
            events.append(f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}')

    return events


def _make_ssl_ctx(cert_p12_b64: Optional[str], cert_pass: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE  # TAK servers commonly use self-signed certs

    if cert_p12_b64:
        try:
            from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
            from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
        except ImportError:
            raise RuntimeError(
                "The 'cryptography' package is required for P12 certificate support. "
                "Run: pip install cryptography"
            )

        p12_bytes  = base64.b64decode(cert_p12_b64)
        passphrase = cert_pass.encode() if cert_pass else None
        privkey, cert, _ = load_key_and_certificates(p12_bytes, passphrase)

        cert_pem = cert.public_bytes(Encoding.PEM)
        key_pem  = privkey.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

        # ssl.SSLContext.load_cert_chain needs file paths; use temp files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf:
            cf.write(cert_pem)
            cert_path = cf.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as kf:
            kf.write(key_pem)
            key_path = kf.name
        try:
            ctx.load_cert_chain(cert_path, key_path)
        finally:
            os.unlink(cert_path)
            os.unlink(key_path)

    return ctx


def push_cot(config: dict, overlay_state: dict, tools: Optional[list] = None) -> dict:
    """
    Stream CoT events to a TAK server over TCP or SSL.
    Returns {"success": bool, "sent": int, "error": str | None}
    """
    host      = (config.get("host") or "").strip()
    port      = int(config.get("port") or 8087)
    use_ssl   = bool(config.get("ssl"))
    cert_p12  = config.get("cert_p12")    # base64-encoded P12 bytes
    cert_pass = config.get("cert_pass") or ""

    if not host:
        return {"success": False, "sent": 0, "error": "TAK server host not configured"}

    events = _build_events(overlay_state, tools)
    if not events:
        return {"success": False, "sent": 0, "error": "No active overlays to push"}

    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(15)

        if use_ssl:
            ctx  = _make_ssl_ctx(cert_p12, cert_pass)
            sock = ctx.wrap_socket(raw, server_hostname=host)
        else:
            sock = raw

        sock.connect((host, port))
        for ev in events:
            sock.sendall(ev.encode("utf-8"))
        sock.close()
        return {"success": True, "sent": len(events), "error": None}

    except Exception as exc:
        return {"success": False, "sent": 0, "error": str(exc)}
