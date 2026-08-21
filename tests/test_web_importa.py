"""
Proves de la pantalla de càrrega de treballadors.

La garantia que es prova amb més insistència és la de les BAIXES: cap compte
es desactiva si l'administrador no ha marcat la casella. Un CSV mal exportat
no pot fer fora mitja plantilla d'un clic.
"""
from __future__ import annotations

import io
from datetime import date

import pytest

from magatzem import comptes

RUTA = "/configuracio/importa"


def text(r):
    return r.get_data(as_text=True)


def csv_de(*files, capcalera="usuari;nom;correu;servei;rol;data_alta;contrasenya"):
    return "﻿" + capcalera + "\n" + "\n".join(files) + "\n"


def puja(client, contingut, nom="treballadors.csv"):
    return client.post(
        RUTA,
        data={"accio": "previsualitza",
              "fitxer": (io.BytesIO(contingut.encode("utf-8-sig")), nom)},
        content_type="multipart/form-data", follow_redirects=True)


def aplica(client, contingut, baixes=()):
    dades = {"accio": "aplica", "contingut": contingut}
    if baixes:
        dades["baixa"] = list(baixes)
    return client.post(RUTA, data=dades, follow_redirects=True)


def quants_actius(magatzem):
    return len(comptes.llista(magatzem, actius=True))


# -- permisos ---------------------------------------------------------------
def test_un_treballador_no_hi_entra(client, entra):
    entra("treb01")
    assert client.get(RUTA).status_code == 403


def test_un_responsable_tampoc(client, entra):
    entra("resp01")
    assert client.get(RUTA).status_code == 403


def test_sense_sessio_no_s_hi_arriba(client):
    assert client.get(RUTA).status_code in (301, 302, 401)


def test_un_admin_hi_entra(client, entra):
    entra("admin01")
    resposta = client.get(RUTA)
    assert resposta.status_code == 200
    assert "Puja el fitxer" in text(resposta)


# -- previsualització -------------------------------------------------------
def test_la_previsualitzacio_no_escriu_res(client, entra, magatzem, serveis):
    entra("admin01")
    abans = quants_actius(magatzem)
    resposta = puja(client, csv_de(
        f"nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;Clau-1234"))
    assert resposta.status_code == 200
    assert "Es crearan" in text(resposta)
    assert quants_actius(magatzem) == abans, "la previsualització ha escrit!"


def test_la_previsualitzacio_ensenya_les_baixes_sense_aplicar_les(
        client, entra, magatzem, serveis):
    entra("admin01")
    # Al fitxer només hi ha treb01: la resta desapareixen.
    resposta = puja(client, csv_de(
        "treb01;Treballador U;treb01@exemple.cat;Oficines;treballador;;"))
    contingut = text(resposta)
    assert "Ja no surten al fitxer" in contingut
    assert "no esborra res" in contingut
    # Cap s'ha desactivat.
    assert comptes.per_login(magatzem, "treb02").actiu is True


# -- LA garantia: cap baixa sense marcar ------------------------------------
def test_aplicar_sense_marcar_cap_baixa_no_desactiva_ningu(
        client, entra, magatzem, serveis):
    """Si això falla, un fitxer mal exportat fa fora mitja plantilla."""
    entra("admin01")
    abans = quants_actius(magatzem)
    contingut = csv_de("treb01;Treballador U;treb01@exemple.cat;Oficines;treballador;;")

    puja(client, contingut)
    aplica(client, contingut)          # sense cap `baixa` al formulari

    assert quants_actius(magatzem) == abans
    for login in ("treb02", "treb03", "resp01", "resp02", "admin01"):
        assert comptes.per_login(magatzem, login).actiu is True, login


def test_nomes_es_dona_de_baixa_qui_s_ha_marcat(client, entra, magatzem, serveis):
    entra("admin01")
    contingut = csv_de("treb01;Treballador U;treb01@exemple.cat;Oficines;treballador;;")

    puja(client, contingut)
    aplica(client, contingut, baixes=["treb02"])

    assert comptes.per_login(magatzem, "treb02").actiu is False
    assert comptes.per_login(magatzem, "treb03").actiu is True


def test_una_baixa_no_esborra_el_compte(client, entra, magatzem, serveis):
    entra("admin01")
    contingut = csv_de("treb01;Treballador U;treb01@exemple.cat;Oficines;treballador;;")
    puja(client, contingut)
    aplica(client, contingut, baixes=["treb02"])

    doc = magatzem.doc("treballadors", "treb02")
    assert doc is not None, "el compte s'ha esborrat!"
    assert doc["data_baixa"] is not None


# -- creació ----------------------------------------------------------------
def test_es_crea_un_compte_nou_amb_la_contrasenya_del_fitxer(
        client, entra, magatzem, serveis):
    from core import comptes as regles

    entra("admin01")
    contingut = csv_de(
        "nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;Clau-Prova-1")
    puja(client, contingut)
    aplica(client, contingut)

    nova = comptes.per_login(magatzem, "nova")
    assert nova is not None and nova.nom == "Persona Nova"
    # La contrasenya del fitxer s'ha xifrat, i serveix per entrar.
    assert regles.verifica(comptes.hash_de(magatzem, "nova"), "Clau-Prova-1")


def test_un_compte_nou_neix_amb_canvi_pendent(client, entra, magatzem, serveis):
    entra("admin01")
    contingut = csv_de(
        "nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;Clau-Prova-1")
    puja(client, contingut)
    aplica(client, contingut)
    assert magatzem.doc("treballadors", "nova")["canvi_pendent"] is True


def test_sense_contrasenya_al_fitxer_se_n_genera_i_es_mostra(
        client, entra, magatzem, serveis):
    entra("admin01")
    contingut = csv_de("nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;")
    puja(client, contingut)
    resposta = aplica(client, contingut)

    contingut = " ".join(text(resposta).split())   # el HTML parteix les frases
    assert "Contrasenyes generades" in contingut
    assert "no es tornaran a mostrar mai" in contingut
    assert comptes.per_login(magatzem, "nova") is not None


def test_la_contrasenya_que_venia_del_fitxer_no_es_mostra(
        client, entra, magatzem, serveis):
    """Si nòmines ja l'ha enviada per correu, aquí no s'ha de repetir."""
    entra("admin01")
    contingut = csv_de(
        "nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;Clau-Secreta-9")
    puja(client, contingut)
    resposta = aplica(client, contingut)
    assert "Clau-Secreta-9" not in text(resposta)


# -- actualització i idempotència ------------------------------------------
def test_actualitza_el_servei_d_un_existent(client, entra, magatzem, serveis):
    entra("admin01")
    contingut = csv_de(
        "treb01;Treballador U;treb01@exemple.cat;Brigada;treballador;;")
    puja(client, contingut)
    aplica(client, contingut)
    assert comptes.per_login(magatzem, "treb01").servei_id == serveis["Brigada"]


def test_carregar_dues_vegades_no_duplica(client, entra, magatzem, serveis):
    entra("admin01")
    contingut = csv_de(
        "nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;Clau-Prova-1")
    puja(client, contingut)
    aplica(client, contingut)
    primer = quants_actius(magatzem)

    puja(client, contingut)
    resposta = aplica(client, contingut)
    assert quants_actius(magatzem) == primer
    assert "Sense canvis" in text(resposta) or "0 comptes creats" in text(resposta)


# -- fitxers dolents --------------------------------------------------------
def test_una_fila_dolenta_no_atura_la_resta(client, entra, magatzem, serveis):
    entra("admin01")
    resposta = puja(client, csv_de(
        "nova;Persona Nova;nova@exemple.cat;Oficines;treballador;;Clau-1",
        ";Sense Usuari;dolenta@exemple.cat;Oficines;treballador;;Clau-2"))
    contingut = text(resposta)
    assert "Errors" in contingut
    assert "Es crearan" in contingut


def test_un_servei_inexistent_es_un_error_no_una_creacio(
        client, entra, magatzem, serveis):
    entra("admin01")
    resposta = puja(client, csv_de(
        "nova;Persona Nova;nova@exemple.cat;Inventat;treballador;;Clau-1"))
    assert "no existeix" in text(resposta)


def test_un_fitxer_buit_dona_avis_no_error(client, entra):
    entra("admin01")
    resposta = puja(client, "")
    assert resposta.status_code == 200
    assert "buit" in text(resposta)


def test_no_triar_cap_fitxer_dona_avis(client, entra):
    entra("admin01")
    resposta = client.post(RUTA, data={"accio": "previsualitza"},
                           content_type="multipart/form-data",
                           follow_redirects=True)
    assert resposta.status_code == 200
    assert "Cal triar un fitxer" in text(resposta)


def test_aplicar_sense_contingut_dona_avis(client, entra):
    entra("admin01")
    resposta = aplica(client, "")
    assert resposta.status_code == 200
    assert "perdut el contingut" in text(resposta)


def test_una_capcalera_invalida_no_proposa_cap_baixa(client, entra, magatzem):
    """La protecció que evita que un CSV il·legible faci fora tothom."""
    entra("admin01")
    resposta = puja(client, csv_de("Nom Qualsevol", capcalera="nom"))
    contingut = text(resposta)
    assert "Errors" in contingut
    assert "Ja no surten al fitxer" not in contingut
