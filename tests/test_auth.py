"""Proves de l'autenticació: entrada, confinaments, segon factor i recuperació."""
from __future__ import annotations

import pyotp
import pytest

from core import comptes as regles_comptes
from core.model import ErrorHorari
from magatzem import comptes
from tests.conftest import CONTRASENYA_PROVA, SECRET_TOTP


def text(resposta):
    return resposta.get_data(as_text=True)


# -- entrada ----------------------------------------------------------------
def test_entrada_correcta(client, entra):
    assert "Fitxar" in text(entra("treb01"))


def test_contrasenya_incorrecta(client):
    resposta = client.post("/login", data={"usuari": "treb01",
                                           "contrasenya": "no-és-aquesta"})
    assert resposta.status_code == 401
    assert "no són correctes" in text(resposta)


def test_el_missatge_no_revela_si_el_compte_existeix(client):
    """Si el missatge fos diferent, la pàgina et diria qui té compte a
    l'ajuntament."""
    dolenta = client.post("/login", data={"usuari": "treb01",
                                          "contrasenya": "malament"})
    inexistent = client.post("/login", data={"usuari": "no-existeix",
                                             "contrasenya": "malament"})
    assert "no són correctes" in text(dolenta)
    assert "no són correctes" in text(inexistent)
    assert dolenta.status_code == inexistent.status_code


def test_un_compte_desactivat_no_pot_entrar(client, magatzem):
    comptes.actualitza(magatzem, "treb01", actiu=False)
    resposta = client.post("/login", data={"usuari": "treb01",
                                           "contrasenya": CONTRASENYA_PROVA})
    assert resposta.status_code == 401


def test_bloqueig_per_massa_intents(client):
    for _ in range(9):
        resposta = client.post("/login", data={"usuari": "treb01",
                                               "contrasenya": "malament"})
    assert resposta.status_code == 429
    assert "massa intents" in text(resposta)


@pytest.mark.parametrize("desti", ["//evil.example", "http://evil.example",
                                   "https://evil.example/x"])
def test_next_maliciós_es_rebutja(client, desti):
    """Open redirect clàssic: el `next` només pot ser una ruta interna."""
    resposta = client.post("/login", data={"usuari": "treb01",
                                           "contrasenya": CONTRASENYA_PROVA,
                                           "next": desti})
    assert "evil.example" not in resposta.headers.get("Location", "")


def test_next_intern_si_que_val(client):
    resposta = client.post("/login", data={"usuari": "treb01",
                                           "contrasenya": CONTRASENYA_PROVA,
                                           "next": "/hores"})
    assert resposta.headers["Location"].endswith("/hores")


def test_sortir(client, entra):
    entra("treb01")
    assert "Has sortit" in text(client.get("/logout", follow_redirects=True))
    assert client.get("/hores").status_code == 302


# -- confinaments -----------------------------------------------------------
def test_amb_contrasenya_provisional_no_es_pot_anar_enlloc(client, magatzem):
    comptes.actualitza(magatzem, "treb01", canvi_pendent=True)
    client.post("/login", data={"usuari": "treb01",
                                "contrasenya": CONTRASENYA_PROVA})
    resposta = client.get("/hores", follow_redirects=True)
    assert "Canvia la contrasenya" in text(resposta)


def test_un_responsable_sense_segon_factor_queda_confinat(client, magatzem):
    comptes.actualitza(magatzem, "resp01", totp_actiu=False, totp_secret=None)
    client.post("/login", data={"usuari": "resp01",
                                "contrasenya": CONTRASENYA_PROVA})
    resposta = client.get("/gestio", follow_redirects=True)
    assert "Activa la verificació en dos passos" in text(resposta)


def test_un_treballador_ras_no_esta_obligat_al_segon_factor(client, entra):
    assert "Fitxar" in text(entra("treb01"))


# -- segon factor -----------------------------------------------------------
def test_la_contrasenya_sola_no_obre_la_sessio(client):
    """L'error que buidaria de sentit tot el 2FA: entrar abans del codi."""
    client.post("/login", data={"usuari": "resp01",
                                "contrasenya": CONTRASENYA_PROVA})
    assert client.get("/gestio").status_code == 302      # encara no hi és


def test_entrada_amb_segon_factor(client, entra):
    assert "Gestió" in text(entra("resp01"))


def test_codi_incorrecte(client):
    client.post("/login", data={"usuari": "resp01",
                                "contrasenya": CONTRASENYA_PROVA})
    resposta = client.post("/login/totp", data={"codi": "000000"})
    assert resposta.status_code == 401
    assert "no és correcte" in text(resposta)


def test_el_segon_factor_caduca(client, monkeypatch):
    import web.auth as modul
    client.post("/login", data={"usuari": "resp01",
                                "contrasenya": CONTRASENYA_PROVA})
    monkeypatch.setattr(modul, "MINUTS_SEGON_FACTOR", -1)
    resposta = client.post("/login/totp",
                           data={"codi": pyotp.TOTP(SECRET_TOTP).now()},
                           follow_redirects=True)
    assert "Has trigat massa" in text(resposta)


def test_un_codi_de_recuperacio_serveix_una_sola_vegada(client, magatzem):
    from core import totp as regles_totp
    codis = regles_totp.genera_codis_recuperacio(2)
    comptes.desa_codis_recuperacio(magatzem, "resp01", regles_totp.a_desar(codis))

    client.post("/login", data={"usuari": "resp01",
                                "contrasenya": CONTRASENYA_PROVA})
    primera = client.post("/login/totp", data={"codi": codis[0]},
                          follow_redirects=True)
    assert "Gestió" in text(primera)

    client.get("/logout")
    client.post("/login", data={"usuari": "resp01",
                                "contrasenya": CONTRASENYA_PROVA})
    segona = client.post("/login/totp", data={"codi": codis[0]})
    assert segona.status_code == 401       # ja s'havia fet servir


def test_activacio_del_segon_factor(client, magatzem, entra):
    entra("treb01")
    pagina = client.get("/totp")
    assert "Activa la verificació" in text(pagina)
    assert "<svg" in text(pagina)          # el QR es genera al servidor

    with client.session_transaction() as sessio:
        secret = sessio["totp_provisional"]
    resposta = client.post("/totp/confirma",
                           data={"codi": pyotp.TOTP(secret).now()})
    assert "Guarda aquests codis" in text(resposta)
    assert (magatzem.doc("treballadors", "treb01") or {})["totp_actiu"] is True


def test_un_responsable_no_pot_desactivar_el_segon_factor(client, entra):
    entra("resp01")
    resposta = client.post("/totp/desactiva", follow_redirects=True)
    assert "no pot desactivar" in text(resposta)


# -- recuperació ------------------------------------------------------------
def test_la_recuperacio_no_revela_si_el_correu_existeix(client):
    import re

    def sense_csrf(resposta):
        """El testimoni CSRF porta una marca de temps a dins, o sigui que
        canvia entre dues peticions de segons diferents. No diu res de si el
        compte existeix: es normalitza per no comparar soroll."""
        return re.sub(r'name="csrf_token" value="[^"]+"', "CSRF",
                      text(resposta))

    coneguda = client.post("/recupera", data={"correu": "treb01@exemple.cat"},
                           follow_redirects=True)
    desconeguda = client.post("/recupera", data={"correu": "ningu@exemple.cat"},
                              follow_redirects=True)
    assert "Si aquest correu té compte" in text(coneguda)
    assert coneguda.status_code == desconeguda.status_code
    assert sense_csrf(coneguda) == sense_csrf(desconeguda)


def test_recuperacio_amb_token_bo(client, app, magatzem):
    token = regles_comptes.token_recuperacio("treb01", app.config["SECRET_KEY"])
    resposta = client.post(f"/recupera/{token}",
                           data={"nova": "unaCosaLlarga1", "repeticio": "unaCosaLlarga1"},
                           follow_redirects=True)
    assert "Ja pots entrar-hi" in text(resposta)
    assert regles_comptes.verifica(comptes.hash_de(magatzem, "treb01"),
                                   "unaCosaLlarga1")


def test_recuperacio_amb_token_manipulat(client):
    resposta = client.get("/recupera/aixo-no-es-un-token", follow_redirects=True)
    assert "ha caducat o no és vàlid" in text(resposta)


def test_recuperacio_amb_contrasenyes_diferents(client, app):
    token = regles_comptes.token_recuperacio("treb01", app.config["SECRET_KEY"])
    resposta = client.post(f"/recupera/{token}",
                           data={"nova": "unaCosaLlarga1", "repeticio": "altra"})
    assert "no coincideixen" in text(resposta)


# -- canvi de contrasenya ---------------------------------------------------
def test_canvi_de_contrasenya(client, entra, magatzem):
    entra("treb01")
    resposta = client.post("/canvia-contrasenya",
                           data={"actual": CONTRASENYA_PROVA,
                                 "nova": "unaAltraDeLlarga1",
                                 "repeticio": "unaAltraDeLlarga1"},
                           follow_redirects=True)
    assert "Contrasenya canviada" in text(resposta)


def test_no_es_canvia_sense_saber_l_actual(client, entra):
    entra("treb01")
    resposta = client.post("/canvia-contrasenya",
                           data={"actual": "malament", "nova": "unaCosaLlarga1",
                                 "repeticio": "unaCosaLlarga1"})
    assert "actual no és correcta" in text(resposta)


def test_la_contrasenya_nova_no_pot_ser_la_provisional(client, entra):
    entra("treb01")
    resposta = client.post("/canvia-contrasenya",
                           data={"actual": CONTRASENYA_PROVA,
                                 "nova": CONTRASENYA_PROVA,
                                 "repeticio": CONTRASENYA_PROVA})
    assert "diferent de la provisional" in text(resposta)


def test_politica_de_llargada_minima():
    with pytest.raises(ErrorHorari, match="10"):
        regles_comptes.valida_politica("curta")


def test_la_contrasenya_provisional_no_te_caracters_confusos():
    """Es tecleja a mà des d'un paper o d'un correu."""
    for _ in range(20):
        assert not set(regles_comptes.contrasenya_provisional()) & set("O0lI1")
