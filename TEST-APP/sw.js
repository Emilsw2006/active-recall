const CACHE_NAME = 'active-recall-v24';
const JS_CSS = /\.(js|css)(\?.*)?$/;

// One-shot flag: serve reset page on first navigation after activation
let justActivated = false;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => {
  justActivated = true;
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Reset page: unregisters ALL service workers and reloads fresh
const RESET_HTML = `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:#1a2540;font-family:sans-serif;color:rgba(255,255,255,0.6);font-size:14px;}</style>
</head><body>Actualizando...</body>
<script>
navigator.serviceWorker.getRegistrations()
  .then(function(regs){ return Promise.all(regs.map(function(r){ return r.unregister(); })); })
  .then(function(){ location.replace('/app'); });
</script></html>`;

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.protocol === 'ws:' || url.protocol === 'wss:') return;

  // On first navigation after activation: serve reset page
  if (justActivated && e.request.mode === 'navigate') {
    justActivated = false;
    e.respondWith(new Response(RESET_HTML, {
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    }));
    return;
  }

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

  // Images, fonts: cache-first
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
