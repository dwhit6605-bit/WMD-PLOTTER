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
from datetime import datetime, timezone


_MANIFEST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<MissionPackageManifest version="2">
  <Configuration>
    <Parameter name="uid" value="{uid}"/>
    <Parameter name="name" value="{name}"/>
    <Parameter name="onReceiveDelete" value="false"/>
  </Configuration>
  <Contents>
    <Content ignore="false" zipEntry="files/{kml_filename}">
      <Parameter name="contentType" value="KML"/>
      <Parameter name="name" value="{kml_display_name}"/>
    </Content>
  </Contents>
</MissionPackageManifest>
"""


def build_tak_data_package(kml_bytes: bytes, active_tools: list[str]) -> tuple[bytes, str]:
    """
    Wrap KML bytes in a TAK Data Package ZIP.

    Returns (zip_bytes, suggested_filename).
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tool_tag = "_".join(active_tools) if active_tools else "scenario"
    pkg_name = f"WMD_PLOTTER_{tool_tag}_{ts}"
    kml_filename = f"{pkg_name}.kml"
    pkg_uid = str(uuid.uuid4())

    manifest = _MANIFEST_TEMPLATE.format(
        uid=pkg_uid,
        name=f"WMD PLOTTER — {tool_tag.replace('_', ' ').upper()} {ts}",
        kml_filename=kml_filename,
        kml_display_name=f"WMD PLOTTER Hazard Zones ({ts})",
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("MANIFEST/manifest.xml", manifest.encode("utf-8"))
        zf.writestr(f"files/{kml_filename}", kml_bytes)
    buf.seek(0)

    return buf.read(), f"{pkg_name}.zip"
