# Encàrrec 3D · Web de gestió (responsables i administradors)

**Onada 3** · Depèn de: 1A, 1B, 1C, 1D, 1E, 2A · Alhora que: 3A, 3B, 3C, 3E
· **És la tasca amb més control d'accés de tot el projecte.** Cada ruta d'aquí
ensenya o modifica dades d'altres persones.

## Objectiu

Que un responsable resolgui en una sola pantalla tot el que té pendent del seu
servei: absències per aprovar, correccions de marcatge per validar i una vista
de qui hi ha i qui no.

## Escrius

```
web/gestio.py                  templates/gestio/index.html
templates/gestio/hores.html    static/css/gestio.css
tests/test_web_gestio.py
```

## Llegeixes

`DISSENY.md` §2 (rols, i les tres regles invariables), §6 (blueprint `gestio`).
Tot `core/` i `magatzem/`.

## Feina

### Decorador d'accés, el primer que has d'escriure

```python
def cal_aprovar(f):
    """Exigeix rol 'admin' o 'responsable'. Qualsevol altre, 403."""
```

I una funció auxiliar que resolgui **una sola vegada per petició** els àmbits
de la persona (`magatzem.comptes.ambits_de`), amb la convenció que `'*'`
(`model.AMBIT_TOTS`) a la llista vol dir «tots els serveis» i que un `admin`
sempre els té tots. **Una sola vegada per petició**: resoldre'ls tres cops és
tres lectures del magatzem multiplicades per cada visita a la pàgina.

**Cada consulta d'aquesta pàgina es filtra per aquests àmbits.** No hi ha cap
excepció, ni per comoditat en el desenvolupament.

### `/gestio` (GET)

Tres blocs a la mateixa pàgina:

1. **Absències pendents del meu àmbit.** Per cadascuna: qui, tipus, dates,
   dies, motiu i **el saldo del sol·licitant** (perquè el responsable decideixi
   amb la informació al davant). I, molt important, **l'avís de solapaments**:
   qui més del mateix servei té absències aprovades o pendents que trepitgen
   aquestes dates. És el que evita quedar-se sense ningú a la brigada l'agost.
   Botons d'aprovar i denegar, amb un camp de motiu.
2. **Correccions de marcatge pendents de validar** del meu àmbit: qui, quin dia,
   quin marcatge original, quin de nou i la nota. Botons de validar i rebutjar.
3. **Calendari general de l'àmbit** (`?any=&mes=`), amb les absències de tothom
   del servei pintades per servei, amb la llegenda.

### `/gestio/resol` (POST)

`regles.pot_resoldre(qui, absencia, ambits)` **abans de res**. Fals → 403.
Recorda que això inclou **la pròpia sol·licitud, encara que siguis
administrador**. Després: `magatzem.absencies.resol`, registra `ABSENCIA_RESOL`,
`notifica.avisa_resolucio` al treballador (fail-soft).

Torna a comprovar el saldo en aprovar: entre la sol·licitud i l'aprovació poden
haver passat coses. Si ja no quadra, `flash` explicant-ho i no aprovis.

### `/gestio/marcatge` (POST)

`core.fitxatge.pot_validar(qui, marcatge)` → fals, 403. Inclou el cas de qui
vol validar una correcció que ha fet ell mateix. Després,
`magatzem.marcatges.valida`, registra `VALIDA_CORRECCIO`.

En **rebutjar**, la fila nova passa a `REBUTJAT` i **l'original torna a
`anulat = 0`**: si no, el dia es queda sense cap marcatge vàlid i les hores
d'aquella persona desapareixen. Aquest és el punt més fàcil de fer malament
de tot l'encàrrec.

### `/gestio/hores` (GET, `?any=&mes=&servei=`)

Taula d'una fila per treballador de l'àmbit: hores teòriques, fetes, absència,
saldo del mes i saldo acumulat de l'any, i una columna que compti les
incidències. Ordenable per saldo. Enllaç al detall de cada persona.

**Cost**: `magatzem.marcatges.del_periode_serveis` d'un sol cop, i després
`comput.resum_periode` per persona en memòria. **Res de consultes dins d'un
bucle de treballadors**: al magatzem de producció, cada document llegit compta
contra el límit gratuït diari (`DISSENY.md` §3.5). Una consulta per persona en
una taula de 24 files és la manera més fàcil de multiplicar el consum per 24.

## Acceptació

- [ ] Un `treballador` que demana qualsevol ruta de `/gestio*` rep **403**.
- [ ] Un `responsable` només veu i resol el **seu** servei; una absència d'un
      altre servei li dona 403 encara que en sàpiga l'identificador.
- [ ] Un `responsable` amb `'*'` als àmbits ho veu tot.
- [ ] **Ningú pot resoldre la seva pròpia sol·licitud**, ni sent `admin`.
      Prova-ho amb l'admin: és el cas que la gent es deixa.
- [ ] **Ningú pot validar una correcció que ha fet ell mateix.**
- [ ] Rebutjar una correcció **restaura** l'original i les hores del dia tornen
      a ser les d'abans. Prova-ho comparant els minuts abans i després.
- [ ] L'avís de solapaments detecta els casos del mateix servei.
- [ ] `pytest -q` verd.

## Paranys

- **L'identificador sempre ve del formulari.** Cada acció ha de tornar a
  carregar l'objecte de la base de dades i comprovar l'àmbit. No confiïs en
  cap camp amagat, ni en el que hagi ensenyat la pàgina anterior.
- **Rebutjar ≠ esborrar.** El llibre de registre no s'esborra mai: la fila
  rebutjada hi queda amb estat `REBUTJAT`, i l'original es reactiva.
- **Aprovar no ha de tocar cap saldo.** Els dies gastats es calculen sols. Si
  et veus escrivint a `saldo_absencia`, atura't.
- **El calendari general només per a l'àmbit.** Un responsable de Brigada no ha
  de veure les vacances d'Oficines.
- **No facis aquí la pantalla de configuració.** Serveis, festius, patrons i
  altes són de l'agent 3E.
