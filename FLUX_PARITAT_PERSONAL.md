# Flux · Portar el mòdul de Gestió de personal de nòmines al control horari

**Data:** 2026-08-21 · **Estat:** pendent d'executar

## Per què

Decisió de l'ajuntament: **el servidor municipal no ha d'intercanviar dades
per Internet**. Per tant les vacances i els permisos passen al control horari
(que és al núvol i accessible des de fora) i nòmines es queda en local amb
nòmines, factures i el correu.

El mòdul de Gestió de personal de `nòmines-beta` (`core/vacances/`,
1.433 línies + ~539 de rutes + 460 de plantilles, i **1.444 línies de proves
dedicades**) porta un any funcionant i fa coses que el control horari encara
no fa. Aquest document enumera **només les diferències reals**, verificades
llegint els dos codis, i l'ordre en què convé tancar-les.

**El que NO es porta**, i per què:

| | Motiu |
|---|---|
| Historial i repositori de nòmines | És la dada més sensible que teniu. Moure-la al núvol contradiu la decisió de dalt. Es queda a nòmines |
| Login amb T-CAT (certificat) | Necessita mTLS acabat a l'nginx de l'ajuntament. No té equivalent a Cloud Run sense muntar-hi infraestructura |
| Servei «Oficines» com a porta d'accés a Nòmines/Factures | Concepte propi de nòmines. Al control horari no hi ha res a què donar accés |
| Pany de fitxer interprocés (`pany_fitxer.py`, 163 línies) | Resol un problema que Firestore ja no té: les transaccions són atòmiques de sèrie |
| Autoregistre amb token | Amb la càrrega per CSV, les altes ja no es fan d'una en una. Queda com a opcional |

---

## Els buits, verificats

### 🔴 B1 · No surt cap correu de producció

**El més greu, i no és codi.** El servei desplegat a Cloud Run **no té cap
variable `SMTP_*` configurada**; ho he comprovat al servei. `core/notifica.py`
ho detecta i desactiva els avisos en silenci (anota `CORREU_DESACTIVAT` al
registre i continua).

Conseqüència d'avui: **ningú s'assabenta que té una sol·licitud per aprovar,
i ningú s'assabenta que li han resolt.** Tot el circuit depèn que la gent
entri a mirar-ho.

A nòmines això funciona des del primer dia (`core/vacances/notifica.py`,
fail-soft, avisa l'aprovador en sol·licitar i el treballador en resoldre).

**Decisió pendent teva.** Hi ha una tensió amb la decisió d'arquitectura:

- **(a) Donar SMTP al control horari.** Les credencials de correu de
  l'ajuntament acabarien a Secret Manager, al núvol. És la via directa però
  toca el principi que acabes de fixar.
- **(b) Que nòmines faci de passarel·la.** El control horari deixa els avisos
  pendents en una col·lecció i nòmines els recull i els envia. Respecta el
  principi, però nòmines hauria de **sortir a Internet a buscar-los**
  (connexió sortint a Firestore), que és precisament el que vols evitar.
- **(c) Deixar-ho sense correu** i que la gent hi entri. Funciona, però
  n'has de ser conscient: sense avisos, les sol·licituds s'encallen.

La (a) és la que menys friccions té i la que tota la resta del disseny ja
suposa. **Digues quina vols abans que ningú comenci per aquí.**

---

### 🟠 B2 · El calendari pinta absències en caps de setmana i festius

`web/absencies.py:60-66` i `web/gestio.py:95-101` recorren **tots** els dies
entre `data_inici` i `data_fi` i els marquen tots.

nòmines ho fa bé (`core/vacances/calendari.py`): marca **només els dies
hàbils no festius**, que són els que realment consumeixen saldo.

Efecte: unes vacances de dilluns a divendres de la setmana següent pinten
també el dissabte i el diumenge del mig, com si es gastessin. Confon en
mirar-ho i no quadra amb el nombre de dies que diu la sol·licitud.

**On es toca:** els dos bucles. La informació ja hi és a totes dues pantalles
(`festius.del_any` / `festius.entre` ja es consulten).

---

### 🟠 B3 · El calendari de gestió amaga les sol·licituds pendents

`magatzem/absencies.py:65` (`aprovades_en`) filtra **només `APROVADA`**.
nòmines hi pinta `PENDENT` **i** `APROVADA`.

Efecte: l'aprovador obre el calendari del seu servei per decidir i **no veu
les altres sol·licituds que encara no ha resolt**. Justament la informació que
li cal per no aprovar-ne dues que es trepitgen.

L'avís de solapament sí que hi és a la fitxa de cada pendent (`solapaments_servei`),
o sigui que la dada s'obté; el que falla és que el calendari no la pinta.

**On es toca:** `aprovades_en` (o una germana `visibles_en`) i la crida de
`web/gestio.py`. La plantilla `_calendari.html` **ja distingeix** l'estat
pendent amb la classe `cal-pendent`: està preparada i no s'usa.

---

### 🟡 B4 · No hi ha màquina d'estats

`magatzem/absencies.py:136` (`anula`) només bloqueja el que ja està anul·lat.
Una sol·licitud **DENEGADA es pot anul·lar**, cosa que no vol dir res.

nòmines té la taula explícita a `core/vacances/model.py`:

```python
TRANSICIONS = {
    PENDENT:  frozenset({APROVADA, DENEGADA, ANULADA}),
    APROVADA: frozenset({ANULADA}),
    DENEGADA: frozenset(),      # final
    ANULADA:  frozenset(),      # final
}
```

**On es toca:** portar la taula a `core/model.py`, una funció
`valida_transicio()` a `core/regles.py`, i cridar-la des de `resol()` i
`anula()`.

---

### 🟡 B5 · El calendari general no diu de qui és cada absència

Ara pinta el **nom de pila** i prou (`treballador.nom.split()[0]`).

nòmines hi porta `usuari, nom, servei, tipus, estat`, ordena per
`(servei, nom, usuari)` i la plantilla **acoloreix per servei amb llegenda**
(`vacances_gestio.html:137,151`).

Amb tres serveis i ~25 persones la diferència es nota: d'un cop d'ull veus si
la Brigada s'ha quedat sense ningú.

---

### 🟢 B6 · Sense autoregistre (opcional)

nòmines té alta per token (`/registre`, `/registre/<token>`): el treballador
tria usuari, contrasenya i servei.

El control horari ho resol per l'altre costat, amb la **càrrega massiva per
CSV**, que per a una alta de 25 persones de cop és millor. Ho deixo apuntat
per si mai voleu que algú es doni d'alta sol; **no ho faria ara**.

---

## El que el control horari ja fa igual o millor

Perquè quedi clar què **no** cal tocar:

- **Prorrata de saldos**: idèntica, i amb el mateix criteri d'arrodoniment de
  l'Administració (fracció ≥ 0,4 amunt). Prorrateja per alta **i per baixa**,
  i deixa el disponible **negatiu** a propòsit quan s'han gaudit dies de més,
  amb `a_liquidar` per a la quitança. Paritat completa.
- **Saldo desat per any i per tipus**, amb valor per defecte de configuració.
- **Validació de sol·licituds**: mateix any natural, cap dia hàbil, solapaments,
  saldo insuficient. Mateixos missatges i mateix fons.
- **Ningú resol la seva pròpia sol·licitud, ni sent administrador.**
- **Aprovació per àmbit de servei**, amb `*` per a tots.
- **Importació de festius de la Generalitat** + alta manual.
- **Purga per retenció**, i la del control horari està ancorada a la data real
  del sistema (no a la que se li passi), que és més robusta.
- **Registre d'auditoria** a cada operació.
- **PWA instal·lable**: les dues la tenen, i amb la mateixa regla de no
  cachejar mai pàgines amb dades.

I el que només té el control horari: **càrrega massiva per CSV**,
**arquitectura separable** (port/adaptador, un blueprint per fitxer, contra un
`app_web.py` de 3.700+ línies), i **accés real des de fora**.

---

## Ordre d'execució

Tres onades. Dins de cada onada, els encàrrecs no es trepitgen i es poden
repartir; entre onades, sí que hi ha ordre.

### Onada 1 · Que el circuit es tanqui

| | Encàrrec | Fitxers | Depèn de |
|---|---|---|---|
| **P0** | **Decidir B1** (correu) i aplicar-ho | configuració de Cloud Run, o disseny nou | **tu** |
| **P1** | B4 · màquina d'estats | `core/model.py`, `core/regles.py`, `magatzem/absencies.py` | — |

`P1` no depèn de `P0` i es pot començar ja.

### Onada 2 · Que el calendari digui la veritat

| | Encàrrec | Fitxers | Depèn de |
|---|---|---|---|
| **P2** | B2 · no marcar caps de setmana ni festius | `web/absencies.py`, `web/gestio.py` (o millor: una funció compartida a `core/calendari.py`) | — |
| **P3** | B3 · pintar també les pendents | `magatzem/absencies.py`, `web/gestio.py` | — |

`P2` i `P3` toquen el mateix bucle de `web/gestio.py`: **fes-los seguits, no
en paral·lel**, o resol-los amb un sol encàrrec.

### Onada 3 · Acabats

| | Encàrrec | Fitxers | Depèn de |
|---|---|---|---|
| **P4** | B5 · servei, tipus i colors al calendari general | `web/gestio.py`, `templates/_calendari.html`, `static/css/base.css` | P3 |

---

## Regles per a qui ho executi

1. **Cada encàrrec porta les seves proves.** El mòdul de nòmines té 1.444
   línies de proves dedicades; les d'aquí han de tenir el mateix nivell. Per a
   B2 i B3 concretament: una prova que agafi unes vacances **que travessin un
   cap de setmana** i comprovi que dissabte i diumenge queden nets, i una que
   comprovi que una PENDENT surt al calendari de gestió.

2. **Mira't la prova de nòmines abans d'escriure la teva.**
   `tests/test_vacances_calendari.py` (113 línies) i `test_vacances.py` (583)
   ja tenen els casos frontera pensats. Copia'ls d'idea, no de codi.

3. **Res del que es porti pot dependre de `dades_vacances.json`**, de fitxers
   locals ni de l'SMTP de l'ajuntament. El control horari ha de continuar
   arrencant amb `REBOST=memoria` i sense cap servei extern.

4. **No tocar mai cap fitxer de `expedients-nomines-beta` ni de
   `expedients-nomines-v2`** (regla 2 del `CLAUDE.md`). Llegir-ne el codi per
   copiar-ne les idees, sí; escriure-hi, mai.

5. **Els tipus d'absència segueixen sent `vacances` i `assumptes_propis`.**
   Res que sigui categoria especial de l'article 9 del RGPD (regla 3).

---

## El que continua obert i no és feina de codi

- **El DPD.** nòmines té vistiplau del 2026-07-21 per sortir a Internet, però
  per un camí que **descartava explícitament** que un tercer acabés el TLS
  (opció D del seu `ACCES_ONLINE_PERSONAL.md`, art. 28 RGPD) — que és el que
  fa Google al control horari. L'anàlisi ja està escrita; adaptar-la és molt
  menys feina que fer-la de zero.
- **Congelar el mòdul de nòmines** quan el control horari agafi el relleu, per
  no acabar amb dos calendaris i dos saldos que divergeixen. La manera menys
  agressiva: treure'n l'enllaç del menú i deixar-hi un avís amb l'adreça nova.
- **Migrar les dades que ja hi hagi** a `dades_vacances.json` (sol·licituds
  històriques i saldos). Ara mateix hi ha **1 treballador**, o sigui que és
  barat; si algú hi entra dades abans de decidir-ho, deixarà de ser-ho.
