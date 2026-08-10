"""
magatzem/horaris.py — Patrons d'horari.

Els trams viuen DINS del document del patró: sempre es llegeixen junts i són
pocs, o sigui que separar-los només costaria lectures.
"""
from __future__ import annotations

from typing import Sequence

from core.model import ErrorHorari, Patro, Tram
from magatzem.conversio import a_hora, de_hora
from magatzem.rebost import PATRONS

__all__ = ["PATRONS", "patrons", "patro", "desa_patro", "elimina_patro",
           "trams_des_de_formulari"]


def _a_patro(doc: dict) -> Patro:
    trams = []
    for t in doc.get("trams") or []:
        try:
            trams.append(Tram(int(t["dia_setmana"]),
                              a_hora(t["hora_inici"]), a_hora(t["hora_fi"])))
        except (KeyError, ValueError, TypeError):
            continue          # un tram malformat no ha de tombar el patró
    trams.sort(key=lambda t: (t.dia_setmana, t.hora_inici))
    return Patro(id=doc["id"], nom=doc.get("nom", ""),
                 trams=tuple(trams), descripcio=doc.get("descripcio", ""))


def patrons(mag) -> list[Patro]:
    return sorted((_a_patro(d) for d in mag.consulta(PATRONS)),
                  key=lambda p: p.nom.lower())


def patro(mag, patro_id: str) -> Patro | None:
    doc = mag.doc(PATRONS, patro_id) if patro_id else None
    return _a_patro(doc) if doc else None


def _valida_trams(trams: Sequence[Tram]) -> None:
    for t in trams:
        if not 1 <= t.dia_setmana <= 7:
            raise ErrorHorari("El dia de la setmana ha d'anar de dilluns a diumenge.")
        if t.hora_fi <= t.hora_inici:
            raise ErrorHorari(
                f"L'hora de fi ha de ser posterior a la d'inici "
                f"({de_hora(t.hora_inici)} - {de_hora(t.hora_fi)}).")
    # Solapaments dins del mateix dia: no és un error fatal, però amagar-ho
    # faria que les hores teòriques sortissin dobles sense explicació.
    per_dia: dict[int, list[Tram]] = {}
    for t in trams:
        per_dia.setdefault(t.dia_setmana, []).append(t)
    for dia, llista in per_dia.items():
        llista.sort(key=lambda t: t.hora_inici)
        for anterior, seguent in zip(llista, llista[1:]):
            if seguent.hora_inici < anterior.hora_fi:
                raise ErrorHorari(
                    "Hi ha dos trams del mateix dia que es trepitgen: "
                    f"{de_hora(anterior.hora_inici)}-{de_hora(anterior.hora_fi)} i "
                    f"{de_hora(seguent.hora_inici)}-{de_hora(seguent.hora_fi)}.")


def desa_patro(mag, nom: str, descripcio: str, trams: Sequence[Tram],
               patro_id: str | None = None) -> str:
    nom = (nom or "").strip()
    if not nom:
        raise ErrorHorari("El patró d'horari ha de tenir un nom.")
    _valida_trams(trams)
    dades = {
        "nom": nom, "descripcio": (descripcio or "").strip(),
        "trams": [{"dia_setmana": t.dia_setmana,
                   "hora_inici": de_hora(t.hora_inici),
                   "hora_fi": de_hora(t.hora_fi)} for t in trams],
    }
    if patro_id:
        if not mag.doc(PATRONS, patro_id):
            raise ErrorHorari("Aquest patró d'horari no existeix.")
        mag.desa(PATRONS, patro_id, dades)
        return patro_id
    return mag.afegeix(PATRONS, dades)


def elimina_patro(mag, patro_id: str) -> None:
    mag.esborra(PATRONS, patro_id)


def trams_des_de_formulari(dies, inicis, fins) -> list[Tram]:
    """Converteix les tres llistes paral·leles d'un formulari en trams.
    Les files buides s'ignoren en lloc de fer petar res."""
    trams = []
    for dia, inici, fi in zip(dies or [], inicis or [], fins or []):
        if not (dia and inici and fi):
            continue
        try:
            trams.append(Tram(int(dia), a_hora(inici), a_hora(fi)))
        except (ValueError, TypeError):
            raise ErrorHorari("Hi ha una hora que no té el format correcte (HH:MM).")
    return trams
