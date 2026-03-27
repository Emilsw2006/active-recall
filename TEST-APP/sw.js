const CACHE_NAME = 'active-recall-v1';
const PRECACHE = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/i18n.js',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];

// Install — precache shell
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// Activate — clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch — network first for API, cache first for assets
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Skip non-GET, WebSocket, and API requests
  if (e.request.method !== 'GET') return;
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;
  if (url.origin !== location.origin) return;

  e.respondWith(
    caches.match(e.request).then(cached => {
      const fetchPromise = fetch(e.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return response;
      }).catch(() => cached);

      return cached || fetchPromise;
    })
  );
});
