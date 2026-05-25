"""
Radiological Dispersal Model — Gaussian plume with EPA FGR-12 cloudshine DCF values.

References:
  Eckerman, K.F., Ryman, J.C. (1993). Federal Guidance Report No. 12.
    External Exposure to Radionuclides in Air, Water, and Soil. EPA-402-R-93-081.
  IAEA EPR-FIRST RESPONDERS 2006. Method of assessment for RDD scenarios.

Physics:
  Cloudshine dose rate [mSv/hr] = C_air [Ci/m³] × DCF [mSv/hr per Ci/m³]
  Air concentration [Ci/m³] from Gaussian plume with Q [Ci/s] (identical math to
  chemical plume — units are Ci instead of g).

  DCF conversion from FGR-12 [Sv·m³/(Bq·s)]:
    DCF_msvhr = FGR12 × 3.7e10 [Bq/Ci] × 1000 [mSv/Sv] × 3600 [s/hr]
              = FGR12 × 1.332e17
"""

from dispersion import compute_plume_polygon, plume_to_latlon

# ── Radionuclide database ─────────────────────────────────────────────────────
# dcf_cloud: mSv/hr per Ci/m³ (cloudshine, from EPA FGR-12 × 1.332e17 conversion)
RADIONUCLIDES: list[dict] = [
    {
        "id": "cs137",
        "name": "Cesium-137",
        "symbol": "Cs-137",
        "dcf_cloud": 2940,
        "half_life": "30.2 yr",
        "type": "gamma",
        "notes": "Most common RDD isotope · 662 keV gamma",
    },
    {
        "id": "co60",
        "name": "Cobalt-60",
        "symbol": "Co-60",
        "dcf_cloud": 14400,
        "half_life": "5.27 yr",
        "type": "gamma",
        "notes": "High-energy gamma (1.17 + 1.33 MeV) · industrial sterilization",
    },
    {
        "id": "ir192",
        "name": "Iridium-192",
        "symbol": "Ir-192",
        "dcf_cloud": 5180,
        "half_life": "73.8 d",
        "type": "gamma",
        "notes": "Industrial radiography source · 0.37 MeV avg",
    },
    {
        "id": "i131",
        "name": "Iodine-131",
        "symbol": "I-131",
        "dcf_cloud": 1120,
        "half_life": "8.02 d",
        "type": "gamma",
        "notes": "Thyroid uptake concern · 364 keV gamma · nuclear fallout",
    },
    {
        "id": "am241",
        "name": "Americium-241",
        "symbol": "Am-241",
        "dcf_cloud": 140,
        "half_life": "432 yr",
        "type": "alpha/gamma",
        "notes": "Smoke detector source · 60 keV gamma · primarily alpha emitter",
    },
    {
        "id": "sr90",
        "name": "Strontium-90",
        "symbol": "Sr-90",
        "dcf_cloud": 13,
        "half_life": "28.8 yr",
        "type": "beta",
        "notes": "Pure beta emitter · very low cloudshine · bone seeker",
    },
    {
        "id": "ra226",
        "name": "Radium-226",
        "symbol": "Ra-226",
        "dcf_cloud": 2770,
        "half_life": "1600 yr",
        "type": "gamma",
        "notes": "Legacy medical/industrial · 186 keV gamma + daughters",
    },
    {
        "id": "pu239",
        "name": "Plutonium-239",
        "symbol": "Pu-239",
        "dcf_cloud": 7,
        "half_life": "24100 yr",
        "type": "alpha",
        "notes": "Weapons material · alpha emitter · very low cloudshine",
    },
    {
        "id": "u235",
        "name": "Uranium-235",
        "symbol": "U-235",
        "dcf_cloud": 613,
        "half_life": "703 My",
        "type": "gamma",
        "notes": "Weapons-grade uranium · 185 keV gamma",
    },
    {
        "id": "cf252",
        "name": "Californium-252",
        "symbol": "Cf-252",
        "dcf_cloud": 799,
        "half_life": "2.65 yr",
        "type": "neutron/gamma",
        "notes": "Neutron emitter · well-logging / startup sources",
    },
]

# ── Dose zones (cloudshine threshold dose rates) ──────────────────────────────
DOSE_ZONES: list[dict] = [
    {
        "level": "pag",
        "label": "PAG Evacuation Zone",
        "dose_msvhr": 0.1,
        "color": "#FFD700",
        "desc": "0.1 mSv/hr — EPA Protective Action Guide: general population evacuation",
    },
    {
        "level": "worker",
        "label": "Emergency Worker Limit",
        "dose_msvhr": 1.0,
        "color": "#FF8C00",
        "desc": "1 mSv/hr — Controlled access · emergency responder threshold",
    },
    {
        "level": "high",
        "label": "High Radiation Zone",
        "dose_msvhr": 10.0,
        "color": "#FF4500",
        "desc": "10 mSv/hr — NRC high radiation area · immediate evacuation",
    },
    {
        "level": "extreme",
        "label": "Extreme Hazard Zone",
        "dose_msvhr": 100.0,
        "color": "#9B2DC8",
        "desc": "100 mSv/hr — Very high radiation · lethal over hours",
    },
]


def get_radionuclide(rad_id: str) -> dict | None:
    return next((r for r in RADIONUCLIDES if r["id"] == rad_id), None)


def compute_radiation_contours(
    Q_ci_s: float,
    u_ms: float,
    stability: str,
    dcf_cloud: float,
    source_lat: float,
    source_lon: float,
    wind_from_deg: float,
    H_m: float = 0.0,
) -> dict:
    """
    Compute dose rate contour polygons for all dose zones.

    The Gaussian plume math is identical to chemical dispersion — Ci/s source
    term produces Ci/m³ concentration, which × DCF gives mSv/hr dose rate.

    Returns:
        {
          "pag":     {"latlon": [...], "label": ..., "color": ...,
                      "max_downwind_m": float, "max_width_m": float, "dose_msvhr": float},
          "worker":  {...},
          "high":    {...},
          "extreme": {...},
        }
    """
    result = {}
    for zone in DOSE_ZONES:
        threshold_ci_m3 = zone["dose_msvhr"] / dcf_cloud
        polygon_xy = compute_plume_polygon(threshold_ci_m3, Q_ci_s, u_ms, stability, H_m)
        if not polygon_xy:
            result[zone["level"]] = {
                "latlon": [],
                "label": zone["label"],
                "color": zone["color"],
                "dose_msvhr": zone["dose_msvhr"],
                "desc": zone["desc"],
                "max_downwind_m": 0,
                "max_width_m": 0,
            }
            continue

        xs = [p[0] for p in polygon_xy]
        ys = [abs(p[1]) for p in polygon_xy]
        max_x = max(xs)
        max_y = max(ys) if ys else 0

        latlon = plume_to_latlon(polygon_xy, source_lat, source_lon, wind_from_deg)
        result[zone["level"]] = {
            "latlon": latlon,
            "label": zone["label"],
            "color": zone["color"],
            "dose_msvhr": zone["dose_msvhr"],
            "desc": zone["desc"],
            "max_downwind_m": max_x,
            "max_width_m": max_y * 2,
        }

    return result
