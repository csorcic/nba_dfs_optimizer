// Service worker: makes the app installable and usable offline.
// App files: served from cache (updated when a new version is deployed).
// Slate data: network first, falling back to the last slate seen.
const VERSION = "b91ae172e0";
const CACHE = `dfs-${VERSION}`;
const SHELL = ["./","index.html","app/app.js","app/state.js","app/worker.js","app/styles.css","app/optimizer/rules.js","app/optimizer/model.js","app/optimizer/solvers.js","app/optimizer/optimizer.js","app/optimizer/csv.js","vendor/highs.mjs","vendor/highs.wasm","vendor/lp-solver.mjs","manifest.webmanifest","icons/icon-192.png","icons/icon-512.png","icons/maskable-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("dfs-") && k !== CACHE && k !== "dfs-data").map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.includes("/data/")) {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          if (r.ok) caches.open("dfs-data").then((c) => c.put(url.pathname, r.clone()));
          return r;
        })
        .catch(() => caches.open("dfs-data").then((c) => c.match(url.pathname)).then((r) => r || Response.error())),
    );
    return;
  }
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((r) => r || fetch(e.request)));
});
