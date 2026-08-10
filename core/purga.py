"""
core/purga.py — Conservació de dades.

Article 5.1.e del RGPD: no conservar les dades més enllà del que cal. Els
terminis són a DISSENY.md §3.6.

Dues salvaguardes que no es toquen:

· `simulacio=True` per defecte. Esborrar és irreversible i ha de ser una
  decisió conscient, no un efecte secundari d'una crida.
· MAI s'esborra res de l'any en curs ni de l'anterior, passi el que passi
  amb el càlcul de dates. És la xarxa contra un error que buidaria el llibre.

El log d'activitat NO es purga aquí: porta un camp `caduca_el` i a producció
l'esborra sola la política TTL de Firestore, gratuïtament.
"""
from __future__ import annotations

from datetime import date

from core.registre import registra

ANYS_MARCATGES = 4        # art. 34.9 de l'Estatut dels treballadors
ANYS_ABSENCIES = 4        # prescripció laboral
ANYS_COMPTES_BAIXA = 1    # després, anonimització

# Cap purga pot tocar l'any en curs ni l'anterior.
ANYS_INTOCABLES = 2


def data_limit(avui: date, anys: int, avui_real: date | None = None) -> date:
    """La data abans de la qual es pot esborrar, amb la salvaguarda aplicada.

    El sostre s'ancora a la data REAL, no a la que ens passin: l'amenaca que
    aixo evita es justament un `avui` mal calculat que faci el limit massa
    recent i buidi el llibre. Ancorar-lo a l'argument no protegiria de res."""
    avui_real = avui_real or date.today()
    proposta = date(avui.year - anys, avui.month, 1)
    sostre = date(avui_real.year - ANYS_INTOCABLES, 1, 1)
    return min(proposta, sostre)


def purga(mag, avui: date | None = None, simulacio: bool = True,
          maxim: int = 500) -> dict:
    """Esborra el que ha caducat. Retorna els comptadors per col·lecció."""
    from magatzem import absencies, comptes, marcatges

    avui = avui or date.today()
    limit_marcatges = data_limit(avui, ANYS_MARCATGES)
    limit_absencies = data_limit(avui, ANYS_ABSENCIES)

    resultat = {"simulacio": simulacio, "avui": avui.isoformat(),
                "limit_marcatges": limit_marcatges.isoformat(),
                "limit_absencies": limit_absencies.isoformat()}

    if simulacio:
        resultat["marcatges"] = len(mag.consulta(
            "marcatges", [("data", "<", limit_marcatges.isoformat())], limit=maxim))
        resultat["absencies"] = len(mag.consulta(
            "absencies", [("data_fi", "<", limit_absencies.isoformat())], limit=maxim))
    else:
        resultat["marcatges"] = marcatges.purga(mag, limit_marcatges, maxim)
        resultat["absencies"] = absencies.purga(mag, limit_absencies, maxim)

    # Comptes de baixa: anonimització, MAI esborrat. Si s'esborressin, el
    # llibre dels quatre anys quedaria orfe i s'incompliria justament
    # l'obligació que aquest mòdul havia de fer complir.
    anonimitzats = 0
    for treballador in comptes.llista(mag, actius=False):
        if treballador.actiu or not treballador.data_baixa:
            continue
        if treballador.data_baixa >= date(avui.year - ANYS_COMPTES_BAIXA,
                                          avui.month, 1):
            continue
        if treballador.nom.startswith("esborrat-"):
            continue
        anonimitzats += 1
        if not simulacio:
            comptes.actualitza(mag, treballador.login,
                               nom=f"esborrat-{treballador.login}",
                               correu="", correu_norm="")
    resultat["comptes_anonimitzats"] = anonimitzats

    registra("PURGA", detall=str(resultat))
    return resultat


def executa_si_toca(mag, config: dict) -> dict | None:
    """La crida d'arrencada. Només fa res amb `PURGA_AUTOMATICA=1`, que ve
    desactivat per defecte."""
    if not (config or {}).get("PURGA_AUTOMATICA"):
        return None
    return purga(mag, simulacio=False)
