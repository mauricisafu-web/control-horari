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
