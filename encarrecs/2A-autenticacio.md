# Encàrrec 2A · Autenticació, comptes i TOTP

**Onada 2** · Depèn de: 0A i **1A** · Alhora que: 2B, 2C, 2D
· Fins que això no hi sigui, no es pot provar cap pantalla amb sessió.

## Objectiu

Que una persona pugui entrar amb el seu compte, se li obligui a canviar la
contrasenya provisional, activi la verificació en dos passos si el rol l'hi
exigeix, i pugui recuperar l'accés si l'ha perdut.

> El TOTP **ja existeix provat** a `expedients-nomines-beta/core/totp.py` amb
> els seus tests. Adapta'l (allà les dades són en un `.ini`; aquí, al magatzem
> de documents, dins del propi document del treballador).
> **No escriguis res en aquella carpeta.**

## Escrius

```
web/auth.py          core/comptes.py       core/totp.py
templates/auth/login.html        templates/auth/login_totp.html
templates/auth/canvia_contrasenya.html
templates/auth/recupera.html     templates/auth/recupera_nova.html
templates/auth/totp.html
static/css/auth.css
tests/test_auth.py   tests/test_totp.py
```

`templates/avis_legal.html` ja és de 0A; si li falta contingut, és de l'agent 4D.

## Llegeixes

`DISSENY.md` §6 (taula de rutes d'`auth`), §2 (rols), §7 (seguretat).
`magatzem/comptes.py` (agent 1A). De referència:
`expedients-nomines-beta/core/totp.py` i les rutes de login d'`app_web.py`.

## Feina

### `core/comptes.py`

```python
def hash_contrasenya(text) -> str                 # scrypt de werkzeug
def verifica(hash, text) -> bool
def contrasenya_provisional() -> str              # CSPRNG, 14 caràcters
def valida_politica(text) -> None                 # ErrorHorari si no compleix
def token_recuperacio(id, secret) -> str          # signat i amb caducitat
def obre_token(token, secret, max_edat) -> int | None
```

Política mínima: 10 caràcters. **Prohibeix explícitament** la contrasenya
provisional que s'acaba de rebre com a contrasenya nova. Res de regles
barroques de símbols obligatoris: fan que la gent escrigui la contrasenya en
un post-it.

### `web/auth.py`

Les onze rutes de `DISSENY.md` §6. Punts que has de fer bé:

1. **Límit d'intents per IP.** Comptador en memòria del procés, amb poda
   (l'aplicació corre amb una sola instància, no cal res més). Missatge genèric
   («usuari o contrasenya incorrectes») tant si el compte no existeix com si la
   contrasenya és dolenta: no s'ha de poder endevinar qui té compte.
2. **Sessió nova en entrar** (`session.clear()` abans de `login_user`):
   anti-fixació de sessió.
3. **`next` de la redirecció**: només rutes internes. Rebutja `//`, `http://` i
   qualsevol cosa amb host. És un forat d'open redirect clàssic.
4. **`canvi_pendent`**: un `before_request` del blueprint que confina qui el
   té posat a `/canvia-contrasenya` (deixant passar `/logout` i els estàtics).
5. **TOTP obligatori** per a `admin` i `responsable`: un altre confinament, cap
   a `/totp`, mentre no el tinguin actiu. Per a `treballador` és opcional.
6. **Segon factor**: després de la contrasenya correcta, si el compte té TOTP
   actiu, **no** facis `login_user` encara. Deixa un identificador a la sessió
   (`session['pendent_totp']`) amb una marca de temps i verifica el codi a
   `/login/totp`. Si es triga més de 5 minuts, es torna a començar.
7. **Codis de recuperació**: 8 codis d'un sol ús, ensenyats **una sola vegada**
   en activar el TOTP, desats com a hash a `codi_recuperacio`. En fer-ne servir
   un, es marca `usat_el`.
8. **Recuperació de contrasenya**: enllaç signat amb caducitat de 30 minuts al
   correu registrat. La resposta és **la mateixa** tant si el correu existeix
   com si no («Si aquest correu té compte, hi rebràs un enllaç»): si no, la
   pàgina et diu qui té compte a l'ajuntament.
9. **Registre d'activitat** a `LOGIN`, `LOGIN_FALLIT`, `LOGOUT`,
   `CANVI_CONTRASENYA`, `TOTP` — amb login i IP, mai la contrasenya.
10. Completa el `user_loader` que 0A va deixar retornant `None`.

### Plantilles

Senzilles i mòbil primer. La de login porta l'enllaç a `/avis-legal` (art. 13
del RGPD) i el de recuperació. La de TOTP ensenya el QR **en SVG generat al
servidor** (`qrcode`), mai una imatge d'un servei extern, i el secret en text
per si algú no pot llegir el codi.

## Acceptació

- [ ] Es pot entrar, sortir, canviar la contrasenya i recuperar-la.
- [ ] Un compte amb `canvi_pendent` no pot anar enlloc més que a canviar-la.
- [ ] Un `responsable` sense TOTP actiu queda confinat a `/totp`.
- [ ] La fixture `entra` de `conftest.py` funciona → **això desbloqueja
      l'onada 3 sencera**; comprova-ho abans de dir que has acabat.
- [ ] `pytest -q` verd (tota la suite, no només la teva).

Cobertura mínima: login correcte i incorrecte; bloqueig per intents; `next`
maliciós rebutjat (`//evil.com`, `http://evil.com`); confinament per
`canvi_pendent`; confinament per TOTP segons rol; cicle sencer de TOTP (alta,
QR, confirmació, entrada amb codi, codi caducat, codi de recuperació, codi de
recuperació ja usat); recuperació amb token bo, caducat i manipulat; que la
resposta de `/recupera` no revela si el correu existeix.

## Paranys

- **`pyotp` accepta una finestra de temps.** Fes servir `valid_window=1` (±30 s):
  sense això, la meitat dels mòbils amb el rellotge una mica desviat no entren.
- **El secret del TOTP és tan sensible com la contrasenya.** No el treguis mai
  per un log ni per un missatge d'error.
- **No facis `login_user` abans del segon factor.** És l'error que buida de
  sentit tot el 2FA.
- **La contrasenya no pot arribar mai a la URL.** Només POST.
- **Si `SMTP_HOST` no està configurat** (cas normal en desenvolupament), la
  recuperació ha de dir-ho clarament al log i ensenyar un avís, no petar.
