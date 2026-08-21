"""
Proves dels avisos push.

CAP prova surt a la xarxa: `pywebpush.webpush` se substitueix sempre. Un test
que depèn d'un servei de push de Google és un test que un dia falla sense que
ningú hagi tocat res.

Les dues garanties que es proven amb més insistència:

1. **Fail-soft.** Cap avís que falla no pot tombar l'operació que l'ha
   provocat. Una sol·licitud desada sense avís és un problema petit; una
   sol·licitud que no es desa perquè l'avís ha petat, un de gros.
2. **Textos genèrics.** Els avisos es llegeixen a la pantalla de bloqueig,
   on els pot veure qui tingui el telèfon a la mà: mai hi ha d'aparèixer ni
   qui demana, ni quants dies, ni quin període.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from core import push
from magatzem import absencies as mag_absencies, subscripcions


CONFIG = {"VAPID_PUBLIC": "publica-de-prova",
          "VAPID_PRIVATE": "privada-de-prova",
          "VAPID_SUBJECT": "mailto:proves@exemple.cat"}

SUB = {"id": "abc123", "endpoint": "https://push.exemple.cat/xyz",
       "p256dh": "clau-p256dh", "auth": "clau-auth"}


class PushFals:
    """Substitut de `pywebpush.webpush` que apunta què s'hi ha enviat."""

    def __init__(self, error=None):
        self.enviats = []
        self.error = error

    def __call__(self, **kwargs):
        if self.error:
            raise self.error
        self.enviats.append(kwargs)

    @property
    def carregues(self):
        return [json.loads(e["data"]) for e in self.enviats]


@pytest.fixture
def push_fals(monkeypatch):
    fals = PushFals()
    import pywebpush
    monkeypatch.setattr(pywebpush, "webpush", fals)
    return fals


def text(r):
    return r.get_data(as_text=True)


# -- configuració -----------------------------------------------------------
def test_sense_claus_els_avisos_queden_desactivats():
    assert push.hi_ha_push({}) is False
    assert push.hi_ha_push({"VAPID_PUBLIC": "x"}) is False
    assert push.hi_ha_push(CONFIG) is True


def test_sense_claus_no_s_envia_res_i_no_peta(push_fals):
    assert push.envia({}, [SUB], "Títol", "Cos") == 0
    assert push_fals.enviats == []


# -- enviament --------------------------------------------------------------
def test_s_envia_a_cada_dispositiu(push_fals):
    altre = {**SUB, "id": "def456", "endpoint": "https://push.exemple.cat/abc"}
    assert push.envia(CONFIG, [SUB, altre], "Títol", "Cos", ruta="/gestio") == 2
    assert len(push_fals.enviats) == 2


def test_la_carrega_porta_titol_cos_i_ruta(push_fals):
    push.envia(CONFIG, [SUB], "Sol·licitud pendent", "Tens feina", ruta="/gestio")
    carrega = push_fals.carregues[0]
    assert carrega == {"titol": "Sol·licitud pendent", "cos": "Tens feina",
                       "ruta": "/gestio"}


def test_els_avisos_caduquen(push_fals):
    """Rebre «tens una sol·licitud» una setmana després no ajuda ningú."""
    push.envia(CONFIG, [SUB], "Títol", "Cos")
    assert push_fals.enviats[0]["ttl"] == push.CADUCITAT


def test_la_clau_privada_no_viatja_mai_dins_del_missatge(push_fals):
    push.envia(CONFIG, [SUB], "Títol", "Cos")
    assert "privada-de-prova" not in push_fals.enviats[0]["data"]


# -- fail-soft --------------------------------------------------------------
def test_un_error_del_servei_de_push_no_llanca(monkeypatch):
    import pywebpush
    monkeypatch.setattr(pywebpush, "webpush",
                        PushFals(error=RuntimeError("s'ha begut l'enteniment")))
    assert push.envia(CONFIG, [SUB], "Títol", "Cos") == 0


def test_una_subscripcio_caducada_s_esborra(monkeypatch):
    """410 Gone: el navegador s'ha desinstal·lat o s'ha tret el permís."""
    import pywebpush

    class Resposta:
        status_code = 410

    class Fals:
        def __call__(self, **kwargs):
            e = pywebpush.WebPushException("ja no hi és")
            e.response = Resposta()
            raise e

    monkeypatch.setattr(pywebpush, "webpush", Fals())
    esborrades = []
    push.envia(CONFIG, [SUB], "Títol", "Cos", esborra=esborrades.append)
    assert esborrades == ["abc123"]


def test_un_error_normal_no_esborra_la_subscripcio(monkeypatch):
    """Un 500 del servei de push és temporal: seria absurd desapuntar algú."""
    import pywebpush

    class Resposta:
        status_code = 500

    class Fals:
        def __call__(self, **kwargs):
            e = pywebpush.WebPushException("no va")
            e.response = Resposta()
            raise e

    monkeypatch.setattr(pywebpush, "webpush", Fals())
    esborrades = []
    push.envia(CONFIG, [SUB], "Títol", "Cos", esborra=esborrades.append)
    assert esborrades == []


def test_un_dispositiu_mort_no_impedeix_avisar_els_altres(monkeypatch):
    import pywebpush
    bons = []

    class Fals:
        def __call__(self, **kwargs):
            if "mort" in kwargs["subscription_info"]["endpoint"]:
                raise RuntimeError("aquest no respon")
            bons.append(kwargs)

    monkeypatch.setattr(pywebpush, "webpush", Fals())
    mort = {**SUB, "id": "mort", "endpoint": "https://push.exemple.cat/mort"}
    assert push.envia(CONFIG, [mort, SUB], "Títol", "Cos") == 1
    assert len(bons) == 1


# -- els textos concrets ----------------------------------------------------
def test_l_avis_de_nova_solicitud_no_diu_de_qui_es(push_fals):
    push.avisa_nova_solicitud(CONFIG, [SUB])
    carrega = push_fals.carregues[0]
    tot = (carrega["titol"] + carrega["cos"]).lower()
    for filtracio in ("dies", "gener", "febrer", "@", "treb", "/"):
        assert filtracio not in tot, f"l'avís filtra «{filtracio}»: {tot}"
    assert carrega["ruta"] == "/gestio"


def test_l_avis_de_resolucio_distingeix_aprovada_de_denegada(push_fals):
    push.avisa_resolucio(CONFIG, [SUB], aprovada=True)
    push.avisa_resolucio(CONFIG, [SUB], aprovada=False)
    aprovada, denegada = push_fals.carregues
    assert "aprovad" in aprovada["titol"].lower()
    assert "denegad" in denegada["titol"].lower()
    assert aprovada["ruta"] == denegada["ruta"] == "/absencies"


def test_cap_avis_no_porta_ni_codi_ni_dates(push_fals):
    push.avisa_nova_solicitud(CONFIG, [SUB])
    push.avisa_resolucio(CONFIG, [SUB], aprovada=True)
    push.avisa_anulacio(CONFIG, [SUB])
    for carrega in push_fals.carregues:
        text_avis = carrega["titol"] + carrega["cos"]
        assert "A-20" not in text_avis, "hi surt el codi de la sol·licitud"
        assert "20" not in text_avis.replace("2 passos", ""), "hi surt un any"


# -- magatzem de subscripcions ---------------------------------------------
def test_subscriure_s_dues_vegades_no_duplica(magatzem):
    subscripcions.desa(magatzem, "treb01", SUB["endpoint"], "a", "b")
    subscripcions.desa(magatzem, "treb01", SUB["endpoint"], "a", "b")
    assert len(subscripcions.de_treballador(magatzem, "treb01")) == 1


def test_una_persona_pot_tenir_el_mobil_i_el_pc(magatzem):
    subscripcions.desa(magatzem, "treb01", "https://push/mobil", "a", "b")
    subscripcions.desa(magatzem, "treb01", "https://push/pc", "c", "d")
    assert len(subscripcions.de_treballador(magatzem, "treb01")) == 2


def test_les_subscripcions_no_es_barregen_entre_persones(magatzem):
    subscripcions.desa(magatzem, "treb01", "https://push/un", "a", "b")
    subscripcions.desa(magatzem, "treb02", "https://push/dos", "c", "d")
    meves = subscripcions.de_treballador(magatzem, "treb01")
    assert [s["endpoint"] for s in meves] == ["https://push/un"]


def test_de_treballadors_no_repeteix_dispositius(magatzem):
    subscripcions.desa(magatzem, "treb01", "https://push/un", "a", "b")
    trobades = subscripcions.de_treballadors(magatzem,
                                             ["treb01", "treb01", "treb02"])
    assert len(trobades) == 1


def test_esborra_de_les_treu_totes(magatzem):
    subscripcions.desa(magatzem, "treb01", "https://push/mobil", "a", "b")
    subscripcions.desa(magatzem, "treb01", "https://push/pc", "c", "d")
    assert subscripcions.esborra_de(magatzem, "treb01") == 2
    assert subscripcions.de_treballador(magatzem, "treb01") == []


# -- rutes ------------------------------------------------------------------
def test_les_rutes_de_push_demanen_sessio(client):
    assert client.get("/push/clau").status_code in (301, 302, 401)
    assert client.post("/push/subscriu", json={}).status_code in (301, 302, 401)


def test_la_clau_publica_es_pot_demanar_amb_sessio(client, entra):
    entra("treb01")
    dades = client.get("/push/clau").get_json()
    assert "activat" in dades and "clau" in dades


def test_sense_claus_configurades_no_es_demana_permis(client, entra):
    """Val més no demanar res que demanar-ho i després no enviar mai res."""
    entra("treb01")
    assert client.get("/push/clau").get_json()["activat"] is False


def test_una_subscripcio_incompleta_es_rebutja(client, entra, magatzem):
    entra("treb01")
    resposta = client.post("/push/subscriu",
                           json={"endpoint": "https://push/x"})   # sense keys
    assert resposta.status_code == 400
    assert subscripcions.de_treballador(magatzem, "treb01") == []


def test_una_subscripcio_valida_es_desa(client, entra, magatzem):
    entra("treb01")
    resposta = client.post("/push/subscriu", json={
        "endpoint": "https://push.exemple.cat/xyz",
        "keys": {"p256dh": "clau-p", "auth": "clau-a"}})
    assert resposta.status_code == 200
    desades = subscripcions.de_treballador(magatzem, "treb01")
    assert len(desades) == 1
    assert desades[0]["endpoint"] == "https://push.exemple.cat/xyz"


def test_la_subscripcio_es_desa_a_nom_de_qui_te_la_sessio(client, entra, magatzem):
    """Ningú pot subscriure un altre: el login surt de la sessió, no del cos."""
    entra("treb01")
    client.post("/push/subscriu", json={
        "endpoint": "https://push/x", "treballador_id": "admin01",
        "keys": {"p256dh": "p", "auth": "a"}})
    assert subscripcions.de_treballador(magatzem, "admin01") == []
    assert len(subscripcions.de_treballador(magatzem, "treb01")) == 1


def test_es_pot_donar_de_baixa(client, entra, magatzem):
    entra("treb01")
    client.post("/push/subscriu", json={
        "endpoint": "https://push/x", "keys": {"p256dh": "p", "auth": "a"}})
    client.post("/push/baixa", json={"endpoint": "https://push/x"})
    assert subscripcions.de_treballador(magatzem, "treb01") == []


# -- integració amb el circuit d'absències ---------------------------------
def test_demanar_vacances_avisa_els_aprovadors(client, entra, magatzem,
                                               serveis, dies_habils_propers,
                                               monkeypatch):
    import pywebpush
    fals = PushFals()
    monkeypatch.setattr(pywebpush, "webpush", fals)
    monkeypatch.setitem(client.application.config["APP"], "VAPID_PUBLIC", "p")
    monkeypatch.setitem(client.application.config["APP"], "VAPID_PRIVATE", "s")

    subscripcions.desa(magatzem, "resp01", "https://push/resp", "p", "a")

    entra("treb01")
    dies = dies_habils_propers
    client.post("/absencies/solicita",
                data={"tipus": "vacances", "inici": dies[0].isoformat(),
                      "fi": dies[-1].isoformat(), "motiu": ""},
                follow_redirects=True)

    assert fals.enviats, "no s'ha avisat cap aprovador"
    assert fals.carregues[0]["ruta"] == "/gestio"


def test_si_el_push_peta_la_solicitud_es_desa_igualment(
        client, entra, magatzem, serveis, dies_habils_propers, monkeypatch):
    """LA garantia: cap avís no pot tombar l'operació de l'usuari."""
    import pywebpush
    monkeypatch.setattr(pywebpush, "webpush",
                        PushFals(error=RuntimeError("tot malament")))
    monkeypatch.setitem(client.application.config["APP"], "VAPID_PUBLIC", "p")
    monkeypatch.setitem(client.application.config["APP"], "VAPID_PRIVATE", "s")
    subscripcions.desa(magatzem, "resp01", "https://push/resp", "p", "a")

    entra("treb01")
    dies = dies_habils_propers
    client.post("/absencies/solicita",
                data={"tipus": "vacances", "inici": dies[0].isoformat(),
                      "fi": dies[-1].isoformat(), "motiu": ""},
                follow_redirects=True)

    meves = mag_absencies.de_treballador(magatzem, "treb01", dies[0].year)
    assert [a for a in meves if a.data_inici == dies[0]], \
        "la sol·licitud s'ha perdut perquè l'avís ha fallat"


def test_resoldre_avisa_el_treballador(client, entra, magatzem, serveis,
                                       dies_habils_propers, monkeypatch):
    import pywebpush
    fals = PushFals()
    monkeypatch.setattr(pywebpush, "webpush", fals)
    monkeypatch.setitem(client.application.config["APP"], "VAPID_PUBLIC", "p")
    monkeypatch.setitem(client.application.config["APP"], "VAPID_PRIVATE", "s")

    codi = mag_absencies.crea(magatzem, "treb01", serveis["Oficines"],
                              "vacances", dies_habils_propers[0],
                              dies_habils_propers[-1], 5)
    subscripcions.desa(magatzem, "treb01", "https://push/treb", "p", "a")

    entra("resp01")
    client.post("/gestio/resol", data={"codi": codi, "accio": "aprova"},
                follow_redirects=True)

    assert fals.enviats, "no s'ha avisat el treballador"
    assert fals.carregues[-1]["ruta"] == "/absencies"


def test_donar_de_baixa_un_compte_li_treu_les_subscripcions(
        client, entra, magatzem, serveis):
    """Qui ja no hi treballa no ha de continuar rebent avisos, i el seu
    dispositiu deixa de ser una dada que tinguem cap motiu per conservar."""
    subscripcions.desa(magatzem, "treb01", "https://push/x", "p", "a")
    entra("admin01")
    client.post("/configuracio/compte",
                data={"accio": "baixa", "login": "treb01",
                      "data_baixa": date.today().isoformat()},
                follow_redirects=True)
    assert subscripcions.de_treballador(magatzem, "treb01") == []


# -- service worker ---------------------------------------------------------
def test_el_service_worker_sap_rebre_avisos(client):
    codi = text(client.get("/sw.js"))
    assert "addEventListener('push'" in codi
    assert "addEventListener('notificationclick'" in codi


def test_el_service_worker_segueix_sense_cachejar_pagines(client):
    """L'afegit del push no pot haver tocat la regla de sempre.

    Es mira la llista ESTATICS de debò, no el text sencer del fitxer: els
    comentaris hi anomenen rutes amb dades precisament per advertir que no
    s'hi han de posar."""
    codi = text(client.get("/sw.js"))
    llista = codi.split("const ESTATICS = [")[1].split("]")[0]
    for amb_dades in ("/hores", "/absencies", "/gestio", "/marcatges"):
        assert amb_dades not in llista, f"el sw cacheja {amb_dades}!"
