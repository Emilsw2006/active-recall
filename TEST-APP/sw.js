const CACHE_NAME = 'active-recall-v19';
const JS_CSS = /\.(js|css)(\?.*)?$/;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window' }))
      .then(clients => clients.forEach(c => c.postMessage({ type: 'sw-updated' })))
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;

  // JS and CSS: ALWAYS fetch from network, never cache
  if (JS_CSS.test(url.pathname)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Images, fonts, icons: cache-first
  const isStatic = /\.(png|svg|ico|woff2?|ttf|webmanifest)$/.test(url.pathname)
    || url.pathname.endsWith('/app') || url.pathname === '/';
  if (!isStatic) return;

  e.respondWith(
    fetch(e.request).then(response => {
      if (response && response.status === 200) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
      }
      return response;
    }).catch(() => caches.match(e.request))
  );
});
