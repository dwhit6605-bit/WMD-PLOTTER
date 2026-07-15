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


# ── XML / string helpers ─────────────────────────────────────────────────────

def _xml_escape(s: str) -> str:
    """Escape a string for safe insertion into an XML element (not inside CDATA)."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


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
    <name>{_xml_escape(name)}</name>
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
    <name>{_xml_escape(name)}</name>
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
        name=f"[CHEM] INCIDENT: {chem}",
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
        name="[EXP] DETONATION POINT",
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


def _bleve_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a BLEVE overlay state."""
    fuel_name = state.get("fuel_name", state.get("fuel_id", "Unknown"))
    mass_kg   = state["mass_kg"]
    fb        = state.get("fireball", {})
    now       = state.get("computed_at", "")

    styles = ""
    for zone in state.get("zones", []):
        styles += _kml_style(f"bleve_{zone['level']}", zone["color"], 20)

    source_desc = (
        f"<b>Fuel:</b> {fuel_name}<br/>"
        f"<b>Mass:</b> {mass_kg:.1f} kg<br/>"
        f"<b>Fireball radius:</b> {fb.get('radius_m',0):.0f} m<br/>"
        f"<b>Fireball duration:</b> {fb.get('duration_s',0):.1f} s<br/>"
        f"<b>SEP:</b> {fb.get('sep_kwm2',0)} kW/m²<br/>"
        f"<b>Model:</b> Roberts (1982) BLEVE fireball<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name="[BLEVE] FIREBALL SOURCE",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff0066cc",
    )

    for zone in reversed(state.get("zones", [])):
        coords = _lonlat_ring_to_kml(zone["lonlat"])
        desc = (
            f"<b>{zone['label']}</b><br/>"
            f"{('q = '+str(zone['q_kwm2'])+' kW/m²') if zone.get('q_kwm2') else 'Fireball zone'}<br/>"
            f"Radius: {zone['radius_km']:.3f} km ({zone['radius_m']:.0f} m)<br/>"
            f"{zone.get('desc', '')}"
        )
        placemarks += _polygon_placemark(zone["label"], desc, f"bleve_{zone['level']}", coords)

    folder = f"""
  <Folder>
    <name>BLEVE Thermal Zones — {fuel_name} ({mass_kg:.0f} kg)</name>
    <description><![CDATA[Roberts (1982) fireball · r={fb.get('radius_m',0):.0f} m · {fb.get('duration_s',0):.1f} s]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


def _radiation_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a radiation overlay state."""
    nuclide   = state["radionuclide_name"]
    symbol    = state.get("radionuclide_symbol", nuclide)
    Q_ci_s    = state["release_rate_ci_s"]
    wind_ms   = state["wind_speed_ms"]
    wind_from = state["wind_dir_from_deg"]
    stab      = state["stability_class"]
    H_m       = state["release_height_m"]
    dcf       = state["dcf_cloud"]
    now       = state.get("computed_at", "")
    wind_mph  = wind_ms * 2.237
    contours  = state["contours"]

    styles = ""
    for level, info in contours.items():
        if info.get("latlon"):
            styles += _kml_style(f"rad_{level}", info["color"], 30)

    source_desc = (
        f"<b>Radionuclide:</b> {nuclide} ({symbol})<br/>"
        f"<b>Release rate:</b> {Q_ci_s*60:.4g} Ci/min ({Q_ci_s:.4g} Ci/s)<br/>"
        f"<b>Height:</b> {H_m:.0f} m<br/>"
        f"<b>DCF (cloudshine):</b> {dcf:,} mSv/hr per Ci/m³<br/>"
        f"<b>Wind:</b> {wind_mph:.1f} mph from {wind_from:.0f}°<br/>"
        f"<b>Stability:</b> PG-{stab}<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name=f"[RAD] SOURCE: {symbol}",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff2800c8",
    )

    zone_order = ["extreme", "high", "worker", "pag"]
    for level in zone_order:
        info = contours.get(level, {})
        if not info.get("latlon"):
            continue
        desc = (
            f"<b>{info['label']}</b><br/>"
            f"Dose rate: {info['dose_msvhr']} mSv/hr<br/>"
            f"Max downwind: {info['max_downwind_m']/1000:.2f} km<br/>"
            f"Max width: {info['max_width_m']/1000:.2f} km<br/>"
            f"{info.get('desc','')}"
        )
        coords = _latlon_ring_to_kml(info["latlon"])
        placemarks += _polygon_placemark(info["label"], desc, f"rad_{level}", coords)

    folder = f"""
  <Folder>
    <name>Radiation Zones — {symbol}</name>
    <description><![CDATA[Cloudshine dose rates (EPA FGR-12) · PG-{stab} · {wind_mph:.1f} mph from {wind_from:.0f}°]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


def _erg_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for an ERG overlay state."""
    un    = state.get("un_number", "????")
    name  = state.get("name", "Unknown")
    size  = state.get("spill_size", "small").title()
    guide = state.get("guide", "—")
    sz    = state.get(state.get("spill_size", "small"), {})
    now   = state.get("computed_at", "")

    COLOR_MAP = {
        "isolation": "#FF2200",
        "pad_day":   "#FFAA00",
        "pad_night": "#FF4400",
    }

    styles = ""
    placemarks = _point_placemark(
        name=f"[ERG] SPILL SOURCE UN{un}",
        desc=(
            f"<b>UN{un}</b> - {name}<br/>"
            f"<b>Guide:</b> #{guide}<br/>"
            f"<b>Spill size:</b> {size}<br/>"
            f"<b>Isolation:</b> {sz.get('isolation_m', '?')} m<br/>"
            f"<b>PAD (day):</b> {sz.get('day_pad_km', '?')} km<br/>"
            f"<b>PAD (night):</b> {sz.get('night_pad_km', '?')} km<br/>"
            f"<b>Source:</b> ERG 2024 Table 1 / DOT/PHMSA<br/>"
            f"<b>Computed:</b> {now}"
        ),
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff0000ff",
    )

    level_order = ["pad_night", "pad_day", "isolation"]
    for level in level_order:
        zone = next((z for z in state.get("zones", []) if z.get("level") == level), None)
        if not zone:
            continue
        color = COLOR_MAP.get(level, "#888888")
        styles += _kml_style(f"erg_{level}", color, 25)
        coords = _lonlat_ring_to_kml(zone["lonlat"])
        r_m = zone.get("radius_m", 0)
        desc = (
            f"<b>{zone['label']}</b><br/>"
            f"Radius: {r_m} m ({r_m/1000:.2f} km)<br/>"
            f"{zone.get('desc', '')}"
        )
        placemarks += _polygon_placemark(zone["label"], desc, f"erg_{level}", coords)

    folder = f"""
  <Folder>
    <name>ERG Zones UN{un} {_xml_escape(name)} ({size})</name>
    <description><![CDATA[ERG 2024 Table 1 - Initial Isolation & Protective Action Distances - Guide #{guide}]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


def _dense_gas_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a dense-gas overlay state."""
    gas_name  = state.get("gas_name",    state.get("gas_id", "Unknown"))
    formula   = state.get("gas_formula", "")
    rate_kpm  = state.get("release_rate_kg_min", 0)
    H_m       = state.get("release_height_m", 0)
    wind_ms   = state.get("wind_speed_ms", 0)
    wind_from = state.get("wind_dir_from_deg", 0)
    stab      = state.get("stability_class", "D")
    now       = state.get("computed_at", "")
    wind_mph  = wind_ms * 2.237

    styles = ""
    for zone in state.get("zones", []):
        styles += _kml_style(f"dg_{zone['level']}", zone["color"], 25)

    source_desc = (
        f"<b>Gas:</b> {gas_name} ({formula})<br/>"
        f"<b>Release rate:</b> {rate_kpm:.1f} kg/min<br/>"
        f"<b>Height:</b> {H_m:.0f} m<br/>"
        f"<b>Wind:</b> {wind_mph:.1f} mph from {wind_from:.0f}°<br/>"
        f"<b>Stability:</b> PG-{stab}<br/>"
        f"<b>Model:</b> Modified Pasquill-Gifford (dense-gas σ_z)<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name=f"[DG] DENSE GAS: {gas_name}",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff00aaff",
    )

    for zone in state.get("zones", []):
        if not zone.get("lonlat"):
            continue
        coords = _lonlat_ring_to_kml(zone["lonlat"])
        desc = (
            f"<b>{zone['label']}</b><br/>"
            f"Threshold: {zone.get('threshold_ppm', '?')} ppm<br/>"
            f"Max downwind: {zone.get('max_downwind_km', 0):.2f} km<br/>"
            f"Max width: {zone.get('max_width_km', 0):.2f} km"
        )
        placemarks += _polygon_placemark(zone["label"], desc, f"dg_{zone['level']}", coords)

    folder = f"""
  <Folder>
    <name>Dense Gas — {gas_name} ({rate_kpm:.1f} kg/min)</name>
    <description><![CDATA[Modified PG dispersion · PG-{stab} · {wind_mph:.1f} mph from {wind_from:.0f}°]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


def _fire_smoke_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a fire/smoke overlay state."""
    fire_name = state.get("fire_name", state.get("fire_type_id", "Unknown"))
    hrr_mw    = state.get("hrr_mw", 0)
    wind_ms   = state.get("wind_speed_ms", 0)
    wind_from = state.get("wind_dir_from_deg", 0)
    stab      = state.get("stability_class", "D")
    now       = state.get("computed_at", "")
    wind_mph  = wind_ms * 2.237

    styles = ""
    for zone in state.get("zones", []):
        styles += _kml_style(f"fs_{zone['level']}", zone["color"], 25)

    source_desc = (
        f"<b>Fire type:</b> {fire_name}<br/>"
        f"<b>HRR:</b> {hrr_mw:.0f} MW<br/>"
        f"<b>Wind:</b> {wind_mph:.1f} mph from {wind_from:.0f}°<br/>"
        f"<b>Stability:</b> PG-{stab}<br/>"
        f"<b>Model:</b> Briggs (1975) buoyant plume + Gaussian<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name=f"[FIRE] {fire_name}",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff0055ff",
    )

    for zone in state.get("zones", []):
        if not zone.get("lonlat"):
            continue
        coords = _lonlat_ring_to_kml(zone["lonlat"])
        poll = zone.get("type", "smoke")
        if poll == "smoke_pm25":
            thresh_str = f"PM2.5: {zone.get('threshold_ugm3', '?')} µg/m³"
        else:
            thresh_str = f"CO: {zone.get('threshold_ppm', '?')} ppm"
        desc = (
            f"<b>{zone['label']}</b><br/>"
            f"{thresh_str}<br/>"
            f"Max downwind: {zone.get('max_downwind_km', 0):.2f} km<br/>"
            f"Max width: {zone.get('max_width_km', 0):.2f} km"
        )
        placemarks += _polygon_placemark(zone["label"], desc, f"fs_{zone['level']}", coords)

    folder = f"""
  <Folder>
    <name>Fire / Smoke — {fire_name} ({hrr_mw:.0f} MW)</name>
    <description><![CDATA[Briggs (1975) buoyant plume · PG-{stab} · {wind_mph:.1f} mph from {wind_from:.0f}°]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


def _population_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a population exposure overlay state."""
    county  = state.get("county_name", "Unknown")
    density = state.get("pop_density_per_km2", 0)
    source  = state.get("data_source", "")
    now     = state.get("computed_at", "")
    zones   = state.get("zones", [])

    total_pop = sum(z.get("pop_estimate", 0) for z in zones)

    styles = ""
    for i, zone in enumerate(zones):
        styles += _kml_style(f"pop_{i}", zone.get("color", "#888888"), 20)

    source_desc = (
        f"<b>County:</b> {county}<br/>"
        f"<b>Pop density:</b> {density:.1f} people/km²<br/>"
        f"<b>Total estimated exposed:</b> ~{total_pop:,}<br/>"
        f"<b>Source:</b> {source}<br/>"
        f"<b>Computed:</b> {now}"
    )
    placemarks = _point_placemark(
        name="[POP] EXPOSURE CENTER",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff00ffaa",
    )

    for i, zone in enumerate(zones):
        latlon = zone.get("latlon", [])
        if not latlon:
            continue
        coords = _latlon_ring_to_kml(latlon)
        desc = (
            f"<b>{zone['label']}</b><br/>"
            f"Estimated population: ~{zone.get('pop_estimate', 0):,}<br/>"
            f"Area: {zone.get('area_km2', 0):.2f} km²"
        )
        placemarks += _polygon_placemark(zone["label"], desc, f"pop_{i}", coords)

    folder = f"""
  <Folder>
    <name>Population Exposure — {county}</name>
    <description><![CDATA[~{total_pop:,} estimated exposed · {density:.0f} people/km² · {source}]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return styles, folder


# Infra type → (KML AABBGGRR icon color, human label)
_INFRA_KML_COLORS: dict[str, tuple[str, str]] = {
    "hospital":     ("ff4444ff", "Hospital"),
    "fire_station": ("ff0088ff", "Fire Station"),
    "police":       ("ffff8844", "Police Station"),
    "school":       ("ff44aa44", "School"),
    "nursing_home": ("ffaa88ff", "Care Facility"),
    "pharmacy":     ("ff88aa00", "Pharmacy"),
    "shelter":      ("ff006688", "Emergency Shelter"),
    "power_plant":  ("ff00aaff", "Power Plant"),
    "water_works":  ("ffff8800", "Water Treatment"),
    "government":   ("ff888888", "Government"),
    "military":     ("ff006644", "Military"),
    "fuel":         ("ff006688", "Gas Station"),
}


def _infra_folder(state: dict) -> tuple[str, str]:
    """Return (styles_xml, folder_xml) for a cached infrastructure overlay state."""
    radius = state.get("radius", 0)
    items  = state.get("items", [])
    now    = state.get("computed_at", "")

    source_desc = (
        f"<b>Search radius:</b> {radius/1000:.1f} km<br/>"
        f"<b>Facilities found:</b> {len(items)}<br/>"
        f"<b>Source:</b> OpenStreetMap / Overpass API<br/>"
        f"<b>Queried:</b> {now}"
    )
    placemarks = _point_placemark(
        name="[INFRA] SEARCH CENTER",
        desc=source_desc,
        lat=state["source_lat"],
        lon=state["source_lon"],
        icon_color="ff00ffaa",
    )

    for item in items:
        itype = item.get("type", "")
        icon_color, type_label = _INFRA_KML_COLORS.get(itype, ("ff888888", itype.replace("_", " ").title()))
        name     = item.get("name", type_label)
        dist_km  = item.get("distKm", 0)
        item_lat = item.get("lat", 0)
        item_lon = item.get("lon", 0)
        desc = (
            f"<b>{name}</b><br/>"
            f"Type: {type_label}<br/>"
            f"Distance from incident: {dist_km:.2f} km"
        )
        placemarks += _point_placemark(
            name=f"{name} ({type_label})",
            desc=desc,
            lat=item_lat,
            lon=item_lon,
            icon_color=icon_color,
        )

    folder = f"""
  <Folder>
    <name>Critical Infrastructure ({len(items)} facilities)</name>
    <description><![CDATA[{len(items)} facilities within {radius/1000:.1f} km · Source: OpenStreetMap]]></description>
    <open>1</open>
    {placemarks}
  </Folder>"""
    return "", folder


# Registry: map overlay_state key → folder builder function.
# To add a new tool: implement _<tool>_folder(state) and add it here.
_FOLDER_BUILDERS: dict = {
    "plume":     _plume_folder,
    "blast":     _blast_folder,
    "radiation": _radiation_folder,
    "bleve":     _bleve_folder,
    "erg":       _erg_folder,
    "dense_gas":  _dense_gas_folder,
    "fire_smoke": _fire_smoke_folder,
    "population": _population_folder,
    "infra":      _infra_folder,
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
<kml xmlns="http://www.opengis.net/kml/2.2"
     xmlns:atom="http://www.w3.org/2005/Atom">
<Document id="wmd-plotter-root">
  <name>{_xml_escape(f"WHITWERX WMD Display - {active_str}")}</name>
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


def build_timeseries_kml(steps: list, chemical_name: str,
                          source_lat: float, source_lon: float) -> str:
    """
    Build a time-stamped KML for a 24-hr NWS plume time series.
    Each hour gets its own <Folder> with a <TimeSpan> so ATAK's / Google
    Earth's time slider animates through the hourly forecast plumes.

    steps: list of dicts from POST /api/plume/timeseries — each must have
      start_time (ISO-8601), wind_speed_mph, wind_dir_label, stability_class,
      short_forecast, geojson.features (plume contour polygons).
    """
    from datetime import timedelta
    import re

    def _iso_to_kml(iso: str) -> str:
        return iso.replace("+00:00", "Z").rstrip("Z") + "Z"

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    level_colors = {"high": "#f85149", "medium": "#FF8C00", "low": "#FFD700"}
    level_fill   = {"high": 55, "medium": 45, "low": 35}

    # Collect all unique styles once (same 3 levels repeat each hour)
    all_styles = ""
    for level, color in level_colors.items():
        all_styles += _kml_style(f"ts_{level}", color, level_fill[level])

    # Source point
    source_pm = _point_placemark(
        name=f"[CHEM] {chemical_name} — Source",
        desc=f"<b>{chemical_name}</b><br/>24-hr NWS forecast plume time series<br/>Generated: {now_str}",
        lat=source_lat,
        lon=source_lon,
    )

    hour_folders = ""
    for step in steps:
        hour      = step["hour"]
        t_begin   = _iso_to_kml(step["start_time"])
        # stale after next hour
        t_end_re  = re.sub(r'T(\d{2}):', lambda m: f"T{(int(m.group(1))+1)%24:02d}:", t_begin, count=1)

        wind_label = f"{step['wind_dir_label']} {step['wind_speed_mph']:.1f} mph · PG-{step['stability_class']}"
        folder_name = f"+{hour}h · {wind_label}"
        placemarks = ""

        for feat in step.get("geojson", {}).get("features", []):
            props = feat.get("properties", {})
            level = props.get("level")
            if not level:
                continue
            coords_list = feat.get("geometry", {}).get("coordinates", [[]])
            if not coords_list:
                continue
            ring = coords_list[0]
            coords_str = " ".join(f"{pt[0]:.6f},{pt[1]:.6f},0" for pt in ring)
            desc = (
                f"<b>{props.get('label','')}</b><br/>"
                f"Max downwind: {props.get('max_downwind_m',0)/1000:.2f} km<br/>"
                f"Wind: {wind_label}<br/>"
                f"Forecast: {step.get('short_forecast','')}"
            )
            placemarks += _polygon_placemark(
                name=props.get("label", level),
                desc=desc,
                style_id=f"ts_{level}",
                coords_str=coords_str,
            )

        if not placemarks:
            placemarks = "<!-- no contours this hour -->"

        hour_folders += f"""
  <Folder>
    <name>{_xml_escape(folder_name)}</name>
    <TimeSpan><begin>{t_begin}</begin><end>{t_end_re}</end></TimeSpan>
    <visibility>0</visibility>
    {placemarks}
  </Folder>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document id="wmd-timeseries-root">
  <name>{_xml_escape(f"WMD PLOTTER — {chemical_name} 24-hr Forecast Plumes")}</name>
  <description><![CDATA[
    <b>WHITWERX WMD Display — Plume Time Series</b><br/>
    Chemical: {_xml_escape(chemical_name)}<br/>
    24-hr NWS hourly forecast, one plume per hour.<br/>
    Use the ATAK / Google Earth time slider to step through frames.<br/>
    Generated: {now_str}<br/>
    <b>FOR PLANNING USE ONLY — NOT OFFICIAL EMERGENCY GUIDANCE</b>
  ]]></description>
  <open>1</open>
  {all_styles}
  <Folder>
    <name>Source</name>
    {source_pm}
  </Folder>
  {hour_folders}
</Document>
</kml>"""
