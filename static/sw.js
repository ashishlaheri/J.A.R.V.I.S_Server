// J.A.R.V.I.S. Service Worker v3.1
const CACHE_NAME = 'jarvis-v3.1';
const ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/manifest.json'
];

// Install — cache shell assets
self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate — clean old caches
self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys
                .filter(k => k !== CACHE_NAME)
                .map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// Fetch — network first, cache fallback (keeps data fresh)
self.addEventListener('fetch', (e) => {
    // Skip WebSocket and API requests
    if (e.request.url.includes('/ws') || e.request.url.includes('/api/')) return;

    e.respondWith(
        fetch(e.request)
            .then(response => {
                // Cache successful responses
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
                }
                return response;
            })
            .catch(() => caches.match(e.request))
    );
});
