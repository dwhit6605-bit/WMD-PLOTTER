"""
EPA Acute Exposure Guideline Levels (AEGL) — multi-time-point values.
Source: US EPA AEGL Program — https://www.epa.gov/aegl
        Final AEGL values published in the Federal Register.

Coverage: ~25 chemicals with 10-minute, 60-minute, and 8-hour values.
Values are ppm (v/v) at standard temperature and pressure.

AEGL-1: Notable discomfort, irritation, or non-sensory effects (reversible).
AEGL-2: Irreversible or serious long-lasting adverse health effects.
AEGL-3: Life-threatening health effects or death.
"""

# {chem_id: {level: {"10min": ppm, "60min": ppm, "8hr": ppm}}}
AEGL: dict[str, dict] = {

    # ── Industrial gases ──────────────────────────────────────────────────────
    "ammonia": {
        1: {"10min": 30,   "60min": 30,   "8hr": 30},
        2: {"10min": 220,  "60min": 160,  "8hr": 110},
        3: {"10min": 2700, "60min": 1100, "8hr": 390},
    },
    "chlorine": {
        1: {"10min": 0.5,  "60min": 0.5,  "8hr": 0.5},
        2: {"10min": 2.8,  "60min": 2.0,  "8hr": 0.71},
        3: {"10min": 50,   "60min": 20,   "8hr": 7.1},
    },
    "chlorine_cwa": {   # same chemical, different DB ID
        1: {"10min": 0.5,  "60min": 0.5,  "8hr": 0.5},
        2: {"10min": 2.8,  "60min": 2.0,  "8hr": 0.71},
        3: {"10min": 50,   "60min": 20,   "8hr": 7.1},
    },
    "hydrogen_sulfide": {
        1: {"10min": 0.75, "60min": 0.51, "8hr": 0.25},
        2: {"10min": 41,   "60min": 27,   "8hr": 17},
        3: {"10min": 76,   "60min": 50,   "8hr": 31},
    },
    "hydrogen_fluoride": {
        1: {"10min": 1.0,  "60min": 1.0,  "8hr": 1.0},
        2: {"10min": 95,   "60min": 24,   "8hr": 8.6},
        3: {"10min": 170,  "60min": 44,   "8hr": 15},
    },
    "anhydrous_hf": {   # same as HF
        1: {"10min": 1.0,  "60min": 1.0,  "8hr": 1.0},
        2: {"10min": 95,   "60min": 24,   "8hr": 8.6},
        3: {"10min": 170,  "60min": 44,   "8hr": 15},
    },
    "hydrogen_cyanide": {
        1: {"10min": 2.5,  "60min": 2.5,  "8hr": 2.5},
        2: {"10min": 17,   "60min": 7.1,  "8hr": 2.5},
        3: {"10min": 27,   "60min": 15,   "8hr": 6.6},
    },
    "hydrogen_cyanide_ac": {    # same as HCN
        1: {"10min": 2.5,  "60min": 2.5,  "8hr": 2.5},
        2: {"10min": 17,   "60min": 7.1,  "8hr": 2.5},
        3: {"10min": 27,   "60min": 15,   "8hr": 6.6},
    },
    "phosgene": {
        1: {"10min": 0.30, "60min": 0.30, "8hr": 0.30},
        2: {"10min": 1.5,  "60min": 0.30, "8hr": 0.04},
        3: {"10min": 3.6,  "60min": 0.75, "8hr": 0.10},
    },
    "diphosgene": {     # similar profile to phosgene but lower potency
        1: {"10min": 0.30, "60min": 0.30, "8hr": 0.30},
        2: {"10min": 1.5,  "60min": 0.30, "8hr": 0.04},
        3: {"10min": 3.6,  "60min": 0.75, "8hr": 0.10},
    },
    "sulfur_dioxide": {
        1: {"10min": 0.20, "60min": 0.20, "8hr": 0.20},
        2: {"10min": 0.75, "60min": 0.75, "8hr": 0.75},
        3: {"10min": 30,   "60min": 30,   "8hr": 30},
    },
    "hydrogen_chloride": {
        1: {"10min": 1.8,  "60min": 1.8,  "8hr": 1.8},
        2: {"10min": 100,  "60min": 43,   "8hr": 26},
        3: {"10min": 620,  "60min": 210,  "8hr": 130},
    },
    "arsine": {
        1: {"10min": 0.005,"60min": 0.005,"8hr": 0.005},
        2: {"10min": 0.13, "60min": 0.080,"8hr": 0.057},
        3: {"10min": 0.75, "60min": 0.43, "8hr": 0.29},
    },
    "phosphine": {
        1: {"10min": 0.030,"60min": 0.030,"8hr": 0.030},
        2: {"10min": 0.27, "60min": 0.21, "8hr": 0.16},
        3: {"10min": 0.50, "60min": 0.40, "8hr": 0.30},
    },
    "bromine": {
        1: {"10min": 0.20, "60min": 0.20, "8hr": 0.20},
        2: {"10min": 1.5,  "60min": 0.55, "8hr": 0.32},
        3: {"10min": 7.7,  "60min": 4.3,  "8hr": 2.7},
    },
    "fluorine": {
        1: {"10min": 0.20, "60min": 0.20, "8hr": 0.20},
        2: {"10min": 4.0,  "60min": 1.6,  "8hr": 1.0},
        3: {"10min": 9.0,  "60min": 3.5,  "8hr": 2.3},
    },
    "acrolein": {
        1: {"10min": 0.033,"60min": 0.033,"8hr": 0.033},
        2: {"10min": 0.44, "60min": 0.44, "8hr": 0.44},
        3: {"10min": 2.5,  "60min": 2.5,  "8hr": 2.5},
    },
    "formaldehyde": {
        1: {"10min": 1.0,  "60min": 0.60, "8hr": 0.080},
        2: {"10min": 14,   "60min": 9.4,  "8hr": 3.0},
        3: {"10min": 17,   "60min": 12,   "8hr": 4.8},
    },
    "cyanogen_chloride": {
        1: {"10min": 0.40, "60min": 0.40, "8hr": 0.40},
        2: {"10min": 2.5,  "60min": 2.0,  "8hr": 1.7},
        3: {"10min": 12,   "60min": 8.5,  "8hr": 7.0},
    },
    "chloropicrin": {
        1: {"10min": 0.050,"60min": 0.050,"8hr": 0.050},
        2: {"10min": 0.30, "60min": 0.23, "8hr": 0.18},
        3: {"10min": 1.5,  "60min": 1.0,  "8hr": 0.73},
    },
    "methyl_isocyanate": {
        1: {"10min": 0.004,"60min": 0.004,"8hr": 0.004},
        2: {"10min": 0.040,"60min": 0.019,"8hr": 0.011},
        3: {"10min": 0.40, "60min": 0.19, "8hr": 0.10},
    },
    "methyl_bromide": {
        1: {"10min": 0.87, "60min": 0.87, "8hr": 0.87},
        2: {"10min": 28,   "60min": 28,   "8hr": 21},
        3: {"10min": 190,  "60min": 99,   "8hr": 66},
    },
    "acrylonitrile": {
        1: {"10min": 2.1,  "60min": 1.7,  "8hr": 1.3},
        2: {"10min": 35,   "60min": 35,   "8hr": 35},
        3: {"10min": 85,   "60min": 85,   "8hr": 85},
    },
    "ethylene_oxide": {
        1: {"10min": 11,   "60min": 7.2,  "8hr": 3.6},
        2: {"10min": 56,   "60min": 28,   "8hr": 14},
        3: {"10min": 480,  "60min": 240,  "8hr": 120},
    },
    "nitrogen_tetroxide": {
        1: {"10min": 0.50, "60min": 0.50, "8hr": 0.50},
        2: {"10min": 11,   "60min": 11,   "8hr": 11},
        3: {"10min": 100,  "60min": 50,   "8hr": 25},
    },

    # ── Chemical warfare agents ───────────────────────────────────────────────
    "sarin": {
        1: {"10min": 0.0000016, "60min": 0.0000016, "8hr": 0.0000016},
        2: {"10min": 0.0000066, "60min": 0.0000033, "8hr": 0.0000022},
        3: {"10min": 0.000064,  "60min": 0.000032,  "8hr": 0.000021},
    },
    "soman": {
        1: {"10min": 0.00000056,"60min": 0.00000056,"8hr": 0.00000056},
        2: {"10min": 0.0000024, "60min": 0.0000012, "8hr": 0.00000081},
        3: {"10min": 0.000022,  "60min": 0.000011,  "8hr": 0.0000075},
    },
    "tabun": {
        1: {"10min": 0.00000094,"60min": 0.00000094,"8hr": 0.00000094},
        2: {"10min": 0.0000064, "60min": 0.0000032, "8hr": 0.0000021},
        3: {"10min": 0.000059,  "60min": 0.000030,  "8hr": 0.000020},
    },
    "vx": {
        1: {"10min": 0.0000003, "60min": 0.0000003, "8hr": 0.0000003},
        2: {"10min": 0.0000038, "60min": 0.0000019, "8hr": 0.0000013},
        3: {"10min": 0.000027,  "60min": 0.000014,  "8hr": 0.0000092},
    },
}


def get_aegl(chem_id: str) -> dict | None:
    """Return full AEGL multi-time table for a chemical, or None."""
    return AEGL.get(chem_id)
