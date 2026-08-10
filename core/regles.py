"""
core/regles.py — Regles d'absències: dies hàbils, saldos i permisos.

Funcions PURES: no consulten res, no escriuen res, no saben quin dia és
(llevat que els ho diguis). Es proven sense servidor.

Principi que governa tot el fitxer: el saldo DESAT és l'assignació anual; els
dies gastats es calculen SEMPRE sumant les absències aprovades. Cap operació
muta cap saldo. Per això anul·lar una absència retorna els dies tot sol i el
resultat és auditable i idempotent.
"""
from __future__ import annotations

import math
from calendar import isleap
from datetime import date, timedelta
from typing import Iterable, Sequence

from core.model import (
    APROVADA, AMBIT_TOTS, Absencia, ErrorHorari, ETIQUETA_TIPUS, PENDENT,
    ROL_ADMIN, ROL_RESPONSABLE, Saldo, Treballador,
)

# Divisor de la prorrata. És 365 SEMPRE, també els anys de traspàs: és el
# criteri heretat de la gestió de personal de l'ajuntament, no un error.
DIES_ANY = 365


def dies_habils(inici: date, fi: date, festius: Iterable[date]) -> int:
    """Dies laborables (dilluns a divendres) entre les dues dates INCLOSES,
    excloent-ne els festius."""
    if fi < inici:
        raise ErrorHorari("La data final no pot ser anterior a la inicial.")
    festius = set(festius or ())
    dies, dia = 0, inici
    while dia <= fi:
        if dia.weekday() < 5 and dia not in festius:
            dies += 1
        dia += timedelta(days=1)
    return dies


def dies_de_relacio(any: int, alta: date | None, baixa: date | None) -> int:
    """Dies d'un any en què hi ha relació laboral, comptant el dia d'alta.

    Sense cap de les dues dates dins de l'any, l'any sencer."""
    primer, ultim = date(any, 1, 1), date(any, 12, 31)
    inici = max(alta, primer) if alta else primer
    fi = min(baixa, ultim) if baixa else ultim
    if fi < inici:
        return 0
    return (fi - inici).days + 1


def es_any_sencer(any: int, alta: date | None, baixa: date | None) -> bool:
    """Cert si la relació laboral cobreix l'any de punta a punta: llavors no
    es prorrateja res (els treballadors de sempre no s'han de tocar)."""
    return dies_de_relacio(any, alta, baixa) >= (366 if isleap(any) else 365)


def arrodoneix_prorrata(valor: float) -> int:
    """Criteri de l'Administració pública: fracció >= 0,4 amunt.

    NO és el 0,5 habitual, i per això no es pot fer servir `round()` (que a
    més fa arrodoniment bancari: `round(14.5)` val 14).
        14,16 -> 14   ·   3,86 -> 4   ·   14,4 -> 15
    """
    enter = math.floor(valor)
    # L'epsilon evita que un 0,4 que en coma flotant surti 0,39999999 caigui
    # cap avall just al cas frontera, que és justament el que distingeix
    # aquesta funció de l'arrodoniment normal.
    return enter + 1 if (valor - enter) >= 0.4 - 1e-9 else enter


def prorrata_saldo(assignacio_anual: int, dies_relacio: int) -> int:
    """Dies que corresponen per un tram de relació laboral.

    Es prorrateja l'assignació DESADA, no la de configuració: qui tingui 26
    dies per conveni, se li prorrategen els 26."""
    if dies_relacio <= 0:
        return 0
    return arrodoneix_prorrata(dies_relacio * assignacio_anual / DIES_ANY)


def calcula_saldo(tipus: str, any: int, assignacio_anual: int,
                  absencies: Sequence[Absencia],
                  data_alta: date | None = None,
                  data_baixa: date | None = None) -> Saldo:
    """El saldo d'un tipus d'absència per a un any.

    `absencies` són les del treballador (de qualsevol any i tipus: aquí es
    filtren)."""
    delany = [a for a in absencies
              if a.tipus == tipus and a.data_inici.year == any]
    gastats = sum(a.dies for a in delany if a.estat == APROVADA)
    pendents = sum(a.dies for a in delany if a.estat == PENDENT)

    sencer = es_any_sencer(any, data_alta, data_baixa)
    dies_relacio = dies_de_relacio(any, data_alta, data_baixa)
    assignats = (assignacio_anual if sencer
                 else prorrata_saldo(assignacio_anual, dies_relacio))

    # El disponible pot quedar NEGATIU i no s'arrodoneix mai a zero: són dies
    # gaudits per damunt del meritat, que s'han de descomptar a la quitança.
    disponibles = assignats - gastats
    hi_ha_baixa = bool(data_baixa and data_baixa.year <= any)

    return Saldo(
        tipus=tipus, any=any,
        anual=assignacio_anual, assignats=assignats,
        gastats=gastats, pendents=pendents, disponibles=disponibles,
        prorratejat=not sencer, dies_relacio=dies_relacio,
        baixa=hi_ha_baixa, a_liquidar=disponibles if hi_ha_baixa else 0,
    )


def valida_solicitud(tipus: str, inici: date, fi: date, dies: int,
                     saldo: Saldo, solapaments: Sequence[Absencia] = ()) -> None:
    """Llança ErrorHorari, amb missatge per a l'usuari, si la sol·licitud no
    es pot acceptar."""
    if fi < inici:
        raise ErrorHorari("La data final no pot ser anterior a la inicial.")

    if inici.year != fi.year:
        raise ErrorHorari(
            "Una sol·licitud no pot anar d'un any a l'altre, perquè els dies "
            "es compten per any natural. Fes-ne dues: una fins al 31 de "
            "desembre i una altra a partir de l'1 de gener.")

    if dies <= 0:
        raise ErrorHorari(
            "Les dates que has triat no tenen cap dia hàbil: són tot cap de "
            "setmana o festiu.")

    if solapaments:
        primera = solapaments[0]
        raise ErrorHorari(
            f"Aquestes dates es trepitgen amb la sol·licitud {primera.codi} "
            f"({primera.data_inici.strftime('%d/%m/%Y')} - "
            f"{primera.data_fi.strftime('%d/%m/%Y')}), que ja tens "
            f"{'aprovada' if primera.estat == APROVADA else 'pendent'}.")

    if dies > saldo.disponibles:
        etiqueta = ETIQUETA_TIPUS.get(tipus, tipus).lower()
        if saldo.disponibles < 0:
            raise ErrorHorari(
                f"No pots demanar més dies de {etiqueta}: ja n'has gaudit "
                f"{abs(saldo.disponibles)} més dels que et corresponen aquest "
                f"any, i s'hauran de regularitzar.")
        raise ErrorHorari(
            f"Demanes {dies} dies de {etiqueta} i només te'n "
            f"{'queda 1' if saldo.disponibles == 1 else f'queden {saldo.disponibles}'}.")


def pot_resoldre(qui: Treballador, absencia: Absencia,
                 ambits: Sequence[str], servei_del_solicitant: str | None = None) -> bool:
    """Si `qui` pot aprovar o denegar aquesta sol·licitud.

    És una comprovació de SEGURETAT: cada ruta que resol una absència l'ha de
    cridar abans de tocar res."""
    # Mai la pròpia, ni sent administrador. Que la resolgui algú altre.
    if qui.id == absencia.treballador_id:
        return False
    if qui.rol == ROL_ADMIN:
        return True
    if qui.rol != ROL_RESPONSABLE:
        return False
    if AMBIT_TOTS in (ambits or ()):
        return True
    return servei_del_solicitant is not None and servei_del_solicitant in (ambits or ())
