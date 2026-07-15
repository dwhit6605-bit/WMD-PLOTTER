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
from typing import Optional


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


_TOOL_HAZARD_LABEL = {
    "plume":      "CHEM",
    "radiation":  "RAD",
    "blast":      "BLAST",
    "bleve":      "BLEVE",
    "erg":        "HAZMAT",
    "dense_gas":  "DGAS",
    "fire_smoke": "FIRE",
}


def incident_sa_cot_event(lat: float, lon: float, tool: str,
                           agent_name: str = "", callsign: str = "WMD PLOTTER",
                           release_rate_gs: float = 0.0,
                           wind_speed_ms: float = 0.0, wind_dir_label: str = "",
                           stability_class: str = "") -> str:
    """SA marker (type a-h-G, red) at the incident origin with full CBRN detail in remarks."""
    hazard = _TOOL_HAZARD_LABEL.get(tool, "HAZMAT")
    label  = f"WMD-{hazard}"
    if agent_name:
        label += f"/{agent_name[:14]}"
    now   = datetime.now(timezone.utc)
    stale = now + timedelta(hours=8)
    uid   = f"wmd-incident-{tool}-{int(now.timestamp())}"

    parts = [f"AGENT: {agent_name}"] if agent_name else []
    if release_rate_gs > 0:
        parts.append(f"RATE: {release_rate_gs / 1000 * 60:.2f} kg/min")
    if wind_speed_ms > 0:
        spd_mph = wind_speed_ms * 2.237
        parts.append(f"WIND: {wind_dir_label} {spd_mph:.1f} mph")
    if stability_class:
        parts.append(f"PG-{stability_class}")
    parts.append(f"TIME: {now.strftime('%Y-%m-%d %H:%M')} UTC")
    remarks = f"WMD PLOTTER | {hazard} INCIDENT | " + " | ".join(parts)

    return f"""<event version="2.0" uid="{uid}" type="a-h-G" how="h-e"
       time="{_cot_time(now)}" start="{_cot_time(now)}" stale="{_cot_time(stale)}">
  <point lat="{lat:.6f}" lon="{lon:.6f}" hae="0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <contact callsign="{label}"/>
    <uid Droid="{label}"/>
    <remarks>{remarks}</remarks>
    <archive/>
    <marti><dest callsign="All Streaming"/></marti>
  </detail>
</event>"""


# CoT type per facility category — best-fit MIL-STD-2525C atom types
_FAC_COT_TYPE: dict[str, str] = {
    "hospital":    "a-f-G-E-V-M",  # friendly · ground · medical
    "school":      "a-f-G-C-I",    # friendly · ground · civilian installation
    "refinery":    "a-n-G-I-U-E",  # neutral  · ground · industrial · utility · petroleum
    "chemical":    "a-n-G-I-U-E",
    "industrial":  "a-n-G-I-U-E",
    "water":       "a-n-G-I-U-W",  # neutral  · ground · industrial · utility · water
    "power":       "a-n-G-I-U-E",
}

_FAC_PREFIX: dict[str, str] = {
    "hospital":   "HOSP",
    "school":     "SCHL",
    "refinery":   "REF",
    "chemical":   "CHEM",
    "industrial": "IND",
    "water":      "WATR",
    "power":      "PWR",
}


def facility_cot_event(lat: float, lon: float, name: str,
                        fac_type: str, notes: str = "") -> str:
    """SA point for a facility from the facility library — typed by category."""
    cot_type = _FAC_COT_TYPE.get(fac_type, "a-n-G")
    prefix   = _FAC_PREFIX.get(fac_type, "FAC")
    callsign = f"{prefix}·{name[:24]}"
    now   = datetime.now(timezone.utc)
    stale = now + timedelta(hours=24)
    uid   = f"wmd-fac-{abs(hash(name + fac_type)) % 0xFFFFFF:06x}"
    remarks = notes[:200] if notes else f"{fac_type.title()} facility"
    return f"""<event version="2.0" uid="{uid}" type="{cot_type}" how="h-e"
       time="{_cot_time(now)}" start="{_cot_time(now)}" stale="{_cot_time(stale)}">
  <point lat="{lat:.6f}" lon="{lon:.6f}" hae="0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <contact callsign="{callsign}"/>
    <uid Droid="{callsign}"/>
    <remarks>{remarks}</remarks>
    <archive/>
    <marti><dest callsign="All Streaming"/></marti>
  </detail>
</event>"""


def line_cot_event(uid: str, label: str, color: str, latlngs: list) -> str:
    """
    CoT polyline event for ATAK drawn lines (evac routes, roads).
    Uses type u-d-f + closed="false" — same type as filled polygons but
    open, which is how ATAK natively represents drawn line segments.
    latlngs: list of [lat, lon] pairs.
    """
    now   = datetime.now(timezone.utc)
    stale = now + timedelta(hours=8)
    stroke = _hex_to_argb_int(color, 220)
    fill   = _hex_to_argb_int(color, 0)   # transparent fill for lines
    vertices = "\n        ".join(
        f'<vertex lat="{pt[0]:.6f}" lon="{pt[1]:.6f}" hae="0"/>' for pt in latlngs
    )
    return f"""<event version="2.0" uid="{uid}" type="u-d-f" how="h-e"
       time="{_cot_time(now)}" start="{_cot_time(now)}" stale="{_cot_time(stale)}">
  <point lat="{latlngs[0][0]:.6f}" lon="{latlngs[0][1]:.6f}" hae="0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <shape>
      <polyline closed="false">
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


def bftr_cot_event(filename: str, url: str, sha256: str, size_bytes: int,
                   contact_uid: Optional[str] = None) -> str:
    """
    Build a b-f-t-r (file transfer request) CoT event.
    ATAK receives this and auto-downloads the file at `url`.
    If contact_uid is None, sends to "All Streaming" (broadcast).
    """
    now = datetime.now(timezone.utc)
    stale = now + timedelta(hours=1)
    uid_suffix = contact_uid or "broadcast"
    marti_dest = (f'<dest uid="{contact_uid}"/>' if contact_uid
                  else '<dest callsign="All Streaming"/>')
    return f"""<event version="2.0" uid="wmd-bftr-{int(now.timestamp())}-{uid_suffix}" type="b-f-t-r"
       time="{_cot_time(now)}" start="{_cot_time(now)}" stale="{_cot_time(stale)}" how="h-g-i-g-o">
  <point lat="0.0" lon="0.0" hae="0.0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <fileshare filename="{filename}" senderUrl="{url}" sha256="{sha256}"
               sizeInBytes="{size_bytes}" senderUid="WMD-PLOTTER"
               senderCallsign="WMD PLOTTER" name="{filename}"/>
    <marti>{marti_dest}</marti>
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
