"""Proves de core/regles.py — dies hàbils, prorrateig i permisos."""
from __future__ import annotations

from datetime import date

import pytest

from core import regles
from core.model import (
    AMBIT_TOTS, APROVADA, Absencia, ErrorHorari, PENDENT, ROL_ADMIN,
    ROL_RESPONSABLE, ROL_TREBALLADOR, Treballador,
)


def treballador(id="treb01", rol=ROL_TREBALLADOR, servei_id="s1"):
    return Treballador(id=id, login=id, nom=id, correu=f"{id}@exemple.cat",
                       rol=rol, servei_id=servei_id)


def absencia(codi="A-2026-0001", treballador_id="treb01", tipus="vacances",
             inici=date(2026, 8, 3), fi=date(2026, 8, 14), dies=10,
             estat=APROVADA):
    return Absencia(id=codi, codi=codi, treballador_id=treballador_id,
                    tipus=tipus, data_inici=inici, data_fi=fi, dies=dies,
                    estat=estat)


# -- dies hàbils ------------------------------------------------------------
def test_dies_habils_una_setmana_sencera():
    assert regles.dies_habils(date(2026, 8, 3), date(2026, 8, 7), []) == 5


def test_dies_habils_exclou_cap_de_setmana():
    # De dilluns a diumenge: només 5 de laborables.
    assert regles.dies_habils(date(2026, 8, 3), date(2026, 8, 9), []) == 5


def test_dies_habils_exclou_festius():
    assert regles.dies_habils(date(2026, 8, 3), date(2026, 8, 7),
                              [date(2026, 8, 5)]) == 4


def test_dies_habils_un_sol_dia():
    assert regles.dies_habils(date(2026, 8, 3), date(2026, 8, 3), []) == 1


def test_dies_habils_cap_de_setmana_sencer_dona_zero():
    assert regles.dies_habils(date(2026, 8, 8), date(2026, 8, 9), []) == 0


def test_dies_habils_amb_data_final_anterior():
    with pytest.raises(ErrorHorari):
        regles.dies_habils(date(2026, 8, 7), date(2026, 8, 3), [])


# -- prorrateig -------------------------------------------------------------
def test_arrodoniment_fraccio_petita_avall():
    assert regles.arrodoneix_prorrata(14.16) == 14


def test_arrodoniment_fraccio_gran_amunt():
    assert regles.arrodoneix_prorrata(3.86) == 4


def test_arrodoniment_el_cas_del_0_4_puja():
    """El cas que distingeix el criteri de l'Administració del 0,5 habitual:
    amb round() de Python això valdria 14."""
    assert regles.arrodoneix_prorrata(14.4) == 15


def test_dies_de_relacio_alta_a_mig_any_compta_el_dia_d_alta():
    # De l'11/05/2026 al 31/12/2026.
    assert regles.dies_de_relacio(2026, date(2026, 5, 11), None) == 235


def test_dies_de_relacio_any_sencer():
    assert regles.dies_de_relacio(2026, date(2020, 1, 1), None) == 365


def test_dies_de_relacio_baixa_a_mig_any():
    assert regles.dies_de_relacio(2026, None, date(2026, 8, 31)) == 243


def test_prorrateig_del_cas_de_referencia():
    """Alta l'11/05/2026: 235 dies -> 14 de vacances i 4 d'assumptes propis."""
    assert regles.prorrata_saldo(22, 235) == 14
    assert regles.prorrata_saldo(6, 235) == 4


def test_prorrateig_de_l_assignacio_desada_no_de_la_de_config():
    """Qui tingui 26 dies per conveni, se li prorrategen els 26."""
    assert regles.prorrata_saldo(26, 235) == 17


# -- saldo ------------------------------------------------------------------
def test_saldo_sense_alta_ni_baixa_no_es_prorrateja():
    saldo = regles.calcula_saldo("vacances", 2026, 22, [])
    assert saldo.assignats == 22 and not saldo.prorratejat
    assert saldo.disponibles == 22


def test_saldo_descompta_nomes_les_aprovades():
    absencies = [absencia(dies=10, estat=APROVADA),
                 absencia(codi="A-2026-0002", dies=3, estat=PENDENT,
                          inici=date(2026, 9, 1), fi=date(2026, 9, 3))]
    saldo = regles.calcula_saldo("vacances", 2026, 22, absencies)
    assert saldo.gastats == 10
    assert saldo.pendents == 3
    assert saldo.disponibles == 12


def test_saldo_prorratejat_amb_alta_a_mig_any():
    saldo = regles.calcula_saldo("vacances", 2026, 22, [],
                                 data_alta=date(2026, 5, 11))
    assert saldo.prorratejat and saldo.assignats == 14
    assert saldo.dies_relacio == 235


def test_saldo_negatiu_amb_baixa_no_s_arrodoneix_a_zero():
    """Qui plega el 31/08 merita 15 dies; si n'ha gaudit 20, en deu 5. Això
    NO es tapa: són dies cobrats de més per a la quitança."""
    absencies = [absencia(dies=20)]
    saldo = regles.calcula_saldo("vacances", 2026, 22, absencies,
                                 data_baixa=date(2026, 8, 31))
    assert saldo.assignats == 15
    assert saldo.disponibles == -5
    assert saldo.baixa and saldo.a_liquidar == -5


# -- validació de sol·licituds ---------------------------------------------
def saldo_amb(disponibles):
    return regles.calcula_saldo("vacances", 2026, disponibles, [])


def test_solicitud_correcta_no_llanca_res():
    regles.valida_solicitud("vacances", date(2026, 8, 3), date(2026, 8, 7),
                            5, saldo_amb(22))


def test_solicitud_amb_data_final_anterior():
    with pytest.raises(ErrorHorari, match="anterior"):
        regles.valida_solicitud("vacances", date(2026, 8, 7), date(2026, 8, 3),
                                1, saldo_amb(22))


def test_solicitud_que_creua_l_any():
    with pytest.raises(ErrorHorari, match="d'un any a l'altre"):
        regles.valida_solicitud("vacances", date(2026, 12, 28),
                                date(2027, 1, 5), 5, saldo_amb(22))


def test_solicitud_sense_prou_saldo():
    with pytest.raises(ErrorHorari, match="queden 3"):
        regles.valida_solicitud("vacances", date(2026, 8, 3), date(2026, 8, 14),
                                10, saldo_amb(3))


def test_solicitud_amb_saldo_negatiu_explica_el_deute():
    saldo = regles.calcula_saldo("vacances", 2026, 22, [absencia(dies=20)],
                                 data_baixa=date(2026, 8, 31))
    with pytest.raises(ErrorHorari, match="dels que et corresponen"):
        regles.valida_solicitud("vacances", date(2026, 9, 1), date(2026, 9, 2),
                                2, saldo)


def test_solicitud_solapada_diu_amb_quina():
    with pytest.raises(ErrorHorari, match="A-2026-0001"):
        regles.valida_solicitud("vacances", date(2026, 8, 5), date(2026, 8, 6),
                                2, saldo_amb(22), [absencia()])


def test_solicitud_sense_cap_dia_habil():
    with pytest.raises(ErrorHorari, match="cap dia hàbil"):
        regles.valida_solicitud("vacances", date(2026, 8, 8), date(2026, 8, 9),
                                0, saldo_amb(22))


# -- permisos ---------------------------------------------------------------
def test_ningu_resol_la_seva_propia_ni_sent_admin():
    admin = treballador("admin01", ROL_ADMIN)
    propia = absencia(treballador_id="admin01")
    assert regles.pot_resoldre(admin, propia, [AMBIT_TOTS]) is False


def test_admin_resol_la_d_un_altre():
    admin = treballador("admin01", ROL_ADMIN)
    assert regles.pot_resoldre(admin, absencia(), []) is True


def test_responsable_amb_el_servei_del_solicitant():
    resp = treballador("resp01", ROL_RESPONSABLE)
    assert regles.pot_resoldre(resp, absencia(), ["s1"], "s1") is True


def test_responsable_sense_el_servei_no_pot():
    resp = treballador("resp01", ROL_RESPONSABLE)
    assert regles.pot_resoldre(resp, absencia(), ["s2"], "s1") is False


def test_responsable_amb_ambit_de_tots_els_serveis():
    resp = treballador("resp01", ROL_RESPONSABLE)
    assert regles.pot_resoldre(resp, absencia(), [AMBIT_TOTS], "s9") is True


def test_un_treballador_ras_no_resol_res():
    assert regles.pot_resoldre(treballador(), absencia("A-2026-0009", "altre"),
                               ["s1"], "s1") is False
