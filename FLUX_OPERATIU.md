# FLUX_OPERATIU.md — De «construït» a «en marxa»

> Aquest document és diferent de `desplegament/DESPLEGAMENT.md` (que és
> **tècnic**: comandes de `gcloud`/`firebase`). Aquest és **operatiu**: l'ordre
> real de passos, barrejant tècnica, decisions i persones, perquè l'aplicació
> passi de «funciona en local amb dades de mentida» a «la fa servir la
> plantilla de debò».
>
> Estat de partida (2026-08-10): aplicació construïda, 330 proves verdes,
> verificada d'extrem a extrem amb dades sintètiques. **Res desplegat encara.**
> Pilot decidit **sense passar pel DPD** — vegeu la Fase 3 per saber què
> implica exactament això.

---

## Com llegir aquest document

Cada pas té una marca de qui l'ha de fer:

- 🧑 **Tu** — requereix una decisió, un compte, una targeta o parlar amb algú.
  Cap agent ho pot fer per tu.
- 🤖 **Jo (amb tu al costat)** — tècnic, ho puc fer jo si em dónes l'accés
  (per exemple, si m'obres una sessió de terminal autenticada).
- ✅ **Ja fet**

Segueix les fases en ordre. No té sentit fer la Fase 2 sense haver tancat la
Fase 1, i intentar-ho és exactament el que va fer perdre setmanes amb el
Tailscale i l'Oracle Cloud en aquest mateix projecte.

---

## Fase 0 — Ja fet ✅

- [x] Aplicació construïda i provada (330 proves).
- [x] Recorregut sencer verificat amb dades sintètiques: fitxatge, vacances,
      aprovació, informes.
- [x] Artefactes de desplegament preparats (`Dockerfile`, regles i índexs de
      Firestore, `firebase.json`).
- [x] `docker compose` funciona en local sense cap compte de Google.

Si vols tornar-ho a veure funcionar abans de continuar:

```bash
cd /c/Users/secretari/control-horari
DADES_PROVA=1 "C:/Users/secretari/AppData/Local/Programs/Python/Python312/python.exe" app_web.py
```

`http://127.0.0.1:5004` → `admin01` / `Prova-1234`.

---

## Fase 1 — Compte i eines 🧑

**Bloqueig real: implica una targeta i una identitat de Google.** Ningú ho pot
fer en el teu lloc.

1. [ ] Crear (o triar) el compte de Google que administrarà el projecte.
2. [ ] A <https://console.firebase.google.com>, crear el projecte
       (per exemple `control-horari-torre-espanyol`).
3. [ ] Activar el **pla Blaze**. Cal targeta. La factura prevista és **0 €**
       (vegeu `desplegament/FIREBASE.md` §2), però Cloud Run no funciona amb
       el pla gratuït.
4. [ ] **Abans de fer res més**: crear l'**alerta de pressupost a 1 €**
       (Facturació → Pressupostos i alertes), amb avís per correu.
5. [ ] Crear la base de dades de **Firestore, mode natiu**, ubicació
       **`eur3`** (no es pot canviar després).
6. [ ] Instal·lar les eines:
       ```bash
       npm install -g firebase-tools
       ```
       `gcloud` (<https://cloud.google.com/sdk/docs/install>) i **Java**
       (per a l'emulador de Firestore de la Fase 2).
7. [ ] Autenticar-te:
       ```bash
       gcloud auth login && firebase login
       ```

**Fet quan:** pots executar `firebase projects:list` i hi surt el projecte.

---

## Fase 2 — Provar-ho contra l'emulador abans de tocar producció 🤖

Aquest pas és el que tanca el risc estructural del projecte: fins ara totes
les proves han corregut contra un magatzem en memòria, i **una consulta sense
el seu índex passa aquestes proves i falla en producció**. Amb Node i Java
instal·lats, jo puc fer-ho:

```bash
firebase emulators:start --only firestore
```

I fer córrer `tests/integracio/` contra l'emulador. Si hi surt algun error
d'índex que falta, el corregim aquí, no el dia del desplegament real.

**Fet quan:** les proves d'integració passen contra l'emulador.

---

## Fase 3 — Decisió de compliment: què implica «pilot sense DPD» 🧑

Has decidit no passar pel DPD per al pilot. És una decisió vàlida, però amb
una condició que no és negociable i que ja he aplicat al codi:

> **Mentre no hi hagi vistiplau, l'aplicació només pot tenir dades
> sintètiques.** El dia que un treballador real hi entri i fitxi, hi ha un
> tractament de dades personals de ple dret (article 4.1 RGPD), amb DPD o
> sense.

Coses que **sí** pots fer ara, sense el DPD:
- [ ] Desplegar a Firebase amb dades sintètiques (Fase 4).
- [ ] Ensenyar l'aplicació a algú de l'ajuntament fent-hi de treballador de
      prova.
- [ ] Decidir la configuració real (serveis, horaris, festius) sense encara
      donar d'alta ningú.

Coses que **has de resoldre abans** de donar d'alta el primer treballador
real (Fase 6):
- [ ] Omplir els camps entre claudàtors de `templates/avis_legal.html`
      (nom de l'ajuntament, adreça, correu de contacte, DPD si n'hi ha).
- [ ] Decidir si acceptes el DPA de Google Cloud ara (recomanat, encara que
      sigui informal) o quan es formalitzi amb el DPD.
- [ ] Confirmar la normativa local de registre de jornada per a personal
      funcionari, i si cal informar-ne la representació del personal abans
      del pilot.
- [ ] Quan tanquis això amb el DPD més endavant, l'encàrrec ja preparat
      (`encarrecs/4D-compliment-rgpd.md`) genera el RAT, l'anàlisi de riscos
      i la nota informativa formal.

**Fet quan:** l'avís legal ja no té claudàtors i saps què li diràs al DPD
quan hi parlis.

---

## Fase 4 — Desplegament real, amb dades sintètiques 🧑🤖

Segueix `desplegament/DESPLEGAMENT.md` punt per punt (jo et puc acompanyar en
cada comanda). Resum de l'ordre:

1. [ ] Regles i índexs de Firestore:
       `firebase deploy --only firestore:rules,firestore:indexes`
       — i **esperar** que els índexs acabin de construir-se.
2. [ ] Política TTL sobre `activitat.caduca_el` (a la consola de Firestore).
3. [ ] Secret de sessió a Secret Manager.
4. [ ] `gcloud run deploy` amb **`--min-instances 0`** (no es toca: és el que
       fa que sigui gratis).
5. [ ] `firebase deploy --only hosting`.
6. [ ] Poblar amb dades sintètiques contra Firestore de debò:
       ```bash
       REBOST=firestore PROJECTE_FIREBASE=<el-teu-projecte> python eines/dades_prova.py
       ```

**Fet quan**, TOTS aquests punts, no només que «carregui»:
- [ ] Des d'un **mòbil amb dades mòbils** (no la wifi de l'ajuntament): entrar,
      fitxar, veure el saldo.
- [ ] La PWA s'instal·la (Android amb Chrome, iPhone amb Safari).
- [ ] Cronometrada l'arrencada en fred (uns segons, no minuts).
- [ ] La URL directa `*.run.app` és rebutjada (403).
- [ ] Un client anònim no llegeix res de Firestore.
- [ ] **Al cap d'una setmana**: consum revisat a la consola — molt per sota
      dels límits gratuïts.

Si algun d'aquests punts falla, **es corregeix aquí**, amb dades sintètiques,
no amb dades reals a sobre.

---

## Fase 5 — Configuració real (encara amb dades sintètiques) 🧑

Amb l'aplicació desplegada de debò, entra com a administrador i substitueix
la configuració de mentida per la real, **sense donar d'alta ningú real
encara**:

1. [ ] `/configuracio/` → esborra els serveis d'exemple i crea els reals
       (Oficines, Brigada, SAIAR... els que tingui l'ajuntament).
2. [ ] Importa els festius de l'any (`Importa'ls de la Generalitat`) i afegeix
       els festius propis que faltin.
3. [ ] `/configuracio/horaris` → crea els patrons d'horari reals de
       l'ajuntament (torns d'oficines, de la brigada...).
4. [ ] Paràmetres (`dies_vacances_defecte`, `nom_ajuntament`...) ajustats a
       la realitat.
5. [ ] Esborra els comptes `prova*` un cop la configuració real estigui a punt
       (o deixa'ls per a la Fase 7, la prova pilot).

**Fet quan:** la configuració reflecteix l'ajuntament real, encara amb zero
treballadors reals donats d'alta.

---

## Fase 6 — Nota informativa i tancament del compliment 🧑

**No s'envia res fins que tu ho confirmis expressament** — ja ho vas deixar
clar en aquest projecte i continua valent aquí.

1. [ ] Tancar amb el DPD (encara que sigui informalment per al pilot) el que
       queda de la Fase 3.
2. [ ] Redactar/confirmar la nota informativa amb la URL final de
       l'aplicació.
3. [ ] Decidir el canal per fer-la arribar (correu, paper, tauler d'anuncis).

**Fet quan:** tens la nota llesta i saps a qui l'envies i quan.

---

## Fase 7 — Pilot amb persones reals 🧑

1. [ ] Tria 2-3 treballadors, un de cada servei si es pot.
2. [ ] Envia'ls la nota informativa **abans** de crear-los el compte.
3. [ ] Dona'ls d'alta des de `/configuracio/comptes` (o amb
       `eines/gestiona_comptes.py` si prefereixes la consola). Reben la
       contrasenya provisional per correu.
4. [ ] Ensenya'ls a instal·lar la PWA (`/instal-lacio` ho explica per Android
       i iPhone).
5. [ ] TOTP obligatori si algun d'ells és responsable o administrador.
6. [ ] Deixa-ho correr **1-2 setmanes**.

**Fet quan:** el pilot ha fet un cicle complet — fitxatges normals, com a
mínim una sol·licitud de vacances demanada i resolta — sense que ningú s'hagi
quedat encallat.

---

## Fase 8 — Revisió i ampliació 🧑

1. [ ] Repassar el log d'activitat i preguntar directament al pilot: què no
       s'entén, què fa falta.
2. [ ] Corregir el que calgui (jo puc ajudar-hi si em dius què ha sortit).
3. [ ] Donar d'alta la resta de la plantilla, per tandes si l'ajuntament és
       gran, d'una vegada si són poques persones.
4. [ ] Configurar la còpia de seguretat setmanal
       (`gcloud firestore export`) cap a fora de Google, i **provar-ne la
       restauració** un cop.
5. [ ] Decidir qui és responsable del manteniment trimestral
       (`desplegament/MANTENIMENT.md`).

**Fet quan:** tota la plantilla té compte i l'aplicació és l'eina real de
control horari de l'ajuntament.

---

## Full de ruta ràpid (resum d'una pantalla)

```
1. Compte Google + Blaze + alerta 1€ + eines            🧑
2. Emulador de Firestore (índexs verificats)              🤖
3. Omplir avís legal + decidir DPD/normativa              🧑
4. Desplegar a Firebase amb dades sintètiques + verificar  🧑🤖
5. Configuració real (serveis/horaris/festius)             🧑
6. Nota informativa (NO s'envia fins que ho confirmis)     🧑
7. Pilot amb 2-3 persones, 1-2 setmanes                    🧑
8. Revisió, còpies de seguretat, alta de tota la plantilla 🧑
```

Camí crític: **1 → 4** és tot tècnic i el podem fer junts en una sessió. **3**
i **6-7** depenen de persones i de temps de resposta que no controlem —
pots avançar 1, 2, 4 i 5 mentre esperes la resposta del DPD o dels
treballadors del pilot.
