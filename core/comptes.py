"""
core/comptes.py — Contrasenyes i tokens.

Funcions pures de criptografia i validació. No toquen el magatzem.
"""
from __future__ import annotations

import secrets
import string

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from core.model import ErrorHorari

LLARGADA_MINIMA = 10
LLARGADA_PROVISIONAL = 14

# Sense caràcters que es confonen en llegir-los d'un paper o d'un correu:
# ni O ni 0, ni l ni 1 ni I. Una contrasenya provisional es tecleja a mà.
ALFABET = "".join(c for c in string.ascii_letters + string.digits
                  if c not in "O0lI1")


def hash_contrasenya(text: str) -> str:
    return generate_password_hash(text)


def verifica(hash: str | None, text: str) -> bool:
    if not hash or not text:
        return False
    try:
        return check_password_hash(hash, text)
    except (ValueError, TypeError):
        return False


def contrasenya_provisional() -> str:
    return "".join(secrets.choice(ALFABET) for _ in range(LLARGADA_PROVISIONAL))


def valida_politica(text: str, provisional: str | None = None) -> None:
    """Mínim de llargada i prou.

    Res de regles barroques de símbols obligatoris: fan que la gent acabi
    escrivint la contrasenya en un post-it enganxat a la pantalla, que és
    pitjor que qualsevol contrasenya feble."""
    text = text or ""
    if len(text) < LLARGADA_MINIMA:
        raise ErrorHorari(
            f"La contrasenya ha de tenir com a mínim {LLARGADA_MINIMA} "
            f"caràcters.")
    if text.strip() != text:
        raise ErrorHorari("La contrasenya no pot començar ni acabar amb espais.")
    if provisional and text == provisional:
        raise ErrorHorari(
            "Has de triar una contrasenya diferent de la provisional que has "
            "rebut: aquella ha viatjat per correu i no és segura.")


def token_recuperacio(login: str, secret: str) -> str:
    return URLSafeTimedSerializer(secret, salt="recuperacio").dumps(login)


def obre_token(token: str, secret: str, max_edat: int = 1800) -> str | None:
    """El login del token, o None si és caducat, manipulat o inventat."""
    try:
        return URLSafeTimedSerializer(secret, salt="recuperacio").loads(
            token, max_age=max_edat)
    except (SignatureExpired, BadSignature, TypeError):
        return None
