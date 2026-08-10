"""Proves de core/calendari.py — la graella mensual."""
from __future__ import annotations

from datetime import date

import pytest

from core import calendari


def test_totes_les_setmanes_tenen_set_caselles():
    graella = calendari.graella_mes(2026, 8)
    assert all(len(s) == 7 for s in graella["setmanes"])


def test_comenca_en_dilluns():
    graella = calendari.graella_mes(2026, 8)
    assert graella["setmanes"][0][0]["data"].weekday() == 0


def test_els_dies_d_altres_mesos_es_marquen():
    graella = calendari.graella_mes(2026, 8)   # l'1 d'agost del 2026 és dissabte
    primera = graella["setmanes"][0]
    assert primera[0]["del_mes"] is False
    assert any(c["del_mes"] for c in primera)


def test_mes_que_comenca_en_dilluns():
    graella = calendari.graella_mes(2026, 6)   # l'1 de juny del 2026 és dilluns
    assert graella["setmanes"][0][0]["data"] == date(2026, 6, 1)


def test_febrer_d_any_de_traspas():
    graella = calendari.graella_mes(2028, 2)
    dies = [c["dia"] for s in graella["setmanes"] for c in s if c["del_mes"]]
    assert max(dies) == 29


@pytest.mark.parametrize("mes", [0, 13, "agost", None, -1, 99])
def test_els_mesos_invalids_cauen_al_mes_actual(mes):
    """Els paràmetres vénen de la URL: res del que hi arribi ha de petar."""
    graella = calendari.graella_mes(2026, mes)
    assert graella["mes"] == date.today().month
    assert graella["any"] == date.today().year


@pytest.mark.parametrize("any", ["dos mil", None, 1000, 9999])
def test_els_anys_invalids_cauen_a_l_any_actual(any):
    assert calendari.graella_mes(any, 8)["any"] == date.today().year


def test_navegacio_entre_mesos():
    assert calendari.graella_mes(2026, 1)["mes_anterior"] == (2025, 12)
    assert calendari.graella_mes(2026, 12)["mes_seguent"] == (2027, 1)


def test_els_esdeveniments_van_al_dia_correcte():
    graella = calendari.graella_mes(2026, 8, {date(2026, 8, 5): ["Vacances"]})
    caselles = [c for s in graella["setmanes"] for c in s
                if c["data"] == date(2026, 8, 5)]
    assert caselles[0]["items"] == ["Vacances"]


def test_els_festius_es_marquen():
    graella = calendari.graella_mes(2026, 8, festius={date(2026, 8, 15): "Assumpció"})
    caselles = [c for s in graella["setmanes"] for c in s
                if c["data"] == date(2026, 8, 15)]
    assert caselles[0]["festiu"] == "Assumpció"


def test_els_caps_de_setmana_es_marquen():
    graella = calendari.graella_mes(2026, 8)
    caselles = [c for s in graella["setmanes"] for c in s]
    dissabte = [c for c in caselles if c["data"] == date(2026, 8, 8)][0]
    dilluns = [c for c in caselles if c["data"] == date(2026, 8, 3)][0]
    assert dissabte["cap_de_setmana"] is True
    assert dilluns["cap_de_setmana"] is False
