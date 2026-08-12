/*
 * Impact assessment — what falls inside the hazard zones.
 * Faithful port of backend/impact.py; cross-validated in test_model_port.py.
 *
 * Pure geometry (ray-casting point-in-polygon, shoelace area, haversine), no
 * data-source knowledge — the offline app feeds it points from the local
 * facility store the same way the server feeds it the facility library.
 */
(function (root, factory) {
  const mod = factory();
  if (typeof module === 'object' && module.exports) module.exports = mod;
  else { root.WMDModels = root.WMDModels || {}; root.WMDModels.impact = mod; }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const EARTH_RADIUS_M = 6371000.0;

  function haversine_m(lat1, lon1, lat2, lon2) {
    const p1 = Math.PI / 180 * lat1, p2 = Math.PI / 180 * lat2;
    const dp = Math.PI / 180 * (lat2 - lat1), dl = Math.PI / 180 * (lon2 - lon1);
    const a = Math.pow(Math.sin(dp / 2), 2) + Math.cos(p1) * Math.cos(p2) * Math.pow(Math.sin(dl / 2), 2);
    return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a));
  }

  function point_in_ring(lat, lon, ring) {
    let inside = false;
    const n = ring.length;
    if (n < 3) return false;
    let j = n - 1;
    for (let i = 0; i < n; i++) {
      const yi = ring[i][0], xi = ring[i][1];
      const yj = ring[j][0], xj = ring[j][1];
      if ((yi > lat) !== (yj > lat)) {
        const x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi;
        if (lon < x_cross) inside = !inside;
      }
      j = i;
    }
    return inside;
  }

  function ring_area_deg2(ring) {
    const n = ring.length;
    if (n < 3) return 0.0;
    let area = 0.0, j = n - 1;
    for (let i = 0; i < n; i++) {
      const yi = ring[i][0], xi = ring[i][1];
      const yj = ring[j][0], xj = ring[j][1];
      area += (xj + xi) * (yj - yi);
      j = i;
    }
    return Math.abs(area) / 2.0;
  }

  function extract_zones(overlays) {
    const zones = [];
    for (const tool in (overlays || {})) {
      const state = overlays[tool];
      if (!state || typeof state !== 'object') continue;
      const contours = state.contours;
      if (!contours || typeof contours !== 'object') continue;
      const src_lat = state.source_lat, src_lon = state.source_lon;
      for (const level in contours) {
        const info = contours[level];
        if (!info || typeof info !== 'object') continue;
        const ring = info.latlon || [];
        if (ring.length < 3) continue;
        zones.push({ tool, level, label: info.label || level, color: info.color || '#888888',
          ring, area: ring_area_deg2(ring),
          source_lat: src_lat == null ? null : src_lat,
          source_lon: src_lon == null ? null : src_lon });
      }
    }
    zones.sort((a, b) => a.area - b.area);   // smallest (most severe) first
    return zones;
  }

  function assess(zones, points) {
    const buckets = zones.map(() => []);
    const total_by_category = {};
    let hit = 0;

    for (const pt of points) {
      const lat = pt.lat, lon = pt.lon;
      if (lat == null || lon == null) continue;
      for (let zi = 0; zi < zones.length; zi++) {
        const z = zones[zi];
        if (point_in_ring(lat, lon, z.ring)) {
          const enriched = Object.assign({}, pt);
          if (z.source_lat != null && z.source_lon != null) {
            enriched.distance_m = Math.round(haversine_m(z.source_lat, z.source_lon, lat, lon) * 10) / 10;
          }
          buckets[zi].push(enriched);
          const cat = pt.category || pt.kind || 'other';
          total_by_category[cat] = (total_by_category[cat] || 0) + 1;
          hit += 1;
          break;
        }
      }
    }

    const out_zones = [];
    for (let zi = 0; zi < zones.length; zi++) {
      const z = zones[zi], pts = buckets[zi];
      if (!pts.length) continue;
      const by_cat = {};
      for (const p of pts) { const cat = p.category || p.kind || 'other'; by_cat[cat] = (by_cat[cat] || 0) + 1; }
      pts.sort((a, b) => (a.distance_m || 0) - (b.distance_m || 0));
      out_zones.push({ tool: z.tool, level: z.level, label: z.label, color: z.color,
        count: pts.length, by_category: by_cat, points: pts });
    }

    return { zones: out_zones, total: hit, by_category: total_by_category, unaffected: points.length - hit };
  }

  return { haversine_m, point_in_ring, ring_area_deg2, extract_zones, assess };
});
