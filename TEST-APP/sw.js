const CACHE_NAME = 'active-recall-v18';

// Install — activate immediately
self.addEventListener('install', () => self.skipWaiting());

// Activate — clear old caches, claim clients, tell them to reload
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window' }))
      .then(clients => clients.forEach(client => client.postMessage({ type: 'sw-updated' })))
  );
});

// Fetch — network first, fallback to cache
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  if (e.request.method !== 'GET') return;
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;
  // Skip API calls
  if (url.pathname.startsWith('/auth') || url.pathname.startsWith('/asignaturas') ||
      url.pathname.startsWith('/documentos') || url.pathname.startsWith('/atomos') ||
      url.pathname.startsWith('/sesiones') || url.pathname.startsWith('/flashcards')) return;

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
