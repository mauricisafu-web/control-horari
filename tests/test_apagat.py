"""
Proves de l'interruptor del fitxador.

L'ajuntament pot voler NOMÉS la part de vacances i permisos. Aquestes proves
fixen les dues cares del tracte:

1. Apagat, les pantalles de fitxar no existeixen per a ningú. Amagar l'enllaç
   del menú i deixar la ruta oberta no és amagar res.
2. Apagat, demanar i aprovar vacances continua funcionant sencer. Si això es
   trenca, l'aplicació es queda sense l'única cosa que l'ajuntament en volia.
"""
from __future__ import annotations

from datetime import date

import pytest

from core.model import APROVADA
from magatzem import absencies as mag_absencies, parametres


@pytest.fixture
def apagat(magatzem):
    parametres.desa(magatzem, "fitxatge_actiu", False)
    return magatzem


def text(r):
    return r.get_data(as_text=True)


# -- el fitxador desapareix -------------------------------------------------
@pytest.mark.parametrize("ruta", ["/hores", "/el-meu-horari", "/marcatges"])
def test_les_pantalles_de_fitxatge_no_existeixen(client, entra, apagat, ruta):
    entra("treb01")
    assert client.get(ruta).status_code == 404


@pytest.mark.parametrize("ruta", ["/fitxa", "/marcatges/corregeix"])
def test_tampoc_s_hi_pot_escriure(client, entra, apagat, ruta):
    """La porta del darrere: qui sàpiga l'adreça del POST no ha de poder
    fitxar igualment."""
    entra("treb01")
    assert client.post(ruta, data={"tipus": "entrada"}).status_code == 404


def test_l_arrel_porta_a_absencies_i_no_a_un_404(client, entra, apagat):
    """`/` és l'arrel de l'aplicació: qui entra ha d'anar a parar a algun
    lloc, no a una pàgina d'error."""
    entra("treb01")
    resposta = client.get("/")
    assert resposta.status_code == 302
    assert "/absencies" in resposta.headers["Location"]


def test_els_informes_tambe_desapareixen(client, entra, apagat):
    """L'informe ÉS el registre de jornada: sense fitxatge no hi ha res a
    informar."""
    entra("admin01")
    assert client.get("/informes").status_code == 404


def test_la_gestio_d_hores_i_de_marcatges_desapareix(client, entra, apagat):
    entra("resp01")
    assert client.get("/gestio/hores").status_code == 404
    assert client.post("/gestio/marcatge", data={"marcatge": "x"}).status_code == 404


def test_el_menu_no_ensenya_el_fitxador(client, entra, apagat):
    entra("treb01")
    menu = text(client.get("/absencies"))
    assert ">Fitxar<" not in menu
    assert ">Hores<" not in menu
    assert ">Absències<" in menu


def test_la_gestio_segueix_funcionant_sense_fitxatge(client, entra, apagat):
    """La pantalla de gestió barreja absències i correccions de marcatge:
    apagar-ne una meitat no pot tombar l'altra."""
    entra("resp01")
    assert client.get("/gestio").status_code == 200


# -- les vacances continuen senceres ---------------------------------------
def test_es_pot_demanar_i_aprovar_una_absencia_amb_el_fitxador_apagat(
        client, entra, apagat, magatzem, serveis, dies_habils_propers):
    entra("treb01")
    dies = dies_habils_propers
    client.post("/absencies/solicita",
                data={"tipus": "vacances", "inici": dies[0].isoformat(),
                      "fi": dies[-1].isoformat(), "motiu": "estiu"},
                follow_redirects=True)

    meves = mag_absencies.de_treballador(magatzem, "treb01", dies[0].year)
    demanada = [a for a in meves if a.data_inici == dies[0]]
    assert demanada, "no s'ha desat la sol·licitud"

    # Cal sortir abans: amb sessio oberta, /login redirigeix sense canviar de
    # persona, i el test aprovaria la seva propia sol·licitud (que es
    # justament el que l'aplicacio prohibeix).
    client.get("/logout")
    entra("resp01")
    client.post("/gestio/resol", data={"codi": demanada[0].codi,
                                       "accio": "aprova"},
                follow_redirects=True)
    assert mag_absencies.per_codi(magatzem, demanada[0].codi).estat == APROVADA


# -- engegat, tot torna -----------------------------------------------------
def test_engegat_de_naixement(client, entra):
    """Sense tocar res, el fitxador hi és: l'aplicació és, de naixement, de
    control horari."""
    entra("treb01")
    assert client.get("/").status_code == 200
    assert client.get("/hores").status_code == 200


def test_l_admin_el_pot_apagar_i_tornar_a_engegar(client, entra, magatzem):
    entra("admin01")
    client.post("/configuracio/fitxatge", data={}, follow_redirects=True)
    assert parametres.tots(magatzem)["fitxatge_actiu"] is False
    assert client.get("/hores").status_code == 404

    client.post("/configuracio/fitxatge", data={"fitxatge_actiu": "1"},
                follow_redirects=True)
    assert parametres.tots(magatzem)["fitxatge_actiu"] is True
    assert client.get("/hores").status_code == 200


def test_apagar_no_esborra_cap_marcatge(client, entra, magatzem):
    from magatzem import marcatges
    entra("treb01")
    client.post("/fitxa", data={"tipus": "entrada"}, follow_redirects=True)
    abans = len(marcatges.del_dia(magatzem, "treb01", date.today()))
    assert abans > 0

    parametres.desa(magatzem, "fitxatge_actiu", False)
    assert len(marcatges.del_dia(magatzem, "treb01", date.today())) == abans


def test_un_treballador_no_pot_apagar_el_fitxador(client, entra):
    entra("treb01")
    assert client.post("/configuracio/fitxatge", data={}).status_code == 403


def test_un_responsable_tampoc(client, entra):
    entra("resp01")
    assert client.post("/configuracio/fitxatge", data={}).status_code == 403
