# Encàrrec 2D · Correus i eines de consola

**Onada 2** · Depèn de: 0A i 1A · Alhora que: 2A, 2B, 2C

## Objectiu

Els avisos per correu (que mai han de poder bloquejar res) i les eines de
consola per administrar l'aplicació sense entrar-hi.

> El patró de correu **ja existeix provat** a
> `expedients-nomines-beta/core/vacances/notifica.py` i `envia_nomines.py`.
> Adapta'l. **No escriguis res en aquella carpeta.**

## Escrius

```
core/notifica.py     eines/gestiona_comptes.py
config.ini.example   tests/test_notifica.py
```

## Llegeixes

`DISSENY.md` §4.5 i §9 (variables d'SMTP). `magatzem/comptes.py` (agent 1A).

## Feina

### `core/notifica.py` — la regla és **fail-soft**

```python
def hi_ha_correu(config) -> bool
def envia(config, desti, assumpte, cos) -> bool      # False si no ha pogut
def avisa_nova_solicitud(config, absencia, treballador, aprovadors) -> None
def avisa_resolucio(config, absencia, treballador) -> None
def avisa_correccio_pendent(config, marcatge, treballador, responsables) -> None
def envia_provisional(config, treballador, contrasenya) -> bool
```

**Cap flux de dades es bloqueja mai perquè l'SMTP falli.** `try/except` ampli:
si falla, es retorna `False`, s'anota al registre d'activitat i qui ha cridat
la funció ensenya un avís. La sol·licitud, la resolució o l'alta **ja s'han
desat** abans d'intentar el correu. Aquest ordre és obligatori.

Excepció única: `envia_provisional`. Si la contrasenya provisional no arriba,
el compte no serveix de res. Qui la crida (agent 3E) decidirà si crea el
compte igualment; tu retorna `False` honestament.

Si `SMTP_HOST` no està configurat, `hi_ha_correu` retorna fals i `envia` no
intenta res: escriu al log que el correu està desactivat. És el cas normal en
desenvolupament i **no és un error**.

Els cossos dels correus, en català, curts i **sense dades de més**: qui, quin
tipus d'absència i quines dates. Res de motius mèdics (que no n'hi ha) ni de
saldos. Que el correu no sigui, ell mateix, una filtració.

Verificació del TLS **activada per defecte**; només es pot desactivar amb un
paràmetre explícit de `config.ini` i amb un comentari que digui que és un risc
assumit.

### `eines/gestiona_comptes.py`

Ordres: `llista`, `afegeix`, `rol`, `desactiva`, `contrasenya`, `totp-reset`.

Patró de seguretat en **dos passos** per a tot el que enviï correus o afecti
molta gent: `--prova` ensenya què faria i `--confirma` ho fa. És el patró de
`eines/altes_personal.py` de la beta i ha evitat més d'un ensurt.

**Cap ordre d'aquesta eina no pot escriure dades reals al repositori** ni
treure-les per pantalla més enllà del que calgui per operar.

### `config.ini.example`

Plantilla comentada amb els paràmetres d'SMTP. **`config.ini` real està al
`.gitignore`** i no s'ha de crear mai amb dades de l'ajuntament dins d'aquest
repositori.

## Acceptació

- [ ] Cap funció de `notifica.py` propaga mai una excepció d'SMTP.
- [ ] Amb `SMTP_HOST` buit, tot funciona i s'anota al log.
- [ ] `eines/gestiona_comptes.py --ajuda` s'entén sense llegir el codi.
- [ ] Les ordres perilloses exigeixen `--confirma`.
- [ ] `pytest tests/test_notifica.py -q` verd.

Cobertura mínima: **cap test envia cap correu de debò** (injecta un servidor
fals o `monkeypatch` sobre `smtplib.SMTP`); SMTP no configurat → `False` sense
excepció; servidor que rebutja la connexió → `False` sense excepció;
autenticació fallida → `False` sense excepció; enviament correcte → `True` i
el cos conté el que ha de contenir i **no conté** el que no.

## Paranys

- **L'SMTP del port 25 està bloquejat a Cloud Run** (i a gairebé tots els
  núvols). Ha de ser 587 amb STARTTLS o 465 amb SSL. Deixa-ho escrit al
  `config.ini.example`.
- **Un `except` que se'l menja tot i no diu res** és pitjor que l'error. Cada
  captura ha d'escriure al registre d'activitat què ha passat.
- **Els temps d'espera de l'SMTP.** Sense `timeout`, un servidor que no
  respon deixa penjada la petició web fins que el navegador es rendeix. Posa-hi
  10 segons.
- **No enviïs res de debò a ningú.** Ni una prova. L'usuari ha demanat
  expressament que no surti cap correu real sense que ell ho confirmi.
