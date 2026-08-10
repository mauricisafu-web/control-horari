"""
web/pwa.py — El que fa que l'aplicació sigui instal·lable al mòbil.

Cap d'aquestes rutes exigeix sessió: el navegador demana el manifest i el
service worker ABANS que ningú hagi entrat.
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, send_from_directory

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
