# Encàrrec 3A · Web de fitxatge — la pantalla principal

**Onada 3** · Depèn de: 1A, 1B, 1C, 2A · Alhora que: 3B, 3C, 3D, 3E
· **És la pantalla que justifica tota l'aplicació.** Si només se'n fa una, és
aquesta.

## Objectiu

Que un treballador obri l'aplicació al mòbil, vegi immediatament què li toca
fer i ho faci amb un sol toc.

## Escrius

```
web/fitxatge.py                    templates/fitxatge/inici.html
templates/fitxatge/marcatges.html  static/css/fitxatge.css
tests/test_web_fitxatge.py
```

## Llegeixes

`DISSENY.md` §6 (blueprint `fitxatge`), §8 (interfície). `core/fitxatge.py`
(1C), `core/comput.py` (1B), `magatzem/marcatges.py` (1A).

## Feina

### `/` — la pantalla principal

De dalt a baix, i res més:

1. **L'hora, en gran.** Actualitzada per JavaScript (fitxer extern, la CSP no
   permet codi en línia); si no hi ha JS, l'hora del servidor en carregar.
2. **Què consta ara**: «Ets DINS des de les 8:03» / «Ets FORA» / «En pausa des
   de les 11:00». Text, no només color.
3. **UN botó gran** amb l'acció principal de `accions_possibles(estat)[0]`.
   Mínim 64 px d'alçada i a l'amplada de la pantalla. Ha de ser utilitzable
   amb guants i amb sol.
4. La segona acció, si n'hi ha (`sortida` quan s'està dins), com a botó
   secundari clarament diferent.
5. Sota, discret: hores fetes avui, teòriques d'avui, saldo del dia i saldo
   acumulat del mes. Amb `formata_minuts`.
6. Si el dia té anomalies, un avís tranquil amb l'enllaç a `/marcatges` per
   corregir-ho.

**No hi posis res més.** Ni menús desplegables, ni gràfics, ni consells. Aquesta
pantalla es mira tres segons, dues vegades al dia.

### `/fitxa` (POST)

`core.fitxatge.valida_marcatge` → `magatzem.marcatges.afegeix` amb
`origen='web'`, `moment=model.ara_utc()`, `data=model.data_local(...)`, la IP i
`creat_per` igual al mateix treballador. Registra `FITXATGE`. Torna a `/` amb
un `flash` que confirmi **l'hora exacta que s'ha registrat** («Entrada
registrada a les 8:03»): és el rebut del treballador.

Si `valida_marcatge` llança `ErrorHorari`, `flash` amb el seu missatge i
tornada a `/`. **Mai un 500.**

### `/marcatges` (GET)

Els meus marcatges del mes (`?any=&mes=`), agrupats per dia, amb l'hora local,
l'origen, les anomalies marcades i les correccions pendents de validar ben
visibles. Cada dia, amb un botó per corregir.

### `/marcatges/corregeix` (POST)

`core.fitxatge.prepara_correccio` → `magatzem.marcatges.afegeix`. Registra
`CORRECCIO`. **Comprovació obligatòria**: el marcatge que es corregeix ha de
ser del treballador de la sessió. Si no ho és, 403 —encara que l'identificador
vingui del formulari, o precisament per això.

Avisa els responsables de l'àmbit amb `notifica.avisa_correccio_pendent`
(fail-soft: si el correu falla, la correcció ja està desada).

## Acceptació

- [ ] Amb un compte de prova: entrada, pausa, represa i sortida, i els números
      del dia surten bé. **Fes-ho al navegador de debò**, no només amb tests.
- [ ] El botó principal ofereix sempre, i només, el que es pot fer.
- [ ] Un doble toc ràpid no crea dos marcatges.
- [ ] Un treballador **no pot** corregir el marcatge d'un altre (403).
- [ ] La pantalla es veu bé a 375 px sense desplaçament horitzontal.
- [ ] `pytest -q` verd (tota la suite).

Cobertura mínima: cicle sencer del dia; fitxar una sortida estant fora →
`flash` amb el missatge de domini, no un error; doble toc; correcció pròpia →
`PENDENT_VALIDACIO`; correcció d'un altre → 403; `/` sense sessió → redirecció
al login; `?any=` i `?mes=` invàlids → mes actual, mai error.

## Paranys

- **`moment` és UTC i es mostra en local.** Per ensenyar l'hora,
  `Marcatge.hora_local` o `model.a_local()`. Si en algun lloc surt l'hora amb
  dues hores de diferència, és això.
- **La IP real** ve de `request.remote_addr` **només si `ProxyFix` està
  actiu** (`DARRERE_PROXY=1`). En local no ho estarà: no és un error.
- **No calculis res tu.** Els minuts els fa `core/comput.py`. Si et cal un
  número que no et dona, és una incidència, no una funció nova al blueprint.
- **No posis el botó de fitxar dins d'un formulari amb `GET`.** Ha de ser POST
  amb CSRF: si no, una imatge en un correu podria fer fitxar algú.
- **Que funcioni sense JavaScript.** El rellotge és un adorn; el botó és un
  `<form method="post">` de tota la vida.
