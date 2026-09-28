const CACHE_NAME = 'tnm-tools-v1';
const ASSETS = ['/tools', '/manifest.json'];

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS).catch(() => {}))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
        ))
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const req = event.request;
    // Не кэшируем POST и /api/
    if (req.method !== 'GET') return;
    if (req.url.includes('/api/')) return;

    event.respondWith(
        fetch(req).then(res => {
            // Кэшируем успешные GET на /tools и статику
            if (res.ok && (req.url.includes('/tools') || req.url.endsWith('.js') || req.url.endsWith('.css'))) {
                const clone = res.clone();
                caches.open(CACHE_NAME).then(c => c.put(req, clone));
            }
            return res;
        }).catch(() => caches.match(req))
    );
});
