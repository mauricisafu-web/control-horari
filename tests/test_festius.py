"""
Proves de core/festius.py.

CAP prova surt a Internet: la resposta s'injecta pel paràmetre `obre`. Un test
que depèn de la xarxa és un test que un dia fallarà sense que ningú hagi tocat
res, i que no funciona sense connexió.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import date

import pytest

from core import festius
from core.model import ErrorHorari


class RespostaFalsa:
    def __init__(self, contingut):
        self._contingut = contingut

    def read(self):
        return self._contingut

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def obre_amb(per_dataset: dict):
    """Fabrica un `obre` que retorna una resposta diferent per dataset."""
    def _obre(url):
        for fragment, dades in per_dataset.items():
            if fragment in url:
                return RespostaFalsa(json.dumps(dades).encode("utf-8"))
        return RespostaFalsa(b"[]")
    return _obre


def test_importa_generals_i_locals():
    obre = obre_amb({
        festius.DATASET_GENERALS: [
            {"data": "2026-01-01", "nom_festiu": "Cap d'Any"},
            {"data": "2026-01-06T00:00:00", "nom_festiu": "Reis"},
        ],
        festius.DATASET_LOCALS: [
            {"data": "2026-08-15", "nom_festiu": "Festa major"},
        ],
    })
    resultat = festius.importa(2026, "43152", obre=obre)
    assert len(resultat) == 3
    assert resultat[0] == (date(2026, 1, 1), "Cap d'Any", "general")
    assert resultat[-1] == (date(2026, 8, 15), "Festa major", "local")


def test_el_resultat_ve_ordenat_per_data():
    obre = obre_amb({festius.DATASET_GENERALS: [
        {"data": "2026-06-24", "nom_festiu": "Sant Joan"},
        {"data": "2026-01-01", "nom_festiu": "Cap d'Any"}]})
    dates = [f[0] for f in festius.importa(2026, obre=obre)]
    assert dates == sorted(dates)


def test_resposta_buida_no_peta():
    assert festius.importa(2026, obre=obre_amb({})) == []


def test_les_files_sense_data_s_ignoren_sense_tombar_la_importacio():
    """Tolerant en llegir, estricte en validar: si un dia el dataset canvia
    de forma, el que es pugui aprofitar s'aprofita."""
    obre = obre_amb({festius.DATASET_GENERALS: [
        {"nom_festiu": "Sense data"},
        {"data": "no és una data", "nom_festiu": "Dolenta"},
        {"data": "2026-01-01", "nom_festiu": "Bona"},
        "això no és ni un diccionari",
    ]})
    resultat = festius.importa(2026, obre=obre)
    assert resultat == [(date(2026, 1, 1), "Bona", "general")]


def test_una_data_repetida_no_es_duplica():
    obre = obre_amb({
        festius.DATASET_GENERALS: [{"data": "2026-08-15", "nom_festiu": "Assumpció"}],
        festius.DATASET_LOCALS: [{"data": "2026-08-15", "nom_festiu": "Festa major"}],
    })
    assert len(festius.importa(2026, obre=obre)) == 1


def test_json_invalid_dona_error_entenedor():
    def obre(url):
        return RespostaFalsa(b"<html>error del servidor</html>")
    with pytest.raises(ErrorHorari, match="format"):
        festius.importa(2026, obre=obre)


def test_error_de_xarxa_recorda_que_l_alta_manual_hi_es():
    def obre(url):
        raise urllib.error.URLError("sense connexió")
    with pytest.raises(ErrorHorari, match="a mà"):
        festius.importa(2026, obre=obre)


def test_temps_d_espera_exhaurit():
    def obre(url):
        raise TimeoutError()
    with pytest.raises(ErrorHorari):
        festius.importa(2026, obre=obre)


def test_el_codi_ine_viatja_a_la_consulta():
    vistos = []

    def obre(url):
        vistos.append(url)
        return RespostaFalsa(b"[]")

    festius.importa(2026, "43152", obre=obre)
    assert any("43152" in u for u in vistos)
    # I no hi viatja cap dada de ningú: només any i codi de municipi.
    assert all("treballador" not in u and "correu" not in u for u in vistos)
