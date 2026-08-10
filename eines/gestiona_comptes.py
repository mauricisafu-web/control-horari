"""
eines/gestiona_comptes.py — Gestió de comptes des de la consola.

Serveix per crear el PRIMER administrador, quan encara no es pot entrar a
l'aplicació, i per als casos en què cal tocar un compte sense navegador.

    python eines/gestiona_comptes.py llista
    python eines/gestiona_comptes.py afegeix --login secretari --nom "..." \
        --correu "..." --rol admin
    python eines/gestiona_comptes.py rol --login x --rol responsable
    python eines/gestiona_comptes.py contrasenya --login x
    python eines/gestiona_comptes.py totp-reset --login x
    python eines/gestiona_comptes.py desactiva --login x --confirma

Contra PRODUCCIÓ cal dir-ho explícitament:

    REBOST=firestore PROJECTE_FIREBASE=... python eines/gestiona_comptes.py llista

Les ordres que canvien coses exigeixen `--confirma`: és el patró de dos
passos que ha evitat més d'un ensurt en aquest projecte.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ARREL = Path(__file__).resolve().parents[1]
if str(ARREL) not in sys.path:
    sys.path.insert(0, str(ARREL))

from core import comptes as regles                                # noqa: E402
from core.model import ErrorHorari, ETIQUETA_ROL, ROLS            # noqa: E402
from magatzem import comptes, serveis                             # noqa: E402
from magatzem.rebost import inicialitza, obre_rebost              # noqa: E402


def _magatzem():
    mag = obre_rebost()
    inicialitza(mag)
    mena = mag.__class__.__name__
    if mena == "RebostFirestore":
        print("  ⚠  Estàs treballant contra PRODUCCIÓ (Firestore).\n")
    return mag


def llista(mag, arg) -> None:
    noms = serveis.noms(mag)
    plantilla = comptes.llista(mag, actius=False)
    if not plantilla:
        print("  (encara no hi ha cap compte)")
        return
    print(f"  {'usuari':14} {'nom':26} {'rol':14} {'servei':12} estat")
    for t in plantilla:
        estat = "actiu" if t.actiu else "de baixa"
        print(f"  {t.login:14} {t.nom[:26]:26} "
              f"{ETIQUETA_ROL.get(t.rol, t.rol):14} "
              f"{(noms.get(t.servei_id) or '—')[:12]:12} {estat}")


def afegeix(mag, arg) -> None:
    if not arg.confirma:
        print(f"  Es crearia el compte «{arg.login}» ({arg.rol}).")
        print("  Torna-ho a executar amb --confirma per fer-ho de debò.")
        return
    provisional = regles.contrasenya_provisional()
    comptes.crea(mag, arg.login, arg.nom, arg.correu,
                 regles.hash_contrasenya(provisional), arg.rol)
    print(f"  Compte «{arg.login}» creat.")
    print(f"  Contrasenya provisional: {provisional}")
    print("  NO es tornarà a mostrar. Fes-la arribar per un canal segur; "
          "la primera vegada que entri, l'aplicació l'obligarà a canviar-la.")


def rol(mag, arg) -> None:
    if arg.rol not in ROLS:
        raise ErrorHorari(f"El rol ha de ser un de {ROLS}.")
    if not arg.confirma:
        print(f"  {arg.login} passaria a ser {arg.rol}. Falta --confirma.")
        return
    comptes.actualitza(mag, arg.login, rol=arg.rol)
    print(f"  {arg.login} ara és {ETIQUETA_ROL[arg.rol]}.")


def contrasenya(mag, arg) -> None:
    if not arg.confirma:
        print(f"  Es generaria una contrasenya nova per a {arg.login}. "
              f"Falta --confirma.")
        return
    provisional = regles.contrasenya_provisional()
    comptes.actualitza(mag, arg.login,
                       hash_contrasenya=regles.hash_contrasenya(provisional),
                       canvi_pendent=True)
    print(f"  Contrasenya provisional de {arg.login}: {provisional}")


def totp_reset(mag, arg) -> None:
    if not arg.confirma:
        print(f"  Es reiniciaria el segon factor de {arg.login}. Falta --confirma.")
        return
    comptes.actualitza(mag, arg.login, totp_actiu=False, totp_secret=None,
                       codis_recuperacio=[])
    print(f"  {arg.login} haurà de tornar a activar la verificació en dos passos.")


def desactiva(mag, arg) -> None:
    if not arg.confirma:
        print(f"  Es donaria de baixa {arg.login}. Falta --confirma.")
        return
    from datetime import date
    comptes.desactiva(mag, arg.login, date.today())
    print(f"  {arg.login} donat de baixa. El compte NO s'esborra: el registre "
          f"de jornada s'ha de conservar quatre anys.")


ORDRES = {"llista": llista, "afegeix": afegeix, "rol": rol,
          "contrasenya": contrasenya, "totp-reset": totp_reset,
          "desactiva": desactiva}


def main() -> None:
    analitzador = argparse.ArgumentParser(description=__doc__)
    analitzador.add_argument("ordre", choices=sorted(ORDRES))
    analitzador.add_argument("--login")
    analitzador.add_argument("--nom", default="")
    analitzador.add_argument("--correu", default="")
    analitzador.add_argument("--rol", default="treballador")
    analitzador.add_argument("--confirma", action="store_true")
    arg = analitzador.parse_args()

    if arg.ordre != "llista" and not arg.login:
        analitzador.error("aquesta ordre necessita --login")

    try:
        ORDRES[arg.ordre](_magatzem(), arg)
    except ErrorHorari as e:
        print(f"  Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
