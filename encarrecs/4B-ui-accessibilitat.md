# Encàrrec 4B · Coherència visual i accessibilitat

**Onada 4** · Depèn de: l'onada 3 sencera · **VA SOL**: cap altre agent
d'interfície pot treballar mentre corre aquest.

## Objectiu

Que les pantalles fetes per cinc agents diferents semblin la mateixa
aplicació, i que les pugui fer servir tothom de la plantilla, també qui hi veu
poc o té dificultats motrius.

## Escrius

**Excepcionalment, pots tocar fitxers d'altres agents**, i només aquests:

```
static/css/*        (tots)
templates/**        (només marcatge, etiquetes i atributs: NO lògica Jinja)
tests/test_ui.py
```

**No** toquis cap `.py`. Si un canvi necessita codi de servidor, anota'l a
`incidencies/4B.md`.

## Llegeixes

`DISSENY.md` §8. Totes les plantilles i tots els fulls d'estil.

## Feina

### 1. Unificació

Recorre les pantalles i fes un inventari del que s'ha duplicat o divergit:
botons de mides diferents, targetes amb marges diferents, taules amb estils
propis, cinc grisos on n'hi hauria d'haver un. Puja al `base.css` el que és
comú i deixa als fulls de mòdul **només** el que és realment específic.

Resultat esperat: els fulls de mòdul han d'aprimar-se, no engreixar-se.

### 2. Accessibilitat — objectiu WCAG 2.1 AA

Repassa i corregeix:

- **Contrast** de 4,5:1 al text i 3:1 als elements d'interfície. Comprova'l de
  debò amb una eina, no a ull. Els grisos clars sobre blanc són el sospitós
  habitual.
- **Res que depengui només del color.** Els estats (pendent, aprovada,
  denegada, saldo negatiu, incidència) han de portar sempre text o icona. Un
  daltònic ha de poder fer servir la pantalla de gestió.
- **Àrees tàctils** de 44×44 px com a mínim. Els botons d'anul·lar i les fletxes
  de mes són els que solen quedar petits.
- **`<label>` de debò** associat a cada camp (`for`/`id`), no un `<span>` al
  costat. Els camps de data i hora, també.
- **Focus visible** i ordre de tabulació lògic. Que es pugui fitxar sense
  ratolí.
- **Taules amb `<th scope>`** i `<caption>`; les de dades, no per maquetar.
- **Idioma** `lang="ca"` i textos alternatius en català.
- **Missatges d'error associats al camp** (`aria-describedby`), no només un
  `flash` a dalt de tot.
- **Zoom fins al 200 %** sense perdre contingut ni desplaçament horitzontal.

### 3. Mòbil

Repassa **totes** les pantalles a **375 px**:

- Cap pàgina es desplaça horitzontalment. Les taules amples es desplacen **dins
  del seu contenidor** (`overflow-x: auto` amb el seu embolcall), no la pàgina.
- La navegació és usable amb el polze.
- El botó de fitxar és arribable sense fer scroll.

### 4. Detalls pendents d'altres agents

Recull les incidències que t'hagin deixat (l'agent 2B en deixa una sobre
l'enllaç a `/instal-lacio` al peu) i resol-les si són d'interfície.

### 5. Mode fosc

`base.css` ja ha de tenir les variables amb `prefers-color-scheme`. Comprova
que **totes** les pantalles funcionen en fosc: el que se sol trencar són els
colors escrits a pèl dins dels fulls de mòdul i els estats de les etiquetes.

## Acceptació

- [ ] Cap pantalla amb desplaçament horitzontal a 375 px.
- [ ] Contrast comprovat amb una eina a totes les combinacions de color.
- [ ] Cap estat que es distingeixi només pel color.
- [ ] Tots els camps amb `<label>` associat.
- [ ] L'aplicació és utilitzable **només amb teclat**, de punta a punta.
- [ ] El mode fosc funciona a totes les pantalles.
- [ ] `pytest -q` verd — **cap canvi teu ha de trencar cap test d'un altre.**
      Si en trenques un perquè has canviat un text que un test comprovava,
      **arregla el test**: aquest és l'únic cas en què pots tocar el fitxer de
      proves d'un altre agent, i has d'anotar-ho.

`tests/test_ui.py` ha de comprovar automàticament el que es pugui: que totes
les plantilles tenen `lang="ca"`, que no hi ha `<script>` amb codi a dins
(CSP), que no hi ha `style=` en línia amb colors, i que cada `<input>` té un
`<label>` amb el seu `for`.

## Paranys

- **No refacis el disseny.** L'encàrrec és unificar i fer accessible, no
  redissenyar. Si canvies l'aspecte de tot, els tests dels altres cauran i
  perdràs (i faràs perdre) una onada.
- **No treguis text «per fer-ho més net».** Les explicacions del saldo
  prorratejat i del saldo negatiu hi són perquè, sense elles, l'usuari es pensa
  que el programa s'equivoca.
- **Cap font externa, cap icona d'un CDN.** La CSP les bloqueja i, a més, seria
  una connexió a un tercer des del navegador del treballador.
- **Prova el fosc de debò**, canviant la preferència del sistema; no confiïs
  que les variables ja ho resolen.
