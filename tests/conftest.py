"""
tests/conftest.py — Fixtures compartides. FITXER CONGELAT.

Cap agent l'edita. Si necessites una fixture que no hi és, la defineixes al
TEU fitxer de tests (les locals hi tenen preferència) i, si creus que hauria
de ser comuna, ho anotes a `incidencies/<el-teu-id>.md`.

Les proves corren SEMPRE contra `RebostMemoria`: són instantànies, no
necessiten ni Node, ni Java, ni emulador, ni connexió, i no poden tocar cap
dada de veritat encara que algú s'equivoqui de variable d'entorn. La
verificació contra Firestore de debò es fa a `tests/integracio/` (agent 1A) i
és una porta de l'onada 5A, abans de desplegar.

Totes les dades d'aquí són SINTÈTIQUES. Mai un nom, un correu ni una
contrasenya reals de l'ajuntament.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ARREL = Path(__file__).resolve().parents[1]
if str(ARREL) not in sys.path:
    sys.path.insert(0, str(ARREL))

from magatzem import rebost as reb  # noqa: E402

# Contrasenya de tots els comptes de prova. Sintètica i pública a propòsit.
CONTRASENYA_PROVA = "Prova-1234"

# Secret TOTP de prova, conegut i públic. Els comptes que veuen dades d'altres
# persones (admin i responsables) el porten activat, perquè les proves passin
# pel MATEIX camí que la producció: amb segon factor.
SECRET_TOTP = "JBSWY3DPEHPK3PXP"
AMB_TOTP = ("admin01", "resp01", "resp02")

# (login, nom, correu, rol, servei)
COMPTES = (
    ("admin01", "Admin de Prova", "admin01@exemple.cat", "admin", "Oficines"),
    ("resp01", "Responsable Oficines", "resp01@exemple.cat", "responsable", "Oficines"),
    ("resp02", "Responsable Brigada", "resp02@exemple.cat", "responsable", "Brigada"),
    ("treb01", "Treballador U", "treb01@exemple.cat", "treballador", "Oficines"),
    ("treb02", "Treballador Dos", "treb02@exemple.cat", "treballador", "Brigada"),
    ("treb03", "Treballadora Tres", "treb03@exemple.cat", "treballador", "SAIAR"),
)

SERVEIS = ("Oficines", "Brigada", "SAIAR")

# Àmbit d'aprovació de cada responsable. `None` voldria dir «tots els serveis».
AMBITS = {"resp01": ["Oficines"], "resp02": ["Brigada"]}


def _pobla(magatzem) -> None:
    """Un món coherent i mínim: 3 serveis, 6 comptes dels tres rols, un patró
    de 7 h de dilluns a divendres assignat a tothom, dos festius i els saldos
    de l'any en curs."""
    from werkzeug.security import generate_password_hash

    ara = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    any_actual = date.today().year
    hash_prova = generate_password_hash(CONTRASENYA_PROVA)

    ids_servei = {}
    for nom in SERVEIS:
        ids_servei[nom] = magatzem.afegeix(reb.SERVEIS, {"nom": nom, "color": "#1e4078"})

    # Un patró de 7 h diàries (08:00-15:00), de dilluns a divendres.
    patro_id = magatzem.afegeix(reb.PATRONS, {
        "nom": "Jornada de prova",
        "descripcio": "08:00 a 15:00, de dilluns a divendres",
        "trams": [{"dia_setmana": d, "hora_inici": "08:00", "hora_fi": "15:00"}
                  for d in range(1, 6)],
    })

    for login, nom, correu, rol, servei in COMPTES:
        # L'identificador del document ÉS el login: llegir un compte és una
        # crida directa, no una consulta.
        magatzem.desa(reb.TREBALLADORS, login, {
            "login": login, "nom": nom, "correu": correu,
            "correu_norm": correu.strip().lower(),
            "hash_contrasenya": hash_prova, "rol": rol,
            "servei_id": ids_servei[servei],
            "data_alta": f"{any_actual - 3}-01-01", "data_baixa": None,
            "actiu": True, "canvi_pendent": False,
            "totp_secret": SECRET_TOTP if login in AMB_TOTP else None,
            "totp_actiu": login in AMB_TOTP,
            "creat_el": ara, "ultim_acces": None,
            "ambits": [ids_servei[s] for s in AMBITS.get(login, [])],
            "assignacions": [{"patro_id": patro_id,
                              "data_inici": f"{any_actual - 3}-01-01",
                              "data_fi": None, "coeficient": 100}],
            "codis_recuperacio": [],
        })
        # Un document de saldos per treballador i any: una sola lectura.
        magatzem.desa(reb.SALDOS, f"{login}_{any_actual}", {
            "treballador_id": login, "any": any_actual,
            "vacances": 22, "assumptes_propis": 6,
        })

    # Un document de festius per any: una sola lectura per a tot el calendari.
    magatzem.desa(reb.FESTIUS, str(any_actual), {
        "any": any_actual,
        "dies": {
            f"{any_actual}-01-01": {"nom": "Cap d'Any", "ambit": "general"},
            f"{any_actual}-01-06": {"nom": "Reis", "ambit": "general"},
        },
    })

    reb.inicialitza(magatzem)


@pytest.fixture
def magatzem():
    """Magatzem de documents en memòria, poblat amb les dades sintètiques."""
    m = reb.RebostMemoria()
    _pobla(m)
    return m


@pytest.fixture
def magatzem_buit():
    """Magatzem sense res, només amb els paràmetres inicials. Per a les proves
    d'alta des de zero (l'agent 3E l'usa per al recorregut de posada en marxa)."""
    m = reb.RebostMemoria()
    reb.inicialitza(m)
    return m


@pytest.fixture
def serveis(magatzem) -> dict[str, str]:
    """{nom del servei: identificador}."""
    return {d["nom"]: d["id"] for d in magatzem.consulta(reb.SERVEIS)}


@pytest.fixture
def patro_id(magatzem) -> str:
    return magatzem.consulta(reb.PATRONS)[0]["id"]


@pytest.fixture
def app(magatzem, monkeypatch):
    """Aplicació Flask de proves sobre el magatzem en memòria.

    La importació d'`app_web` és DINS de la fixture a propòsit: les proves de
    domini pur (`core/`) no han de dependre que la capa web existeixi."""
    monkeypatch.setenv("REBOST", "memoria")
    monkeypatch.setenv("SECRET_KEY", "clau-de-prova-no-real")
    monkeypatch.setenv("FLASK_DEBUG", "0")

    import app_web
    return app_web.crea_app({"TESTING": True, "WTF_CSRF_ENABLED": False},
                            magatzem=magatzem)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def entra(client):
    """Deixa una sessió oberta: `entra('treb01')`. Falla si no s'hi ha pogut
    entrar, perquè un test que creu que té sessió i no en té dona errors
    incomprensibles."""
    def _entra(login: str, contrasenya: str = CONTRASENYA_PROVA):
        resposta = client.post("/login",
                               data={"usuari": login, "contrasenya": contrasenya},
                               follow_redirects=True)
        # Els comptes amb segon factor encara no han entrat: falta el codi.
        if "Verificació en dos passos" in resposta.get_data(as_text=True):
            import pyotp
            resposta = client.post(
                "/login/totp", data={"codi": pyotp.TOTP(SECRET_TOTP).now()},
                follow_redirects=True)
        assert resposta.status_code == 200, f"No s'ha pogut entrar com a {login}"
        return resposta
    return _entra


@pytest.fixture
def dies_habils_propers():
    """Cinc dies hàbils a partir de demà, per demanar absències sense xocar
    amb caps de setmana."""
    dies, dia = [], date.today() + timedelta(days=1)
    while len(dies) < 5:
        if dia.weekday() < 5:
            dies.append(dia)
        dia += timedelta(days=1)
    return dies
