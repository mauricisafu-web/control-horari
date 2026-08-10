# Encàrrec 5 · Desplegament real i posada en marxa

**Onada 5** · Depèn de: les onades 0 a 4 · **Seqüencial i amb l'usuari
present.** Aquí es toquen coses que costen diners i que afecten persones
reals: cap pas s'automatitza sense confirmació.

---

## 5A · Prova d'extrem a extrem amb Docker, en local

**Objectiu**: no repetir el que va passar amb Tailscale i amb Oracle. No es
toca Google fins que tot funcioni en una màquina que controlem.

**Escrius**: `desplegament/*` (correccions), `ESTAT.md`.

### Feina

0. **Instal·lar Node.js i Java** (fins ara no calien: tot el desenvolupament
   ha anat amb el magatzem en memòria). Són necessaris per a
   `firebase-tools` i per a l'emulador de Firestore. Instal·lar també
   `gcloud`. Si no hi ha permisos d'administrador a l'ordinador, **atura't
   aquí i digues-ho**: és un bloqueig real, no una excusa.
1. **`firebase emulators:start --only firestore`** i fer córrer
   `tests/integracio/` (agent 1A). **Aquesta és la porta que valida tot el
   muntatge**: fins aquí, tot s'ha provat contra memòria. Si aquí surt algun
   índex que falta o alguna consulta que Firestore no admet, es corregeix
   **abans** de continuar.
2. `docker build` i `docker compose up` amb el que ha deixat l'agent 2C, i
   poblar amb `eines/dades_prova.py --recrea`.
3. Recorregut manual sencer, al navegador:
   - entrar amb un compte de treballador; canviar la contrasenya provisional;
   - fitxar entrada, pausa, represa i sortida; comprovar les hores del dia;
   - demanar unes vacances; entrar amb el responsable; aprovar-les;
   - comprovar que el dia de vacances surt cobert al resum d'hores;
   - fer una correcció de marcatge; validar-la amb el responsable;
   - **rebutjar-ne una altra** i comprovar que les hores tornen a ser les d'abans;
   - exportar el registre en CSV i en PDF;
   - instal·lar la PWA des de `localhost`.
4. **Prova de recuperació**: aturar el contenidor, esborrar-lo, tornar-lo a
   aixecar amb el volum, i comprovar que hi és tot.
5. Comprovar l'hora: fitxar i veure que l'hora registrada és **la del rellotge
   de la paret**, no dues hores menys.

### Fet quan

Tot el recorregut passa sense cap error i sense haver de tocar res a mà. Si
alguna cosa falla, es corregeix i **es torna a començar el recorregut sencer**.

---

## 5B · Desplegament a Firebase

**Objectiu**: que l'aplicació sigui a Internet amb dades **sintètiques**, i
verificada des de fora.

**Escrius**: `desplegament/*`, `ESTAT.md`. **Res del codi de l'aplicació.**

### Feina

Segueix `desplegament/FIREBASE.md` §7, en aquest ordre i sense saltar-te'n cap:

1. Projecte de Firebase, pla Blaze, **regió de la UE**.
2. **Alerta de pressupost a 1 €**, abans que res més. Si algun dia una
   configuració errònia dispara el consum, ho has de saber el mateix dia.
3. Regles i índexs de Firestore desplegats; política TTL de `activitat`
   activada. Comprovar que un client anònim **no pot llegir res**.
4. Secret a Secret Manager (`SECRET_KEY`).
5. `gcloud run deploy` amb **totes** les opcions de `FIREBASE.md` §4.
   Comprova-ho: **`--min-instances 0`** (si hi ha un 1, la factura deixa de
   ser zero).
6. `firebase deploy --only hosting,firestore:rules,firestore:indexes`.
7. **Verificació des d'un mòbil amb dades mòbils, no amb la wifi de
   l'ajuntament.** Aquest pas no és opcional: és exactament el que no es va
   fer amb el túnel i el que va fer perdre setmanes.
8. Instal·lar la PWA a Android i a iPhone.
9. **Mesurar l'arrencada en fred de debò**: deixar-ho una hora sense tocar i
   cronometrar la primera petició. Ha de ser de pocs segons; si són molts més,
   cal saber-ho abans que ho descobreixi la plantilla.
10. Comprovar que la URL directa de `*.run.app` és rebutjada per `DOMINI_PUBLIC`.
11. Configurar l'exportació setmanal fora de Google i **provar-ne la
    restauració**.

### Fet quan

La llista de verificació de `FIREBASE.md` §7 està tota marcada, amb dades
sintètiques. **Cap dada real encara.**

### I una setmana després

**Mirar el consum a la consola de Google.** Ha de ser molt per sota dels
límits gratuïts. Si no ho és, aturar-se i trobar quina pantalla llegeix de
més **abans** de donar d'alta ningú més.

---

## 5C · Posada en marxa

**Objectiu**: que la plantilla ho faci servir. És el pas que depèn de persones,
no de tecnologia.

**Escrius**: `ESTAT.md`, `compliment/*` (actualitzacions).

### Feina, en ordre estricte

1. **Vistiplau del DPD** amb els documents de l'agent 4D. Fins aquí, res de
   dades reals. Si el DPD posa condicions, s'apliquen abans de continuar.
2. **Buidar les dades sintètiques** i crear la configuració real: serveis,
   festius de l'any (importats), patrons d'horari acordats.
3. **Nota informativa** als treballadors amb la URL final. **No s'envia fins
   que l'usuari ho confirmi expressament** — instrucció seva, ja donada abans
   en aquest projecte.
4. **Pilot amb 2-3 persones**, una de cada servei, durant una o dues setmanes.
   Recollir el que no s'entén: si algú no sap si ha fitxat, és un problema de
   disseny, no de l'usuari.
5. **Altes de tothom** amb contrasenya provisional i canvi obligatori.
   TOTP obligatori per a responsables i administradors.
6. **Revisió al cap d'un mes**: log d'accessos, incidències, temps de resposta,
   marcatges oblidats. Ajustar el que calgui.

### Fet quan

Tots els treballadors donats d'alta i un cicle mensual complet fet amb
l'aplicació: fitxatges, correccions, unes vacances demanades i aprovades, i el
registre exportat.

---

## Paranys de tota l'onada

- **No desplegar mai un divendres** ni el dia abans d'unes vacances.
- **No posar dades reals abans del vistiplau del DPD.** És l'única condició que
  no admet excepcions per pressa.
- **No donar per bo res que no s'hagi vist funcionar** des d'un dispositiu de
  fora de l'ajuntament. Dues vegades s'ha donat per bo un accés extern que no
  funcionava.
- **Guardar el rebut de tot**: quina versió s'ha desplegat, quan, i què s'ha
  verificat. `ESTAT.md` és per a això.
- **La factura ha de ser 0,00 €.** Si el primer mes no ho és, alguna cosa del
  disseny s'ha trencat: no ho pagis i esbrina-ho. L'alerta de pressupost a 1 €
  hi és precisament per assabentar-te'n abans que sigui una quantitat.
- **`--min-instances 0`.** Si algú el puja a 1 «perquè vagi més ràpid», el
  projecte passa a costar 10-15 € al mes.
