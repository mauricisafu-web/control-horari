# Encàrrec 0A · Esquelet executable

**Onada 0** · Depèn de: res (el contracte ja hi és) · **Bloqueja tota la resta.**

## Objectiu

Que `python app_web.py` aixequi una aplicació Flask al port 5004, amb els vuit
blueprints registrats, les capçaleres de seguretat a totes les respostes i el
magatzem inicialitzat sol. Encara no hi ha ni login ni funcionalitat: hi ha
**esquelet**.

## Escrius

```
app_web.py                 configuracio.py            core/registre.py
web/__init__.py            web/auth.py                web/fitxatge.py
web/hores.py               web/absencies.py           web/gestio.py
web/configuracio.py        web/informes.py            web/pwa.py
templates/base.html        templates/error.html       templates/en_construccio.html
templates/avis_legal.html  static/css/base.css        static/js/app.js
tests/test_esquelet.py
```

## Llegeixes

`DISSENY.md` §6 (taula de rutes), §7 (seguretat), §8 (interfície), §9
(variables d'entorn); `core/model.py`, `magatzem/rebost.py` i `tests/conftest.py` (ja fets).

## Feina

### `configuracio.py`

Una funció `carrega() -> dict` que llegeix les variables de `DISSENY.md` §9 de
l'entorn amb els seus valors per defecte i les converteix al tipus correcte.
`SECRET_KEY`: de l'entorn; si no hi és, del fitxer `.secret_key`; si tampoc hi
és, el genera amb `secrets.token_hex(32)`, el desa amb permisos 600 i avisa al
log. **Mai** una clau fixa al codi.

### `app_web.py`

```python
def crea_app(config_extra: dict | None = None, magatzem=None) -> Flask
```

És el patró de fàbrica: `conftest.py` ja el crida **exactament així** (amb el
paràmetre `magatzem` per injectar-hi el de proves) i el `Dockerfile` també
(`'app_web:crea_app()'`). Ha de fer:

1. Carregar la configuració i aplicar `ProxyFix` si `DARRERE_PROXY=1`.
2. El magatzem: si l'argument `magatzem` ve donat, aquell; si no,
   `rebost.obre_rebost()` (que llegeix `REBOST` i per defecte és memòria).
   Després, `rebost.inicialitza(mag)`. **Un sol magatzem per procés**, desat a
   `app.extensions['magatzem']`, i accessible als blueprints com a `g.mag` via
   un `before_request`. Deixa-ho documentat amb un exemple al capdamunt del
   fitxer: **és el mecanisme que faran servir tots els blueprints.**
3. CSRF (Flask-WTF) i Flask-Login (`login_view = 'auth.login'`). El
   `user_loader` de moment pot retornar `None`: el completa l'agent 2A.
4. Registrar els vuit blueprints de `web/`.
5. `@app.after_request` amb **totes** les capçaleres de `DISSENY.md` §7. Una
   sola funció, no repetida enlloc més.
6. `@app.before_request` de caducitat de sessió per inactivitat i, si
   `DOMINI_PUBLIC` té valor, el rebuig de peticions amb un altre `Host` (403).
7. Gestors d'error 404, 403, 413, 500 i CSRF caducat, tots amb
   `templates/error.html` i missatge **en català**.
8. Al final, el bloc `if __name__ == '__main__':` que arrenca al **5004**.

### `core/registre.py`

`registra(accio, usuari='', detall='', ip='')` cap a `logs/activitat.log` amb
`RotatingFileHandler` (5 fitxers d'1 MB). Sanititza el text (treu salts de
línia i caràcters de control: anti-injecció al log) i **no hi deixa passar mai
dades personals** més enllà del login. Les accions permeses són la llista de
`DISSENY.md` §4.5.

### Els vuit blueprints

Cadascun és un esquelet mínim, i prou:

```python
"""web/hores.py — Resum d'hores. L'omple l'agent 3B."""
from flask import Blueprint, render_template

hores = Blueprint('hores', __name__)

@hores.route('/hores')
def resum():
    return render_template('en_construccio.html', modul='Hores')
```

**Important**: el nom del blueprint i el nom de la funció han de coincidir amb
els `url_for(...)` de `DISSENY.md` §6, perquè `templates/base.html` ja hi
enllaçarà. `web/pwa.py` i la ruta `/avis-legal` de `web/auth.py` van **sense**
`login_required`.

### `templates/base.html`

L'esquelet de totes les pàgines. Ha de tenir:

- `<html lang="ca">`, `<meta name="viewport">`, enllaç al manifest i al full
  `base.css`, i `theme-color`.
- Navegació **per rol**, amagant el que l'usuari no pot veure. Mentre no hi
  hagi login, ensenya-la sencera si `current_user` no està autenticat i
  documenta-ho amb un comentari.
- Zona de `flash` amb les categories `ok`, `avis`, `error`.
- Blocs Jinja: `{% block titol %}`, `{% block css_extra %}`,
  `{% block contingut %}`, `{% block js_extra %}`. **Aquests quatre noms són
  contracte**: tots els altres agents els faran servir.
- Peu amb l'enllaç a `/avis-legal`.

### `static/css/base.css`

Variables de color (clar i fosc amb `prefers-color-scheme`), tipografia del
sistema (cap font externa: CSP), i les classes compartides: `.targeta`,
`.camp`, `.fila`, `.accions`, `.btn`, `.btn-gran`, `.flash`, `.taula`,
`.etiqueta`, `.subtitol`. **Mòbil primer**: es dissenya a 375 px i s'eixampla.
Contrast mínim 4,5:1 i àrees tàctils de 44 px.

## Acceptació

- [ ] `python app_web.py` arrenca al 5004 i respon.
- [ ] `/avis-legal` respon 200 **sense sessió**.
- [ ] Les vuit rutes principals responen (200 o redirecció al login), cap 404.
- [ ] Totes les respostes porten CSP, `nosniff`, `X-Frame-Options: DENY`,
      `Referrer-Policy` i `Cache-Control: no-store`.
- [ ] El magatzem s'inicialitza sol en arrencar (els paràmetres per defecte
      hi són) i **per defecte és el de memòria**: sense variables d'entorn,
      `python app_web.py` ha de funcionar sense cap compte de Google.
- [ ] `pytest -q` verd.
- [ ] `grep -rn "import flask" core/` no retorna res.
- [ ] `grep -rn "google" app_web.py configuracio.py web/` no retorna res.

## Proves

```bash
C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q
```

```bash
C:\Users\secretari\AppData\Local\Programs\Python\Python312\python.exe app_web.py
```

`tests/test_esquelet.py` ha de comprovar, com a mínim: que `crea_app()`
funciona amb i sense magatzem injectat, que hi ha les capçaleres, que
`/avis-legal` és públic, que un 404 retorna la pàgina en català, i que
`g.mag` arriba als blueprints.

## Paranys

- **`Cache-Control: no-store` a `/static/`** trencaria la PWA. Exclou-ne els
  estàtics: allà interessa la cache, i no hi ha dades de ningú.
- **La CSP i el JS**: `default-src 'self'` sense `unsafe-inline`. Res de
  `onclick=` als atributs ni de `<script>` amb codi a dins. Tot a fitxers de
  `/static/js/`.
- **UN sol magatzem per procés**, no un per petició: obrir-ne un a cada
  petició costaria una connexió nova cada vegada. El que va a `g` a
  `before_request` és una referència al que ja hi ha, no un objecte nou.
- **No facis el login.** És de l'agent 2A. Si el fas, li trepitjaràs el fitxer.
