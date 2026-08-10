"""
core/registre.py — Registre d'activitat.

Escriu a `logs/activitat.log` (rotatiu) i a la sortida estàndard. A Cloud Run
el disc és efímer, i és la sortida estàndard la que arriba a Cloud Logging:
per això s'escriu als dos llocs.

REGLA: aquí no hi entren MAI dades personals més enllà del login de qui fa
l'acció, ni secrets. «Qui, què, quan i des d'on», i prou.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

ARREL = Path(__file__).resolve().parents[1]
CARPETA = ARREL / "logs"
FITXER = CARPETA / "activitat.log"

# Accions previstes (DISSENY.md §4.5). No és una llista tancada per codi —una
# acció nova no ha de fer petar res— però sí el vocabulari acordat.
ACCIONS = (
    "LOGIN", "LOGIN_FALLIT", "LOGOUT", "FITXATGE", "CORRECCIO",
    "VALIDA_CORRECCIO", "ABSENCIA_SOL", "ABSENCIA_RESOL", "ABSENCIA_ANULA",
    "CONFIG", "ALTA_COMPTE", "CANVI_CONTRASENYA", "TOTP", "INFORME", "PURGA",
)

_registrador: logging.Logger | None = None


def _neteja(text) -> str:
    """Treu salts de línia i caràcters de control.

    Sense això, qui pugui escriure en un camp que acabi al registre pot
    fabricar-hi línies senceres i inventar-se entrades (injecció al log)."""
    if text is None:
        return ""
    net = "".join(c if c.isprintable() else " " for c in str(text))
    return net.replace("\r", " ").replace("\n", " ").strip()[:300]


def _obte() -> logging.Logger:
    global _registrador
    if _registrador is not None:
        return _registrador

    reg = logging.getLogger("control_horari.activitat")
    reg.setLevel(logging.INFO)
    reg.propagate = False
    format = logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(format)
    reg.addHandler(consola)

    # El fitxer és una comoditat en local; si no es pot escriure (contenidor
    # amb disc de només lectura), l'aplicació ha de continuar igualment.
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        fitxer = RotatingFileHandler(FITXER, maxBytes=1_000_000, backupCount=5,
                                     encoding="utf-8")
        fitxer.setFormatter(format)
        reg.addHandler(fitxer)
    except OSError:
        pass

    _registrador = reg
    return reg


def registra(accio: str, usuari: str = "", detall: str = "", ip: str = "") -> None:
    """Anota una acció. No llança mai: un error del registre no pot tombar
    una operació de l'usuari."""
    try:
        _obte().info("%s | %s | %s | %s", _neteja(accio), _neteja(usuari),
                     _neteja(ip), _neteja(detall))
    except Exception:      # noqa: BLE001 — deliberadament ampli
        pass
