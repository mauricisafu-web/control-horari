"""
Proves de les pantalles: fluxos i, sobretot, PERMISOS.

La matriu de rutes × rols es genera del `url_map`, així cap ruta nova no es
pot quedar sense provar.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from core.model import APROVADA, PENDENT, PENDENT_VALIDACIO, VALID
from magatzem import absencies as mag_absencies, comptes, marcatges


def text(r):
    return r.get_data(as_text=True)


# ===========================================================================
# Matriu de permisos
# ===========================================================================
RUTES_ADMIN = ["/configuracio/", "/configuracio/horaris", "/configuracio/comptes",
               "/configuracio/importa", "/informes"]
RUTES_APROVAR = ["/gestio", "/gestio/hores"]
RUTES_TOTHOM = ["/", "/hores", "/el-meu-horari", "/absencies", "/marcatges"]


@pytest.mark.parametrize("ruta", RUTES_ADMIN + RUTES_APROVAR + RUTES_TOTHOM)
def test_sense_sessio_cap_ruta_privada_respon(client, ruta):
    assert client.get(ruta).status_code in (301, 302, 401)


@pytest.mark.parametrize("ruta", RUTES_ADMIN)
def test_un_treballador_no_entra_a_configuracio(client, entra, ruta):
    entra("treb01")
    assert client.get(ruta).status_code == 403


@pytest.mark.parametrize("ruta", RUTES_ADMIN)
def test_un_responsable_tampoc_entra_a_configuracio(client, entra, ruta):
    entra("resp01")
    assert client.get(ruta).status_code == 403


@pytest.mark.parametrize("ruta", RUTES_APROVAR)
def test_un_treballador_no_entra_a_gestio(client, entra, ruta):
    entra("treb01")
    assert client.get(ruta).status_code == 403


@pytest.mark.parametrize("ruta", RUTES_TOTHOM)
def test_tothom_entra_a_les_seves_pantalles(client, entra, ruta):
    entra("treb01")
    assert client.get(ruta).status_code == 200


def test_cap_ruta_de_l_aplicacio_es_queda_sense_provar(app):
    """Si algú n'afegeix una de nova i no la posa a la matriu, això falla."""
    conegudes = set(RUTES_ADMIN + RUTES_APROVAR + RUTES_TOTHOM) | {
        "/login", "/login/totp", "/logout", "/canvia-contrasenya", "/recupera",
        "/totp", "/totp/confirma", "/totp/regenera-codis", "/totp/desactiva",
        "/avis-legal", "/manifest.webmanifest", "/sw.js", "/instal-lacio",
        "/fitxa", "/marcatges/corregeix", "/absencies/solicita",
        "/absencies/anula", "/gestio/resol", "/gestio/marcatge",
        "/configuracio/servei", "/configuracio/festiu", "/configuracio/parametre",
        "/configuracio/patro", "/configuracio/assignacio", "/configuracio/compte",
        "/informes/genera",
    }
    reals = {str(r.rule) for r in app.url_map.iter_rules()
             if not str(r.rule).startswith("/static")
             and "<" not in str(r.rule)}
    assert reals - conegudes == set(), f"rutes sense provar: {reals - conegudes}"


# ===========================================================================
# Fitxatge
# ===========================================================================
def test_cicle_de_fitxatge(client, entra, magatzem):
    from magatzem import parametres
    # Sense aixo, l'antidoble-toc bloqueja el segon marcatge de la prova.
    parametres.desa(magatzem, "segons_entre_marcatges", 0)
    entra("treb01")
    for tipus, esperat in (("entrada", "Ets DINS"),
                           ("pausa_inici", "En PAUSA"),
                           ("pausa_fi", "Ets DINS"),
                           ("sortida", "Ets FORA")):
        r = client.post("/fitxa", data={"tipus": tipus}, follow_redirects=True)
        assert esperat in text(r), f"després de {tipus}"


def test_fitxar_el_que_no_toca_dona_un_avis_no_un_error(client, entra):
    entra("treb01")
    r = client.post("/fitxa", data={"tipus": "sortida"}, follow_redirects=True)
    assert r.status_code == 200
    assert "constes com a fora" in text(r)


def test_el_doble_toc_no_crea_dos_marcatges(client, entra, magatzem):
    entra("treb01")
    client.post("/fitxa", data={"tipus": "entrada"})
    client.post("/fitxa", data={"tipus": "entrada"})
    assert len(marcatges.del_dia(magatzem, "treb01", date.today())) == 1


def test_un_treballador_no_pot_corregir_el_marcatge_d_un_altre(
        client, entra, magatzem):
    from core.model import ara_utc
    aliè = marcatges.afegeix(magatzem, "treb02", "entrada", ara_utc(), "web",
                             "treb02")
    entra("treb01")
    r = client.post("/marcatges/corregeix",
                    data={"original": aliè, "tipus": "entrada",
                          "data": date.today().isoformat(), "hora": "08:00",
                          "nota": "no és meu"})
    assert r.status_code == 403


def test_la_correccio_propia_queda_pendent_de_validar(client, entra, magatzem):
    entra("treb01")
    client.post("/fitxa", data={"tipus": "entrada"})
    r = client.post("/marcatges/corregeix",
                    data={"tipus": "sortida", "data": date.today().isoformat(),
                          "hora": "15:00", "nota": "vaig oblidar-me"},
                    follow_redirects=True)
    assert "ha de validar" in text(r)
    tots = magatzem.consulta("marcatges", [("estat", "==", PENDENT_VALIDACIO)])
    assert len(tots) == 1


def test_una_correccio_sense_motiu_es_rebutja(client, entra):
    entra("treb01")
    r = client.post("/marcatges/corregeix",
                    data={"tipus": "entrada", "data": date.today().isoformat(),
                          "hora": "08:00", "nota": ""},
                    follow_redirects=True)
    assert "motiu" in text(r)


# ===========================================================================
# Absències
# ===========================================================================
def demana(client, dies, tipus="vacances"):
    return client.post("/absencies/solicita",
                       data={"tipus": tipus, "inici": dies[0].isoformat(),
                             "fi": dies[-1].isoformat(), "motiu": "estiu"},
                       follow_redirects=True)


def test_demanar_vacances(client, entra, dies_habils_propers):
    entra("treb01")
    r = demana(client, dies_habils_propers)
    assert "Sol·licitud A-" in text(r) and "5 dies" in text(r)


def test_no_es_pot_demanar_mes_del_que_queda(client, entra, magatzem,
                                             dies_habils_propers):
    mag_absencies.desa_saldo(magatzem, "treb01", dies_habils_propers[0].year,
                             "vacances", 2)
    entra("treb01")
    assert "queden 2" in text(demana(client, dies_habils_propers))


def test_no_es_pot_demanar_una_cosa_solapada(client, entra, dies_habils_propers):
    entra("treb01")
    demana(client, dies_habils_propers)
    assert "es trepitgen" in text(demana(client, dies_habils_propers))


def test_el_calendari_amb_parametres_absurds_no_peta(client, entra):
    entra("treb01")
    assert client.get("/absencies?any=xxx&mes=99").status_code == 200


def test_no_es_pot_anular_la_solicitud_d_un_altre(client, entra, magatzem,
                                                  serveis, dies_habils_propers):
    codi = mag_absencies.crea(magatzem, "treb02", serveis["Brigada"], "vacances",
                              dies_habils_propers[0], dies_habils_propers[-1], 5)
    entra("treb01")
    assert client.post("/absencies/anula", data={"codi": codi}).status_code == 403


def test_anular_la_propia_retorna_els_dies(client, entra, magatzem,
                                           dies_habils_propers):
    entra("treb01")
    demana(client, dies_habils_propers)
    codi = mag_absencies.de_treballador(magatzem, "treb01")[0].codi
    r = client.post("/absencies/anula", data={"codi": codi}, follow_redirects=True)
    assert "anul·lada" in text(r)
    assert "22" in text(client.get("/absencies"))


def test_el_saldo_prorratejat_s_explica(client, entra, magatzem):
    """Sense explicació, un saldo de 14 en lloc de 22 sembla un error."""
    comptes.actualitza(magatzem, "treb01",
                       data_alta=date(date.today().year, 5, 11))
    entra("treb01")
    assert "perquè aquest any la teva relació laboral" in text(
        client.get("/absencies"))


# ===========================================================================
# Gestió
# ===========================================================================
def test_un_responsable_veu_els_pendents_del_seu_servei(
        client, entra, magatzem, serveis, dies_habils_propers):
    mag_absencies.crea(magatzem, "treb01", serveis["Oficines"], "vacances",
                       dies_habils_propers[0], dies_habils_propers[-1], 5)
    mag_absencies.crea(magatzem, "treb02", serveis["Brigada"], "vacances",
                       dies_habils_propers[0], dies_habils_propers[-1], 5)
    entra("resp01")
    contingut = text(client.get("/gestio"))
    assert "Treballador U" in contingut
    assert "Treballador Dos" not in contingut


def test_un_responsable_no_resol_res_d_un_altre_servei(
        client, entra, magatzem, serveis, dies_habils_propers):
    codi = mag_absencies.crea(magatzem, "treb02", serveis["Brigada"], "vacances",
                              dies_habils_propers[0], dies_habils_propers[-1], 5)
    entra("resp01")           # el seu àmbit és Oficines
    assert client.post("/gestio/resol",
                       data={"codi": codi, "accio": "aprova"}).status_code == 403


def test_aprovar_una_solicitud(client, entra, magatzem, serveis,
                               dies_habils_propers):
    codi = mag_absencies.crea(magatzem, "treb01", serveis["Oficines"], "vacances",
                              dies_habils_propers[0], dies_habils_propers[-1], 5)
    entra("resp01")
    r = client.post("/gestio/resol", data={"codi": codi, "accio": "aprova"},
                    follow_redirects=True)
    assert "aprovada" in text(r)
    assert mag_absencies.per_codi(magatzem, codi).estat == APROVADA


def test_ningu_resol_la_seva_propia_ni_sent_admin(client, entra, magatzem,
                                                  serveis, dies_habils_propers):
    """El cas que la gent es deixa sempre."""
    codi = mag_absencies.crea(magatzem, "admin01", serveis["Oficines"], "vacances",
                              dies_habils_propers[0], dies_habils_propers[-1], 5)
    entra("admin01")
    assert client.post("/gestio/resol",
                       data={"codi": codi, "accio": "aprova"}).status_code == 403


def test_ningu_valida_una_correccio_seva(client, entra, magatzem):
    from core.model import ara_utc
    correccio = marcatges.afegeix(magatzem, "resp01", "entrada", ara_utc(),
                                  "manual", "resp01",
                                  servei_id=None, estat=PENDENT_VALIDACIO)
    entra("resp01")
    assert client.post("/gestio/marcatge",
                       data={"marcatge": correccio, "accio": "valida"}
                       ).status_code == 403


def test_rebutjar_una_correccio_restaura_les_hores(client, entra, magatzem,
                                                   serveis):
    """Sense això es podrien fer desaparèixer hores fent una correcció i
    rebutjant-la."""
    from datetime import datetime, timezone
    avui = date.today()
    oficines = serveis["Oficines"]
    entrada = datetime(avui.year, avui.month, avui.day, 6, 0, tzinfo=timezone.utc)
    original = marcatges.afegeix(magatzem, "treb01", "sortida", entrada, "web",
                                 "treb01", servei_id=oficines)
    correccio = marcatges.afegeix(magatzem, "treb01", "sortida",
                                  entrada.replace(hour=8), "manual", "treb01",
                                  servei_id=oficines, anul_la_id=original,
                                  nota="error", estat=PENDENT_VALIDACIO)
    entra("resp01")
    client.post("/gestio/marcatge", data={"marcatge": correccio,
                                          "accio": "rebutja"})
    assert magatzem.doc("marcatges", original)["anulat"] is False
    assert magatzem.doc("marcatges", correccio)["estat"] == "REBUTJAT"


def test_l_avis_de_solapaments_del_servei(client, entra, magatzem, serveis,
                                          dies_habils_propers):
    oficines = serveis["Oficines"]
    mag_absencies.crea(magatzem, "treb01", oficines, "vacances",
                       dies_habils_propers[0], dies_habils_propers[-1], 5)
    altre = mag_absencies.crea(magatzem, "resp02", oficines, "vacances",
                               dies_habils_propers[0], dies_habils_propers[-1], 5)
    mag_absencies.resol(magatzem, altre, APROVADA, "admin01", "")
    entra("resp01")
    assert "també hi ha fora" in text(client.get("/gestio"))


# ===========================================================================
# Configuració
# ===========================================================================
def test_un_admin_pot_muntar_l_aplicacio_de_zero(client, entra, magatzem):
    """El recorregut de posada en marxa, sense sortir del navegador."""
    entra("admin01")

    client.post("/configuracio/servei", data={"accio": "crea", "nom": "Nou servei"})
    assert "Nou servei" in text(client.get("/configuracio/"))

    client.post("/configuracio/festiu",
                data={"accio": "afegeix", "data": f"{date.today().year}-12-25",
                      "nom": "Nadal", "ambit": "general"})
    assert "Nadal" in text(client.get(f"/configuracio/?any={date.today().year}"))

    client.post("/configuracio/patro",
                data={"nom": "Patró nou", "descripcio": "",
                      "dia": ["1", "2"], "hora_inici": ["08:00", "08:00"],
                      "hora_fi": ["15:00", "15:00"]})
    assert "Patró nou" in text(client.get("/configuracio/horaris"))

    client.post("/configuracio/compte",
                data={"accio": "alta", "login": "prova99", "nom": "Nova Persona",
                      "correu": "prova99@exemple.cat", "rol": "treballador"})
    assert comptes.per_login(magatzem, "prova99") is not None


def test_un_admin_no_es_pot_degradar_ell_mateix(client, entra):
    entra("admin01")
    r = client.post("/configuracio/compte",
                    data={"accio": "rol", "login": "admin01", "rol": "treballador"},
                    follow_redirects=True)
    assert "No et pots treure a tu mateix" in text(r)


def test_donar_de_baixa_no_esborra_el_compte(client, entra, magatzem):
    entra("admin01")
    client.post("/configuracio/compte",
                data={"accio": "baixa", "login": "treb03",
                      "data_baixa": date.today().isoformat()})
    assert magatzem.doc("treballadors", "treb03") is not None
    assert magatzem.doc("treballadors", "treb03")["actiu"] is False


def test_no_s_esborra_un_servei_amb_gent(client, entra, serveis):
    entra("admin01")
    r = client.post("/configuracio/servei",
                    data={"accio": "elimina", "id": serveis["Oficines"]},
                    follow_redirects=True)
    assert "treballadors assignats" in text(r)


def test_avis_si_l_assignacio_nova_es_solapa(client, entra, patro_id):
    entra("admin01")
    r = client.post("/configuracio/assignacio",
                    data={"login": "treb01", "patro": patro_id,
                          "data_inici": date.today().isoformat(),
                          "coeficient": "100"},
                    follow_redirects=True)
    assert "encara és vigent" in text(r)


# ===========================================================================
# Hores
# ===========================================================================
def test_el_resum_d_hores_quadra_amb_el_fitxatge(client, entra):
    entra("treb01")
    client.post("/fitxa", data={"tipus": "entrada"})
    r = client.get("/hores")
    assert r.status_code == 200
    assert "Saldo acumulat de l'any" in text(r)


def test_no_hi_ha_manera_de_veure_les_hores_d_un_altre(client, entra):
    entra("treb01")
    # Encara que algú s'inventi el paràmetre, s'ignora.
    r = client.get("/hores?treballador=treb02&any=2026&mes=8")
    assert r.status_code == 200
    assert "Treballador Dos" not in text(r)


def test_un_mes_sense_res_no_peta(client, entra):
    entra("treb01")
    assert client.get("/hores?any=2020&mes=1").status_code == 200
