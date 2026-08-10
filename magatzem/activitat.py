"""
magatzem/activitat.py — Rastre d'accions, persistit.

Complementa `core/registre.py` (que escriu al log del servidor): això és el
rastre consultable des de l'aplicació.

Cada entrada porta `caduca_el` a un any vista. A producció, una política TTL
de Firestore sobre aquest camp les esborra soles: gratuïtament, automàticament
i sense una línia de codi de purga.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from core.model import ara_utc
from magatzem.conversio import de_moment
from magatzem.rebost import ACTIVITAT

MESOS_CONSERVACIO = 12


def registra(mag, accio: str, usuari: str = "", detall: str = "",
             ip: str = "") -> None:
    """No llança mai: un error del rastre no pot tombar l'operació de
    l'usuari. Aquí no hi entren dades personals més enllà del login."""
    try:
        ara = ara_utc()
        mag.afegeix(ACTIVITAT, {
            "accio": str(accio)[:40],
            "usuari": str(usuari)[:60],
            "detall": str(detall)[:200],
            "ip": str(ip)[:60],
            "quan": de_moment(ara),
            "data": ara.date().isoformat(),
            "caduca_el": de_moment(ara + timedelta(days=365)),
        })
    except Exception:      # noqa: BLE001 — deliberadament ampli
        pass


def consulta(mag, desde: date | None = None, fins: date | None = None,
             usuari: str | None = None, limit: int = 200) -> list[dict]:
    filtres = []
    if usuari:
        filtres.append(("usuari", "==", usuari))
    elif desde:
        filtres.append(("data", ">=", desde.isoformat()))
    entrades = mag.consulta(ACTIVITAT, filtres, ordre="quan", descendent=True,
                            limit=limit)
    if fins:
        entrades = [e for e in entrades if e.get("data", "") <= fins.isoformat()]
    if usuari and desde:
        entrades = [e for e in entrades if e.get("data", "") >= desde.isoformat()]
    return entrades
