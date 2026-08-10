# DISSENY.md — Contracte tècnic de «Control horari»

> Aquest document és el **CONTRACTE** entre totes les peces i entre tots els
> agents. Qualsevol agent que hi treballi l'ha de llegir sencer abans de tocar
> res, juntament amb `CLAUDE.md`.
>
> **Cap agent modifica aquest fitxer.** Si el contracte és incoherent,
> incomplet o impossible, s'anota a `incidencies/<el-teu-id>.md` i s'aplica la
> solució mínima que et desbloquegi, deixant-ho escrit. Qui integra decideix.
>
> Versió del contracte: **1.0** (2026-08-05).

---

## 1. Decisions de producte

Preses per l'usuari (secretari-interventor) el 2026-08-05:

1. **Fitxatge real**: cada treballador registra entrada, sortida i pauses des
   del seu mòbil. És l'element nou respecte del mòdul de vacances que ja
   existeix a la beta de nòmines.
2. **Horari teòric** per treballador, amb vigències, per poder comparar hores
   fetes amb hores degudes i mantenir un **saldo horari**.
3. **Vacances i assumptes propis** amb saldos, prorrateig per alta i baixa, i
   aprovació per servei d'un sol nivell.
4. **Festius** generals, locals i propis; importables de les dades obertes de
   la Generalitat.
5. **Aplicació TOTALMENT independent.** No altera, no llegeix i no depèn de cap
   altra aplicació de l'usuari. `expedients-nomines-beta` i
   `expedients-nomines-v2` continuen exactament com estan; se'n pot **copiar
   codi provat** com a referència, però **cap agent hi escriu mai**, ni hi
   comparteix fitxers, ni comptes, ni configuració, ni magatzem. Si demà
   desapareguessin, aquesta aplicació continuaria funcionant igual.
6. **Cost zero.** Requisit dur de l'usuari: el desplegament no pot costar ni un
   euro. Tot el disseny s'hi subordina — vegeu §3.5 (pressupost de lectures) i
   `desplegament/FIREBASE.md` §2.
7. **Persistència en Firestore**, darrere d'un port intercanviable
   (§3 i §5). Es va valorar SQLite, però amb cost zero obliga a l'escalat a
   zero de Cloud Run, i llavors hi ha una finestra real de pèrdua dels últims
   marcatges: inacceptable per a un llibre de registre legalment exigible.
8. **Desplegament a Firebase** (detall a `desplegament/FIREBASE.md`).
9. **Res del NAS.** L'opció del NAS Synology queda descartada i no es
   contempla enlloc del projecte.

### Fora d'abast a la versió 1 (decisions conscients, no oblits)

| Fora d'abast | Per què |
|---|---|
| Fitxatge fora de línia amb cua al dispositiu | Desaria dades personals al mòbil i complicaria la fiabilitat de l'hora. Es documenta com a millora futura amb el seu propi encàrrec. |
| Geolocalització o biometria | Decisió de compliment (`CLAUDE.md`, regla 4). No s'implementa mai. |
| Permisos de salut, naixement, cura o violència de gènere | Entrarien a l'art. 9 RGPD i canviarien tota l'avaluació de riscos. |
| Quadrants de torns rotatius amb detecció de descoberts | L'usuari va triar l'opció sense quadrants. El model d'horaris hi és preparat (patrons + vigències) però no s'hi construeix la planificació. |
| Integració amb el programa de nòmines o amb l'ABSIS/CGAP | Aplicació independent. |

---

## 2. Rols i visibilitat

Tres rols, exclusius, al camp `treballador.rol`:

| Rol | Què veu i què pot fer |
|---|---|
| `treballador` | El seu fitxatge, el seu horari, les seves hores, les seves absències i el seu calendari. Res de ningú altre. |
| `responsable` | Tot l'anterior per a ell mateix, **més** el seu àmbit: aprova/denega absències, valida correccions de marcatge i consulta hores i calendari dels serveis que té assignats al camp `ambits`. |
| `admin` | Tot. **Únic** amb accés a `/configuracio*` i `/informes`. Sempre pot aprovar i validar de qualsevol servei. |

Regles invariables:

- **Ningú resol mai una sol·licitud pròpia**, ni sent `admin`. L'ha de resoldre
  un altre `responsable` amb àmbit o un altre `admin`.
- **Ningú valida mai una correcció de marcatge pròpia** feta per ell mateix,
  amb la mateixa lògica.
- Un `responsable` amb **`'*'`** (la constant `model.AMBIT_TOTS`) dins de
  `ambits` té àmbit sobre **tots** els serveis.
- Tot accés a una dada d'una altra persona passa per una comprovació d'àmbit
  explícita al blueprint. **No hi ha cap ruta que confiï en un identificador
  del formulari sense comprovar-ne la propietat o l'àmbit** (anti-IDOR).

---

## 3. Model de dades (Firestore)

Magatzem de **documents**, no relacional. S'hi accedeix **només** a través del
port de `magatzem/rebost.py` (vuit operacions), amb dos adaptadors:
`RebostMemoria` per a proves i desenvolupament, `RebostFirestore` per a
producció. **Ni `core/` ni `web/` saben que Firestore existeix.**

> Aquesta indirecció és el que fa que el projecte no quedi lligat a Google:
> sortir-ne seria escriure un tercer adaptador (SQLite, Postgres) i res més.

### 3.0 Les tres regles que expliquen tot el model

1. **Cada document que retorna una consulta és una lectura facturada.** El
   nivell gratuït permanent són **50.000 lectures i 20.000 escriptures al
   dia**. Amb 24 treballadors hi sobra molt marge, *però només si el model
   evita les consultes que arrosseguen col·leccions senceres*.
2. **Per això els identificadors són significatius**: el login, l'any, el
   codi de l'absència. Llegir un compte és una crida directa (1 lectura), no
   una consulta amb filtre.
3. **Per això s'agrupa el que sempre es llegeix junt**: els festius d'un any
   en un sol document, els saldos d'un treballador i any en un sol document,
   els trams dins del patró, i les assignacions d'horari i els àmbits
   d'aprovació dins del document del treballador.

### 3.1 Col·leccions

| Col·lecció | Identificador | Contingut |
|---|---|---|
| `parametres` | `config` (fix) | tots els paràmetres de l'aplicació en un document |
| `serveis` | automàtic | `nom`, `color` |
| `treballadors` | **el `login`** (immutable) | compte + fitxa + àmbits + assignacions |
| `festius` | **l'any** en text | `dies: {"AAAA-MM-DD": {nom, ambit}}` |
| `patrons` | automàtic | `nom`, `descripcio`, `trams: [...]` |
| `absencies` | **el codi** `A-2026-0001` | una sol·licitud |
| `saldos` | `<login>_<any>` | assignació anual de cada tipus |
| `marcatges` | automàtic | el llibre de registre (l'única que creix de debò) |
| `comptadors` | clau del comptador | seqüències atòmiques |
| `activitat` | automàtic | log d'activitat, amb caducitat automàtica |

### 3.2 Forma dels documents

```jsonc
// treballadors/{login}
{
  "login": "treb01", "nom": "…", "correu": "…",
  "correu_norm": "…",              // en minúscules: és per on es cerca
  "hash_contrasenya": "scrypt:…", "rol": "treballador",
  "servei_id": "…", "data_alta": "2023-01-01", "data_baixa": null,
  "actiu": true, "canvi_pendent": false,
  "totp_secret": null, "totp_actiu": false,
  "creat_el": "…Z", "ultim_acces": "…Z",
  "ambits": ["<serveiId>", …],     // buit si no és responsable; ["*"] = tots
  "assignacions": [ {"patro_id": "…", "data_inici": "…",
                     "data_fi": null, "coeficient": 100} ],
  "codis_recuperacio": [ {"hash": "…", "usat_el": null} ]
}

// patrons/{id}
{ "nom": "Oficines hivern", "descripcio": "…",
  "trams": [ {"dia_setmana": 1, "hora_inici": "08:00", "hora_fi": "15:00"}, … ] }

// festius/{any}
{ "any": 2026,
  "dies": { "2026-01-01": {"nom": "Cap d'Any", "ambit": "general"}, … } }

// saldos/{login}_{any}
{ "treballador_id": "treb01", "any": 2026, "vacances": 22, "assumptes_propis": 6 }

// absencies/{codi}
{ "codi": "A-2026-0001", "treballador_id": "treb01",
  "servei_id": "…",                // DESNORMALITZAT: vegeu la nota de sota
  "tipus": "vacances", "data_inici": "…", "data_fi": "…", "dies": 10,
  "estat": "PENDENT", "motiu": "", "creada_el": "…Z",
  "resolta_per": null, "resolta_el": null, "motiu_resolucio": "" }

// marcatges/{id}
{ "treballador_id": "treb01",
  "servei_id": "…",                // DESNORMALITZAT
  "moment": "2026-08-05T06:03:00Z",  // UTC
  "data": "2026-08-05",              // data LOCAL
  "tipus": "entrada", "origen": "web",
  "anul_la_id": null, "anulat": false, "estat": "VALID",
  "nota": "", "creat_el": "…Z", "creat_per": "treb01", "ip": "" }
```

**Per què `servei_id` es duplica a `absencies` i `marcatges`**: Firestore no fa
unions. Sense aquest camp, «dona'm les absències pendents del meu servei»
obligaria a llegir tots els treballadors del servei i després consultar-hi una
vegada per cadascun. Amb ell, és una consulta. **Contrapartida assumida**: si
algú canvia de servei, els documents antics conserven el servei que tenia
quan van passar les coses — cosa que, per a un registre històric, és
justament el que volem.

### 3.3 Índexs compostos (declarar-los a `firestore.indexes.json`)

Sense l'índex declarat, la consulta **falla en producció** (i funciona en
proves, perquè `RebostMemoria` no en necessita cap: és el parany més traïdor
d'aquest disseny). Els necessaris:

| Col·lecció | Camps |
|---|---|
| `marcatges` | `treballador_id` ASC, `data` ASC |
| `marcatges` | `servei_id` ASC, `data` ASC |
| `marcatges` | `servei_id` ASC, `estat` ASC |
| `absencies` | `treballador_id` ASC, `data_inici` ASC |
| `absencies` | `servei_id` ASC, `estat` ASC |
| `absencies` | `estat` ASC, `data_inici` ASC |

**Restricció de Firestore**: una consulta només pot tenir desigualtats sobre
**un** camp. Per això els marcatges es consulten sempre amb `treballador_id ==`
o `servei_id ==` més un rang sobre `data`, mai amb dos rangs.

### 3.4 Semàntica que la forma dels documents no diu

- **`moment` és sempre UTC** (`model.ara_utc()`), amb sufix `Z`. **`data` és la
  data LOCAL** d'`Europe/Madrid` d'aquell instant (`model.data_local()`),
  calculada en inserir. Així una jornada no es parteix pel canvi d'hora ni pel
  fus del contenidor.
- **Correccions.** Qui corregeix insereix un document nou amb `origen='manual'`,
  `anul_la_id` apuntant al corregit i `nota` amb el motiu; alhora, el corregit
  passa a `anulat: true`. **Les dues escriptures van dins d'un `lot()`**: o hi
  són totes dues o cap. Si qui corregeix és el mateix treballador, el document
  nou neix `estat='PENDENT_VALIDACIO'` i **no compta** fins que un responsable
  del seu àmbit el valida; si és un responsable o un admin, neix `VALID`.
- **Afegir un marcatge oblidat** és el mateix mecanisme sense `anul_la_id`.
- **Al còmput només hi entren** els documents amb `anulat: false` i
  `estat: 'VALID'` (`Marcatge.compta`).
- **`data_alta`/`data_baixa`** delimiten la relació laboral i disparen el
  prorrateig de vacances.
- **Els saldos desen l'ASSIGNACIÓ**; els dies gastats es calculen sempre com a
  suma de les absències `APROVADA`. Cap mutació de saldo en aprovar o anul·lar:
  idempotent i auditable.
- **Els codis d'absència** (`A-<any>-<seq>`) surten de
  `rebost.incrementa(COMPTADORS, f'absencies_{any}', 'n')`, que és **atòmic al
  servidor**. Mai de comptar documents.

### 3.5 Pressupost de lectures (comprovar-ho abans d'afegir cap pantalla)

| Operació | Lectures |
|---|---|
| Entrar i fitxar | ~4 (compte, festius de l'any, marcatges del dia, paràmetres) |
| El meu mes d'hores | ~90 (compte + festius + ~80 marcatges + absències) |
| Gestió d'un responsable | ~50 |
| **Informe d'un mes × 24 treballadors** | ~2.000 |
| Informe d'un any × 1 treballador | ~1.000 |

Amb 24 treballadors, l'ús diari normal ronda les **2.000-4.000 lectures**: un
5-8 % del nivell gratuït. **Límit de disseny (agent 4A)**: cap informe pot
demanar alhora més d'un mes de tots els treballadors o més d'un any d'un de
sol. Amb aquest límit, arribar a les 50.000 lectures diàries és impossible en
l'ús normal.

### 3.6 Conservació i purga

| Dada | Conservació | Base | Com |
|---|---|---|---|
| `marcatges` | **4 anys** | art. 34.9 ET | `core/purga.py`, amb simulació |
| `absencies` | 4 anys | prescripció laboral | `core/purga.py` |
| `activitat` | 1 any | minimització | **política TTL de Firestore**: automàtica, gratuïta i sense codi |
| Comptes de baixa | 1 any després de `data_baixa`, i llavors anonimització | minimització | `core/purga.py` |

El log d'activitat porta un camp `caduca_el` i s'esborra sol. Els marcatges i
les absències **no**: esborrar un llibre de registre legalment exigible ha de
ser una acció conscient i revisable, no un efecte secundari.


## 4. Contracte del domini (`core/`)

`core/` **no importa flask ni sqlite3**. Rep dataclasses, retorna dataclasses.

### 4.1 `core/model.py` — CONGELAT a l'onada 0

Conté, i només conté:

```python
# Constants
TIPUS_ABSENCIA = ('vacances', 'assumptes_propis', 'recuperacio')
ETIQUETA_TIPUS = {'vacances': 'Vacances',
                  'assumptes_propis': 'Assumptes propis',
                  'recuperacio': 'Recuperació d\'hores'}
PENDENT, APROVADA, DENEGADA, ANULADA = 'PENDENT', 'APROVADA', 'DENEGADA', 'ANULADA'
ENTRADA, SORTIDA, PAUSA_INICI, PAUSA_FI = 'entrada', 'sortida', 'pausa_inici', 'pausa_fi'
VALID, PENDENT_VALIDACIO, REBUTJAT = 'VALID', 'PENDENT_VALIDACIO', 'REBUTJAT'
ZONA = ZoneInfo('Europe/Madrid')

class ErrorHorari(Exception):
    """Error de domini amb missatge en català apte per a l'usuari."""

@dataclass(frozen=True)
class Treballador:
    id: int; login: str; nom: str; correu: str; rol: str
    servei_id: int | None; servei: str | None
    data_alta: date | None; data_baixa: date | None
    actiu: bool; totp_actiu: bool
    # propietats: es_admin, pot_aprovar

@dataclass(frozen=True)
class Tram:
    dia_setmana: int      # 1 = dilluns
    hora_inici: time
    hora_fi: time
    @property
    def minuts(self) -> int: ...

@dataclass(frozen=True)
class Patro:
    id: int; nom: str; trams: tuple[Tram, ...]

@dataclass(frozen=True)
class Assignacio:
    patro: Patro; data_inici: date; data_fi: date | None; coeficient: int

@dataclass(frozen=True)
class Marcatge:
    id: int; treballador_id: int
    moment: datetime      # amb tzinfo=UTC
    data: date            # data local
    tipus: str; origen: str; estat: str
    anulat: bool; anul_la_id: int | None
    nota: str; creat_per: int

@dataclass(frozen=True)
class Absencia:
    id: int; codi: str; treballador_id: int; tipus: str
    data_inici: date; data_fi: date; dies: int; estat: str
    motiu: str; creada_el: datetime
    resolta_per: int | None; resolta_el: datetime | None; motiu_resolucio: str

@dataclass(frozen=True)
class ResumDia:
    data: date
    minuts_teorics: int
    minuts_fets: int
    minuts_pausa: int
    minuts_absencia: int      # minuts teòrics coberts per absència aprovada
    saldo: int                # fets + absencia − teorics
    festiu: str | None
    absencia: str | None      # etiqueta del tipus, si n'hi ha
    anomalies: tuple[str, ...]
    marcatges: tuple[Marcatge, ...]

@dataclass(frozen=True)
class ResumPeriode:
    inici: date; fi: date
    minuts_teorics: int; minuts_fets: int; minuts_absencia: int; saldo: int
    dies: tuple[ResumDia, ...]

@dataclass(frozen=True)
class Saldo:
    tipus: str; any: int
    anual: int          # assignació anual sencera
    assignats: int      # després de prorratejar
    gastats: int
    pendents: int       # dies en sol·licituds PENDENT
    disponibles: int    # assignats − gastats  (pot ser NEGATIU: vegeu §4.3)
    prorratejat: bool
    dies_relacio: int
    baixa: bool
    a_liquidar: int

# Utilitats de temps (també part del contracte congelat)
def ara_utc() -> datetime          # instant actual en UTC, amb tzinfo, sense microsegons
def a_local(moment) -> datetime    # el mateix instant en hora d'Europe/Madrid
def data_local(moment) -> date     # la data LOCAL: és el valor de `marcatge.data`
```

**Ja escrit i verificat.** `core/model.py`, `magatzem/rebost.py`,
`magatzem/rebost_firestore.py` i `tests/conftest.py` existeixen, s'executen i
estan provats (els dos adaptadors amb la mateixa superfície, aïllament de les
còpies, lot atòmic que no escriu res si el bloc falla, comptador atòmic,
conversió UTC↔local correcta). Els agents hi construeixen a sobre; no els
reescriuen.

> **Parany ja resolt**: `zoneinfo.ZoneInfo('Europe/Madrid')` peta amb
> `ZoneInfoNotFoundError` tant a Windows com a les imatges `python:*-slim`,
> perquè cap de les dues porta la base de zones del sistema — i `core/model.py`
> la crida en importar-se, o sigui que l'aplicació **ni arrenca**. Per això
> **`tzdata` és una dependència obligatòria** del `requirements.txt` i **s'ha
> d'instal·lar també dins la imatge de Docker**.

### 4.2 `core/comput.py` — el cor del mòdul d'horaris

```python
def minuts_teorics_dia(data: date,
                       assignacions: Sequence[Assignacio],
                       festius: Mapping[date, str]) -> int:
    """Minuts que el treballador ha de fer aquell dia.

    0 si és festiu o si cap assignació hi és vigent. Altrament, la suma dels
    trams del patró vigent per al dia de la setmana, aplicant el coeficient
    (arrodonit a l'enter més proper). Si hi ha més d'una assignació vigent
    (solapament mal configurat), guanya la de `data_inici` més recent."""

def minuts_fets_dia(marcatges: Sequence[Marcatge]) -> tuple[int, int, tuple[str, ...]]:
    """(minuts_treballats, minuts_pausa, anomalies) d'un dia.

    Empella els marcatges VÀLIDS per ordre de `moment` i els aparella:
    entrada→sortida sumen presència; pausa_inici→pausa_fi resten. Els minuts
    treballats són presència − pausa, mai negatius.

    Anomalies detectades (cadenes en català, no excepcions — un dia rar es
    mostra, no peta):
      · 'sortida sense entrada prèvia'
      · 'jornada oberta: falta la sortida'
      · 'pausa sense tancar'
      · 'jornada de més de {jornada_maxima} h'
      · 'dos marcatges del mateix tipus seguits'
    """

def resum_dia(data, marcatges, assignacions, festius, absencies,
              jornada_maxima_minuts: int = 600) -> ResumDia: ...

def resum_periode(inici, fi, marcatges, assignacions, festius, absencies,
                  jornada_maxima_minuts: int = 600) -> ResumPeriode:
    """Recorre dia a dia. NO fa cap consulta: rep-ho tot precarregat."""

def formata_minuts(minuts: int) -> str:
    """-95 -> '−1 h 35 min'. Signe menys tipogràfic. Mai decimals."""
```

Regla del saldo diari: `saldo = minuts_fets + minuts_absencia − minuts_teorics`.
Una absència aprovada cobreix **exactament** els minuts teòrics del dia: qui té
vacances no acumula saldo ni el perd.

### 4.3 `core/regles.py` — absències

```python
def dies_habils(inici: date, fi: date, festius: Iterable[date]) -> int
def dies_de_relacio(any: int, alta: date | None, baixa: date | None) -> int
def arrodoneix_prorrata(valor: float) -> int
    """Criteri de l'Administració pública: fracció >= 0,4 amunt, < 0,4 avall.
    NO és el 0,5 habitual. 14,16 -> 14 ; 3,86 -> 4 ; 14,4 -> 15."""
def prorrata_saldo(assignacio_anual: int, dies_relacio: int) -> int
    """dies = dies_relacio * assignacio_anual / 365, arrodonit amb el criteri
    anterior. Sense alta ni baixa dins l'any, retorna l'assignació sencera."""
def calcula_saldo(...) -> Saldo
def valida_solicitud(...) -> None
    """Llança ErrorHorari amb missatge en català si:
       · data_fi < data_inici
       · la sol·licitud creua l'any natural (cal partir-la en dues)
       · dies > disponibles del tipus i l'any
       · se solapa amb una altra sol·licitud PENDENT o APROVADA del mateix
         treballador"""
def pot_resoldre(qui: Treballador, absencia: Absencia,
                 ambits: Sequence[int | None]) -> bool
    """Mai la pròpia, ni sent admin. admin sempre (llevat de la pròpia).
    responsable si té el servei del sol·licitant o si `'*'` és a `ambits`."""
```

**Saldo negatiu a propòsit.** Amb `data_baixa`, el tram meritat es retalla; si
la persona ja n'havia gaudit més, `disponibles` queda **negatiu** i no
s'arrodoneix a zero: són dies cobrats de més que s'han de descomptar a la
quitança. `Saldo.a_liquidar` ho expressa: > 0 dies pendents de compensar-li,
< 0 dies a descomptar, 0 quadrat.

### 4.4 `core/fitxatge.py` — màquina d'estats

```python
def estat_actual(marcatges_del_dia: Sequence[Marcatge]) -> str
    """'FORA' | 'DINS' | 'EN_PAUSA'"""

def accions_possibles(estat: str) -> tuple[str, ...]
    """FORA -> ('entrada',) ; DINS -> ('pausa_inici', 'sortida')
       EN_PAUSA -> ('pausa_fi',)
    La interfície NOMÉS ofereix aquestes accions: és impossible fitxar una
    sortida sense haver entrat."""

def valida_marcatge(tipus: str, moment: datetime,
                    marcatges_del_dia: Sequence[Marcatge],
                    minim_segons: int = 60) -> None
    """ErrorHorari si el tipus no és possible en l'estat actual, si el moment
    és anterior a l'últim marcatge, o si han passat menys de `minim_segons`
    des de l'últim (protecció contra el doble toc del mòbil)."""

def prepara_correccio(original: Marcatge | None, tipus: str, moment: datetime,
                      nota: str, autor: Treballador) -> dict
    """Retorna el diccionari de la fila nova (amb `anul_la_id`, `origen`,
    `estat` segons el rol de l'autor). No escriu res: qui escriu és
    `magatzem/marcatges.py`."""
```

### 4.5 Resta de `core/`

- `calendari.py`: `graella_mes(any, mes, esdeveniments) -> dict` amb
  `{'setmanes': [[{'dia', 'data', 'festiu', 'items': [...]}]]}`. Pura, sense
  HTML. La reutilitzen el calendari personal i el del servei.
- `festius.py`: `importa(any, codi_ine) -> list[tuple[date, str, str]]`. Única
  crida de xarxa de l'aplicació, sortint i a dades públiques
  (`analisi.transparenciacatalunya.cat`, datasets `8qnu-agns` generals i
  `b4eh-r8up` locals). Si falla, `ErrorHorari` amb missatge clar: l'alta manual
  sempre continua disponible.
- `comptes.py`: hash scrypt, generació de contrasenya provisional (CSPRNG, 14
  caràcters), política mínima, tokens signats de recuperació i d'alta.
- `totp.py`: secret, URI `otpauth://`, QR en SVG, verificació amb finestra ±1,
  codis de recuperació d'un sol ús.
- `notifica.py`: correus **fail-soft**. Cap flux de dades es bloqueja mai
  perquè l'SMTP falli: es desa, s'anota al log i es mostra un avís.
- `registre.py`: `registra(accio, usuari, detall='', ip='')` a
  `logs/activitat.log` rotatiu. Accions: `LOGIN`, `LOGIN_FALLIT`, `LOGOUT`,
  `FITXATGE`, `CORRECCIO`, `VALIDA_CORRECCIO`, `ABSENCIA_SOL`, `ABSENCIA_RESOL`,
  `ABSENCIA_ANULA`, `CONFIG`, `ALTA_COMPTE`, `CANVI_CONTRASENYA`, `TOTP`,
  `INFORME`, `PURGA`. **Mai** dades personals més enllà del login i l'id, mai
  secrets; text sanititzat contra injecció al log.

---

## 5. Contracte del magatzem (`magatzem/`)

Única capa que sap com es desen les dades. Rep i retorna dataclasses de
`core/model.py`; mai deixa sortir un document cru cap enfora.

### 5.1 El port — `magatzem/rebost.py` (JA ESCRIT, CONGELAT)

Vuit operacions, i cap més. Les implementen `RebostMemoria` (proves) i
`RebostFirestore` (producció), amb la **mateixa signatura exacta**.

```python
doc(colleccio, id) -> dict | None            # lectura directa; el dict porta 'id'
consulta(colleccio, filtres=(), ordre=None, descendent=False, limit=None) -> list[dict]
    # filtres: [(camp, operador, valor)]
    # operadors: '==' '<' '<=' '>' '>=' 'in' 'array_conte'
desa(colleccio, id, dades) -> None           # substitueix el document sencer
actualitza(colleccio, id, camps) -> None     # fusiona; error si no existeix
afegeix(colleccio, dades) -> str             # identificador automàtic
esborra(colleccio, id) -> None
incrementa(colleccio, id, camp, quantitat=1) -> int   # ATÒMIC
lot() -> Lot                                 # escriptures agrupades: totes o cap
```

També hi ha, al mateix fitxer: les constants de col·lecció (`TREBALLADORS`,
`MARCATGES`…), `obre_rebost(mena=None)` i `inicialitza(rebost)`.

**Limitació coneguda i acceptada**: `lot()` és un lot d'escriptures, no una
transacció amb lectura. Si dues persones modifiquen el mateix document alhora,
guanya l'última. Amb 24 treballadors això no passa; i on la correcció importa
de debò —els números de seqüència— hi ha `incrementa`, que sí que és atòmic.

**Si et cal una operació que no hi és, és una INCIDÈNCIA**: afegir-n'hi una vol
dir implementar-la bé als dos adaptadors i provar-la als dos.

### 5.2 Els repositoris (agent 1A)

S'escriuen **una sola vegada**, contra el port. Funcionen amb tots dos
adaptadors sense saber quin tenen a sota. Primer argument sempre `mag` (el
rebost).

```python
# magatzem/comptes.py
def per_login(mag, login) -> Treballador | None       # 1 lectura directa
def per_correu(mag, correu) -> Treballador | None     # consulta per correu_norm
def hash_de(mag, login) -> str | None
def llista(mag, actius=True, servei_id=None) -> list[Treballador]
def crea(mag, login, nom, correu, hash_contrasenya, rol, servei_id, data_alta) -> str
def actualitza(mag, login, **camps) -> None           # LLISTA BLANCA de camps
def desactiva(mag, login, data_baixa) -> None
def ambits_de(mag, login) -> list[str]   # conté '*' (AMBIT_TOTS) si els té tots
def desa_ambits(mag, login, serveis) -> None
def assignacions_de(mag, login) -> list[Assignacio]   # amb el Patro sencer
def assigna(mag, login, patro_id, data_inici, data_fi, coeficient) -> None
def desassigna(mag, login, index) -> None
def codis_recuperacio(mag, login) -> list[dict]
def desa_codis_recuperacio(mag, login, codis) -> None

# magatzem/marcatges.py
def del_dia(mag, login, data) -> list[Marcatge]
def del_periode(mag, login, inici, fi) -> list[Marcatge]
def del_periode_serveis(mag, serveis, inici, fi) -> dict[str, list[Marcatge]]
def afegeix(mag, login, tipus, moment, origen, creat_per, servei_id,
            ip='', nota='', anul_la_id=None, estat='VALID') -> str
    """L'ÚNICA funció que escriu al llibre. Amb `anul_la_id`, insereix el
    document nou I marca l'original `anulat` dins del MATEIX `lot()`."""
def valida(mag, marcatge_id, validador_login, accepta: bool) -> None
    """En rebutjar, torna a posar `anulat: false` a l'original: si no, el dia
    es quedaria sense cap marcatge vàlid i desapareixerien hores."""
def pendents_validacio(mag, serveis) -> list[Marcatge]
def purga(mag, abans_de: date) -> int

# magatzem/absencies.py
def de_treballador(mag, login, any=None) -> list[Absencia]
def pendents(mag, serveis) -> list[Absencia]
def aprovades_en(mag, inici, fi, serveis=None) -> list[Absencia]
def solapaments(mag, login, inici, fi, excloent=None) -> list[Absencia]
def solapaments_servei(mag, servei_id, inici, fi) -> list[tuple[Treballador, Absencia]]
def crea(mag, login, servei_id, tipus, inici, fi, dies, motiu) -> str  # el codi
def resol(mag, codi, estat, resolta_per, motiu) -> None
def anula(mag, codi, per_qui) -> None
def saldo_assignat(mag, login, any, tipus) -> int | None
def desa_saldo(mag, login, any, tipus, dies) -> None
def purga(mag, abans_de: date) -> int

# magatzem/horaris.py
def patrons(mag) -> list[Patro]
def patro(mag, id) -> Patro | None
def desa_patro(mag, nom, descripcio, trams, id=None) -> str
def elimina_patro(mag, id) -> None

# magatzem/festius.py
def del_any(mag, any) -> dict[date, str]     # 1 lectura per a tot l'any
def entre(mag, inici, fi) -> dict[date, str]
def afegeix(mag, data, nom, ambit) -> None
def elimina(mag, data) -> None
def fusiona(mag, festius) -> int             # dedupe per data; retorna els nous

# magatzem/parametres.py
def tots(mag) -> dict
def enter(mag, clau, defecte) -> int
def text(mag, clau, defecte='') -> str
def desa(mag, clau, valor) -> None

# magatzem/activitat.py
def registra(mag, accio, usuari='', detall='', ip='') -> None
    """Hi posa `caduca_el` a un any vista: la política TTL de Firestore
    l'esborra sola, sense codi i sense cost."""
def consulta(mag, desde=None, fins=None, usuari=None, limit=200) -> list[dict]
```

### 5.3 Regles del magatzem

- **Conversió de tipus a la frontera.** Els documents desen text ISO; les
  dataclasses porten `date`, `time` i `datetime` de debò. Dues funcions
  privades `_a_data()` i `_a_moment()`, i fer-les servir sempre. Tot
  `datetime` que en surti ha de portar `tzinfo=UTC` explícit.
- **Cap funció obre el magatzem**: el reben. Qui el crea és `app_web.py` (un
  per procés) o la fixture de proves.
- **`actualitza` amb llista blanca de camps.** Mai passar-hi directament el
  que arriba d'un formulari.
- **Cap regla de negoci aquí.** «Té prou dies?», «se solapa?» i «pot aprovar?»
  són de `core/`. `solapaments()` retorna les absències que se solapen; qui
  decideix què fer-ne és `core/`.
- **Cada consulta nova s'ha de contrastar amb §3.3 (índexs) i §3.5
  (pressupost de lectures).** Una consulta sense índex compost declarat passa
  les proves i falla en producció.


## 6. Rutes (`web/`)

Totes amb CSRF a cada POST i `@login_required` excepte les marcades.
Un blueprint per fitxer; el nom del blueprint és el del fitxer.

### `web/auth.py`  (blueprint `auth`, sense prefix)

| Ruta | Mètode | Qui | Què |
|---|---|---|---|
| `/login` | GET/POST | públic | usuari + contrasenya; límit d'intents per IP; sessió nova (anti-fixació) |
| `/login/totp` | GET/POST | sessió a mitges | segon factor |
| `/logout` | GET | amb sessió | tanca |
| `/canvia-contrasenya` | GET/POST | amb sessió | canvi propi; obligatori si `canvi_pendent` |
| `/recupera` | GET/POST | públic | envia enllaç signat al correu registrat |
| `/recupera/<token>` | GET/POST | públic | fixa contrasenya nova |
| `/totp` | GET | amb sessió | alta del segon factor (QR) |
| `/totp/confirma` | POST | amb sessió | verifica i activa |
| `/totp/regenera-codis` | POST | amb sessió | codis de recuperació nous |
| `/totp/desactiva` | POST | amb sessió | només si el rol no l'exigeix |
| `/avis-legal` | GET | **públic** | informació de l'art. 13 |

TOTP **obligatori** per a `admin` i `responsable`: mentre no el tinguin actiu,
un hook els confina a `/totp`. Per a `treballador` és opcional i recomanat.

### `web/fitxatge.py`  (blueprint `fitxatge`)

| Ruta | Mètode | Qui | Què |
|---|---|---|---|
| `/` | GET | tothom | **Pantalla principal**: rellotge, estat actual, botó gran amb l'única acció possible, resum del dia i saldo del mes |
| `/fitxa` | POST | tothom | registra el marcatge (valida amb `core.fitxatge`) i torna a `/` |
| `/marcatges` | GET | tothom | els meus marcatges del mes, amb anomalies marcades |
| `/marcatges/corregeix` | POST | tothom (els propis) | crea la correcció en estat `PENDENT_VALIDACIO` |

### `web/hores.py`  (blueprint `hores`)

| Ruta | Mètode | Qui | Què |
|---|---|---|---|
| `/hores` | GET | tothom | resum mensual propi: taula dia a dia, teòriques/fetes/saldo, saldo acumulat de l'any (`?any=&mes=`) |
| `/el-meu-horari` | GET | tothom | patró vigent, trams per dia i vigències |

### `web/absencies.py`  (blueprint `absencies`)

| Ruta | Mètode | Qui | Què |
|---|---|---|---|
| `/absencies` | GET | tothom | saldos per tipus i any + formulari + les meves sol·licituds + calendari personal (`?any=&mes=`) |
| `/absencies/solicita` | POST | tothom | valida, desa i avisa els responsables de l'àmbit |
| `/absencies/anula` | POST | propietari si PENDENT; responsable/admin si APROVADA | anul·la |

### `web/gestio.py`  (blueprint `gestio`)

| Ruta | Mètode | Qui | Què |
|---|---|---|---|
| `/gestio` | GET | responsable+admin | pendents del meu àmbit amb saldo i **avís de solapaments** del servei, correccions de marcatge pendents, i calendari general de l'àmbit |
| `/gestio/resol` | POST | responsable+admin (àmbit; mai la pròpia) | aprova/denega + correu al treballador |
| `/gestio/marcatge` | POST | responsable+admin | valida o rebutja una correcció |
| `/gestio/hores` | GET | responsable+admin | resum d'hores del servei per al mes (`?any=&mes=&servei=`) |

### `web/configuracio.py`  (blueprint `configuracio`, prefix `/configuracio`)

Només `admin`. Serveis, festius (manual + importació Gencat), patrons
d'horari i trams, assignacions per treballador, alta i baixa de comptes,
rols i àmbits d'aprovació, saldos anuals, paràmetres.

### `web/informes.py`  (blueprint `informes`, prefix `/informes`)

Només `admin`. Exportació del registre de jornada en **CSV** i en **PDF** per
treballador i període (obligació de tenir-lo a disposició de la Inspecció de
Treball i dels representants del personal), i resum d'hores del conjunt.

### `web/pwa.py`  (blueprint `pwa`, **sense** `login_required`)

`/manifest.webmanifest`, `/sw.js` (servit des de l'arrel perquè l'abast del
service worker sigui tot el lloc) i `/instal-lacio` (com instal·lar-la al mòbil,
amb captures pròpies o instruccions per Android i iOS).

---

## 7. Seguretat (obligatori a totes les respostes)

Implementat a `app_web.py` (onada 0) i no duplicat enlloc més:

- Capçaleres: `Content-Security-Policy: default-src 'self'; img-src 'self'
  data:; object-src 'none'; base-uri 'none'; form-action 'self';
  frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`,
  `Cache-Control: no-store` a tota resposta amb dades, i `Strict-Transport-
  Security` quan `COOKIE_SECURE=1`.
- Cookies `HttpOnly` + `SameSite=Lax` + `Secure` si `COOKIE_SECURE=1`.
- Sessió: caducitat per inactivitat (`SESSIO_MINUTS`, defecte 20 a producció).
- `ProxyFix` si `DARRERE_PROXY=1` (imprescindible darrere de Cloud Run per
  tenir la IP real al log i als límits d'intents).
- Límit d'intents de login per IP, amb poda del comptador.
- CSRF a tots els POST (Flask-WTF).
- El depurador **sempre desactivat** llevat de `FLASK_DEBUG=1` en local.
- **Comprovació d'origen**: en producció es rebutgen les peticions el `Host` de
  les quals no és el domini públic esperat (`DOMINI_PUBLIC`). Impedeix que
  algú entri per la URL directa de Cloud Run saltant-se Firebase Hosting.

---

## 8. Interfície i PWA

- Mòbil primer. Es dissenya a **375 px** d'amplada i s'eixampla; no al revés.
- La pantalla `/` és la raó de ser de la PWA: **un sol botó gran** amb l'acció
  que toca (`ENTRADA` / `PAUSA` / `SORTIDA`), l'hora en gran, i sota, discret,
  el resum del dia. Que un treballador de la brigada la pugui fer servir amb
  guants i amb sol.
- Objectiu d'accessibilitat: **WCAG 2.1 AA**. Contrast ≥ 4,5:1, àrees tàctils
  ≥ 44 px, `<label>` real a tot camp, focus visible, res que depengui només del
  color (els estats porten sempre text).
- Sense CDN i sense scripts inline (CSP). Un sol full `base.css` amb variables
  de color i un full per mòdul.
- Service worker: **només cacheja estàtics** (CSS, icones, manifest). **Cap
  resposta amb dades es desa mai** al dispositiu — el mòbil pot ser compartit o
  perdre's, i seria contradir el `Cache-Control: no-store` del servidor.
- Manifest amb `display: standalone`, `start_url: /`, `lang: ca`, icones 192 i
  512 (normals i maskable) i `shortcuts` per anar directe a fitxar.

---

## 9. Configuració (variables d'entorn)

| Variable | Defecte | Què fa |
|---|---|---|
| `REBOST` | `memoria` | `memoria` o `firestore`. **El defecte és memòria a propòsit**: cap prova ni cap sessió de desenvolupament pot tocar dades de veritat per descuit. El contenidor de producció el posa explícitament. |
| `PROJECTE_FIREBASE` | buit | identificador del projecte de Google (només amb `REBOST=firestore`) |
| `BASE_FIRESTORE` | `(default)` | nom de la base de dades de Firestore |
| `FIRESTORE_EMULATOR_HOST` | buit | si hi és, el client va a l'emulador local. **Només per a `tests/integracio/`** |
| `SECRET_KEY` | fitxer `.secret_key` | signatura de sessions |
| `COOKIE_SECURE` | `0` | cookies només per HTTPS + HSTS |
| `DARRERE_PROXY` | `0` | activa ProxyFix |
| `DOMINI_PUBLIC` | buit | si hi és, rebutja peticions amb un altre `Host` |
| `SESSIO_MINUTS` | `20` | caducitat per inactivitat |
| `TZ` | `Europe/Madrid` | zona del contenidor (el càlcul no hi confia) |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USUARI` `SMTP_PASSWORD` `SMTP_TLS` | — | correu; sense SMTP_HOST, els correus queden desactivats i s'anota al log |
| `PURGA_AUTOMATICA` | `0` | executa la purga per conservació a l'arrencada |
| `REGISTRE_OBERT` | `0` | permet l'autoregistre amb correu conegut (només durant l'alta inicial) |
| `FLASK_DEBUG` | `0` | només en local |

---

## 10. Proves

Les proves corren **sempre contra `RebostMemoria`**: instantànies, sense Node,
sense Java, sense emulador i sense connexió. Cap agent necessita res instal·lat
per començar, i cap prova pot tocar dades de veritat.

- `tests/conftest.py` (**ja escrit, congelat**) ofereix:
  - `magatzem` — magatzem en memòria poblat amb les dades sintètiques (3
    serveis, 6 comptes dels tres rols, un patró d'horari de 7 h, festius i
    saldos de l'any en curs).
  - `magatzem_buit` — només amb els paràmetres inicials, per a les proves
    d'alta des de zero.
  - `serveis`, `patro_id` — identificadors a mà.
  - `app`, `client` — aplicació Flask de proves sobre aquell magatzem.
  - `entra('treb01')` — deixa una sessió oberta.
  - `dies_habils_propers` — cinc dies hàbils a partir de demà.
- Cada agent escriu els seus tests al **seu** fitxer i hi posa les seves
  fixtures locals. **Ningú edita `conftest.py`** ni el fitxer de tests d'un altre.
- Cobertura mínima exigida per encàrrec: el camí feliç, cada error de domini
  amb el seu missatge, i els permisos (qui NO hi ha de poder).
- Tota funció de `core/` ha de tenir prova **sense servidor**.

### El risc d'aquest muntatge, i com es tanca

Provar contra memòria i desplegar contra Firestore vol dir que **una divergència
entre els dos adaptadors passaria les proves i petaria en producció**. El cas
real més probable: una consulta composta sense el seu índex declarat (§3.3),
que en memòria funciona i a Firestore falla.

Es tanca de dues maneres, totes dues obligatòries:

1. `tests/test_rebost.py` (agent 1A) prova **els dos adaptadors amb el mateix
   joc de proves**, parametritzat. El de Firestore s'omet si no hi ha emulador.
2. `tests/integracio/` (agent 1A) corre contra l'**emulador de Firestore** de
   debò i és una **porta de l'onada 5A**: no es desplega res sense haver-la
   passat. Necessita Node.js i Java, que ara mateix no hi ha a l'ordinador;
   instal·lar-los és part de l'onada 5A, no abans.

---

## 11. Desplegament (resum; el detall és a `desplegament/FIREBASE.md`)

```
Mòbil del treballador
   │ HTTPS
Firebase Hosting  (<projecte>.web.app, TLS automàtic, PWA instal·lable)
   │ rewrite "**"
Cloud Run  (regió UE, contenidor Flask + gunicorn)
   ├── min-instances = 0   ← escala a zero: fora de l'horari NO corre res
   ├── max-instances = 2     (Firestore no té el problema d'un sol escriptor)
   └── sense disc: tot l'estat és a Firestore
         │
Firestore (regió UE, mode natiu)
   └── còpia setmanal exportada FORA de Google
Secret Manager: SECRET_KEY, SMTP_PASSWORD (opcional)
```

**Cost: 0 €.** Tot cau dins del nivell gratuït permanent (no d'una prova de 90
dies): Cloud Run 2 M de peticions i 180.000 vCPU-segons al mes; Firestore
50.000 lectures, 20.000 escriptures i 1 GiB al dia; Hosting 10 GB de trànsit.
L'ús previst amb 24 treballadors és **un 5-8 %** del més ajustat d'aquests
límits (§3.5). Cal, això sí, un compte de facturació (pla Blaze) amb una
alerta de pressupost: vegeu `desplegament/FIREBASE.md` §2.

**Preu real d'escalar a zero**: la primera petició del dia triga entre 2 i 5
segons. Amb 24 persones que entren dues o tres vegades al dia, és assumible i
és el que fa que la factura sigui zero.

El contenidor **no sap que és a Firebase**: parla amb el port de
`magatzem/rebost.py` i prou. Sortir de Google seria escriure un tercer
adaptador (SQLite, Postgres) i canviar on es desplega — sense tocar `core/`
ni `web/`. Aquesta portabilitat és un requisit del disseny, no una casualitat.

**El NAS Synology no es contempla** en cap escenari d'aquest projecte.
