# Encàrrec 4A · Informes i purga per conservació

**Onada 4** · Depèn de: l'onada 3 sencera · Alhora que: 4C, 4D (no amb 4B)

## Objectiu

Dues obligacions legals que fins ara no té ningú assignades:

1. **Tenir el registre de jornada a disposició** dels treballadors, dels seus
   representants i de la Inspecció de Treball (art. 34.9 ET).
2. **No conservar les dades més enllà del termini** (art. 5.1.e RGPD).

> **Aquest és l'encàrrec que pot fer que l'aplicació deixi de ser gratuïta.**
> Un informe és, per naturalesa, la pantalla que llegeix més documents, i el
> nivell gratuït de Firestore són 50.000 lectures al dia. Llegeix
> `DISSENY.md` §3.5 abans de començar: hi ha un **límit de disseny** que has
> d'implementar, no només respectar.

## Escrius

```
web/informes.py            core/purga.py
templates/informes/index.html    static/css/informes.css
tests/test_informes.py     tests/test_purga.py
```

## Llegeixes

`DISSENY.md` §3.6 (taula de conservació), §3.5 (pressupost de lectures), §6.
De referència: la purga de `expedients-nomines-beta` (`MANTENIMENT.md` §1.6).

## Feina

### `/informes` — només `admin`

Formulari: treballador (o tots), període (des de / fins a), format (CSV o PDF).

**Límit dur, i s'ha d'aplicar al servidor** (no només amagar-ho al formulari):
una petició pot demanar **com a màxim un mes de tots els treballadors, o un
any d'un de sol**. Fora d'aquí, missatge en català que expliqui el límit i
proposi partir la consulta. Amb aquest límit, l'informe més car són ~2.000
lectures i arribar al límit diari és impossible en l'ús normal.

Ensenya a la pàgina, discretament, **quantes lectures costarà** la consulta
demanada abans de fer-la. No és per a l'usuari final: és per a qui manté
l'aplicació, i és el que farà que un problema de consum es vegi el primer dia
i no a la factura.

**CSV**: una fila per marcatge, amb capçalera en català, separador `;` i
codificació **UTF-8 amb BOM** (perquè l'Excel en castellà/català l'obri bé sense
que ningú hagi de fer res). Columnes: treballador, servei, data, hora local,
tipus, origen, estat, nota, qui l'ha creat.

**PDF** (`reportlab`): un full per treballador amb capçalera de l'ajuntament,
període, i la taula dia a dia amb entrades, sortides, hores fetes, hores
degudes i saldo; total del període al peu; i una línia de peu amb la data
d'expedició. És el document que es porta a una inspecció: ha de ser llegible i
complet, no maco.

També: **resum d'hores del conjunt** per al període (una fila per persona), en
pantalla i en CSV.

Registra `INFORME` a cada exportació, amb qui l'ha demanat i quin període.
L'accés al registre d'una altra persona és una acció que ha de deixar rastre.

### `core/purga.py`

```python
def purga(mag, avui=None, simulacio=True) -> dict
```

Esborra, segons `DISSENY.md` §3.6: marcatges i absències de més de 4 anys, i
anonimitza els comptes desactivats fa més d'1 any (login i nom substituïts per
`esborrat-<id>`, correu buit, **conservant els documents** perquè el registre
no quedi orfe).

**El log d'activitat NO és feina teva**: s'esborra sol amb la política TTL de
Firestore sobre el camp `caduca_el` (gratuïta, automàtica i sense codi; la
configura l'agent 2C). Si el purgues tu també, faràs lectures i escriptures
per no res.

Requisits:

- **`simulacio=True` per defecte**: retorna què esborraria sense esborrar res.
  El mode real és una decisió conscient.
- Retorna un diccionari amb els comptadors per col·lecció, que es registra al log.
- S'executa a l'arrencada **només si `PURGA_AUTOMATICA=1`** (desactivat per
  defecte). Fes la crida a `app_web.py`... **que no és teu**: exposa
  `purga.executa_si_toca(mag, config)` i anota a `incidencies/4A.md` que cal
  una línia a `crea_app`. Ho farà qui integra.
- **Mai esborra res de l'any en curs ni de l'anterior**, passi el que passi.
  Una salvaguarda contra un error de càlcul de dates que buidi el llibre.

## Acceptació

- [ ] El CSV s'obre bé a l'Excel amb accents i tot.
- [ ] El PDF d'una persona i un mes es genera i és llegible.
- [ ] Un `responsable` o un `treballador` que demani `/informes*` rep **403**.
- [ ] `purga(simulacio=True)` no toca res i informa correctament.
- [ ] `purga(simulacio=False)` esborra exactament el que ha dit la simulació.
- [ ] La salvaguarda dels dos últims anys funciona (prova-la donant-li una data
      «avui» absurda, com l'any 2100: no ha d'esborrar l'any en curs).
- [ ] `pytest -q` verd.

## Paranys

- **Un informe de tots els treballadors i d'un any sencer** no és lent: és
  **car**. Amb el límit dur implementat no pot passar; sense ell, unes quantes
  consultes com aquesta esgoten el nivell gratuït del dia i l'aplicació deixa
  de funcionar per a tothom. No et saltis el límit «per provar».
- **La purga esborra documents un per un i cada esborrat és una escriptura**
  (20.000/dia al nivell gratuït). Fes-la per lots amb un màxim per execució, i
  que pugui continuar on ho havia deixat el dia següent.
- **El PDF no ha de contenir cap dada que no calgui**: ni NIF, ni adreça, ni
  correu. Nom, servei i hores.
- **La purga és irreversible.** Que la prova de `simulacio=False` corri sempre
  sobre un `RebostMemoria` acabat de crear, mai contra Firestore.
- **Anonimitzar no és esborrar.** Els marcatges han de continuar existint amb
  el seu `treballador_id`: si els esborres, el llibre dels 4 anys queda coix i
  s'incompleix l'obligació que aquest encàrrec havia de complir.
