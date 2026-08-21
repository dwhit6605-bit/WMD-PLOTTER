/*
 * Tests for the WMD → CoT transform. Plain node, no CloudTAK/AWS needed:
 *   node integrations/cloudtak-etl/transform.test.js
 * This is the part of the ETL that can be verified off-cloud; the submit/
 * webhook wiring in task.ts needs a real CloudTAK instance to exercise.
 */
import { wmdToCot, buildRemarks } from './transform.js';

const results = [];
const check = (name, cond, detail) => {
  results.push([name, !!cond]);
  console.log((cond ? 'PASS  ' : 'FAIL  ') + name + (detail && !cond ? `   [${detail}]` : ''));
};

// A realistic WMD /api/plume FeatureCollection: three plume_contour polygons
// plus the source-point marker (which must be dropped).
const wmd = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.25, 34.05] },
      properties: { type: 'source', chemical: 'Chlorine' } },
    { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[-118.25,34.05],[-118.24,34.05],[-118.24,34.06],[-118.25,34.05]]] },
      properties: { type: 'plume_contour', level: 'high', label: 'AEGL-3 (60min)', color: '#FF0000', threshold_ppm: 20, max_downwind_km: 0.68 } },
    { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[-118.25,34.05],[-118.22,34.05],[-118.22,34.06],[-118.25,34.05]]] },
      properties: { type: 'plume_contour', level: 'medium', label: 'AEGL-2 (60min)', color: '#FF8C00', threshold_ppm: 2, max_downwind_km: 2.86 } },
    { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[-118.25,34.05],[-118.17,34.05],[-118.17,34.06],[-118.25,34.05]]] },
      properties: { type: 'plume_contour', level: 'low', label: 'AEGL-1 (60min)', color: '#FFFF00', threshold_ppm: 1, max_downwind_km: 7.69 } },
  ],
};

const meta = {
  name: 'Downtown Chlorine Leak', kind: 'chem incident', agent: 'Chlorine',
  rate_kg_min: 50, wind_label: 'W 6.7 mph', stability: 'D',
  now: '2026-08-12T17:00:00.000Z', stale_minutes: 60, source_uid: 'incident-A',
};

const fc = wmdToCot(wmd, meta);

check('returns a FeatureCollection', fc.type === 'FeatureCollection');
check('drops the source point, keeps 3 hazard polygons', fc.features.length === 3,
  `got ${fc.features.length}`);
check('all outputs are polygons', fc.features.every(f => f.geometry.type === 'Polygon'));

const f0 = fc.features[0];
check('stable id per incident+zone (idempotent re-broadcast)', f0.properties.id === 'wmd-incident-a-high',
  f0.properties.id);
check('CoT type is a drawn shape (u-d-f)', f0.properties.type === 'u-d-f');
check('callsign names agent + zone', f0.properties.callsign === 'Chlorine · AEGL-3 (60min)',
  f0.properties.callsign);
check('remarks carry agent/rate/wind/stability', /AGENT: Chlorine/.test(f0.properties.remarks)
  && /RATE: 50\.00 kg\/min/.test(f0.properties.remarks) && /PG-D/.test(f0.properties.remarks),
  f0.properties.remarks);
check('geometry passed through unchanged', JSON.stringify(f0.geometry) === JSON.stringify(wmd.features[1].geometry));
check('zone color passed through as stroke+fill', f0.properties.stroke === '#FF0000' && f0.properties.fill === '#FF0000');
check('severe zone renders stronger fill', f0.properties['fill-opacity'] === 0.45,
  String(f0.properties['fill-opacity']));
check('low zone renders lighter fill', fc.features[2].properties['fill-opacity'] === 0.25,
  String(fc.features[2].properties['fill-opacity']));

check('time/start set from meta', f0.properties.start === '2026-08-12T17:00:00.000Z');
check('stale is start + 60 min', f0.properties.stale === '2026-08-12T18:00:00.000Z', f0.properties.stale);

// Re-running with the same meta must produce identical ids (idempotent).
const fc2 = wmdToCot(wmd, meta);
check('re-broadcast is idempotent (same ids)',
  fc.features.map(f => f.properties.id).join() === fc2.features.map(f => f.properties.id).join());

// A blast FeatureCollection (circles) should transform the same way.
const blast = { type: 'FeatureCollection', features: [
  { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[-118.25,34.05],[-118.24,34.05],[-118.24,34.06],[-118.25,34.05]]] },
    properties: { type: 'blast_zone', level: 'severe', label: 'Severe Structural Damage', color: '#CC0000', radius_km: 0.2 } },
  { type: 'Feature', geometry: { type: 'Point', coordinates: [-118.25, 34.05] }, properties: { type: 'blast_source' } },
]};
const bfc = wmdToCot(blast, { name: 'VBIED', kind: 'blast', agent: 'TNT 500kg', now: meta.now });
check('blast: 1 zone kept, source dropped', bfc.features.length === 1, `got ${bfc.features.length}`);
check('blast: severe zone strong fill', bfc.features[0].properties['fill-opacity'] === 0.45);

// Guard: non-FeatureCollection input throws.
let threw = false;
try { wmdToCot({ foo: 1 }); } catch (e) { threw = true; }
check('rejects non-FeatureCollection input', threw);

console.log('');
const failed = results.filter(r => !r[1]);
console.log(`${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
