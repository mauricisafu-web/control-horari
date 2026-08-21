"""
tests/test_exporta.py — Proves de l'exportador des de nòmines.

Cap prova toca la carpeta de nòmines ni cap dada real: l'xlsx d'entrada se'l
fabriquen elles mateixes a `tmp_path`, amb noms inventats i correus
`@exemple.cat`.

Cap prova pot enviar un correu: `smtplib` es substitueix sempre per un doble
que apunta què li han demanat. Si algun camí se saltés el doble, la prova
petaria amb «cap prova no pot connectar a un SMTP de debò» en comptes
d'escriure a ningú.
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import pytest

ARREL = Path(__file__).resolve().parents[1]
if str(ARREL) not in sys.path:
    sys.path.insert(0, str(ARREL))

from core.format_importacio import CODIFICACIO, COLUMNES, SEPARADOR  # noqa: E402
from eines import exporta_des_de_nomines as exporta                  # noqa: E402

# Persones inventades. Les dues «Anna Puig» i el «Andreu Puigverd» hi són per
# forçar la desambiguació del nom d'usuari.
PERSONES = [
    ("Anna Puig Roca", "anna.puig@exemple.cat"),
    ("Anna Puig Serra", "anna.serra@exemple.cat"),
    ("Andreu Puigverd Móra", "andreu.puigverd@exemple.cat"),
    ("Òscar Ferré de la Peña", "oscar.ferre@exemple.cat"),
    ("Núria Solà Ç", "nuria.sola@exemple.cat"),
]


# --------------------------------------------------------------------------
# Utillatge
# --------------------------------------------------------------------------
def fes_xlsx(desti: Path, persones=PERSONES) -> Path:
    """Un `treballadors.xlsx` sintètic, igual de format que el de nòmines."""
    openpyxl = pytest.importorskip("openpyxl")
    llibre = openpyxl.Workbook()
    full = llibre.active
    full.append(["Nom", "Correu"])
    for nom, correu in persones:
        full.append([nom, correu])
    llibre.save(desti)
    return desti


def fes_config(desti: Path, tipus: str = "starttls") -> Path:
    desti.write_text(
        "[smtp]\n"
        "servidor = smtp.exemple.cat\n"
        "port = 587\n"
        f"tipus = {tipus}\n"
        "usuari = avisos@exemple.cat\n"
        "contrasenya = contrasenya-de-prova\n"
        "remitent = avisos@exemple.cat\n", encoding="utf-8")
    return desti


def llegeix(ruta: Path) -> list[dict]:
    with open(ruta, encoding=CODIFICACIO, newline="") as f:
        return list(csv.DictReader(f, delimiter=SEPARADOR))


class ServidorFals:
    """Doble d'`smtplib.SMTP`. Apunta els missatges i no surt de la memòria."""

    instancies: list["ServidorFals"] = []

    def __init__(self, *arg, **clau):
        self.arguments = (arg, clau)
        self.missatges = []
        self.logins = []
        self.starttls_fet = False
        self.tancat = False
        self.falla_a = ()           # correus que rebotaran
        ServidorFals.instancies.append(self)

    def starttls(self, *arg, **clau):
        self.starttls_fet = True

    def login(self, usuari, contrasenya):
        self.logins.append(usuari)

    def send_message(self, missatge):
        if missatge["To"] in self.falla_a:
            raise OSError("bústia inexistent")
        self.missatges.append(missatge)

    def quit(self):
        self.tancat = True


@pytest.fixture(autouse=True)
def smtp_fals(monkeypatch):
    """Cap prova pot obrir una connexió SMTP de debò, ni per despistada."""
    ServidorFals.instancies.clear()

    def prohibit(*arg, **clau):
        raise AssertionError("cap prova no pot connectar a un SMTP de debò")

    monkeypatch.setattr(exporta.smtplib, "SMTP", ServidorFals)
    monkeypatch.setattr(exporta.smtplib, "SMTP_SSL", ServidorFals)
    monkeypatch.setattr(exporta.smtplib, "LMTP", prohibit, raising=False)
    return ServidorFals


# --------------------------------------------------------------------------
# Nom d'usuari
# --------------------------------------------------------------------------
def test_usuari_sense_accents_ni_xifres():
    assert exporta.proposa_usuari("Òscar Ferré de la Peña", set()) == "oferre"
    assert exporta.proposa_usuari("Núria Solà", set()) == "nsola"
    # La ç cau a «c» en treure els accents, i el punt volat desapareix.
    assert exporta.proposa_usuari("Cesc Vall·llosera", set()) == "cvallllosera"


def test_usuari_desambigua_sense_repetir_se():
    usats: set[str] = set()
    proposats = []
    for nom, _ in PERSONES:
        usuari = exporta.proposa_usuari(nom, usats)
        usats.add(usuari)
        proposats.append(usuari)
    assert len(set(proposats)) == len(proposats), proposats
    assert all(u.isalpha() and u.islower() for u in proposats), proposats
    assert proposats[0] == "apuig"
    assert proposats[1].startswith("apuig") and proposats[1] != "apuig"


def test_usuari_d_un_nom_sense_lletres_es_buit():
    assert exporta.proposa_usuari("1234 ---", set()) == ""


# --------------------------------------------------------------------------
# prepara
# --------------------------------------------------------------------------
def test_prepara_escriu_les_columnes_del_contracte(tmp_path):
    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    sortida = tmp_path / "sortida.csv"

    codi = exporta.main(["prepara", "--xlsx", str(xlsx),
                         "--sortida", str(sortida)])

    assert codi == 0
    files = llegeix(sortida)
    assert list(files[0].keys()) == list(COLUMNES)
    assert len(files) == len(PERSONES)
    # El BOM hi ha de ser: és el que fa que l'Excel l'obri bé.
    assert sortida.read_bytes().startswith(b"\xef\xbb\xbf")
    assert SEPARADOR.encode() in sortida.read_bytes()


def test_prepara_deixa_servei_i_rol_buits_i_dona_contrasenya_a_tothom(tmp_path):
    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    sortida = tmp_path / "sortida.csv"
    exporta.main(["prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)])

    files = llegeix(sortida)
    assert all(f["servei"] == "" and f["rol"] == "" for f in files)
    assert all(len(f["contrasenya"]) >= 10 for f in files)
    # Cadascú la seva: res de reaprofitar-ne una per a tothom.
    assert len({f["contrasenya"] for f in files}) == len(files)


def test_prepara_no_ensenya_cap_contrasenya_per_pantalla(tmp_path, capsys):
    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    sortida = tmp_path / "sortida.csv"
    exporta.main(["prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)])

    text = capsys.readouterr().out
    for fila in llegeix(sortida):
        assert fila["contrasenya"] not in text


def test_prepara_avisa_que_el_fitxer_porta_dades_personals(tmp_path, capsys):
    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    exporta.main(["prepara", "--xlsx", str(xlsx),
                  "--sortida", str(tmp_path / "s.csv")])

    text = capsys.readouterr().out.upper()
    assert "DADES PERSONALS" in text and "CONTRASENYES" in text
    assert "ESBORRA" in text


def test_prepara_avisa_dels_correus_repetits(tmp_path, capsys):
    xlsx = fes_xlsx(tmp_path / "t.xlsx", [
        ("Marta Roig Vila", "repe@exemple.cat"),
        ("Pere Lluch Font", "repe@exemple.cat"),
    ])
    exporta.main(["prepara", "--xlsx", str(xlsx),
                  "--sortida", str(tmp_path / "s.csv")])

    assert "més d'un cop" in capsys.readouterr().out


def test_el_nom_per_defecte_porta_la_data():
    nom = exporta.nom_sortida_defecte(date(2026, 8, 21))
    assert nom == "treballadors-2026-08-21.csv"


def test_prepara_salta_les_files_buides_del_full(tmp_path):
    xlsx = fes_xlsx(tmp_path / "t.xlsx", [
        ("Marta Roig Vila", "marta@exemple.cat"),
        ("", ""),
        ("Pere Lluch Font", "pere@exemple.cat"),
    ])
    sortida = tmp_path / "s.csv"
    exporta.main(["prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)])
    assert len(llegeix(sortida)) == 2


# --------------------------------------------------------------------------
# El CSV generat, contra l'analitzador de debò
# --------------------------------------------------------------------------
def test_el_csv_generat_l_accepta_l_analitzador(tmp_path):
    """L'acceptació de l'encàrrec: el que escriu `prepara` ha d'entrar a
    `core.importa.analitza()` sense cap error.

    Mentre INT-A no hi hagi aterrat, `analitza()` encara llança
    `NotImplementedError` i la prova se salta amb un motiu explícit: així no
    dona un fals verd ni un fals vermell (vegeu `incidencies/INT-B.md`)."""
    from core import importa

    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    sortida = tmp_path / "s.csv"
    exporta.main(["prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)])
    contingut = sortida.read_text(encoding=CODIFICACIO)

    try:
        files, errors = importa.analitza(contingut)
    except NotImplementedError:
        pytest.skip("core.importa.analitza() encara no està implementat "
                    "(INT-A); el CSV es valida estructuralment a la prova "
                    "següent.")

    assert errors == [], [e.detall for e in errors]
    assert len(files) == len(PERSONES)
    assert {f.usuari for f in files} == {f["usuari"] for f in llegeix(sortida)}


def test_el_csv_generat_compleix_el_contracte_de_columnes(tmp_path):
    """Xarxa de seguretat de la prova anterior: capçalera exacta, columnes
    obligatòries plenes i cap separador dins d'un valor."""
    from core.format_importacio import COLUMNES_OBLIGATORIES

    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    sortida = tmp_path / "s.csv"
    exporta.main(["prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)])

    linies = sortida.read_text(encoding=CODIFICACIO).splitlines()
    assert linies[0] == SEPARADOR.join(COLUMNES)
    for fila in llegeix(sortida):
        for columna in COLUMNES_OBLIGATORIES:
            assert fila[columna], (columna, fila)
        assert all(SEPARADOR not in (v or "") for v in fila.values())


# --------------------------------------------------------------------------
# envia
# --------------------------------------------------------------------------
def fes_csv(desti: Path, files) -> Path:
    exporta.escriu_csv(desti, files)
    return desti


def files_de_prova():
    return [
        {"usuari": "apuig", "nom": "Anna Puig Roca",
         "correu": "anna@exemple.cat", "servei": "Oficines", "rol": "",
         "data_alta": "", "contrasenya": "ProvaProva24"},
        {"usuari": "plluch", "nom": "Pere Lluch Font",
         "correu": "pere@exemple.cat", "servei": "Brigada", "rol": "",
         "data_alta": "", "contrasenya": "AltraProva24"},
        # Sense contrasenya: ja té compte al control horari, no li toca correu.
        {"usuari": "mroig", "nom": "Marta Roig Vila",
         "correu": "marta@exemple.cat", "servei": "Oficines", "rol": "",
         "data_alta": "", "contrasenya": ""},
    ]


def test_envia_sense_prova_ni_confirma_no_fa_res(tmp_path, capsys):
    csv_ = fes_csv(tmp_path / "t.csv", files_de_prova())

    codi = exporta.main(["envia", "--fitxer", str(csv_),
                         "--config", str(fes_config(tmp_path / "c.ini"))])

    assert codi == 2
    assert ServidorFals.instancies == []
    assert "No s'ha fet res" in capsys.readouterr().out


def test_envia_amb_prova_no_envia_i_diu_a_qui_escriuria(tmp_path, capsys):
    csv_ = fes_csv(tmp_path / "t.csv", files_de_prova())

    codi = exporta.main(["envia", "--fitxer", str(csv_), "--prova",
                         "--config", str(fes_config(tmp_path / "c.ini"))])

    assert codi == 0
    assert ServidorFals.instancies == []
    text = capsys.readouterr().out
    assert "anna@exemple.cat" in text and "pere@exemple.cat" in text
    # Qui no té contrasenya surt com a saltat, no com a destinatari.
    assert "marta@exemple.cat" in text and "sense contrasenya" in text
    # I cap contrasenya no apareix per pantalla.
    assert "ProvaProva24" not in text and "AltraProva24" not in text


def test_envia_amb_confirma_escriu_a_qui_te_contrasenya(tmp_path):
    csv_ = fes_csv(tmp_path / "t.csv", files_de_prova())

    codi = exporta.main(["envia", "--fitxer", str(csv_), "--confirma",
                         "--config", str(fes_config(tmp_path / "c.ini"))])

    assert codi == 0
    servidor = ServidorFals.instancies[-1]
    destinataris = [m["To"] for m in servidor.missatges]
    assert destinataris == ["anna@exemple.cat", "pere@exemple.cat"]
    assert servidor.starttls_fet and servidor.logins == ["avisos@exemple.cat"]
    assert servidor.tancat


def test_el_correu_diu_usuari_contrasenya_i_que_es_provisional(tmp_path):
    csv_ = fes_csv(tmp_path / "t.csv", files_de_prova())
    exporta.main(["envia", "--fitxer", str(csv_), "--confirma",
                  "--config", str(fes_config(tmp_path / "c.ini"))])

    cos = ServidorFals.instancies[-1].missatges[0].get_content()
    assert "apuig" in cos and "ProvaProva24" in cos
    assert "PROVISIONAL" in cos.upper()
    assert "canviar-la" in cos


def test_envia_es_fail_soft_i_reporta_qui_no_l_ha_rebut(tmp_path, capsys):
    csv_ = fes_csv(tmp_path / "t.csv", files_de_prova())
    original = ServidorFals.__init__

    def amb_rebot(self, *arg, **clau):
        original(self, *arg, **clau)
        self.falla_a = ("anna@exemple.cat",)

    ServidorFals.__init__ = amb_rebot
    try:
        codi = exporta.main(["envia", "--fitxer", str(csv_), "--confirma",
                             "--config", str(fes_config(tmp_path / "c.ini"))])
    finally:
        ServidorFals.__init__ = original

    assert codi == 1
    # El segon s'ha enviat igualment: un rebot no atura la resta.
    assert [m["To"] for m in ServidorFals.instancies[-1].missatges] == \
        ["pere@exemple.cat"]
    text = capsys.readouterr().out
    assert "NO els han rebut" in text and "anna@exemple.cat" in text


def test_envia_amb_ssl_no_fa_starttls(tmp_path):
    csv_ = fes_csv(tmp_path / "t.csv", files_de_prova())
    config = fes_config(tmp_path / "c.ini", tipus="ssl")

    exporta.main(["envia", "--fitxer", str(csv_), "--confirma",
                  "--config", str(config)])

    assert ServidorFals.instancies[-1].starttls_fet is False


def test_smtp_es_llegeix_del_config_ini_de_nomines(tmp_path):
    cfg = exporta.carrega_smtp(fes_config(tmp_path / "c.ini"))
    assert cfg["servidor"] == "smtp.exemple.cat"
    assert cfg["remitent"] == "avisos@exemple.cat"


def test_un_config_sense_seccio_smtp_s_explica(tmp_path):
    ini = tmp_path / "c.ini"
    ini.write_text("[altre]\nx = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit) as excepcio:
        exporta.carrega_smtp(ini)
    assert "smtp" in str(excepcio.value)


def test_un_csv_que_no_hi_es_no_peta_lletjament(tmp_path):
    with pytest.raises(SystemExit) as excepcio:
        exporta.main(["envia", "--fitxer", str(tmp_path / "no-hi-es.csv"),
                      "--prova"])
    assert "prepara" in str(excepcio.value)


# --------------------------------------------------------------------------
# La carpeta de nòmines: només lectura
# --------------------------------------------------------------------------
def test_la_ruta_de_nomines_nomes_surt_com_a_valor_per_defecte():
    """Regla dura de l'encàrrec: la carpeta de nòmines pot sortir en un
    comentari o com a valor per defecte d'un argument, mai fixada dins la
    lògica."""
    codi = Path(exporta.__file__).read_text(encoding="utf-8").splitlines()
    sospitoses = [
        linia for linia in codi
        if "expedients-nomines" in linia
        and not linia.lstrip().startswith("#")
        and not linia.startswith("CARPETA_NOMINES")
    ]
    assert sospitoses == [], sospitoses


def test_cap_ordre_obre_res_en_escriptura_fora_de_la_sortida(tmp_path,
                                                             monkeypatch):
    """`prepara` i `envia` només han d'obrir en escriptura el fitxer que els
    ha dit l'usuari."""
    oberts = []
    obre_original = exporta.open if hasattr(exporta, "open") else open

    import builtins
    original = builtins.open

    def vigilat(fitxer, mode="r", *arg, **clau):
        if any(m in mode for m in "wxa+"):
            oberts.append(Path(fitxer).resolve())
        return original(fitxer, mode, *arg, **clau)

    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")   # abans de vigilar
    sortida = tmp_path / "s.csv"

    monkeypatch.setattr(builtins, "open", vigilat)
    exporta.main(["prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)])
    monkeypatch.setattr(builtins, "open", original)

    assert oberts == [sortida.resolve()]
    assert obre_original is original


# --------------------------------------------------------------------------
# Regressió: la consola de Windows en cp1252
# --------------------------------------------------------------------------
def test_prepara_no_peta_amb_la_consola_en_cp1252(tmp_path):
    """Va passar de debò el 2026-08-21: la consola de Windows arrenca en
    cp1252, que no té els caràcters «⚠», «✓» ni «✗» dels avisos. `capsys`
    substitueix stdout per un flux que SÍ els accepta, així que aquesta
    prova no es podia escriure amb `capsys`: calia un procés de debò amb la
    mateixa codificació que trobaria l'usuari, o el forat es tornaria a
    colar sense que cap prova se n'adonés.

    Amb el fitxer ja escrit correctament i només el missatge final petant,
    l'usuari es quedava sense saber-ho: `prepara` semblava haver fallat del
    tot quan en realitat el CSV ja hi era."""
    import os
    import subprocess

    xlsx = fes_xlsx(tmp_path / "treballadors.xlsx")
    sortida = tmp_path / "s.csv"

    entorn = dict(os.environ)
    entorn.pop("PYTHONIOENCODING", None)
    entorn.pop("PYTHONUTF8", None)
    entorn["PYTHONLEGACYWINDOWSSTDIO"] = "1"

    resultat = subprocess.run(
        [sys.executable, str(ARREL / "eines" / "exporta_des_de_nomines.py"),
         "prepara", "--xlsx", str(xlsx), "--sortida", str(sortida)],
        capture_output=True, text=False, env=entorn, timeout=30)

    assert resultat.returncode == 0, resultat.stderr.decode("cp1252", "replace")
    assert sortida.exists()
