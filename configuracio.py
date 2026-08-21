"""
configuracio.py — Lectura de la configuració de l'entorn.

Un sol lloc que llegeix les variables de DISSENY.md §9, les converteix al
tipus correcte i hi posa els valors per defecte. Ningú més crida `os.environ`.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ARREL = Path(__file__).resolve().parent
FITXER_CLAU = ARREL / ".secret_key"


def _bool(nom: str, defecte: bool = False) -> bool:
    valor = os.environ.get(nom)
    if valor is None:
        return defecte
    return valor.strip().lower() in ("1", "si", "sí", "true", "yes", "on")


def _enter(nom: str, defecte: int) -> int:
    try:
        return int(os.environ.get(nom, defecte))
    except (TypeError, ValueError):
        return defecte


def secret_key() -> str:
    """La clau de signatura de sessions.

    De l'entorn; si no hi és, del fitxer `.secret_key`; si tampoc, se'n genera
    una i es desa. MAI una clau fixa al codi: amb una clau coneguda, qualsevol
    es pot fabricar una cookie de sessió d'administrador."""
    de_entorn = os.environ.get("SECRET_KEY")
    if de_entorn:
        return de_entorn
    if FITXER_CLAU.exists():
        clau = FITXER_CLAU.read_text(encoding="utf-8").strip()
        if clau:
            return clau
    clau = secrets.token_hex(32)
    FITXER_CLAU.write_text(clau, encoding="utf-8")
    try:
        FITXER_CLAU.chmod(0o600)      # efectiu a Linux; a Windows s'ignora
    except OSError:
        pass
    return clau


def carrega() -> dict:
    """Tota la configuració de l'aplicació, ja convertida."""
    return {
        # Magatzem. El defecte és memòria A PROPÒSIT: cap prova ni cap sessió
        # de desenvolupament pot tocar dades de producció per descuit.
        "REBOST": os.environ.get("REBOST", "memoria").strip().lower(),
        "PROJECTE_FIREBASE": os.environ.get("PROJECTE_FIREBASE", ""),

        "SECRET_KEY": secret_key(),
        "COOKIE_SECURE": _bool("COOKIE_SECURE", False),
        "DARRERE_PROXY": _bool("DARRERE_PROXY", False),
        "DOMINI_PUBLIC": os.environ.get("DOMINI_PUBLIC", "").strip(),
        "SESSIO_MINUTS": _enter("SESSIO_MINUTS", 20),
        "FLASK_DEBUG": _bool("FLASK_DEBUG", False),
        "PURGA_AUTOMATICA": _bool("PURGA_AUTOMATICA", False),
        "REGISTRE_OBERT": _bool("REGISTRE_OBERT", False),
        # Omple el magatzem amb dades SINTETIQUES en arrencar. Nomes per a
        # demostracions i desenvolupament: mai a produccio.
        "DADES_PROVA": _bool("DADES_PROVA", False),

        # Correu. Sense SMTP_HOST, les notificacions queden desactivades i
        # s'anota al registre: NO és un error, és el cas normal en local.
        "SMTP_HOST": os.environ.get("SMTP_HOST", ""),
        "SMTP_PORT": _enter("SMTP_PORT", 587),
        "SMTP_USUARI": os.environ.get("SMTP_USUARI", ""),
        "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
        "SMTP_TLS": _bool("SMTP_TLS", True),
        "SMTP_REMITENT": os.environ.get("SMTP_REMITENT", ""),

        # Avisos push cap al mòbil (RFC 8292). Sense claus, queden
        # desactivats i s'anota, igual que el correu sense SMTP_HOST.
        # Es generen UNA vegada amb `python eines/claus_push.py` i la
        # privada va a Secret Manager, mai al repositori.
        "VAPID_PUBLIC": os.environ.get("VAPID_PUBLIC", "").strip(),
        "VAPID_PRIVATE": os.environ.get("VAPID_PRIVATE", "").strip(),
        "VAPID_SUBJECT": os.environ.get(
            "VAPID_SUBJECT", "mailto:secretaria@torredelespanyol.cat"),

        "PORT": _enter("PORT", 5004),
    }
