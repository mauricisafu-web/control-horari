# Encàrrec 1E · Calendari i festius

**Onada 1** · Depèn de: 0A · Alhora que: 1A, 1B, 1C, 1D

## Objectiu

Dues peces independents: la graella mensual que faran servir totes les
pantalles de calendari, i la importació de festius de les dades obertes de la
Generalitat.

> La importació **ja existeix provada** a
> `expedients-nomines-beta/core/vacances/festius_gencat.py`. Llegeix-la i
> adapta-la. **No escriguis res en aquella carpeta.**

## Escrius

```
core/calendari.py    core/festius.py
tests/test_calendari.py    tests/test_festius.py
```

## Llegeixes

`DISSENY.md` §4.5. `core/model.py`. De referència:
`expedients-nomines-beta/core/vacances/festius_gencat.py` i `calendari.py`.

## Feina

### `core/calendari.py` — `graella_mes(any, mes, esdeveniments) -> dict`

Estructura **pura**, sense una sola etiqueta HTML: qui pinta és la plantilla.

```python
{
  'any': 2026, 'mes': 8, 'nom_mes': 'agost',
  'mes_anterior': (2026, 7), 'mes_seguent': (2026, 9),
  'setmanes': [
     [ {'dia': 27, 'data': date(2026,7,27), 'del_mes': False,
        'festiu': None, 'cap_de_setmana': False, 'items': []},
       ... 7 caselles ... ],
     ...
  ]
}
```

- Setmanes de **dilluns a diumenge**, sempre 7 caselles; els dies d'abans i
  després del mes hi surten amb `del_mes: False` (perquè la graella no quedi
  coixa).
- `esdeveniments`: `dict[date, list[dict]]` que el mòdul rep ja fet i que
  col·loca a `items` sense mirar-ne el contingut. Així la mateixa funció
  serveix per al calendari personal (absències pròpies) i per al del servei
  (absències de tothom), que és exactament el que farem.
- `any` i `mes` invàlids (mes 13, mes 0, text) **no fan petar res**: cauen al
  mes actual. Aquesta funció rep paràmetres de la URL i qualsevol hi pot
  escriure el que vulgui.
- Fes servir `calendar.Calendar(firstweekday=0)` de la biblioteca estàndard;
  no reinventis el calendari.

### `core/festius.py` — `importa(any, codi_ine) -> list[tuple[date, str, str]]`

Retorna `(data, nom, àmbit)`, on l'àmbit és `'general'` o `'local'`.

- Festes generals de Catalunya: dataset `8qnu-agns` (12 l'any).
- Festes locals: dataset `b4eh-r8up`, filtrat per `codi_municipi_ine`
  (43152, la Torre de l'Espanyol; és un paràmetre de la base de dades,
  editable).
- Servidor: `analisi.transparenciacatalunya.cat`.

Aquesta és **l'única crida de xarxa de tota l'aplicació**. Per tant:

- Només **surt**, i només a dades públiques. S'hi envien un any i un codi INE:
  cap dada de ningú.
- **Temps màxim d'espera explícit** (10 s). Sense això, un servidor que no
  respon deixa penjada la pàgina de configuració.
- Si falla el que sigui —xarxa, format inesperat, dataset que canvia—,
  `ErrorHorari` amb un missatge clar que digui que l'alta manual continua
  disponible. **La importació és una comoditat, no una dependència**: si un
  dia la Generalitat canvia l'API, l'aplicació ha de continuar funcionant.
- `urllib.request` de la biblioteca estàndard. No afegeixis `requests` al
  `requirements.txt`.

## Acceptació

- [ ] `graella_mes` amb l'estructura exacta de dalt.
- [ ] `importa` amb temps màxim d'espera i `ErrorHorari` a tot error.
- [ ] `grep -n "import flask\|magatzem\|google" core/` (els teus dos fitxers) buit.
- [ ] `pytest tests/test_calendari.py tests/test_festius.py -q` verd.

Cobertura mínima del calendari: un mes que comença en dilluns i un que comença
en diumenge; un mes de 28, 30 i 31 dies; febrer d'un any de traspàs; paràmetres
invàlids (mes 0, mes 13, `'agost'`, `None`) que cauen al mes actual; els
`items` col·locats al dia correcte; totes les setmanes amb 7 caselles.

Cobertura mínima dels festius: **cap test no ha de sortir a Internet**. Injecta
la resposta (paràmetre opcional `obre_url` o `monkeypatch` sobre
`urllib.request.urlopen`) i prova: resposta bona → llista correcta; resposta
buida → llista buida sense petar; JSON invàlid → `ErrorHorari`; temps
d'espera exhaurit → `ErrorHorari`; codi INE inexistent → llista buida.

## Paranys

- **Un test que surt a Internet és un test que un dia fallarà** sense que
  ningú hagi tocat res, i que no funciona sense connexió. Injecta la resposta
  sempre.
- **Els noms dels camps dels datasets oberts canvien.** Sigues tolerant en
  llegir (`.get()` amb valor per defecte) i estricte en validar: si no hi ha
  data, salta l'entrada en lloc de fer petar la importació sencera.
- **Les dates arriben com a text** i de vegades amb hora (`2026-01-01T00:00:00`).
  Normalitza-les a `date`.
- **No desis res.** `importa()` retorna una llista; qui la fusiona amb la base
  de dades és `magatzem/festius.fusiona()`, de l'agent 1A.
