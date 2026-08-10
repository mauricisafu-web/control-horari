# Encàrrec 2C · Desplegament (Docker, Firebase, Firestore)

**Onada 2** · Depèn de: 0A · Alhora que: 2A, 2B, 2D
· **No toca gens el codi de l'aplicació.** Es pot avançar quan es vulgui.

## Objectiu

Deixar preparat tot el que cal per desplegar, i **provat en local amb Docker**.
No desplegues res de debò: això és de l'onada 5, amb l'usuari. I tampoc no et
cal cap compte de Google per fer aquest encàrrec.

## Escrius

```
desplegament/Dockerfile              desplegament/docker-compose.yml
desplegament/firestore.rules         desplegament/firestore.indexes.json
desplegament/DESPLEGAMENT.md         desplegament/MANTENIMENT.md
.dockerignore                        firebase.json
.firebaserc.example                  public/robots.txt
```

`desplegament/FIREBASE.md` ja existeix i és el teu disseny: **segueix-lo, no el
reescriguis**. Pots corregir-hi errors de fet que descobreixis provant, i has
d'anotar a `incidencies/2C.md` tot el que no encaixi.

## Llegeixes

`desplegament/FIREBASE.md` sencer (§4 té el codi de partida), `DISSENY.md`
§3.3 (índexs), §3.5 (pressupost de lectures), §9 i §11.

## Feina

### 1. `firestore.indexes.json` — el fitxer que decideix si això funciona

Els **sis** índexs compostos de `DISSENY.md` §3.3, en el format de Firebase.
Sense això, les consultes de l'agent 1A passen les proves (que corren en
memòria) i **fallen en producció** amb un error d'índex que falta. És el
parany estructural d'aquest projecte i tu ets qui el tanca.

Al final de l'onada 3, **torna a repassar** que cap agent no hagi introduït
cap consulta composta que no hi sigui. Deixa-ho anotat com a tasca teva.

### 2. `firestore.rules` — denega-ho tot

Tal com és a `FIREBASE.md` §4, amb el comentari que ho explica: l'aplicació hi
entra amb l'SDK d'administrador (que se salta les regles), i cap navegador
parla mai amb Firestore. Les regles hi són perquè, si algú filtrés una clau de
client, no serveixi absolutament de res.

### 3. `Dockerfile` i `.dockerignore`

El `.dockerignore` és **el fitxer més important d'aquest encàrrec**: el context
de construcció és la carpeta sencera, i un `COPY . /app` a seques hi ficaria
dades de prova i secrets. Ha d'excloure, com a mínim: `.git/`, `.venv/`,
`__pycache__/`, `.pytest_cache/`, `dades_prova/`, `logs/`, `.secret_key`,
`config.ini`, `.env`, `public/`, `.firebase/`, `encarrecs/`, `incidencies/`, i
qualsevol `*.json` de credencials.

Comprova-ho de debò després de construir:

```bash
docker run --rm --entrypoint sh control-horari -c "ls -a /app | grep -E 'secret|env|credencial' || echo 'cap secret a la imatge: correcte'"
```

### 4. `docker-compose.yml` per a la prova local

Un sol servei, amb **`REBOST=memoria`** per defecte perquè es pugui provar
sense cap compte de Google, i el port 8080 publicat. Amb una variant comentada
per apuntar a l'emulador (`FIRESTORE_EMULATOR_HOST`) quan l'onada 5A el tingui.

**Cap volum de dades**: aquesta aplicació no desa res al disc. Si et veus
muntant un volum, alguna cosa no quadra amb el disseny.

### 5. `DESPLEGAMENT.md` i `MANTENIMENT.md`

- **`DESPLEGAMENT.md`**: els passos exactes, en ordre, amb les ordres
  copiables, escrit per a algú que no ha vist mai el projecte. Inclou-hi
  **com crear l'alerta de pressupost a 1 €**, que és el primer que s'ha de fer.
- **`MANTENIMENT.md`**: què s'ha de fer i cada quant — actualització de
  dependències (trimestral), **revisió del consum a la consola de Google**
  (mensual el primer trimestre, després trimestral), prova de restauració de
  la còpia (anual), i revisió del log d'activitat. Amb un buit marcat per a
  qui n'és responsable: ho decideix l'usuari.

## Acceptació

- [ ] `docker build` funciona.
- [ ] La imatge **no conté** cap secret ni cap fitxer de `dades_prova/`
      (comprovat amb l'ordre de dalt, no per fe).
- [ ] `docker compose up` aixeca l'aplicació, s'hi arriba per
      `http://localhost:8080` i funciona **sense cap compte de Google**.
- [ ] Dins del contenidor, `python -c "from core import model; print(model.ZONA)"`
      funciona (`tzdata` instal·lat) i `date` dona **hora peninsular**, no UTC.
- [ ] `firestore.indexes.json` té els sis índexs de `DISSENY.md` §3.3.
- [ ] `firestore.rules` denega tot l'accés de client.
- [ ] `firebase.json` amb el *rewrite* a Cloud Run i `public/` només amb el
      `robots.txt`.
- [ ] Les ordres de `gcloud run deploy` de `DESPLEGAMENT.md` porten
      **`--min-instances 0`**. Si algú hi posa 1, la factura deixa de ser zero:
      deixa-ho escrit en majúscules al costat.
- [ ] `DESPLEGAMENT.md` es pot seguir de dalt a baix sense saber res del
      projecte.

## Paranys — tots són errors que ja s'han comès en aquest projecte

1. **El contenidor sense el codi.** En un projecte anterior de l'usuari, el
   `Dockerfile` només copiava `requirements.txt` i el contenidor entrava en
   bucle de reinici amb `ModuleNotFoundError`. **Comprova que `app_web.py` és
   dins de la imatge.**
2. **`tzdata` que falta.** Les imatges `slim` no porten la base de zones i
   `TZ` s'ignora en silenci. Aquí, a més, l'aplicació **ni arrenca**
   (`core/model.py` fa `ZoneInfo` en importar-se), cosa que almenys ho fa
   evident de seguida.
3. **Índexs no declarats.** L'equivalent modern del punt anterior: funciona en
   proves i peta en producció. És el teu encàrrec evitar-ho.
4. **`--min-instances 1`.** Una instància sempre encesa són 10-15 € al mes i
   trenca el requisit dur del projecte.
5. **Provar-ho tot en local abans de tocar res de debò.** És la lliçó que va
   costar setmanes amb el túnel que no funcionava: no donis per bo res que no
   hagis vist funcionar.
6. **No hi posis nginx.** Firebase Hosting ja fa el TLS. Afegir-hi un proxy
   propi tornaria a portar el problema dels certificats que aquesta decisió
   elimina.
7. **No hi posis cap disc ni cap volum de dades.** Tot l'estat és a Firestore.
