// Minimal PWA app-shell service worker.
//
// Scope, deliberately: cache the static app shell (HTML/JS/CSS/icons) only, so
// the app can be installed and reopens instantly. This intentionally does NOT
// cache anything else — no API responses, no Supabase auth traffic, no
// inventory/supplier/product/receipt data. Offline business workflows are out
// of scope for this pass; a stale-but-installable shell is all this provides.

// CACHE_VERSION is stamped in at build time (see scripts/stamp-sw-version.mjs,
// wired into `npm run build`) so every deploy gets a distinct cache name
// automatically — no one has to remember to bump a version number by hand.
// In dev (where the placeholder is never replaced) it falls back to "dev".
const CACHE_VERSION = "__CACHE_VERSION__".startsWith("__") ? "dev" : "__CACHE_VERSION__";
const CACHE_NAME = `patti-back-office-shell-${CACHE_VERSION}`;

const STATIC_EXTENSIONS = [".js", ".css", ".svg", ".png", ".ico", ".webmanifest", ".woff", ".woff2"];

function isStaticAsset(pathname) {
  return STATIC_EXTENSIONS.some((ext) => pathname.endsWith(ext));
}

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only ever handle GET; never intercept auth/API mutations or anything else.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never touch cross-origin requests (Supabase Auth, the API server on a
  // different origin/port, etc.) — let the browser handle those normally.
  if (url.origin !== self.location.origin) return;

  // Never cache API traffic even if it's ever proxied under the same origin.
  if (url.pathname.startsWith("/api/")) return;

  const isNavigation = request.mode === "navigate";
  if (!isNavigation && !isStaticAsset(url.pathname)) return;

  if (isNavigation) {
    // Network-first for the app shell HTML, so users get fresh content when
    // online; fall back to the cached shell only if the network is down.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
    return;
  }

  // Cache-first for hashed static assets — a content change produces a new
  // filename, so aggressively caching the old one is safe.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
    )
  );
});
