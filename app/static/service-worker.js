const CACHE_NAME = 'agrivision-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  // Only cache GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request).catch(() => {
          // If fetch fails (offline) and it's a page navigation
          if (event.request.mode === 'navigate') {
             return new Response(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Offline - PikDrishti AI</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body { font-family: sans-serif; text-align: center; padding: 2rem; color: #333; background: #f5f7f5; }
                        .card { background: white; padding: 2rem; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                        h2 { color: #2E7D32; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>You are offline</h2>
                        <p>Please check your internet connection.</p>
                        <p>Previously saved information is still available if cached.</p>
                        <button onclick="window.location.reload()" style="background: #2E7D32; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer;">Retry</button>
                    </div>
                </body>
                </html>
             `, { headers: { 'Content-Type': 'text/html' } });
          }
        });
      })
  );
});
