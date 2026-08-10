# Desplegament a Firebase — disseny i passos

> Decisió de l'usuari (2026-08-05): l'aplicació s'allotja a **Firebase** i
> **no pot costar ni un euro**. L'agent **2C** prepara les peces; l'agent
> **5B** les executa de debò amb l'usuari.
>
> Lliçó de les dues temptatives fallides (Tailscale Funnel i Oracle Cloud):
> **no es dona res per bo fins que no s'ha vist funcionar des d'un mòbil amb
> dades mòbils, fora de la xarxa de l'ajuntament.**

---

## 1. Arquitectura

```
   Mòbil personal del treballador (dades mòbils, des de casa)
        │  HTTPS
        ▼
   Firebase Hosting            <projecte>.web.app
     · certificat TLS automàtic i renovat sol
     · CDN, HTTP/2 — i, sobretot, l'HTTPS que fa la PWA instal·lable
     · cap router, cap DDNS, cap certificat per mantenir
        │  rewrite "**"
        ▼
   Cloud Run  (regió de la UE)
     · imatge Docker: Flask + gunicorn
     · min-instances = 0   ← escala a zero: de nit i els caps de setmana,
                             no corre res i no es factura res
     · max-instances = 2   ← Firestore no té el problema del sol escriptor
     · sense disc: tot l'estat viu a Firestore
        │
        ▼
   Firestore  (regió de la UE, mode natiu)
     · l'aplicació hi parla NOMÉS pel port de magatzem/rebost.py
     · regles de seguretat: DENEGA-HO TOT (cap navegador hi entra mai)
     · política TTL sobre `activitat` (esborrat automàtic i gratuït)
        │
        └── exportació setmanal FORA de Google
```

**Cap NAS, cap VPS, cap túnel, cap port obert al router.** Aquesta és la
diferència respecte de tot el que s'havia intentat abans.

---

## 2. Els 0 € — d'on surten i com es protegeixen

### El nivell gratuït que fem servir és PERMANENT, no una prova de 90 dies

| Servei | Nivell gratuït permanent | Ús previst amb 24 treballadors |
|---|---|---|
| **Firestore** | 50.000 lectures/dia · 20.000 escriptures/dia · 1 GiB | ~3.000 lectures i ~150 escriptures/dia · ~30 MB als 4 anys |
| **Cloud Run** | 2 M peticions/mes · 180.000 vCPU-s/mes · 360.000 GiB-s/mes | ~6.000 peticions/mes · ~3.000 vCPU-s |
| **Hosting** | 10 GB emmagatzemats · 360 MB/dia de trànsit | testimonial |
| **Secret Manager** | 6 secrets actius | 2 |

Marge: fem servir entre un **5 % i un 8 %** del límit més ajustat. Perquè
això es mantingui, hi ha dues regles de disseny que **no són negociables**:

1. **`min-instances = 0`.** Una sola instància sempre encesa costaria 10-15 €
   al mes. És exactament la despesa que aquesta decisió elimina.
2. **El pressupost de lectures de `DISSENY.md` §3.5.** El model de dades està
   fet per llegir poc (identificadors significatius, festius i saldos agrupats
   per any). Qualsevol pantalla nova s'hi ha de contrastar.

### El que has de saber abans de dir que sí

- **Cal un compte de facturació (pla Blaze) amb una targeta.** El pla gratuït
  (Spark) no permet Cloud Run. La factura prevista és de **0,00 €**, però la
  targeta hi ha de ser. No hi ha cap manera d'evitar-ho mantenint un servidor
  propi amb Python.
- **Protecció obligatòria, el primer dia**: alerta de pressupost a **1 €** amb
  avís per correu, i **quotes** a la consola per limitar les peticions. Si
  algun dia una configuració errònia o un atac disparessin l'ús, ho saps el
  mateix dia.
- **Preu real d'escalar a zero**: la primera petició del dia triga **entre 2 i
  5 segons** (arrencada en fred del contenidor). Amb dues o tres entrades al
  dia per persona, és perfectament assumible; i és el que fa que sigui gratis.

### Si algun dia deixés de ser gratis

El port de `magatzem/rebost.py` permet escriure un tercer adaptador (SQLite o
Postgres) sense tocar `core/` ni `web/`. La sortida està preparada per
disseny. **Cap crida a una API de Google pot aparèixer mai fora de
`magatzem/rebost_firestore.py`** — mantenir-ho és responsabilitat de tots els
agents, i l'agent 4C ho ha de comprovar.

---

## 3. El que s'ha de tramitar (començar el dia 1)

| # | Tràmit | Qui | Bloqueja |
|---|---|---|---|
| T1 | Projecte de Firebase, pla Blaze, **regió de la UE** | Usuari | El desplegament (onada 5) |
| T2 | **Alerta de pressupost a 1 €** i quotes | Usuari | Res, però fes-ho el primer dia |
| T3 | Acceptar el **Data Processing Addendum** de Google Cloud | Usuari + DPD | Posar-hi dades **reals** |
| T4 | **Vistiplau del DPD** (documents de l'agent 4D) | DPD | Posar-hi dades **reals** |

**T3 i T4 no bloquegen el desenvolupament ni el desplegament de proves**: tot
es desplega i es valida amb dades sintètiques. Aquesta separació és deliberada.

### El canvi de qualificació, dit clar al DPD

El principi del projecte anterior era «les dades no surten del servidor de
l'ajuntament», i amb aquest criteri es va descartar Cloudflare Tunnel. Amb
Firebase, Google **allotja** les dades: és **encarregat del tractament** de ple
dret (art. 28 RGPD). Cal DPA signat, regió de la UE i entrada nova al RAT.

- **A favor**: aquesta aplicació no toca mai nòmines ni factures; cap categoria
  especial de l'art. 9; ni ubicació ni biometria al fitxatge; el conjunt de
  dades és mínim.
- **En contra, sense amagar-ho**: el registre de presència diària és més
  revelador que un saldo de vacances, i és un proveïdor nou i internacional.

---

## 4. Peces a construir (agent 2C)

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

# tzdata: ni Windows ni les imatges slim porten la base de zones, i
# core/model.py fa ZoneInfo('Europe/Madrid') en importar-se → sense això
# l'aplicació NI ARRENCA. ca-certificates: SMTP i importació de festius.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Madrid

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

ENV REBOST=firestore DARRERE_PROXY=1 COOKIE_SECURE=1 SESSIO_MINUTS=20
# Cloud Run injecta $PORT. Dos workers: amb Firestore no hi ha cap fitxer
# compartit, però el comptador d'intents de login viu a la memòria del
# procés — amb 2 workers un atacant tindria el doble d'intents. Per això
# UN worker i fils: el límit es manté exacte.
CMD exec gunicorn -w 1 --threads 8 -b 0.0.0.0:${PORT:-8080} 'app_web:crea_app()'
```

### `.dockerignore` — el fitxer més important d'aquest encàrrec

Ha d'excloure com a mínim: `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`,
`dades_prova/`, `logs/`, `.secret_key`, `config.ini`, `.env`, `public/`,
`.firebase/`, `encarrecs/`, `incidencies/`, `*.json` de credencials.

### `firebase.json`

```json
{
  "hosting": {
    "public": "public",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      { "source": "**",
        "run": { "serviceId": "control-horari", "region": "europe-west1" } }
    ]
  },
  "firestore": {
    "rules": "desplegament/firestore.rules",
    "indexes": "desplegament/firestore.indexes.json"
  }
}
```

`public/` conté només un `robots.txt` amb `Disallow: /`. Tota la resta,
inclosos `/static/*`, `/sw.js` i `/manifest.webmanifest`, la serveix Flask.

> **A verificar el dia del desplegament**: la llista de regions de Cloud Run
> admeses pels *rewrites* de Hosting canvia amb el temps. `europe-west1`
> (Bèlgica) ho ha estat sempre i és a la UE, que és el requisit. Si la regió no
> hi és, Hosting falla en desplegar — no ho descobreixis amb dades reals a dins.

### `desplegament/firestore.rules` — denega-ho tot

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // L'aplicació hi entra amb l'SDK d'administrador, que se salta les
    // regles. CAP navegador parla mai amb Firestore directament: tota
    // l'autorització viu al servidor, a web/. Aquestes regles hi són perquè,
    // si algú filtrés una clau de client, no serveixi absolutament de res.
    allow read, write: if false;
  }
}
```

### `desplegament/firestore.indexes.json`

Els sis índexs compostos de `DISSENY.md` §3.3. **Sense això, les consultes
passen les proves (en memòria) i fallen en producció.**

### Política TTL

Camp `caduca_el` de la col·lecció `activitat`, configurat a la consola de
Firestore. Esborra el log d'activitat sol, gratis i sense codi.

### Comandes

```bash
gcloud run deploy control-horari --source . --region europe-west1 --min-instances 0 --max-instances 2 --cpu 1 --memory 512Mi --concurrency 20 --allow-unauthenticated --set-env-vars TZ=Europe/Madrid,REBOST=firestore,PROJECTE_FIREBASE=EL-TEU-PROJECTE,DARRERE_PROXY=1,COOKIE_SECURE=1,DOMINI_PUBLIC=EL-TEU-PROJECTE.web.app --set-secrets SECRET_KEY=control-horari-secret:latest
```

```bash
firebase deploy --only hosting,firestore:rules,firestore:indexes
```

---

## 5. Seguretat pròpia d'aquest desplegament

| Risc | Mitigació |
|---|---|
| **Algú entra per la URL directa de Cloud Run** i se salta Hosting. Els *rewrites* obliguen a `--allow-unauthenticated`. | L'aplicació rebutja tota petició amb un `Host` diferent de `DOMINI_PUBLIC` (`DISSENY.md` §7). I, sobretot, té la seva pròpia autenticació: aquella URL no dona accés a res. |
| Secrets a la imatge | `SECRET_KEY` només per Secret Manager. Mai al `Dockerfile` ni al compose. |
| Algú accedeix a Firestore des d'un navegador | Regles «denega-ho tot». No hi ha cap SDK de client a l'aplicació. |
| Força bruta al login | Límit d'intents per IP (necessita `DARRERE_PROXY=1`) + TOTP obligatori per a responsables i administradors. |
| Despesa inesperada | Alerta de pressupost a 1 € i quotes de peticions. |
| Pèrdua de dades | Exportació setmanal de Firestore a un bucket **i** descàrrega fora de Google. Una còpia dins del mateix proveïdor no és una còpia de seguretat. |

---

## 6. Còpia de seguretat i recuperació

- **Exportació setmanal** de Firestore (`gcloud firestore export`) a un bucket
  de la UE. Atenció: les exportacions **no entren al nivell gratuït de
  Firestore** —es facturen com a lectures— però amb aquest volum són cèntims;
  tot i així, **programa-la setmanal, no diària**, i comprova-ho a la factura
  del primer mes.
- **Còpia fora de Google**: descarregar l'exportació a l'ordinador de
  l'ajuntament i desar-la xifrada.
- **Provar la restauració** abans de la posada en marxa i un cop l'any. Un
  sistema de còpies que no s'ha provat mai no és un sistema de còpies.

---

## 7. Llista de verificació (agent 5B, amb l'usuari)

- [ ] Projecte de Firebase creat, pla Blaze actiu, **regió de la UE**.
- [ ] **Alerta de pressupost a 1 €** configurada i provada.
- [ ] Regles de Firestore desplegades i comprovades: un client anònim **no**
      pot llegir res.
- [ ] Els sis índexs compostos creats.
- [ ] Política TTL de `activitat` activada.
- [ ] `tests/integracio/` verd contra l'**emulador** (requereix Node.js i Java;
      instal·lar-los és part de l'onada 5A).
- [ ] `docker compose up` funciona **en local** i s'hi pot fitxar (onada 5A).
- [ ] Desplegament a Cloud Run correcte i `/` respon.
- [ ] `firebase deploy` fet i el domini `*.web.app` respon.
- [ ] **Des d'un mòbil amb dades mòbils, fora de la xarxa de l'ajuntament**:
      s'hi entra, es fitxa una entrada i una sortida, i es veu el saldo.
- [ ] La PWA s'instal·la a la pantalla d'inici (Android i iPhone).
- [ ] Mesurada l'arrencada en fred real (ha de ser de pocs segons).
- [ ] La URL directa de `*.run.app` és rebutjada per `DOMINI_PUBLIC`.
- [ ] Exportació setmanal configurada i **restauració provada**.
- [ ] **Consultat el consum a la consola després d'una setmana**: ha de ser
      molt per sota dels límits gratuïts. Si no ho és, atura't i revisa quina
      pantalla llegeix de més abans de continuar.
- [ ] Només llavors: vistiplau del DPD, altes reals i pilot amb 2-3 persones.
