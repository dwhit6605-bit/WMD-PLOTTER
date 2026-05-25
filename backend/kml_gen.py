"""
KML generator for WHITWERX Model Display (WMD).

Produces:
  1. Combined KML document (all active overlays in named folders).
  2. KML NetworkLink document that polls the live endpoint.

Adding a new tool: implement _<tool>_folder(state) → str, register it
in _FOLDER_BUILDERS, and write to overlay_state["<tool>"] in main.py.

Spec: OGC KML 2.2 / Google Earth KML reference.
"""

from datetime import datetime, timezone


# ── Colour helpers (KML uses AABBGGRR hex) ────────────────────────────────────

def _hex_to_kml_color(hex_color: str, alpha_pct: int = 50) -> str:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    aa = format(int(alpha_pct / 100 * 255), "02x")
    return f"{aa}{b}{g}{r}"


# ── KML building blocks ───────────────────────────────────────────────────────

def _kml_style(style_id: str, hex_color: str, fill_alpha: int = 50,
               dash: bool = False) -> str:
    line_color = _hex_to_kml_color(hex_color, 100)
    poly_color = _hex_to_kml_color(hex_color, fill_alpha)
    return f"""
  <Style id="{style_id}">
    <LineStyle>
      <color>{line_color}</color>
      <width>2</width>
    </LineStyle>
    <PolyStyle>
      <color>{poly_color}</color>
      <fill>1</fill>
      <outline>1</outline>
    </PolyStyle>
  </Style>"""


def _latlon_ring_to_kml(latlon: list) -> str:
    """[(lat, lon), ...] → KML coordinates string (lon,lat,0)."""
    return " ".join(f"{lon:.6f},{lat:.6f},0" for lat, lon in latlon)


def _lonlat_ring_to_kml(lonlat: list) -> str:
    """[[lon, lat], ...] → KML coordinates string (lon,lat,0)."""
    return " ".join(f"{pt[0]:.6f},{pt[1]:.6f},0" for pt in lonlat)


def _polygon_placemark(name: str, desc: str, style_id: str, coords_str: str) -> str:
    return f"""
  <Placemark>
    <name>{name}</name>
    <description><![CDATA[{desc}]]></description>
    <styleUrl>#{style_id}</styleUrl>
    <Polygon>
      <extrude>0</extrude>
      <altitudeMode>clampToGround</altitudeMode>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>{coords_str}</coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>"""


def _point_placemark(name: str, desc: str, lat: float, lon: float,
                     icon_color: str = "ff0000ff") -> str:
    return f"""
  <Placemark>
    <name>{name}</name>
    <description><![CDATA[{desc}]]></description>
    <Style>
      <IconStyle>
        <color>{icon_color}</color>
        <scale>1.2</scale>
        <Icon>
          <href>https://maps.google.com/mapfiles/kml/shapes/placemark_circle_highlight.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Point>
      <coordinates>{lon:.6f},{lat:.6f},0</coordinates>
    </Point>
  </Placemark>"""


# ── Per-tool folder builders ──────────────────────────────────────────────────

def _plume_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a plume overlay state."""
    now       = state.get("computed_at", "")
    chem      = state["chemical_name"]
    contours  = state["contours"]
    wind_ms   = state["wind_speed_ms"]
    wind_from = state["wind_dir_from_deg"]
    stab      = state["stability_class"]
    Q_gs      = state["release_rate_gs"]
    H_m       = state["release_height_m"]
    wx_desc   = state.get("weather_desc", "")
    wind_mph  = wind_ms * 2.237

    styles = ""
    for level, info in contours.items():
        if info.get("latlon"):
            fill_alpha = {"low": 35, "medium": 45, "high": 55}.get(level, 40)
            styles += _kml_style(f"plume_{level}", info["color"], fill_alpha)

    source_desc = (
        f"<b>Chemical:</b> {chem}<br/>"
        f"<b>Release rate:</b> {Q_gs:.1f} g/s ({Q_gs/1000*60:.2f} kg/min)<br/>"
        f"<b>Height:</b> {H_m:.0f} m<br/>"
        f"<b>Wind:</b> {wind_mph:.1f} mph from {wind_from:.0f}°<br/>"
        f"<b>Stability:</b> PG-{stab}<br/>"
        f"<b>Weather:</b> {wx_desc}<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name=f"⚠ INCIDENT: {chem}",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
    )

    level_order = ["low", "medium", "high"]
    for level in level_order:
        info = contours.get(level, {})
        if not info.get("latlon"):
            continue
        desc = (
            f"<b>{info['label']}</b><br/>"
            f"Threshold: {info['threshold_ppm']:.4g} ppm<br/>"
            f"Max downwind: {info['max_downwind_m']/1000:.2f} km<br/>"
            f"Max width: {info['max_width_m']/1000:.2f} km"
        )
        coords = _latlon_ring_to_kml(info["latlon"])
        placemarks += _polygon_placemark(info["label"], desc, f"plume_{level}", coords)

    folder = f"""
  <Folder>
    <name>Chemical Plume — {chem}</name>
    <description><![CDATA[Gaussian plume (PG-{stab}) · {wind_mph:.1f} mph from {wind_from:.0f}°]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


def _blast_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a blast overlay state."""
    exp_name  = state.get("explosive_name", state.get("explosive_id", "Unknown"))
    weight_kg = state["weight_kg"]
    W_tnt     = state["W_tnt_kg"]
    now       = state.get("computed_at", "")

    styles = ""
    for zone in state.get("zones", []):
        styles += _kml_style(f"blast_{zone['level']}", zone["color"], 20)

    source_desc = (
        f"<b>Explosive:</b> {exp_name}<br/>"
        f"<b>Yield:</b> {weight_kg:.1f} kg<br/>"
        f"<b>TNT equiv:</b> {W_tnt:.2f} kg<br/>"
        f"<b>Model:</b> Brode (1955) / Hopkinson-Cranz<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name="💥 DETONATION POINT",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff0000cc",
    )

    for zone in reversed(state.get("zones", [])):
        coords = _lonlat_ring_to_kml(zone["lonlat"])
        desc = (
            f"<b>{zone['label']}</b><br/>"
            f"{zone['psi']} psi / {zone['kPa']} kPa<br/>"
            f"Radius: {zone['radius_km']:.3f} km ({zone['radius_m']:.0f} m)<br/>"
            f"{zone['desc']}"
        )
        placemarks += _polygon_placemark(zone["label"], desc, f"blast_{zone['level']}", coords)

    folder = f"""
  <Folder>
    <name>Blast Zones — {exp_name} ({weight_kg:.1f} kg)</name>
    <description><![CDATA[{W_tnt:.2f} kg TNT equiv · Brode (1955) model]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


# Registry: map overlay_state key → folder builder function.
# To add a new tool: implement _<tool>_folder(state) and add it here.
_FOLDER_BUILDERS: dict = {
    "plume": _plume_folder,
    "blast": _blast_folder,
}


# ── Public API ────────────────────────────────────────────────────────────────

def build_combined_kml(overlay_state: dict) -> str:
    """
    Build a single KML document combining all active overlays.
    overlay_state: {"plume": {...} or {}, "blast": {...} or {}, ...}
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_styles = ""
    all_folders = ""
    active = []

    for key, builder in _FOLDER_BUILDERS.items():
        state = overlay_state.get(key, {})
        if not state:
            continue
        try:
            styles, folder = builder(state)
            all_styles  += styles
            all_folders += folder
            active.append(key.title())
        except Exception:
            pass

    active_str = " + ".join(active) if active else "No active overlays"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>WHITWERX WMD Display — {active_str}</name>
  <description><![CDATA[
    <b>WHITWERX Model Display (WMD)</b><br/>
    Active overlays: {active_str}<br/>
    Generated: {now}<br/>
    <b>FOR PLANNING USE ONLY — NOT OFFICIAL EMERGENCY GUIDANCE</b>
  ]]></description>
  <open>1</open>
  {all_styles}
  {all_folders}
</Document>
</kml>"""


def build_network_link_kml(live_kml_url: str, refresh_interval_seconds: int = 30) -> str:
    """KML NetworkLink — Google Earth polls live_kml_url on an interval."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<NetworkLink>
  <name>WHITWERX WMD Display — Live Overlays</name>
  <description>Live overlays from WHITWERX Model Display. Refreshes every {refresh_interval_seconds}s.</description>
  <open>1</open>
  <Link>
    <href>{live_kml_url}</href>
    <refreshMode>onInterval</refreshMode>
    <refreshInterval>{refresh_interval_seconds}</refreshInterval>
    <viewRefreshMode>never</viewRefreshMode>
  </Link>
</NetworkLink>
</kml>"""


# Keep the old function name for any direct callers (delegates to combined builder).
def build_plume_kml(source_lat, source_lon, chemical_name, contours,
                    wind_speed_ms, wind_dir_from_deg, stability_class,
                    release_rate_gs, release_height_m, weather_desc="") -> str:
    state = {
        "source_lat": source_lat, "source_lon": source_lon,
        "chemical_name": chemical_name, "contours": contours,
        "wind_speed_ms": wind_speed_ms, "wind_dir_from_deg": wind_dir_from_deg,
        "stability_class": stability_class, "release_rate_gs": release_rate_gs,
        "release_height_m": release_height_m, "weather_desc": weather_desc,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    return build_combined_kml({"plume": state})
