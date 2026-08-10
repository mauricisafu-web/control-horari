# ESTAT.md — Taulell de progrés

**Versió del contracte**: 1.0 · **Última actualització**: 2026-08-10

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
| 5 · Desplegament | 🟨 **PREPARAT** | Artefactes fets i provats en local. **Bloquejat pel compte de Google** |

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

### Bloquejat: compte de Google (ho ha de fer l'usuari)

Crear un compte, activar el pla Blaze amb una targeta i autenticar-s'hi són
accions de compte i de pagament. Els passos exactes són a
`desplegament/DESPLEGAMENT.md`.

| # | Tràmit | Qui |
|---|---|---|
| T1 | Projecte de Firebase, pla Blaze, Firestore a `eur3` o `europe-west1` | Usuari |
| T2 | **Alerta de pressupost a 1 €** — el primer de tot | Usuari |
| T3 | Instal·lar `firebase-tools`, `gcloud` i Java | Usuari |

Un cop fet, el desplegament és seguir `DESPLEGAMENT.md` de dalt a baix.

### Pendent de decisió de l'usuari (pilot sense DPD)

L'usuari ha decidit fer un **pilot sense passar pel DPD**. Això no elimina el
tràmit, el posposa:

- [ ] Documentació de compliment (RAT, anàlisi de riscos, nota informativa a
      la plantilla). Hi ha l'encàrrec preparat a `encarrecs/4D-compliment-rgpd.md`.
- [ ] Omplir els camps entre claudàtors de `templates/avis_legal.html`
      (ajuntament, adreça, contacte, DPD).
- [ ] Acceptar el DPA de Google Cloud.
- [ ] Confirmar la normativa local de registre de jornada per a personal
      funcionari i si cal informar-ne la representació del personal.

**Mentre no es faci: dades sintètiques.** El dia que un treballador real
fitxi, hi ha un tractament de dades personals de ple dret.

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

---

## Registre de desplegaments

| Data | Versió | On | Verificat per | Notes |
|---|---|---|---|---|
| 2026-08-10 | `main` | local (Docker i `python app_web.py`) | Opus | Recorregut sencer amb dades sintètiques |
| | | Firebase | | pendent del compte de Google |
