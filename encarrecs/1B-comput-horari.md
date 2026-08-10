# Encàrrec 1B · Còmput horari

**Onada 1** · Depèn de: 0A · Alhora que: 1A, 1C, 1D, 1E
· **És el cor de l'aplicació.** Si això està malament, tots els números que
veurà un treballador estaran malament.

## Objectiu

`core/comput.py`: donades les dades ja carregades, calcular quants minuts
havia de fer una persona, quants n'ha fet i quin saldo li queda. Funcions
**pures**: cap consulta, cap `datetime.now()`, cap flask.

## Escrius

```
core/comput.py     tests/test_comput.py
```

## Llegeixes

`DISSENY.md` §4.2 (signatures exactes) i §3.2 (semàntica de `moment`, `data` i
`compta`). `core/model.py`.

## Feina

Implementa amb les signatures literals de `DISSENY.md` §4.2:

### `minuts_teorics_dia(data, assignacions, festius) -> int`

- 0 si la data és a `festius`.
- 0 si cap assignació hi és vigent (`Assignacio.vigent_el`).
- Altrament: suma dels `Tram.minuts` del patró per al dia de la setmana
  (`data.isoweekday()`, 1 = dilluns), multiplicada pel coeficient i dividida
  per 100, **arrodonida a l'enter més proper**.
- Si hi ha més d'una assignació vigent (configuració dolenta), guanya la de
  `data_inici` més recent. Documenta-ho amb un comentari.

### `minuts_fets_dia(marcatges) -> (minuts, minuts_pausa, anomalies)`

El nucli. Ordena per `moment` **només els marcatges amb `.compta` cert** i
recorre'ls amb una màquina d'estats senzilla:

- `entrada` obre presència; `sortida` la tanca i suma.
- `pausa_inici` obre pausa; `pausa_fi` la tanca i suma a pausa.
- Minuts treballats = presència − pausa, **mai negatiu**.

Anomalies (cadenes en català, **mai excepcions**: un dia rar s'ha de mostrar,
no fer petar la pàgina):

| Situació | Text |
|---|---|
| `sortida` sense `entrada` oberta | `'sortida sense entrada prèvia'` |
| El dia acaba amb presència oberta | `'jornada oberta: falta la sortida'` |
| El dia acaba amb pausa oberta | `'pausa sense tancar'` |
| Presència > `jornada_maxima_minuts` | `'jornada de més de {h} h'` |
| Dos marcatges iguals seguits | `'dos marcatges del mateix tipus seguits'` |

Una jornada oberta **no** suma minuts fins a l'últim marcatge: suma 0 i marca
l'anomalia. Comptar fins a mitjanit inventaria hores que ningú ha fet.

### `resum_dia(...) -> ResumDia`

Ajunta-ho tot. `minuts_absencia` = els minuts teòrics del dia **si** hi ha una
absència `APROVADA` que el cobreix; si no, 0. `saldo = minuts_fets +
minuts_absencia − minuts_teorics`. Omple `festiu` i `absencia` (l'etiqueta de
`ETIQUETA_TIPUS`).

**Conseqüència volguda**: qui té vacances aprovades acaba el dia amb saldo 0.
Ni acumula ni perd. Que hi hagi una prova explícita d'això.

### `resum_periode(inici, fi, ...) -> ResumPeriode`

Dia a dia entre les dues dates incloses. **No consulta res**: rep-ho tot
precarregat i indexa'l en memòria (`dict[date, list[Marcatge]]`) abans del
bucle; si per a cada dia recorres la llista sencera de marcatges, un informe
anual de 24 persones s'arrossega.

### `formata_minuts(minuts) -> str`

`0 → '0 h 0 min'` · `95 → '1 h 35 min'` · `-95 → '−1 h 35 min'` (signe menys
tipogràfic U+2212, no un guionet). Mai decimals.

## Acceptació

- [ ] Les cinc funcions amb la signatura exacta de `DISSENY.md` §4.2.
- [ ] `grep -n "import flask\|magatzem\|google\|datetime.now" core/comput.py` buit.
- [ ] Cap funció fa cap consulta ni llegeix cap fitxer.
- [ ] `pytest tests/test_comput.py -q` verd.

Els tests han de cobrir, com a mínim:

- dia normal complet; dia amb pausa; dia festiu; dia sense assignació vigent;
- coeficient del 50 % (mitja jornada) i l'arrodoniment;
- **cada una de les cinc anomalies**, per separat;
- marcatges anul·lats i `PENDENT_VALIDACIO`: **no compten** (prova-ho, és el
  parany més fàcil de deixar-se);
- dia amb absència aprovada → saldo 0;
- dia amb absència **pendent** → NO cobreix res, saldo negatiu;
- un període que creua un canvi d'hora (l'últim diumenge de març i el
  d'octubre): els minuts han de sortir bé perquè els instants són UTC;
- un període d'un any amb dades sintètiques: ha de trigar menys d'un segon.

## Paranys

- **No facis servir `moment.hour`**: `moment` és UTC. Per a la presentació,
  `Marcatge.hora_local`. Per als càlculs de durada, resta els `datetime` UTC
  directament (`(b - a).total_seconds() / 60`), que és exacte i immune al canvi
  d'hora.
- **Un dia pot no tenir cap marcatge i tenir minuts teòrics**: és una absència
  injustificada, saldo negatiu. És correcte i s'ha de veure.
- **Els marcatges d'un dia poden estar desordenats** a la base de dades si algú
  n'ha afegit un a mà. Ordena sempre per `moment`.
- **No inventis toleràncies ni arrodoniments de cortesia** («si arriba amb
  menys de 5 minuts de retard, no compta»). Si això s'ha de fer, és una
  decisió de l'ajuntament amb el seu paràmetre; ara no hi és.
