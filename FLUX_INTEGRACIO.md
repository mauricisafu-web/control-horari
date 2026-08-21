# FLUX_INTEGRACIO.md — Construir la integració amb nòmines en paral·lel

> Mateixa filosofia que `FLUX_DE_TREBALL.md`: **contracte abans que codi** i
> **propietat exclusiva de fitxers**, perquè diversos agents hi treballin
> alhora sense trepitjar-se.

## Contracte, ja congelat

Escrit i verificat abans de repartir res. **Cap agent el modifica.**

| Fitxer | Què hi ha |
|---|---|
| `core/format_importacio.py` | Columnes, `FilaImportada`, `Proposta`, `Pla`, accions |
| `core/importa.py` | Signatures i docstrings; els cossos els omple INT-A |
| `desplegament/INTEGRACIO_NOMINES.md` | El perquè de cada decisió |

Com que les signatures ja hi són, **els tres agents poden començar alhora**:
INT-C importa `core/importa.py` encara que els cossos no hi siguin.

## Les tres tasques

```
   INT-A  Analitzador          core/importa.py + proves          (pur)
   INT-B  Exportador           eines/exporta_des_de_nomines.py   (independent)
   INT-C  Pantalla de càrrega  web/ + templates/ + proves        (consumeix A)
              └── els tres alhora: cap escriu on escriu un altre
```

## Propietat de fitxers

| Tasca | Escriu (exclusiu) | Llegeix |
|---|---|---|
| **INT-A** | `core/importa.py`, `tests/test_importa.py` | `core/format_importacio.py`, `core/model.py` |
| **INT-B** | `eines/exporta_des_de_nomines.py`, `tests/test_exporta.py` | `core/format_importacio.py` |
| **INT-C** | `web/configuracio.py` (només hi AFEGEIX rutes), `templates/configuracio/importa.html`, `static/css/importa.css`, `tests/test_web_importa.py` | `core/importa.py`, `magatzem/comptes.py` |

**Fitxers congelats**: `core/format_importacio.py`, i tot el que ja ho era
(`core/model.py`, `magatzem/rebost.py`, `tests/conftest.py`).

## Ordre real

INT-A i INT-B no depenen de ningú. INT-C depèn del *comportament* d'INT-A,
però no de la seva existència: pot escriure la ruta i la plantilla i deixar
les proves preparades. Si INT-A encara no ha acabat, les proves d'INT-C
fallaran amb `NotImplementedError` — és l'esperat, i es tornen a passar quan
INT-A aterra.

## Definició de fet

Idèntica a `FLUX_DE_TREBALL.md` §5: proves noves verdes, suite sencera
verda, `git status` sense fitxers de fora de la llista, tot en català, cap
dada real, i incidències anotades a `incidencies/<ID>.md`.

**Recordatori que val per a tots**: `core/` no importa `flask`, ni
`magatzem`, ni res de Google. I **no es toca mai** `expedients-nomines-beta`:
se'n pot LLEGIR (l'xlsx, la configuració), mai escriure-hi.
