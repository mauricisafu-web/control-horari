/*
 * Registre del service worker.
 *
 * En fitxer extern a propòsit: la política de seguretat de continguts de
 * l'aplicació no permet scripts en línia (`script-src 'self'`).
 *
 * Els service workers només funcionen en CONTEXTOS SEGURS: HTTPS, o bé
 * `localhost`. Per http://192.168.x.x el navegador no el registra i
 * l'aplicació no és instal·lable — continua funcionant amb normalitat com a
 * web, simplement sense icona pròpia.
 */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js').catch(function () {
      /* Sense service worker l'app funciona igual: no cal molestar l'usuari. */
    });
  });
}

/* Rellotge de la pantalla de fitxatge. Si no hi ha JS, la plantilla ja
 * ensenya l'hora del servidor: això només la manté viva. */
document.addEventListener('DOMContentLoaded', function () {
  var rellotge = document.getElementById('rellotge');
  if (!rellotge) { return; }
  function posa() {
    var ara = new Date();
    var hh = String(ara.getHours()).padStart(2, '0');
    var mm = String(ara.getMinutes()).padStart(2, '0');
    rellotge.textContent = hh + ':' + mm;
  }
  posa();
  setInterval(posa, 10000);
});

/* --------------------------------------------------------------------------
 * Avisos push.
 *
 * NO es demana permís en carregar la pàgina: un permís demanat de sobte, sense
 * que ningú l'hagi buscat, el denega tothom i llavors ja no es pot tornar a
 * demanar mai més. Es demana NOMÉS quan la persona prem el botó d'activar-los,
 * que viu a la pàgina d'instal·lació.
 *
 * A l'iPhone això només funciona si l'aplicació s'ha AFEGIT A LA PANTALLA
 * D'INICI: dins del Safari normal, l'iOS no deixa subscriure-s'hi. Per això el
 * botó explica què s'ha de fer quan detecta que no hi ha suport.
 * ----------------------------------------------------------------------- */
(function () {
  var boto = document.getElementById('activa-avisos');
  var estat = document.getElementById('estat-avisos');
  if (!boto || !estat) { return; }

  function diu(text, mena) {
    estat.textContent = text;
    estat.className = 'estat-avisos ' + (mena || '');
  }

  function aBytes(base64) {
    /* La clau VAPID viatja en base64url i `applicationServerKey` la vol en
       bytes. */
    var pla = (base64 + '='.repeat((4 - base64.length % 4) % 4))
      .replace(/-/g, '+').replace(/_/g, '/');
    var cru = atob(pla);
    var bytes = new Uint8Array(cru.length);
    for (var i = 0; i < cru.length; i++) { bytes[i] = cru.charCodeAt(i); }
    return bytes;
  }

  var suportat = ('serviceWorker' in navigator) && ('PushManager' in window)
              && ('Notification' in window);
  if (!suportat) {
    boto.disabled = true;
    diu("Aquest navegador no pot rebre avisos. Si tens un iPhone, primer has "
      + "d'afegir l'aplicació a la pantalla d'inici amb el botó de compartir; "
      + "després torna aquí.", 'avis');
    return;
  }

  if (Notification.permission === 'denied') {
    boto.disabled = true;
    diu("Has bloquejat els avisos per a aquesta aplicació. Per tornar-los a "
      + "permetre, has de canviar-ho a la configuració del navegador.", 'avis');
    return;
  }

  navigator.serviceWorker.ready.then(function (reg) {
    return reg.pushManager.getSubscription();
  }).then(function (sub) {
    if (sub) { diu('Els avisos estan activats en aquest dispositiu.', 'ok'); }
  }).catch(function () { /* sense service worker encara: el botó ja hi és */ });

  boto.addEventListener('click', function () {
    boto.disabled = true;
    diu('Un moment…');

    Notification.requestPermission().then(function (permis) {
      if (permis !== 'granted') {
        boto.disabled = false;
        diu('No s\'han activat: cal donar permís al navegador.', 'avis');
        return;
      }
      return navigator.serviceWorker.ready
        .then(function (reg) {
          return fetch('/push/clau').then(function (r) { return r.json(); })
            .then(function (dades) {
              if (!dades.activat) {
                throw new Error('els avisos no estan configurats al servidor');
              }
              return reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: aBytes(dades.clau),
              });
            });
        })
        .then(function (sub) {
          return fetch('/push/subscriu', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(sub),
          });
        })
        .then(function (r) {
          if (!r.ok) { throw new Error('el servidor no l\'ha acceptada'); }
          diu('Fet: rebràs un avís al mòbil quan hi hagi novetats.', 'ok');
        });
    }).catch(function (e) {
      boto.disabled = false;
      diu('No s\'han pogut activar (' + e.message + ').', 'error');
    });
  });
})();
