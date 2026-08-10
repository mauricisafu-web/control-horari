"""Proves de la PWA: instal·lable, i que el service worker no cachegi dades."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ARREL = Path(__file__).resolve().parents[1]


def test_el_manifest_es_public_i_valid(client):
    resposta = client.get("/manifest.webmanifest")
    assert resposta.status_code == 200
    assert "application/manifest+json" in resposta.headers["Content-Type"]

    manifest = json.loads(resposta.get_data(as_text=True))
    for clau in ("name", "short_name", "start_url", "display", "icons"):
        assert clau in manifest
    assert manifest["display"] == "standalone"
    assert manifest["lang"] == "ca"


def test_hi_ha_les_quatre_icones():
    manifest = json.loads((ARREL / "static/manifest.webmanifest").read_text("utf-8"))
    assert len(manifest["icons"]) == 4
    for icona in manifest["icons"]:
        cami = ARREL / icona["src"].lstrip("/")
        assert cami.exists(), f"falta {cami}"
        assert cami.stat().st_size > 500


def test_hi_ha_icones_maskable():
    """Sense una icona «maskable», Android en retalla els extrems."""
    manifest = json.loads((ARREL / "static/manifest.webmanifest").read_text("utf-8"))
    assert any(i.get("purpose") == "maskable" for i in manifest["icons"])


def test_el_service_worker_es_public_i_te_abast_d_arrel(client):
    """Servit des de /static/ només controlaria /static/*: l'aplicació no
    seria instal·lable."""
    resposta = client.get("/sw.js")
    assert resposta.status_code == 200
    assert resposta.headers["Service-Worker-Allowed"] == "/"


def test_el_service_worker_NO_cacheja_cap_pagina():
    """La salvaguarda contra que algú hi afegeixi '/' o '/hores' un dia.

    Aquesta aplicació tracta dades personals i el mòbil es pot perdre o
    compartir: cachejar pàgines contradiria el `Cache-Control: no-store` que
    el servidor envia a cada resposta."""
    sw = (ARREL / "static/sw.js").read_text("utf-8")
    inici = sw.index("const ESTATICS")
    llista = sw[inici:sw.index("]", inici)]

    permesos = ("/static/", "/manifest.webmanifest")
    for linia in llista.splitlines():
        net = linia.strip().strip("',\"")
        if net.startswith("/"):
            assert net.startswith(permesos), f"el sw cacheja una pàgina: {net}"


def test_la_pagina_d_instal_lacio_explica_android_i_iphone(client):
    resposta = client.get("/instal-lacio")
    assert resposta.status_code == 200
    contingut = resposta.get_data(as_text=True)
    assert "Android" in contingut and "iPhone" in contingut
    # A l'iPhone només funciona amb Safari, i la gent s'hi perd.
    assert "Safari" in contingut


@pytest.mark.parametrize("ruta", ["/manifest.webmanifest", "/sw.js",
                                  "/instal-lacio", "/avis-legal"])
def test_les_rutes_publiques_responen_sense_sessio(client, ruta):
    """El navegador demana el manifest abans que ningú hagi entrat."""
    assert client.get(ruta).status_code == 200


def test_cap_script_en_linia_a_les_plantilles():
    """La política de continguts no permet `script-src 'unsafe-inline'`: un
    script dins d'una plantilla no s'executaria mai."""
    for plantilla in (ARREL / "templates").rglob("*.html"):
        contingut = plantilla.read_text("utf-8")
        for tros in contingut.split("<script")[1:]:
            capçalera = tros.split(">")[0]
            assert "src=" in capçalera, f"script en línia a {plantilla.name}"
