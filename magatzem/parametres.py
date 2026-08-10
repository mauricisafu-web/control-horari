"""magatzem/parametres.py — Els paràmetres de l'aplicació, en un sol document."""
from __future__ import annotations

from magatzem.rebost import DOC_CONFIG, PARAMETRES


def tots(mag) -> dict:
    """Una sola lectura per a tota la configuració."""
    return mag.doc(PARAMETRES, DOC_CONFIG) or {}


def enter(mag, clau: str, defecte: int = 0) -> int:
    try:
        return int(tots(mag).get(clau, defecte))
    except (TypeError, ValueError):
        return defecte


def text(mag, clau: str, defecte: str = "") -> str:
    valor = tots(mag).get(clau, defecte)
    return "" if valor is None else str(valor)


def desa(mag, clau: str, valor) -> None:
    mag.actualitza(PARAMETRES, DOC_CONFIG, {clau: valor})
