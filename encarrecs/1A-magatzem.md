# Encàrrec 1A · Magatzem (repositoris sobre el port de documents)

**Onada 1** · Depèn de: 0A · Alhora que: 1B, 1C, 1D, 1E (no us toqueu res)
· **És el camí crític**: sense això, l'onada 3 no pot començar.

## Objectiu

Implementar els repositoris de `magatzem/`: l'única capa que sap on es desen
les dades. S'escriuen **una sola vegada**, contra el port de vuit operacions de
`magatzem/rebost.py`, i funcionen igual amb l'adaptador de memòria (proves) i
amb el de Firestore (producció).

## Escrius

```
magatzem/comptes.py     magatzem/marcatges.py    magatzem/absencies.py
magatzem/horaris.py     magatzem/festius.py      magatzem/parametres.py
magatzem/activitat.py
eines/dades_prova.py
tests/test_magatzem.py  tests/test_rebost.py     tests/integracio/*
```

**NO toques** `magatzem/rebost.py` ni `magatzem/rebost_firestore.py`: són el
contracte i estan congelats i provats.

## Llegeixes

`DISSENY.md` §3 sencer (model de documents, índexs, pressupost de lectures) i
**§5 sencer: les signatures són literals, no orientatives**.
`magatzem/rebost.py` (el port) i `core/model.py`.

## Feina

Implementa **totes** les funcions de `DISSENY.md` §5.2 amb el nom, els
arguments i el tipus de retorn exactes. Primer argument sempre `mag`.

### Regles transversals

- **Mai importis `google.cloud`.** Tu parles amb el port (`mag.doc()`,
  `mag.consulta()`, `mag.desa()`…) i prou. Si et cal una operació que no hi és,
  és una incidència, no un `import`.
- **Conversió de tipus a la frontera.** Els documents desen text ISO; les
  dataclasses porten `date`, `time` i `datetime` de debò. Fes-te `_a_data()` i
  `_a_moment()` privades i fes-les servir sempre. Tot `datetime` que surti ha
  de portar `tzinfo=UTC` explícit.
- **Cap regla de negoci aquí.** «Té prou dies?», «se solapa?» i «pot aprovar?»
  són de `core/`. `solapaments()` retorna les absències que se solapen; qui
  decideix què fer-ne és `core/`.

### Els sis punts on hi ha la dificultat

1. **`marcatges.afegeix()` és l'ÚNICA funció que escriu al llibre.** Amb
   `anul_la_id`, ha d'inserir el document nou **i** posar `anulat: true` a
   l'original **dins del mateix `mag.lot()`**: o totes dues escriptures o cap.
   Si l'original no existeix, ja està anul·lat o és d'un altre treballador,
   `ErrorHorari`.

2. **`marcatges.valida()` en REBUTJAR ha de tornar l'original a
   `anulat: false`.** Si no, el dia es queda sense cap marcatge vàlid i
   desapareixen hores d'una persona. És el punt més fàcil de fer malament de
   tot l'encàrrec; que tingui el seu test amb els minuts comparats abans i
   després.

3. **`absencies.crea()` treu el número de
   `mag.incrementa(COMPTADORS, f'absencies_{any}', 'n')`**, que és **atòmic al
   servidor**. Mai comptis documents per saber quin número toca: dues
   sol·licituds simultànies agafarien el mateix codi.

4. **`comptes.actualitza(mag, login, **camps)` amb LLISTA BLANCA.** Només
   `nom, correu, correu_norm, rol, servei_id, data_alta, data_baixa, actiu,
   canvi_pendent, hash_contrasenya, totp_secret, totp_actiu, ultim_acces,
   ambits, assignacions, codis_recuperacio`. Qualsevol altra clau,
   `ErrorHorari`. Mai passis directament el que arriba d'un formulari.

5. **`comptes.ambits_de()` retorna `list[str]`**, i `'*'`
   (`model.AMBIT_TOTS`) hi vol dir «tots els serveis». Els blueprints hi
   confiaran per decidir permisos: si t'equivoques aquí, s'obre un forat de
   seguretat. Que tingui test propi.

6. **`comptes.assignacions_de()` retorna `Assignacio` amb el `Patro` sencer a
   dins** (amb els seus `Tram`), ordenades per `data_inici`. Les assignacions
   viuen dins del document del treballador i els patrons són pocs: llegeix els
   patrons **una vegada** i reutilitza'ls, no un per assignació.

### El pressupost de lectures no és decoratiu

Cada document que retorna una consulta és una lectura facturada, i el nivell
gratuït en són 50.000 al dia. Abans d'escriure cada funció, mira `DISSENY.md`
§3.5 i pregunta't quantes lectures costa.

- `per_login` ha de ser **`mag.doc(TREBALLADORS, login)`**: una lectura
  directa, no una consulta amb filtre.
- `festius.del_any` ha de ser **una** lectura (tot l'any va en un document).
- `del_periode` filtra per `treballador_id ==` i un rang sobre `data`. **Mai
  dos rangs alhora** (Firestore no ho admet) i **mai una consulta sense filtre
  de treballador o de servei**.
- Cada consulta composta que escriguis ha de tenir el seu índex a
  `DISSENY.md` §3.3. **Si necessites una consulta que no hi és, és una
  incidència**: l'índex l'ha de declarar l'agent 2C i, sense declarar-lo, la
  consulta passa les teves proves (en memòria) i **falla en producció**.

### `tests/test_rebost.py` — la prova que tanca el risc del muntatge

Un **mateix** joc de proves, parametritzat amb `pytest.mark.parametrize`, que
corre contra `RebostMemoria` i contra `RebostFirestore`. El de Firestore
s'omet amb `pytest.skip` si no hi ha `FIRESTORE_EMULATOR_HOST`.

Ha de cobrir les vuit operacions i, sobretot, el que és fàcil que divergeixi:
document inexistent → `None`; `actualitza` sobre un document que no hi és →
error; els set operadors de filtre; ordenació ascendent i descendent;
documents als quals falta el camp d'ordenació; `limit`; `incrementa` des de
zero i concurrent; `lot()` que avorta i no escriu res; i que el que retorna una
lectura sigui una còpia (mutar-la no ha de canviar el que hi ha desat).

### `tests/integracio/`

Les mateixes proves de `test_magatzem.py`, però contra l'**emulador de
Firestore**. S'ometen senceres si no hi ha emulador. **No has d'instal·lar
res**: escriu-les i deixa-les preparades; qui les farà córrer és l'onada 5A,
que és quan s'instal·laran Node i Java. Deixa'n les instruccions al capdamunt
del fitxer.

### `eines/dades_prova.py`

Script de consola que pobla un magatzem amb dades **de mentida però
realistes**:

```
--recrea            buida i torna a poblar
--treballadors N    (defecte 24)
--mesos N           mesos de marcatges enrere (defecte 3)
--rebost memoria|firestore   (defecte: memoria)
```

Genera 3 serveis, N treballadors amb noms clarament inventats (`Treballador
01`…, correus `@exemple.cat`), un administrador i dos responsables, 2 patrons,
els festius de l'any, saldos, absències en tots els estats, i marcatges amb
variació realista (entrades entre les 7:45 i les 8:20, alguna jornada oberta
sense sortida, alguna pausa sense tancar) **perquè les anomalies de l'agent 1B
tinguin casos de prova de debò**.

**Cap nom, correu ni dada real. Cap.** I amb `--rebost firestore`, que demani
confirmació abans d'escriure: és l'única eina que podria tocar producció.

## Acceptació

- [ ] Totes les funcions de `DISSENY.md` §5.2 amb la signatura exacta.
- [ ] `grep -rn "google" magatzem/comptes.py magatzem/marcatges.py …` buit
      (cap import de Google fora de l'adaptador).
- [ ] Cap funció retorna un document cru: dataclasses o primitius.
- [ ] `tests/test_rebost.py` passa amb l'adaptador de memòria i està preparat
      per al de Firestore.
- [ ] `eines/dades_prova.py --recrea` funciona i l'aplicació hi arrenca.
- [ ] `pytest -q` verd, amb `tests/test_magatzem.py` cobrint: alta i lectura de
      cada entitat, l'anul·lació de marcatge amb la seva correcció, **el
      rebuig que restaura l'original**, la seqüència de codis d'absència, la
      llista blanca d'`actualitza`, i els àmbits amb `'*'`.
- [ ] Cada consulta composta que has escrit té el seu índex a `DISSENY.md`
      §3.3, o hi ha una incidència que ho digui.

## Proves

```bash
C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_magatzem.py tests/test_rebost.py -q
```

## Paranys

- **El teu codi passarà les proves en memòria i podria fallar a Firestore.**
  És el risc estructural d'aquest muntatge. Les dues coses que el disparen:
  una consulta amb dues desigualtats, i una consulta composta sense índex
  declarat. Revisa-les una per una abans de dir que has acabat.
- **`consulta()` sense filtres llegeix la col·lecció sencera.** Amb
  `marcatges` això són desenes de milers de lectures. No ho facis mai.
- **Els `datetime` sense `tzinfo` són una bomba de rellotgeria.** Tot el que
  surti de `moment` i `creat_el` ha de portar UTC explícit.
- **`servei_id` es duplica a `marcatges` i `absencies` a propòsit** (§3.2).
  Has d'omplir-lo en crear-los; si el deixes buit, les consultes per servei no
  trobaran res i les pantalles de gestió sortiran buides sense cap error.
