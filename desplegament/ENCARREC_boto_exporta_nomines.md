# Encàrrec · Botó d'exportació de treballadors, dins de nòmines

**Per a l'altre xat (el de `expedients-nomines-beta`). No toca res de
`control-horari`: només el llegeix com a referència del contracte.**

## Objectiu

Un botó a `Configuració → Usuaris` (`/usuaris`, `templates/usuaris.html`) que
generi i descarregui directament el CSV que la pantalla `Configuració →
Importa` del control horari sap llegir. Avui aquest fitxer es genera a mà
amb `python eines/exporta_des_de_nomines.py prepara`, executat des d'un
terminal a `control-horari`; l'objectiu és estalviar-se aquest pas.

**Res del que fa aquest botó escriu res a `nòmines`.** És una exportació de
sola lectura: no toca `treballadors.xlsx`, `usuaris.ini` ni
`dades_vacances.json`.

## Una troballa important abans de picar codi

`nòmines-beta` ja té un mòdul de «Gestió de personal» sencer —vacances,
saldos, aprovació per servei, calendari— a `core/vacances/magatzem.py` /
`dades_vacances.json` (disseny a `VACANCES_DISSENY.md`, 2026-07-21). Cada
treballador hi té un `servei` assignat (Oficines / Brigada / SAIAR).

`treballadors.xlsx`, en canvi, només té `Nom | Correu`: cap servei.

**Aprofita-ho:** la llista completa de gent surt de `treballadors.xlsx` (és
la que està sempre al dia, ~25 persones); el `servei` de cadascú s'agafa de
`_vac().carrega()['treballadors']` quan hi hagi una fila amb el mateix
correu (comparació en minúscules). Si no hi és, `servei` queda buit, com ara.

Això no és una decisió de si el mòdul vell es retira o no —això et toca
decidir-ho a tu— és només aprofitar una dada que ja existeix perquè el CSV
surti més complet.

## El contracte del fitxer (CONGELAT, no es toca)

Definit a `control-horari/core/format_importacio.py`. Si mai canvia, canvia
allà i s'avisa als dos costats; aquí només es reprodueix:

- Separador `;`, codificació `utf-8-sig` (amb BOM, perquè l'Excel l'obri bé)
- Columnes, en aquest ordre:
  `usuari;nom;correu;servei;rol;data_alta;contrasenya`
- `usuari`, `nom`, `correu` obligatoris; la resta poden anar buides
- `rol` buit vol dir «treballador» al control horari — deixa-ho sempre buit,
  l'administrador ja ho ajusta allà si cal
- `data_alta` buida sempre (només cal per a altes a mig any, i això s'edita
  a mà)

## Peces que ja existeixen a `nòmines` i es poden reutilitzar tal qual

- **La llista de gent**: `_llegeix_treballadors()` (línia ~490 d'`app_web.py`)
  — `[(nom, correu), ...]` de `treballadors.xlsx`.
- **El servei de cadascú**: `_vac().carrega()['treballadors']` — dict
  `usuari_intern -> {'nom', 'correu', 'servei', 'saldos'}`. Fes-ne un índex
  per correu en minúscules abans de creuar-lo amb la llista de dalt.
- **La contrasenya provisional**: `_genera_contrasenya(longitud=14)` (línia
  ~374). Ja exclou `l1IO0` i ja fa 14 caràcters: exactament la política que
  demana `control-horari/core/comptes.py` (`LLARGADA_PROVISIONAL = 14`,
  mateix alfabet). No cal escriure'n una altra.
- **El patró de descàrrega en memòria**: mira `vacances_nomines_descarrega()`
  (línia ~3308) — ruta `GET`, `send_file(io.BytesIO(...), as_attachment=True,
  download_name=..., mimetype=...)`, amb
  `resp.headers['Cache-Control'] = 'no-store'`. Copia aquest patró, no el de
  `/exporta` (aquell és `POST` perquè rep un PDF pujat; aquí no cal pujar res,
  així que `GET` i un simple `<a>` ja fan).

## El que falta escriure

### Proposta de nom d'usuari

`nòmines` no en té cap (l'alta d'usuaris és manual, un a un). Porta
l'algorisme de `control-horari/eines/exporta_des_de_nomines.py::
proposa_usuari()`: inicial del nom + primer cognom, sense accents, només
`a-z`; si xoca amb un que ja s'ha proposat en aquesta mateixa exportació,
s'allarga amb lletres del cognom següent (mai amb xifres). Porta-la's tal
qual —ja està provada i resol bé els casos de noms repetits— com a funció
nova dins de `nòmines`, no com una importació entre apps (les dues han de
seguir sent independents).

### La ruta

```python
@app.route('/usuaris/exporta-control-horari')
@admin_required
def usuaris_exporta_control_horari():
    """CSV per carregar a Configuració → Importa del control horari.
    Sola lectura: no desa res a nòmines."""
    persones = _llegeix_treballadors()
    if not persones:
        flash('No hi ha cap treballador a la llista.', 'error')
        return redirect(url_for('usuaris'))

    per_correu = {
        (v.get('correu') or '').strip().lower(): v.get('servei', '')
        for v in _vac().carrega()['treballadors'].values()
    }

    usats = set()
    files = []
    for nom, correu in persones:
        usuari = proposa_usuari(nom, usats)   # la funció portada
        usats.add(usuari)
        files.append({
            'usuari': usuari, 'nom': nom, 'correu': correu,
            'servei': per_correu.get(correu.strip().lower(), ''),
            'rol': '', 'data_alta': '',
            'contrasenya': _genera_contrasenya(14),
        })

    buf = io.StringIO()
    escriptor = csv.DictWriter(
        buf, fieldnames=['usuari', 'nom', 'correu', 'servei', 'rol',
                         'data_alta', 'contrasenya'],
        delimiter=';', extrasaction='ignore')
    escriptor.writeheader()
    escriptor.writerows(files)
    contingut = ('﻿' + buf.getvalue()).encode('utf-8')

    registra('EXPORTA_TREBALLADORS_CH', f'{len(files)} treballadors')
    nom_fitxer = f'treballadors-{date.today().isoformat()}.csv'
    resp = send_file(io.BytesIO(contingut), as_attachment=True,
                     download_name=nom_fitxer, mimetype='text/csv')
    resp.headers['Cache-Control'] = 'no-store'
    return resp
```

Ajusta noms de funcions/imports al que ja hi hagi importat dalt de
`app_web.py` (`io`, `csv`, `date` seur segur que ja hi són; comprova-ho abans
d'afegir-los duplicats).

### La plantilla

A `templates/usuaris.html`, una targeta petita, per exemple després de la
d'«Afegir un treballador»:

```html
<div class="card">
  <h1>Exportar per al control horari</h1>
  <p class="subtitol">
    Genera el fitxer per carregar a <em>Configuració → Importa</em> del
    control horari, amb una contrasenya provisional per a tothom.
  </p>
  <p class="accions">
    <a class="btn" href="{{ url_for('usuaris_exporta_control_horari') }}">
      Descarregar CSV
    </a>
  </p>
  <p class="ajuda">
    ⚠ El fitxer porta contrasenyes en clar. Abans de pujar-lo, buida la
    columna «contrasenya» de qui ja tingui compte al control horari (una
    càrrega no la hi canvia), i esborra el fitxer quan hagis acabat.
  </p>
</div>
```

## Un avís de l'altra banda

`control-horari/eines/exporta_des_de_nomines.py` va petar fa poc en
producció (Windows, consola en `cp1252`, no accepta `⚠✓✗` als missatges de
terminal). Aquí no aplica igual —és HTML, no terminal— però si en algun
moment aquest botó escriu res per `print()` en comptes de `flash()`,
vigileu-hi.

## Prova mínima que hi hauria de ser

Una prova que pugi un `treballadors.xlsx` sintètic (com fa
`tests/test_vacances_web.py` o semblant) i comprovi:

- la resposta és un `text/csv` amb `Content-Disposition: attachment`
- la primera línia (decodificada com a `utf-8-sig`) és exactament
  `usuari;nom;correu;servei;rol;data_alta;contrasenya`
- una persona que surti a `dades_vacances.json` amb `servei: "Oficines"` surt
  al CSV amb `servei` omplert; una que no hi surti, amb `servei` buit
- dues persones amb el mateix cognom no reben el mateix `usuari`
