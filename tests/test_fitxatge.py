"""Proves de core/fitxatge.py — la màquina d'estats del fitxatge."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from core import fitxatge
from core.model import (
    DINS, EN_PAUSA, ENTRADA, ErrorHorari, FORA, Marcatge, ORIGEN_MANUAL,
    PAUSA_FI, PAUSA_INICI, PENDENT_VALIDACIO, ROL_ADMIN, ROL_RESPONSABLE,
    ROL_TREBALLADOR, SORTIDA, Treballador, VALID, ZONA,
)

DIA = date(2026, 8, 3)


def marca(hora, tipus, anulat=False, estat=VALID, id="m", creat_per="treb01"):
    local = datetime.combine(DIA, hora, tzinfo=ZONA)
    return Marcatge(id=id, treballador_id="treb01",
                    moment=local.astimezone(timezone.utc), data=DIA,
                    tipus=tipus, anulat=anulat, estat=estat, creat_per=creat_per)


def moment(hora):
    return datetime.combine(DIA, hora, tzinfo=ZONA).astimezone(timezone.utc)


def treballador(id="treb01", rol=ROL_TREBALLADOR):
    return Treballador(id=id, login=id, nom=id, correu=f"{id}@exemple.cat", rol=rol)


# -- estat ------------------------------------------------------------------
def test_sense_marcatges_es_fora():
    assert fitxatge.estat_actual([]) == FORA


def test_despres_d_entrar_es_dins():
    assert fitxatge.estat_actual([marca(time(8, 0), ENTRADA)]) == DINS


def test_durant_la_pausa():
    assert fitxatge.estat_actual([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(11, 0), PAUSA_INICI, id="2")]) == EN_PAUSA


def test_despres_de_tornar_de_la_pausa_torna_a_ser_dins():
    assert fitxatge.estat_actual([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(11, 0), PAUSA_INICI, id="2"),
        marca(time(11, 30), PAUSA_FI, id="3")]) == DINS


def test_despres_de_sortir_torna_a_ser_fora():
    assert fitxatge.estat_actual([
        marca(time(8, 0), ENTRADA, id="1"),
        marca(time(15, 0), SORTIDA, id="2")]) == FORA


def test_un_marcatge_anulat_no_canvia_l_estat():
    assert fitxatge.estat_actual([
        marca(time(8, 0), ENTRADA, id="1", anulat=True)]) == FORA


def test_una_entrada_pendent_de_validar_deixa_la_persona_fora():
    """Si l'última entrada està pendent de validar, la persona continua
    constant com a fora: encara no compta."""
    assert fitxatge.estat_actual([
        marca(time(8, 0), ENTRADA, id="1", estat=PENDENT_VALIDACIO)]) == FORA


# -- accions ----------------------------------------------------------------
def test_accions_des_de_cada_estat():
    assert fitxatge.accions_possibles(FORA) == (ENTRADA,)
    assert fitxatge.accions_possibles(DINS) == (PAUSA_INICI, SORTIDA)
    assert fitxatge.accions_possibles(EN_PAUSA) == (PAUSA_FI,)


# -- validació --------------------------------------------------------------
def test_entrada_estant_fora_es_valida():
    fitxatge.valida_marcatge(ENTRADA, moment(time(8, 0)), [])


def test_sortida_estant_fora_diu_que_toca_entrar():
    with pytest.raises(ErrorHorari) as e:
        fitxatge.valida_marcatge(SORTIDA, moment(time(15, 0)), [])
    assert "constes com a fora" in str(e.value)
    assert "fitxar l'entrada" in str(e.value)


def test_doble_toc_del_mobil_amb_missatge_tranquil():
    marcatges = [marca(time(8, 0), ENTRADA)]
    with pytest.raises(ErrorHorari) as e:
        fitxatge.valida_marcatge(PAUSA_INICI, moment(time(8, 0)) + timedelta(seconds=5),
                                 marcatges)
    assert "ja s'ha registrat fa un moment" in str(e.value)


def test_marcatge_anterior_a_l_ultim():
    marcatges = [marca(time(12, 0), ENTRADA)]
    with pytest.raises(ErrorHorari, match="anterior"):
        fitxatge.valida_marcatge(SORTIDA, moment(time(9, 0)), marcatges)


def test_cicle_sencer_del_dia():
    marcatges = []
    for hora, tipus in ((time(8, 0), ENTRADA), (time(11, 0), PAUSA_INICI),
                        (time(11, 30), PAUSA_FI), (time(15, 0), SORTIDA)):
        fitxatge.valida_marcatge(tipus, moment(hora), marcatges)
        marcatges.append(marca(hora, tipus, id=f"m{len(marcatges)}"))
    assert fitxatge.estat_actual(marcatges) == FORA


# -- correccions ------------------------------------------------------------
def test_correccio_d_un_treballador_queda_pendent_de_validar():
    original = marca(time(15, 0), SORTIDA, id="orig")
    camps = fitxatge.prepara_correccio(original, SORTIDA, moment(time(17, 0)),
                                       "Vaig oblidar-me de fitxar", treballador())
    assert camps["estat"] == PENDENT_VALIDACIO
    assert camps["anul_la_id"] == "orig"
    assert camps["origen"] == ORIGEN_MANUAL


def test_correccio_d_un_responsable_ja_es_valida():
    camps = fitxatge.prepara_correccio(None, SORTIDA, moment(time(17, 0)),
                                       "Afegit pel responsable",
                                       treballador("resp01", ROL_RESPONSABLE))
    assert camps["estat"] == VALID
    assert camps["anul_la_id"] is None


def test_una_correccio_sense_motiu_no_val():
    with pytest.raises(ErrorHorari, match="motiu"):
        fitxatge.prepara_correccio(None, SORTIDA, moment(time(17, 0)), "  ",
                                   treballador())


def test_correccio_amb_un_tipus_inventat():
    with pytest.raises(ErrorHorari):
        fitxatge.prepara_correccio(None, "esmorzar", moment(time(10, 0)),
                                   "motiu", treballador())


# -- qui valida -------------------------------------------------------------
def test_ningu_valida_una_correccio_seva():
    resp = treballador("resp01", ROL_RESPONSABLE)
    seva = marca(time(9, 0), ENTRADA, creat_per="resp01")
    assert fitxatge.pot_validar(resp, seva) is False


def test_un_responsable_valida_la_d_un_altre():
    resp = treballador("resp01", ROL_RESPONSABLE)
    aliena = marca(time(9, 0), ENTRADA, creat_per="treb01")
    assert fitxatge.pot_validar(resp, aliena) is True


def test_un_admin_tambe_valida():
    admin = treballador("admin01", ROL_ADMIN)
    assert fitxatge.pot_validar(admin, marca(time(9, 0), ENTRADA)) is True


def test_un_treballador_ras_no_valida_res():
    assert fitxatge.pot_validar(treballador("treb02"),
                                marca(time(9, 0), ENTRADA)) is False
