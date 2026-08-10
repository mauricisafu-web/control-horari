/*
 * Service worker del Control horari.
 *
 * REGLA CRÍTICA: aquesta aplicació tracta dades personals (presència diària,
 * absències). El service worker NO desa MAI cap resposta de pàgina: només els
 * fitxers ESTÀTICS de presentació (fulls d'estil, icones, manifest), que no
 * contenen cap dada de ningú.
 *
 * Si es cachegessin les pàgines, quedarien al dispositiu del treballador (i al
 * d'algú altre si el mòbil es comparteix o es perd), contradient el
 * `Cache-Control: no-store` que el servidor envia a cada resposta amb dades.
 *
 * Serveix, doncs, per a dues coses:
 *   · fer l'aplicació INSTAL·LABLE (requisit de les PWA);
 *   · que la interfície carregui de pressa i no es vegi trencada si la
 *     cobertura va justa.
 */
const CACHE = 'control-horari-estatics-v1';

// NOMÉS presentació. Cap URL amb dades. Si algú hi afegeix '/' o '/hores'
// algun dia, el test de tests/test_pwa.py ha de fallar.
const ESTATICS = [
  '/static/css/base.css',
  '/manifest.webmanifest',
  '/static/icones/icona-192.png',
  '/static/icones/icona-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      // Si un fitxer no hi és, la instal·lació NO ha de fallar: l'aplicació
      // ha de continuar funcionant igual, només sense cache.
      .then((c) => c.addAll(ESTATICS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((claus) => Promise.all(
        claus.filter((k) => k !== CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);

  // Tot el que no sigui un estàtic propi va SEMPRE a la xarxa i no es desa:
  // altres orígens, POST, i qualsevol pàgina amb dades.
  const esEstatic = url.pathname.startsWith('/static/')
                 || url.pathname === '/manifest.webmanifest';
  if (req.method !== 'GET' || url.origin !== self.location.origin || !esEstatic) {
    return;  // sense respondre-hi: el navegador ho fa com sempre
  }

  // Estàtics: primer la cache (ràpid) i s'actualitza en segon pla.
  e.respondWith(
    caches.match(req).then((desada) => {
      const xarxa = fetch(req).then((resp) => {
        if (resp && resp.ok) {
          const copia = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copia));
        }
        return resp;
      }).catch(() => desada);
      return desada || xarxa;
    })
  );
});
