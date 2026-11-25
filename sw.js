// Éclaircie : service worker désactivé (25/11/2026, l'appli buguait après sa mise en place).
// Cette version vide le cache, se désinscrit et recharge la page une fois, pour revenir au fonctionnement d'avant.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil((async () => {
  for (const k of await caches.keys()) await caches.delete(k);
  await self.registration.unregister();
  for (const c of await self.clients.matchAll({ type: 'window' })) c.navigate(c.url);
})()));
