const CACHE_NAME = 'active-recall-v49';
const JS_CSS = /\.(js|css)(\?.*)?$/;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => {
  // Delete all old caches so stale assets are gone
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
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

  // HTML navigations: always network
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }

  // Images, fonts, manifest: cache-first
  const isStatic = /\.(png|svg|ico|woff2?|ttf|webmanifest)$/.test(url.pathname);
  if (!isStatic) return;

  e.respondWith(
    caches.match(e.request).then(cached => cached ||
      fetch(e.request).then(res => {
        if (res && res.status === 200) {
          caches.open(CACHE_NAME).then(c => c.put(e.request, res.clone()));
        }
        return res;
      })
    )
  );
});








