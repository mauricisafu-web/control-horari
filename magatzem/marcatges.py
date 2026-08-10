"""
magatzem/marcatges.py — El llibre de registre de jornada.

Un document NO s'edita ni s'esborra mai. Una correcció insereix un document
nou que apunta al corregit (`anul_la_id`) amb autor i motiu; l'única
escriptura permesa sobre un document existent és posar-hi `anulat: true`, i
sempre alhora que s'insereix el que el substitueix.

Aquesta és la col·lecció que creix de debò: ~24 treballadors × 2-4 marcatges
al dia × 4 anys de conservació. Cada consulta d'aquí compta contra el límit
gratuït diari, o sigui que cap d'elles pot anar sense filtre.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Sequence

from core.model import (
    AMBIT_TOTS, ErrorHorari, Marcatge, ORIGEN_WEB, PENDENT_VALIDACIO,
    REBUTJAT, TIPUS_MARCATGE, VALID, ara_utc, data_local,
)
from magatzem.conversio import a_data, a_moment, de_data, de_moment
from magatzem.rebost import MARCATGES


def _a_marcatge(doc: dict) -> Marcatge:
    return Marcatge(
        id=doc["id"], treballador_id=doc.get("treballador_id", ""),
        moment=a_moment(doc.get("moment")),
        data=a_data(doc.get("data")),
        tipus=doc.get("tipus", ""), origen=doc.get("origen", ORIGEN_WEB),
        estat=doc.get("estat", VALID), anulat=bool(doc.get("anulat", False)),
        anul_la_id=doc.get("anul_la_id"), nota=doc.get("nota", ""),
        creat_per=doc.get("creat_per"),
    )


def _ordena(docs) -> list[Marcatge]:
    marcatges = [_a_marcatge(d) for d in docs]
    return sorted((m for m in marcatges if m.moment and m.data),
                  key=lambda m: m.moment)


def del_dia(mag, login: str, dia: date) -> list[Marcatge]:
    return _ordena(mag.consulta(MARCATGES, [
        ("treballador_id", "==", login), ("data", "==", dia.isoformat())]))


def del_periode(mag, login: str, inici: date, fi: date) -> list[Marcatge]:
    """Igualtat sobre el treballador i UN rang sobre la data: és l'única forma
    que admet Firestore (no hi caben dues desigualtats)."""
    return _ordena(mag.consulta(MARCATGES, [
        ("treballador_id", "==", login),
        ("data", ">=", inici.isoformat()), ("data", "<=", fi.isoformat())]))


def del_periode_serveis(mag, serveis: Sequence[str], inici: date, fi: date
                        ) -> dict[str, list[Marcatge]]:
    """Els marcatges d'un àmbit, agrupats per treballador. UNA consulta per
    servei (o una de sola si l'àmbit és tot), mai una per persona."""
    rang = [("data", ">=", inici.isoformat()), ("data", "<=", fi.isoformat())]
    docs: list[dict] = []
    if AMBIT_TOTS in (serveis or ()):
        docs = mag.consulta(MARCATGES, rang)
    else:
        for servei_id in serveis or ():
            docs += mag.consulta(MARCATGES, [("servei_id", "==", servei_id)] + rang)

    per_treballador: dict[str, list[Marcatge]] = {}
    for m in _ordena(docs):
        per_treballador.setdefault(m.treballador_id, []).append(m)
    return per_treballador


def per_id(mag, marcatge_id: str) -> Marcatge | None:
    doc = mag.doc(MARCATGES, marcatge_id) if marcatge_id else None
    return _a_marcatge(doc) if doc else None


def afegeix(mag, login: str, tipus: str, moment: datetime, origen: str,
            creat_per: str, servei_id: str | None = None, ip: str = "",
            nota: str = "", anul_la_id: str | None = None,
            estat: str = VALID) -> str:
    """L'ÚNICA funció que escriu al llibre.

    Amb `anul_la_id`, insereix el document nou I marca l'original anul·lat
    dins del MATEIX lot: o hi són les dues escriptures o cap."""
    if tipus not in TIPUS_MARCATGE:
        raise ErrorHorari("El tipus de marcatge no és vàlid.")

    original = None
    if anul_la_id:
        original = mag.doc(MARCATGES, anul_la_id)
        if original is None:
            raise ErrorHorari("El marcatge que vols corregir no existeix.")
        if original.get("treballador_id") != login:
            raise ErrorHorari("Aquest marcatge no és d'aquest treballador.")
        if original.get("anulat"):
            raise ErrorHorari("Aquest marcatge ja estava corregit.")

    dia = data_local(moment)
    dades = {
        "treballador_id": login,
        "servei_id": servei_id,
        "moment": de_moment(moment),
        "data": de_data(dia),
        "tipus": tipus, "origen": origen,
        "anul_la_id": anul_la_id, "anulat": False, "estat": estat,
        "nota": (nota or "")[:300],
        "creat_el": de_moment(ara_utc()), "creat_per": creat_per,
        "ip": (ip or "")[:60],
    }

    if original is None:
        return mag.afegeix(MARCATGES, dades)

    nou_id = mag.afegeix(MARCATGES, dades)
    with mag.lot() as lot:
        lot.actualitza(MARCATGES, anul_la_id, {"anulat": True})
    return nou_id


def valida(mag, marcatge_id: str, validador_login: str, accepta: bool) -> None:
    """Accepta o rebutja una correcció pendent.

    En REBUTJAR, l'original torna a `anulat: false`. Sense això el dia es
    quedaria sense cap marcatge vàlid i desapareixerien hores d'una persona."""
    doc = mag.doc(MARCATGES, marcatge_id)
    if doc is None:
        raise ErrorHorari("Aquest marcatge no existeix.")
    if doc.get("estat") != PENDENT_VALIDACIO:
        raise ErrorHorari("Aquest marcatge no està pendent de validació.")

    with mag.lot() as lot:
        lot.actualitza(MARCATGES, marcatge_id, {
            "estat": VALID if accepta else REBUTJAT,
            "validat_per": validador_login,
            "validat_el": de_moment(ara_utc()),
        })
        original = doc.get("anul_la_id")
        if original and not accepta:
            lot.actualitza(MARCATGES, original, {"anulat": False})


def pendents_validacio(mag, serveis: Sequence[str]) -> list[Marcatge]:
    if AMBIT_TOTS in (serveis or ()):
        docs = mag.consulta(MARCATGES, [("estat", "==", PENDENT_VALIDACIO)])
    else:
        docs = []
        for servei_id in serveis or ():
            docs += mag.consulta(MARCATGES, [
                ("servei_id", "==", servei_id),
                ("estat", "==", PENDENT_VALIDACIO)])
    return _ordena(docs)


def purga(mag, abans_de: date, maxim: int = 500) -> int:
    """Esborra els marcatges anteriors a una data. Per lots: cada esborrat és
    una escriptura i el límit gratuït en són 20.000 al dia."""
    docs = mag.consulta(MARCATGES, [("data", "<", abans_de.isoformat())],
                        limit=maxim)
    for d in docs:
        mag.esborra(MARCATGES, d["id"])
    return len(docs)
