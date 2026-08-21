"""
eines/exporta_des_de_nomines.py — Exportador de treballadors cap al control
horari, executat des del PC de l'ajuntament.

Llegeix la llista de treballadors que manté l'aplicació de nòmines
(`treballadors.xlsx`, columnes «Nom» i «Correu»), en proposa el nom d'usuari,
hi genera una contrasenya provisional i escriu el CSV que la pantalla
«Carrega treballadors des d'un fitxer» del control horari sap llegir.

Després envia a cada persona el seu usuari i la seva contrasenya amb l'SMTP
que l'aplicació de nòmines JA té configurat. Així la contrasenya neix i
s'envia des del PC de l'ajuntament, i al núvol només hi arriba per ser
xifrada: el control horari desplegat no necessita SMTP.
(Vegeu `desplegament/INTEGRACIO_NOMINES.md`.)

    python eines/exporta_des_de_nomines.py prepara --xlsx <ruta> --sortida <csv>
    python eines/exporta_des_de_nomines.py envia --fitxer <csv> --prova
    python eines/exporta_des_de_nomines.py envia --fitxer <csv> --confirma

REGLA DURA: de la carpeta de nòmines només se'n LLEGEIX. Aquesta eina no hi
escriu mai res, ni el CSV (que va on digui `--sortida`, per defecte al
directori actual). Per això viu al repositori del control horari encara que
operi sobre dades de nòmines, i per això totes les rutes són ARGUMENTS amb un
valor per defecte, mai valors fixats dins la lògica.

`envia` funciona en DOS PASSOS a propòsit: sense `--prova` ni `--confirma` no
fa res. Enviar dotzenes de correus reals a persones reals no ha de poder
passar per accident.
"""
from __future__ import annotations

import argparse
import configparser
import csv
import re
import smtplib
import ssl
import sys
import unicodedata
from datetime import date
from email.message import EmailMessage
from pathlib import Path

ARREL = Path(__file__).resolve().parents[1]
if str(ARREL) not in sys.path:
    sys.path.insert(0, str(ARREL))

from core import comptes                                          # noqa: E402
from core.format_importacio import (CODIFICACIO, COLUMNES,        # noqa: E402
                                    SEPARADOR)

# --------------------------------------------------------------------------
# Rutes de l'aplicació de nòmines: NOMÉS com a valor per defecte d'un
# argument. Si la carpeta canvia de lloc, es passa `--xlsx` i `--config` i
# aquesta eina continua funcionant sense tocar-ne ni una línia.
# --------------------------------------------------------------------------
CARPETA_NOMINES = Path(r"C:\Users\secretari\expedients-nomines-beta")
XLSX_DEFECTE = CARPETA_NOMINES / "treballadors.xlsx"
CONFIG_DEFECTE = CARPETA_NOMINES / "config.ini"

ESPERA_SMTP = 15        # segons; un servidor mut no ha de penjar l'eina
ASSUMPTE = "El teu compte del control horari de l'Ajuntament"

# Partícules que no compten per formar el nom d'usuari: «de», «la»…
PARTICULES = ("de", "del", "la", "los", "las", "i", "ma")


# --------------------------------------------------------------------------
# Nom d'usuari
# --------------------------------------------------------------------------
def _sense_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def proposa_usuari(nom: str, ja_usats: set[str]) -> str:
    """Inicial del nom + primer cognom, en minúscules i sense accents.

    Adaptació de `proposa_usuari()` de l'aplicació de nòmines, que ja fa anys
    que resol aquests noms bé. Dues diferències volgudes:

    - aquí el login només pot portar lletres «a-z» (així ho demana
      `INTEGRACIO_NOMINES.md`), o sigui que també cau el punt volat de
      «l·l»; la ç ja queda en «c» en treure els accents;
    - la desambiguació continua sent SENSE XIFRES: s'allarga amb les lletres
      del cognom següent fins que el nom és únic. Un «jgarcia2» no diu res a
      ningú i s'escriu malament la meitat de les vegades.
    """
    parts = [p for p in _sense_accents(nom or "").lower().split()
             if p not in PARTICULES]
    parts = [re.sub(r"[^a-z]", "", p) for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    base = (parts[0][0] + parts[1]) if len(parts) >= 2 else parts[0]
    if base not in ja_usats:
        return base
    extra = parts[2] if len(parts) >= 3 else parts[-1]
    for i in range(1, len(extra) + 1):
        candidat = base + extra[:i]
        if candidat not in ja_usats:
            return candidat
    # Últim recurs: encara sense xifres.
    candidat = base + "x"
    while candidat in ja_usats:
        candidat += "x"
    return candidat


# --------------------------------------------------------------------------
# Lectura de l'xlsx de nòmines (només lectura)
# --------------------------------------------------------------------------
def llegeix_treballadors(ruta_xlsx: Path) -> list[tuple[str, str]]:
    """Les parelles (nom, correu) del full, saltant la capçalera i les files
    buides. `read_only=True`: no s'hi escriu ni per accident."""
    import openpyxl        # dependència de nòmines; vegeu incidencies/INT-B.md

    ruta_xlsx = Path(ruta_xlsx)
    if not ruta_xlsx.exists():
        raise SystemExit(f"No es troba {ruta_xlsx}: cal la llista de "
                         f"treballadors de l'aplicació de nòmines.")
    llibre = openpyxl.load_workbook(ruta_xlsx, read_only=True, data_only=True)
    try:
        persones = []
        for fila in llibre.active.iter_rows(min_row=2, values_only=True):
            if not fila:
                continue
            nom = str(fila[0] or "").strip()
            correu = str(fila[1] or "").strip() if len(fila) > 1 else ""
            if not nom and not correu:
                continue
            persones.append((nom, correu))
        return persones
    finally:
        llibre.close()


# --------------------------------------------------------------------------
# Construcció i escriptura del CSV
# --------------------------------------------------------------------------
def nom_sortida_defecte(avui: date | None = None) -> str:
    """`treballadors-AAAA-MM-DD.csv`. La data al nom perquè, quan n'hi hagi
    tres a la carpeta de descàrregues, se sàpiga quin és el bo."""
    return f"treballadors-{(avui or date.today()).isoformat()}.csv"


def construeix_files(persones) -> tuple[list[dict], list[str]]:
    """Les files del CSV i la llista d'avisos per ensenyar per pantalla.

    `servei` i `rol` queden BUITS a propòsit: nòmines no en sap res i
    inventar-los seria pitjor que deixar-los per omplir. Tothom rep
    contrasenya provisional; qui ja tingui compte al control horari, se li
    buida la casella en revisar el fitxer (una càrrega no pot canviar la
    contrasenya de ningú que ja estigui fent servir l'aplicació)."""
    files, avisos = [], []
    usats: set[str] = set()
    correus_vistos: set[str] = set()

    for nom, correu in persones:
        usuari = proposa_usuari(nom, usats)
        if not usuari:
            avisos.append(f"«{nom or '(sense nom)'}»: no se n'ha pogut "
                          f"proposar cap nom d'usuari; omple'l a mà.")
        usats.add(usuari)

        clau = correu.lower()
        if not correu:
            avisos.append(f"«{nom}»: no té correu al full de nòmines.")
        elif clau in correus_vistos:
            avisos.append(f"«{nom}»: el correu {correu} surt més d'un cop; "
                          f"el control horari els vol únics.")
        correus_vistos.add(clau)

        files.append({
            "usuari": usuari,
            "nom": nom,
            "correu": correu,
            "servei": "",
            "rol": "",
            "data_alta": "",
            "contrasenya": comptes.contrasenya_provisional(),
        })
    return files, avisos


def escriu_csv(ruta_sortida: Path, files) -> None:
    """CSV amb `;` i UTF-8 amb BOM: el mateix criteri que la resta
    d'exportacions, perquè l'Excel l'obri bé sense fer-hi res."""
    ruta_sortida = Path(ruta_sortida)
    with open(ruta_sortida, "w", encoding=CODIFICACIO, newline="") as f:
        escriptor = csv.DictWriter(f, fieldnames=list(COLUMNES),
                                   delimiter=SEPARADOR, extrasaction="ignore")
        escriptor.writeheader()
        for fila in files:
            escriptor.writerow(fila)


def llegeix_csv(ruta: Path) -> list[dict]:
    ruta = Path(ruta)
    if not ruta.exists():
        raise SystemExit(f"No es troba {ruta}: executa primer «prepara».")
    with open(ruta, encoding=CODIFICACIO, newline="") as f:
        lector = csv.DictReader(f, delimiter=SEPARADOR)
        if not lector.fieldnames or "correu" not in lector.fieldnames:
            raise SystemExit(f"{ruta} no sembla el fitxer de treballadors: "
                             f"no hi ha cap columna «correu».")
        return [{(k or "").strip(): (v or "").strip() for k, v in fila.items()}
                for fila in lector]


# --------------------------------------------------------------------------
# Correu (l'SMTP de nòmines, LLEGIT del seu config.ini)
# --------------------------------------------------------------------------
def carrega_smtp(ruta_config: Path) -> dict:
    """La secció `[smtp]` del `config.ini` de nòmines. Només lectura."""
    ruta_config = Path(ruta_config)
    if not ruta_config.exists():
        raise SystemExit(f"No es troba {ruta_config}: cal la configuració "
                         f"SMTP de l'aplicació de nòmines.")
    cp = configparser.ConfigParser()
    cp.read(ruta_config, encoding="utf-8")
    if not cp.has_section("smtp"):
        raise SystemExit(f"{ruta_config} no té cap secció [smtp].")
    return dict(cp.items("smtp"))


def connecta_smtp(cfg: dict):
    """Connexió SMTP: plain (25), starttls (587) o ssl (465).

    Còpia adaptada del `connecta_smtp()` de nòmines —codi que ja ha enviat
    correus de debò— i no una crida a aquell mòdul: aquesta aplicació no
    depèn de cap altra. Per defecte es VERIFICA el certificat; només es
    desactiva si el `config.ini` ho diu (hi ha hostings compartits amb el
    certificat a nom d'una altra màquina)."""
    tipus = str(cfg.get("tipus", "starttls")).lower()
    port = int(cfg.get("port", 587))
    verifica = str(cfg.get("verifica_tls", "si")).strip().lower() \
        not in ("no", "0", "false")
    ctx = ssl.create_default_context()
    if not verifica:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if tipus == "ssl":
        servidor = smtplib.SMTP_SSL(cfg["servidor"], port,
                                    timeout=ESPERA_SMTP, context=ctx)
    else:
        servidor = smtplib.SMTP(cfg["servidor"], port, timeout=ESPERA_SMTP)
        if tipus == "starttls":
            servidor.starttls(context=ctx)
    usuari = str(cfg.get("usuari", "")).strip()
    contrasenya = str(cfg.get("contrasenya", "")).strip()
    if usuari and contrasenya and contrasenya != "CANVIA_AIXO":
        servidor.login(usuari, contrasenya)
    return servidor


def cos_correu(nom: str, usuari: str, contrasenya: str) -> str:
    return (
        f"Hola{', ' + nom if nom else ''}.\n\n"
        f"Ja tens compte a l'aplicació de control horari de l'Ajuntament.\n\n"
        f"    Usuari: {usuari}\n"
        f"    Contrasenya provisional: {contrasenya}\n\n"
        f"Aquesta contrasenya és PROVISIONAL: la primera vegada que entris, "
        f"l'aplicació t'obligarà a canviar-la. Fes-ho de seguida, perquè ha "
        f"viatjat per correu i el correu no és un canal segur.\n\n"
        f"Atentament,\nAjuntament\n")


def envia_un(servidor, remitent: str, fila: dict) -> None:
    """Un correu. Llança si falla: qui crida decideix si continua."""
    missatge = EmailMessage()
    missatge["Subject"] = ASSUMPTE
    missatge["From"] = remitent
    missatge["To"] = fila["correu"]
    missatge.set_content(cos_correu(fila.get("nom", ""), fila.get("usuari", ""),
                                    fila.get("contrasenya", "")))
    servidor.send_message(missatge)


# --------------------------------------------------------------------------
# Ordres
# --------------------------------------------------------------------------
def prepara(arg) -> int:
    persones = llegeix_treballadors(arg.xlsx)
    if not persones:
        print("  El full no té cap persona: no s'ha generat cap fitxer.")
        return 1

    files, avisos = construeix_files(persones)
    sortida = Path(arg.sortida) if arg.sortida else Path(nom_sortida_defecte())
    escriu_csv(sortida, files)

    print(f"  Generat: {sortida}")
    print(f"  {len(files)} persones · columnes «servei» i «rol» buides")
    if avisos:
        print("\n  AVISOS:")
        for avis in avisos:
            print(f"    · {avis}")
    print("\n  REVISA-HO abans d'enviar res:")
    print("    · «usuari»: només lletres minúscules i sense repetits.")
    print("    · «servei»: el nom tal com és al control horari.")
    print("    · «rol»: buit = treballador; si no, «responsable» o «admin».")
    print("    · «data_alta»: només si va entrar a mig any i cal prorratejar-li")
    print("      els dies de vacances.")
    print("    · «contrasenya»: BUIDA-LA a qui ja tingui compte al control")
    print("      horari; una càrrega no canvia la contrasenya de ningú.")
    print("\n  ⚠  Aquest fitxer conté DADES PERSONALS i CONTRASENYES en clar.")
    print("     No l'enviïs per correu, no el deixis a una carpeta compartida")
    print("     i ESBORRA'L quan l'hagis fet servir.")
    print(f"\n  Després:  python eines/exporta_des_de_nomines.py envia "
          f"--fitxer {sortida} --prova")
    return 0


def envia(arg) -> int:
    if not arg.prova and not arg.confirma:
        print("  No s'ha fet res: cal dir-ho explícitament.")
        print("    --prova     diu a qui escriuria, sense enviar res")
        print("    --confirma  envia els correus de debò")
        return 2

    files = llegeix_csv(arg.fitxer)
    amb_clau = [f for f in files if f.get("contrasenya")]
    sense_clau = [f for f in files if not f.get("contrasenya")]

    if not amb_clau:
        print("  Cap fila té contrasenya: no hi ha res a enviar.")
        return 1

    if arg.prova:
        print(f"  PROVA: no s'ha enviat res.\n")
        print(f"  Rebrien el correu ({len(amb_clau)}):")
        for fila in amb_clau:
            # La contrasenya NO es mostra ni s'escriu enlloc: només viatja
            # dins del correu de la persona.
            print(f"    · {fila.get('usuari', '?'):16} {fila.get('correu', '')}")
        if sense_clau:
            print(f"\n  Se saltarien (sense contrasenya, {len(sense_clau)}):")
            for fila in sense_clau:
                print(f"    · {fila.get('usuari', '?'):16} "
                      f"{fila.get('correu', '')}")
        print(f"\n  Per enviar-ho de debò, repeteix-ho amb --confirma.")
        return 0

    cfg = carrega_smtp(arg.config)
    remitent = cfg.get("remitent") or cfg.get("usuari") or ""
    try:
        servidor = connecta_smtp(cfg)
    except Exception as e:                              # noqa: BLE001
        print(f"  No s'ha pogut connectar a l'SMTP: {type(e).__name__}: {e}")
        return 1

    enviats, fallits = [], []
    try:
        for fila in amb_clau:
            correu = fila.get("correu", "")
            if not correu:
                fallits.append((fila.get("usuari", "?"), "no té correu"))
                continue
            try:
                envia_un(servidor, remitent, fila)
                enviats.append(correu)
                print(f"    ✓ {correu}")
            except Exception as e:                      # noqa: BLE001
                # Fail-soft: que un correu rebotat no deixi la resta de la
                # plantilla sense credencials.
                fallits.append((correu, f"{type(e).__name__}: {e}"))
                print(f"    ✗ {correu}")
    finally:
        try:
            servidor.quit()
        except Exception:                               # noqa: BLE001
            pass

    print(f"\n  Enviats: {len(enviats)}")
    if fallits:
        print(f"  NO els han rebut ({len(fallits)}):")
        for qui, motiu in fallits:
            print(f"    · {qui}: {motiu}")
        print("  Torna-hi amb un fitxer que només tingui aquestes files.")
    if sense_clau:
        print(f"  Saltats per no tenir contrasenya: {len(sense_clau)}")
    print("\n  ⚠  Ja pots ESBORRAR el fitxer: conté contrasenyes en clar.")
    return 1 if fallits else 0


def construeix_analitzador() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Exporta els treballadors de nòmines cap al control "
                    "horari i els envia la contrasenya provisional.")
    ordres = ap.add_subparsers(dest="ordre", required=True)

    p = ordres.add_parser("prepara", help="genera el CSV per al control horari")
    p.add_argument("--xlsx", default=XLSX_DEFECTE,
                   help=f"full de treballadors de nòmines "
                        f"(defecte: {XLSX_DEFECTE})")
    p.add_argument("--sortida", default=None,
                   help="fitxer CSV a generar (defecte: "
                        "treballadors-AAAA-MM-DD.csv al directori actual)")
    p.set_defaults(func=prepara)

    e = ordres.add_parser("envia", help="envia les credencials provisionals")
    e.add_argument("--fitxer", required=True, help="el CSV ja revisat")
    e.add_argument("--config", default=CONFIG_DEFECTE,
                   help=f"config.ini amb l'SMTP (defecte: {CONFIG_DEFECTE})")
    e.add_argument("--prova", action="store_true",
                   help="diu a qui escriuria, sense enviar res")
    e.add_argument("--confirma", action="store_true",
                   help="envia els correus DE DEBÒ")
    e.set_defaults(func=envia)
    return ap


def main(argv=None) -> int:
    # La consola de Windows arrenca en cp1252 per defecte, que no te
    # els caracters "⚠", "✓" i "✗" que fan servir els avisos.
    # Sense aixo, l'eina peta DESPRES d'haver generat be el fitxer: el
    # CSV surt correcte pero el missatge final no arriba a sortir mai.
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    arg = construeix_analitzador().parse_args(argv)
    return arg.func(arg)


if __name__ == "__main__":
    sys.exit(main())
