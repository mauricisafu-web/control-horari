"""
web/pwa.py — El que fa que l'aplicació sigui instal·lable al mòbil, i les
subscripcions als avisos push.

El manifest i el service worker NO exigeixen sessió: el navegador els demana
abans que ningú hagi entrat. Les rutes de subscripció, en canvi, sí: una
subscripció va lligada a una persona.
"""
from __future__ import annotations

from flask import (
    Blueprint, current_app, g, jsonify, render_template, request,
    send_from_directory,
)
from flask_login import current_user, login_required

from core.registre import registra
from magatzem import subscripcions as mag_subs

pwa = Blueprint("pwa", __name__)


@pwa.route("/manifest.webmanifest")
def manifest():
    resposta = send_from_directory(current_app.static_folder, "manifest.webmanifest")
    resposta.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
    return resposta


@pwa.route("/sw.js")
def sw():
    """Servit des de l'ARREL a propòsit: l'abast d'un service worker no pot
    ser més ampli que el seu propi camí. Des de `/static/` només controlaria
    `/static/*` i l'aplicació no seria instal·lable."""
    resposta = send_from_directory(current_app.static_folder, "sw.js")
    resposta.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resposta.headers["Service-Worker-Allowed"] = "/"
    return resposta


@pwa.route("/instal-lacio")
def instal_lacio():
    return render_template("pwa/instal_lacio.html")


# --------------------------------------------------------------------------
# Avisos push
# --------------------------------------------------------------------------
@pwa.route("/push/clau")
@login_required
def clau():
    """La clau pública VAPID, que el navegador necessita per subscriure's.

    És PÚBLICA per disseny (va dins de cada petició al servei de push); l'únic
    secret és la privada, que no surt mai del servidor. Amb `activat: false`,
    el navegador ni tan sols demana permís: val més no demanar res que
    demanar-ho i després no enviar mai res."""
    config = current_app.config["APP"]
    return jsonify({"activat": bool(config.get("VAPID_PUBLIC")),
                    "clau": config.get("VAPID_PUBLIC", "")})


@pwa.route("/push/subscriu", methods=["POST"])
@login_required
def subscriu():
    dades = request.get_json(silent=True) or {}
    endpoint = str(dades.get("endpoint") or "")
    claus = dades.get("keys") or {}
    p256dh, auth = str(claus.get("p256dh") or ""), str(claus.get("auth") or "")

    if not endpoint or not p256dh or not auth:
        return jsonify({"ok": False, "motiu": "subscripció incompleta"}), 400

    mag_subs.desa(g.mag, current_user.get_id(), endpoint, p256dh, auth)
    registra("PUSH_ALTA", current_user.get_id(), ip=request.remote_addr or "")
    return jsonify({"ok": True})


@pwa.route("/push/baixa", methods=["POST"])
@login_required
def baixa():
    """Quan algú desactiva els avisos des del seu dispositiu."""
    dades = request.get_json(silent=True) or {}
    endpoint = str(dades.get("endpoint") or "")
    if endpoint:
        mag_subs.esborra_per_endpoint(g.mag, endpoint)
    else:
        mag_subs.esborra_de(g.mag, current_user.get_id())
    registra("PUSH_BAIXA", current_user.get_id(), ip=request.remote_addr or "")
    return jsonify({"ok": True})
