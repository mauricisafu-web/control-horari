"""
magatzem/absencies.py — Sol·licituds de vacances i assumptes propis.

L'identificador del document ÉS el codi (`A-2026-0001`). El `servei_id` s'hi
desa duplicat perquè un responsable pugui consultar les del seu servei sense
haver de llegir abans tots els treballadors: Firestore no fa unions.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from core.model import (
    AMBIT_TOTS, ANULADA, APROVADA, Absencia, DENEGADA, ErrorHorari, PENDENT,
    TIPUS_ABSENCIA, ara_utc,
)
from magatzem.conversio import a_data, a_moment, de_data, de_moment
from magatzem.rebost import ABSENCIES, COMPTADORS, SALDOS


def _a_absencia(doc: dict) -> Absencia:
    return Absencia(
        id=doc["id"], codi=doc.get("codi", doc["id"]),
        treballador_id=doc.get("treballador_id", ""),
        tipus=doc.get("tipus", ""),
        data_inici=a_data(doc.get("data_inici")),
        data_fi=a_data(doc.get("data_fi")),
        dies=int(doc.get("dies", 0)), estat=doc.get("estat", PENDENT),
        motiu=doc.get("motiu", ""), creada_el=a_moment(doc.get("creada_el")),
        resolta_per=doc.get("resolta_per"),
        resolta_el=a_moment(doc.get("resolta_el")),
        motiu_resolucio=doc.get("motiu_resolucio", ""),
    )


def _ordena(docs) -> list[Absencia]:
    absencies = [_a_absencia(d) for d in docs]
    return sorted((a for a in absencies if a.data_inici and a.data_fi),
                  key=lambda a: a.data_inici, reverse=True)


def per_codi(mag, codi: str) -> Absencia | None:
    doc = mag.doc(ABSENCIES, codi) if codi else None
    return _a_absencia(doc) if doc else None


def de_treballador(mag, login: str, any: int | None = None) -> list[Absencia]:
    absencies = _ordena(mag.consulta(ABSENCIES, [("treballador_id", "==", login)]))
    if any is None:
        return absencies
    return [a for a in absencies if a.data_inici.year == any]


def pendents(mag, serveis: Sequence[str]) -> list[Absencia]:
    if AMBIT_TOTS in (serveis or ()):
        docs = mag.consulta(ABSENCIES, [("estat", "==", PENDENT)])
    else:
        docs = []
        for servei_id in serveis or ():
            docs += mag.consulta(ABSENCIES, [("servei_id", "==", servei_id),
                                             ("estat", "==", PENDENT)])
    return sorted(_ordena(docs), key=lambda a: a.data_inici)


def aprovades_en(mag, inici: date, fi: date,
                 serveis: Sequence[str] | None = None) -> list[Absencia]:
    if serveis is None or AMBIT_TOTS in serveis:
        docs = mag.consulta(ABSENCIES, [("estat", "==", APROVADA)])
    else:
        docs = []
        for servei_id in serveis:
            docs += mag.consulta(ABSENCIES, [("servei_id", "==", servei_id),
                                             ("estat", "==", APROVADA)])
    # El filtre de dates es fa en memòria: Firestore no admet un rang sobre
    # data_inici i un altre sobre data_fi a la mateixa consulta.
    return [a for a in _ordena(docs) if a.data_inici <= fi and a.data_fi >= inici]


def solapaments(mag, login: str, inici: date, fi: date,
                excloent: str | None = None) -> list[Absencia]:
    """Les sol·licituds pròpies PENDENT o APROVADA que trepitgen aquestes
    dates."""
    return [a for a in de_treballador(mag, login)
            if a.estat in (PENDENT, APROVADA)
            and a.codi != excloent
            and a.data_inici <= fi and a.data_fi >= inici]


def solapaments_servei(mag, servei_id: str, inici: date, fi: date,
                       excloent_treballador: str | None = None) -> list[Absencia]:
    """Qui més del servei té absències que es trepitgen amb aquestes dates.
    És l'avís que evita quedar-se sense ningú a la brigada l'agost."""
    docs = mag.consulta(ABSENCIES, [("servei_id", "==", servei_id)])
    return [a for a in _ordena(docs)
            if a.estat in (PENDENT, APROVADA)
            and a.treballador_id != excloent_treballador
            and a.data_inici <= fi and a.data_fi >= inici]


def crea(mag, login: str, servei_id: str | None, tipus: str, inici: date,
         fi: date, dies: int, motiu: str = "") -> str:
    """Crea la sol·licitud i retorna el seu codi.

    El número surt d'un comptador ATÒMIC del servidor: comptar documents per
    saber quin toca faria que dues sol·licituds simultànies agafessin el
    mateix codi."""
    if tipus not in TIPUS_ABSENCIA:
        raise ErrorHorari("El tipus d'absència no és vàlid.")
    seguent = mag.incrementa(COMPTADORS, f"absencies_{inici.year}", "n")
    codi = f"A-{inici.year}-{seguent:04d}"
    mag.desa(ABSENCIES, codi, {
        "codi": codi, "treballador_id": login, "servei_id": servei_id,
        "tipus": tipus,
        "data_inici": de_data(inici), "data_fi": de_data(fi),
        "dies": int(dies), "estat": PENDENT, "motiu": (motiu or "")[:300],
        "creada_el": de_moment(ara_utc()),
        "resolta_per": None, "resolta_el": None, "motiu_resolucio": "",
    })
    return codi


def resol(mag, codi: str, estat: str, resolta_per: str, motiu: str = "") -> None:
    if estat not in (APROVADA, DENEGADA):
        raise ErrorHorari("La resolució ha de ser aprovar o denegar.")
    doc = mag.doc(ABSENCIES, codi)
    if doc is None:
        raise ErrorHorari("Aquesta sol·licitud no existeix.")
    if doc.get("estat") != PENDENT:
        raise ErrorHorari("Aquesta sol·licitud ja estava resolta.")
    mag.actualitza(ABSENCIES, codi, {
        "estat": estat, "resolta_per": resolta_per,
        "resolta_el": de_moment(ara_utc()), "motiu_resolucio": (motiu or "")[:300],
    })


def anula(mag, codi: str, per_qui: str) -> None:
    """Els dies tornen sols al disponible: el càlcul és dinàmic i aquí no es
    toca cap saldo."""
    doc = mag.doc(ABSENCIES, codi)
    if doc is None:
        raise ErrorHorari("Aquesta sol·licitud no existeix.")
    if doc.get("estat") == ANULADA:
        raise ErrorHorari("Aquesta sol·licitud ja estava anul·lada.")
    mag.actualitza(ABSENCIES, codi, {
        "estat": ANULADA, "resolta_per": per_qui,
        "resolta_el": de_moment(ara_utc()),
    })


# -- saldos -----------------------------------------------------------------
def _clau(login: str, any: int) -> str:
    return f"{login}_{any}"


def saldo_assignat(mag, login: str, any: int, tipus: str) -> int | None:
    doc = mag.doc(SALDOS, _clau(login, any))
    if not doc or tipus not in doc:
        return None
    try:
        return int(doc[tipus])
    except (TypeError, ValueError):
        return None


def desa_saldo(mag, login: str, any: int, tipus: str, dies: int) -> None:
    clau = _clau(login, any)
    if mag.doc(SALDOS, clau):
        mag.actualitza(SALDOS, clau, {tipus: int(dies)})
    else:
        mag.desa(SALDOS, clau, {"treballador_id": login, "any": int(any),
                                tipus: int(dies)})


def purga(mag, abans_de: date, maxim: int = 500) -> int:
    docs = mag.consulta(ABSENCIES, [("data_fi", "<", abans_de.isoformat())],
                        limit=maxim)
    for d in docs:
        mag.esborra(ABSENCIES, d["id"])
    return len(docs)
