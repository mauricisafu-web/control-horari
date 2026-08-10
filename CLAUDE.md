# CLAUDE.md — Control horari · Ajuntament de la Torre de l'Espanyol

> **Llegeix aquest fitxer sencer abans de tocar res.** Si treballes com a agent
> d'una onada, llegeix també `DISSENY.md` (el contracte tècnic) i el teu
> encàrrec a `encarrecs/`. No comencis a escriure codi sense els tres.

## Què és això

Aplicació web **PWA** per al control de la jornada laboral dels ~24
treballadors de l'ajuntament:

1. **Fitxatge** (registre de jornada): entrada, sortida i pauses des del mòbil
   personal del treballador.
2. **Horari teòric**: patrons d'horari per servei i treballador, amb vigències
   (estiu/hivern, reduccions de jornada).
3. **Saldo horari**: hores fetes vs. hores degudes, per dia, mes i any.
4. **Vacances i assumptes propis**: sol·licitud, aprovació per servei, saldos
   amb prorrateig per alta i baixa.
5. **Festius**: calendari laboral (generals, locals i propis), importables de
   les dades obertes de la Generalitat.

Usuari propietari: el secretari-interventor. Els usuaris finals són
treballadors **no tècnics** que hi entraran des del mòbil. La interfície ha de
ser òbvia sense formació: la pantalla d'inici ha de tenir un botó gran que
digui què toca fitxar ara.

## ⚠️ REGLES CRÍTIQUES — NO LES SALTIS MAI

1. **Cap dada real en aquest repositori ni en cap context de Claude.** Ni
   noms, ni correus, ni NIF, ni credencials de l'ajuntament. Tot el
   desenvolupament i totes les proves es fan amb les dades sintètiques que
   genera `eines/dades_prova.py` (comptes `prova01`…, correus `@exemple.cat`).
   Que el codi corri en local no fa segur posar-hi dades reals: el model és al
   núvol i qualsevol fitxer que llegeixi hi viatja, **i també qualsevol dada
   que aparegui en pantalla durant una prova al navegador**.
2. **Aquesta aplicació és TOTALMENT independent de qualsevol altra.**
   Instrucció explícita de l'usuari. Vol dir les cinc coses alhora:
   - no importa cap mòdul de cap altre projecte en temps d'execució;
   - no llegeix ni escriu cap fitxer fora de la seva carpeta;
   - no comparteix magatzem, comptes, sessions ni configuració amb ningú;
   - **no modifica mai cap fitxer** de `expedients-nomines-beta` ni de
     `expedients-nomines-v2` (ni per «arreglar-hi» una cosa evident);
   - si aquelles carpetes desapareguessin demà, aquesta aplicació continuaria
     funcionant exactament igual.

   **Copiar codi provat d'allà i adaptar-lo és correcte i desitjable** —és
   codi que ja ha funcionat amb persones de debò—, però és una còpia, no una
   dependència. I aquesta aplicació **no toca mai nòmines ni factures**.
3. **Frontera de dades: cap categoria especial de l'art. 9 RGPD.** Els tipus
   d'absència són `vacances`, `assumptes_propis` i `recuperacio`. **No
   s'afegeixen mai** baixes mèdiques, IT, permisos per naixement, per cura ni
   per violència de gènere: entrarien a l'art. 9 i canviarien tota
   l'avaluació de riscos de l'aplicació exposada a Internet. Si el projecte
   ho arriba a necessitar, és una decisió de l'usuari i del DPD, mai d'un
   agent.
4. **Cap biometria i cap geolocalització al fitxatge.** És una decisió de
   disseny (criteri de l'AEPD sobre control horari) i un argument central
   davant del DPD: es registra QUAN, mai ON ni amb quin cos. No introdueixis
   `navigator.geolocation` ni cap empremta de dispositiu.
5. **Determinista i sense IA en temps d'execució.** Claude construeix i manté
   l'eina; l'eina no crida cap model. Cap dependència d'IA al `requirements.txt`.
6. **Cap CDN, cap script inline.** La CSP és `default-src 'self'` sense
   `unsafe-inline` per a scripts. Tot el CSS i el JS són fitxers propis servits
   des de `/static/`.
7. **Si detectes una incoherència del contracte, no la resolguis pel teu
   compte.** Escriu-la a `incidencies/<el-teu-id>.md` i aplica la solució
   mínima que et desbloquegi, deixant-ho anotat. Canviar `DISSENY.md`,
   l'esquema de la base de dades o `core/model.py` és competència de qui
   integra, no dels agents.

## Principis d'arquitectura

- **Server-rendered.** Flask + Jinja2. El JavaScript és mínim i opcional:
  l'aplicació ha de funcionar sencera sense JS (formularis POST normals). El
  JS només afegeix comoditat (registre del service worker, rellotge, confirmar
  accions).
- **Domini pur separat de la web.** `core/` NO importa `flask` mai. Són
  funcions i dataclasses pures, testejables sense servidor. `web/` només fa
  d'adaptador HTTP: llegir el formulari, cridar el domini, triar la plantilla.
- **`magatzem/` és l'única capa que sap on es desen les dades.** A sota hi ha
  un **port de vuit operacions** (`magatzem/rebost.py`) amb dos adaptadors:
  memòria per a proves i Firestore per a producció. `core/` i `web/` **no
  saben ni que Firestore existeix**, i cap crida a una API de Google pot
  aparèixer mai fora de `magatzem/rebost_firestore.py`. Això no és purisme:
  és el que fa que sortir de Google, si algun dia deixa de ser gratis, sigui
  escriure un tercer adaptador i res més.
- **Res derivat s'hi desa.** Els minuts fets, els minuts deguts, el saldo i els
  dies gastats de vacances **es calculen sempre** a partir dels fets registrats
  (marcatges, absències aprovades, festius, patró vigent). No hi ha cap taula
  de totals que es pugui desincronitzar. És més lent i és auditable: guanya
  l'auditable.
- **El registre de jornada és un llibre, no un formulari.** Una fila de
  `marcatge` no s'edita ni s'esborra mai. Una correcció insereix una fila nova
  que apunta a la corregida, amb autor i motiu. L'única escriptura permesa
  sobre una fila existent és marcar-la `anulat = 1`, i sempre acompanyada de la
  fila que la substitueix.
- **Blueprints, no monòlit.** Cada mòdul de la web és un blueprint en un fitxer
  propi. És el que permet que diversos agents hi treballin alhora sense
  trepitjar-se. (Diferència deliberada respecte de la beta de nòmines, on tot
  viu en un `app_web.py` de 168 KB que fa impossible el treball paral·lel.)

## Entorn

- **Carpeta de treball**: `C:\Users\secretari\control-horari`. Res fora d'aquí.
- **Python**: `C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe`
  (el `python` del PATH és un stub buit de la Microsoft Store i no funciona).
- **Port de desenvolupament**: **5004**. El 5002 i el 5003 són d'altres
  projectes de l'usuari; no els ocupis (és l'única relació que hi ha amb ells).
- **Magatzem en desenvolupament i en proves**: `REBOST=memoria` (el valor per
  defecte). **No cal instal·lar res**: ni Node, ni Java, ni emulador, ni
  connexió. Les dades es perden en aturar el procés, que és el que volem.
  `eines/dades_prova.py` en pobla un de nou amb dades sintètiques.
- **No et cal cap compte de Google per desenvolupar.** Firestore només entra
  en joc a l'onada 5.
- Ordres habituals:

```bash
C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q
```

```bash
C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe eines/dades_prova.py --recrea
```

```bash
C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe app_web.py
```

## Convencions

- **Codi, comentaris, docstrings, missatges i interfície en català.** Sense
  excepcions. Els noms de funcions i variables també (`minuts_teorics_dia`, no
  `theoretical_minutes`).
- Comentaris que expliquen **per què**, no què. Densitat: la del codi que
  t'envolta.
- Dates: **ISO** (`AAAA-MM-DD`) a la base de dades, als formularis i a les
  URL; **format català** (`dd/mm/aaaa`) a la vista. Hores: `HH:MM` sempre.
- Instants: es desen en **UTC** amb sufix `Z`; es mostren en hora local
  d'`Europe/Madrid` amb `zoneinfo`. Mai es confia en la zona del contenidor per
  al càlcul.
- Durades: sempre en **minuts enters**. Res de floats d'hores.
- Errors de domini: excepció `ErrorHorari` (a `core/model.py`) amb un missatge
  en català apte per ensenyar a l'usuari. La capa web els converteix en `flash`,
  mai en un 500.
- Escriptures: sempre dins d'una transacció; `PRAGMA foreign_keys = ON`.
- Tests: `pytest`, un fitxer per àrea, noms en català
  (`def test_saldo_negatiu_no_s_arrodoneix_a_zero()`).

## Estructura

```
app_web.py            factory Flask + registre de blueprints (CONGELAT a l'onada 0)
configuracio.py       lectura d'entorn i valors per defecte (CONGELAT)
core/                 domini pur — mai importa flask ni res de Google
  model.py            dataclasses, constants, ErrorHorari (CONGELAT: és el contracte)
  regles.py           dies hàbils, prorrateig, validacions d'absència
  comput.py           minuts teòrics/fets, saldo horari
  fitxatge.py         màquina d'estats dels marcatges
  calendari.py        graella mensual
  festius.py          importació de festius (dades obertes Gencat)
  comptes.py          contrasenyes, política, tokens
  totp.py             verificació en dos passos
  notifica.py         correus fail-soft
  registre.py         log d'activitat
magatzem/             única capa que sap on es desen les dades
  rebost.py           EL PORT: 8 operacions + adaptador de memòria (CONGELAT)
  rebost_firestore.py adaptador de producció (CONGELAT)
  comptes.py marcatges.py absencies.py horaris.py festius.py
  parametres.py activitat.py     ← escrits UNA vegada, contra el port
web/                  un blueprint per fitxer
  auth.py fitxatge.py absencies.py hores.py gestio.py configuracio.py
  informes.py pwa.py
templates/            base.html (CONGELAT) + una carpeta per mòdul
static/css/           base.css (CONGELAT) + un full per mòdul
static/js/            pwa.js i poc més
tests/                conftest.py (CONGELAT) + test_<àrea>.py
eines/                scripts de consola (dades de prova, gestió de comptes)
desplegament/         Dockerfile, firebase.json, regles i índexs de Firestore, guies
encarrecs/            un fitxer per tasca: el brief que es dona a cada agent
incidencies/          un fitxer per agent: on s'anoten els xocs amb el contracte
```

## Documents que manen

| Fitxer | Què hi ha | Qui el pot canviar |
|---|---|---|
| `DISSENY.md` | El contracte tècnic: model de dades, signatures, rutes, rols | Només qui integra |
| `FLUX_DE_TREBALL.md` | Onades, propietat de fitxers, protocol d'integració | Només qui integra |
| `ESTAT.md` | Taulell de progrés | Només qui integra |
| `encarrecs/*.md` | El brief de cada tasca | Només qui integra |
| `incidencies/<id>.md` | Xocs amb el contracte trobats per l'agent `<id>` | Només l'agent `<id>` |
| `desplegament/FIREBASE.md` | Disseny i passos del desplegament | Agent de desplegament |

## Cost zero — requisit dur

L'usuari ha posat com a condició que el desplegament **no costi ni un euro**.
Tot el disseny s'hi subordina i **tres coses no són negociables**:

1. **`min-instances = 0`** a Cloud Run (escala a zero). Una instància sempre
   encesa costaria 10-15 € al mes.
2. **El pressupost de lectures** de `DISSENY.md` §3.5. Cada pantalla nova s'hi
   ha de contrastar: el nivell gratuït de Firestore és de 50.000 lectures al
   dia i l'ús previst n'és un 5-8 %.
3. **Cap dependència de pagament**, cap servei extern nou, cap API de tercers
   fora de la importació de festius (dades obertes, gratuïta).

Si en algun moment el teu encàrrec sembla exigir sortir d'aquí, **atura't i
pregunta**: no és una decisió d'agent.

## Estat del compliment normatiu (llegir abans de posar-hi dades reals)

- L'allotjament és **Firebase / Google Cloud** per decisió de l'usuari
  (2026-08-05). Això fa Google **encarregat del tractament** (art. 28 RGPD):
  cal acceptar el DPA de Google Cloud, fixar la regió a la **UE** i
  actualitzar el RAT.
- **Cap dada real fins que el DPD ho autoritzi per escrit.** Tot el
  desplegament es prova i es valida amb dades sintètiques. Aquesta és la
  condició que permet que tota la feina tècnica avanci en paral·lel al tràmit.
- El registre de jornada revela presència diària: és més revelador que un
  saldo de vacances. Per compensar-ho, el disseny no recull ni ubicació ni
  biometria, i la conservació és de 4 anys amb purga automàtica.
