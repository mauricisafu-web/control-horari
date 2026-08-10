# Encàrrec 2B · PWA instal·lable

**Onada 2** · Depèn de: 0A · Alhora que: 2A, 2C, 2D
· No depèn de cap funcionalitat: es pot avançar a l'onada 1 si vas curt.

## Objectiu

Que un treballador pugui **instal·lar l'aplicació a la pantalla d'inici** del
mòbil i obrir-la com una app, sense barra de navegador. És el requisit que
justifica tot el desplegament amb HTTPS.

## Escrius

```
web/pwa.py                    static/manifest.webmanifest
static/sw.js                  static/js/pwa.js
static/icones/*               templates/pwa/instal_lacio.html
eines/genera_icones.py        tests/test_pwa.py
```

## Llegeixes

`DISSENY.md` §8. De referència: `expedients-nomines-beta/static/sw.js`,
`pwa.js` i `manifest.webmanifest` — **el service worker d'allà ja té ben
resolta la regla crítica de no cachejar dades**; copia'n el criteri.

## Feina

### `web/pwa.py` — **sense `login_required`**

| Ruta | Què |
|---|---|
| `/manifest.webmanifest` | el manifest, amb `Content-Type: application/manifest+json` |
| `/sw.js` | el service worker, **servit des de l'arrel** |
| `/instal-lacio` | pàgina d'instruccions per instal·lar-la |

**Per què `/sw.js` i no `/static/sw.js`**: l'abast d'un service worker no pot
ser més ampli que el seu propi camí. Servit des de `/static/`, només
controlaria `/static/*`. Ha de sortir de l'arrel.

Aquestes tres rutes han de respondre **sense sessió**: el navegador demana el
manifest abans que ningú entri.

### `static/manifest.webmanifest`

```
name        Control horari · Ajuntament de la Torre de l'Espanyol
short_name  Control horari
lang        ca
start_url   /
scope       /
display     standalone
orientation portrait-primary
background_color / theme_color   coherents amb base.css
icons       192 i 512, purpose "any" i "maskable" (quatre fitxers)
shortcuts   "Fitxar" -> /
```

### `static/sw.js` — **la regla crítica**

**El service worker NO desa MAI cap resposta de pàgina.** Només els estàtics de
presentació: `base.css`, els fulls dels mòduls, les icones i el manifest.

El motiu s'ha d'escriure al capdamunt del fitxer: aquesta aplicació tracta
dades personals, i el mòbil d'un treballador es pot compartir o perdre.
Cachejar les pàgines contradiria el `Cache-Control: no-store` que el servidor
envia a cada resposta.

Comportament:

- `install`: obre la cache i hi posa la llista d'estàtics, amb `catch` perquè
  un fitxer que falti **no faci fallar la instal·lació**.
- `activate`: esborra les caches de versions anteriors, `clients.claim()`.
- `fetch`: si no és `GET`, si no és del mateix origen o si el camí no comença
  per `/static/`, **no hi responguis** (`return` sense `respondWith`): que ho
  faci el navegador com sempre. Els estàtics, cache primer i actualització en
  segon pla.

### `static/js/pwa.js`

Registre del service worker, en fitxer extern perquè la CSP no permet scripts
en línia. Si el registre falla, **silenci**: sense service worker l'aplicació
funciona igual, només no és instal·lable. No molestis l'usuari amb un error.

### `eines/genera_icones.py`

Genera les quatre icones PNG a partir d'un disseny simple fet per codi (un
rellotge o unes inicials sobre el color corporatiu). Sense dependències noves:
si `Pillow` no hi és, escriu els PNG a mà amb `zlib` i `struct` — la beta ja ho
fa a `eines/genera_icona.py`, mira-t'ho. Les icones **maskable** necessiten
marge de seguretat: el dibuix ha de cabre dins del 80 % central, o Android
n'hi retallarà els extrems.

### `templates/pwa/instal_lacio.html`

Instruccions curtes i separades per a **Android (Chrome)** i **iPhone
(Safari)** — que són diferents i la gent es perd. Amb el detall que a l'iPhone
cal fer «Compartir → Afegir a la pantalla d'inici», que no és evident. Enllaça
aquesta pàgina des del peu de `base.html`... **no**: `base.html` és de 0A i no
el pots tocar. Enllaça-la des de la teva pàgina i anota a `incidencies/2B.md`
que caldria l'enllaç al peu, perquè ho faci l'agent 4B.

## Acceptació

- [ ] `/manifest.webmanifest`, `/sw.js` i `/instal-lacio` responen **sense
      sessió**, amb el tipus de contingut correcte.
- [ ] El manifest valida (sense errors a les eines de desenvolupament del
      navegador) i les quatre icones existeixen i s'obren.
- [ ] Amb `https://localhost` o `http://localhost`, Chrome ofereix instal·lar
      l'aplicació. **Comprova-ho de debò al navegador**, no només amb un test.
- [ ] `pytest tests/test_pwa.py -q` verd, incloent-hi un test que llegeixi
      `sw.js` i comprovi que **no** hi ha cap ruta de pàgina a la llista de
      la cache (és la salvaguarda contra que algú hi afegeixi `/` un dia).

## Paranys

- **Els service workers només funcionen en context segur**: HTTPS o
  `localhost`. Per `http://192.168.x.x:5004` el navegador no el registra i
  l'aplicació no és instal·lable. No és un error teu: prova-ho a `localhost`.
- **La cache del service worker és molt insistent.** Puja el número de versió
  del nom de la cache (`control-horari-estatics-v2`) cada cop que canviïn els
  estàtics, o els usuaris veuran l'aparença antiga durant dies.
- **No afegeixis notificacions push.** Necessitarien un servei extern de
  missatgeria i canviarien l'avaluació de protecció de dades. Fora d'abast.
- **No afegeixis cua de fitxatges fora de línia.** És una decisió expressa
  (`DISSENY.md` §1): desaria dades personals al dispositiu.
