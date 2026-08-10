"""
core/comput.py — El cor: quantes hores havia de fer i quantes n'ha fet.

Funcions PURES. No consulten res, no saben quin dia és, no criden
`datetime.now()`. Reben les dades ja carregades i retornen números.

Regla que ho governa tot: res del que es calcula aquí es desa enlloc. Els
totals es tornen a fer cada vegada a partir dels fets registrats (marcatges,
absències aprovades, festius, patró vigent). És més lent i és auditable:
guanya l'auditable.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Mapping, Sequence

from core.model import (
    APROVADA, Absencia, Assignacio, ENTRADA, ETIQUETA_TIPUS, Marcatge,
    PAUSA_FI, PAUSA_INICI, ResumDia, ResumPeriode, SORTIDA,
)

JORNADA_MAXIMA_DEFECTE = 600      # 10 h; per sobre, s'avisa


def assignacio_vigent(data: date,
                      assignacions: Sequence[Assignacio]) -> Assignacio | None:
    """La que val aquell dia. Si n'hi ha més d'una (configuració solapada),
    guanya la de `data_inici` més recent."""
    vigents = [a for a in assignacions if a.vigent_el(data)]
    if not vigents:
        return None
    return max(vigents, key=lambda a: a.data_inici)


def minuts_teorics_dia(data: date, assignacions: Sequence[Assignacio],
                       festius: Mapping[date, str]) -> int:
    """Minuts que el treballador havia de fer aquell dia."""
    if data in (festius or {}):
        return 0
    assignacio = assignacio_vigent(data, assignacions)
    if assignacio is None:
        return 0
    minuts = sum(t.minuts for t in assignacio.patro.trams_del_dia(data.isoweekday()))
    if assignacio.coeficient == 100:
        return minuts
    return math.floor(minuts * assignacio.coeficient / 100 + 0.5)


def minuts_fets_dia(marcatges: Sequence[Marcatge],
                    jornada_maxima_minuts: int = JORNADA_MAXIMA_DEFECTE
                    ) -> tuple[int, int, tuple[str, ...]]:
    """(minuts treballats, minuts de pausa, anomalies) d'un dia.

    Les anomalies són cadenes en català, MAI excepcions: un dia rar s'ha de
    poder mostrar, no fer petar la pàgina de ningú."""
    valids = sorted((m for m in marcatges if m.compta), key=lambda m: m.moment)

    presencia = timedelta()
    pausa = timedelta()
    obert_entrada = None
    obert_pausa = None
    anterior = None
    anomalies: list[str] = []

    def avisa(text: str) -> None:
        if text not in anomalies:
            anomalies.append(text)

    for m in valids:
        if anterior is not None and m.tipus == anterior:
            avisa("dos marcatges del mateix tipus seguits")

        if m.tipus == ENTRADA:
            if obert_entrada is None:
                obert_entrada = m.moment
        elif m.tipus == SORTIDA:
            if obert_entrada is None:
                avisa("sortida sense entrada prèvia")
            else:
                presencia += m.moment - obert_entrada
                obert_entrada = None
            if obert_pausa is not None:
                avisa("pausa sense tancar")
                obert_pausa = None
        elif m.tipus == PAUSA_INICI:
            if obert_pausa is None:
                obert_pausa = m.moment
        elif m.tipus == PAUSA_FI:
            if obert_pausa is None:
                avisa("pausa sense tancar")
            else:
                pausa += m.moment - obert_pausa
                obert_pausa = None
        anterior = m.tipus

    # Una jornada oberta NO suma minuts: comptar fins a mitjanit inventaria
    # hores que ningú ha fet.
    if obert_entrada is not None:
        avisa("jornada oberta: falta la sortida")
    if obert_pausa is not None:
        avisa("pausa sense tancar")

    minuts_presencia = int(presencia.total_seconds() // 60)
    minuts_pausa = int(pausa.total_seconds() // 60)
    if minuts_presencia > jornada_maxima_minuts:
        avisa(f"jornada de més de {jornada_maxima_minuts // 60} h")

    return max(0, minuts_presencia - minuts_pausa), minuts_pausa, tuple(anomalies)


def absencia_del_dia(data: date,
                     absencies: Sequence[Absencia]) -> Absencia | None:
    """L'absència APROVADA que cobreix aquell dia, si n'hi ha."""
    for a in absencies:
        if a.estat == APROVADA and a.cobreix(data):
            return a
    return None


def resum_dia(data: date, marcatges: Sequence[Marcatge],
              assignacions: Sequence[Assignacio], festius: Mapping[date, str],
              absencies: Sequence[Absencia] = (),
              jornada_maxima_minuts: int = JORNADA_MAXIMA_DEFECTE) -> ResumDia:
    teorics = minuts_teorics_dia(data, assignacions, festius)
    fets, pausa, anomalies = minuts_fets_dia(marcatges, jornada_maxima_minuts)

    # Una absència aprovada cobreix EXACTAMENT els minuts teòrics del dia: qui
    # té vacances ni acumula saldo ni el perd.
    absencia = absencia_del_dia(data, absencies)
    minuts_absencia = teorics if absencia is not None else 0

    return ResumDia(
        data=data,
        minuts_teorics=teorics,
        minuts_fets=fets,
        minuts_pausa=pausa,
        minuts_absencia=minuts_absencia,
        saldo=fets + minuts_absencia - teorics,
        festiu=(festius or {}).get(data),
        absencia=ETIQUETA_TIPUS.get(absencia.tipus) if absencia else None,
        anomalies=anomalies,
        marcatges=tuple(sorted((m for m in marcatges if m.compta),
                               key=lambda m: m.moment)),
    )


def resum_periode(inici: date, fi: date, marcatges: Sequence[Marcatge],
                  assignacions: Sequence[Assignacio],
                  festius: Mapping[date, str],
                  absencies: Sequence[Absencia] = (),
                  jornada_maxima_minuts: int = JORNADA_MAXIMA_DEFECTE
                  ) -> ResumPeriode:
    """Dia a dia entre les dues dates incloses. NO consulta res."""
    if fi < inici:
        inici, fi = fi, inici

    # Índex per data ABANS del bucle: recórrer la llista sencera per a cada
    # dia faria que un informe anual s'arrossegués.
    per_dia: dict[date, list[Marcatge]] = {}
    for m in marcatges:
        per_dia.setdefault(m.data, []).append(m)

    dies: list[ResumDia] = []
    teorics = fets = absents = 0
    dia = inici
    while dia <= fi:
        resum = resum_dia(dia, per_dia.get(dia, ()), assignacions, festius,
                          absencies, jornada_maxima_minuts)
        dies.append(resum)
        teorics += resum.minuts_teorics
        fets += resum.minuts_fets
        absents += resum.minuts_absencia
        dia += timedelta(days=1)

    return ResumPeriode(
        inici=inici, fi=fi,
        minuts_teorics=teorics, minuts_fets=fets, minuts_absencia=absents,
        saldo=fets + absents - teorics,
        dies=tuple(dies),
    )


def formata_minuts(minuts: int) -> str:
    """95 -> '1 h 35 min' · -95 -> '−1 h 35 min' (signe menys tipogràfic)."""
    minuts = int(minuts or 0)
    signe = "−" if minuts < 0 else ""
    minuts = abs(minuts)
    return f"{signe}{minuts // 60} h {minuts % 60} min"
