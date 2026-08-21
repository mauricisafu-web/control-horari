# Encàrrec INT-B · Exportador des de l'aplicació de nòmines

**Alhora que**: INT-A i INT-C. No depens de ningú.

## Objectiu

Una eina de consola que llegeix la llista de treballadors de l'aplicació de
nòmines, en genera el CSV per al control horari, i envia a cada persona nova
la seva contrasenya provisional.

## Escrius

```
eines/exporta_des_de_nomines.py
tests/test_exporta.py
```

## Regla dura

**NO es modifica cap fitxer de `C:\Users\secretari\expedients-nomines-beta`.**
Se'n pot LLEGIR (`treballadors.xlsx`, `config.ini` per a l'SMTP), mai
escriure-hi. És una instrucció explícita de l'usuari.

Per això l'eina viu al repositori del control horari encara que operi sobre
dades de nòmines. Les rutes són **arguments**, no valors fixos al codi.

## Llegeixes

`core/format_importacio.py` (congelat), `desplegament/INTEGRACIO_NOMINES.md`,
i de referència `expedients-nomines-beta/eines/altes_personal.py` — la funció
`proposa_usuari()` ja resol el nom d'usuari sense accents ni duplicats:
**adapta-la, no la reinventis**.

## Feina

```
python eines/exporta_des_de_nomines.py prepara --xlsx <ruta> --sortida <csv>
python eines/exporta_des_de_nomines.py envia --fitxer <csv> --prova
python eines/exporta_des_de_nomines.py envia --fitxer <csv> --confirma
```

### `prepara`

- Llegeix l'xlsx (columnes `Nom | Correu`) amb `openpyxl`.
- Proposa el nom d'usuari de cadascú (inicial + primer cognom, sense accents,
  desambiguat sense xifres).
- Genera una **contrasenya provisional** per a cadascú amb
  `core.comptes.contrasenya_provisional()` — ja evita caràcters confusos.
- Escriu el CSV amb les columnes de `core/format_importacio.py`, amb `;` i
  `utf-8-sig`.
- Deixa `servei` i `rol` buits: nòmines no ho sap. L'usuari els omple.
- El nom del fitxer per defecte porta la DATA.
- En acabar, avisa per pantalla que **el fitxer conté contrasenyes i dades
  personals**, i que s'ha d'esborrar quan s'hagi fet servir.

### `envia`

- Llegeix el CSV ja revisat i envia a cada persona **que hi tingui
  contrasenya** un correu amb el seu usuari i la contrasenya provisional.
- Patró de DOS PASSOS: `--prova` diu a qui escriuria sense enviar res;
  `--confirma` envia de debò. **Sense cap de les dues, no fa res.**
- L'SMTP surt del `config.ini` de nòmines (llegit, mai escrit); la ruta és un
  argument amb valor per defecte.
- Fail-soft: si un correu falla, es continua amb els altres i es reporta al
  final qui no l'ha rebut.
- El text ha de dir que la contrasenya és provisional i que l'aplicació
  obligarà a canviar-la al primer accés.

## Acceptació

- [ ] `prepara` genera un CSV que `core.importa.analitza()` accepta sense cap
      error. **Prova-ho de debò a un test.**
- [ ] Els noms d'usuari no tenen accents, ni xifres, ni duplicats.
- [ ] `envia` sense `--confirma` no envia res.
- [ ] Cap prova envia cap correu real (`monkeypatch` sobre `smtplib`).
- [ ] Cap prova llegeix l'xlsx real de l'ajuntament: crea'n un de sintètic
      amb `openpyxl` al `tmp_path`.
- [ ] La ruta de la carpeta de nòmines només pot sortir en comentaris o com a
      valor per defecte d'un argument, mai fixada dins la lògica.
- [ ] `pytest tests/test_exporta.py -q` verd.

## Paranys

- **Cap dada real a les proves.** Noms inventats i `@exemple.cat`.
- **No escriguis res a la carpeta de nòmines**, ni el CSV: la sortida va on
  digui `--sortida`, per defecte al directori actual.
- **Les contrasenyes no es registren al log.** Ni al de nòmines ni enlloc.
- `openpyxl` ja és una dependència del projecte de nòmines, però **no ho és
  del control horari**: si no hi és, afegeix-la al `requirements.txt`... i
  aquest fitxer no és teu, o sigui que anota-ho a `incidencies/INT-B.md`.
