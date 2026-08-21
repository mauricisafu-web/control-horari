# Com es desplega — passos exactes

> Escrit per a algú que no ha vist mai aquest projecte. Segueix-ho en ordre i
> no te'n saltis cap.
>
> **Objectiu de cost: 0,00 €.** Tot cau dins del nivell gratuït permanent.
> El pas 1 és l'alerta de pressupost precisament perquè te n'assabentis el
> mateix dia si això deixés de ser cert.

---

## 0. Provar-ho en local (fes-ho SEMPRE primer)

No es toca res de Google fins que l'aplicació no s'hagi vist funcionar en una
màquina que controlem. És la lliçó que ha costat setmanes en aquest projecte.

```bash
docker compose -f desplegament/docker-compose.yml up --build
```

Obre `http://localhost:8080` i entra amb `admin01` / `Prova-1234` (dades
sintètiques). Comprova, com a mínim: fitxar entrada i sortida, demanar
vacances amb un compte i aprovar-les amb un altre, i que el saldo quadra.

Sense Docker, també funciona directament:

```bash
DADES_PROVA=1 python app_web.py
```

---

## 1. Compte de Google i protecció de despesa

**Aquest pas el fa l'usuari: implica crear un compte i posar-hi una targeta.**

1. Crear un projecte a <https://console.firebase.google.com>.
2. Activar el **pla Blaze** (de pagament per ús). El pla gratuït no permet
   Cloud Run. La factura prevista és de 0,00 €, però la targeta hi ha de ser.
3. **Abans de res més**: crear una **alerta de pressupost d'1 €** a
   *Facturació → Pressupostos i alertes*, amb avís per correu al 50 %, 90 % i
   100 %.
4. Crear la base de dades de **Firestore en mode natiu**, amb la ubicació a
   **`eur3`** o **`europe-west1`** (la ubicació **no es pot canviar després**).

## 2. Eines

```bash
npm install -g firebase-tools
```

També cal `gcloud` (<https://cloud.google.com/sdk/docs/install>) i, per a
l'emulador de Firestore, **Java**.

```bash
gcloud auth login && firebase login
```

Copia `.firebaserc.example` a `.firebaserc` i posa-hi l'identificador del
projecte.

## 3. Regles i índexs de Firestore

```bash
firebase deploy --only firestore:rules,firestore:indexes
```

Els índexs triguen uns minuts a construir-se. **Espera't que estiguin
llestos**: si no, les consultes fallen amb un error d'índex que falta.

Comprova que les regles deneguen tot l'accés de client: a la consola, pestanya
*Regles → Simulador*, qualsevol lectura ha de sortir denegada.

## 4. Política de caducitat del registre d'activitat

A la consola de Firestore, *Temps de vida (TTL)*: col·lecció `activitat`, camp
`caduca_el`. Això esborra sol el registre d'accessos al cap d'un any,
gratuïtament i sense codi.

## 5. Secret de sessió

```bash
python -c "import secrets; print(secrets.token_hex(32))" | gcloud secrets create control-horari-secret --data-file=-
```

## 6. Desplegament del servidor

```bash
gcloud run deploy control-horari --source . --region europe-west1 --min-instances 0 --max-instances 2 --cpu 1 --memory 512Mi --concurrency 20 --allow-unauthenticated --set-env-vars TZ=Europe/Madrid,REBOST=firestore,PROJECTE_FIREBASE=EL-TEU-PROJECTE,DARRERE_PROXY=1,COOKIE_SECURE=1,DOMINI_PUBLIC=EL-TEU-PROJECTE.web.app --set-secrets SECRET_KEY=control-horari-secret:latest
```

> ⚠️ **`--min-instances 0` NO ES TOCA.** Posar-hi un 1 fa que la instància
> estigui sempre encesa i el projecte passa a costar **10-15 € al mes**. El
> preu d'escalar a zero és que la primera petició del dia triga uns segons.

Dona-li permís al compte de servei per llegir Firestore i el secret
(*IAM → Cloud Run Service Agent*: `Cloud Datastore User` i
`Secret Manager Secret Accessor`).

## 7. Hosting

```bash
firebase deploy --only hosting
```

Ja tens l'aplicació a `https://EL-TEU-PROJECTE.web.app`.

## 8. Primer administrador

L'aplicació arrenca amb el magatzem buit. Per crear el primer compte, arrenca
temporalment amb `REGISTRE_OBERT=1`, o bé fes-ho des d'una consola local
apuntada al projecte:

```bash
REBOST=firestore PROJECTE_FIREBASE=EL-TEU-PROJECTE python eines/gestiona_comptes.py afegeix
```

Després desactiva `REGISTRE_OBERT`.

---

## 9. Verificació — no donis res per bo sense fer això

- [ ] **Des d'un mòbil amb dades mòbils**, no amb la wifi de l'ajuntament:
      entrar, fitxar una entrada i una sortida, i veure el saldo.
- [ ] Instal·lar la PWA a la pantalla d'inici (Android amb Chrome, iPhone amb
      Safari) i comprovar que s'obre sense barra de navegador.
- [ ] Cronometrar l'arrencada en fred: deixar-ho una hora sense tocar i mirar
      quant triga la primera petició.
- [ ] Comprovar que la URL directa `https://control-horari-XXXX.run.app` **és
      rebutjada** (403): és la porta del darrere que tanca `DOMINI_PUBLIC`.
- [ ] Un client anònim no pot llegir res de Firestore.
- [ ] **Al cap d'una setmana**: mirar el consum a la consola. Ha de ser molt
      per sota dels límits gratuïts. Si no ho és, aturar-se i trobar quina
      pantalla llegeix de més abans de donar d'alta ningú més.

## 10. Còpies de seguretat

```bash
gcloud firestore export gs://EL-TEU-BUCKET/copies/$(date +%Y%m%d)
```

**Setmanal, no diària**: les exportacions es facturen com a lectures i no
entren al nivell gratuït (amb aquest volum són cèntims, però convé mirar-ho a
la factura del primer mes). Descarrega-la i guarda-la **fora de Google**: una
còpia dins del mateix proveïdor no és una còpia de seguretat.

I **prova la restauració** abans de posar-hi dades reals, i un cop l'any. Un
sistema de còpies que no s'ha provat mai no és un sistema de còpies.

## 11. Avaries conegudes

### «El formulari ha caducat» en entrar (error 400)

Va passar de debò el 2026-08-21, amb l'aplicació ja desplegada.

**Causa.** Firebase Hosting només reenvia cap a Cloud Run la galeta que es diu
exactament `__session`; la resta les elimina pel camí. Amb el nom per defecte
de Flask (`session`), la sessió no arriba mai al servidor: cada petició en
comença una de nova, el testimoni CSRF del formulari no quadra amb el de la
sessió i entrar és impossible. En local no es veu, perquè en local no hi ha
Hosting pel mig.

**Solució.** `SESSION_COOKIE_NAME="__session"` a `app_web.py`. Ho protegeixen
dues proves a `tests/test_esquelet.py`; si algú les toca, l'aplicació
desplegada deixa de funcionar tot i que en local sembli correcta.

**Com comprovar-ho des del terminal.** Dues trampes van fer-me creure que la
correcció no havia funcionat:

- `curl -c fitxer.txt` **no desa el pot de galetes** en aquest Windows. Passa
  la galeta a mà amb `-H "Cookie: __session=..."`.
- Flask-WTF, en HTTPS, exigeix la capçalera `Referer` (`WTF_CSRF_SSL_STRICT`).
  Un `curl` pelat no l'envia i el CSRF falla encara que tot estigui bé. Cal
  afegir-hi `-H "Referer: https://EL-DOMINI/login"`.

Amb les dues coses, el POST amb una contrasenya dolenta ha de respondre
«l'usuari o la contrasenya no són correctes» — que vol dir que el CSRF ha
passat.
