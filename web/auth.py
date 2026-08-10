"""web/auth.py — Esquelet d'autenticació. L'omple l'onada 2."""
from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import LoginManager

auth = Blueprint("auth", __name__)

gestor_login = LoginManager()
gestor_login.login_view = "auth.login"
gestor_login.login_message = "Cal que entris per veure aquesta pàgina."
gestor_login.login_message_category = "avis"


@gestor_login.user_loader
def carrega_usuari(login):
    return None


@auth.route("/login", methods=["GET", "POST"])
def login():
    return render_template("en_construccio.html", modul="Entrada")


@auth.route("/logout")
def logout():
    return render_template("en_construccio.html", modul="Sortida")


@auth.route("/canvia-contrasenya", methods=["GET", "POST"])
def canvia_contrasenya():
    return render_template("en_construccio.html", modul="Canvi de contrasenya")


@auth.route("/recupera", methods=["GET", "POST"])
def recupera():
    return render_template("en_construccio.html", modul="Recuperació")


@auth.route("/totp")
def totp():
    return render_template("en_construccio.html", modul="Verificació en dos passos")


@auth.route("/avis-legal")
def avis_legal():
    """Pública SEMPRE: és la informació de l'article 13 del RGPD i s'ha de
    poder llegir abans d'entrar-hi."""
    return render_template("avis_legal.html")
