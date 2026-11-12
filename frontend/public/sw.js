// Online game: never cache authenticated requests, room state, or old app HTML.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  if (event.request.mode !== 'navigate') return;
  event.respondWith(fetch(event.request).catch(() => new Response('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>OUT. — Offline</title><body><h1>You are offline</h1><p>OUT. needs an internet connection to play. Reconnect and reload to return to your room.</p><a href="/">Try again</a></body></html>', {headers:{'Content-Type':'text/html'},status:503})));
});
