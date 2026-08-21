# Integració amb l'aplicació de nòmines

> Com es creen i es mantenen els comptes del control horari a partir de la
> llista de treballadors que gestiona l'aplicació de nòmines.
>
> Decidit amb l'usuari el 2026-08-20. Substitueix l'alta manual un per un de
> `/configuracio/comptes`, que es manté per als casos solts.

---

## Principi: un fitxer, una direcció

```
   App de NÒMINES (local, PC de l'ajuntament)
     · sap qui està d'alta
     · sap les dates d'alta
     · JA TÉ l'SMTP configurat
     · genera la contrasenya provisional
     · ENVIA el correu a cada treballador
             │
             │   fitxer  treballadors-AAAA-MM-DD.csv
             ▼
   CONTROL HORARI (Cloud Run)
     · rep el fitxer, en fa una PREVISUALITZACIÓ
     · crea/actualitza comptes
     · xifra la contrasenya rebuda i marca `canvi_pendent`
     · NO envia cap correu, NO retorna cap contrasenya
```

**Per què en una sola direcció.** Si el control horari generés les
contrasenyes, hauria de tornar-les d'alguna manera a nòmines per poder-les
enviar: un segon fitxer amb contrasenyes en clar sortint de Google. Generant-
les a nòmines, això desapareix: la contrasenya neix i s'envia des del PC de
l'ajuntament, i al núvol només hi arriba per ser xifrada immediatament.

**Conseqüència volguda:** el control horari desplegat **no necessita SMTP**.
Les credencials de correu de l'ajuntament no viatgen mai a Google.

## Per què no una API entre les dues aplicacions

Es va valorar i es descarta. L'aplicació de nòmines corre **en local**, sense
adreça pública; el control horari corre a Cloud Run. Perquè es poguessin
parlar caldria exposar la de nòmines a Internet, que és precisament el que es
va descartar el 2026-08-05 perquè aquella màquina té les nòmines a dins.

Tampoc no s'escull que nòmines escrigui directament a Firestore: obligaria a
posar credencials de Google al PC de nòmines i trencaria la independència
entre les dues aplicacions.

---

## Format del fitxer

CSV amb `;` i UTF-8 amb BOM (el mateix criteri que els informes, perquè
l'Excel l'obri bé). Capçalera obligatòria:

| Columna | Obligatòria | Notes |
|---|---|---|
| `usuari` | sí | minúscules, només lletres. El genera nòmines |
| `nom` | sí | nom i cognoms |
| `correu` | sí | ha de ser únic |
| `servei` | no | nom del servei tal com és al control horari. Buit = no es toca |
| `rol` | no | `treballador` (defecte), `responsable` o `admin` |
| `data_alta` | no | `AAAA-MM-DD`. Dispara el prorrateig de vacances |
| `contrasenya` | només per als nous | la provisional que nòmines ha enviat per correu |

**La columna `contrasenya` només es fa servir per als comptes NOUS.** Per als
que ja existeixen s'ignora sempre: una càrrega no pot canviar la contrasenya
de ningú que ja estigui fent servir l'aplicació.

---

## Què fa la càrrega

Pantalla nova a `/configuracio/comptes`: **«Carrega treballadors des d'un
fitxer»**. Sempre en dos passos.

### Pas 1 — Previsualització (no toca res)

| Situació | Què proposa |
|---|---|
| Al fitxer, no a l'app | **Crear** el compte |
| Als dos llocs, amb canvis | **Actualitzar** nom, servei, rol o data d'alta |
| Als dos llocs, igual | No fer res |
| A l'app, no al fitxer | **Avisar** i esperar la teva confirmació |
| Fila amb error | Mostrar el problema i saltar-la; la resta continua |

### Pas 2 — Aplicar

Només el que hagis confirmat. Les baixes van a part: surten amb una casella
per marcar una per una, i **cap es dona de baixa sense que la marquis**.

Donar de baixa **no esborra res**: posa data de baixa i desactiva el compte,
però conserva els marcatges, que s'han de guardar 4 anys. Si la persona torna,
es reactiva.

### Idempotent

Carregar dues vegades el mateix fitxer no duplica res ni torna a crear
comptes. Es pot repetir sense por.

---

## El que el fitxer no pot portar, i s'ha de fer un cop a mà

L'aplicació de nòmines **no sap** res d'això, i el control horari sí que ho
necessita:

- **Servei** de cada persona. La primera càrrega el pot portar si l'omples al
  full; a partir d'aquí queda desat i no cal repetir-lo.
- **Horari assignat** (patró + vigència). Es fa a `/configuracio/horaris`.
  Sense horari assignat, les hores previstes surten a zero.
- **Àmbit d'aprovació** dels responsables: quins serveis pot aprovar cadascú.
- **Saldos** de vacances diferents del valor per defecte.

Res d'això canvia cada mes: es fa un cop i es manté.

---

## Peces a construir

### A l'aplicació de nòmines

`eines/exporta_per_control_horari.py`, amb el patró de dos passos que ja fa
servir `eines/altes_personal.py`:

```
python eines/exporta_per_control_horari.py prepara
    Llegeix treballadors.xlsx, proposa el nom d'usuari de cadascú
    (reaprofitant `proposa_usuari()`, que ja funciona), genera una
    contrasenya provisional per als nous i escriu el CSV.

python eines/exporta_per_control_horari.py envia --prova
python eines/exporta_per_control_horari.py envia --confirma
    Envia a cada treballador nou el seu usuari i la contrasenya provisional,
    amb l'SMTP que l'aplicació ja té configurat. Sense --confirma no
    s'envia res.
```

### Al control horari

- `core/importa.py` — analitza el CSV i calcula el pla (crear / actualitzar /
  baixa / error). **Funció pura**, provable sense servidor ni fitxers.
- Dues rutes a `web/configuracio.py`: previsualitzar i aplicar.
- `templates/configuracio/importa.html`.
- Proves: fitxer correcte, capçalera que falta, correu duplicat, servei
  inexistent, càrrega repetida (idempotència), i que **cap baixa no s'apliqui
  sense confirmació**.

---

## Seguretat i protecció de dades

- El CSV conté noms, correus i contrasenyes provisionals: **és un fitxer amb
  dades personals**. Es fa servir i s'esborra; no es versiona mai (ja entra al
  `.gitignore` per l'extensió i la ubicació).
- La contrasenya del fitxer **es xifra en arribar** i mai es desa en clar.
- Els comptes nous neixen amb `canvi_pendent`, o sigui que l'aplicació obliga
  a canviar la contrasenya al primer accés.
- La càrrega queda al registre d'activitat (`ALTA_COMPTE`, `CONFIG`), amb qui
  l'ha feta i quants comptes ha tocat, mai amb dades personals.
- L'aplicació de nòmines **no rep mai res** del control horari: no hi ha canal
  de tornada.
