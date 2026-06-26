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
import time
import threading
from typing import Optional

from tak_dp import _polygon_cot_event, point_cot_event


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
            events.append(_polygon_cot_event(uid, label, color, lonlat, src_lat, src_lon))

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
            events.append(_polygon_cot_event(uid, label, color, lonlat, src_lat, src_lon))

    return events


def _make_ssl_ctx(cert_b64: Optional[str], cert_pass: str) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE  # TAK servers commonly use self-signed certs

    if cert_b64:
        raw = base64.b64decode(cert_b64)
        if raw.lstrip().startswith(b"-----BEGIN"):
            # PEM format — write to temp file and load directly
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
                f.write(raw)
                pem_path = f.name
            try:
                ctx.load_cert_chain(pem_path)
            finally:
                os.unlink(pem_path)
        else:
            # P12/PFX binary
            try:
                from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
                from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
            except ImportError:
                raise RuntimeError(
                    "The 'cryptography' package is required for P12 certificate support. "
                    "Run: pip install cryptography"
                )
            passphrase = cert_pass.encode() if cert_pass else None
            privkey, cert, _ = load_key_and_certificates(raw, passphrase)
            cert_pem = cert.public_bytes(Encoding.PEM)
            key_pem  = privkey.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cf:
                cf.write(cert_pem); cert_path = cf.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as kf:
                kf.write(key_pem);  key_path = kf.name
            try:
                ctx.load_cert_chain(cert_path, key_path)
            finally:
                os.unlink(cert_path)
                os.unlink(key_path)

    return ctx


def _linger(sock, seconds: float) -> None:
    """Drain any server bytes until timeout, then return. Prevents TCP RST on close."""
    deadline = time.monotonic() + seconds
    buf = bytearray(512)
    try:
        sock.settimeout(0.05)
        while time.monotonic() < deadline:
            try:
                sock.recv_into(buf)
            except (TimeoutError, OSError):
                time.sleep(0.05)
    except Exception:
        pass


def _send_one_event(host: str, port: int, use_ssl: bool,
                    cert_p12: Optional[str], cert_pass: str,
                    cot_xml: str, results: list, idx: int) -> None:
    """
    Send a single CoT event on its own TLS connection + 2 s linger.
    Mirrors TAKPhotoSpotter's per-event socket approach so the server's
    XML parser sees one clean <?xml...?><event> document per connection.
    """
    payload = f'<?xml version="1.0" encoding="UTF-8"?>\n{cot_xml}'.encode("utf-8")
    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(15)
        if use_ssl:
            ctx  = _make_ssl_ctx(cert_p12, cert_pass)
            sock = ctx.wrap_socket(raw, server_hostname=host)
        else:
            sock = raw
        sock.connect((host, port))
        sock.sendall(payload)
        _linger(sock, 2.0)
        sock.close()
        results[idx] = True
    except Exception as exc:
        results[idx] = str(exc)


def push_cot(config: dict, overlay_state: dict, tools: Optional[list] = None) -> dict:
    """
    Send each CoT event on its own parallel TLS connection (TAKPhotoSpotter pattern).
    Sending multiple events on a single connection caused the server's streaming XML
    parser to see concatenated <?xml?> declarations and discard events after the first.
    """
    host      = (config.get("host") or "").strip()
    port      = int(config.get("port") or 8087)
    use_ssl   = bool(config.get("ssl"))
    cert_p12  = config.get("cert_p12")
    cert_pass = config.get("cert_pass") or ""

    if not host:
        return {"success": False, "sent": 0, "error": "TAK server host not configured"}

    events = _build_events(overlay_state, tools)
    if not events:
        return {"success": False, "sent": 0, "error": "No active overlays to push"}

    results = [None] * len(events)
    threads = [
        threading.Thread(
            target=_send_one_event,
            args=(host, port, use_ssl, cert_p12, cert_pass, ev, results, i),
            daemon=True,
        )
        for i, ev in enumerate(events)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    sent   = sum(1 for r in results if r is True)
    errors = [r for r in results if isinstance(r, str)]
    if sent == 0:
        return {"success": False, "sent": 0, "error": errors[0] if errors else "All sends failed"}
    return {"success": True, "sent": sent, "error": errors[0] if errors else None}


def push_test_point(config: dict, lat: float = 0.0, lon: float = 0.0,
                    callsign: str = "WMD PLOTTER") -> dict:
    """
    Send a single SA point marker (type a-f-G) to the TAK server.
    Used to verify the full pipeline — connection, auth, and ATAK routing —
    independently of polygon rendering.
    """
    host    = (config.get("host") or "").strip()
    port    = int(config.get("port") or 8087)
    use_ssl = bool(config.get("ssl"))

    if not host:
        return {"success": False, "error": "TAK server host not configured"}

    xml = point_cot_event(lat, lon, callsign)
    payload = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml}'.encode("utf-8")

    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(15)
        if use_ssl:
            ctx  = _make_ssl_ctx(config.get("cert_p12"), config.get("cert_pass") or "")
            sock = ctx.wrap_socket(raw, server_hostname=host)
        else:
            sock = raw
        sock.connect((host, port))
        sock.sendall(payload)
        _linger(sock, 2.0)
        sock.close()
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
