const CACHE_NAME = 'active-recall-v3';

// Install — skip precaching to avoid path issues, cache on demand
self.addEventListener('install', () => self.skipWaiting());

// Activate — clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch — network first, fallback to cache
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Skip non-GET, WebSocket, and API requests
  if (e.request.method !== 'GET') return;
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;

  // Only cache static assets (css, js, images, fonts)
  const isStatic = /\.(css|js|png|svg|ico|woff2?|ttf|json)$/.test(url.pathname)
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
