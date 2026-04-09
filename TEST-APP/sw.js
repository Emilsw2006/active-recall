const CACHE_NAME = 'active-recall-v20';
const JS_CSS = /\.(js|css)(\?.*)?$/;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window', includeUncontrolled: true }))
      .then(clients => Promise.all(
        clients.map(client => {
          // Force a fresh navigation — this breaks the stale-JS cycle
          try { return client.navigate(client.url); } catch(e) { return Promise.resolve(); }
        })
      ))
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;

  // JS and CSS: ALWAYS network, never cache
  if (JS_CSS.test(url.pathname)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // HTML navigation: always network
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }

  // Images, fonts: cache-first
  const isStatic = /\.(png|svg|ico|woff2?|ttf|webmanifest)$/.test(url.pathname);
  if (!isStatic) return;

  e.respondWith(
    caches.match(e.request).then(cached => cached ||
      fetch(e.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return response;
      })
    )
  );
});
