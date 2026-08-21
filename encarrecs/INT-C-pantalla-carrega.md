# Encàrrec INT-C · Pantalla de càrrega de treballadors

**Alhora que**: INT-A i INT-B. Consumeixes `core/importa.py`, que ja té les
signatures congelades encara que els cossos els estigui fent INT-A.

## Objectiu

Que un administrador pugi el CSV, **vegi què passarà abans que passi**, i
apliqui només el que confirmi.

## Escrius

```
web/configuracio.py                      (només AFEGEIX rutes noves)
templates/configuracio/importa.html
static/css/importa.css
tests/test_web_importa.py
```

## Llegeixes

`core/importa.py` i `core/format_importacio.py` (contracte),
`magatzem/comptes.py`, `desplegament/INTEGRACIO_NOMINES.md`, i
`web/configuracio.py` per seguir-ne l'estil.

## Feina

Dues rutes noves, **totes dues amb `@cal_admin`**:

| Ruta | Mètode | Què |
|---|---|---|
| `/configuracio/importa` | GET | formulari per pujar el fitxer |
| `/configuracio/importa` | POST | previsualitza (`accio=previsualitza`) o aplica (`accio=aplica`) |

Enllaça-hi des de `templates/configuracio/comptes.html`... **que no és teu**:
anota-ho a `incidencies/INT-C.md` i ho farà qui integra.

### Previsualització

- Llegeix el fitxer pujat (`utf-8-sig`), crida `importa.analitza()` i
  `importa.calcula_pla()`.
- Ensenya quatre blocs: **crear**, **actualitzar**, **ja no surten al fitxer**
  i **errors**, amb el `detall` de cada proposta.
- Els que **ja no surten** porten cada un la seva **casella de selecció**,
  desmarcada per defecte. Al costat, ben visible: donar de baixa no esborra
  els marcatges.
- Perquè aplicar no hagi de tornar a pujar el fitxer, el contingut viatja en
  un camp amagat. **Límit de mida** (el mateix `MAX_CONTENT_LENGTH` de l'app).

### Aplicar

- Torna a analitzar i recalcular el pla: **no confiïs en res del formulari**
  més enllà de quines baixes s'han marcat.
- Crea els nous amb `comptes.crea()`, xifrant la contrasenya del fitxer amb
  `core.comptes.hash_contrasenya()`. Si una fila nova **no porta
  contrasenya**, genera-la amb `contrasenya_provisional()` i **ensenya-la un
  sol cop** a la pantalla de resultat, avisant que no es tornarà a mostrar.
- Actualitza els existents amb `comptes.actualitza()`.
- Dona de baixa **només** els que l'administrador hagi marcat, amb
  `comptes.desactiva()`.
- Registra `ALTA_COMPTE` i `CONFIG` amb els comptadors, **mai amb noms ni
  contrasenyes**.
- Ensenya un resum final: quants creats, actualitzats i donats de baixa.

## Acceptació

- [ ] Un `treballador` i un `responsable` que demanin `/configuracio/importa`
      reben **403**.
- [ ] La previsualització **no escriu res** al magatzem. Prova-ho comptant
      els comptes abans i després.
- [ ] Cap baixa s'aplica si no s'ha marcat la casella. **Aquesta prova és
      obligatòria.**
- [ ] Carregar dues vegades el mateix fitxer no duplica comptes (idempotent).
- [ ] Un fitxer amb una fila dolenta importa la resta i reporta l'error.
- [ ] Un fitxer que no és CSV, o buit, dona un avís en català, mai un 500.
- [ ] `pytest -q` verd (tota la suite).
- [ ] Les rutes noves s'han d'afegir a la matriu de `tests/test_web.py`, que
      **no és teu**: anota-ho a `incidencies/INT-C.md`.

## Paranys

- **Si `core/importa.py` encara llança `NotImplementedError`**, és que INT-A
  no ha acabat. Escriu igualment la ruta, la plantilla i les proves; digues
  al final que les proves queden pendents del seu aterratge.
- **La contrasenya del fitxer no es registra ni es mostra** si ja venia
  donada: només es xifra. La pantalla només ensenya les que hagi hagut de
  generar l'aplicació.
- **No toquis les rutes que ja hi ha** a `web/configuracio.py`: només
  n'afegeixes.
- El formulari de pujada necessita `enctype="multipart/form-data"`.
- Recorda que `web/configuracio.py` té una variable de mòdul
  `PARAMETRES_EDITABLES` i el decorador `cal_admin` ja importat: reutilitza'ls.
