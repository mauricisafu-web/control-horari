"""Proves dels repositoris de magatzem/."""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from core.model import (
    AMBIT_TOTS, APROVADA, DENEGADA, ENTRADA, ErrorHorari, PENDENT,
    PENDENT_VALIDACIO, REBUTJAT, SORTIDA, Tram, VALID, ara_utc,
)
from magatzem import (
    absencies, comptes, festius, horaris, marcatges, parametres, serveis,
)

DIA = date(2026, 8, 3)


# -- paràmetres -------------------------------------------------------------
def test_parametres_inicials(magatzem):
    assert parametres.enter(magatzem, "dies_vacances_defecte", 0) == 22
    assert parametres.text(magatzem, "codi_ine_municipi") == "43152"


def test_desar_un_parametre(magatzem):
    parametres.desa(magatzem, "dies_ap_defecte", 8)
    assert parametres.enter(magatzem, "dies_ap_defecte", 0) == 8


def test_un_parametre_corrupte_no_peta(magatzem):
    parametres.desa(magatzem, "jornada_maxima_minuts", "molt")
    assert parametres.enter(magatzem, "jornada_maxima_minuts", 600) == 600


# -- comptes ----------------------------------------------------------------
def test_lectura_directa_per_login(magatzem):
    treballador = comptes.per_login(magatzem, "treb01")
    assert treballador.nom == "Treballador U"
    assert treballador.servei == "Oficines"      # el nom del servei, resolt


def test_compte_inexistent(magatzem):
    assert comptes.per_login(magatzem, "no-hi-soc") is None


def test_cerca_per_correu_ignora_majuscules(magatzem):
    assert comptes.per_correu(magatzem, "  TREB01@Exemple.CAT ").login == "treb01"


def test_llista_nomes_els_actius(magatzem):
    comptes.desactiva(magatzem, "treb03", date(2026, 6, 30))
    logins = [t.login for t in comptes.llista(magatzem)]
    assert "treb03" not in logins
    assert "treb03" in [t.login for t in comptes.llista(magatzem, actius=False)]


def test_donar_de_baixa_no_esborra_el_compte(magatzem):
    """El registre de jornada s'ha de conservar 4 anys i els marcatges hi
    apunten: un compte no s'esborra mai."""
    comptes.desactiva(magatzem, "treb03", date(2026, 6, 30))
    assert magatzem.doc("treballadors", "treb03") is not None


def test_alta_amb_login_repetit(magatzem):
    with pytest.raises(ErrorHorari, match="(?i)ja hi ha un compte"):
        comptes.crea(magatzem, "treb01", "Un altre", "nou@exemple.cat",
                     "hash", "treballador")


def test_alta_amb_correu_repetit(magatzem):
    with pytest.raises(ErrorHorari, match="correu"):
        comptes.crea(magatzem, "treb09", "Nou", "treb01@exemple.cat",
                     "hash", "treballador")


def test_alta_correcta_neix_amb_canvi_pendent(magatzem):
    comptes.crea(magatzem, "treb09", "Nova", "treb09@exemple.cat", "hash",
                 "treballador", data_alta=date(2026, 5, 11))
    doc = magatzem.doc("treballadors", "treb09")
    assert doc["canvi_pendent"] is True and doc["actiu"] is True


def test_actualitza_te_llista_blanca(magatzem):
    with pytest.raises(ErrorHorari, match="no es poden modificar"):
        comptes.actualitza(magatzem, "treb01", rol="admin", es_deu="molt")


def test_actualitza_normalitza_el_correu(magatzem):
    comptes.actualitza(magatzem, "treb01", correu="  NOU@Exemple.CAT ")
    assert comptes.per_correu(magatzem, "nou@exemple.cat").login == "treb01"


def test_ambits_d_un_responsable(magatzem, serveis_ids):
    assert comptes.ambits_de(magatzem, "resp01") == [serveis_ids["Oficines"]]
    assert comptes.ambits_de(magatzem, "treb01") == []


def test_ambit_de_tots_els_serveis(magatzem):
    comptes.desa_ambits(magatzem, "resp01", [AMBIT_TOTS])
    assert AMBIT_TOTS in comptes.ambits_de(magatzem, "resp01")
    assert len(comptes.de_serveis(magatzem, [AMBIT_TOTS])) == 6


def test_assignacions_amb_el_patro_sencer(magatzem):
    assignacions = comptes.assignacions_de(magatzem, "treb01")
    assert len(assignacions) == 1
    assert len(assignacions[0].patro.trams) == 5
    assert assignacions[0].patro.trams[0].minuts == 420


def test_assignar_un_patro_inexistent(magatzem):
    with pytest.raises(ErrorHorari, match="patró"):
        comptes.assigna(magatzem, "treb01", "no-existeix", DIA)


def test_coeficient_fora_de_rang(magatzem, patro_id):
    with pytest.raises(ErrorHorari, match="percentatge"):
        comptes.assigna(magatzem, "treb01", patro_id, DIA, coeficient=150)


# -- serveis ----------------------------------------------------------------
def test_crear_un_servei_repetit(magatzem):
    with pytest.raises(ErrorHorari, match="(?i)ja hi ha un servei"):
        serveis.crea(magatzem, "  oficines ")


def test_no_s_esborra_un_servei_amb_gent(magatzem, serveis_ids):
    with pytest.raises(ErrorHorari, match="treballadors assignats"):
        serveis.elimina(magatzem, serveis_ids["Oficines"], treballadors_assignats=3)


# -- horaris ----------------------------------------------------------------
def test_patro_amb_hora_de_fi_anterior(magatzem):
    with pytest.raises(ErrorHorari, match="posterior"):
        horaris.desa_patro(magatzem, "Dolent", "", [Tram(1, time(15, 0), time(8, 0))])


def test_patro_amb_trams_solapats(magatzem):
    with pytest.raises(ErrorHorari, match="trepitgen"):
        horaris.desa_patro(magatzem, "Dolent", "", [
            Tram(1, time(8, 0), time(14, 0)), Tram(1, time(13, 0), time(17, 0))])


def test_patro_sense_nom(magatzem):
    with pytest.raises(ErrorHorari, match="nom"):
        horaris.desa_patro(magatzem, "  ", "", [])


def test_desar_i_llegir_un_patro(magatzem):
    id = horaris.desa_patro(magatzem, "Brigada", "estiu",
                            [Tram(1, time(7, 0), time(14, 0))])
    patro = horaris.patro(magatzem, id)
    assert patro.nom == "Brigada" and patro.trams[0].minuts == 420


# -- festius ----------------------------------------------------------------
def test_festius_de_l_any_en_una_lectura(magatzem):
    dels_any = festius.del_any(magatzem, date.today().year)
    assert len(dels_any) == 2


def test_afegir_i_treure_un_festiu(magatzem):
    festius.afegeix(magatzem, date(2026, 8, 15), "Assumpció", "general")
    assert date(2026, 8, 15) in festius.del_any(magatzem, 2026)
    festius.elimina(magatzem, date(2026, 8, 15))
    assert date(2026, 8, 15) not in festius.del_any(magatzem, 2026)


def test_fusionar_no_pisa_els_que_ja_hi_son(magatzem):
    """Els festius propis de l'ajuntament han de guanyar sobre una importació."""
    festius.afegeix(magatzem, date(2026, 8, 15), "Festa nostra", "propi")
    nous, repetits = festius.fusiona(magatzem, [
        (date(2026, 8, 15), "Assumpció", "general"),
        (date(2026, 12, 25), "Nadal", "general")])
    assert (nous, repetits) == (1, 1)
    assert festius.del_any(magatzem, 2026)[date(2026, 8, 15)] == "Festa nostra"


def test_festius_entre_dues_dates_de_dos_anys(magatzem):
    festius.afegeix(magatzem, date(2026, 12, 25), "Nadal")
    festius.afegeix(magatzem, date(2027, 1, 1), "Cap d'Any")
    trobats = festius.entre(magatzem, date(2026, 12, 1), date(2027, 1, 31))
    assert len(trobats) == 2


# -- marcatges --------------------------------------------------------------
def afegeix_marcatge(magatzem, tipus, hores, login="treb01", **extra):
    from datetime import datetime, timezone
    moment = datetime(2026, 8, 3, hores, 0, tzinfo=timezone.utc)
    return marcatges.afegeix(magatzem, login, tipus, moment, "web", login, **extra)


def test_afegir_i_llegir_marcatges_del_dia(magatzem):
    afegeix_marcatge(magatzem, ENTRADA, 6)
    afegeix_marcatge(magatzem, SORTIDA, 13)
    del_dia = marcatges.del_dia(magatzem, "treb01", DIA)
    assert [m.tipus for m in del_dia] == [ENTRADA, SORTIDA]
    assert del_dia[0].moment.tzinfo is not None      # sempre amb zona


def test_un_tipus_de_marcatge_inventat(magatzem):
    with pytest.raises(ErrorHorari):
        afegeix_marcatge(magatzem, "esmorzar", 10)


def test_la_correccio_anula_l_original_en_el_mateix_lot(magatzem):
    original = afegeix_marcatge(magatzem, SORTIDA, 13)
    afegeix_marcatge(magatzem, SORTIDA, 15, anul_la_id=original,
                     estat=PENDENT_VALIDACIO)
    assert magatzem.doc("marcatges", original)["anulat"] is True
    # El repositori retorna el LLIBRE sencer (l'anul·lat també hi ha de ser:
    # és la traça de l'auditoria). Qui filtra és el domini, amb `.compta`.
    del_dia = marcatges.del_dia(magatzem, "treb01", DIA)
    assert len(del_dia) == 2
    assert [m for m in del_dia if m.compta] == []


def test_no_es_corregeix_un_marcatge_d_un_altre(magatzem):
    original = afegeix_marcatge(magatzem, SORTIDA, 13, login="treb02")
    with pytest.raises(ErrorHorari, match="d'aquest treballador"):
        afegeix_marcatge(magatzem, SORTIDA, 15, anul_la_id=original)


def test_no_es_corregeix_dues_vegades_el_mateix(magatzem):
    original = afegeix_marcatge(magatzem, SORTIDA, 13)
    afegeix_marcatge(magatzem, SORTIDA, 15, anul_la_id=original)
    with pytest.raises(ErrorHorari, match="ja estava corregit"):
        afegeix_marcatge(magatzem, SORTIDA, 16, anul_la_id=original)


def test_rebutjar_una_correccio_restaura_l_original(magatzem):
    """Sense això, el dia es quedaria sense cap marcatge vàlid i
    desapareixerien hores d'una persona."""
    original = afegeix_marcatge(magatzem, SORTIDA, 13)
    correccio = afegeix_marcatge(magatzem, SORTIDA, 15, anul_la_id=original,
                                 estat=PENDENT_VALIDACIO)
    marcatges.valida(magatzem, correccio, "resp01", accepta=False)
    assert magatzem.doc("marcatges", original)["anulat"] is False
    assert magatzem.doc("marcatges", correccio)["estat"] == REBUTJAT


def test_acceptar_una_correccio(magatzem):
    original = afegeix_marcatge(magatzem, SORTIDA, 13)
    correccio = afegeix_marcatge(magatzem, SORTIDA, 15, anul_la_id=original,
                                 estat=PENDENT_VALIDACIO)
    marcatges.valida(magatzem, correccio, "resp01", accepta=True)
    assert magatzem.doc("marcatges", correccio)["estat"] == VALID
    assert magatzem.doc("marcatges", original)["anulat"] is True


def test_no_es_valida_un_marcatge_que_no_esta_pendent(magatzem):
    id = afegeix_marcatge(magatzem, ENTRADA, 6)
    with pytest.raises(ErrorHorari, match="pendent"):
        marcatges.valida(magatzem, id, "resp01", accepta=True)


def test_pendents_de_validacio_per_servei(magatzem, serveis_ids):
    afegeix_marcatge(magatzem, ENTRADA, 6, servei_id=serveis_ids["Oficines"],
                     estat=PENDENT_VALIDACIO)
    afegeix_marcatge(magatzem, ENTRADA, 7, login="treb02",
                     servei_id=serveis_ids["Brigada"], estat=PENDENT_VALIDACIO)
    assert len(marcatges.pendents_validacio(magatzem, [serveis_ids["Oficines"]])) == 1
    assert len(marcatges.pendents_validacio(magatzem, [AMBIT_TOTS])) == 2


def test_marcatges_d_un_periode_per_servei(magatzem, serveis_ids):
    afegeix_marcatge(magatzem, ENTRADA, 6, servei_id=serveis_ids["Oficines"])
    afegeix_marcatge(magatzem, ENTRADA, 6, login="treb02",
                     servei_id=serveis_ids["Brigada"])
    per_treballador = marcatges.del_periode_serveis(
        magatzem, [serveis_ids["Oficines"]], DIA, DIA)
    assert list(per_treballador) == ["treb01"]


def test_purga_de_marcatges_antics(magatzem):
    afegeix_marcatge(magatzem, ENTRADA, 6)
    assert marcatges.purga(magatzem, date(2026, 8, 4)) == 1
    assert marcatges.del_dia(magatzem, "treb01", DIA) == []


# -- absències --------------------------------------------------------------
def test_els_codis_son_seqüencials_i_atomics(magatzem, serveis_ids):
    codis = [absencies.crea(magatzem, "treb01", serveis_ids["Oficines"],
                            "vacances", date(2026, 8, i), date(2026, 8, i), 1)
             for i in range(3, 6)]
    assert codis == ["A-2026-0001", "A-2026-0002", "A-2026-0003"]


def test_els_codis_es_reinicien_cada_any(magatzem, serveis_ids):
    absencies.crea(magatzem, "treb01", serveis_ids["Oficines"], "vacances",
                   date(2026, 8, 3), date(2026, 8, 3), 1)
    codi = absencies.crea(magatzem, "treb01", serveis_ids["Oficines"], "vacances",
                          date(2027, 8, 3), date(2027, 8, 3), 1)
    assert codi == "A-2027-0001"


def test_solapaments_propis(magatzem, serveis_ids):
    absencies.crea(magatzem, "treb01", serveis_ids["Oficines"], "vacances",
                   date(2026, 8, 3), date(2026, 8, 14), 10)
    trobats = absencies.solapaments(magatzem, "treb01", date(2026, 8, 10),
                                    date(2026, 8, 20))
    assert len(trobats) == 1


def test_solapaments_del_servei_exclouen_el_solicitant(magatzem, serveis_ids):
    """L'avís que evita quedar-se sense ningú a la brigada l'agost."""
    oficines = serveis_ids["Oficines"]
    absencies.crea(magatzem, "treb01", oficines, "vacances",
                   date(2026, 8, 3), date(2026, 8, 14), 10)
    absencies.crea(magatzem, "resp01", oficines, "vacances",
                   date(2026, 8, 10), date(2026, 8, 20), 9)
    altres = absencies.solapaments_servei(magatzem, oficines, date(2026, 8, 3),
                                          date(2026, 8, 14),
                                          excloent_treballador="treb01")
    assert [a.treballador_id for a in altres] == ["resp01"]


def test_resoldre_i_no_poder_resoldre_dues_vegades(magatzem, serveis_ids):
    codi = absencies.crea(magatzem, "treb01", serveis_ids["Oficines"], "vacances",
                          date(2026, 8, 3), date(2026, 8, 7), 5)
    absencies.resol(magatzem, codi, APROVADA, "resp01", "endavant")
    assert absencies.per_codi(magatzem, codi).estat == APROVADA
    with pytest.raises(ErrorHorari, match="ja estava resolta"):
        absencies.resol(magatzem, codi, DENEGADA, "resp01", "")


def test_anular_no_toca_cap_saldo(magatzem, serveis_ids):
    """Els dies tornen sols al disponible perquè el càlcul és dinàmic."""
    codi = absencies.crea(magatzem, "treb01", serveis_ids["Oficines"], "vacances",
                          date(2026, 8, 3), date(2026, 8, 7), 5)
    absencies.resol(magatzem, codi, APROVADA, "resp01", "")
    absencies.anula(magatzem, codi, "resp01")
    aprovades = [a for a in absencies.de_treballador(magatzem, "treb01")
                 if a.estat == APROVADA]
    assert aprovades == []
    assert absencies.saldo_assignat(magatzem, "treb01", date.today().year,
                                    "vacances") == 22


def test_pendents_del_meu_ambit(magatzem, serveis_ids):
    absencies.crea(magatzem, "treb01", serveis_ids["Oficines"], "vacances",
                   date(2026, 8, 3), date(2026, 8, 7), 5)
    absencies.crea(magatzem, "treb02", serveis_ids["Brigada"], "vacances",
                   date(2026, 8, 3), date(2026, 8, 7), 5)
    assert len(absencies.pendents(magatzem, [serveis_ids["Oficines"]])) == 1
    assert len(absencies.pendents(magatzem, [AMBIT_TOTS])) == 2


def test_saldos(magatzem):
    any = date.today().year
    assert absencies.saldo_assignat(magatzem, "treb01", any, "vacances") == 22
    absencies.desa_saldo(magatzem, "treb01", any, "vacances", 26)
    assert absencies.saldo_assignat(magatzem, "treb01", any, "vacances") == 26
    assert absencies.saldo_assignat(magatzem, "treb01", 2099, "vacances") is None


@pytest.fixture
def serveis_ids(magatzem):
    return {s["nom"]: s["id"] for s in magatzem.consulta("serveis")}
