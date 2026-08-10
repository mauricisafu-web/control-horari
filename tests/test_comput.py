"""Proves de core/comput.py — el cor del càlcul d'hores."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from core import comput
from core.model import (
    APROVADA, Absencia, Assignacio, ENTRADA, Marcatge, PAUSA_FI, PAUSA_INICI,
    PENDENT, PENDENT_VALIDACIO, Patro, SORTIDA, Tram, ZONA,
)

# Un patró de 7 h (08:00-15:00), de dilluns a divendres.
PATRO = Patro(id="p1", nom="Oficines",
              trams=tuple(Tram(d, time(8, 0), time(15, 0)) for d in range(1, 6)))
ASSIGNACIO = [Assignacio(patro=PATRO, data_inici=date(2020, 1, 1))]

DILLUNS = date(2026, 8, 3)
DISSABTE = date(2026, 8, 8)


def marca(hora_local, tipus, dia=DILLUNS, anulat=False, estat="VALID", id="m"):
    """Un marcatge a una hora LOCAL concreta, desat en UTC (com a producció)."""
    local = datetime.combine(dia, hora_local, tzinfo=ZONA)
    return Marcatge(id=id, treballador_id="treb01",
                    moment=local.astimezone(timezone.utc), data=dia,
                    tipus=tipus, anulat=anulat, estat=estat, creat_per="treb01")


# -- minuts teòrics ---------------------------------------------------------
def test_dia_laborable_normal():
    assert comput.minuts_teorics_dia(DILLUNS, ASSIGNACIO, {}) == 420


def test_cap_de_setmana_no_te_hores():
    assert comput.minuts_teorics_dia(DISSABTE, ASSIGNACIO, {}) == 0


def test_festiu_no_te_hores():
    assert comput.minuts_teorics_dia(DILLUNS, ASSIGNACIO,
                                     {DILLUNS: "Festa major"}) == 0


def test_sense_assignacio_vigent_no_te_hores():
    futura = [Assignacio(patro=PATRO, data_inici=date(2030, 1, 1))]
    assert comput.minuts_teorics_dia(DILLUNS, futura, {}) == 0


def test_mitja_jornada():
    mitja = [Assignacio(patro=PATRO, data_inici=date(2020, 1, 1), coeficient=50)]
    assert comput.minuts_teorics_dia(DILLUNS, mitja, {}) == 210


def test_coeficient_amb_arrodoniment():
    reduida = [Assignacio(patro=PATRO, data_inici=date(2020, 1, 1), coeficient=33)]
    assert comput.minuts_teorics_dia(DILLUNS, reduida, {}) == 139   # 138,6


def test_canvi_de_patro_a_mig_mes():
    """El cas que trenca els càlculs ingenus: guanya la vigent de cada dia."""
    estiu = Patro(id="p2", nom="Estiu",
                  trams=tuple(Tram(d, time(8, 0), time(14, 0)) for d in range(1, 6)))
    assignacions = [
        Assignacio(patro=PATRO, data_inici=date(2020, 1, 1), data_fi=date(2026, 8, 4)),
        Assignacio(patro=estiu, data_inici=date(2026, 8, 5)),
    ]
    assert comput.minuts_teorics_dia(date(2026, 8, 3), assignacions, {}) == 420
    assert comput.minuts_teorics_dia(date(2026, 8, 5), assignacions, {}) == 360


# -- minuts fets ------------------------------------------------------------
def test_jornada_completa():
    fets, pausa, anomalies = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"), marca(time(15, 0), SORTIDA, id="2")])
    assert fets == 420 and pausa == 0 and anomalies == ()


def test_jornada_amb_pausa():
    fets, pausa, anomalies = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(11, 0), PAUSA_INICI, id="2"),
        marca(time(11, 30), PAUSA_FI, id="3"),
        marca(time(15, 0), SORTIDA, id="4")])
    assert fets == 390 and pausa == 30 and anomalies == ()


def test_dues_jornades_el_mateix_dia():
    """Matí i tarda amb sortida al mig: normal a la brigada."""
    fets, _, anomalies = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"), marca(time(13, 0), SORTIDA, id="2"),
        marca(time(15, 0), ENTRADA, id="3"), marca(time(18, 0), SORTIDA, id="4")])
    assert fets == 480 and anomalies == ()


def test_anomalia_sortida_sense_entrada():
    _, _, anomalies = comput.minuts_fets_dia([marca(time(15, 0), SORTIDA)])
    assert "sortida sense entrada prèvia" in anomalies


def test_anomalia_jornada_oberta_no_suma_hores():
    """Comptar fins a mitjanit inventaria hores que ningú ha fet."""
    fets, _, anomalies = comput.minuts_fets_dia([marca(time(8, 0), ENTRADA)])
    assert fets == 0
    assert "jornada oberta: falta la sortida" in anomalies


def test_anomalia_pausa_sense_tancar():
    _, _, anomalies = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(11, 0), PAUSA_INICI, id="2")])
    assert "pausa sense tancar" in anomalies


def test_anomalia_jornada_massa_llarga():
    _, _, anomalies = comput.minuts_fets_dia([
        marca(time(6, 0), ENTRADA, id="1"), marca(time(20, 0), SORTIDA, id="2")])
    assert any("més de 10 h" in a for a in anomalies)


def test_anomalia_dos_marcatges_iguals_seguits():
    _, _, anomalies = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"), marca(time(9, 0), ENTRADA, id="2")])
    assert "dos marcatges del mateix tipus seguits" in anomalies


def test_els_marcatges_anulats_no_compten():
    fets, _, _ = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(12, 0), SORTIDA, id="2", anulat=True),
        marca(time(15, 0), SORTIDA, id="3")])
    assert fets == 420


def test_els_pendents_de_validacio_no_compten():
    fets, _, anomalies = comput.minuts_fets_dia([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(15, 0), SORTIDA, id="2", estat=PENDENT_VALIDACIO)])
    assert fets == 0
    assert "jornada oberta: falta la sortida" in anomalies


def test_els_marcatges_desordenats_s_ordenen():
    fets, _, anomalies = comput.minuts_fets_dia([
        marca(time(15, 0), SORTIDA, id="2"), marca(time(8, 0), ENTRADA, id="1")])
    assert fets == 420 and anomalies == ()


# -- resum del dia ----------------------------------------------------------
def test_resum_dia_amb_saldo_positiu():
    resum = comput.resum_dia(DILLUNS, [
        marca(time(8, 0), ENTRADA, id="1"), marca(time(16, 0), SORTIDA, id="2")],
        ASSIGNACIO, {})
    assert resum.minuts_teorics == 420 and resum.minuts_fets == 480
    assert resum.saldo == 60


def test_dia_de_vacances_aprovades_queda_a_zero():
    """Qui té vacances ni acumula saldo ni el perd."""
    vacances = [Absencia(id="A-2026-0001", codi="A-2026-0001",
                         treballador_id="treb01", tipus="vacances",
                         data_inici=DILLUNS, data_fi=DILLUNS, dies=1,
                         estat=APROVADA)]
    resum = comput.resum_dia(DILLUNS, [], ASSIGNACIO, {}, vacances)
    assert resum.minuts_absencia == 420 and resum.saldo == 0
    assert resum.absencia == "Vacances"


def test_una_absencia_pendent_no_cobreix_res():
    pendent = [Absencia(id="A-2026-0002", codi="A-2026-0002",
                        treballador_id="treb01", tipus="vacances",
                        data_inici=DILLUNS, data_fi=DILLUNS, dies=1,
                        estat=PENDENT)]
    resum = comput.resum_dia(DILLUNS, [], ASSIGNACIO, {}, pendent)
    assert resum.minuts_absencia == 0 and resum.saldo == -420


def test_dia_sense_fitxar_dona_saldo_negatiu():
    resum = comput.resum_dia(DILLUNS, [], ASSIGNACIO, {})
    assert resum.saldo == -420


# -- períodes ---------------------------------------------------------------
def test_resum_periode_suma_la_setmana():
    marcatges = []
    for i in range(5):
        dia = DILLUNS + timedelta(days=i)
        marcatges += [marca(time(8, 0), ENTRADA, dia=dia, id=f"e{i}"),
                      marca(time(15, 0), SORTIDA, dia=dia, id=f"s{i}")]
    resum = comput.resum_periode(DILLUNS, DILLUNS + timedelta(days=6),
                                 marcatges, ASSIGNACIO, {})
    assert resum.minuts_teorics == 2100 and resum.minuts_fets == 2100
    assert resum.saldo == 0 and len(resum.dies) == 7


def test_resum_periode_creua_el_canvi_d_hora():
    """L'últim diumenge d'octubre. Com que els instants són UTC, els minuts
    han de sortir bé encara que el rellotge local retrocedeixi una hora."""
    dilluns_despres = date(2026, 10, 26)
    marcatges = [marca(time(8, 0), ENTRADA, dia=dilluns_despres, id="1"),
                 marca(time(15, 0), SORTIDA, dia=dilluns_despres, id="2")]
    resum = comput.resum_periode(date(2026, 10, 24), date(2026, 10, 26),
                                 marcatges, ASSIGNACIO, {})
    assert resum.minuts_fets == 420


def test_resum_periode_d_un_any_es_rapid():
    import time as rellotge
    inici = rellotge.perf_counter()
    comput.resum_periode(date(2026, 1, 1), date(2026, 12, 31), [],
                         ASSIGNACIO, {})
    assert rellotge.perf_counter() - inici < 1.0


# -- format -----------------------------------------------------------------
def test_format_de_minuts():
    assert comput.formata_minuts(0) == "0 h 0 min"
    assert comput.formata_minuts(95) == "1 h 35 min"
    assert comput.formata_minuts(-95) == "−1 h 35 min"   # menys tipogràfic
