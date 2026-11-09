// Service worker: makes the app installable and usable offline.
// App files: served from cache (updated when a new version is deployed).
// Slate data: network first, falling back to the last slate seen.
const VERSION = "__VERSION__";
const CACHE = `dfs-${VERSION}`;
const SHELL = __SHELL__;

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
          // Copy the response now (it can only be read once) and save it for offline use.
          if (r.ok) {
            const copy = r.clone();
            e.waitUntil(caches.open("dfs-data").then((c) => c.put(url.pathname, copy)));
          }
          return r;
        })
        .catch(() => caches.open("dfs-data").then((c) => c.match(url.pathname)).then((r) => r || Response.error())),
    );
    return;
  }
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((r) => r || fetch(e.request)));
});
