"""Proves de l'esquelet: que l'aplicació s'aixeca i que les defenses hi són."""
from __future__ import annotations

import pytest

from magatzem import rebost as reb


def test_es_crea_amb_magatzem_injectat(app):
    assert app.extensions["magatzem"] is not None


def test_es_crea_sense_magatzem_i_agafa_el_de_memoria(monkeypatch):
    """Sense cap variable d'entorn, l'aplicació ha d'arrencar amb el magatzem
    en memòria: ningú ha de necessitar un compte de Google per treballar-hi."""
    monkeypatch.delenv("REBOST", raising=False)
    monkeypatch.setenv("SECRET_KEY", "clau-de-prova-no-real")
    import app_web
    aplicacio = app_web.crea_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    assert isinstance(aplicacio.extensions["magatzem"], reb.RebostMemoria)


def test_el_magatzem_s_inicialitza_sol(app):
    config = app.extensions["magatzem"].doc(reb.PARAMETRES, reb.DOC_CONFIG)
    assert config["dies_vacances_defecte"] == 22


@pytest.mark.parametrize("capcalera,valor", [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "same-origin"),
])
def test_capceleres_de_seguretat(client, capcalera, valor):
    resposta = client.get("/avis-legal")
    assert resposta.headers[capcalera] == valor


def test_politica_de_continguts_sense_scripts_en_linia(client):
    csp = client.get("/avis-legal").headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "frame-ancestors 'none'" in csp


def test_les_pagines_no_es_cachegen_mai(client):
    """Contrapartida del service worker: cap resposta amb dades es desa."""
    assert client.get("/avis-legal").headers["Cache-Control"] == "no-store"


def test_els_estatics_si_que_es_cachegen(client):
    """Si els estàtics portessin no-store, la PWA no serviria de res."""
    resposta = client.get("/static/css/base.css")
    assert resposta.status_code == 200
    assert "no-store" not in resposta.headers["Cache-Control"]


def test_avis_legal_es_public(client):
    """És la informació de l'article 13: s'ha de poder llegir sense entrar."""
    resposta = client.get("/avis-legal")
    assert resposta.status_code == 200
    assert "Protecció de dades" in resposta.get_data(as_text=True)


def test_el_manifest_i_el_service_worker_son_publics(client):
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert "application/manifest+json" in manifest.headers["Content-Type"]

    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert sw.headers["Service-Worker-Allowed"] == "/"


def test_pagina_de_no_trobat_en_catala(client):
    resposta = client.get("/aquesta-ruta-no-existeix")
    assert resposta.status_code == 404
    assert "no existeix" in resposta.get_data(as_text=True)


def test_les_rutes_privades_demanen_sessio(client):
    for ruta in ("/", "/hores", "/absencies", "/gestio", "/configuracio/",
                 "/informes", "/marcatges"):
        resposta = client.get(ruta)
        assert resposta.status_code in (302, 401), f"{ruta} no demana sessió"


def test_domini_public_rebutja_un_altre_host(magatzem, monkeypatch):
    """Tanca la porta del darrere: la URL directa de Cloud Run també respon,
    i sense això qualsevol se saltaria Firebase Hosting."""
    monkeypatch.setenv("SECRET_KEY", "clau-de-prova-no-real")
    monkeypatch.setenv("DOMINI_PUBLIC", "control-horari.exemple.cat")
    import app_web
    aplicacio = app_web.crea_app({"TESTING": True, "WTF_CSRF_ENABLED": False},
                                 magatzem=magatzem)
    client = aplicacio.test_client()

    assert client.get("/avis-legal", headers={"Host": "impostor.run.app"}).status_code == 403
    assert client.get("/avis-legal",
                      headers={"Host": "control-horari.exemple.cat"}).status_code == 200
