"""
KML generator for WMD Plotter.

Produces:
  1. Full KML document with plume polygons (for static download).
  2. KML NetworkLink document that polls the live endpoint.

Spec: OGC KML 2.2 / Google Earth KML reference.
"""

from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers (KML uses AABBGGRR hex)
# ─────────────────────────────────────────────────────────────────────────────

def _hex_to_kml_color(hex_color: str, alpha_pct: int = 50) -> str:
    """
    Convert #RRGGBB to KML AABBGGRR format.
    alpha_pct: 0–100 fill opacity (100 = fully opaque, 0 = transparent).
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    aa = format(int(alpha_pct / 100 * 255), "02x")
    return f"{aa}{b}{g}{r}"


# ─────────────────────────────────────────────────────────────────────────────
# KML building blocks
# ─────────────────────────────────────────────────────────────────────────────

def _kml_style(style_id: str, hex_color: str, fill_alpha: int = 50) -> str:
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


def _latlon_to_kml_coords(latlon: list[tuple[float, float]], alt: float = 0) -> str:
    """Convert [(lat, lon), ...] to KML coordinates string (lon,lat,alt)."""
    parts = [f"{lon:.6f},{lat:.6f},{alt}" for lat, lon in latlon]
    return " ".join(parts)


def _placemark_polygon(
    name: str,
    description: str,
    style_id: str,
    latlon: list[tuple[float, float]],
) -> str:
    coords = _latlon_to_kml_coords(latlon)
    return f"""
  <Placemark>
    <name>{name}</name>
    <description><![CDATA[{description}]]></description>
    <styleUrl>#{style_id}</styleUrl>
    <Polygon>
      <extrude>0</extrude>
      <altitudeMode>clampToGround</altitudeMode>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>{coords}</coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>"""


def _placemark_point(
    name: str,
    description: str,
    lat: float,
    lon: float,
) -> str:
    return f"""
  <Placemark>
    <name>{name}</name>
    <description><![CDATA[{description}]]></description>
    <Style>
      <IconStyle>
        <color>ff0000ff</color>
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


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def build_plume_kml(
    source_lat: float,
    source_lon: float,
    chemical_name: str,
    contours: dict,            # from dispersion.compute_all_contours()
    wind_speed_ms: float,
    wind_dir_from_deg: float,
    stability_class: str,
    release_rate_gs: float,
    release_height_m: float,
    weather_desc: str = "",
) -> str:
    """
    Build a complete KML document with plume contours.

    contours: {"low": {..., "latlon": [...], "label": str, "color": str, "max_downwind_m": float},
               "medium": {...}, "high": {...}}
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wind_mph = wind_speed_ms * 2.237

    # Build styles
    styles = ""
    for level, info in contours.items():
        if info.get("latlon"):
            style_id = f"style_{level}"
            fill_alpha = {"low": 35, "medium": 45, "high": 55}.get(level, 40)
            styles += _kml_style(style_id, info["color"], fill_alpha)

    # Build placemarks
    placemarks = ""

    # Source marker
    source_desc = (
        f"<b>Chemical:</b> {chemical_name}<br/>"
        f"<b>Release rate:</b> {release_rate_gs:.1f} g/s ({release_rate_gs/1000*60:.2f} kg/min)<br/>"
        f"<b>Height:</b> {release_height_m:.0f} m<br/>"
        f"<b>Wind:</b> {wind_mph:.1f} mph from {wind_dir_from_deg:.0f}°<br/>"
        f"<b>Stability:</b> Pasquill-Gifford {stability_class}<br/>"
        f"<b>Weather:</b> {weather_desc}<br/>"
        f"<b>Generated:</b> {now}"
    )
    placemarks += _placemark_point(
        name=f"⚠ INCIDENT: {chemical_name}",
        description=source_desc,
        lat=source_lat,
        lon=source_lon,
    )

    # Plume polygons (outermost first for visual layering)
    level_order = ["low", "medium", "high"]
    for level in level_order:
        info = contours.get(level, {})
        if not info.get("latlon"):
            continue
        style_id = f"style_{level}"
        downwind_km = info["max_downwind_m"] / 1000
        width_km = info["max_width_m"] / 1000
        desc = (
            f"<b>{info['label']}</b><br/>"
            f"Threshold: {info['threshold_ppm']:.4g} ppm<br/>"
            f"Max downwind: {downwind_km:.2f} km<br/>"
            f"Max width: {width_km:.2f} km"
        )
        placemarks += _placemark_polygon(
            name=info["label"],
            description=desc,
            style_id=style_id,
            latlon=info["latlon"],
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>WMD Plotter — {chemical_name} Plume</name>
  <description><![CDATA[
    Gaussian plume dispersion model.<br/>
    Chemical: {chemical_name}<br/>
    Generated: {now}<br/>
    Wind: {wind_mph:.1f} mph from {wind_dir_from_deg:.0f}°<br/>
    PG Stability: {stability_class}<br/>
    <b>FOR PLANNING USE ONLY — NOT OFFICIAL EMERGENCY GUIDANCE</b>
  ]]></description>
  <open>1</open>
  {styles}
  {placemarks}
</Document>
</kml>"""


def build_network_link_kml(
    live_kml_url: str,
    refresh_interval_seconds: int = 30,
) -> str:
    """
    Build a KML NetworkLink document.
    Google Earth / ArcGIS polls live_kml_url every refresh_interval_seconds.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<NetworkLink>
  <name>WMD Plotter — Live Plume Feed</name>
  <description>Live plume overlay from WMD Plotter. Refreshes every {refresh_interval_seconds}s.</description>
  <open>1</open>
  <Link>
    <href>{live_kml_url}</href>
    <refreshMode>onInterval</refreshMode>
    <refreshInterval>{refresh_interval_seconds}</refreshInterval>
    <viewRefreshMode>never</viewRefreshMode>
  </Link>
</NetworkLink>
</kml>"""
