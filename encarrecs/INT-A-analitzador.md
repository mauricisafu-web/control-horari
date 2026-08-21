# Encàrrec INT-A · Analitzador del fitxer d'importació

**Alhora que**: INT-B i INT-C. No depens de ningú.

## Objectiu

Omplir els cossos de `core/importa.py`: llegir el CSV i calcular què s'hi
faria. Funcions **pures**.

## Escrius

```
core/importa.py          (només els cossos: les signatures són contracte)
tests/test_importa.py
```

## Llegeixes

`core/format_importacio.py` (congelat), `core/model.py`,
`desplegament/INTEGRACIO_NOMINES.md`.

## Feina

### `normalitza_nom_servei(nom)`

Sense accents, minúscules, sense espais sobrers. `"  Oficines "` i
`"oficines"` han de ser la mateixa clau. Fes servir `unicodedata`.

### `analitza(contingut)`

`csv.DictReader` amb `;`. Retorna `(files_valides, errors)`.

- Si a la capçalera hi falta una columna **obligatòria**, és fatal: retorna
  `([], [una sola Proposta d'ERROR])` explicant quina falta.
- Una fila dolenta **no atura res**: es reporta i la resta continua.
- Errors de fila a detectar: usuari buit, nom buit, correu buit, correu
  repetit dins del mateix fitxer, usuari repetit dins del mateix fitxer, rol
  que no és dels tres vàlids, `data_alta` que no és `AAAA-MM-DD`.
- El `linia` de cada fila ha de ser el número REAL al fitxer (capçalera = 1),
  perquè l'usuari el pugui trobar.
- L'usuari es normalitza a minúscules i sense espais.

### `calcula_pla(files, existents, serveis, errors=())`

Per a cada fila:

| Situació | Acció |
|---|---|
| No hi ha compte amb aquell login | `CREAR` |
| Hi ha compte i canvia nom, servei, rol o data d'alta | `ACTUALITZAR` |
| Hi ha compte i tot igual | `SENSE_CANVIS` |
| El servei del fitxer no existeix | `ERROR` d'aquella fila |

I al final, per als comptes **actius** que són a `existents` i **no** al
fitxer: una proposta `BAIXA`.

`detall` ha d'explicar en català què canviarà, perquè es pugui ensenyar:
per exemple `servei: Oficines -> Brigada`. Per a `CREAR`, què es crearà.

**Un compte ja donat de baixa que torna a sortir al fitxer** és
`ACTUALITZAR`, i el `detall` ha de dir que es reactivarà.

## Acceptació

- [ ] Les tres funcions implementades, amb la signatura intacta.
- [ ] `grep -n "import flask\|magatzem\|google\|open(" core/importa.py` buit
      (no llegeix fitxers: rep text).
- [ ] `pytest tests/test_importa.py -q` verd.

Cobertura mínima: capçalera correcta; falta una columna obligatòria; fila
sense correu; correu duplicat al fitxer; rol inventat; data mal formada;
servei inexistent; creació; actualització amb cada camp per separat; sense
canvis; baixa proposada; reactivació d'un donat de baixa; fitxer buit;
fitxer amb només capçalera; i que els números de línia dels errors siguin
els reals.

## Paranys

- **`Pla` i les seves propietats ja existeixen**: no els reimplementis.
- **No proposis mai crear un servei** que no existeix: és `ERROR`.
- **La baixa és una proposta, no una acció.** Aquí només la calcules.
- **No llegeixis del disc**: `analitza` rep el contingut ja llegit. Qui obre
  el fitxer és la capa web.
