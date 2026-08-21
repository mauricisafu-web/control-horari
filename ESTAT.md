# ESTAT.md — Taulell de progrés

**Versió del contracte**: 1.0 · **Última actualització**: 2026-08-20

---

## Resum

| Onada | Estat | Què hi ha |
|---|---|---|
| Preparació | ✅ **FETA** | Contracte, port de magatzem, fixtures, 20 encàrrecs |
| 0 · Esquelet | ✅ **FETA** | Fàbrica, seguretat, blueprints, base.html, PWA |
| 1 · Domini i magatzem | ✅ **FETA** | `core/` sencer i `magatzem/` sencer |
| 2 · Auth, TOTP, PWA, correus | ✅ **FETA** | Entrada amb segon factor, icones, notificacions |
| 3 · Pantalles | ✅ **FETA** | Fitxatge, hores, absències, gestió, configuració |
| 4 · Informes i purga | ✅ **FETA** | CSV i PDF del registre, purga amb salvaguardes |
| 5 · Desplegament | ✅ **DESPLEGAT** | En producció a Firebase Hosting + Cloud Run + Firestore (`eur3`) |

**330 proves verdes.** `core/` no importa Flask ni res de Google, i cap API de
Google apareix fora de `magatzem/rebost_firestore.py`.

---

## Verificat funcionant (extrem a extrem, amb dades sintètiques)

- Entrada amb contrasenya i **segon factor** (admins i responsables).
- **Cicle de fitxatge sencer**: entrada → pausa → represa → sortida, amb l'estat
  correcte a cada pas i el rebut de l'hora exacta.
- Antidoble-toc: dos tocs seguits no creen dos marcatges.
- Correcció de marcatge propi → queda **pendent de validar**; el responsable la
  valida o la rebutja, i **rebutjar-la restaura l'original**.
- Sol·licitud de vacances amb saldo, solapaments i prorrateig explicats;
  aprovació per un responsable del servei; el dia surt cobert al resum d'hores.
- **Ningú resol la seva pròpia sol·licitud**, ni sent administrador.
- Un administrador pot muntar l'aplicació de zero sense sortir del navegador.
- Informes en **CSV** (amb BOM, s'obre bé a l'Excel) i en **PDF**.
- Purga amb simulació i amb la salvaguarda dels dos últims anys.
- Totes les pantalles responen; la matriu de permisos es genera del `url_map`.

## Errors reals trobats i corregits durant la construcció

| On | Què |
|---|---|
| `zoneinfo` | Ni Windows ni `python:slim` porten la base de zones: `tzdata` és dependència obligatòria |
| `web/auth.py` | El comptador d'intents era una variable de mòdul, compartida per totes les instàncies |
| `_calendari.html` | Jinja resolia `casella.items` com el **mètode** del diccionari, no la clau |
| `web/informes.py` | Li faltava el decorador d'administrador |
| `core/fitxatge.py` | Dos marcatges del mateix segon donaven «és anterior» en lloc del missatge del doble toc |
| `web/configuracio.py` | Una variable anomenada `any` tapava la funció incorporada a tota la funció |
| `core/purga.py` | La salvaguarda s'ancorava a la data que li passen, no a la real: no protegia de res |
| `eines/dades_prova.py` | Generava marcatges d'avui a les 15:00 (futur): no es podia fitxar a la demostració |

---

## El que falta, i qui ho ha de fer

### Fet: desplegament real (2026-08-20)

| # | Tràmit | Estat |
|---|---|---|
| T1 | Projecte de Firebase (`control-horari-torre-espanyol`), pla Blaze | Fet |
| T2 | Alerta de pressupost a 1 € | Feta per l'usuari a la consola |
| T3 | `gcloud`, `firebase-tools`, Node, Java instal·lats | Fet |
| — | Netskope (proxy corporatiu) interceptava l'HTTPS de `gcloud`/Node/Python | Resolt amb un paquet de certificats combinat a C:\Users\secretari\.certs\ |
| — | Facturació vinculada (compte "Pago de Firebase") | Feta |
| — | Firestore creat, mode natiu, `eur3` | Fet |
| — | Regles (denega-ho tot als clients) + 7 índexs compostos + TTL sobre `activitat.caduca_el` | Desplegats |
| — | Secret `control-horari-secret` a Secret Manager + permisos al compte de servei | Fet |
| — | Cloud Run (`min-instances=0`, `max-instances=2`, `europe-west1`) | Desplegat |
| — | Firebase Hosting (`control-horari-torre-espanyol.web.app`) | Desplegat |
| — | URL directa de Cloud Run rebutjada (`DOMINI_PUBLIC`) | Verificat, 403 |

**Parany trobat**: `gcloud run deploy --source .` no troba el `Dockerfile`
perquè viu a `desplegament/Dockerfile`, no a l'arrel, i aquesta versió de
`gcloud` no té `--dockerfile`. Es construeix la imatge amb `gcloud builds
submit --config` (apuntant explícitament al Dockerfile) i després es
desplega amb `gcloud run deploy --image`.

**Encara pendent** (vegeu `FLUX_OPERATIU.md` Fases 4-8): verificar des d'un
mòbil amb dades mòbils, instal·lar la PWA, revisar el consum a la consola al
cap d'una setmana, configuració real (serveis/horaris/festius) i alta dels
treballadors.

### Compliment: pilot sense DPD (actualitzat 2026-08-20)

L'usuari ha decidit fer un **pilot sense passar pel DPD**. Això no elimina el
tràmit, el posposa. Estat actual:

- [x] Avís legal (`templates/avis_legal.html`) omplert amb el nom real de
      l'ajuntament i el correu de contacte (`secretaria@torredelespanyol.cat`),
      per instrucció explícita de l'usuari (2026-08-20). Sense adreça postal
      ni nom del DPD (no facilitats).
- [ ] Documentació de compliment (RAT, anàlisi de riscos, nota informativa
      formal). Hi ha l'encàrrec preparat a `encarrecs/4D-compliment-rgpd.md`.
- [ ] Acceptar el DPA de Google Cloud.
- [ ] Confirmar la normativa local de registre de jornada per a personal
      funcionari i si cal informar-ne la representació del personal.

**Dades reals (2026-08-20):** l'usuari ha indicat explícitament que
introduirà dades reals «de les que compto autorització», és a dir, que
considera tenir la base per fer-ho pel seu compte, sense esperar el tràmit
formal del RAT/DPD descrit a dalt. Aquesta és una decisió de l'usuari com a
responsable del tractament, no una validació tècnica: cap agent ha revisat
ni pot revisar si aquesta autorització és suficient.

### Millores que no s'han fet (decisions conscients)

- Repàs d'accessibilitat i coherència visual (`encarrecs/4B`).
- Auditoria de seguretat independent (`encarrecs/4C`).
- Proves d'integració contra l'emulador de Firestore: escrites com a plantilla,
  però **no executades** (cal Node i Java). És una porta abans de desplegar.

---

## Decisions preses

| Data | Decisió |
|---|---|
| 2026-08-05 | Abast: fitxatge + horari teòric + saldo, més vacances i festius |
| 2026-08-05 | Aplicació **totalment independent** de qualsevol altra |
| 2026-08-05 | Allotjament: **Firebase** (Hosting + Cloud Run) |
| 2026-08-05 | **Cost zero**: escalat a zero i pressupost de lectures |
| 2026-08-05 | **El NAS queda descartat** |
| 2026-08-05 | Persistència: **Firestore** darrere d'un port intercanviable |
| 2026-08-05 | Proves contra un adaptador **en memòria**: cap eina externa per treballar |
| 2026-08-10 | **Pilot sense DPD**, per decisió de l'usuari. Dades sintètiques fins que es tramiti |
| 2026-08-10 | Construcció feta per Opus en una sola sessió, no repartida entre agents |
| 2026-08-20 | Desplegament real fet amb Sonnet, guiant l'usuari pas a pas per les accions que exigien el seu compte (autenticacions OAuth, facturació, alerta de pressupost) |
| 2026-08-20 | L'usuari confirma que introduirà dades reals sota la seva pròpia autorització, sense esperar el tràmit formal del DPD |
| 2026-08-21 | **Els avisos es fan per push al mòbil, no per correu.** L'ajuntament no vol que les credencials del seu servidor de correu surtin cap al núvol; un avís push no en necessita cap, i el contingut viatja xifrat d'extrem a extrem. El correu queda al codi per si algun dia es configura |
| 2026-08-21 | **El fitxador s'apaga a producció.** De moment l'ajuntament només vol demanar i aprovar vacances i permisos. No s'esborra: es queda darrere d'un interruptor a Configuració, i tornar-lo a engegar és marcar una casella |

---

## Registre de desplegaments

| Data | Versió | On | Verificat per | Notes |
|---|---|---|---|---|
| 2026-08-10 | `main` | local (Docker i `python app_web.py`) | Opus | Recorregut sencer amb dades sintètiques |
| 2026-08-20 | `4a97e46` | Firebase (`control-horari-torre-espanyol`) | Sonnet, amb l'usuari | Desplegament real: Hosting + Cloud Run + Firestore. Verificat: `/avis-legal` i `/manifest.webmanifest` responen 200 per la URL pública; la URL directa de Cloud Run dona 403 |
| 2026-08-21 | `control-horari-00006-gwk` | Firebase (`control-horari-torre-espanyol`) | Opus | Avisos push. Verificat: el service worker desplegat porta els gestors de `push` i `notificationclick`, l'avís legal els documenta i les claus VAPID arriben al contenidor |
| 2026-08-21 | `control-horari-00003-d8h` | Firebase (`control-horari-torre-espanyol`) | Opus | Interruptor del fitxador, i apagat a producció. Verificat: l'aplicació respon i `/` redirigeix |
| 2026-08-21 | `control-horari-00002-tlg` | Firebase (`control-horari-torre-espanyol`) | Opus | Correcció de la galeta `__session`. Verificat en producció: la sessió es manté entre peticions, el testimoni CSRF és estable i el POST de `/login` supera la comprovació CSRF |

---

## Estat real de les dades de producció (2026-08-21)

| Col·lecció | Documents | Comentari |
|---|---|---|
| `serveis` | 3 | Oficines, Brigada, SAIAR |
| `festius` | 2 | anys 2026 i 2027 importats |
| `treballadors` | 1 | només `msabaterf` (administrador) |
| `patrons` | 0 | buit, i **de moment no cal**: amb el fitxador apagat no hi ha saldo d'hores a calcular, i les vacances es compten en dies hàbils de calendari |
| `absencies` | 0 | correcte: són sol·licituds, encara no n'hi ha cap |

Amb el fitxador apagat, el que queda per posar-ho en marxa és **carregar la
plantilla**: no cal cap patró d'horari. Els patrons només tornaran a fer falta
el dia que s'engegui el fitxatge.
