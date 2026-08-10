"""
core/notifica.py — Avisos per correu.

REGLA: **fail-soft**. Cap flux de dades es bloqueja mai perquè l'SMTP falli.
Primer es desa, després s'intenta el correu; si no surt, es retorna False,
s'anota al registre i qui ha cridat ensenya un avís.

Sense `SMTP_HOST` configurat, els avisos queden desactivats i s'anota. NO és
un error: és el cas normal en desenvolupament i durant el pilot.

Els cossos són curts i sense dades de més: qui, quin tipus d'absència i
quines dates. Res de saldos ni de motius. Que el correu no sigui, ell
mateix, una filtració.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Sequence

from core.registre import registra

ESPERA = 10      # segons; sense això, un servidor mut penja la petició web


def hi_ha_correu(config: dict) -> bool:
    return bool((config or {}).get("SMTP_HOST"))


def envia(config: dict, desti: str | Sequence[str], assumpte: str,
          cos: str) -> bool:
    """True si ha sortit. MAI llança."""
    destinataris = [desti] if isinstance(desti, str) else list(desti or ())
    destinataris = [d for d in destinataris if d]
    if not destinataris:
        return False
    if not hi_ha_correu(config):
        registra("CORREU_DESACTIVAT", detall=assumpte[:80])
        return False

    try:
        missatge = EmailMessage()
        missatge["Subject"] = assumpte
        missatge["From"] = (config.get("SMTP_REMITENT")
                            or config.get("SMTP_USUARI") or "no-reply@localhost")
        missatge["To"] = ", ".join(destinataris)
        missatge.set_content(cos)

        port = int(config.get("SMTP_PORT") or 587)
        if port == 465:
            servidor = smtplib.SMTP_SSL(config["SMTP_HOST"], port, timeout=ESPERA)
        else:
            servidor = smtplib.SMTP(config["SMTP_HOST"], port, timeout=ESPERA)
        with servidor:
            if port != 465 and config.get("SMTP_TLS", True):
                servidor.starttls()
            if config.get("SMTP_USUARI"):
                servidor.login(config["SMTP_USUARI"], config.get("SMTP_PASSWORD", ""))
            servidor.send_message(missatge)
        return True
    except Exception as e:      # noqa: BLE001 — deliberadament ampli
        # Un `except` que se'l menja tot i calla és pitjor que l'error: com a
        # mínim, ha de quedar constància de què ha passat.
        registra("CORREU_FALLIT", detall=f"{type(e).__name__}: {e}"[:180])
        return False


def _dates(absencia) -> str:
    return (f"{absencia.data_inici.strftime('%d/%m/%Y')} a "
            f"{absencia.data_fi.strftime('%d/%m/%Y')}")


def avisa_nova_solicitud(config, absencia, treballador,
                         correus_aprovadors: Sequence[str]) -> bool:
    return envia(
        config, correus_aprovadors,
        f"Sol·licitud d'absència: {treballador.nom}",
        f"{treballador.nom} ha demanat {absencia.dies} dies "
        f"({_dates(absencia)}).\n\n"
        f"Referència: {absencia.codi}\n\n"
        f"Entra a l'aplicació de control horari per resoldre-la.\n")


def avisa_resolucio(config, absencia, treballador) -> bool:
    estat = "aprovada" if absencia.estat == "APROVADA" else "denegada"
    motiu = (f"\nMotiu: {absencia.motiu_resolucio}\n"
             if absencia.motiu_resolucio else "")
    return envia(
        config, treballador.correu,
        f"La teva sol·licitud d'absència ha estat {estat}",
        f"Hola, {treballador.nom}.\n\n"
        f"La sol·licitud {absencia.codi} ({_dates(absencia)}) ha estat "
        f"{estat}.\n{motiu}\n"
        f"Pots consultar-ho a l'aplicació de control horari.\n")


def avisa_correccio_pendent(config, treballador,
                            correus_responsables: Sequence[str]) -> bool:
    return envia(
        config, correus_responsables,
        f"Correcció de fitxatge per validar: {treballador.nom}",
        f"{treballador.nom} ha demanat una correcció al seu registre de "
        f"jornada.\n\nEntra a l'aplicació per validar-la o rebutjar-la.\n")


def envia_provisional(config, treballador, contrasenya: str) -> bool:
    """Excepció al fail-soft: si això no arriba, el compte no serveix de res.
    Retorna False honestament i que decideixi qui l'ha cridat."""
    return envia(
        config, treballador.correu,
        "El teu compte del control horari",
        f"Hola, {treballador.nom}.\n\n"
        f"Ja tens compte a l'aplicació de control horari de l'ajuntament.\n\n"
        f"  Usuari: {treballador.login}\n"
        f"  Contrasenya provisional: {contrasenya}\n\n"
        f"La primera vegada que entris t'obligarà a canviar-la. Fes-ho de "
        f"seguida: aquesta contrasenya ha viatjat per correu i el correu no "
        f"és un canal segur.\n")


def envia_recuperacio(config, treballador, enllac: str) -> bool:
    return envia(
        config, treballador.correu,
        "Recupera la contrasenya del control horari",
        f"Hola, {treballador.nom}.\n\n"
        f"Per posar una contrasenya nova, obre aquest enllaç:\n\n{enllac}\n\n"
        f"Caduca d'aquí a mitja hora. Si no has demanat res, ignora aquest "
        f"correu: no cal que facis res més.\n")
