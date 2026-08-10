"""
core/fitxatge.py — Màquina d'estats del fitxatge.

Decideix què pot fitxar una persona en aquest moment i valida els marcatges
abans de desar-los. És el que fa impossible registrar una sortida sense haver
entrat.

Funcions PURES: no desen res ni consulten res.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from core.model import (
    DINS, EN_PAUSA, ENTRADA, FORA, Marcatge, ORIGEN_MANUAL, PAUSA_FI,
    PAUSA_INICI, PENDENT_VALIDACIO, SORTIDA, Treballador, VALID, ErrorHorari,
)

# Quines accions es poden fer des de cada estat. L'ORDRE importa: la interfície
# ensenya la primera com a botó principal.
ACCIONS = {
    FORA: (ENTRADA,),
    DINS: (PAUSA_INICI, SORTIDA),
    EN_PAUSA: (PAUSA_FI,),
}

ESTAT_DESPRES = {
    ENTRADA: DINS,
    SORTIDA: FORA,
    PAUSA_INICI: EN_PAUSA,
    PAUSA_FI: DINS,
}

EXPLICACIO_ESTAT = {
    FORA: "Ara mateix constes com a fora.",
    DINS: "Ara mateix constes com a dins.",
    EN_PAUSA: "Ara mateix constes en pausa.",
}


def _valids(marcatges: Sequence[Marcatge]) -> list[Marcatge]:
    """Ordenats per moment i només els que compten (ni anul·lats ni pendents
    de validar)."""
    return sorted((m for m in marcatges if m.compta), key=lambda m: m.moment)


def estat_actual(marcatges_del_dia: Sequence[Marcatge]) -> str:
    """FORA, DINS o EN_PAUSA segons l'últim marcatge vàlid del dia."""
    valids = _valids(marcatges_del_dia)
    if not valids:
        return FORA
    return ESTAT_DESPRES.get(valids[-1].tipus, FORA)


def accions_possibles(estat: str) -> tuple[str, ...]:
    return ACCIONS.get(estat, (ENTRADA,))


def valida_marcatge(tipus: str, moment: datetime,
                    marcatges_del_dia: Sequence[Marcatge],
                    minim_segons: int = 60) -> None:
    """ErrorHorari, amb missatge per a l'usuari, si aquest marcatge no toca."""
    estat = estat_actual(marcatges_del_dia)
    possibles = accions_possibles(estat)

    if tipus not in possibles:
        toca = {ENTRADA: "fitxar l'entrada",
                SORTIDA: "fitxar la sortida",
                PAUSA_INICI: "començar la pausa",
                PAUSA_FI: "tornar de la pausa"}[possibles[0]]
        raise ErrorHorari(f"{EXPLICACIO_ESTAT[estat]} El que toca ara és {toca}.")

    valids = _valids(marcatges_del_dia)
    if valids:
        ultim = valids[-1]
        # ESTRICTAMENT anterior. Dos marcatges del mateix segon NO són un
        # error de rellotge: `ara_utc()` trunca els microsegons, o sigui que
        # el cas d'igualtat és el doble toc, i li toca el missatge de sota.
        if moment < ultim.moment:
            raise ErrorHorari(
                "Aquest fitxatge és anterior a l'últim que tens registrat.")
        # El cas que passarà de debò: el doble toc a la pantalla del mòbil.
        # El missatge ha de tranquil·litzar, no acusar.
        if (moment - ultim.moment).total_seconds() < minim_segons:
            raise ErrorHorari("Aquest fitxatge ja s'ha registrat fa un moment.")


def prepara_correccio(original: Marcatge | None, tipus: str, moment: datetime,
                      nota: str, autor: Treballador) -> dict:
    """Els camps del marcatge NOU d'una correcció. No escriu res: qui escriu
    és `magatzem/marcatges.afegeix`."""
    if not (nota or "").strip():
        raise ErrorHorari("Cal que expliquis el motiu de la correcció.")
    if tipus not in ESTAT_DESPRES:
        raise ErrorHorari("El tipus de marcatge no és vàlid.")

    # Qui es corregeix a si mateix deixa el marcatge PENDENT DE VALIDAR. És
    # el que fa que el registre de jornada sigui creïble davant d'una
    # inspecció: ningú es canvia les hores sense que ho vegi ningú.
    estat = VALID if autor.pot_aprovar else PENDENT_VALIDACIO

    return {
        "tipus": tipus,
        "moment": moment,
        "origen": ORIGEN_MANUAL,
        "estat": estat,
        "nota": nota.strip()[:300],
        "anul_la_id": original.id if original is not None else None,
    }


def pot_validar(qui: Treballador, marcatge: Marcatge) -> bool:
    """Ningú valida una correcció que ha fet ell mateix. Comprovació de
    seguretat: la ruta de gestió l'ha de cridar abans de tocar res."""
    if not qui.pot_aprovar:
        return False
    return qui.id != marcatge.creat_per
