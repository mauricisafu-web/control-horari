"""
core/totp.py — Verificació en dos passos (TOTP, RFC 6238).

100 % local: el codi el genera l'aplicació del mòbil del treballador
(Google Authenticator, FreeOTP, Aegis…) i el verifica el servidor. No hi ha
cap servei extern pel mig i no s'envia cap SMS.

Obligatori per a administradors i responsables: són els comptes que veuen
dades d'altres persones.
"""
from __future__ import annotations

import secrets

import pyotp
import qrcode
import qrcode.image.svg
from werkzeug.security import check_password_hash, generate_password_hash

from core.model import ErrorHorari

EMISSOR = "Control horari"
NOMBRE_CODIS = 8

# Els rellotges dels mòbils van una mica desviats. Amb finestra 0, la meitat
# de la plantilla no podria entrar; amb 1, s'accepten els 30 segons anteriors
# i els posteriors, que és el compromís habitual.
FINESTRA = 1


def genera_secret() -> str:
    return pyotp.random_base32()


def uri(secret: str, login: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=login, issuer_name=EMISSOR)


def qr_svg(secret: str, login: str) -> str:
    """El QR en SVG generat AL SERVIDOR.

    Mai una imatge d'un servei extern: seria enviar el secret del segon
    factor a un tercer, i a més la política de continguts ho bloquejaria."""
    imatge = qrcode.make(uri(secret, login),
                         image_factory=qrcode.image.svg.SvgPathImage)
    from io import BytesIO
    memoria = BytesIO()
    imatge.save(memoria)
    return memoria.getvalue().decode("utf-8")


def verifica(secret: str | None, codi: str) -> bool:
    if not secret or not codi:
        return False
    net = "".join(c for c in str(codi) if c.isdigit())
    if len(net) != 6:
        return False
    try:
        return pyotp.TOTP(secret).verify(net, valid_window=FINESTRA)
    except Exception:      # noqa: BLE001 — un secret corrupte no ha de petar
        return False


# -- codis de recuperació ---------------------------------------------------
def genera_codis_recuperacio(nombre: int = NOMBRE_CODIS) -> list[str]:
    """En clar, per ensenyar-los UNA sola vegada. El que es desa és el hash."""
    return [f"{secrets.randbelow(10**5):05d}-{secrets.randbelow(10**5):05d}"
            for _ in range(nombre)]


def a_desar(codis: list[str]) -> list[dict]:
    return [{"hash": generate_password_hash(c), "usat_el": None} for c in codis]


def consumeix_codi(desats: list[dict], codi: str) -> tuple[bool, list[dict]]:
    """(ha valgut, llista actualitzada). Cada codi serveix UNA vegada."""
    net = (codi or "").strip()
    if not net:
        return False, desats
    actualitzats = [dict(c) for c in desats]
    for entrada in actualitzats:
        if entrada.get("usat_el"):
            continue
        try:
            if check_password_hash(entrada.get("hash", ""), net):
                from core.model import ara_utc
                entrada["usat_el"] = ara_utc().isoformat()
                return True, actualitzats
        except (ValueError, TypeError):
            continue
    return False, desats


def queden(desats: list[dict]) -> int:
    return sum(1 for c in desats or () if not c.get("usat_el"))
