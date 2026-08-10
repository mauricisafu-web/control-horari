"""
core/calendari.py — Graella mensual.

Estructura PURA, sense una sola etiqueta HTML: qui pinta és la plantilla. La
mateixa funció serveix per al calendari personal (absències pròpies) i per al
del servei (absències de tothom): només canvia què li passes a
`esdeveniments`.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Mapping, Sequence

from core.model import MESOS


def _normalitza(any, mes) -> tuple[int, int]:
    """Any i mes vàlids. Els paràmetres vénen de la URL i qualsevol hi pot
    escriure el que vulgui: res del que arribi ha de fer petar la pàgina."""
    avui = date.today()
    try:
        any = int(any)
        mes = int(mes)
    except (TypeError, ValueError):
        return avui.year, avui.month
    if not (1 <= mes <= 12) or not (1900 <= any <= 2200):
        return avui.year, avui.month
    return any, mes


def graella_mes(any, mes, esdeveniments: Mapping[date, Sequence] | None = None,
                festius: Mapping[date, str] | None = None) -> dict:
    """Graella de dilluns a diumenge, amb totes les setmanes de 7 caselles.

    Els dies d'abans i després del mes hi surten amb `del_mes: False` perquè
    la graella no quedi coixa."""
    any, mes = _normalitza(any, mes)
    esdeveniments = esdeveniments or {}
    festius = festius or {}

    anterior = (any - 1, 12) if mes == 1 else (any, mes - 1)
    seguent = (any + 1, 1) if mes == 12 else (any, mes + 1)

    setmanes = []
    for setmana in calendar.Calendar(firstweekday=0).monthdatescalendar(any, mes):
        caselles = []
        for dia in setmana:
            caselles.append({
                "dia": dia.day,
                "data": dia,
                "del_mes": dia.month == mes,
                "festiu": festius.get(dia),
                "cap_de_setmana": dia.weekday() >= 5,
                "avui": dia == date.today(),
                "items": list(esdeveniments.get(dia, ())),
            })
        setmanes.append(caselles)

    return {
        "any": any, "mes": mes, "nom_mes": MESOS[mes - 1],
        "mes_anterior": anterior, "mes_seguent": seguent,
        "setmanes": setmanes,
    }
