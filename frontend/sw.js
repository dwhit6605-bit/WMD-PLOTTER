/**
 * WMD Plotter — Service Worker
 *
 * Strategy:
 *   App shell (HTML, CDN CSS/JS): cache-first with background revalidation
 *   API calls (/api/*, /kml/*, /export/*, /api/*): network-first, no caching
 *   Static assets (/static/*): cache-first
 *
 * Bump CACHE_VERSION on every deploy to invalidate stale shells.
 */

const CACHE_VERSION = "wmd-v2";
const CACHE_NAME    = `wmd-plotter-${CACHE_VERSION}`;

// Resources that form the "app shell" — cached on install
// NOTE: "/" is intentionally excluded — it's auth-protected and must always hit the network
const APP_SHELL = [
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
  "https://cdn.jsdelivr.net/npm/@geoman-io/leaflet-geoman-free@2.14.2/dist/leaflet-geoman.min.css",
  "https://cdn.jsdelivr.net/npm/@geoman-io/leaflet-geoman-free@2.14.2/dist/leaflet-geoman.min.js",
];

// These prefixes always go to the network — never serve stale model or auth data
const NETWORK_ONLY_PREFIXES = [
  "/api/",
  "/kml/",
  "/export/",
  "/auth/",
];

// Exact paths that must always hit the network (auth-protected HTML pages)
const NETWORK_ONLY_EXACT = new Set(["/", "/login", "/register", "/admin/users"]);

// ── Install: pre-cache the app shell ─────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL).catch((err) => {
        // CDN failures during install should not block SW activation
        console.warn("[SW] App shell pre-cache partial failure:", err);
      });
    })
  );
  self.skipWaiting();
});

// ── Activate: evict old cache versions ───────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("wmd-plotter-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: route by resource type ────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Always network for API / model endpoints and auth-protected pages
  const isNetworkOnly =
    NETWORK_ONLY_EXACT.has(url.pathname) ||
    NETWORK_ONLY_PREFIXES.some((p) => url.pathname.startsWith(p));
  if (isNetworkOnly) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Non-GET (POST model runs, etc.) — always network
  if (event.request.method !== "GET") {
    event.respondWith(fetch(event.request));
    return;
  }

  // App shell + static assets: cache-first, network fallback
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response && response.status === 200 && response.type !== "opaque") {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, response.clone()));
          }
          return response;
        })
        .catch(() => cached); // offline: fall through to cached copy

      // Return cache immediately; refresh in background
      return cached || networkFetch;
    })
  );
});
