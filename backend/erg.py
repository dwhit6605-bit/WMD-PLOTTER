"""
ERG 2024 — Initial Isolation and Protective Action Distance (PAD) lookup.

Source: U.S. DOT Emergency Response Guidebook 2024, Table 1
        https://www.phmsa.dot.gov/hazmat/erg/emergency-response-guidebook-erg

Coverage: Toxic Inhalation Hazard (TIH) materials from Table 1 (~95 entries).
          Water-reactive TIH chemicals omitted; land-spill values only.

Accuracy note: Values from ERG 2024 Table 1.  Minor rounding may differ from
the printed document.  Always verify against the physical ERG before operations.

Zone geometry:
  Initial Isolation — full circle, radius = isolation_m
  Protective Action (day)   — downwind 180° sector if wind known; else full circle
  Protective Action (night) — same geometry, larger radius
"""

import math

# ── ERG 2024 Table 1 ─────────────────────────────────────────────────────────
# Structure per entry:
#   name, guide, hl (highlighted/dangerous),
#   small: {isolation_m, day_pad_km, night_pad_km}
#   large: {isolation_m, day_pad_km, night_pad_km}

ERG_TABLE1: dict[str, dict] = {
    "1005": {"name": "Ammonia, anhydrous",                   "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 150, "day_pad_km": 0.8, "night_pad_km": 2.7}},
    "1008": {"name": "Boron trifluoride",                    "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 200, "day_pad_km": 1.2, "night_pad_km": 4.6}},
    "1016": {"name": "Carbon monoxide",                      "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.1},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 0.9}},
    "1017": {"name": "Chlorine",                             "guide": 124, "hl": False,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.1},
             "large": {"isolation_m": 400, "day_pad_km": 2.1, "night_pad_km": 6.7}},
    "1023": {"name": "Coal gas",                             "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.7}},
    "1026": {"name": "Cyanogen",                             "guide": 119, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.9},
             "large": {"isolation_m": 300, "day_pad_km": 2.1, "night_pad_km": 7.1}},
    "1040": {"name": "Ethylene oxide",                       "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.5}},
    "1045": {"name": "Fluorine",                             "guide": 124, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.4},
             "large": {"isolation_m": 500, "day_pad_km": 3.4, "night_pad_km": 11.0}},
    "1048": {"name": "Hydrogen bromide, anhydrous",          "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.4}},
    "1050": {"name": "Hydrogen chloride, anhydrous",         "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.5, "night_pad_km": 1.8}},
    "1051": {"name": "Hydrogen cyanide, stabilized (HCN)",   "guide": 117, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.1},
             "large": {"isolation_m": 300, "day_pad_km": 1.3, "night_pad_km": 3.5}},
    "1052": {"name": "Hydrogen fluoride, anhydrous",         "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.3, "night_pad_km": 1.1},
             "large": {"isolation_m": 200, "day_pad_km": 1.4, "night_pad_km": 4.7}},
    "1053": {"name": "Hydrogen sulfide",                     "guide": 117, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.6},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.4}},
    "1062": {"name": "Methyl bromide",                       "guide": 123, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 200, "day_pad_km": 0.9, "night_pad_km": 3.8}},
    "1064": {"name": "Methyl mercaptan",                     "guide": 117, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.6}},
    "1067": {"name": "Dinitrogen tetroxide",                 "guide": 124, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.2}},
    "1069": {"name": "Nitrosyl chloride",                    "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 400, "day_pad_km": 3.4, "night_pad_km": 10.5}},
    "1076": {"name": "Phosgene (CG)",                        "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.0, "night_pad_km": 10.9}},
    "1079": {"name": "Sulfur dioxide",                       "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.5, "night_pad_km": 1.9}},
    "1082": {"name": "Trifluorochloroethylene",              "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 100, "day_pad_km": 0.5, "night_pad_km": 1.6}},
    "1092": {"name": "Acrolein, inhibited",                  "guide": 131, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.2},
             "large": {"isolation_m": 300, "day_pad_km": 1.5, "night_pad_km": 4.7}},
    "1098": {"name": "Allyl alcohol",                        "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.3}},
    "1135": {"name": "Ethylene chlorohydrin",                "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.2}},
    "1143": {"name": "Crotonaldehyde",                       "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.4}},
    "1163": {"name": "Dimethylhydrazine, unsymmetrical",     "guide": 131, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.8},
             "large": {"isolation_m": 300, "day_pad_km": 1.6, "night_pad_km": 5.4}},
    "1185": {"name": "Ethyleneimine, inhibited",             "guide": 131, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.6},
             "large": {"isolation_m": 200, "day_pad_km": 0.9, "night_pad_km": 3.0}},
    "1238": {"name": "Methyl chloroformate",                 "guide": 155, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.5},
             "large": {"isolation_m": 200, "day_pad_km": 1.1, "night_pad_km": 3.7}},
    "1239": {"name": "Methyl chloromethyl ether",            "guide": 131, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.5},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.3}},
    "1244": {"name": "Methylhydrazine",                      "guide": 131, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.3}},
    "1251": {"name": "Methyl vinyl ketone, stabilized",      "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1259": {"name": "Nickel carbonyl",                      "guide": 131, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 1.9},
             "large": {"isolation_m": 600, "day_pad_km": 4.9, "night_pad_km": 10.9}},
    "1380": {"name": "Pentaborane",                          "guide": 135, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.6},
             "large": {"isolation_m": 200, "day_pad_km": 0.9, "night_pad_km": 3.1}},
    "1510": {"name": "Tetranitromethane",                    "guide": 141, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.0}},
    "1560": {"name": "Arsenic trichloride",                  "guide": 151, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.4}},
    "1580": {"name": "Chloropicrin",                         "guide": 154, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.4},
             "large": {"isolation_m": 400, "day_pad_km": 2.5, "night_pad_km": 7.2}},
    "1589": {"name": "Cyanogen chloride (CK)",               "guide": 125, "hl": True,
             "small": {"isolation_m": 100, "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.0, "night_pad_km": 10.9}},
    "1605": {"name": "Ethylene dibromide",                   "guide": 154, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1612": {"name": "Hexaethyl tetraphosphate",             "guide": 123, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1660": {"name": "Nitric oxide",                         "guide": 124, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.2},
             "large": {"isolation_m": 200, "day_pad_km": 1.2, "night_pad_km": 3.7}},
    "1670": {"name": "Perchloromethyl mercaptan",            "guide": 157, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.3},
             "large": {"isolation_m": 400, "day_pad_km": 2.6, "night_pad_km": 7.4}},
    "1695": {"name": "Chloroacetone, stabilized",            "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.4}},
    "1697": {"name": "Chloroacetophenone (CN / Mace)",        "guide": 159, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.2}},
    "1698": {"name": "Adamsite (DM)",                        "guide": 154, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1699": {"name": "Diphenylchloroarsine (DA)",             "guide": 154, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.2}},
    "1722": {"name": "Allyl chloroformate",                  "guide": 155, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.6},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.2}},
    "1741": {"name": "Boron trichloride",                    "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.5}},
    "1744": {"name": "Bromine",                              "guide": 154, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.4}},
    "1745": {"name": "Bromine pentafluoride",                "guide": 144, "hl": True,
             "small": {"isolation_m": 30,  "day_pad_km": 0.3, "night_pad_km": 1.2},
             "large": {"isolation_m": 300, "day_pad_km": 2.3, "night_pad_km": 7.0}},
    "1749": {"name": "Chlorine trifluoride",                 "guide": 124, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.0},
             "large": {"isolation_m": 500, "day_pad_km": 4.0, "night_pad_km": 10.0}},
    "1752": {"name": "Chloroacetyl chloride",                "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.8},
             "large": {"isolation_m": 200, "day_pad_km": 1.2, "night_pad_km": 4.0}},
    "1754": {"name": "Chlorosulfuric acid",                  "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1809": {"name": "Phosphorus trichloride",               "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.5},
             "large": {"isolation_m": 200, "day_pad_km": 1.1, "night_pad_km": 3.7}},
    "1810": {"name": "Phosphoryl chloride",                  "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.4}},
    "1817": {"name": "Pyrosulfuryl chloride",                "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.3}},
    "1818": {"name": "Silicon tetrachloride",                "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1828": {"name": "Sulfur chlorides",                     "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.1}},
    "1829": {"name": "Sulfur trioxide",                      "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "1831": {"name": "Sulfuric acid, fuming",                "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.4}},
    "1834": {"name": "Sulfuryl chloride",                    "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 100, "day_pad_km": 0.5, "night_pad_km": 1.7}},
    "1836": {"name": "Thionyl chloride",                     "guide": 137, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.0}},
    "1859": {"name": "Silicon tetrafluoride",                "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 200, "day_pad_km": 1.1, "night_pad_km": 3.7}},
    "1892": {"name": "Ethyldichloroarsine (ED)",              "guide": 151, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.3}},
    "2032": {"name": "Nitric acid, fuming",                  "guide": 157, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.2}},
    "2186": {"name": "Hydrogen chloride, refrigerated liquid", "guide": 125, "hl": False,
             "small": {"isolation_m": 60,  "day_pad_km": 0.2, "night_pad_km": 0.6},
             "large": {"isolation_m": 300, "day_pad_km": 1.4, "night_pad_km": 4.8}},
    "2188": {"name": "Arsine",                               "guide": 119, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 1.9},
             "large": {"isolation_m": 600, "day_pad_km": 5.5, "night_pad_km": 11.0}},
    "2189": {"name": "Dichlorosilane",                       "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 200, "day_pad_km": 0.9, "night_pad_km": 3.6}},
    "2190": {"name": "Oxygen difluoride",                    "guide": 124, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.3, "night_pad_km": 11.0}},
    "2191": {"name": "Sulfuryl fluoride",                    "guide": 123, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.2}},
    "2194": {"name": "Selenium hexafluoride",                "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.3, "night_pad_km": 11.0}},
    "2196": {"name": "Tungsten hexafluoride",                "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.3, "night_pad_km": 1.1},
             "large": {"isolation_m": 400, "day_pad_km": 3.3, "night_pad_km": 9.2}},
    "2197": {"name": "Hydrogen iodide, anhydrous",           "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.4}},
    "2198": {"name": "Phosphorus pentafluoride",             "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.4, "night_pad_km": 1.7},
             "large": {"isolation_m": 400, "day_pad_km": 3.3, "night_pad_km": 9.6}},
    "2199": {"name": "Phosphine",                            "guide": 119, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 300, "day_pad_km": 1.6, "night_pad_km": 5.1}},
    "2202": {"name": "Hydrogen selenide, anhydrous",         "guide": 117, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.5, "night_pad_km": 11.0}},
    "2204": {"name": "Carbonyl sulfide",                     "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 200, "day_pad_km": 0.9, "night_pad_km": 3.3}},
    "2232": {"name": "Chloroacetaldehyde",                   "guide": 153, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.0}},
    "2334": {"name": "Allylamine",                           "guide": 132, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 200, "day_pad_km": 1.0, "night_pad_km": 3.2}},
    "2417": {"name": "Carbonyl fluoride",                    "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.4, "night_pad_km": 1.5},
             "large": {"isolation_m": 400, "day_pad_km": 2.9, "night_pad_km": 8.4}},
    "2418": {"name": "Sulfur tetrafluoride",                 "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 500, "day_pad_km": 4.5, "night_pad_km": 11.0}},
    "2420": {"name": "Hexafluoroacetone",                    "guide": 125, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.8},
             "large": {"isolation_m": 200, "day_pad_km": 1.2, "night_pad_km": 3.9}},
    "2421": {"name": "Nitrogen trioxide",                    "guide": 124, "hl": False,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.2},
             "large": {"isolation_m": 400, "day_pad_km": 2.5, "night_pad_km": 7.8}},
    "2474": {"name": "Thiophosgene",                         "guide": 157, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.4, "night_pad_km": 1.5},
             "large": {"isolation_m": 400, "day_pad_km": 2.8, "night_pad_km": 8.3}},
    "2477": {"name": "Methyl isothiocyanate",                "guide": 155, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.4}},
    "2480": {"name": "Methyl isocyanate (MIC)",              "guide": 155, "hl": True,
             "small": {"isolation_m": 100, "day_pad_km": 0.6, "night_pad_km": 3.2},
             "large": {"isolation_m": 800, "day_pad_km": 8.0, "night_pad_km": 11.0}},
    "2481": {"name": "Ethyl isocyanate",                     "guide": 155, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.4, "night_pad_km": 1.4},
             "large": {"isolation_m": 300, "day_pad_km": 2.2, "night_pad_km": 6.8}},
    "2482": {"name": "n-Propyl isocyanate",                  "guide": 155, "hl": False,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.1},
             "large": {"isolation_m": 200, "day_pad_km": 1.4, "night_pad_km": 4.6}},
    "2483": {"name": "Isopropyl isocyanate",                 "guide": 155, "hl": False,
             "small": {"isolation_m": 60,  "day_pad_km": 0.3, "night_pad_km": 1.2},
             "large": {"isolation_m": 200, "day_pad_km": 1.5, "night_pad_km": 4.8}},
    "2484": {"name": "tert-Butyl isocyanate",                "guide": 155, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.8},
             "large": {"isolation_m": 200, "day_pad_km": 1.2, "night_pad_km": 3.8}},
    "2485": {"name": "n-Butyl isocyanate",                   "guide": 155, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.7},
             "large": {"isolation_m": 200, "day_pad_km": 1.1, "night_pad_km": 3.6}},
    "2487": {"name": "Phenyl isocyanate",                    "guide": 155, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 150, "day_pad_km": 0.7, "night_pad_km": 2.2}},
    "2495": {"name": "Iodine pentafluoride",                 "guide": 144, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.2, "night_pad_km": 0.8},
             "large": {"isolation_m": 200, "day_pad_km": 1.2, "night_pad_km": 3.9}},
    "2534": {"name": "Methylchlorosilane",                   "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "2548": {"name": "Chlorine pentafluoride",               "guide": 124, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.4, "night_pad_km": 11.0}},
    "2600": {"name": "Carbon monoxide and hydrogen mixture", "guide": 119, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.1},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 0.9}},
    "2644": {"name": "Methyl iodide",                        "guide": 151, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 1.9}},
    "2646": {"name": "Hexachlorocyclopentadiene",            "guide": 151, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.3, "night_pad_km": 1.0}},
    "2668": {"name": "Chloroacetonitrile",                   "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.2}},
    "2676": {"name": "Stibine",                              "guide": 119, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 600, "day_pad_km": 5.0, "night_pad_km": 11.0}},
    "3057": {"name": "Trifluoroacetyl chloride",             "guide": 125, "hl": True,
             "small": {"isolation_m": 60,  "day_pad_km": 0.5, "night_pad_km": 2.1},
             "large": {"isolation_m": 500, "day_pad_km": 4.0, "night_pad_km": 10.9}},
    "3079": {"name": "Methacrylonitrile, inhibited",         "guide": 131, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.4},
             "large": {"isolation_m": 200, "day_pad_km": 0.9, "night_pad_km": 3.1}},
    "3083": {"name": "Perchloryl fluoride",                  "guide": 124, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.3},
             "large": {"isolation_m": 150, "day_pad_km": 0.6, "night_pad_km": 2.1}},
    "3246": {"name": "Methanesulfonyl chloride",             "guide": 156, "hl": False,
             "small": {"isolation_m": 30,  "day_pad_km": 0.1, "night_pad_km": 0.2},
             "large": {"isolation_m": 100, "day_pad_km": 0.4, "night_pad_km": 1.3}},
}

# Common name / abbreviation aliases → UN number
_ALIASES: dict[str, str] = {
    "ammonia": "1005", "nh3": "1005",
    "chlorine": "1017", "cl2": "1017",
    "phosgene": "1076", "cg": "1076",
    "hcn": "1051", "hydrogen cyanide": "1051", "ac": "1051",
    "hf": "1052", "hydrogen fluoride": "1052",
    "h2s": "1053", "hydrogen sulfide": "1053",
    "cyanogen chloride": "1589", "ck": "1589",
    "so2": "1079", "sulfur dioxide": "1079",
    "mic": "2480", "methyl isocyanate": "2480",
    "arsine": "2188",
    "phosphine": "2199",
    "fluorine": "1045",
    "chloropicrin": "1580",
    "nickel carbonyl": "1259",
    "acrolein": "1092",
    "cn": "1697", "mace": "1697",
    "dm": "1698", "adamsite": "1698",
    "da": "1699",
    "ed": "1892",
    "nitric oxide": "1660", "no": "1660",
    "bromine": "1744",
    "co": "1016", "carbon monoxide": "1016",
    "stibine": "2676",
    "arsenic trichloride": "1560",
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_erg_entry(un_number: str) -> dict | None:
    """Return full ERG entry for a UN number (string, no leading zeros)."""
    un = un_number.strip().lstrip("0") or "0"
    un = un_number.strip().zfill(4)
    entry = ERG_TABLE1.get(un)
    if entry:
        return {"un_number": un, **entry}
    return None


def search_erg(query: str, limit: int = 10) -> list[dict]:
    """Search by UN number or chemical name substring."""
    q = query.strip().lower()
    if not q:
        return []

    results: list[dict] = []

    # Alias lookup
    alias_un = _ALIASES.get(q)
    if alias_un:
        e = ERG_TABLE1.get(alias_un.zfill(4))
        if e:
            results.append({"un_number": alias_un.zfill(4), "name": e["name"],
                             "guide": e["guide"], "hl": e["hl"]})

    # Exact UN number
    if q.isdigit():
        un = q.zfill(4)
        e = ERG_TABLE1.get(un)
        if e and not any(r["un_number"] == un for r in results):
            results.append({"un_number": un, "name": e["name"],
                             "guide": e["guide"], "hl": e["hl"]})

    # Name substring
    for un, e in ERG_TABLE1.items():
        if q in e["name"].lower() and not any(r["un_number"] == un for r in results):
            results.append({"un_number": un, "name": e["name"],
                             "guide": e["guide"], "hl": e["hl"]})
        if len(results) >= limit:
            break

    return results[:limit]


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _circle_coords(lat: float, lon: float, radius_m: float, segments: int = 64) -> list:
    pts = []
    for i in range(segments + 1):
        a = 2 * math.pi * i / segments
        dlat = (radius_m * math.cos(a)) / 111_320
        dlon = (radius_m * math.sin(a)) / (111_320 * math.cos(math.radians(lat)))
        pts.append([lon + dlon, lat + dlat])
    return pts


def _sector_coords(lat: float, lon: float, radius_m: float,
                   center_compass_deg: float, half_span: float = 90,
                   segments: int = 36) -> list:
    """Filled pie-sector polygon facing center_compass_deg (clockwise from N)."""
    pts = [[lon, lat]]  # hub
    start = center_compass_deg - half_span
    for i in range(segments + 1):
        angle_deg = start + (2 * half_span) * i / segments
        a = math.radians(angle_deg)
        dlat = (radius_m * math.cos(a)) / 111_320
        dlon = (radius_m * math.sin(a)) / (111_320 * math.cos(math.radians(lat)))
        pts.append([lon + dlon, lat + dlat])
    pts.append([lon, lat])  # close
    return pts


# ── Zone computation ──────────────────────────────────────────────────────────

def compute_erg_zones(lat: float, lon: float, un_number: str,
                      spill_size: str = "small",
                      wind_dir_from_deg: float | None = None) -> dict | None:
    """
    Compute ERG isolation and PAD zones as GeoJSON.

    wind_dir_from_deg: direction FROM which the wind blows (met convention).
                       None → show full circles (conservative).
    """
    entry = get_erg_entry(un_number)
    if not entry:
        return None

    sz = entry[spill_size]
    iso_r      = sz["isolation_m"]
    pad_day_m  = sz["day_pad_km"] * 1000
    pad_ngt_m  = sz["night_pad_km"] * 1000

    downwind = None if wind_dir_from_deg is None else (wind_dir_from_deg + 180) % 360

    def _zone_feature(level, label, color, radius_m, desc):
        coords = (
            _circle_coords(lat, lon, radius_m)
            if downwind is None or level == "isolation"
            else _sector_coords(lat, lon, radius_m, downwind)
        )
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "type": "erg_zone",
                "level": level, "label": label,
                "color": color, "radius_m": round(radius_m),
                "desc": desc,
            },
        }

    features = [
        _zone_feature("pad_night", f"PAD Night — {sz['night_pad_km']} km", "#FF4400",
                       pad_ngt_m, "Protective Action Distance (nighttime / stable conditions)"),
        _zone_feature("pad_day",   f"PAD Day — {sz['day_pad_km']} km",   "#FFAA00",
                       pad_day_m, "Protective Action Distance (daytime / unstable conditions)"),
        _zone_feature("isolation", f"Initial Isolation — {iso_r} m",     "#FF2200",
                       iso_r,     "Evacuate all persons in all directions from the spill"),
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "type": "erg_source",
                "un_number": entry["un_number"],
                "name": entry["name"],
            },
        },
    ]

    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "un_number": entry["un_number"],
        "name": entry["name"],
        "guide": entry["guide"],
        "hl": entry["hl"],
        "spill_size": spill_size,
        "small": entry["small"],
        "large": entry["large"],
        "wind_used": downwind is not None,
    }
