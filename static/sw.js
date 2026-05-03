// J.A.R.V.I.S. Service Worker — offline caching + push notifications
const CACHE_NAME = 'jarvis-v3';
const STATIC_ASSETS = ['/', '/static/css/style.css', '/static/js/app.js'];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Network first, fall back to cache
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});

// Push notifications
self.addEventListener('push', (event) => {
    const data = event.data ? event.data.json() : { title: 'J.A.R.V.I.S.', body: 'You have a notification.' };
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/icon.png',
            badge: '/static/icon.png',
            vibrate: [200, 100, 200]
        })
    );
});
