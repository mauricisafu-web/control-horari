"""Proves de core/importa.py — anàlisi del CSV de treballadors i càlcul del pla.

Totes les dades són inventades: comptes `prova…` i correus `@exemple.cat`.
No hi entra mai una persona de veritat de l'ajuntament.
"""
from __future__ import annotations

from datetime import date

from core import importa
from core.format_importacio import (
    ACTUALITZAR, BAIXA, CREAR, ERROR, SENSE_CANVIS,
)
from core.model import ROL_ADMIN, ROL_RESPONSABLE, ROL_TREBALLADOR, Treballador

# {nom del servei: identificador}, tal com ho dona el magatzem.
SERVEIS = {"Oficines": "s1", "Brigada": "s2", "Serveis Socials": "s3"}

CAPCALERA = "usuari;nom;correu;servei;rol;data_alta;contrasenya"


def csv_de(*files: str, capcalera: str = CAPCALERA) -> str:
    """Munta el text d'un CSV a partir de la capçalera i unes quantes files."""
    return "\n".join((capcalera,) + files) + "\n"


def treballador(login="prova01", nom="Persona Una", correu=None,
                rol=ROL_TREBALLADOR, servei_id="s1", servei="Oficines",
                data_alta=date(2020, 1, 1), actiu=True) -> Treballador:
    return Treballador(id=login, login=login, nom=nom,
                       correu=correu or f"{login}@exemple.cat", rol=rol,
                       servei_id=servei_id, servei=servei,
                       data_alta=data_alta, actiu=actiu)


def accions(pla) -> list[str]:
    return [p.accio for p in pla.propostes]


def per_login(pla, login: str):
    return next(p for p in pla.propostes if p.login == login)


# -- normalitza_nom_servei --------------------------------------------------
def test_normalitza_treu_espais_i_majuscules():
    assert importa.normalitza_nom_servei("  Oficines ") == "oficines"
    assert importa.normalitza_nom_servei("oficines") == "oficines"


def test_normalitza_treu_accents():
    assert (importa.normalitza_nom_servei("Atenció Ciutadana")
            == importa.normalitza_nom_servei("atencio ciutadana"))


def test_normalitza_espais_interiors_repetits():
    assert importa.normalitza_nom_servei("Serveis   Socials") == "serveis socials"


def test_normalitza_text_buit():
    assert importa.normalitza_nom_servei("") == ""


# -- analitza: capçalera ----------------------------------------------------
def test_capcalera_correcta_llegeix_totes_les_files():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2024-03-01;Tmp-1234",
        "prova02;Persona Dos;prova02@exemple.cat;Brigada;responsable;2024-04-01;",
    ))
    assert errors == []
    assert [f.usuari for f in files] == ["prova01", "prova02"]
    assert files[0].data_alta == date(2024, 3, 1)
    assert files[0].contrasenya == "Tmp-1234"
    assert files[1].contrasenya is None
    assert files[1].rol == ROL_RESPONSABLE


def test_capcalera_nomes_amb_les_obligatories():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat",
        capcalera="usuari;nom;correu"))
    assert errors == []
    assert files[0].servei is None
    assert files[0].rol == ROL_TREBALLADOR
    assert files[0].data_alta is None


def test_falta_una_columna_obligatoria_es_fatal():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;Oficines", capcalera="usuari;nom;servei"))
    assert files == []
    assert len(errors) == 1
    assert errors[0].accio == ERROR
    assert "correu" in errors[0].detall


def test_falten_dues_columnes_obligatories_es_diuen_totes():
    _, errors = importa.analitza(csv_de("Persona Una", capcalera="nom"))
    assert len(errors) == 1
    assert "usuari" in errors[0].detall and "correu" in errors[0].detall


def test_capcalera_amb_espais_i_majuscules_es_accepta():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat",
        capcalera=" Usuari ;NOM;Correu"))
    assert errors == []
    assert files[0].usuari == "prova01"


def test_fitxer_buit():
    files, errors = importa.analitza("")
    assert files == []
    assert len(errors) == 1 and errors[0].accio == ERROR


def test_fitxer_nomes_amb_capcalera():
    files, errors = importa.analitza(CAPCALERA + "\n")
    assert files == [] and errors == []


# -- analitza: errors de fila -----------------------------------------------
def test_fila_sense_correu():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;;Oficines;treballador;;",
        "prova02;Persona Dos;prova02@exemple.cat;Brigada;treballador;;",
    ))
    # Una fila dolenta no atura la resta.
    assert [f.usuari for f in files] == ["prova02"]
    assert len(errors) == 1
    assert "correu" in errors[0].detall
    assert errors[0].login == "prova01"


def test_fila_sense_usuari_i_sense_nom():
    _, errors = importa.analitza(csv_de(";;prova01@exemple.cat;;;;"))
    assert len(errors) == 1
    assert "usuari" in errors[0].detall and "nom" in errors[0].detall


def test_correu_duplicat_dins_del_fitxer():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;repetit@exemple.cat;;;;",
        "prova02;Persona Dos;repetit@exemple.cat;;;;",
    ))
    # La primera aparició val; la segona és l'error.
    assert [f.usuari for f in files] == ["prova01"]
    assert len(errors) == 1
    assert errors[0].login == "prova02"
    assert "repetit@exemple.cat" in errors[0].detall


def test_correu_duplicat_encara_que_canvii_la_caixa():
    _, errors = importa.analitza(csv_de(
        "prova01;Persona Una;Repetit@Exemple.cat;;;;",
        "prova02;Persona Dos;repetit@exemple.cat;;;;",
    ))
    assert len(errors) == 1


def test_usuari_duplicat_dins_del_fitxer():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;;;",
        "PROVA01;Persona Dos;prova02@exemple.cat;;;;",
    ))
    assert [f.usuari for f in files] == ["prova01"]
    assert len(errors) == 1
    assert "usuari" in errors[0].detall


def test_rol_inventat():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;secretari;;"))
    assert files == []
    assert "secretari" in errors[0].detall


def test_data_mal_formada():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;;01/03/2024;"))
    assert files == []
    assert "AAAA-MM-DD" in errors[0].detall


def test_data_inexistent_al_calendari():
    _, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;;2024-02-31;"))
    assert len(errors) == 1


def test_data_sense_guions_no_val():
    # `date.fromisoformat` l'acceptaria; el format del fitxer, no.
    _, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;;20240301;"))
    assert len(errors) == 1


def test_usuari_es_normalitza_a_minuscules_i_sense_espais():
    files, _ = importa.analitza(csv_de(
        " PROVA 01 ;Persona Una;prova01@exemple.cat;;;;"))
    assert files[0].usuari == "prova01"


def test_fila_totalment_buida_no_es_un_error():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;;;",
        ";;;;;;",
    ))
    assert len(files) == 1 and errors == []


def test_els_numeros_de_linia_son_els_reals():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;;;",       # línia 2
        "prova02;Persona Dos;prova02@exemple.cat;;;;",       # línia 3
        "prova03;Persona Tres;;;;;",                          # línia 4: dolenta
        "prova04;Persona Quatre;prova04@exemple.cat;;;;",    # línia 5
    ))
    assert [f.linia for f in files] == [2, 3, 5]
    assert errors[0].fila.linia == 4
    assert "Línia 4" in errors[0].detall


def test_la_linia_es_manté_amb_un_camp_entre_cometes_i_salts():
    files, _ = importa.analitza(csv_de(
        '"prova01";"Persona\nUna";prova01@exemple.cat;;;;',   # línies 2 i 3
        "prova02;Persona Dos;prova02@exemple.cat;;;;",        # línia 4
    ))
    assert files[1].linia == 4


# -- calcula_pla: creació ---------------------------------------------------
def test_compte_nou_es_crea():
    files, errors = importa.analitza(csv_de(
        "prova09;Persona Nova;prova09@exemple.cat;Brigada;treballador;2026-01-07;Tmp-1234"))
    pla = importa.calcula_pla(files, [], SERVEIS, errors)
    assert accions(pla) == [CREAR]
    proposta = pla.crear[0]
    assert proposta.servei_id == "s2"
    assert "Persona Nova" in proposta.detall
    assert pla.hi_ha_res_a_fer


def test_creacio_sense_servei():
    files, _ = importa.analitza(csv_de(
        "prova09;Persona Nova;prova09@exemple.cat;;;;", ))
    pla = importa.calcula_pla(files, [], SERVEIS)
    assert pla.crear[0].servei_id is None
    assert "sense servei" in pla.crear[0].detall


def test_el_nom_del_servei_es_compara_normalitzat():
    files, _ = importa.analitza(csv_de(
        "prova09;Persona Nova;prova09@exemple.cat;  serveis   socials ;;;"))
    pla = importa.calcula_pla(files, [], SERVEIS)
    assert pla.crear[0].servei_id == "s3"


# -- calcula_pla: servei inexistent -----------------------------------------
def test_servei_inexistent_es_error_de_la_fila():
    files, _ = importa.analitza(csv_de(
        "prova09;Persona Nova;prova09@exemple.cat;Piscina;;;",
        "prova10;Persona Deu;prova10@exemple.cat;Oficines;;;",
    ))
    pla = importa.calcula_pla(files, [], SERVEIS)
    assert accions(pla) == [ERROR, CREAR]
    assert "Piscina" in pla.errors[0].detall
    # Mai es proposa crear el servei que falta.
    assert "crear" not in pla.errors[0].detall.lower().split("«")[0]


def test_servei_inexistent_no_provoca_una_baixa():
    # La persona SÍ que surt al fitxer, encara que la fila tingui un error.
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Piscina;;;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert pla.baixes == ()


def test_una_fila_rebutjada_per_analitza_tampoc_provoca_una_baixa():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;;Oficines;;;"))     # sense correu
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS, errors)
    assert pla.baixes == ()
    assert len(pla.errors) == 1


# -- calcula_pla: actualitzacions -------------------------------------------
def test_actualitza_el_nom():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una Cognom;prova01@exemple.cat;Oficines;treballador;2020-01-01;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert accions(pla) == [ACTUALITZAR]
    assert "nom: Persona Una -> Persona Una Cognom" in pla.actualitzar[0].detall


def test_actualitza_el_servei():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Brigada;treballador;2020-01-01;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert "servei: Oficines -> Brigada" in pla.actualitzar[0].detall
    assert pla.actualitzar[0].servei_id == "s2"


def test_actualitza_el_rol():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;responsable;2020-01-01;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert "rol: Treballador -> Responsable" in pla.actualitzar[0].detall


def test_actualitza_la_data_dalta():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2026-02-01;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert "data d'alta: 01/01/2020 -> 01/02/2026" in pla.actualitzar[0].detall


def test_un_servei_buit_no_esborra_el_que_ja_hi_ha():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;;treballador;2020-01-01;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert accions(pla) == [SENSE_CANVIS]
    assert pla.sense_canvis[0].servei_id == "s1"


def test_una_data_dalta_buida_no_esborra_la_que_hi_ha():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert accions(pla) == [SENSE_CANVIS]


def test_sense_columna_rol_el_defecte_es_treballador():
    # Conseqüència del format: si el fitxer no porta la columna `rol`, el
    # valor per defecte proposa baixar el rol de qui en tenia un de superior.
    # Es veu a la previsualització i l'administrador ho pot no confirmar.
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat", capcalera="usuari;nom;correu"))
    pla = importa.calcula_pla(files, [treballador("prova01", rol=ROL_ADMIN)],
                              SERVEIS)
    assert accions(pla) == [ACTUALITZAR]
    assert "rol: Administrador -> Treballador" in pla.actualitzar[0].detall


# -- calcula_pla: sense canvis i idempotència -------------------------------
def test_sense_canvis_quan_tot_coincideix():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2020-01-01;"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS)
    assert accions(pla) == [SENSE_CANVIS]
    assert not pla.hi_ha_res_a_fer


def test_carregar_dues_vegades_el_mateix_fitxer_no_proposa_res():
    contingut = csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2020-01-01;Tmp-1234")
    existents = [treballador("prova01")]
    for _ in range(2):
        files, errors = importa.analitza(contingut)
        pla = importa.calcula_pla(files, existents, SERVEIS, errors)
        assert not pla.hi_ha_res_a_fer


# -- calcula_pla: baixes i reactivacions ------------------------------------
def test_qui_no_surt_al_fitxer_es_proposa_de_baixa():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2020-01-01;"))
    pla = importa.calcula_pla(
        files, [treballador("prova01"), treballador("prova02", nom="Persona Dos")],
        SERVEIS)
    assert [p.login for p in pla.baixes] == ["prova02"]
    # La baixa és una proposta: no hi ha res a aplicar automàticament.
    assert not pla.hi_ha_res_a_fer


def test_qui_ja_estava_de_baixa_no_es_torna_a_proposar():
    pla = importa.calcula_pla([], [treballador("prova02", actiu=False)], SERVEIS)
    assert pla.baixes == ()


def test_un_compte_de_baixa_que_torna_al_fitxer_es_reactiva():
    files, _ = importa.analitza(csv_de(
        "prova02;Persona Dos;prova02@exemple.cat;Oficines;treballador;2020-01-01;"))
    pla = importa.calcula_pla(
        files, [treballador("prova02", nom="Persona Dos", actiu=False)], SERVEIS)
    assert accions(pla) == [ACTUALITZAR]
    assert "reactiv" in pla.actualitzar[0].detall


def test_els_errors_de_capcalera_entren_al_pla():
    files, errors = importa.analitza(csv_de("Persona Una", capcalera="nom"))
    pla = importa.calcula_pla(files, [treballador("prova01")], SERVEIS, errors)
    assert len(pla.errors) == 1
    # Un fitxer il·legible no pot proposar la baixa de tothom.
    assert pla.baixes == ()


def test_pla_complet_amb_les_cinc_situacions():
    files, errors = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2020-01-01;",
        "prova02;Persona Dos Nova;prova02@exemple.cat;Brigada;treballador;2020-01-01;",
        "prova09;Persona Nova;prova09@exemple.cat;Oficines;treballador;2026-01-07;Tmp-1234",
        "prova10;Persona Deu;prova10@exemple.cat;Piscina;;;",
    ))
    existents = [treballador("prova01"),
                 treballador("prova02", nom="Persona Dos", servei_id="s1"),
                 treballador("prova03", nom="Persona Tres")]
    pla = importa.calcula_pla(files, existents, SERVEIS, errors)
    assert [p.login for p in pla.sense_canvis] == ["prova01"]
    assert [p.login for p in pla.actualitzar] == ["prova02"]
    assert [p.login for p in pla.crear] == ["prova09"]
    assert [p.login for p in pla.errors] == ["prova10"]
    assert [p.login for p in pla.baixes] == ["prova03"]
    assert pla.hi_ha_res_a_fer


# -- puresa -----------------------------------------------------------------
def test_el_bom_de_lexcel_no_embruta_la_primera_columna():
    # Si qui llegeix el fitxer no fa servir `utf-8-sig`, el BOM arriba aquí.
    files, errors = importa.analitza(
        "﻿" + csv_de("prova01;Persona Una;prova01@exemple.cat"))
    assert errors == []
    assert files[0].usuari == "prova01"


def test_calcula_pla_no_modifica_el_que_rep():
    files, _ = importa.analitza(csv_de(
        "prova01;Persona Una;prova01@exemple.cat;Oficines;treballador;2020-01-01;"))
    existents = [treballador("prova01")]
    copia_serveis = dict(SERVEIS)
    importa.calcula_pla(files, existents, SERVEIS)
    assert SERVEIS == copia_serveis
    assert len(files) == 1 and len(existents) == 1
