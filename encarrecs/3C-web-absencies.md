# Encàrrec 3C · Web d'absències (vacances i assumptes propis)

**Onada 3** · Depèn de: 1A, 1D, 1E, 2A · Alhora que: 3A, 3B, 3D, 3E

## Objectiu

Que un treballador vegi quants dies li queden, en demani des del mòbil i sàpiga
en quin estat està cada sol·licitud.

## Escrius

```
web/absencies.py               templates/absencies/index.html
static/css/absencies.css       tests/test_web_absencies.py
```

## Llegeixes

`DISSENY.md` §6 (blueprint `absencies`), §4.3 (regles). `core/regles.py` (1D),
`core/calendari.py` (1E), `magatzem/absencies.py` (1A), `core/notifica.py` (2D).

## Feina

### `/absencies` (GET, `?any=&mes=`)

Una sola pàgina amb quatre blocs:

1. **Saldos**, una targeta per tipus (vacances, assumptes propis): dies
   assignats, gastats, pendents i **disponibles** en gran.
   - Si `Saldo.prorratejat`, explica-ho en una línia: «Et corresponen 14 dies
     perquè vas entrar l'11/05/2026 (235 dies de relació laboral)». Sense
     l'explicació, un saldo de 14 en lloc de 22 sembla un error del programa.
   - Si `Saldo.disponibles` és **negatiu**, en vermell i amb text explicant que
     són dies gaudits per damunt del meritat, que es regularitzen a la
     liquidació. Mai amagat ni arrodonit a zero.
2. **Formulari de sol·licitud**: tipus, data d'inici, data de fi, motiu
   (opcional). En triar les dates, ensenya els dies hàbils que consumirà —al
   servidor en enviar; si vols fer-ho amb JS, que sigui un extra i que la
   pàgina funcioni igual sense.
3. **Les meves sol·licituds**, les més noves a dalt: codi, tipus, dates, dies,
   estat amb etiqueta de color **i text**, i el motiu de la resolució si n'hi
   ha. Botó d'anul·lar quan pertoqui.
4. **Calendari personal** del mes (`core.calendari.graella_mes`) amb les meves
   absències pintades per tipus, navegable amb `?any=&mes=`.

### `/absencies/solicita` (POST)

`regles.valida_solicitud` → `magatzem.absencies.crea` → registra `ABSENCIA_SOL`
→ `notifica.avisa_nova_solicitud` als responsables de l'àmbit del meu servei.

L'ordre importa: **primer es desa, després s'avisa**. Si el correu falla, la
sol·licitud existeix igualment i es mostra un avís.

`ErrorHorari` → `flash` amb el missatge tal qual i tornada al formulari amb el
que s'havia escrit. **No perdis el que ha teclejat l'usuari** en un error.

### `/absencies/anula` (POST)

- El propietari pot anul·lar la seva sol·licitud **PENDENT**.
- Una **APROVADA** només la pot anul·lar un responsable de l'àmbit o un admin
  (i això passa per la pantalla de gestió, de l'agent 3D; aquí només el cas del
  propietari amb la pendent).
- Comprovació de propietat obligatòria: l'identificador ve del formulari.
  Si no és seva, **403**.
- Els dies tornen sols al disponible: el càlcul és dinàmic, no toquis cap saldo.

## Acceptació

- [ ] Es demanen unes vacances i apareixen com a PENDENT amb el seu codi.
- [ ] Els quatre errors de `valida_solicitud` es veuen com a `flash` en català,
      amb el formulari conservat.
- [ ] El saldo prorratejat s'explica; el negatiu es veu i s'explica.
- [ ] Anul·lar una pendent retorna els dies al disponible.
- [ ] Un treballador **no pot** anul·lar la sol·licitud d'un altre (403).
- [ ] Un treballador **no pot** aprovar-se res a si mateix des d'aquí (aquesta
      pàgina no té cap acció d'aprovar).
- [ ] `pytest -q` verd.

Cobertura mínima: sol·licitud correcta; sol·licitud que creua l'any; sense
saldo; solapada amb una de pendent; solapada amb una d'aprovada; anul·lació
pròpia; anul·lació aliena → 403; anul·lació d'una aprovada des d'aquí → no
permesa; calendari amb paràmetres invàlids; saldo prorratejat i saldo negatiu
ben mostrats.

## Paranys

- **Les dates arriben com a text.** Converteix-les amb `date.fromisoformat`
  dins d'un `try`: un `?data=demà` no ha de fer un 500.
- **El camp `dies` no el calcula el navegador.** El calcula el servidor amb
  `regles.dies_habils` amb els festius de la base de dades. Si el confies al
  formulari, qualsevol es regala vacances.
- **No mostris mai les absències d'altres persones en aquesta pàgina**, ni al
  calendari. El calendari general és de la pantalla de gestió i té un altre
  control d'accés.
- **`recuperacio` és un tipus vàlid** però no té saldo anual: tracta'l a part o
  amaga'l del formulari fins que es decideixi com funciona (i anota-ho a
  `incidencies/3C.md`).
