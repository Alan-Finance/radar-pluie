// Éclaircie : garde sur le téléphone les images radar et prévision déjà vues (leurs noms sont uniques et
// elles ne changent jamais), pour que l'onglet Radar démarre tout de suite à la réouverture de l'appli :
// seules les nouvelles images sont téléchargées. Tout le reste passe normalement par le réseau.
const CACHE = 'eclaircie-radar-v1';
const IMG = /\/data\/[rp]\/[^/]+\.png$/;
const MAX = 150;  // nombre d'images gardées (les plus anciennes sont effacées)

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));

self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || !IMG.test(u.pathname)) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(u.pathname);
    if (hit) return hit;
    const r = await fetch(e.request);
    if (r.ok) { await c.put(u.pathname, r.clone()); trim(c); }
    return r;
  })());
});

let trimming = false;
async function trim(c) {
  if (trimming) return;
  trimming = true;
  try {
    const keys = await c.keys();
    if (keys.length > MAX) await Promise.all(keys.slice(0, keys.length - MAX).map((k) => c.delete(k)));
  } finally { trimming = false; }
}
