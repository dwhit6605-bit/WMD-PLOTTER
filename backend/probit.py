"""
Probit-based casualty estimation for WMD/HAZMAT hazard zones.

The probit (probability unit) model converts a concentration–time product
(Ct) to a fraction of an exposed population that will be killed or injured.

Probit equation:
  Pr = a + b · ln(C^n · t)
  P(death) = Φ(Pr − 5)          where Φ is the standard normal CDF

References:
  Ten Berge, W.F., Zwart, A. & Appelman, L.M. (1986). Concentration–time
    mortality relationship for irritant and systemically acting vapors and
    gases. J. Haz. Mat. 13, 301–309.
  Lees, F.P. (1996). Loss Prevention in the Process Industries, 2nd ed.
  TNO Green Book — Methods for the Determination of Possible Damage (1992).
  Abramowitz, M. & Stegun, I.A. (1964). Handbook of Mathematical Functions,
    formula 26.2.17.

Units: C in ppm, t in minutes.
"""

import math

# ─────────────────────────────────────────────────────────────────────────────
# Standard normal CDF — Abramowitz & Stegun (1964) polynomial approximation
# ─────────────────────────────────────────────────────────────────────────────

_AS_P  = 0.2316419
_AS_B1 =  0.319381530
_AS_B2 = -0.356563782
_AS_B3 =  1.781477937
_AS_B4 = -1.821255978
_AS_B5 =  1.330274429


def _norm_cdf(z: float) -> float:
    """
    Standard normal CDF Φ(z).

    Uses the Abramowitz & Stegun (1964) rational polynomial approximation
    (formula 26.2.17), accurate to |ε| < 7.5 × 10⁻⁸.
    Handles extreme values (|z| > 8) by returning 0 or 1 exactly.
    """
    if z <= -8.0:
        return 0.0
    if z >= 8.0:
        return 1.0

    abs_z = abs(z)
    t = 1.0 / (1.0 + _AS_P * abs_z)
    poly = t * (_AS_B1 + t * (_AS_B2 + t * (_AS_B3 + t * (_AS_B4 + t * _AS_B5))))
    phi = 1.0 - (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * abs_z * abs_z) * poly

    if z >= 0.0:
        return phi
    else:
        return 1.0 - phi


def probit_to_fraction(Y: float) -> float:
    """
    Convert probit value Y to fraction of population affected.

    P = Φ(Y − 5)

    Args:
        Y: Probit value (dimensionless).

    Returns:
        Fraction affected (0.0–1.0).
    """
    return _norm_cdf(Y - 5.0)


# ─────────────────────────────────────────────────────────────────────────────
# Chemical probit coefficients — mortality (P(death))
# Pr = a + b * ln(C^n * t),  C in ppm, t in minutes
# ─────────────────────────────────────────────────────────────────────────────

CHEM_PROBIT = {
    "cl2":     {"a": -8.29,  "b": 0.92,  "n": 2.0},   # Ten Berge (1986)
    "nh3":     {"a": -15.6,  "b": 1.0,   "n": 1.5},
    "hcn":     {"a": -29.42, "b": 3.008, "n": 1.0},
    "so2":     {"a": -19.2,  "b": 2.4,   "n": 1.0},
    "h2s":     {"a": -31.42, "b": 3.008, "n": 1.0},
    "cg":      {"a": -19.27, "b": 3.686, "n": 1.0},   # Phosgene
    "no2":     {"a": -13.79, "b": 1.4,   "n": 2.0},
    "default": {"a": -10.0,  "b": 1.0,   "n": 1.0},
}

# ─────────────────────────────────────────────────────────────────────────────
# Zone-fraction fallback table — (lethality, serious, minor)
# Used when probit data are not available or gas_id is not in CHEM_PROBIT.
# Source: TNO Green Book (1992); FEMA CAMEO/ALOHA planning guidance.
# ─────────────────────────────────────────────────────────────────────────────

ZONE_FRACTIONS: dict[str, tuple[float, float, float]] = {
    # Generic chemical zones
    "high":   (0.50, 0.25, 0.15),
    "medium": (0.10, 0.30, 0.25),
    "low":    (0.02, 0.08, 0.20),

    # Dense gas zones (by threshold id)
    "erpg3":    (0.50, 0.25, 0.15),
    "idlh":     (0.35, 0.30, 0.20),
    "erpg2":    (0.05, 0.25, 0.30),
    "erpg1":    (0.01, 0.05, 0.15),
    "lfl":      (0.45, 0.30, 0.15),
    "half_lfl": (0.05, 0.10, 0.20),

    # Blast overpressure zones
    "severe":          (0.50, 0.30, 0.15),
    "moderate":        (0.20, 0.30, 0.30),
    "light":           (0.05, 0.10, 0.40),
    # Blast by structural damage level
    "catastrophic":    (0.80, 0.15, 0.04),
    "severe_struct":   (0.50, 0.30, 0.15),
    "moderate_struct": (0.20, 0.30, 0.30),
    "light_struct":    (0.05, 0.10, 0.40),
    "glass":           (0.01, 0.03, 0.15),

    # Radiation dose zones
    "extreme": (0.90, 0.08, 0.02),
    "worker":  (0.05, 0.15, 0.30),
    "pag":     (0.00, 0.02, 0.05),

    # BLEVE / fireball thermal zones
    "fireball": (0.95, 0.04, 0.01),
    "lethal":   (0.60, 0.25, 0.10),
    # "severe" already defined above (same fractions)
    # "moderate" already defined above (same fractions)
    "pain":     (0.00, 0.05, 0.30),

    # Fire / smoke / CO zones
    "co_idlh":       (0.30, 0.40, 0.20),
    "co_high":       (0.05, 0.20, 0.40),
    "co_osha":       (0.00, 0.05, 0.20),
    "hazardous":     (0.10, 0.25, 0.40),
    "very_unhealthy":(0.01, 0.10, 0.40),
    "unhealthy":     (0.00, 0.02, 0.20),
    "usg":           (0.00, 0.00, 0.05),
    # "moderate" already defined above
}

# Radiation "high" uses same key as blast — add explicit alias
ZONE_FRACTIONS["high_rad"] = (0.50, 0.30, 0.15)  # radiation high dose


def _probit_lethality(
    threshold_ppm: float,
    exposure_min: float,
    coeffs: dict,
) -> float:
    """
    Compute lethality fraction from probit equation.

    Args:
        threshold_ppm:  Representative concentration (ppm) — the zone boundary.
        exposure_min:   Exposure duration (minutes).
        coeffs:         {"a", "b", "n"} from CHEM_PROBIT.

    Returns:
        Fraction (0–1) of exposed population killed.
    """
    if threshold_ppm <= 0 or exposure_min <= 0:
        return 0.0
    a, b, n = coeffs["a"], coeffs["b"], coeffs["n"]
    # Ct load = C^n * t
    ct = (threshold_ppm ** n) * exposure_min
    if ct <= 0:
        return 0.0
    pr = a + b * math.log(ct)
    return max(0.0, min(1.0, probit_to_fraction(pr)))


def compute_probit_zones(
    zones: list[dict],
    exposure_min: float,
    gas_id: str = None,
) -> dict:
    """
    Estimate casualties in each hazard zone using probit analysis or
    zone-based fallback fractions.

    Args:
        zones:        List of zone dicts, each containing:
                        - "level"         (str)   zone identifier, e.g. "high", "erpg3"
                        - "label"         (str)   human-readable label
                        - "color"         (str)   hex color string
                        - "pop_estimate"  (int/float) estimated population in zone
                        - "threshold_ppm" (float, optional) zone boundary concentration
        exposure_min: Exposure duration in minutes.
        gas_id:       Gas identifier for CHEM_PROBIT lookup (optional).
                      If provided and threshold_ppm present, probit method is used.
                      Otherwise falls back to ZONE_FRACTIONS.

    Returns:
        {
            "zones":        list of input dicts augmented with casualty fields,
            "totals":       {"fatalities", "serious_injuries",
                             "minor_injuries", "total_casualties"},
            "exposure_min": float,
            "method":       str,
            "note":         str,
        }
    """
    coeffs = None
    use_probit = False

    if gas_id is not None:
        coeffs = CHEM_PROBIT.get(gas_id) or CHEM_PROBIT["default"]
        use_probit = True

    method = (
        "Probit (Ten Berge)" if use_probit
        else "Zone-based estimate (TNO Green Book)"
    )

    total_fatalities        = 0
    total_serious_injuries  = 0
    total_minor_injuries    = 0

    enriched_zones = []

    for zone in zones:
        level       = zone.get("level", "")
        pop         = float(zone.get("pop_estimate", 0))
        threshold_ppm = zone.get("threshold_ppm")

        if use_probit and threshold_ppm is not None and threshold_ppm > 0:
            # ── Probit path ──────────────────────────────────────────────────
            lethality = _probit_lethality(threshold_ppm, exposure_min, coeffs)

            # Serious injuries: apply probit at 35% of the Ct load
            # (equivalent to the probit at C reduced to 0.35^(1/n) × C,
            # or simply use a reduced Ct scale factor)
            ct_full   = (threshold_ppm ** coeffs["n"]) * exposure_min
            ct_serious = ct_full * 0.35
            if ct_serious > 0:
                pr_s = coeffs["a"] + coeffs["b"] * math.log(ct_serious)
                frac_serious_cumulative = max(0.0, min(1.0, probit_to_fraction(pr_s)))
            else:
                frac_serious_cumulative = 0.0

            # serious = fraction between lethality threshold and 35%-load threshold
            serious = max(0.0, frac_serious_cumulative - lethality)

            # minor = up to 40% of survivors, capped at 0.5
            survivor_frac = max(0.0, 1.0 - lethality - serious)
            minor = min(0.5, 0.4 * survivor_frac)

        else:
            # ── Fallback: zone-fraction table ────────────────────────────────
            fracs = ZONE_FRACTIONS.get(level)
            if fracs is None:
                # Try without trailing suffix (e.g. "high_rad" → "high")
                base = level.split("_")[0]
                fracs = ZONE_FRACTIONS.get(base, (0.01, 0.05, 0.10))
            lethality, serious, minor = fracs

        fatalities       = int(round(pop * lethality))
        serious_injuries = int(round(pop * serious))
        minor_injuries   = int(round(pop * minor))

        total_fatalities       += fatalities
        total_serious_injuries += serious_injuries
        total_minor_injuries   += minor_injuries

        enriched = dict(zone)
        enriched["lethality_pct"]     = round(lethality * 100.0, 1)
        enriched["serious_pct"]       = round(serious   * 100.0, 1)
        enriched["minor_pct"]         = round(minor     * 100.0, 1)
        enriched["fatalities"]        = fatalities
        enriched["serious_injuries"]  = serious_injuries
        enriched["minor_injuries"]    = minor_injuries
        enriched_zones.append(enriched)

    total_casualties = total_fatalities + total_serious_injuries + total_minor_injuries

    return {
        "zones": enriched_zones,
        "totals": {
            "fatalities":       total_fatalities,
            "serious_injuries": total_serious_injuries,
            "minor_injuries":   total_minor_injuries,
            "total_casualties": total_casualties,
        },
        "exposure_min": exposure_min,
        "method": method,
        "note": (
            "Estimates assume uniform distribution and no warning/evacuation time. "
            "Actual casualties depend on shelter, evacuation actions, and time to escape."
        ),
    }
