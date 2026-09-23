const CACHE_VERSION = "v1";
const CACHE = "aurora-engine-cache-" + CACHE_VERSION;

const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", function (event) {
  console.log("[SW] Installing " + CACHE);
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(ASSETS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  console.log("[SW] Activating " + CACHE);
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(
          keys.filter(function (k) { return k !== CACHE; })
              .map(function (k) { return caches.delete(k); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Network-first per JSON e PNG
  if (url.pathname.endsWith(".json") || url.pathname.endsWith(".png")) {
    event.respondWith(
      fetch(request)
        .then(function (res) {
          var clone = res.clone();
          event.waitUntil(
            caches.open(CACHE).then(function (c) { c.put(request, clone); })
          );
          return res;
        })
        .catch(function () {
          return caches.match(request).then(function (cached) {
            return cached || new Response("", { status: 503, statusText: "Offline" });
          });
        })
    );
    return;
  }

  // Cache-first per il resto
  event.respondWith(
    caches.match(request).then(function (cached) {
      return cached || fetch(request);
    })
  );
});
