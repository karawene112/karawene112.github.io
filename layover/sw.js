/* Keeps the app working offline. Bump the version when you upload a new build. */
const CACHE = "layover-v3.2";
const SHELL = ["./", "./index.html", "./config.js", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", e => {
  const r = e.request; if (r.method !== "GET") return;
  const u = new URL(r.url);
  const own = u.origin === location.origin;
  const lib = /(^|\.)fonts\.(googleapis|gstatic)\.com$|^cdnjs\.cloudflare\.com$|\.tile\.openstreetmap\.org$|^tile\.openstreetmap\.org$/.test(u.hostname);
  if (!own && !lib) return; // live data always comes fresh from the network
  if (own) { // newest version when online, saved copy when offline
    e.respondWith(fetch(r).then(res => { const c = res.clone(); caches.open(CACHE).then(x => x.put(r, c)); return res; })
      .catch(() => caches.match(r).then(m => m || caches.match("./index.html"))));
    return;
  }
  e.respondWith(caches.match(r).then(m => m || fetch(r).then(res => { const c = res.clone(); caches.open(CACHE).then(x => x.put(r, c)); return res; })));
});
