# Encàrrec 1C · Fitxatge (domini)

**Onada 1** · Depèn de: 0A · Alhora que: 1A, 1B, 1D, 1E

## Objectiu

`core/fitxatge.py`: la màquina d'estats que decideix **què pot fitxar una
persona en aquest moment** i que valida els marcatges abans de desar-los. És el
que fa impossible que algú registri una sortida sense haver entrat.

## Escrius

```
core/fitxatge.py     tests/test_fitxatge.py
```

## Llegeixes

`DISSENY.md` §4.4 (signatures) i §3.2 (mecànica de les correccions).
`core/model.py`.

## Feina

### `estat_actual(marcatges_del_dia) -> str`

`FORA`, `DINS` o `EN_PAUSA`, a partir dels marcatges **que compten**
(`.compta`), ordenats per `moment`. Sense cap marcatge, `FORA`.

### `accions_possibles(estat) -> tuple[str, ...]`

| Estat | Accions |
|---|---|
| `FORA` | `('entrada',)` |
| `DINS` | `('pausa_inici', 'sortida')` |
| `EN_PAUSA` | `('pausa_fi',)` |

L'ordre importa: la interfície ensenyarà la **primera** com a botó principal.
La pantalla de fitxatge només oferirà aquestes accions; la validació del punt
següent és la xarxa de seguretat, no l'única defensa.

### `valida_marcatge(tipus, moment, marcatges_del_dia, minim_segons=60)`

`ErrorHorari` amb missatge en català si:

- el tipus no és a `accions_possibles(estat_actual(...))` — missatge que digui
  què SÍ que es pot fer ara (p. ex. «Ara mateix constes com a fora. El que
  toca és fitxar l'entrada.»);
- `moment` és anterior o igual a l'últim marcatge del dia;
- han passat menys de `minim_segons` des de l'últim marcatge. **Aquest cas és
  el que passarà de debò**: el doble toc a la pantalla del mòbil. El missatge
  ha de ser tranquil·litzador, no acusatori: «Aquest fitxatge ja s'ha
  registrat fa un moment.»

### `prepara_correccio(original, tipus, moment, nota, autor) -> dict`

Retorna el **diccionari** de la fila nova, sense escriure res (qui escriu és
`magatzem/marcatges.afegeix`). Regles:

- `origen = 'manual'` sempre.
- `anul_la_id = original.id` si hi ha original; `None` si és un marcatge
  oblidat que s'afegeix de nou.
- **`estat`**: si `autor.pot_aprovar` → `VALID`; si és el mateix treballador
  corregint-se → `PENDENT_VALIDACIO`. Aquesta és la regla que fa que el
  registre de jornada sigui creïble davant d'una inspecció: ningú es canvia
  les hores tot sol sense que ho vegi ningú.
- `nota` obligatòria i no buida: `ErrorHorari` si ho és. Una correcció sense
  motiu no val res.
- **Un responsable no valida mai una correcció seva.** Aquí no ho pots
  comprovar (no saps qui validarà), però sí que has d'exposar
  `pot_validar(qui, marcatge) -> bool` perquè el blueprint 3D ho comprovi:
  `qui.id != marcatge.creat_per and qui.pot_aprovar`.

## Acceptació

- [ ] Les quatre funcions de `DISSENY.md` §4.4 més `pot_validar`.
- [ ] `grep -n "import flask\|magatzem\|google\|datetime.now" core/fitxatge.py` buit.
- [ ] `pytest tests/test_fitxatge.py -q` verd.

Cobertura mínima:

- les tres transicions d'estat, en cadena (entrada → pausa → represa →
  sortida) i cadascuna per separat;
- tots els casos de `valida_marcatge`, comprovant **el text** del missatge (que
  sigui en català i entenedor, no només que salti l'excepció);
- els marcatges anul·lats i els `PENDENT_VALIDACIO` **no** compten per a
  l'estat actual: si l'última entrada està pendent de validar, la persona
  continua constant com a `FORA`;
- `prepara_correccio` amb un treballador (→ `PENDENT_VALIDACIO`), amb un
  responsable (→ `VALID`), sense nota (→ `ErrorHorari`) i sense original;
- `pot_validar` amb el mateix autor (→ fals) i amb un altre responsable
  (→ cert).

## Paranys

- **Un dia amb dues jornades** (matí i tarda, amb sortida al mig) és normal a
  la brigada: `FORA` després de la primera sortida i `entrada` un altre cop.
  La màquina d'estats ho ha de permetre sense queixar-se.
- **La mitjanit no talla res aquí**: tu treballes sempre amb «els marcatges
  d'un dia» tal com te'ls donin. Qui decideix a quin dia pertany un instant és
  `model.data_local()`, i ja està fet.
- **No desis res.** Ni obris cap connexió. Si t'entra la temptació, és que
  estàs fent la feina de 1A o de 3A.
- **No inventis un estat `VACANCES`.** L'estat és només sobre el fitxatge; que
  una persona tingui vacances aprovades ho sap el còmput (1B), no tu.
