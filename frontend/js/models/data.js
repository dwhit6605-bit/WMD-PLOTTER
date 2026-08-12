/*
 * Offline model data bundle — GENERATED, do not edit by hand.
 *
 * Source of truth: backend/chemicals.py, aegl_db.py, erg.py.
 * Regenerate with:  python3 tests/gen_model_data.py
 *
 * Loads in the browser (window.WMDModels.data) and Node (module.exports).
 */
(function (root, factory) {
  const data = factory();
  if (typeof module === 'object' && module.exports) module.exports = data;
  else { root.WMDModels = root.WMDModels || {}; root.WMDModels.data = data; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  return {
 "CHEMICALS": [
  {
   "id": "ammonia",
   "name": "Ammonia",
   "formula": "NH₃",
   "cas": "7664-41-7",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 17.03,
   "boiling_point": -33.35,
   "vapor_pressure_20c": 6506,
   "vapor_density": 0.59,
   "physical_state": "gas",
   "idlh_ppm": 300,
   "erpg1_ppm": 25,
   "erpg2_ppm": 150,
   "erpg3_ppm": 750,
   "aegl1_60_ppm": 30,
   "aegl2_60_ppm": 160,
   "aegl3_60_ppm": 1100,
   "description": "Colorless gas with pungent odor. Lighter than air. Widely used in refrigeration and agriculture. BLEVE risk in pressurized storage.",
   "plume_color": "#FFD700"
  },
  {
   "id": "chlorine",
   "name": "Chlorine",
   "formula": "Cl₂",
   "cas": "7782-50-5",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 70.9,
   "boiling_point": -34.05,
   "vapor_pressure_20c": 6800,
   "vapor_density": 2.47,
   "physical_state": "gas",
   "idlh_ppm": 10,
   "erpg1_ppm": 1,
   "erpg2_ppm": 3,
   "erpg3_ppm": 20,
   "aegl1_60_ppm": 0.5,
   "aegl2_60_ppm": 2.0,
   "aegl3_60_ppm": 20.0,
   "description": "Yellow-green gas, heavier than air. Choking/pulmonary agent. Used in water treatment and chemical manufacturing. Dense-gas behavior.",
   "plume_color": "#ADFF2F"
  },
  {
   "id": "hydrogen_sulfide",
   "name": "Hydrogen Sulfide",
   "formula": "H₂S",
   "cas": "7783-06-4",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 34.08,
   "boiling_point": -60.28,
   "vapor_pressure_20c": 15600,
   "vapor_density": 1.19,
   "physical_state": "gas",
   "idlh_ppm": 50,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 30,
   "erpg3_ppm": 100,
   "aegl1_60_ppm": 0.51,
   "aegl2_60_ppm": 27,
   "aegl3_60_ppm": 50,
   "description": "Rotten-egg odor, flammable. Rapidly paralyzes olfactory nerve — smell cannot be relied upon for warning. Causes rapid unconsciousness at high concentrations.",
   "plume_color": "#DAA520"
  },
  {
   "id": "hydrogen_fluoride",
   "name": "Hydrogen Fluoride",
   "formula": "HF",
   "cas": "7664-39-3",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 20.01,
   "boiling_point": 19.5,
   "vapor_pressure_20c": 783,
   "vapor_density": 0.69,
   "physical_state": "gas",
   "idlh_ppm": 30,
   "erpg1_ppm": 2,
   "erpg2_ppm": 20,
   "erpg3_ppm": 50,
   "aegl1_60_ppm": 0.44,
   "aegl2_60_ppm": 22,
   "aegl3_60_ppm": 95,
   "description": "Extremely corrosive. Penetrates skin causing deep tissue and bone damage (hypocalcemia). Boiling point near ambient; dense white fumes in moist air.",
   "plume_color": "#FF6347"
  },
  {
   "id": "hydrogen_cyanide",
   "name": "Hydrogen Cyanide",
   "formula": "HCN",
   "cas": "74-90-8",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 27.03,
   "boiling_point": 25.6,
   "vapor_pressure_20c": 750,
   "vapor_density": 0.94,
   "physical_state": "gas",
   "idlh_ppm": 50,
   "erpg1_ppm": 2.5,
   "erpg2_ppm": 10,
   "erpg3_ppm": 25,
   "aegl1_60_ppm": 2.0,
   "aegl2_60_ppm": 7.1,
   "aegl3_60_ppm": 15,
   "description": "Colorless liquid/gas with bitter almond odor (30% cannot detect). Blood/cellular asphyxiant. Slightly lighter than air. Also military agent AC.",
   "plume_color": "#FF4500"
  },
  {
   "id": "phosgene",
   "name": "Phosgene",
   "formula": "COCl₂",
   "cas": "75-44-5",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 98.92,
   "boiling_point": 7.6,
   "vapor_pressure_20c": 1173,
   "vapor_density": 3.43,
   "physical_state": "gas",
   "idlh_ppm": 2,
   "erpg1_ppm": 0.2,
   "erpg2_ppm": 1.5,
   "erpg3_ppm": 7.5,
   "aegl1_60_ppm": 0.03,
   "aegl2_60_ppm": 0.6,
   "aegl3_60_ppm": 3.6,
   "description": "Colorless gas, faint hay odor. Choking agent (delayed pulmonary edema 4–24h). Very dense. WWI chemical weapon; still produced industrially.",
   "plume_color": "#98FB98"
  },
  {
   "id": "sulfur_dioxide",
   "name": "Sulfur Dioxide",
   "formula": "SO₂",
   "cas": "7446-09-5",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 64.06,
   "boiling_point": -10.0,
   "vapor_pressure_20c": 3300,
   "vapor_density": 2.26,
   "physical_state": "gas",
   "idlh_ppm": 100,
   "erpg1_ppm": 0.3,
   "erpg2_ppm": 3.0,
   "erpg3_ppm": 15,
   "aegl1_60_ppm": 0.2,
   "aegl2_60_ppm": 0.75,
   "aegl3_60_ppm": 9.2,
   "description": "Colorless gas, sharp pungent odor. Heavier than air. Upper respiratory irritant. Used in refrigeration and smelting. Major industrial release hazard.",
   "plume_color": "#FFA500"
  },
  {
   "id": "hydrogen_chloride",
   "name": "Hydrogen Chloride",
   "formula": "HCl",
   "cas": "7647-01-0",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 36.46,
   "boiling_point": -85.05,
   "vapor_pressure_20c": 40800,
   "vapor_density": 1.27,
   "physical_state": "gas",
   "idlh_ppm": 50,
   "erpg1_ppm": 3.0,
   "erpg2_ppm": 20,
   "erpg3_ppm": 150,
   "aegl1_60_ppm": 1.8,
   "aegl2_60_ppm": 22,
   "aegl3_60_ppm": 620,
   "description": "Colorless gas. Forms dense white fumes (hydrochloric acid mist) in moist air. Strong respiratory irritant. Slightly heavier than air.",
   "plume_color": "#20B2AA"
  },
  {
   "id": "carbon_monoxide",
   "name": "Carbon Monoxide",
   "formula": "CO",
   "cas": "630-08-0",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 28.01,
   "boiling_point": -191.5,
   "vapor_pressure_20c": 99999,
   "vapor_density": 0.97,
   "physical_state": "gas",
   "idlh_ppm": 1200,
   "erpg1_ppm": 200,
   "erpg2_ppm": 350,
   "erpg3_ppm": 500,
   "aegl1_60_ppm": 83,
   "aegl2_60_ppm": 420,
   "aegl3_60_ppm": 1700,
   "description": "Odorless, colorless, non-irritating. Binds hemoglobin (230x O2 affinity). No warning properties. Produced by incomplete combustion. Nearly same density as air.",
   "plume_color": "#808080"
  },
  {
   "id": "nitrogen_dioxide",
   "name": "Nitrogen Dioxide",
   "formula": "NO₂",
   "cas": "10102-44-0",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 46.01,
   "boiling_point": 21.2,
   "vapor_pressure_20c": 720,
   "vapor_density": 1.58,
   "physical_state": "gas",
   "idlh_ppm": 20,
   "erpg1_ppm": 1.0,
   "erpg2_ppm": 15,
   "erpg3_ppm": 30,
   "aegl1_60_ppm": 0.5,
   "aegl2_60_ppm": 20,
   "aegl3_60_ppm": 25,
   "description": "Reddish-brown gas. Delayed pulmonary edema. Heavier than air. Produced in acid spills, fertilizer plants, and combustion. Equilibrium with N₂O₄.",
   "plume_color": "#CD853F"
  },
  {
   "id": "methyl_isocyanate",
   "name": "Methyl Isocyanate",
   "formula": "CH₃NCO",
   "cas": "624-83-9",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 57.05,
   "boiling_point": 39.1,
   "vapor_pressure_20c": 348,
   "vapor_density": 1.97,
   "physical_state": "liquid",
   "idlh_ppm": 3,
   "erpg1_ppm": 0.025,
   "erpg2_ppm": 0.5,
   "erpg3_ppm": 5.0,
   "aegl1_60_ppm": 0.013,
   "aegl2_60_ppm": 0.1,
   "aegl3_60_ppm": 1.2,
   "description": "Bhopal disaster agent. Extremely toxic, reacts violently with water to produce CO₂ and heat (runaway reaction risk). Heavier than air. Severe respiratory/eye damage.",
   "plume_color": "#FF0000"
  },
  {
   "id": "acrolein",
   "name": "Acrolein",
   "formula": "C₃H₄O",
   "cas": "107-02-8",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 56.06,
   "boiling_point": 52.5,
   "vapor_pressure_20c": 210,
   "vapor_density": 1.94,
   "physical_state": "liquid",
   "idlh_ppm": 2,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 0.5,
   "erpg3_ppm": 3.0,
   "aegl1_60_ppm": 0.03,
   "aegl2_60_ppm": 0.44,
   "aegl3_60_ppm": 2.5,
   "description": "Extremely toxic. Combustion product of plastics/wood. Very strong lachrymator. Used as biocide/herbicide. Highly flammable.",
   "plume_color": "#FF8C00"
  },
  {
   "id": "acrylonitrile",
   "name": "Acrylonitrile",
   "formula": "C₃H₃N",
   "cas": "107-13-1",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 53.06,
   "boiling_point": 77.3,
   "vapor_pressure_20c": 83,
   "vapor_density": 1.83,
   "physical_state": "liquid",
   "idlh_ppm": 85,
   "erpg1_ppm": 2.5,
   "erpg2_ppm": 35,
   "erpg3_ppm": 75,
   "aegl1_60_ppm": 1.6,
   "aegl2_60_ppm": 29,
   "aegl3_60_ppm": 85,
   "description": "Flammable liquid used in acrylic fiber production. Cyanogens hazard. IARC Group 2B carcinogen. Forms explosive vapors.",
   "plume_color": "#9370DB"
  },
  {
   "id": "arsine",
   "name": "Arsine",
   "formula": "AsH₃",
   "cas": "7784-42-1",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 77.95,
   "boiling_point": -62.5,
   "vapor_pressure_20c": 11000,
   "vapor_density": 2.7,
   "physical_state": "gas",
   "idlh_ppm": 3,
   "erpg1_ppm": 0.005,
   "erpg2_ppm": 0.1,
   "erpg3_ppm": 1.0,
   "aegl1_60_ppm": 0.005,
   "aegl2_60_ppm": 0.17,
   "aegl3_60_ppm": 0.62,
   "description": "Colorless, garlic-odored gas. Hemolytic agent (destroys red blood cells). Used in semiconductor manufacturing. Very dense, hugs ground.",
   "plume_color": "#7CFC00"
  },
  {
   "id": "phosphine",
   "name": "Phosphine",
   "formula": "PH₃",
   "cas": "7803-51-2",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 33.99,
   "boiling_point": -87.7,
   "vapor_pressure_20c": 35000,
   "vapor_density": 1.17,
   "physical_state": "gas",
   "idlh_ppm": 50,
   "erpg1_ppm": 0.05,
   "erpg2_ppm": 0.5,
   "erpg3_ppm": 5.0,
   "aegl1_60_ppm": 0.03,
   "aegl2_60_ppm": 0.27,
   "aegl3_60_ppm": 1.2,
   "description": "Highly toxic, flammable gas. Used as fumigant and in semiconductor manufacturing. Inhibits cytochrome c oxidase. Garlic/fish odor.",
   "plume_color": "#32CD32"
  },
  {
   "id": "bromine",
   "name": "Bromine",
   "formula": "Br₂",
   "cas": "7726-95-6",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 159.8,
   "boiling_point": 58.8,
   "vapor_pressure_20c": 173,
   "vapor_density": 5.51,
   "physical_state": "liquid",
   "idlh_ppm": 3,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 0.5,
   "erpg3_ppm": 5.0,
   "aegl1_60_ppm": 0.1,
   "aegl2_60_ppm": 0.5,
   "aegl3_60_ppm": 5.0,
   "description": "Reddish-brown fuming liquid. Very dense vapors. Strong oxidizer and corrosive. Severe respiratory and skin damage. Spreads at ground level.",
   "plume_color": "#8B0000"
  },
  {
   "id": "fluorine",
   "name": "Fluorine",
   "formula": "F₂",
   "cas": "7782-41-4",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 38.0,
   "boiling_point": -188.1,
   "vapor_pressure_20c": 99999,
   "vapor_density": 1.31,
   "physical_state": "gas",
   "idlh_ppm": 25,
   "erpg1_ppm": 0.5,
   "erpg2_ppm": 5.0,
   "erpg3_ppm": 20,
   "aegl1_60_ppm": 0.19,
   "aegl2_60_ppm": 1.7,
   "aegl3_60_ppm": 11,
   "description": "Most reactive element. Colorless to pale yellow gas. Reacts violently with virtually all materials. Severe respiratory damage at very low concentrations.",
   "plume_color": "#FFEC8B"
  },
  {
   "id": "chlorine_trifluoride",
   "name": "Chlorine Trifluoride",
   "formula": "ClF₃",
   "cas": "7790-91-2",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 92.45,
   "boiling_point": 11.75,
   "vapor_pressure_20c": 628,
   "vapor_density": 3.19,
   "physical_state": "gas",
   "idlh_ppm": null,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 1.0,
   "erpg3_ppm": 10,
   "aegl1_60_ppm": 0.026,
   "aegl2_60_ppm": 0.54,
   "aegl3_60_ppm": 3.5,
   "description": "Extreme oxidizer — ignites concrete, glass, asbestos on contact. Dense vapor. Used in nuclear fuel processing. Essentially impossible to fight chemically.",
   "plume_color": "#FF69B4"
  },
  {
   "id": "ethylene_oxide",
   "name": "Ethylene Oxide",
   "formula": "C₂H₄O",
   "cas": "75-21-8",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 44.05,
   "boiling_point": 10.7,
   "vapor_pressure_20c": 1460,
   "vapor_density": 1.52,
   "physical_state": "gas",
   "idlh_ppm": 800,
   "erpg1_ppm": 50,
   "erpg2_ppm": 200,
   "erpg3_ppm": 800,
   "aegl1_60_ppm": 8.0,
   "aegl2_60_ppm": 50,
   "aegl3_60_ppm": 390,
   "description": "Flammable, slightly heavier than air. Used in sterilization and chemical manufacturing. IARC Group 1 carcinogen. Wide explosive range (3–100%).",
   "plume_color": "#6495ED"
  },
  {
   "id": "formaldehyde",
   "name": "Formaldehyde",
   "formula": "CH₂O",
   "cas": "50-00-0",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 30.03,
   "boiling_point": -19.0,
   "vapor_pressure_20c": 3850,
   "vapor_density": 1.04,
   "physical_state": "gas",
   "idlh_ppm": 20,
   "erpg1_ppm": 1.0,
   "erpg2_ppm": 10,
   "erpg3_ppm": 25,
   "aegl1_60_ppm": 0.9,
   "aegl2_60_ppm": 14,
   "aegl3_60_ppm": 67,
   "description": "Pungent gas. Carcinogen (IARC Group 1). Severe eye/upper respiratory irritant. Nearly same density as air. Used in resins, textiles, preservatives.",
   "plume_color": "#DEB887"
  },
  {
   "id": "cyanogen_chloride",
   "name": "Cyanogen Chloride",
   "formula": "ClCN",
   "cas": "506-77-4",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 61.47,
   "boiling_point": 12.7,
   "vapor_pressure_20c": 1000,
   "vapor_density": 2.12,
   "physical_state": "gas",
   "idlh_ppm": null,
   "erpg1_ppm": 0.4,
   "erpg2_ppm": 2.0,
   "erpg3_ppm": 10,
   "aegl1_60_ppm": null,
   "aegl2_60_ppm": null,
   "aegl3_60_ppm": null,
   "description": "Military blood agent CK. Colorless gas. Heavier than air. Converts to HCN in body. Lachrymator at low concentrations. Used as tear gas agent.",
   "plume_color": "#DC143C"
  },
  {
   "id": "toluene_diisocyanate",
   "name": "Toluene Diisocyanate (TDI)",
   "formula": "C₉H₆N₂O₂",
   "cas": "584-84-9",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 174.16,
   "boiling_point": 251.0,
   "vapor_pressure_20c": 0.013,
   "vapor_density": 6.0,
   "physical_state": "liquid",
   "idlh_ppm": 2.5,
   "erpg1_ppm": 0.01,
   "erpg2_ppm": 0.1,
   "erpg3_ppm": 1.0,
   "aegl1_60_ppm": 0.002,
   "aegl2_60_ppm": 0.1,
   "aegl3_60_ppm": 0.5,
   "description": "Potent sensitizer and respiratory allergen. Used in polyurethane foam production. Low vapor pressure but extremely toxic. Causes occupational asthma.",
   "plume_color": "#FF1493"
  },
  {
   "id": "methyl_bromide",
   "name": "Methyl Bromide",
   "formula": "CH₃Br",
   "cas": "74-83-9",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 94.94,
   "boiling_point": 3.56,
   "vapor_pressure_20c": 1600,
   "vapor_density": 3.27,
   "physical_state": "gas",
   "idlh_ppm": 250,
   "erpg1_ppm": 25,
   "erpg2_ppm": 200,
   "erpg3_ppm": 850,
   "aegl1_60_ppm": 18,
   "aegl2_60_ppm": 68,
   "aegl3_60_ppm": 310,
   "description": "Colorless odorless gas. Agricultural fumigant. Neurotoxic. Ozone-depleting. Very dense vapors accumulate in low-lying areas. Chloropicrin often added as warning agent.",
   "plume_color": "#556B2F"
  },
  {
   "id": "dimethyl_sulfate",
   "name": "Dimethyl Sulfate",
   "formula": "(CH₃O)₂SO₂",
   "cas": "77-78-1",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 126.13,
   "boiling_point": 188.0,
   "vapor_pressure_20c": 0.7,
   "vapor_density": 4.35,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 1.0,
   "erpg3_ppm": 10,
   "aegl1_60_ppm": null,
   "aegl2_60_ppm": null,
   "aegl3_60_ppm": null,
   "description": "Oily liquid. Strong alkylating agent — carcinogenic, mutagenic. Low odor warning. Delayed symptoms. Very dense vapors. Hydrolyzes to sulfuric acid.",
   "plume_color": "#8B4513"
  },
  {
   "id": "nitrogen_tetroxide",
   "name": "Nitrogen Tetroxide",
   "formula": "N₂O₄",
   "cas": "10544-72-6",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 92.01,
   "boiling_point": 21.15,
   "vapor_pressure_20c": 700,
   "vapor_density": 3.17,
   "physical_state": "liquid",
   "idlh_ppm": 20,
   "erpg1_ppm": 1.0,
   "erpg2_ppm": 15,
   "erpg3_ppm": 30,
   "aegl1_60_ppm": 0.5,
   "aegl2_60_ppm": 20,
   "aegl3_60_ppm": 25,
   "description": "Reddish-brown fuming oxidizer. Rocket propellant (NTO). Dissociates to NO₂ at normal temperatures. Delayed pulmonary edema. Very corrosive, very dense.",
   "plume_color": "#B8860B"
  },
  {
   "id": "chloropicrin",
   "name": "Chloropicrin",
   "formula": "CCl₃NO₂",
   "cas": "76-06-2",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 164.37,
   "boiling_point": 112.4,
   "vapor_pressure_20c": 18.3,
   "vapor_density": 5.67,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 1.0,
   "erpg3_ppm": 3.0,
   "aegl1_60_ppm": null,
   "aegl2_60_ppm": null,
   "aegl3_60_ppm": null,
   "description": "WWI choking/lachrymatory agent (PS). Agricultural fumigant. No odor warning before harmful levels. Vomiting agent at sub-lethal doses. Very dense vapors.",
   "plume_color": "#4682B4"
  },
  {
   "id": "anhydrous_hf",
   "name": "Anhydrous HF (Alkylation Unit)",
   "formula": "HF",
   "cas": "7664-39-3",
   "category": "TIC",
   "subcategory": "Refinery/Petrochemical",
   "mw": 20.01,
   "boiling_point": 19.5,
   "vapor_pressure_20c": 783,
   "vapor_density": 0.69,
   "physical_state": "gas",
   "idlh_ppm": 30,
   "erpg1_ppm": 2.0,
   "erpg2_ppm": 20,
   "erpg3_ppm": 50,
   "aegl1_60_ppm": 0.44,
   "aegl2_60_ppm": 22,
   "aegl3_60_ppm": 95,
   "description": "Used in petroleum alkylation. Aerosol cloud formation — may hug ground despite lower density. Target for CFATS high-risk chemical facilities.",
   "plume_color": "#FF6347"
  },
  {
   "id": "oleum",
   "name": "Oleum (Fuming Sulfuric Acid)",
   "formula": "H₂SO₄·SO₃",
   "cas": "8014-95-7",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 98.08,
   "boiling_point": 337.0,
   "vapor_pressure_20c": 1.0,
   "vapor_density": 3.39,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.1,
   "aegl2_60_ppm": 0.6,
   "aegl3_60_ppm": 12,
   "description": "Generates SO₃ fumes. Extremely corrosive, reacts violently with water. White fuming clouds. Use SO₂/SO₃ thresholds for plume modeling.",
   "plume_color": "#A9A9A9"
  },
  {
   "id": "boron_trifluoride",
   "name": "Boron Trifluoride",
   "formula": "BF₃",
   "cas": "7637-07-2",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 67.81,
   "boiling_point": -99.9,
   "vapor_pressure_20c": 99999,
   "vapor_density": 2.38,
   "physical_state": "gas",
   "idlh_ppm": null,
   "erpg1_ppm": 1.0,
   "erpg2_ppm": 4.0,
   "erpg3_ppm": 20,
   "aegl1_60_ppm": 0.5,
   "aegl2_60_ppm": 4.6,
   "aegl3_60_ppm": 25,
   "description": "Colorless, pungent gas. Fumes in moist air forming HF/H₃BO₃ aerosol. Used as Lewis acid catalyst. Heavier than air. Extremely irritating to lungs.",
   "plume_color": "#20B2AA"
  },
  {
   "id": "sarin",
   "name": "Sarin (GB)",
   "formula": "C₄H₁₀FO₂P",
   "cas": "107-44-8",
   "category": "CWA",
   "subcategory": "Nerve Agent (G-series)",
   "mw": 140.09,
   "boiling_point": 158.0,
   "vapor_pressure_20c": 2.1,
   "vapor_density": 4.86,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.00017,
   "aegl2_60_ppm": 0.00061,
   "aegl3_60_ppm": 0.0038,
   "description": "NATO designation GB. Organophosphorus nerve agent. Irreversible acetylcholinesterase inhibitor. Colorless liquid with faint fruity odor. Rapid incapacitation. Used in Syrian civil war.",
   "plume_color": "#8B0000",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "soman",
   "name": "Soman (GD)",
   "formula": "C₇H₁₆FO₂P",
   "cas": "96-64-0",
   "category": "CWA",
   "subcategory": "Nerve Agent (G-series)",
   "mw": 182.17,
   "boiling_point": 198.0,
   "vapor_pressure_20c": 0.4,
   "vapor_density": 6.33,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 4.7e-05,
   "aegl2_60_ppm": 0.0003,
   "aegl3_60_ppm": 0.019,
   "description": "NATO designation GD. Most toxic of G-series. 'Aging' makes antidotes less effective. Camphor-like odor. Lower volatility than GB but very dense.",
   "plume_color": "#A0522D",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "tabun",
   "name": "Tabun (GA)",
   "formula": "C₅H₁₁N₂O₂P",
   "cas": "77-81-6",
   "category": "CWA",
   "subcategory": "Nerve Agent (G-series)",
   "mw": 162.13,
   "boiling_point": 247.5,
   "vapor_pressure_20c": 0.037,
   "vapor_density": 5.63,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.0008,
   "aegl2_60_ppm": 0.0012,
   "aegl3_60_ppm": 0.0072,
   "description": "First nerve agent synthesized (Germany, 1936). Faint fruity/almond odor. Lowest volatility of G-series. Stockpiled by several nations. Still a significant threat.",
   "plume_color": "#B22222",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "vx",
   "name": "VX",
   "formula": "C₁₁H₂₆NO₂PS",
   "cas": "50782-69-9",
   "category": "CWA",
   "subcategory": "Nerve Agent (V-series)",
   "mw": 267.37,
   "boiling_point": 298.0,
   "vapor_pressure_20c": 0.0007,
   "vapor_density": 9.2,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 1.8e-06,
   "aegl2_60_ppm": 8.8e-06,
   "aegl3_60_ppm": 8.8e-05,
   "description": "Most toxic nerve agent. Oily, persistent liquid. Very low vapor pressure — mainly a skin/contact hazard, but vapor still hazardous in confined areas or warm weather.",
   "plume_color": "#4B0082",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "novichok",
   "name": "Novichok A-230",
   "formula": "C₅H₁₁FNO₂P",
   "cas": "unknown",
   "category": "CWA",
   "subcategory": "Nerve Agent (Novichok)",
   "mw": 163.12,
   "boiling_point": null,
   "vapor_pressure_20c": null,
   "vapor_density": 5.65,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 2e-07,
   "aegl2_60_ppm": 1e-06,
   "aegl3_60_ppm": 9e-06,
   "description": "Fourth-generation nerve agent. Estimated 5–10× more toxic than VX. Used in Salisbury (2018) and Navalny (2020) poisonings. Thresholds are engineering estimates only.",
   "plume_color": "#800080",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "mustard_hd",
   "name": "Sulfur Mustard (HD)",
   "formula": "C₄H₈Cl₂S",
   "cas": "505-60-2",
   "category": "CWA",
   "subcategory": "Blister Agent (Vesicant)",
   "mw": 159.07,
   "boiling_point": 217.0,
   "vapor_pressure_20c": 0.072,
   "vapor_density": 5.5,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.00022,
   "aegl2_60_ppm": 0.00043,
   "aegl3_60_ppm": 0.0077,
   "description": "Garlic/mustard odor. Delayed effects (2–24h) — no immediate pain on skin contact. DNA alkylating agent. Carcinogenic. Used in WWI, Iran-Iraq War. Persists in environment.",
   "plume_color": "#8B8B00",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "lewisite",
   "name": "Lewisite (L)",
   "formula": "C₂H₂AsCl₃",
   "cas": "541-25-3",
   "category": "CWA",
   "subcategory": "Blister Agent (Vesicant)",
   "mw": 207.32,
   "boiling_point": 190.0,
   "vapor_pressure_20c": 0.394,
   "vapor_density": 7.2,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.0001,
   "aegl2_60_ppm": 0.0026,
   "aegl3_60_ppm": 0.026,
   "description": "Geranium-like odor. Immediate pain on contact (unlike mustard). Arsenic-based; BAL (British Anti-Lewisite) is antidote. Very dense vapors. Hydrolysis produces toxic arsenical.",
   "plume_color": "#556B2F",
   "warning": "SCHEDULE 1 CWC AGENT — ILLEGAL TO PRODUCE OR STOCKPILE"
  },
  {
   "id": "phosgene_oxime",
   "name": "Phosgene Oxime (CX)",
   "formula": "CCl₂NOH",
   "cas": "1794-86-1",
   "category": "CWA",
   "subcategory": "Blister Agent (Urticant)",
   "mw": 113.94,
   "boiling_point": 129.0,
   "vapor_pressure_20c": 11.2,
   "vapor_density": 3.9,
   "physical_state": "solid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.0001,
   "aegl2_60_ppm": 0.001,
   "aegl3_60_ppm": 0.01,
   "description": "Not a true vesicant — nettle/urticant agent causing immediate intense pain. Penetrates protective equipment rapidly. Solid at room temp; 'snow' dispersal. Very rare.",
   "plume_color": "#DDA0DD",
   "warning": "SCHEDULE 1 CWC AGENT"
  },
  {
   "id": "hydrogen_cyanide_ac",
   "name": "Hydrogen Cyanide (AC)",
   "formula": "HCN",
   "cas": "74-90-8",
   "category": "CWA",
   "subcategory": "Blood Agent",
   "mw": 27.03,
   "boiling_point": 25.6,
   "vapor_pressure_20c": 750,
   "vapor_density": 0.94,
   "physical_state": "gas",
   "idlh_ppm": 50,
   "erpg1_ppm": 2.5,
   "erpg2_ppm": 10,
   "erpg3_ppm": 25,
   "aegl1_60_ppm": 2.0,
   "aegl2_60_ppm": 7.1,
   "aegl3_60_ppm": 15,
   "description": "Military designation AC. Blood/cellular asphyxiant. Slightly lighter than air. Poor persistence. Bitter almond odor — 30% cannot smell it. High concentrations cause rapid death.",
   "plume_color": "#FF4500",
   "warning": "SCHEDULE 3 CWC AGENT"
  },
  {
   "id": "diphosgene",
   "name": "Diphosgene (DP)",
   "formula": "Cl₃COCOCl",
   "cas": "503-38-8",
   "category": "CWA",
   "subcategory": "Choking Agent",
   "mw": 197.83,
   "boiling_point": 127.0,
   "vapor_pressure_20c": 10,
   "vapor_density": 6.9,
   "physical_state": "liquid",
   "idlh_ppm": null,
   "erpg1_ppm": 0.1,
   "erpg2_ppm": 0.6,
   "erpg3_ppm": 2.0,
   "aegl1_60_ppm": 0.03,
   "aegl2_60_ppm": 0.6,
   "aegl3_60_ppm": 3.6,
   "description": "Trichloromethyl chloroformate. Hydrolyzes to phosgene (CG). WWI choking agent. Dense liquid, very dense vapors. Use phosgene AEGL values for planning.",
   "plume_color": "#228B22",
   "warning": "SCHEDULE 3 CWC AGENT"
  },
  {
   "id": "chlorine_cwa",
   "name": "Chlorine (CL)",
   "formula": "Cl₂",
   "cas": "7782-50-5",
   "category": "CWA",
   "subcategory": "Choking Agent",
   "mw": 70.9,
   "boiling_point": -34.05,
   "vapor_pressure_20c": 6800,
   "vapor_density": 2.47,
   "physical_state": "gas",
   "idlh_ppm": 10,
   "erpg1_ppm": 1,
   "erpg2_ppm": 3,
   "erpg3_ppm": 20,
   "aegl1_60_ppm": 0.5,
   "aegl2_60_ppm": 2.0,
   "aegl3_60_ppm": 20.0,
   "description": "First mass-use chemical weapon (Ypres, 1915). Yellow-green, visible cloud. Pulmonary edema. Dense vapors fill trenches/low areas. Still used by non-state actors (ISIS, Syria).",
   "plume_color": "#ADFF2F",
   "warning": "SCHEDULE 3 CWC AGENT (dual-use)"
  },
  {
   "id": "adamsite",
   "name": "Adamsite (DM)",
   "formula": "C₁₂H₉AsClNO",
   "cas": "578-94-9",
   "category": "CWA",
   "subcategory": "Vomiting Agent",
   "mw": 277.58,
   "boiling_point": 410.0,
   "vapor_pressure_20c": 0.0002,
   "vapor_density": 9.6,
   "physical_state": "solid",
   "idlh_ppm": null,
   "erpg1_ppm": null,
   "erpg2_ppm": null,
   "erpg3_ppm": null,
   "aegl1_60_ppm": 0.0001,
   "aegl2_60_ppm": 0.001,
   "aegl3_60_ppm": 0.01,
   "description": "Diphenylaminochloroarsine. Vomiting/sneezing agent. Dispersed as smoke/aerosol. Solid at room temp. Causes severe nausea, vomiting, and headache. Used for crowd control.",
   "plume_color": "#708090"
  },
  {
   "id": "anhydrous_ammonia_liquid",
   "name": "Liquid Ammonia (Rail/Storage)",
   "formula": "NH₃",
   "cas": "7664-41-7",
   "category": "TIC",
   "subcategory": "Refrigerant/Agricultural",
   "mw": 17.03,
   "boiling_point": -33.35,
   "vapor_pressure_20c": 6506,
   "vapor_density": 0.59,
   "physical_state": "liquid",
   "idlh_ppm": 300,
   "erpg1_ppm": 25,
   "erpg2_ppm": 150,
   "erpg3_ppm": 750,
   "aegl1_60_ppm": 30,
   "aegl2_60_ppm": 160,
   "aegl3_60_ppm": 1100,
   "description": "Large-scale ammonia transport/storage. Flash evaporation on release forms two-phase aerosol cloud. Initial cloud may behave as dense gas before aerosol evaporates. Major CAMEO scenario.",
   "plume_color": "#FFD700"
  },
  {
   "id": "carbon_disulfide",
   "name": "Carbon Disulfide",
   "formula": "CS₂",
   "cas": "75-15-0",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 76.14,
   "boiling_point": 46.2,
   "vapor_pressure_20c": 297,
   "vapor_density": 2.63,
   "physical_state": "liquid",
   "idlh_ppm": 500,
   "erpg1_ppm": 1.0,
   "erpg2_ppm": 50,
   "erpg3_ppm": 500,
   "aegl1_60_ppm": 13,
   "aegl2_60_ppm": 50,
   "aegl3_60_ppm": 500,
   "description": "Highly flammable (flash point -30°C). Neurotoxin. Used in rayon/rubber production. Very low ignition temperature (100°C). Dense vapors.",
   "plume_color": "#DAA520"
  },
  {
   "id": "methyl_mercaptan",
   "name": "Methyl Mercaptan",
   "formula": "CH₃SH",
   "cas": "74-93-1",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 48.11,
   "boiling_point": 5.95,
   "vapor_pressure_20c": 1620,
   "vapor_density": 1.66,
   "physical_state": "gas",
   "idlh_ppm": 150,
   "erpg1_ppm": 0.005,
   "erpg2_ppm": 25,
   "erpg3_ppm": 100,
   "aegl1_60_ppm": 0.002,
   "aegl2_60_ppm": 17,
   "aegl3_60_ppm": 68,
   "description": "Skunk-like odor at ppb levels. Added to natural gas as odorant. Texas City 1987 — large rail car release. Flammable and toxic at higher concentrations.",
   "plume_color": "#9ACD32"
  },
  {
   "id": "allyl_chloride",
   "name": "Allyl Chloride",
   "formula": "C₃H₅Cl",
   "cas": "107-05-1",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 76.53,
   "boiling_point": 44.5,
   "vapor_pressure_20c": 295,
   "vapor_density": 2.64,
   "physical_state": "liquid",
   "idlh_ppm": 300,
   "erpg1_ppm": 3.0,
   "erpg2_ppm": 40,
   "erpg3_ppm": 300,
   "aegl1_60_ppm": 2.0,
   "aegl2_60_ppm": 22,
   "aegl3_60_ppm": 120,
   "description": "Pungent, lachrymatory. Used in epichlorohydrin production. Flammable. Liver and kidney toxin. Dense vapors.",
   "plume_color": "#6B8E23"
  },
  {
   "id": "butadiene",
   "name": "1,3-Butadiene",
   "formula": "C₄H₆",
   "cas": "106-99-0",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 54.09,
   "boiling_point": -4.41,
   "vapor_pressure_20c": 2400,
   "vapor_density": 1.87,
   "physical_state": "gas",
   "idlh_ppm": 2000,
   "erpg1_ppm": 10,
   "erpg2_ppm": 50,
   "erpg3_ppm": 5000,
   "aegl1_60_ppm": 21,
   "aegl2_60_ppm": 1700,
   "aegl3_60_ppm": 5000,
   "description": "Primarily a fire/explosion hazard. IARC Group 1 carcinogen. Wide flammable range (2–12%). Used in synthetic rubber production. Dense vapors.",
   "plume_color": "#B0C4DE"
  },
  {
   "id": "vinyl_chloride",
   "name": "Vinyl Chloride",
   "formula": "C₂H₃Cl",
   "cas": "75-01-4",
   "category": "TIC",
   "subcategory": "Industrial Gas",
   "mw": 62.5,
   "boiling_point": -13.4,
   "vapor_pressure_20c": 2580,
   "vapor_density": 2.15,
   "physical_state": "gas",
   "idlh_ppm": null,
   "erpg1_ppm": 500,
   "erpg2_ppm": 5000,
   "erpg3_ppm": 20000,
   "aegl1_60_ppm": 82,
   "aegl2_60_ppm": 4900,
   "aegl3_60_ppm": 22000,
   "description": "East Palestine, OH (2023). IARC Group 1 carcinogen (angiosarcoma). Explosion/fire hazard primary concern in incidents. Dense vapors. PVC precursor.",
   "plume_color": "#87CEEB"
  },
  {
   "id": "styrene",
   "name": "Styrene",
   "formula": "C₈H₈",
   "cas": "100-42-5",
   "category": "TIC",
   "subcategory": "Industrial Liquid",
   "mw": 104.15,
   "boiling_point": 145.2,
   "vapor_pressure_20c": 5.0,
   "vapor_density": 3.6,
   "physical_state": "liquid",
   "idlh_ppm": 700,
   "erpg1_ppm": 50,
   "erpg2_ppm": 250,
   "erpg3_ppm": 1000,
   "aegl1_60_ppm": 6.0,
   "aegl2_60_ppm": 170,
   "aegl3_60_ppm": 850,
   "description": "Sweet odor. Polystyrene precursor. Vishakhapatnam chemical plant disaster (2020) involved styrene release. Dense vapors. CNS depressant at high levels.",
   "plume_color": "#F0E68C"
  }
 ],
 "AEGL": {
  "ammonia": {
   "1": {
    "10min": 30,
    "60min": 30,
    "8hr": 30
   },
   "2": {
    "10min": 220,
    "60min": 160,
    "8hr": 110
   },
   "3": {
    "10min": 2700,
    "60min": 1100,
    "8hr": 390
   }
  },
  "chlorine": {
   "1": {
    "10min": 0.5,
    "60min": 0.5,
    "8hr": 0.5
   },
   "2": {
    "10min": 2.8,
    "60min": 2.0,
    "8hr": 0.71
   },
   "3": {
    "10min": 50,
    "60min": 20,
    "8hr": 7.1
   }
  },
  "chlorine_cwa": {
   "1": {
    "10min": 0.5,
    "60min": 0.5,
    "8hr": 0.5
   },
   "2": {
    "10min": 2.8,
    "60min": 2.0,
    "8hr": 0.71
   },
   "3": {
    "10min": 50,
    "60min": 20,
    "8hr": 7.1
   }
  },
  "hydrogen_sulfide": {
   "1": {
    "10min": 0.75,
    "60min": 0.51,
    "8hr": 0.25
   },
   "2": {
    "10min": 41,
    "60min": 27,
    "8hr": 17
   },
   "3": {
    "10min": 76,
    "60min": 50,
    "8hr": 31
   }
  },
  "hydrogen_fluoride": {
   "1": {
    "10min": 1.0,
    "60min": 1.0,
    "8hr": 1.0
   },
   "2": {
    "10min": 95,
    "60min": 24,
    "8hr": 8.6
   },
   "3": {
    "10min": 170,
    "60min": 44,
    "8hr": 15
   }
  },
  "anhydrous_hf": {
   "1": {
    "10min": 1.0,
    "60min": 1.0,
    "8hr": 1.0
   },
   "2": {
    "10min": 95,
    "60min": 24,
    "8hr": 8.6
   },
   "3": {
    "10min": 170,
    "60min": 44,
    "8hr": 15
   }
  },
  "hydrogen_cyanide": {
   "1": {
    "10min": 2.5,
    "60min": 2.5,
    "8hr": 2.5
   },
   "2": {
    "10min": 17,
    "60min": 7.1,
    "8hr": 2.5
   },
   "3": {
    "10min": 27,
    "60min": 15,
    "8hr": 6.6
   }
  },
  "hydrogen_cyanide_ac": {
   "1": {
    "10min": 2.5,
    "60min": 2.5,
    "8hr": 2.5
   },
   "2": {
    "10min": 17,
    "60min": 7.1,
    "8hr": 2.5
   },
   "3": {
    "10min": 27,
    "60min": 15,
    "8hr": 6.6
   }
  },
  "phosgene": {
   "1": {
    "10min": 0.3,
    "60min": 0.3,
    "8hr": 0.3
   },
   "2": {
    "10min": 1.5,
    "60min": 0.3,
    "8hr": 0.04
   },
   "3": {
    "10min": 3.6,
    "60min": 0.75,
    "8hr": 0.1
   }
  },
  "diphosgene": {
   "1": {
    "10min": 0.3,
    "60min": 0.3,
    "8hr": 0.3
   },
   "2": {
    "10min": 1.5,
    "60min": 0.3,
    "8hr": 0.04
   },
   "3": {
    "10min": 3.6,
    "60min": 0.75,
    "8hr": 0.1
   }
  },
  "sulfur_dioxide": {
   "1": {
    "10min": 0.2,
    "60min": 0.2,
    "8hr": 0.2
   },
   "2": {
    "10min": 0.75,
    "60min": 0.75,
    "8hr": 0.75
   },
   "3": {
    "10min": 30,
    "60min": 30,
    "8hr": 30
   }
  },
  "hydrogen_chloride": {
   "1": {
    "10min": 1.8,
    "60min": 1.8,
    "8hr": 1.8
   },
   "2": {
    "10min": 100,
    "60min": 43,
    "8hr": 26
   },
   "3": {
    "10min": 620,
    "60min": 210,
    "8hr": 130
   }
  },
  "arsine": {
   "1": {
    "10min": 0.005,
    "60min": 0.005,
    "8hr": 0.005
   },
   "2": {
    "10min": 0.13,
    "60min": 0.08,
    "8hr": 0.057
   },
   "3": {
    "10min": 0.75,
    "60min": 0.43,
    "8hr": 0.29
   }
  },
  "phosphine": {
   "1": {
    "10min": 0.03,
    "60min": 0.03,
    "8hr": 0.03
   },
   "2": {
    "10min": 0.27,
    "60min": 0.21,
    "8hr": 0.16
   },
   "3": {
    "10min": 0.5,
    "60min": 0.4,
    "8hr": 0.3
   }
  },
  "bromine": {
   "1": {
    "10min": 0.2,
    "60min": 0.2,
    "8hr": 0.2
   },
   "2": {
    "10min": 1.5,
    "60min": 0.55,
    "8hr": 0.32
   },
   "3": {
    "10min": 7.7,
    "60min": 4.3,
    "8hr": 2.7
   }
  },
  "fluorine": {
   "1": {
    "10min": 0.2,
    "60min": 0.2,
    "8hr": 0.2
   },
   "2": {
    "10min": 4.0,
    "60min": 1.6,
    "8hr": 1.0
   },
   "3": {
    "10min": 9.0,
    "60min": 3.5,
    "8hr": 2.3
   }
  },
  "acrolein": {
   "1": {
    "10min": 0.033,
    "60min": 0.033,
    "8hr": 0.033
   },
   "2": {
    "10min": 0.44,
    "60min": 0.44,
    "8hr": 0.44
   },
   "3": {
    "10min": 2.5,
    "60min": 2.5,
    "8hr": 2.5
   }
  },
  "formaldehyde": {
   "1": {
    "10min": 1.0,
    "60min": 0.6,
    "8hr": 0.08
   },
   "2": {
    "10min": 14,
    "60min": 9.4,
    "8hr": 3.0
   },
   "3": {
    "10min": 17,
    "60min": 12,
    "8hr": 4.8
   }
  },
  "cyanogen_chloride": {
   "1": {
    "10min": 0.4,
    "60min": 0.4,
    "8hr": 0.4
   },
   "2": {
    "10min": 2.5,
    "60min": 2.0,
    "8hr": 1.7
   },
   "3": {
    "10min": 12,
    "60min": 8.5,
    "8hr": 7.0
   }
  },
  "chloropicrin": {
   "1": {
    "10min": 0.05,
    "60min": 0.05,
    "8hr": 0.05
   },
   "2": {
    "10min": 0.3,
    "60min": 0.23,
    "8hr": 0.18
   },
   "3": {
    "10min": 1.5,
    "60min": 1.0,
    "8hr": 0.73
   }
  },
  "methyl_isocyanate": {
   "1": {
    "10min": 0.004,
    "60min": 0.004,
    "8hr": 0.004
   },
   "2": {
    "10min": 0.04,
    "60min": 0.019,
    "8hr": 0.011
   },
   "3": {
    "10min": 0.4,
    "60min": 0.19,
    "8hr": 0.1
   }
  },
  "methyl_bromide": {
   "1": {
    "10min": 0.87,
    "60min": 0.87,
    "8hr": 0.87
   },
   "2": {
    "10min": 28,
    "60min": 28,
    "8hr": 21
   },
   "3": {
    "10min": 190,
    "60min": 99,
    "8hr": 66
   }
  },
  "acrylonitrile": {
   "1": {
    "10min": 2.1,
    "60min": 1.7,
    "8hr": 1.3
   },
   "2": {
    "10min": 35,
    "60min": 35,
    "8hr": 35
   },
   "3": {
    "10min": 85,
    "60min": 85,
    "8hr": 85
   }
  },
  "ethylene_oxide": {
   "1": {
    "10min": 11,
    "60min": 7.2,
    "8hr": 3.6
   },
   "2": {
    "10min": 56,
    "60min": 28,
    "8hr": 14
   },
   "3": {
    "10min": 480,
    "60min": 240,
    "8hr": 120
   }
  },
  "nitrogen_tetroxide": {
   "1": {
    "10min": 0.5,
    "60min": 0.5,
    "8hr": 0.5
   },
   "2": {
    "10min": 11,
    "60min": 11,
    "8hr": 11
   },
   "3": {
    "10min": 100,
    "60min": 50,
    "8hr": 25
   }
  },
  "sarin": {
   "1": {
    "10min": 1.6e-06,
    "60min": 1.6e-06,
    "8hr": 1.6e-06
   },
   "2": {
    "10min": 6.6e-06,
    "60min": 3.3e-06,
    "8hr": 2.2e-06
   },
   "3": {
    "10min": 6.4e-05,
    "60min": 3.2e-05,
    "8hr": 2.1e-05
   }
  },
  "soman": {
   "1": {
    "10min": 5.6e-07,
    "60min": 5.6e-07,
    "8hr": 5.6e-07
   },
   "2": {
    "10min": 2.4e-06,
    "60min": 1.2e-06,
    "8hr": 8.1e-07
   },
   "3": {
    "10min": 2.2e-05,
    "60min": 1.1e-05,
    "8hr": 7.5e-06
   }
  },
  "tabun": {
   "1": {
    "10min": 9.4e-07,
    "60min": 9.4e-07,
    "8hr": 9.4e-07
   },
   "2": {
    "10min": 6.4e-06,
    "60min": 3.2e-06,
    "8hr": 2.1e-06
   },
   "3": {
    "10min": 5.9e-05,
    "60min": 3e-05,
    "8hr": 2e-05
   }
  },
  "vx": {
   "1": {
    "10min": 3e-07,
    "60min": 3e-07,
    "8hr": 3e-07
   },
   "2": {
    "10min": 3.8e-06,
    "60min": 1.9e-06,
    "8hr": 1.3e-06
   },
   "3": {
    "10min": 2.7e-05,
    "60min": 1.4e-05,
    "8hr": 9.2e-06
   }
  }
 },
 "ERG_TABLE1": {
  "GEN-GAS": {
   "name": "Generic Gas / Unknown Toxic Vapor (Guide 111)",
   "guide": 111,
   "hl": true,
   "small": {
    "isolation_m": 100,
    "day_pad_km": 0.5,
    "night_pad_km": 1.6
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 1.8,
    "night_pad_km": 5.0
   }
  },
  "1005": {
   "name": "Ammonia, anhydrous",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.8,
    "night_pad_km": 2.7
   }
  },
  "1008": {
   "name": "Boron trifluoride",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.2,
    "night_pad_km": 4.6
   }
  },
  "1016": {
   "name": "Carbon monoxide",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.1
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 0.9
   }
  },
  "1017": {
   "name": "Chlorine",
   "guide": 124,
   "hl": false,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.1
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 2.1,
    "night_pad_km": 6.7
   }
  },
  "1023": {
   "name": "Coal gas",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.7
   }
  },
  "1026": {
   "name": "Cyanogen",
   "guide": 119,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.9
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 2.1,
    "night_pad_km": 7.1
   }
  },
  "1040": {
   "name": "Ethylene oxide",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.5
   }
  },
  "1045": {
   "name": "Fluorine",
   "guide": 124,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.4
   },
   "large": {
    "isolation_m": 500,
    "day_pad_km": 3.4,
    "night_pad_km": 11.0
   }
  },
  "1048": {
   "name": "Hydrogen bromide, anhydrous",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.4
   }
  },
  "1050": {
   "name": "Hydrogen chloride, anhydrous",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.5,
    "night_pad_km": 1.8
   }
  },
  "1051": {
   "name": "Hydrogen cyanide, stabilized (HCN)",
   "guide": 117,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.1
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 1.3,
    "night_pad_km": 3.5
   }
  },
  "1052": {
   "name": "Hydrogen fluoride, anhydrous",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.3,
    "night_pad_km": 1.1
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.4,
    "night_pad_km": 4.7
   }
  },
  "1053": {
   "name": "Hydrogen sulfide",
   "guide": 117,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.6
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.4
   }
  },
  "1062": {
   "name": "Methyl bromide",
   "guide": 123,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 0.9,
    "night_pad_km": 3.8
   }
  },
  "1064": {
   "name": "Methyl mercaptan",
   "guide": 117,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.6
   }
  },
  "1067": {
   "name": "Dinitrogen tetroxide",
   "guide": 124,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.2
   }
  },
  "1069": {
   "name": "Nitrosyl chloride",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 3.4,
    "night_pad_km": 10.5
   }
  },
  "1076": {
   "name": "Phosgene (CG)",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.0,
    "night_pad_km": 10.9
   }
  },
  "1079": {
   "name": "Sulfur dioxide",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.5,
    "night_pad_km": 1.9
   }
  },
  "1082": {
   "name": "Trifluorochloroethylene",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.5,
    "night_pad_km": 1.6
   }
  },
  "1092": {
   "name": "Acrolein, inhibited",
   "guide": 131,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.2
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 1.5,
    "night_pad_km": 4.7
   }
  },
  "1098": {
   "name": "Allyl alcohol",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.3
   }
  },
  "1135": {
   "name": "Ethylene chlorohydrin",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.2
   }
  },
  "1143": {
   "name": "Crotonaldehyde",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.4
   }
  },
  "1163": {
   "name": "Dimethylhydrazine, unsymmetrical",
   "guide": 131,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.8
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 1.6,
    "night_pad_km": 5.4
   }
  },
  "1185": {
   "name": "Ethyleneimine, inhibited",
   "guide": 131,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.6
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 0.9,
    "night_pad_km": 3.0
   }
  },
  "1238": {
   "name": "Methyl chloroformate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.5
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.1,
    "night_pad_km": 3.7
   }
  },
  "1239": {
   "name": "Methyl chloromethyl ether",
   "guide": 131,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.5
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.3
   }
  },
  "1244": {
   "name": "Methylhydrazine",
   "guide": 131,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.3
   }
  },
  "1251": {
   "name": "Methyl vinyl ketone, stabilized",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1259": {
   "name": "Nickel carbonyl",
   "guide": 131,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 1.9
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 4.9,
    "night_pad_km": 10.9
   }
  },
  "1380": {
   "name": "Pentaborane",
   "guide": 135,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.6
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 0.9,
    "night_pad_km": 3.1
   }
  },
  "1510": {
   "name": "Tetranitromethane",
   "guide": 141,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.0
   }
  },
  "1560": {
   "name": "Arsenic trichloride",
   "guide": 151,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.4
   }
  },
  "1580": {
   "name": "Chloropicrin",
   "guide": 154,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.4
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 2.5,
    "night_pad_km": 7.2
   }
  },
  "1589": {
   "name": "Cyanogen chloride (CK)",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 100,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.0,
    "night_pad_km": 10.9
   }
  },
  "1605": {
   "name": "Ethylene dibromide",
   "guide": 154,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1612": {
   "name": "Hexaethyl tetraphosphate",
   "guide": 123,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1660": {
   "name": "Nitric oxide",
   "guide": 124,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.2
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.2,
    "night_pad_km": 3.7
   }
  },
  "1670": {
   "name": "Perchloromethyl mercaptan",
   "guide": 157,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.3
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 2.6,
    "night_pad_km": 7.4
   }
  },
  "1695": {
   "name": "Chloroacetone, stabilized",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.4
   }
  },
  "1697": {
   "name": "Chloroacetophenone (CN / Mace)",
   "guide": 159,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.2
   }
  },
  "1698": {
   "name": "Adamsite (DM)",
   "guide": 154,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1699": {
   "name": "Diphenylchloroarsine (DA)",
   "guide": 154,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.2
   }
  },
  "1722": {
   "name": "Allyl chloroformate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.6
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.2
   }
  },
  "1741": {
   "name": "Boron trichloride",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.5
   }
  },
  "1744": {
   "name": "Bromine",
   "guide": 154,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.4
   }
  },
  "1745": {
   "name": "Bromine pentafluoride",
   "guide": 144,
   "hl": true,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.3,
    "night_pad_km": 1.2
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 2.3,
    "night_pad_km": 7.0
   }
  },
  "1749": {
   "name": "Chlorine trifluoride",
   "guide": 124,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.0
   },
   "large": {
    "isolation_m": 500,
    "day_pad_km": 4.0,
    "night_pad_km": 10.0
   }
  },
  "1752": {
   "name": "Chloroacetyl chloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.8
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.2,
    "night_pad_km": 4.0
   }
  },
  "1754": {
   "name": "Chlorosulfuric acid",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1809": {
   "name": "Phosphorus trichloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.5
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.1,
    "night_pad_km": 3.7
   }
  },
  "1810": {
   "name": "Phosphoryl chloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.4
   }
  },
  "1817": {
   "name": "Pyrosulfuryl chloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.3
   }
  },
  "1818": {
   "name": "Silicon tetrachloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1828": {
   "name": "Sulfur chlorides",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.1
   }
  },
  "1829": {
   "name": "Sulfur trioxide",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "1831": {
   "name": "Sulfuric acid, fuming",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.4
   }
  },
  "1834": {
   "name": "Sulfuryl chloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.5,
    "night_pad_km": 1.7
   }
  },
  "1836": {
   "name": "Thionyl chloride",
   "guide": 137,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.0
   }
  },
  "1859": {
   "name": "Silicon tetrafluoride",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.1,
    "night_pad_km": 3.7
   }
  },
  "1892": {
   "name": "Ethyldichloroarsine (ED)",
   "guide": 151,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.3
   }
  },
  "2032": {
   "name": "Nitric acid, fuming",
   "guide": 157,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.2
   }
  },
  "2186": {
   "name": "Hydrogen chloride, refrigerated liquid",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.2,
    "night_pad_km": 0.6
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 1.4,
    "night_pad_km": 4.8
   }
  },
  "2188": {
   "name": "Arsine",
   "guide": 119,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 1.9
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.5,
    "night_pad_km": 11.0
   }
  },
  "2189": {
   "name": "Dichlorosilane",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 0.9,
    "night_pad_km": 3.6
   }
  },
  "2190": {
   "name": "Oxygen difluoride",
   "guide": 124,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.3,
    "night_pad_km": 11.0
   }
  },
  "2191": {
   "name": "Sulfuryl fluoride",
   "guide": 123,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.2
   }
  },
  "2194": {
   "name": "Selenium hexafluoride",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.3,
    "night_pad_km": 11.0
   }
  },
  "2196": {
   "name": "Tungsten hexafluoride",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.3,
    "night_pad_km": 1.1
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 3.3,
    "night_pad_km": 9.2
   }
  },
  "2197": {
   "name": "Hydrogen iodide, anhydrous",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.4
   }
  },
  "2198": {
   "name": "Phosphorus pentafluoride",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.4,
    "night_pad_km": 1.7
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 3.3,
    "night_pad_km": 9.6
   }
  },
  "2199": {
   "name": "Phosphine",
   "guide": 119,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 1.6,
    "night_pad_km": 5.1
   }
  },
  "2202": {
   "name": "Hydrogen selenide, anhydrous",
   "guide": 117,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.5,
    "night_pad_km": 11.0
   }
  },
  "2204": {
   "name": "Carbonyl sulfide",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 0.9,
    "night_pad_km": 3.3
   }
  },
  "2232": {
   "name": "Chloroacetaldehyde",
   "guide": 153,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.0
   }
  },
  "2334": {
   "name": "Allylamine",
   "guide": 132,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.0,
    "night_pad_km": 3.2
   }
  },
  "2417": {
   "name": "Carbonyl fluoride",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.4,
    "night_pad_km": 1.5
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 2.9,
    "night_pad_km": 8.4
   }
  },
  "2418": {
   "name": "Sulfur tetrafluoride",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 500,
    "day_pad_km": 4.5,
    "night_pad_km": 11.0
   }
  },
  "2420": {
   "name": "Hexafluoroacetone",
   "guide": 125,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.8
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.2,
    "night_pad_km": 3.9
   }
  },
  "2421": {
   "name": "Nitrogen trioxide",
   "guide": 124,
   "hl": false,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.2
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 2.5,
    "night_pad_km": 7.8
   }
  },
  "2474": {
   "name": "Thiophosgene",
   "guide": 157,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.4,
    "night_pad_km": 1.5
   },
   "large": {
    "isolation_m": 400,
    "day_pad_km": 2.8,
    "night_pad_km": 8.3
   }
  },
  "2477": {
   "name": "Methyl isothiocyanate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.4
   }
  },
  "2480": {
   "name": "Methyl isocyanate (MIC)",
   "guide": 155,
   "hl": true,
   "small": {
    "isolation_m": 100,
    "day_pad_km": 0.6,
    "night_pad_km": 3.2
   },
   "large": {
    "isolation_m": 800,
    "day_pad_km": 8.0,
    "night_pad_km": 11.0
   }
  },
  "2481": {
   "name": "Ethyl isocyanate",
   "guide": 155,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.4,
    "night_pad_km": 1.4
   },
   "large": {
    "isolation_m": 300,
    "day_pad_km": 2.2,
    "night_pad_km": 6.8
   }
  },
  "2482": {
   "name": "n-Propyl isocyanate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.1
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.4,
    "night_pad_km": 4.6
   }
  },
  "2483": {
   "name": "Isopropyl isocyanate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.3,
    "night_pad_km": 1.2
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.5,
    "night_pad_km": 4.8
   }
  },
  "2484": {
   "name": "tert-Butyl isocyanate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.8
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.2,
    "night_pad_km": 3.8
   }
  },
  "2485": {
   "name": "n-Butyl isocyanate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.7
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.1,
    "night_pad_km": 3.6
   }
  },
  "2487": {
   "name": "Phenyl isocyanate",
   "guide": 155,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.7,
    "night_pad_km": 2.2
   }
  },
  "2495": {
   "name": "Iodine pentafluoride",
   "guide": 144,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.2,
    "night_pad_km": 0.8
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 1.2,
    "night_pad_km": 3.9
   }
  },
  "2534": {
   "name": "Methylchlorosilane",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "2548": {
   "name": "Chlorine pentafluoride",
   "guide": 124,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.4,
    "night_pad_km": 11.0
   }
  },
  "2600": {
   "name": "Carbon monoxide and hydrogen mixture",
   "guide": 119,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.1
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 0.9
   }
  },
  "2644": {
   "name": "Methyl iodide",
   "guide": 151,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 1.9
   }
  },
  "2646": {
   "name": "Hexachlorocyclopentadiene",
   "guide": 151,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.3,
    "night_pad_km": 1.0
   }
  },
  "2668": {
   "name": "Chloroacetonitrile",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.2
   }
  },
  "2676": {
   "name": "Stibine",
   "guide": 119,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 600,
    "day_pad_km": 5.0,
    "night_pad_km": 11.0
   }
  },
  "3057": {
   "name": "Trifluoroacetyl chloride",
   "guide": 125,
   "hl": true,
   "small": {
    "isolation_m": 60,
    "day_pad_km": 0.5,
    "night_pad_km": 2.1
   },
   "large": {
    "isolation_m": 500,
    "day_pad_km": 4.0,
    "night_pad_km": 10.9
   }
  },
  "3079": {
   "name": "Methacrylonitrile, inhibited",
   "guide": 131,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.4
   },
   "large": {
    "isolation_m": 200,
    "day_pad_km": 0.9,
    "night_pad_km": 3.1
   }
  },
  "3083": {
   "name": "Perchloryl fluoride",
   "guide": 124,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.3
   },
   "large": {
    "isolation_m": 150,
    "day_pad_km": 0.6,
    "night_pad_km": 2.1
   }
  },
  "3246": {
   "name": "Methanesulfonyl chloride",
   "guide": 156,
   "hl": false,
   "small": {
    "isolation_m": 30,
    "day_pad_km": 0.1,
    "night_pad_km": 0.2
   },
   "large": {
    "isolation_m": 100,
    "day_pad_km": 0.4,
    "night_pad_km": 1.3
   }
  }
 }
};
});
