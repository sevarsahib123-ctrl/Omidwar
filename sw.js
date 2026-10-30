const CACHE = "omidwar-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/static/icon-192.png", "/static/icon-512.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  // Never cache API responses or private student/grade data.
  if (url.pathname.startsWith("/api/")) return;
  event.respondWith(
    fetch(req).then(response => {
      if (response.ok && (url.pathname === "/" || url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest")) {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put(req, copy));
      }
      return response;
    }).catch(() => caches.match(req).then(hit => hit || caches.match("/")))
  );
});
