# Encàrrec 4C · Auditoria de seguretat

**Onada 4** · Depèn de: l'onada 3 sencera · Alhora que: 4A, 4D

## Objectiu

Trobar els forats **abans** que ho faci algú altre, amb l'aplicació ja sencera
i a punt de sortir a Internet. Aquesta feina és **buscar problemes**, no
arreglar-los tots.

## Escrius

```
desplegament/AUDITORIA.md      tests/test_seguretat.py
```

I, **només** per a les correccions que qui integra t'autoritzi explícitament
després de llegir l'informe, els fitxers concrets que et digui. Per defecte:
tu informes, no toques.

## Llegeixes

Tot. `DISSENY.md` §2 (rols i regles invariables) i §7 (seguretat). De
referència: `expedients-nomines-beta/desplegament/AUDITORIA_NAS.md` — **el
format d'aquell document és el que ha de tenir el teu**: veredicte al
principi, problemes classificats per gravetat, esmena concreta per a cadascun i
ordre recomanat al final. Va funcionar; imita'l.

## Feina

### 1. Matriu de permisos — la prova de foc

Construeix una taula de **totes** les rutes × **tots** els rols i comprova-la
amb tests reals, un per casella. Per a cada ruta:

- Sense sessió → login (o 200 si és pública, i llavors: hauria de ser-ho?).
- Amb `treballador` → el que toca.
- Amb `responsable` fora del seu àmbit → 403.
- Amb `responsable` dins del seu àmbit → el que toca.
- Amb `admin` → el que toca.

**Cap ruta pot quedar sense provar.** Genera la llista amb
`app.url_map.iter_rules()` perquè no se t'escapi cap ruta nova.

### 2. IDOR sistemàtic

Per a **cada** formulari que enviï un identificador (absència, marcatge,
treballador, assignació, patró, servei, festiu), prova d'enviar l'identificador
d'una altra persona amb una sessió que no hi hauria de tenir accés. **N'hi ha
d'haver un test per cada un.** És la família de fallades més probable en una
aplicació feta per cinc agents diferents.

### 3. Les tres regles invariables

Prova que no es poden saltar per cap camí:

- Ningú resol la seva pròpia sol·licitud, **ni sent administrador**.
- Ningú valida una correcció de marcatge feta per ell mateix.
- Rebutjar una correcció restaura l'original (si no, es poden fer desaparèixer
  hores fent una correcció i rebutjant-la).

### 4. Repàs de la llista clàssica

CSRF a tots els POST · capçaleres a totes les respostes · `no-store` on toca i
cache als estàtics · open redirect al `next` · injecció d'SQL (busca qualsevol
SQL construït amb format de cadena) · injecció al log · XSS (busca `|safe` i
`Markup` a les plantilles: **cada aparició s'ha de justificar**) · enumeració
d'usuaris a `/login` i a `/recupera` · límit d'intents · caducitat de sessió ·
`FLASK_DEBUG` mai actiu per defecte · secrets als logs o als missatges d'error ·
`DOMINI_PUBLIC` rebutjant les peticions amb un altre `Host`.

### 5. Independència i cost — específic d'aquest projecte

Tres comprovacions que no són de seguretat clàssica però que l'usuari ha posat
com a condicions dures:

- **Cap API de Google fora de l'adaptador.**
  `grep -rln "google" --include=*.py . | grep -v rebost_firestore` ha de
  sortir buit. Si no, el projecte ha quedat lligat a Firebase i la sortida
  d'emergència ja no existeix.
- **Cap referència a cap altra aplicació de l'usuari** en temps d'execució:
  cap ruta a `expedients-nomines-*`, cap fitxer compartit, cap import.
  Comprova també que cap agent no hi hagi **escrit** res (`git status` en
  aquelles carpetes).
- **Cap consulta composta sense el seu índex** a `desplegament/
  firestore.indexes.json`. Recorre `magatzem/` buscant les crides a
  `consulta()` amb més d'un filtre o amb filtre més ordenació, i contrasta-les
  una per una. **Aquesta és la fallada més probable del projecte sencer**:
  passa totes les proves i peta el dia del desplegament.
- **Pressupost de lectures**: per a cada pantalla, compta les lectures que fa i
  contrasta-ho amb `DISSENY.md` §3.5. Si alguna se n'ha anat, és un punt de
  l'auditoria: no és un problema de rendiment, és un problema de factura.

### 6. Protecció de dades

- Que el registre d'activitat no contingui dades personals més enllà del login.
- Que el service worker no cachegi cap pàgina (llegeix `sw.js` i comprova-ho).
- Que cap resposta amb dades porti `Cache-Control` permissiu.
- Que no hi hagi cap dada real enlloc del repositori: recorre'l buscant patrons
  de NIF, correus que no siguin `@exemple.cat` i noms de persona.
- Que no s'hagi colat cap crida a un servei extern fora de la importació de
  festius.
- Que les regles de Firestore deneguin tot l'accés de client.

### 7. L'informe

`desplegament/AUDITORIA.md`, amb el format de la referència:

- **Veredicte** al principi, en una línia i sense adornar: es pot exposar a
  Internet o no.
- **A. Bloquejants** (impedeixen sortir a producció).
- **B. Funcionals** (arrencaria però no faria el que ha de fer).
- **C. Seguretat** (contradiuen decisions ja preses).
- **D. A verificar al desplegament** (no comprovable des d'aquí).
- **E. Ordre recomanat** de correcció.

Cada punt, amb l'esmena concreta. Res de «caldria revisar la seguretat de les
sessions»: digues quin fitxer, quina línia i què s'hi ha de fer.

## Acceptació

- [ ] Un test per cada casella de la matriu de rutes × rols, generada
      automàticament del `url_map` (cap ruta sense cobrir).
- [ ] Un test d'IDOR per cada formulari amb identificador.
- [ ] Les tres regles invariables, provades.
- [ ] `AUDITORIA.md` escrit amb el format demanat i un veredicte clar.
- [ ] `pytest -q` verd **excepte** els tests que documentin forats reals: aquests
      **han de fallar** i han d'estar marcats amb `@pytest.mark.xfail(strict=True)`
      i un comentari que remeti al punt de l'auditoria. Un forat trobat és un
      test que falla, no un paràgraf en un document.

## Paranys

- **No arreglis res pel teu compte.** Tocaries fitxers de cinc agents alhora i
  la traçabilitat se'n va en orris. Informa; qui integra reparteix.
- **Un veredicte tou no ajuda ningú.** Si l'aplicació no s'ha d'exposar encara,
  digues-ho amb totes les lletres, com va fer l'auditoria del projecte anterior de l'usuari.
- **No et limitis al que ja hi ha a la llista.** La llista és el mínim.
- **Compte amb els falsos positius**: comprova cada troballa abans d'escriure-la.
  Un informe amb soroll és un informe que ningú acaba de llegir.
