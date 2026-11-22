/* Letter Land offline helper.
   - The game page: try the network first (so updates arrive), fall back to the saved copy when offline.
   - Voice and word files (their address ends in ?h=...): once saved they never change, so use the saved copy first. */
const SHELL = 'll-shell-v1', AUD = 'll-audio';

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(['./', './index.html'])).catch(() => {}));
});

self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });

function timeout(ms) { return new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms)); }

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const u = new URL(req.url);
  if (u.origin !== location.origin) return;
  const isPage = req.mode === 'navigate' || u.pathname.endsWith('/') || u.pathname.endsWith('/index.html');
  if (isPage) {
    e.respondWith((async () => {
      const c = await caches.open(SHELL);
      try {
        const r = await Promise.race([fetch(req, { cache: 'no-cache' }), timeout(6000)]);
        if (r && r.ok) { c.put('./index.html', r.clone()); return r; }
        throw new Error('bad');
      } catch (err) {
        return (await c.match('./index.html')) || (await c.match('./')) || Response.error();
      }
    })());
    return;
  }
  if (u.searchParams.has('h')) {
    e.respondWith((async () => {
      const c = await caches.open(AUD);
      const hit = await c.match(req);
      if (hit) return hit;
      const r = await fetch(req);
      if (r && r.ok) { try { await c.put(req, r.clone()); } catch (err) {} }
      return r;
    })());
    return;
  }
  // anything else (sw.js itself, icons): network, falling back to a saved copy
  e.respondWith((async () => {
    const c = await caches.open(SHELL);
    try { const r = await fetch(req); if (r && r.ok) c.put(req, r.clone()); return r; }
    catch (err) { return (await c.match(req)) || Response.error(); }
  })());
});
