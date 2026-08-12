"""
Generate the offline model data bundle from the Python source of truth.

The on-device app needs the chemical / AEGL / ERG tables that the models
consume. Rather than hand-copy ~1,850 lines of Python dicts (and let them
drift), this serialises the live Python data structures to a JS module. Re-run
it whenever backend/chemicals.py, aegl_db.py, or erg.py change:

    python3 tests/gen_model_data.py

Writes frontend/js/models/data.js. test_model_port.py verifies the emitted data
round-trips back to the Python values, so a stale or corrupted bundle fails CI.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

import chemicals
import aegl_db
import erg

OUT = REPO / "frontend" / "js" / "models" / "data.js"

bundle = {
    "CHEMICALS": chemicals.CHEMICALS,   # list of 48 chemical dicts (mw, AEGL, ERG...)
    "AEGL": aegl_db.AEGL,               # dict: 29 chemicals -> AEGL-1/2/3 by duration
    "ERG_TABLE1": erg.ERG_TABLE1,       # dict: 103 UN/guide -> isolation/protective distances
}

# Stable key order and ASCII-safe (chemical names carry ₂/µ etc.; keep them as
# real UTF-8 in the file, which JS handles natively, so ensure_ascii=False).
payload = json.dumps(bundle, ensure_ascii=False, indent=1, sort_keys=False)

header = """/*
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
  return """

OUT.write_text(header + payload + ";\n});\n", encoding="utf-8")

counts = {k: len(v) for k, v in bundle.items()}
print(f"Wrote {OUT.relative_to(REPO)}  ({OUT.stat().st_size:,} bytes)")
print(f"  {counts}")
