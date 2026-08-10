"""
magatzem/festius.py — Calendari laboral.

Un document per any amb TOTS els dies: llegir els festius d'un any és una
sola lectura, no una per dia. És el que fa que el resum mensual d'hores
costi ~90 lectures i no 400.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from core.model import AMBITS_FESTIU, ErrorHorari
from magatzem.conversio import a_data
from magatzem.rebost import FESTIUS


def _dies_del_any(mag, any: int) -> dict:
    doc = mag.doc(FESTIUS, str(any)) or {}
    return dict(doc.get("dies") or {})


def del_any(mag, any: int) -> dict[date, str]:
    """{data: nom} d'un any. UNA lectura."""
    resultat = {}
    for text, info in _dies_del_any(mag, any).items():
        dia = a_data(text)
        if dia is not None:
            resultat[dia] = (info or {}).get("nom", "Festiu")
    return resultat


def detall_del_any(mag, any: int) -> list[tuple[date, str, str]]:
    """(data, nom, àmbit), ordenat. Per a la pantalla de configuració."""
    files = []
    for text, info in _dies_del_any(mag, any).items():
        dia = a_data(text)
        if dia is not None:
            files.append((dia, (info or {}).get("nom", "Festiu"),
                          (info or {}).get("ambit", "general")))
    return sorted(files)


def entre(mag, inici: date, fi: date) -> dict[date, str]:
    """Festius d'un interval. Una lectura per any tocat (normalment, una)."""
    resultat: dict[date, str] = {}
    for any in range(inici.year, fi.year + 1):
        for dia, nom in del_any(mag, any).items():
            if inici <= dia <= fi:
                resultat[dia] = nom
    return resultat


def afegeix(mag, dia: date, nom: str, ambit: str = "general") -> None:
    if ambit not in AMBITS_FESTIU:
        raise ErrorHorari("L'àmbit del festiu no és vàlid.")
    dies = _dies_del_any(mag, dia.year)
    dies[dia.isoformat()] = {"nom": (nom or "Festiu").strip()[:120],
                             "ambit": ambit}
    mag.desa(FESTIUS, str(dia.year), {"any": dia.year, "dies": dies})


def elimina(mag, dia: date) -> None:
    dies = _dies_del_any(mag, dia.year)
    if dies.pop(dia.isoformat(), None) is not None:
        mag.desa(FESTIUS, str(dia.year), {"any": dia.year, "dies": dies})


def fusiona(mag, festius: Iterable[tuple[date, str, str]]) -> tuple[int, int]:
    """Afegeix els que no hi són. Retorna (nous, ja hi eren).

    No sobreescriu mai un festiu existent: els propis de l'ajuntament han de
    guanyar sobre el que digui una importació."""
    per_any: dict[int, dict] = {}
    nous = repetits = 0
    for dia, nom, ambit in festius:
        dies = per_any.setdefault(dia.year, _dies_del_any(mag, dia.year))
        clau = dia.isoformat()
        if clau in dies:
            repetits += 1
            continue
        dies[clau] = {"nom": (nom or "Festiu").strip()[:120], "ambit": ambit}
        nous += 1
    for any, dies in per_any.items():
        mag.desa(FESTIUS, str(any), {"any": any, "dies": dies})
    return nous, repetits
