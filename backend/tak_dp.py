"""
TAK Data Package generator.

Produces a ATAK-compatible Mission Package ZIP:
  MANIFEST/manifest.xml   — package descriptor (MissionPackageManifest v2)
  files/<name>.kml        — the scenario KML

References:
  TAK Product Center — Mission Package Specification (2022)
  https://tak.gov/resources
"""

import io
import uuid
import zipfile
from datetime import datetime, timedelta, timezone


_MANIFEST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<MissionPackageManifest version="2">
  <Configuration>
    <Parameter name="uid" value="{uid}"/>
    <Parameter name="name" value="{name}"/>
    <Parameter name="onReceiveDelete" value="false"/>
    <Parameter name="onReceiveImport" value="true"/>
  </Configuration>
  <Contents>
    <Content ignore="false" zipEntry="files/{kml_filename}">
      <Parameter name="contentType" value="KML"/>
      <Parameter name="name" value="{kml_display_name}"/>
      <Parameter name="visible" value="true"/>
    </Content>
  </Contents>
</MissionPackageManifest>
"""


def build_tak_data_package(kml_bytes: bytes, active_tools: list[str]) -> tuple[bytes, str, str]:
    """
    Wrap KML bytes in a TAK Data Package ZIP.

    Returns (zip_bytes, suggested_filename, pkg_uid).
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tool_tag = "_".join(active_tools) if active_tools else "scenario"
    pkg_name = f"WMD_PLOTTER_{tool_tag}_{ts}"
    kml_filename = f"{pkg_name}.kml"
    pkg_uid = str(uuid.uuid4())

    manifest = _MANIFEST_TEMPLATE.format(
        uid=pkg_uid,
        name=f"WMD PLOTTER {tool_tag.replace('_', ' ').upper()} {ts}",
        kml_filename=kml_filename,
        kml_display_name=f"WMD PLOTTER Hazard Zones {ts}",
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("MANIFEST/manifest.xml", manifest.encode("utf-8"))
        zf.writestr(f"files/{kml_filename}", kml_bytes)
    buf.seek(0)

    return buf.read(), f"{pkg_name}.zip", pkg_uid


# ── CoT XML ───────────────────────────────────────────────────────────────────

def _hex_to_argb_int(hex_color: str, alpha: int = 160) -> int:
    """#RRGGBB → signed ARGB int (ATAK color format)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    val = (alpha << 24) | (r << 16) | (g << 8) | b
    return val - 0x100000000 if val >= 0x80000000 else val


def _cot_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _polygon_cot_event(uid: str, label: str, color: str,
                       lonlat_ring: list, center_lat: float, center_lon: float) -> str:
    now    = datetime.now(timezone.utc)
    stale  = now + timedelta(hours=24)
    fill   = _hex_to_argb_int(color, 80)
    stroke = _hex_to_argb_int(color, 220)
    # hae="0" is required on every vertex — ATAK silently ignores vertices without it
    vertices = "\n        ".join(
        f'<vertex lat="{pt[1]:.6f}" lon="{pt[0]:.6f}" hae="0"/>' for pt in lonlat_ring
    )
    return f"""<event version="2.0" uid="{uid}" type="u-d-f" how="h-e" access="Undefined"
       time="{_cot_time(now)}" start="{_cot_time(now)}" stale="{_cot_time(stale)}">
  <point lat="{center_lat:.6f}" lon="{center_lon:.6f}" hae="0.0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <shape>
      <polyline closed="true">
        {vertices}
      </polyline>
    </shape>
    <color value="{stroke}"/>
    <strokeColor value="{stroke}"/>
    <strokeWeight value="3.0"/>
    <strokeStyle value="solid"/>
    <fillColor value="{fill}"/>
    <archive/>
    <remarks>{label}</remarks>
    <contact callsign="WMD PLOTTER"/>
    <uid Droid="WMD PLOTTER"/>
    <marti><dest callsign="All Streaming"/></marti>
  </detail>
</event>"""


def point_cot_event(lat: float, lon: float, callsign: str = "WMD PLOTTER") -> str:
    """Simple SA marker (type a-f-G) for connectivity testing."""
    now   = datetime.now(timezone.utc)
    stale = now + timedelta(hours=1)
    uid   = f"wmd-test-{int(now.timestamp())}"
    return f"""<event version="2.0" uid="{uid}" type="a-f-G" how="h-e"
       time="{_cot_time(now)}" start="{_cot_time(now)}" stale="{_cot_time(stale)}">
  <point lat="{lat:.6f}" lon="{lon:.6f}" hae="0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <contact callsign="{callsign}"/>
    <uid Droid="{callsign}"/>
    <remarks>WMD PLOTTER connectivity test</remarks>
    <marti><dest callsign="All Streaming"/></marti>
  </detail>
</event>"""


def build_cot_xml(overlay_state: dict) -> str:
    """
    Generate a CoT XML document for all active overlays.
    Feed into ATAK via FreeTAKServer, WinTAK Network Link,
    or UDP broadcast to 239.2.3.1:6969.
    """
    events: list[str] = []

    for tool, state in overlay_state.items():
        if not state:
            continue
        src_lat = state.get("source_lat", 0.0)
        src_lon = state.get("source_lon", 0.0)

        for i, z in enumerate(state.get("zones", [])):
            lonlat = z.get("lonlat") or z.get("coords", [])
            if not lonlat:
                continue
            label = z.get("label") or z.get("level", tool)
            color = z.get("color", "#888888")
            uid   = f"wmd-{tool}-{z.get('level','z')}-{i}"
            events.append(_polygon_cot_event(uid, label, color, lonlat, src_lat, src_lon))

        for i, (level, info) in enumerate(state.get("contours", {}).items()):
            latlon = info.get("latlon", [])
            if not latlon:
                continue
            lonlat = [[pt[1], pt[0]] for pt in latlon]
            label  = info.get("label", f"{tool} {level}")
            color  = info.get("color", "#888888")
            uid    = f"wmd-{tool}-{level}-{i}"
            events.append(_polygon_cot_event(uid, label, color, lonlat, src_lat, src_lon))

    # <events> is the FreeTAK Server / WinTAK bulk-import container.
    # For ATAK UDP streaming send each <event> individually without wrapper.
    body = "\n\n".join(events)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<events>\n{body}\n</events>'
