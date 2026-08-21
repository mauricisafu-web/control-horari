# Encàrrec · Exportació de treballadors i enviament de credencials, dins de nòmines

**Per a l'altre xat (el de `expedients-nomines-beta`). Aquest document viu al
repositori del control horari perquè és qui en defineix el contracte, però
tota la feina que descriu es fa a `nòmines-beta`.**

---

## 0. Per què, i on encaixa cada app

Decisió d'arquitectura de l'ajuntament (2026-08-21):

> **El servidor de l'ajuntament no ha d'intercanviar dades per Internet.**

D'aquí surt el repartiment:

| | **nòmines-beta** (local, LAN) | **control-horari** (Firebase, públic) |
|---|---|---|
| Nòmines, factures, expedients | ✅ s'hi queda | ❌ mai |
| Historial i repositori de nòmines | ✅ s'hi queda | ❌ mai |
| Enviament de correus (SMTP) | ✅ **l'única sortida a Internet** | ❌ no en té |
| Sol·licitud i autorització de vacances i permisos | ⏸️ es congela | ✅ passa aquí |

`nòmines` continua sent la font de veritat de **qui treballa a l'ajuntament**
i l'**única passarel·la de correu**. El control horari no té ni tindrà SMTP:
és al núvol, i fer-hi passar credencials de correu de l'ajuntament seria
contradir la decisió de dalt.

Per tant nòmines ha de saber fer dues coses noves, totes dues des de
**Configuració → Usuaris** (`/usuaris`, `templates/usuaris.html`):

1. **Generar el CSV** de treballadors per carregar al control horari.
2. **Enviar a cadascú, per correu, el seu usuari i la contrasenya
   provisional**, amb l'SMTP que nòmines ja té configurat i funcionant.

Avui totes dues coses ja existeixen, però com a eina de línia d'ordres
(`control-horari/eines/exporta_des_de_nomines.py`, ordres `prepara` i
`envia`), que s'ha d'executar des d'un terminal a l'altre projecte. L'objectiu
és portar-ho a un botó.

---

## 1. El problema de disseny que cal resoldre primer

Les contrasenyes provisionals han de **coincidir** en dos llocs:

- al **correu** que rep cada treballador, i
- a la columna `contrasenya` del **CSV** que es puja al control horari (que és
  on es xifren i es desen).

Si el botó de descarregar i el d'enviar les generessin cadascun per la seva
banda, ningú podria entrar: el correu diria una cosa i el servidor n'esperaria
una altra.

**Solució: el fitxer és el portador.** Dos passos, i les contrasenyes només
existeixen dins del CSV que l'administrador té a les mans:

```
   [Pas 1]  Botó «Generar CSV»  ──► es descarrega treballadors-AAAA-MM-DD.csv
                                     (conté les contrasenyes en clar)
                     │
                     ├──► l'administrador el REVISA (serveis, rols, i buida
                     │     la columna «contrasenya» de qui ja tingui compte)
                     │
   [Pas 2a] Formulari «Enviar credencials» ──► s'hi torna a pujar el MATEIX
                     │                          fitxer; nòmines envia els correus
                     │
   [Pas 2b] El mateix fitxer es puja a
            control-horari → Configuració → Importa
```

És exactament el que fa avui l'eina de línia d'ordres (`prepara` genera,
`envia --fitxer` envia), o sigui que el flux ja està provat. **No inventis un
tercer camí** (guardar les contrasenyes a la sessió, a un fitxer temporal o a
la base de dades): serien contrasenyes en clar persistides, que és justament
el que aquest disseny evita.

---

## 2. El contracte del fitxer (CONGELAT, no es toca)

Definit a `control-horari/core/format_importacio.py`. Si mai ha de canviar,
canvia allà primer i s'avisa als dos costats.

- Separador `;`, codificació `utf-8-sig` (amb BOM, perquè l'Excel l'obri bé)
- Columnes, en aquest ordre exacte:
  `usuari;nom;correu;servei;rol;data_alta;contrasenya`
- `usuari`, `nom`, `correu` obligatoris; la resta poden anar buides
- `rol` buit = «treballador» al control horari. Deixa'l sempre buit: ja
  s'ajusta allà
- `data_alta` buida sempre (només cal per a altes a mig any, i s'edita a mà)
- `contrasenya` buida = el control horari en genera una i la mostra una sola
  vegada per pantalla. **Una càrrega no canvia mai la contrasenya de ningú que
  ja tingui compte**

---

## 3. Peces de nòmines que es reutilitzen tal qual

| Què | On | Nota |
|---|---|---|
| Llista de gent | `_llegeix_treballadors()` (línia ~490) | `[(nom, correu)]` de `treballadors.xlsx` |
| Servei de cadascú | `_vac().carrega()['treballadors']` | dict `usuari -> {nom, correu, servei, saldos}` |
| Contrasenya provisional | `_genera_contrasenya(longitud=14)` (línia ~374) | Ja exclou `l1IO0` i ja fa 14 caràcters: **exactament** la política de `control-horari/core/comptes.py`. No n'escriguis una altra |
| Connexió SMTP | `_config_smtp()` + `connecta_smtp()` d'`envia_nomines.py` | El mateix `config.ini` de sempre |
| Descàrrega en memòria | `vacances_nomines_descarrega()` (línia ~3308) | `send_file(io.BytesIO(...), as_attachment=True, ...)` + `Cache-Control: no-store` |
| Registre d'auditoria | `registra(...)` | Com la resta de l'app |

**Aprofita el `servei`.** `treballadors.xlsx` només té `Nom | Correu`, però el
mòdul de Gestió de personal (`dades_vacances.json`) ja té el servei de
cadascú. Creua'ls **pel correu en minúscules**; si no hi ha coincidència,
`servei` queda buit. Això estalvia omplir a mà una columna de ~25 files.

---

## 4. El que cal escriure

### 4.1 Proposta de nom d'usuari

`nòmines` no en té cap (les altes són manuals, d'una en una). Porta
l'algorisme de `control-horari/eines/exporta_des_de_nomines.py::proposa_usuari()`:

- inicial del nom + primer cognom, sense accents, només `a-z`
- partícules que no compten: `de, del, la, los, las, i, ma`
- si xoca amb un ja proposat **en aquesta mateixa exportació**, s'allarga amb
  lletres del cognom següent — **mai amb xifres** (un `jgarcia2` no diu res a
  ningú i s'escriu malament la meitat de les vegades)

Porta-la's com a funció nova dins de nòmines, **no** com una importació entre
projectes: les dues apps han de continuar sent independents.

### 4.2 Pas 1 — la ruta que genera el CSV

```python
@app.route('/usuaris/exporta-control-horari')
@admin_required
def usuaris_exporta_control_horari():
    """CSV per carregar a Configuració → Importa del control horari.
    SOLA LECTURA: no desa res a nòmines."""
    persones = _llegeix_treballadors()
    if not persones:
        flash('No hi ha cap treballador a la llista.', 'error')
        return redirect(url_for('usuaris'))

    per_correu = {
        (v.get('correu') or '').strip().lower(): v.get('servei', '')
        for v in _vac().carrega()['treballadors'].values()
    }

    usats, files = set(), []
    for nom, correu in persones:
        usuari = proposa_usuari(nom, usats)
        usats.add(usuari)
        files.append({
            'usuari': usuari, 'nom': nom, 'correu': correu,
            'servei': per_correu.get((correu or '').strip().lower(), ''),
            'rol': '', 'data_alta': '',
            'contrasenya': _genera_contrasenya(14),
        })

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=['usuari', 'nom', 'correu', 'servei',
                                        'rol', 'data_alta', 'contrasenya'],
                       delimiter=';', extrasaction='ignore')
    w.writeheader()
    w.writerows(files)
    contingut = ('﻿' + buf.getvalue()).encode('utf-8')

    registra('EXPORTA_TREBALLADORS_CH', f'{len(files)} treballadors')
    resp = send_file(io.BytesIO(contingut), as_attachment=True,
                     download_name=f'treballadors-{date.today().isoformat()}.csv',
                     mimetype='text/csv')
    resp.headers['Cache-Control'] = 'no-store'
    return resp
```

Comprova quins d'`io`, `csv`, `date` ja són importats a dalt d'`app_web.py`
abans d'afegir-los.

### 4.3 Pas 2 — la ruta que envia les credencials

Rep el CSV **ja revisat** i envia un correu a cada fila **que tingui
contrasenya**. Les files amb `contrasenya` buida se salten en silenci: són la
gent que ja té compte i a qui no s'ha de tocar res.

**Dos passos obligatoris, com a l'eina de línia d'ordres.** Enviar dues
dotzenes de correus reals a persones reals no ha de poder passar d'un clic
accidental:

1. `accio=previsualitza` → pantalla amb **a qui s'escriuria** (usuari i
   correu; **mai la contrasenya**) i quantes files se saltarien, sense enviar
   res.
2. `accio=confirma` → envia de debò.

```python
@app.route('/usuaris/envia-credencials-control-horari', methods=['POST'])
@admin_required
def usuaris_envia_credencials_ch():
    fitxer = request.files.get('csv')
    if not fitxer or not fitxer.filename:
        flash('Cal seleccionar el CSV generat al pas anterior.', 'error')
        return redirect(url_for('usuaris'))
    # lectura amb utf-8-sig i delimitador ';'
    # ...
    # accio == 'previsualitza' -> render de la llista, sense enviar
    # accio == 'confirma'      -> connecta_smtp() i envia un a un
```

**FAIL-SOFT en l'enviament**, com fa `core/vacances/notifica.py`: si un correu
rebota, s'anota i **es continua amb la resta**. En acabar, es mostra qui NO
l'ha rebut, perquè es pugui reintentar amb un fitxer que només tingui aquelles
files. Que una adreça mal escrita deixi mitja plantilla sense credencials
seria pitjor que l'error original.

Cos del correu (adapta'l al to de la resta de correus de l'app):

```
Hola, {nom}.

Ja tens compte a l'aplicació de control horari de l'Ajuntament:

    https://control-horari-torre-espanyol.web.app

    Usuari: {usuari}
    Contrasenya provisional: {contrasenya}

Aquesta contrasenya és PROVISIONAL: la primera vegada que entris,
l'aplicació t'obligarà a canviar-la. Fes-ho de seguida, perquè ha viatjat
per correu i el correu no és un canal segur.

Atentament,
Ajuntament de la Torre de l'Espanyol
```

### 4.4 La interfície

A `templates/usuaris.html`, una targeta amb els dos passos junts, perquè
l'ordre quedi clar:

```html
<div class="card">
  <h1>Control horari — altes de treballadors</h1>
  <p class="subtitol">
    L'aplicació de control horari és fora de l'ajuntament i no té correu
    propi: les credencials les envia nòmines des d'aquí.
  </p>

  <h2>Pas 1 · Generar el fitxer</h2>
  <p class="accions">
    <a class="btn" href="{{ url_for('usuaris_exporta_control_horari') }}">
      Descarregar CSV
    </a>
  </p>
  <p class="ajuda">
    Revisa'l abans de continuar: comprova els serveis i <strong>buida la
    columna «contrasenya» de qui ja tingui compte</strong> al control horari.
  </p>

  <h2>Pas 2 · Enviar les credencials</h2>
  <form method="post" enctype="multipart/form-data"
        action="{{ url_for('usuaris_envia_credencials_ch') }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="file" name="csv" accept=".csv" required>
    <button class="btn btn-secundari" name="accio" value="previsualitza"
            type="submit">Veure a qui s'enviaria</button>
  </form>
  <p class="ajuda">
    Puja <strong>el mateix fitxer</strong> del pas 1: les contrasenyes del
    correu han de ser les que després es carreguen al control horari.
  </p>

  <p class="ajuda">
    ⚠ El CSV porta contrasenyes en clar. No l'enviïs per correu, no el
    deixis en una carpeta compartida i <strong>esborra'l</strong> quan
    l'hagis pujat al control horari.
  </p>
</div>
```

---

## 5. Proves mínimes

Al fitxer de proves web que ja hi hagi:

**Generació**
- La resposta és `text/csv` amb `Content-Disposition: attachment`
- La primera línia, decodificada com a `utf-8-sig`, és exactament
  `usuari;nom;correu;servei;rol;data_alta;contrasenya`
- Una persona que a `dades_vacances.json` tingui `servei: "Oficines"` surt amb
  el `servei` omplert; una que no hi sigui, amb el `servei` buit
- Dues persones amb el mateix cognom **no** reben el mateix `usuari`
- La ruta no modifica `treballadors.xlsx` ni `dades_vacances.json` (compara
  les mtimes abans i després)
- Un usuari no administrador rep 403

**Enviament**
- `accio=previsualitza` **no** obre cap connexió SMTP (monkeypatch que ho
  detecti) i **no** ensenya cap contrasenya al HTML
- Les files amb `contrasenya` buida se salten
- Amb un SMTP fals que rebutgi la segona adreça, les altres s'envien igualment
  i la pantalla final diu quina ha fallat
- Un usuari no administrador rep 403

---

## 6. Un avís de l'altra banda

`control-horari/eines/exporta_des_de_nomines.py` va petar en producció perquè
escrivia `⚠ ✓ ✗` per consola i el Windows de l'ajuntament la té en `cp1252`.
Aquí no aplica igual (és HTML), però si en algun punt aquest codi escriu per
`print()` en comptes de `flash()`, vigileu-ho.

---

## 7. Quan estigui fet

L'eina `control-horari/eines/exporta_des_de_nomines.py` es podrà retirar (o
deixar com a via de recanvi documentada). Avisa'm i ho marco a l'`ESTAT.md`
del control horari.
