"""
eines/claus_push.py — Genera el parell de claus VAPID dels avisos push.

S'executa UNA sola vegada per instal·lació. La clau pública viatja al
navegador de cada persona (és pública per disseny); la privada NO ha de sortir
mai del servidor ni entrar mai al repositori.

    python eines/claus_push.py

Si es canvien les claus, TOTES les subscripcions existents deixen de valer i
tothom ha de tornar a activar els avisos. No es fa a la lleugera.
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(dades: bytes) -> str:
    """base64url sense farciment, que és el que demana la RFC 8292."""
    return base64.urlsafe_b64encode(dades).rstrip(b"=").decode("ascii")


def genera() -> tuple[str, str]:
    """(pública, privada), totes dues en base64url."""
    clau = ec.generate_private_key(ec.SECP256R1())
    publica = clau.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint)
    privada = clau.private_numbers().private_value.to_bytes(32, "big")
    return _b64(publica), _b64(privada)


def main() -> int:
    publica, privada = genera()
    print("Claus VAPID generades.\n")
    print(f"  VAPID_PUBLIC={publica}")
    print(f"  VAPID_PRIVATE={privada}")
    print("\nLa PÚBLICA pot anar on sigui: el navegador de cada persona ja la rep.")
    print("La PRIVADA va a Secret Manager i enlloc més:\n")
    print("  gcloud secrets create control-horari-vapid --replication-policy=automatic")
    print("  printf '%s' 'LA-PRIVADA' | gcloud secrets versions add "
          "control-horari-vapid --data-file=-")
    print("\nI al servei:")
    print("  gcloud run services update control-horari --region=europe-west1 \\")
    print("    --set-env-vars VAPID_PUBLIC=LA-PUBLICA \\")
    print("    --update-secrets VAPID_PRIVATE=control-horari-vapid:latest")
    print("\nSi mai les canvies, tothom haurà de tornar a activar els avisos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
