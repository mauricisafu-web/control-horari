"""
core/push.py — Avisos push cap al mòbil, a través de la PWA.

Substitueix el correu com a via d'avís (vegeu `FLUX_PARITAT_PERSONAL.md`, B1):
l'ajuntament no vol que les credencials del seu servidor de correu surtin cap
al núvol, i un avís push no en necessita cap.

COM FUNCIONA, i per què això respecta el principi de no cedir dades:

    aplicació ──(missatge XIFRAT)──► servei de push del navegador ──► mòbil
                                     (Google, Apple o Mozilla)

El servei de push és del fabricant del navegador i no es pot triar. Ara bé,
el contingut viaja xifrat d'extrem a extrem (RFC 8291) amb unes claus que
només tenen l'aplicació i el dispositiu: el servei de push **no pot llegir el
missatge**. Veu que hi ha hagut un avís i cap a quin dispositiu, res més.

Tot i així, l'avís apareix a la pantalla de bloqueig, on el pot llegir qui
tingui el telèfon a la mà. Per això els textos d'aquí són GENÈRICS: diuen que
hi ha alguna cosa, mai qui ni quants dies. El detall es veu entrant.

REGLA: fail-soft, com el correu. Cap avís que falla no tomba mai l'operació
que l'ha provocat. Una sol·licitud desada sense avís és un problema petit;
una sol·licitud que no es desa perquè l'avís ha fallat, un de gros.
"""
from __future__ import annotations

import json
from typing import Sequence

from core.registre import registra

# Els avisos caduquen: si el mòbil ha estat apagat una setmana, rebre llavors
# «tens una sol·licitud per resoldre» no ajuda gens.
CADUCITAT = 60 * 60 * 24          # 24 hores, en segons


def hi_ha_push(config: dict) -> bool:
    """Si els avisos estan configurats. Sense claus VAPID, queden desactivats
    i s'anota, igual que passa amb el correu sense SMTP."""
    config = config or {}
    return bool(config.get("VAPID_PUBLIC") and config.get("VAPID_PRIVATE"))


def _envia_un(config: dict, subscripcio: dict, carrega: dict) -> tuple[bool, str]:
    """Un avís a un dispositiu.

    Retorna (enviat, motiu). Amb `motiu == "caducada"`, qui crida n'ha
    d'esborrar la subscripció: el dispositiu ja no hi és."""
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:                                # pragma: sense cobertura
        return False, "falta la biblioteca pywebpush"

    try:
        webpush(
            subscription_info={
                "endpoint": subscripcio["endpoint"],
                "keys": {"p256dh": subscripcio["p256dh"],
                         "auth": subscripcio["auth"]},
            },
            data=json.dumps(carrega, ensure_ascii=False),
            vapid_private_key=config["VAPID_PRIVATE"],
            vapid_claims={"sub": config.get("VAPID_SUBJECT")
                          or "mailto:secretaria@torredelespanyol.cat"},
            ttl=CADUCITAT,
            timeout=10,
        )
        return True, ""
    except WebPushException as e:
        # 404 i 410 volen dir que aquesta subscripció ja no existeix: el
        # navegador s'ha desinstal·lat o s'ha revocat el permís.
        codi = getattr(getattr(e, "response", None), "status_code", None)
        if codi in (404, 410):
            return False, "caducada"
        return False, f"{codi or 'error'}: {e}"
    except Exception as e:                             # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def envia(config: dict, subscripcions: Sequence[dict], titol: str, cos: str,
          ruta: str = "/", esborra=None) -> int:
    """Envia el mateix avís a un grup de dispositius. Retorna quants n'han
    sortit.

    `esborra` és una funció d'un argument (l'identificador de la subscripció)
    que es crida amb les que el servei de push ja no reconeix. Es passa des de
    fora perquè aquest mòdul no toqui mai el magatzem."""
    if not hi_ha_push(config):
        registra("PUSH_DESACTIVAT", detall=titol[:80])
        return 0

    carrega = {"titol": titol, "cos": cos, "ruta": ruta}
    enviats = 0
    for sub in subscripcions or ():
        ok, motiu = _envia_un(config, sub, carrega)
        if ok:
            enviats += 1
        elif motiu == "caducada" and esborra is not None:
            esborra(sub.get("id", ""))
        elif motiu:
            registra("PUSH_FALLIT", detall=motiu[:120])
    return enviats


# --------------------------------------------------------------------------
# Els avisos concrets. Text GENÈRIC: es llegeixen a la pantalla de bloqueig.
# --------------------------------------------------------------------------
def avisa_nova_solicitud(config, subscripcions, esborra=None) -> int:
    """Als aprovadors del servei: tens feina."""
    return envia(
        config, subscripcions,
        "Sol·licitud pendent",
        "Tens una sol·licitud d'absència per resoldre.",
        ruta="/gestio", esborra=esborra)


def avisa_resolucio(config, subscripcions, aprovada: bool,
                    esborra=None) -> int:
    """Al treballador: ja està resolta.

    Aquí sí que es diu si ha anat bé o malament —és el que la persona vol
    saber i no revela ni dates ni dies a ningú altre— però no s'hi posa mai
    ni el codi ni el període."""
    return envia(
        config, subscripcions,
        "Vacances aprovades" if aprovada else "Sol·licitud denegada",
        "Ja tens resposta a la teva sol·licitud." if aprovada
        else "La teva sol·licitud no s'ha acceptat. Entra-hi per veure'n el motiu.",
        ruta="/absencies", esborra=esborra)


def avisa_anulacio(config, subscripcions, esborra=None) -> int:
    """Al treballador, quan un responsable li anul·la una absència aprovada."""
    return envia(
        config, subscripcions,
        "Absència anul·lada",
        "T'han anul·lat una absència que tenies aprovada.",
        ruta="/absencies", esborra=esborra)
