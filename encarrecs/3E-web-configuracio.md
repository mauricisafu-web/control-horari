# Encàrrec 3E · Web de configuració (només administradors)

**Onada 3** · Depèn de: 1A, 1E, 2A, 2D · Alhora que: 3A, 3B, 3C, 3D

## Objectiu

Que l'administrador pugui posar en marxa i mantenir l'aplicació **sense tocar
la base de dades a mà**: serveis, festius, horaris, comptes, àmbits i saldos.

## Escrius

```
web/configuracio.py                     templates/configuracio/index.html
templates/configuracio/horaris.html     templates/configuracio/comptes.html
static/css/configuracio.css             tests/test_web_configuracio.py
```

## Llegeixes

`DISSENY.md` §6 (blueprint `configuracio`), §2 (rols), §3 (esquema).
Tot `magatzem/`, `core/festius.py` (1E), `core/comptes.py` i `core/notifica.py`.

## Feina

Tot el blueprint amb prefix `/configuracio` i **només per a `admin`**. Un
decorador `cal_admin` al capdamunt, aplicat a totes les rutes sense excepció.

Organitza-ho en tres pàgines, no en una de sola de quilòmetre i mig:

### `/configuracio` — general

- **Serveis**: llista, alta, canvi de nom i color, baixa (només si no té ningú
  assignat; si en té, digues quants i no ho facis).
- **Festius**: llista de l'any amb l'àmbit, alta manual, baixa, i el botó
  d'**importar de la Generalitat** (`core.festius.importa` → `magatzem.festius.
  fusiona`), amb el codi INE del municipi editable. En acabar, digues **quants
  se n'han afegit i quants ja hi eren**. Si falla, el missatge d'`ErrorHorari`
  tal qual i un recordatori que l'alta manual continua disponible.
- **Paràmetres**: dies de vacances i d'AP per defecte, jornada màxima, pausa
  màxima, nom de l'ajuntament.

### `/configuracio/horaris`

- **Patrons**: llista amb el total setmanal calculat, alta i edició amb els
  trams (dia de la setmana, hora d'inici, hora de fi). Validació: `hora_fi >
  hora_inici`, i avisa si dos trams del mateix dia se solapen.
- **Assignacions**: per treballador, l'historial de vigències i el formulari
  per assignar-ne una de nova (patró, data d'inici, data de fi opcional,
  coeficient). **Avisa si la nova vigència se solapa amb una d'existent** i
  ofereix tancar l'anterior el dia abans: és el cas real (canvi d'horari
  d'estiu) i, si no es tanca, `comput` es queda amb la més recent i el resultat
  desconcerta.

### `/configuracio/comptes`

- Llista de treballadors amb login, nom, correu, servei, rol, alta, baixa,
  estat, si té TOTP i el **saldo a liquidar** en vermell si és negatiu.
- **Alta**: nom, correu, login, servei, rol, data d'alta. Genera la contrasenya
  provisional (`core.comptes.contrasenya_provisional`), la desa amb
  `canvi_pendent = 1` i l'envia per correu (`notifica.envia_provisional`). Si
  el correu falla, **crea el compte igualment** i ensenya la contrasenya per
  pantalla una sola vegada, amb l'avís que s'ha de fer arribar per un canal
  segur. (Decisió: bloquejar l'alta per un SMTP mal configurat és pitjor.)
- **Baixa**: data de baixa, desactivació. **No esborris el compte**: el
  registre de jornada s'ha de conservar 4 anys i les files hi apunten.
- **Rol i àmbits d'aprovació**: canviar el rol i, per als responsables,
  marcar els serveis del seu àmbit (amb l'opció «tots els serveis», que desa
  `None`).
- **Saldos anuals**: per treballador, any i tipus. Amb el valor prorratejat
  calculat al costat, perquè es vegi què li tocarà de debò.
- **Reinici de TOTP** quan algú perd el mòbil.

## Acceptació

- [ ] Un `responsable` o un `treballador` que demani qualsevol `/configuracio*`
      rep **403**. Prova-ho ruta per ruta.
- [ ] Amb una base de dades buida, un administrador pot deixar l'aplicació
      llesta per usar **sense sortir del navegador**: crear serveis, importar
      festius, crear un patró, donar d'alta algú i assignar-li l'horari.
      Fes aquest recorregut sencer com a prova final.
- [ ] La importació de festius informa de quants n'ha afegit.
- [ ] Una assignació solapada avisa abans de desar.
- [ ] Donar de baixa **no esborra** el treballador ni els seus marcatges.
- [ ] `pytest -q` verd.

## Paranys

- **El rol i l'àmbit són la porta de la casa.** Un error aquí obre l'aplicació
  sencera. Que cada ruta tingui la seva prova de permisos, no una de sola per
  al blueprint.
- **Canviar el rol d'un mateix a `treballador`** deixaria l'ajuntament sense
  cap administrador. Impedeix-ho: un administrador no es pot degradar ell
  mateix, i no es pot desactivar l'últim administrador actiu.
- **La contrasenya provisional per pantalla**: una sola vegada, sense desar-la
  a la sessió ni al log, i amb l'avís que el correu no és un canal segur.
- **Els festius importats poden trepitjar-ne de propis.** `fusiona` fa dedupe
  per data; digues clarament què ha passat en lloc de sobreescriure en silenci.
- **No posis aquí res que hagi de veure un responsable.** Si dubtes, és de
  l'agent 3D.
