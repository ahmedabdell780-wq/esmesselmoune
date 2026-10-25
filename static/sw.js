/* ===================================================================
   Service Worker — نادي الوفاق الرياضي مسلمون (ESM)
   Version: esm-v2
   =================================================================== */

const CACHE_NAME = 'esm-v2';
const OFFLINE_URL = '/offline/';

// Critical assets to pre-cache on install
const PRECACHE_ASSETS = [
  OFFLINE_URL,
  '/manifest.json',
  '/static/manifest.json',
  '/static/img/icons/icon-192x192.png',
  '/static/img/icons/icon-512x512.png',
  '/static/img/icons/icon-maskable-512x512.png',
  '/static/img/logo.png'
];

// Paths that must NEVER be intercepted or cached
const EXCLUDED_PREFIXES = [
  '/admin/',
  '/accounts/',
  '/api/'
];

// 1. INSTALL
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// 2. ACTIVATE (cleanup old cache versions)
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. FETCH
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Rule A: Only handle GET requests
  if (req.method !== 'GET') {
    return;
  }

  // Rule B: Only handle same-origin requests
  if (url.origin !== self.location.origin) {
    return;
  }

  // Rule C: Ignore excluded administrative/auth paths
  if (EXCLUDED_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return;
  }

  // Strategy 1: Cache-First for static assets (/static/...)
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(req).then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
            return networkResponse;
          }
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(req, responseToCache);
          });
          return networkResponse;
        }).catch(() => {
          // If offline and static asset is not cached, return empty or fail gracefully
          return cachedResponse;
        });
      })
    );
    return;
  }

  // Strategy 2: Stale-While-Revalidate for HTML page navigation
  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) => {
        return fetch(req)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              cache.put(req, networkResponse.clone());
            }
            return networkResponse;
          })
          .catch(async () => {
            // Network failed: try cache
            const cachedResponse = await cache.match(req);
            if (cachedResponse) {
              return cachedResponse;
            }
            // If neither network nor cache has the page, show offline page
            const offlineResponse = await cache.match(OFFLINE_URL);
            return offlineResponse || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
          });
      })
    );
    return;
  }

  // Default: Network with Cache fallback
  event.respondWith(
    caches.match(req).then((cachedResponse) => {
      return fetch(req).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, responseToCache));
        }
        return networkResponse;
      }).catch(() => cachedResponse);
    })
  );
});
