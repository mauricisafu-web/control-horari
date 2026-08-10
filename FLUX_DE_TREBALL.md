# FLUX_DE_TREBALL.md — Com es construeix això amb diversos agents alhora

> Document operatiu. Diu **qui fa què, quan, sobre quins fitxers i quan es
> considera fet**. Els agents no el modifiquen; el modifica només qui integra.

---

## 1. Per què aquest projecte SÍ que es pot paral·lelitzar

La beta de nòmines no es pot repartir entre agents: té un `app_web.py` de
168 KB on viuen totes les rutes. Dos agents que hi treballin alhora es
trepitgen a la primera.

Aquí s'han pres quatre decisions estructurals **expressament** per evitar-ho:

1. **Contracte abans que codi.** `DISSENY.md` fixa el model de dades, les
   dataclasses, les signatures de totes les funcions i la taula de rutes
   **abans** que cap agent comenci. Ningú inventa cap interfície.
2. **Blueprints, un fitxer per mòdul.** Cap agent no toca mai el fitxer d'un
   altre. `app_web.py` només crea l'aplicació i registra els vuit blueprints,
   que ja hi són registrats des del primer dia encara que siguin buits: així
   no hi ha ni un sol conflicte de fusió al registre.
3. **Fitxers calents congelats.** `core/model.py`, `magatzem/rebost.py`,
   `tests/conftest.py`, `templates/base.html`, `static/css/base.css`,
   `requirements.txt` i `app_web.py` es tanquen a l'onada 0 i **ningú més els
   toca**. Són exactament els fitxers on tots els projectes multiagent
   xoquen.
4. **Propietat exclusiva de fitxers.** Cada tasca té una llista tancada de
   fitxers que pot escriure. Si la intersecció de dues tasques d'una mateixa
   onada no és buida, és un error del pla, no de l'agent.

---

## 2. Mapa d'onades

```
       ONADA 0                ONADA 1                ONADA 2
   ┌──────────────┐   ┌───────────────────┐   ┌──────────────────┐
   │ 0A Esquelet  │──▶│ 1A Magatzem       │──▶│ 2A Auth + TOTP   │
   │    executable│   │ 1B Còmput horari  │   │ 2B PWA           │
   └──────────────┘   │ 1C Fitxatge       │   │ 2C Desplegament  │
     (1 agent)        │ 1D Absències      │   │ 2D Correus+eines │
                      │ 1E Calendari+fest.│   └──────────────────┘
                      └───────────────────┘      (4 agents)
                         (5 agents)

       ONADA 3                              ONADA 4              ONADA 5
   ┌──────────────────────┐        ┌────────────────────┐   ┌──────────────┐
   │ 3A Web fitxatge      │───────▶│ 4A Informes+purga  │──▶│ 5A Docker    │
   │ 3B Web hores         │        │ 4B UI+accessibilit.│   │ 5B Firebase  │
   │ 3C Web absències     │        │ 4C Auditoria segur.│   │ 5C Posada en │
   │ 3D Web gestió        │        │ 4D Compliment RGPD │   │    marxa     │
   │ 3E Web configuració  │        └────────────────────┘   └──────────────┘
   └──────────────────────┘             (4 agents)          (seqüencial,
        (5 agents)                                           amb l'usuari)
```

Dependències reals (no de conveniència):

- **Tot depèn de l'onada 0**: fins que l'aplicació no arrenca i `pytest` no
  passa, no es llança res més.
- **L'onada 1 no depèn de si mateixa.** `core/` és domini pur: 1B, 1C, 1D i 1E
  no es criden entre elles i no toquen la base de dades. 1A (magatzem) tampoc
  depèn d'elles. Els cinc poden anar alhora sense cap coordinació.
- **L'onada 2 només necessita l'esquelet**, no el domini: 2B (PWA), 2C
  (desplegament) i 2D (correus) es podrien avançar a l'onada 1 si vas curt de
  temps. 2A (auth) necessita 1A per llegir comptes.
- **L'onada 3 necessita 1A + el seu mòdul de domini.** Cada blueprint és
  l'adaptador HTTP del `core/` corresponent.
- **L'onada 4 necessita l'aplicació sencera funcionant.**
- **L'onada 5 la condueix l'usuari**, amb un agent de suport.

### Si només pots tenir un agent alhora

Ordre estrictament seqüencial recomanat: `0A → 1A → 1B → 1C → 1D → 1E → 2A →
3A → 3C → 3D → 3B → 3E → 2B → 2D → 4A → 2C → 4B → 4C → 4D → 5A → 5B → 5C`.

L'ordre no és casual: després de `3A` ja tens **una aplicació que fitxa de
debò**, que és el mínim demostrable. Si has d'aturar el projecte a mitges, para
allà i tindràs alguna cosa útil.

---

## 3. Taula de propietat de fitxers

Un fitxer té **un sol propietari per onada**. Fora de la teva llista, no
escrius: ni per «arreglar una cosa petita», ni per afegir un `import`. Si
necessites un canvi en un fitxer que no és teu, és una incidència.

| Tasca | Escriu (exclusiu) | Llegeix (referència) |
|---|---|---|
| **0A** Esquelet executable | `app_web.py`, `configuracio.py`, `core/registre.py`, `web/__init__.py`, `web/{auth,fitxatge,hores,absencies,gestio,configuracio,informes,pwa}.py` (només l'esquelet buit), `templates/base.html`, `templates/error.html`, `templates/en_construccio.html`, `templates/avis_legal.html`, `static/css/base.css`, `static/js/app.js`, `tests/test_esquelet.py` | tot |
| **1A** Magatzem | `magatzem/{comptes,marcatges,absencies,horaris,festius,parametres,activitat}.py`, `eines/dades_prova.py`, `tests/test_magatzem.py`, `tests/test_rebost.py`, `tests/integracio/*` | `magatzem/rebost.py`, `magatzem/rebost_firestore.py`, `core/model.py` |
| **1B** Còmput horari | `core/comput.py`, `tests/test_comput.py` | `core/model.py` |
| **1C** Fitxatge (domini) | `core/fitxatge.py`, `tests/test_fitxatge.py` | `core/model.py` |
| **1D** Absències (domini) | `core/regles.py`, `tests/test_regles.py` | `core/model.py` |
| **1E** Calendari i festius | `core/calendari.py`, `core/festius.py`, `tests/test_calendari.py`, `tests/test_festius.py` | `core/model.py` |
| **2A** Autenticació | `web/auth.py`, `core/comptes.py`, `core/totp.py`, `templates/auth/*`, `static/css/auth.css`, `tests/test_auth.py`, `tests/test_totp.py` | `magatzem/comptes.py` |
| **2B** PWA | `web/pwa.py`, `static/js/pwa.js`, `static/sw.js`, `static/manifest.webmanifest`, `static/icones/*`, `templates/pwa/*`, `eines/genera_icones.py`, `tests/test_pwa.py` | `templates/base.html` |
| **2C** Desplegament | `desplegament/*` sencer (Dockerfile, compose, `firestore.rules`, `firestore.indexes.json`, guies), `.dockerignore`, `firebase.json`, `.firebaserc.example`, `public/robots.txt` | tot |
| **2D** Correus i eines | `core/notifica.py`, `eines/gestiona_comptes.py`, `config.ini.example`, `tests/test_notifica.py` | `configuracio.py` |
| **3A** Web fitxatge | `web/fitxatge.py`, `templates/fitxatge/*`, `static/css/fitxatge.css`, `tests/test_web_fitxatge.py` | `core/fitxatge.py`, `core/comput.py`, `magatzem/marcatges.py` |
| **3B** Web hores | `web/hores.py`, `templates/hores/*`, `static/css/hores.css`, `tests/test_web_hores.py` | `core/comput.py` |
| **3C** Web absències | `web/absencies.py`, `templates/absencies/*`, `static/css/absencies.css`, `tests/test_web_absencies.py` | `core/regles.py`, `core/calendari.py` |
| **3D** Web gestió | `web/gestio.py`, `templates/gestio/*`, `static/css/gestio.css`, `tests/test_web_gestio.py` | tot `core/` i `magatzem/` |
| **3E** Web configuració | `web/configuracio.py`, `templates/configuracio/*`, `static/css/configuracio.css`, `tests/test_web_configuracio.py` | tot `magatzem/` |
| **4A** Informes i purga | `web/informes.py`, `core/purga.py`, `templates/informes/*`, `static/css/informes.css`, `tests/test_informes.py`, `tests/test_purga.py` | tot |
| **4B** UI i accessibilitat | `static/css/*` (**tots**, en aquesta onada n'agafa la propietat), `templates/**` (només retocs de marcatge i etiquetes), `tests/test_ui.py` | tot |
| **4C** Auditoria de seguretat | `desplegament/AUDITORIA.md`, `tests/test_seguretat.py` + **PR de correccions puntuals autoritzades** | tot |
| **4D** Compliment RGPD | `compliment/*.md`, `templates/avis_legal.html` | tot |
| **5A/5B/5C** Desplegament real | `desplegament/*`, `ESTAT.md` | tot |

**Fitxers CONGELATS des de l'inici** (ja escrits; ningú els toca sense
autorització explícita de qui integra):

```
CLAUDE.md   DISSENY.md   FLUX_DE_TREBALL.md   requirements.txt   pytest.ini
core/model.py            tests/conftest.py
magatzem/rebost.py       magatzem/rebost_firestore.py
```

El port del magatzem (`rebost.py`) està congelat **especialment**: té dos
adaptadors que han de mantenir la mateixa superfície exacta. Afegir-hi una
operació vol dir implementar-la i provar-la als dos, i és feina de qui integra.

A partir de l'onada 0 s'hi afegeixen: `app_web.py`, `configuracio.py`,
`templates/base.html` i `static/css/base.css`.

**Nota sobre 4B**: és l'única onada on un agent pot tocar fitxers d'altres
(els fulls d'estil i el marcatge de les plantilles). Per això va **sola** dins
la seva franja: quan corre 4B, cap agent d'interfície treballa en paral·lel.

---

## 4. Com es llança un agent

### Opció recomanada: un worktree de git per agent

```bash
cd /c/Users/secretari/control-horari && git worktree add ../ch-1B agent/1B-comput
```

Cada agent treballa a la seva còpia i no veu els fitxers a mig fer dels
altres. Qui integra fusiona a `main` quan la tasca passa la porta.

### Opció simple: la mateixa còpia, sense branques

Funciona **perquè la propietat de fitxers és exclusiva**, però amb dues
condicions: que els agents d'una mateixa onada no siguin mai dos que escriguin
el mateix fitxer (ho garanteix la taula de §3), i que **cap agent no faci
`git commit`**: commiteja qui integra, al final de cada onada. És l'opció
aconsellada si no vols gestionar branques.

### El prompt

Cada tasca té un fitxer a `encarrecs/<ID>-<nom>.md` pensat per donar-lo tal
qual. El prompt per llançar l'agent és sempre aquest, canviant l'identificador:

```
Ets l'agent 1B d'aquest projecte. Treballa a C:\Users\secretari\control-horari.

Llegeix, en aquest ordre i sencers, abans de tocar res:
  1. CLAUDE.md
  2. DISSENY.md
  3. encarrecs/1B-comput-horari.md

Fes NOMÉS el que diu el teu encàrrec, escrivint NOMÉS els fitxers de la seva
llista de propietat. Quan acabis, executa la suite sencera i informa del
resultat real (si falla alguna cosa, digues-ho; no ho amaguis ni ho arreglis
tocant fitxers que no són teus).
```

---

## 5. Definició de FET (cap tasca s'accepta sense els sis punts)

1. **Els tests nous passen** i cobreixen: el camí feliç, cada error de domini
   amb el seu missatge, i els permisos (qui NO hi ha de poder accedir).
2. **La suite sencera passa.** Si un test d'un altre agent falla per culpa
   teva, no has acabat. Si falla per una cosa que no és teva, ho anotes a la
   teva incidència i ho dius.
3. **`git status` no mostra cap fitxer fora de la teva llista de propietat.**
   És la comprovació objectiva, i és la que fa qui integra abans d'acceptar.
4. **Tot en català**: codi, comentaris, missatges, interfície.
5. **Cap dada real** i cap dependència nova a `requirements.txt`.
6. **`incidencies/<ID>.md` escrit** si has trobat qualsevol cosa del contracte
   que no encaixa (encara que l'hagis pogut esquivar). Si no n'hi ha hagut cap,
   el fitxer no cal.

---

## 6. Portes d'integració

Al final de cada onada, qui integra fa aquesta seqüència. **No es passa a
l'onada següent sense superar-la.**

| # | Comprovació | Com |
|---|---|---|
| 1 | Suite verda sencera | `python -m pytest -q` |
| 2 | `core/` no importa flask ni res de Google | `grep -rn "import flask\|from flask\|google" core/` ha de sortir buit |
| 2b | Cap API de Google fora de l'adaptador | `grep -rln "google" --include=*.py . \| grep -v rebost_firestore` ha de sortir buit |
| 3 | Cap fitxer congelat modificat | `git diff --name-only <tag-onada-anterior>..HEAD` contrastat amb la llista |
| 4 | L'aplicació arrenca i el login funciona | `python app_web.py` i entrar amb un compte de prova |
| 5 | Incidències llegides i resoltes o assumides | `ls incidencies/` |
| 6 | `ESTAT.md` actualitzat i etiqueta de git | `git tag onada-N` |

Portes específiques per onada:

- **Onada 0**: l'app arrenca al 5004, els vuit blueprints hi són registrats i
  responen «en construcció», `/avis-legal` respon sense sessió, les capçaleres
  de seguretat hi són a totes les respostes i la base de dades es crea sola en
  arrencar. **Encara NO hi ha login**: l'autenticació és de l'onada 2, perquè
  necessita el magatzem de comptes (1A). Fins llavors, les fixtures `client` i
  `entra` de `conftest.py` no s'usen: l'onada 1 és domini pur i es prova sense
  servidor.
- **Onada 1**: `pytest tests/test_comput.py tests/test_fitxatge.py
  tests/test_regles.py tests/test_calendari.py tests/test_magatzem.py` verd, i
  `eines/dades_prova.py --recrea` genera una base de dades poblada.
- **Onada 2**: es pot entrar amb usuari i contrasenya, forçar el canvi
  inicial, activar el TOTP i tornar a entrar-hi; la PWA és instal·lable en
  local per HTTPS (o `localhost`); `docker compose up` aixeca l'aplicació.
- **Onada 3**: **prova d'extrem a extrem manual**: fitxar una entrada, una
  pausa, una sortida; veure el saldo del dia; demanar vacances amb un compte;
  aprovar-les amb un altre; comprovar que el dia surt cobert al resum d'hores.
- **Onada 4**: el registre de jornada s'exporta en CSV i PDF; la purga esborra
  el que toca i res més; l'auditoria no deixa cap punt vermell obert.
- **Onada 5**: un mòbil amb dades mòbils (no wifi de l'ajuntament) entra a
  l'URL pública, s'hi instal·la la PWA i fitxa.

---

## 7. Què fa un agent quan es bloqueja

Per ordre. **No saltis passos.**

1. **Rellegeix `DISSENY.md`.** El 90% dels dubtes hi són contestats.
2. **Si el contracte no ho cobreix**: pren la decisió **mínima i reversible**
   que et desbloquegi, i escriu-la a `incidencies/<ID>.md` amb aquest format:

   ```markdown
   ## [1B] minuts teòrics amb dues assignacions solapades
   **Què diu el contracte:** «guanya la de data_inici més recent» (§4.2)
   **Què hi falta:** què passa si tenen la mateixa data_inici.
   **Què he fet:** guanya la d'`id` més alt (l'última desada).
   **Cost de canviar-ho:** una línia a `core/comput.py`.
   ```

3. **Si el bloqueig és a un fitxer que no és teu**: **no el toquis**. Anota la
   incidència, fes tota la resta de la teva feina i informa'n en acabar. Qui
   integra ho resol o obre una tasca nova.
4. **Si el bloqueig és una decisió de producte o de compliment** (afegir un
   tipus d'absència, guardar una dada nova, canviar l'esquema): **atura't i
   pregunta**. Això no ho decideix cap agent.

---

## 8. Regles d'or

1. **No inventis interfícies.** Si una funció no és a `DISSENY.md` §4 o §5, no
   la cridis: o l'has d'escriure tu, o és d'un altre i encara no hi és.
2. **No refactoritzis codi que no és teu**, ni que sigui evidentment
   millorable. Anota-ho i segueix.
3. **No ampliïs l'abast.** Si l'encàrrec no ho demana, no ho facis. Les bones
   idees van a `incidencies/<ID>.md`, no al codi.
4. **No toquis `expedients-nomines-beta` ni `expedients-nomines-v2`.** Ni per
   llegir-hi dades. Copiar-ne codi i adaptar-lo, sí; escriure-hi, mai.
5. **Res de dades reals.** Ni per «provar-ho de veritat un moment».
6. **Informa del que ha passat de debò.** Si tres tests fallen, digues que en
   fallen tres. Un informe optimista costa una onada sencera de depuració.

---

## 9. Estat previst d'esforç

| Onada | Tasques | Agents alhora | Sessions estimades |
|---|---|---|---|
| 0 | 1 | 1 | 1 |
| 1 | 5 | 5 | 1-2 per agent |
| 2 | 4 | 4 | 1-2 per agent |
| 3 | 5 | 5 | 2 per agent |
| 4 | 4 | 3 (4B va sola) | 1-2 per agent |
| 5 | 3 | 1 + usuari | 2-4, depèn de tercers |

Camí crític real: `0A → 1A → 3D → 4C → 5B`. Tota la resta hi cap a sobre.

El que **no** controlem des d'aquí i pot allargar-ho tot: el vistiplau del DPD
per posar-hi dades reals, i el compte de facturació de Google Cloud. Totes
dues coses es poden tramitar **en paral·lel** a l'onada 1: comença-les el
primer dia (vegeu `encarrecs/4D-compliment-rgpd.md` i
`desplegament/FIREBASE.md` §1).
