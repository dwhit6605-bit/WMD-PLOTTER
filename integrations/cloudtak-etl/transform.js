/*
 * WMD PLOTTER hazard GeoJSON  →  CloudTAK / TAK CoT-styled features.
 *
 * The pure, deterministic core of the ETL. Kept separate from task.ts (which
 * wires into @tak-ps/etl and needs the CloudTAK/AWS runtime) so this can be
 * unit-tested with plain node — see transform.test.js.
 *
 * Input:  a WMD PLOTTER model FeatureCollection (exactly what /api/plume,
 *         /api/blast, /api/radiation, … return) plus incident metadata.
 * Output: a FeatureCollection whose features carry the properties CloudTAK's
 *         `submit()` expects — callsign, remarks, time/start/stale, and the
 *         stroke/fill styling ATAK renders. `submit()` turns these into CoT and
 *         the Layer fans them out to the connected TAK users.
 */

'use strict';

// Zone hazard color → a solid ARGB-ish hex ATAK understands, plus opacities.
// WMD already emits a per-zone `color`; we pass it through and set sensible
// opacities so inner (more severe) zones read stronger.
function zoneStyle(color, level) {
  const strong = level === 'high' || level === 'severe' || level === 'fireball'
    || level === 'extreme' || level === 'erpg3' || level === 'lethal';
  return {
    stroke: color || '#FF3B3B',
    'stroke-width': 2,
    'stroke-opacity': 1,
    fill: color || '#FF3B3B',
    'fill-opacity': strong ? 0.45 : 0.25,
  };
}

/*
 * Build the ATAK remarks string, matching the house style already used by the
 * direct-CoT path (backend/tak_dp.py): a single pipe-delimited line so it reads
 * cleanly in the ATAK radial/detail view.
 */
function buildRemarks(meta, feat) {
  const p = feat.properties || {};
  const bits = ['WMD PLOTTER'];
  if (meta.kind) bits.push(meta.kind.toUpperCase());
  if (meta.agent) bits.push(`AGENT: ${meta.agent}`);
  if (meta.rate_kg_min != null) bits.push(`RATE: ${Number(meta.rate_kg_min).toFixed(2)} kg/min`);
  if (meta.wind_label) bits.push(`WIND: ${meta.wind_label}`);
  if (meta.stability) bits.push(`PG-${meta.stability}`);
  if (p.threshold_ppm != null) bits.push(`${p.label || p.level}: ${p.threshold_ppm} ppm`);
  if (p.max_downwind_km != null) bits.push(`${p.max_downwind_km} km downwind`);
  else if (p.max_downwind_m != null) bits.push(`${(p.max_downwind_m / 1000).toFixed(2)} km downwind`);
  if (meta.time) bits.push(`TIME: ${meta.time}`);
  return bits.join(' | ');
}

// Which WMD feature types are hazard polygons worth broadcasting (vs. the
// source-point marker or non-geometry features).
const HAZARD_TYPES = new Set([
  'plume_contour', 'blast_zone', 'bleve_zone', 'plume_contour_rad',
  'dense_gas_contour', 'smoke_pm25', 'smoke_co', 'radiation_zone',
]);

/**
 * @param {object} wmd    A WMD PLOTTER model FeatureCollection.
 * @param {object} meta   { name, kind, agent, rate_kg_min, wind_label,
 *                          stability, time, stale_minutes, source_uid }
 * @returns {object}      A FeatureCollection ready for ETL submit().
 */
function wmdToCot(wmd, meta = {}) {
  if (!wmd || wmd.type !== 'FeatureCollection' || !Array.isArray(wmd.features)) {
    throw new Error('wmdToCot: expected a GeoJSON FeatureCollection');
  }
  const now = meta.time || meta.now || new Date().toISOString();
  const staleMin = meta.stale_minutes != null ? meta.stale_minutes : 60;
  const base = (meta.source_uid || meta.name || 'wmd-incident')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

  const out = [];
  let idx = 0;

  for (const f of wmd.features) {
    const p = f.properties || {};
    const isPolygon = f.geometry && (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon');
    if (!isPolygon) continue;
    if (p.type && !HAZARD_TYPES.has(p.type)) continue;
    if (!f.geometry.coordinates || !f.geometry.coordinates.length) continue;

    const label = p.label || p.level || 'Hazard Zone';
    const style = zoneStyle(p.color, p.level);

    out.push({
      type: 'Feature',
      geometry: f.geometry,
      properties: Object.assign({
        // Identity: stable per incident+zone so re-broadcast UPDATES the same
        // CoT rather than piling up duplicates in ATAK.
        id: `wmd-${base}-${p.level || idx}`,
        type: 'u-d-f',                 // ATAK "drawn free-form" shape
        how: 'h-g-i-g-o',
        callsign: `${meta.agent || meta.name || 'HAZARD'} · ${label}`,
        remarks: buildRemarks(meta, f),
        time: now,
        start: now,
        stale: staleIso(now, staleMin),
        archived: true,
      }, style),
    });
    idx++;
  }

  return { type: 'FeatureCollection', features: out };
}

function staleIso(startIso, minutes) {
  const t = new Date(startIso).getTime();
  return new Date(t + minutes * 60000).toISOString();
}

export { wmdToCot, buildRemarks, zoneStyle, HAZARD_TYPES };
