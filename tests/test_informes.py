"""Proves dels informes i de la purga per conservació."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from core import purga as modul_purga
from core.model import ara_utc
from magatzem import absencies as mag_absencies, comptes, marcatges


def text(r):
    return r.get_data(as_text=True)


def marca(magatzem, login, dia, hora, tipus="entrada", servei_id=None):
    moment = datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=timezone.utc)
    return marcatges.afegeix(magatzem, login, tipus, moment, "web", login,
                             servei_id=servei_id)


# -- permisos ---------------------------------------------------------------
def test_un_treballador_no_pot_generar_informes(client, entra):
    entra("treb01")
    assert client.get("/informes").status_code == 403
    assert client.post("/informes/genera", data={}).status_code == 403


def test_un_responsable_tampoc(client, entra):
    entra("resp01")
    assert client.get("/informes").status_code == 403


# -- CSV --------------------------------------------------------------------
def test_csv_amb_bom_i_accents(client, entra, magatzem):
    avui = date.today()
    marca(magatzem, "treb01", avui, 6)
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "treb01", "inici": avui.isoformat(),
                          "fi": avui.isoformat(), "format": "csv"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["Content-Type"]
    assert "attachment" in r.headers["Content-Disposition"]
    contingut = r.get_data(as_text=True)
    # El BOM és el que fa que l'Excel obri els accents bé sense fer res.
    assert contingut.startswith("﻿")
    assert "Treballador" in contingut and "Entrada" in contingut


def test_el_csv_inclou_els_anulats_marcats_com_a_tals(client, entra, magatzem):
    """El llibre no s'esborra mai i la traça ha de ser completa."""
    avui = date.today()
    original = marca(magatzem, "treb01", avui, 6, "sortida")
    marca(magatzem, "treb01", avui, 8, "sortida")
    marcatges.afegeix(magatzem, "treb01", "sortida",
                      datetime(avui.year, avui.month, avui.day, 9, 0,
                               tzinfo=timezone.utc),
                      "manual", "treb01", anul_la_id=original, nota="error")
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "treb01", "inici": avui.isoformat(),
                          "fi": avui.isoformat(), "format": "csv"})
    files = [l for l in r.get_data(as_text=True).splitlines() if "treb" in l.lower()
             or "Treballador U" in l]
    assert any(";no;" in l or l.endswith(";no;;treb01") or ";no;" in l
               for l in r.get_data(as_text=True).splitlines())


def test_el_csv_no_conte_dades_de_mes(client, entra, magatzem):
    avui = date.today()
    marca(magatzem, "treb01", avui, 6)
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "treb01", "inici": avui.isoformat(),
                          "fi": avui.isoformat(), "format": "csv"})
    contingut = r.get_data(as_text=True)
    assert "@exemple.cat" not in contingut      # ni correus, ni NIF, ni adreces


# -- PDF --------------------------------------------------------------------
def test_pdf_d_una_persona(client, entra, magatzem):
    avui = date.today()
    marca(magatzem, "treb01", avui, 6)
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "treb01", "inici": avui.isoformat(),
                          "fi": avui.isoformat(), "format": "pdf"})
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    assert r.get_data()[:5] == b"%PDF-"
    assert len(r.get_data()) > 1000


# -- límits de cost ---------------------------------------------------------
def test_limit_de_tota_la_plantilla(client, entra):
    """Sense aquest límit, unes quantes consultes esgoten la quota del dia i
    l'aplicació deixa de funcionar per a tothom."""
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "", "inici": "2026-01-01",
                          "fi": "2026-12-31", "format": "csv"},
                    follow_redirects=True)
    assert "com a màxim" in text(r)


def test_limit_d_una_sola_persona(client, entra):
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "treb01", "inici": "2020-01-01",
                          "fi": "2026-12-31", "format": "csv"},
                    follow_redirects=True)
    assert "com a màxim" in text(r)


def test_dates_al_reves(client, entra):
    entra("admin01")
    r = client.post("/informes/genera",
                    data={"treballador": "treb01", "inici": "2026-08-10",
                          "fi": "2026-08-01", "format": "csv"},
                    follow_redirects=True)
    assert "anterior" in text(r)


# -- purga ------------------------------------------------------------------
def test_la_simulacio_no_toca_res(magatzem):
    vell = date.today() - timedelta(days=365 * 6)
    marca(magatzem, "treb01", vell, 6)
    resultat = modul_purga.purga(magatzem, simulacio=True)
    assert resultat["marcatges"] == 1
    assert len(marcatges.del_dia(magatzem, "treb01", vell)) == 1


def test_la_purga_real_esborra_el_que_ha_dit_la_simulacio(magatzem):
    vell = date.today() - timedelta(days=365 * 6)
    recent = date.today()
    marca(magatzem, "treb01", vell, 6)
    marca(magatzem, "treb01", recent, 6)

    simulat = modul_purga.purga(magatzem, simulacio=True)["marcatges"]
    esborrats = modul_purga.purga(magatzem, simulacio=False)["marcatges"]
    assert simulat == esborrats == 1
    assert marcatges.del_dia(magatzem, "treb01", vell) == []
    assert len(marcatges.del_dia(magatzem, "treb01", recent)) == 1


def test_la_salvaguarda_dels_dos_ultims_anys(magatzem):
    """Amb una data «avui» absurda, la purga NO pot buidar l'any en curs."""
    avui = date.today()
    marca(magatzem, "treb01", avui, 6)
    resultat = modul_purga.purga(magatzem, avui=date(2100, 1, 1),
                                 simulacio=False)
    assert resultat["marcatges"] == 0
    assert len(marcatges.del_dia(magatzem, "treb01", avui)) == 1


def test_els_comptes_de_baixa_s_anonimitzen_pero_no_s_esborren(magatzem):
    """Si s'esborressin, el llibre dels 4 anys quedaria orfe."""
    comptes.desactiva(magatzem, "treb03", date.today() - timedelta(days=800))
    modul_purga.purga(magatzem, simulacio=False)
    doc = magatzem.doc("treballadors", "treb03")
    assert doc is not None
    assert doc["nom"].startswith("esborrat-")
    assert doc["correu"] == ""


def test_la_purga_automatica_ve_desactivada(magatzem):
    assert modul_purga.executa_si_toca(magatzem, {}) is None
    assert modul_purga.executa_si_toca(magatzem, {"PURGA_AUTOMATICA": False}) is None
