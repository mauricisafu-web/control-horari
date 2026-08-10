"""
eines/dades_prova.py — Dades SINTÈTIQUES per poder provar i ensenyar l'app.

Cap nom, cap correu i cap dada real de l'ajuntament. Mai. Els noms són
òbviament inventats i els correus són d'un domini d'exemple, precisament
perquè ningú els pugui confondre amb els de debò.

    python eines/dades_prova.py                  # magatzem en memòria (mostra i surt)
    python eines/dades_prova.py --treballadors 8 --mesos 1

Per veure-les a l'aplicació, arrenca-la amb la sembra activada:

    DADES_PROVA=1 python app_web.py
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ARREL = Path(__file__).resolve().parents[1]
if str(ARREL) not in sys.path:
    sys.path.insert(0, str(ARREL))

from core.model import (                                          # noqa: E402
    AMBIT_TOTS, APROVADA, DENEGADA, ENTRADA, PAUSA_FI, PAUSA_INICI, PENDENT,
    ROL_ADMIN, ROL_RESPONSABLE, ROL_TREBALLADOR, SORTIDA, Tram, ZONA,
)
from magatzem import (                                            # noqa: E402
    absencies, comptes, festius, horaris, serveis as mag_serveis,
)
from magatzem.rebost import RebostMemoria, inicialitza               # noqa: E402

CONTRASENYA = "Prova-1234"
SERVEIS = ("Oficines", "Brigada", "SAIAR")

# Noms clarament inventats: ningú els pot confondre amb els de debò.
NOMS = ("Aina", "Bernat", "Carla", "Dídac", "Elena", "Ferran", "Gemma",
        "Hèctor", "Irene", "Jordi", "Laia", "Marc", "Núria", "Oriol",
        "Paula", "Quim", "Rosa", "Sergi", "Tània", "Ulisses", "Vera",
        "Xavier", "Íngrid", "Zoe")
COGNOMS = ("Prova", "Exemple", "Fictici", "Simulat", "Inventat", "Demo")


def _hash():
    from werkzeug.security import generate_password_hash
    return generate_password_hash(CONTRASENYA)


def pobla(mag, nombre_treballadors: int = 24, mesos: int = 3,
          llavor: int = 20260805) -> dict:
    """Deixa el magatzem amb un món coherent. Retorna un resum."""
    atzar = random.Random(llavor)      # reproduïble: les proves no ballen
    inicialitza(mag)
    avui = date.today()
    hash_comu = _hash()

    ids_servei = {nom: mag_serveis.crea(mag, nom) for nom in SERVEIS}

    # Dos patrons: el d'oficines i el de brigada (que entra abans).
    patro_oficines = horaris.desa_patro(
        mag, "Oficines", "De 8 a 15, de dilluns a divendres",
        [Tram(d, time(8, 0), time(15, 0)) for d in range(1, 6)])
    patro_brigada = horaris.desa_patro(
        mag, "Brigada", "De 7 a 14.30, de dilluns a divendres",
        [Tram(d, time(7, 0), time(14, 30)) for d in range(1, 6)])

    # Festius de l'any: uns quants de fixos, sense sortir a Internet.
    for dia, nom in ((date(avui.year, 1, 1), "Cap d'Any"),
                     (date(avui.year, 1, 6), "Reis"),
                     (date(avui.year, 6, 24), "Sant Joan"),
                     (date(avui.year, 8, 15), "l'Assumpció"),
                     (date(avui.year, 12, 25), "Nadal")):
        festius.afegeix(mag, dia, nom, "general")
    festius.afegeix(mag, date(avui.year, 9, 8), "Festa major", "local")
    festius_any = festius.del_any(mag, avui.year)

    # Comptes: un administrador, dos responsables i la resta, treballadors.
    plantilla = []
    for i in range(nombre_treballadors):
        login = f"prova{i + 1:02d}"
        nom = f"{NOMS[i % len(NOMS)]} {COGNOMS[i % len(COGNOMS)]}"
        servei = SERVEIS[i % len(SERVEIS)]
        if i == 0:
            rol, login = ROL_ADMIN, "admin01"
        elif i in (1, 2):
            rol, login = ROL_RESPONSABLE, f"resp{i:02d}"
        else:
            rol = ROL_TREBALLADOR
        alta = date(avui.year - 2, 1, 1) if i % 7 else date(avui.year, 5, 11)
        comptes.crea(mag, login, nom, f"{login}@exemple.cat", hash_comu, rol,
                     ids_servei[servei], alta)
        comptes.actualitza(mag, login, canvi_pendent=False)
        comptes.assigna(mag, login,
                        patro_brigada if servei == "Brigada" else patro_oficines,
                        alta)
        absencies.desa_saldo(mag, login, avui.year, "vacances", 22)
        absencies.desa_saldo(mag, login, avui.year, "assumptes_propis", 6)
        plantilla.append((login, ids_servei[servei], rol))

    comptes.desa_ambits(mag, "resp01", [ids_servei["Oficines"]])
    comptes.desa_ambits(mag, "resp02", [ids_servei["Brigada"], ids_servei["SAIAR"]])
    comptes.desa_ambits(mag, "admin01", [AMBIT_TOTS])

    # Absències en tots els estats.
    nombre_absencies = 0
    for i, (login, servei_id, _) in enumerate(plantilla[:8]):
        inici = avui + timedelta(days=10 + i * 3)
        while inici.weekday() >= 5:
            inici += timedelta(days=1)
        fi = inici + timedelta(days=4)
        codi = absencies.crea(mag, login, servei_id, "vacances", inici, fi, 5,
                              "Vacances d'estiu")
        if i % 3 == 1:
            absencies.resol(mag, codi, APROVADA, "resp01", "")
        elif i % 3 == 2:
            absencies.resol(mag, codi, DENEGADA, "resp01",
                            "Aquella setmana hi ha massa gent fora")
        nombre_absencies += 1

    # Marcatges dels últims mesos, amb variació realista.
    from magatzem import marcatges as mag_marcatges
    nombre_marcatges = 0
    # Fins AHIR, no fins avui: si es generessin els marcatges d'avui (amb la
    # sortida a les 15:00), qui obris la demostracio al mati es trobaria que
    # ja ha plegat i no podria fitxar res.
    dia = avui - timedelta(days=30 * mesos)
    while dia < avui:
        if dia.weekday() < 5 and dia not in festius_any:
            for login, servei_id, _ in plantilla:
                if atzar.random() < 0.06:
                    continue                        # algú que no hi és
                base = 7 if servei_id == ids_servei["Brigada"] else 8
                entrada = datetime.combine(
                    dia, time(base, atzar.choice([45, 50, 55, 0, 5, 10, 15, 20])),
                    tzinfo=ZONA) - timedelta(minutes=15)
                sortida = entrada + timedelta(hours=7,
                                              minutes=atzar.choice([-20, 0, 0, 15, 40]))

                def posa(tipus, moment):
                    nonlocal nombre_marcatges
                    mag_marcatges.afegeix(mag, login, tipus,
                                          moment.astimezone(timezone.utc),
                                          "web", login, servei_id=servei_id)
                    nombre_marcatges += 1

                posa(ENTRADA, entrada)
                if atzar.random() < 0.5:
                    pausa = entrada + timedelta(hours=3)
                    posa(PAUSA_INICI, pausa)
                    # Alguna pausa queda sense tancar: és el cas real que ha
                    # de fer saltar l'avís d'anomalia.
                    if atzar.random() > 0.05:
                        posa(PAUSA_FI, pausa + timedelta(minutes=20))
                # I alguna jornada queda oberta, per la mateixa raó.
                if atzar.random() > 0.04:
                    posa(SORTIDA, sortida)
        dia += timedelta(days=1)

    return {"treballadors": len(plantilla), "serveis": len(SERVEIS),
            "marcatges": nombre_marcatges, "absencies": nombre_absencies,
            "contrasenya": CONTRASENYA}


def main() -> None:
    analitzador = argparse.ArgumentParser(description=__doc__)
    analitzador.add_argument("--treballadors", type=int, default=24)
    analitzador.add_argument("--mesos", type=int, default=3)
    arguments = analitzador.parse_args()

    mag = RebostMemoria()
    resum = pobla(mag, arguments.treballadors, arguments.mesos)

    print("\n  Dades sintètiques generades (magatzem en memòria):")
    for clau in ("serveis", "treballadors", "marcatges", "absencies"):
        print(f"    {clau:14} {resum[clau]}")
    print(f"\n  Comptes: admin01 (administrador), resp01 i resp02 "
          f"(responsables), prova04… (treballadors)")
    print(f"  Contrasenya de tots: {resum['contrasenya']}")
    print("\n  Per veure-ho a l'aplicació:  DADES_PROVA=1 python app_web.py\n")


if __name__ == "__main__":
    main()
