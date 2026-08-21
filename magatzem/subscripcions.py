"""
magatzem/subscripcions.py — Subscripcions als avisos push.

Una subscripció és el que el navegador dona quan algú accepta rebre avisos:
una URL del servei de push del seu navegador (`endpoint`) més dues claus per
xifrar-li el missatge. Amb això, i només amb això, se li pot fer arribar un
avís al mòbil.

L'identificador del document és una EMPREMTA de l'endpoint, no l'endpoint
sencer: els endpoints són llarguíssims i porten caràcters que no valen com a
identificador a Firestore. Fer-ne l'empremta també fa que subscriure's dues
vegades des del mateix dispositiu no creï dos documents.

DADES PERSONALS: l'endpoint identifica un dispositiu concret d'una persona
concreta. Per això aquí hi ha `esborra_de` (que es crida en sortir i en donar
de baixa un compte) i per això surt a l'avís legal.
"""
from __future__ import annotations

import hashlib
from typing import Sequence

from core.model import ara_utc
from magatzem.conversio import de_moment
from magatzem.rebost import SUBSCRIPCIONS


def empremta(endpoint: str) -> str:
    """Identificador estable i curt d'un endpoint."""
    return hashlib.sha256((endpoint or "").encode("utf-8")).hexdigest()[:32]


def desa(mag, login: str, endpoint: str, p256dh: str, auth: str) -> str:
    """Desa (o refresca) la subscripció d'un dispositiu. Idempotent: el
    mateix dispositiu subscrit dues vegades és un sol document."""
    id_ = empremta(endpoint)
    mag.desa(SUBSCRIPCIONS, id_, {
        "treballador_id": login,
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth,
        "creada": de_moment(ara_utc()),
    })
    return id_


def de_treballador(mag, login: str) -> list[dict]:
    """Totes les subscripcions d'una persona: pot tenir-ne el mòbil i el PC."""
    return mag.consulta(SUBSCRIPCIONS, [("treballador_id", "==", login)])


def de_treballadors(mag, logins: Sequence[str]) -> list[dict]:
    """Les de diverses persones, per avisar tots els aprovadors d'un servei.

    Es consulta un a un i no amb un `in`: la llista d'aprovadors és curta i
    així no depenem del límit de valors que admet l'operador."""
    trobades: dict[str, dict] = {}
    for login in dict.fromkeys(logins or ()):        # sense repetits, en ordre
        for sub in de_treballador(mag, login):
            trobades[sub["id"]] = sub
    return list(trobades.values())


def esborra(mag, id_: str) -> None:
    """Treu una subscripció. Es crida quan el servei de push respon que ja no
    val (el navegador s'ha desinstal·lat, o l'usuari ha tret el permís)."""
    mag.esborra(SUBSCRIPCIONS, id_)


def esborra_per_endpoint(mag, endpoint: str) -> None:
    mag.esborra(SUBSCRIPCIONS, empremta(endpoint))


def esborra_de(mag, login: str) -> int:
    """Totes les d'una persona. En sortir de la sessió i en donar de baixa un
    compte: ningú ha de continuar rebent avisos d'una aplicació on ja no hi
    és."""
    quantes = 0
    for sub in de_treballador(mag, login):
        mag.esborra(SUBSCRIPCIONS, sub["id"])
        quantes += 1
    return quantes
