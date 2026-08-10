"""
web/auth.py — Entrada, contrasenyes i verificació en dos passos.

Punts que aquí s'han de fer bé o no serveix de res la resta:

· El missatge d'error del login és SEMPRE el mateix, existeixi el compte o no:
  si no, la pàgina et diu qui té compte a l'ajuntament.
· Sessió nova en entrar (anti-fixació).
· Amb el segon factor actiu, `login_user` NO es fa fins que el codi és
  correcte. Fer-lo abans buidaria de sentit tot el 2FA.
· El `next` de la redirecció només accepta rutes internes.
"""
from __future__ import annotations

import time
from datetime import timedelta

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request,
    session, url_for,
)
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user,
    logout_user,
)

from core import comptes as regles_comptes, notifica, totp as regles_totp
from core.model import ErrorHorari, ROL_ADMIN, ROL_RESPONSABLE, ara_utc
from core.registre import registra
from magatzem import activitat, comptes

auth = Blueprint("auth", __name__)

gestor_login = LoginManager()
gestor_login.login_view = "auth.login"
gestor_login.login_message = "Cal que entris per veure aquesta pàgina."
gestor_login.login_message_category = "avis"

# Límit d'intents per IP. En memòria: l'aplicació corre amb un sol worker i
# amb 24 treballadors no cal res més sofisticat.
#
# El comptador viu a `app.extensions`, no en una variable de mòdul: una
# variable global la compartirien totes les instàncies del procés, i llavors
# el bloqueig d'una es propagaria a les altres.
MAXIM_INTENTS = 8
FINESTRA_INTENTS = 900          # 15 minuts
MINUTS_SEGON_FACTOR = 5

# Rutes on es pot anar encara que el compte estigui confinat.
LLIURES = {"auth.logout", "auth.canvia_contrasenya", "auth.avis_legal",
           "auth.totp", "auth.totp_confirma", "static",
           "pwa.manifest", "pwa.sw", "pwa.instal_lacio"}


class Usuari(UserMixin):
    """Embolcall de `core.model.Treballador` per a Flask-Login."""

    def __init__(self, treballador):
        self.treballador = treballador

    def get_id(self):
        return self.treballador.login

    def __getattr__(self, nom):
        return getattr(self.treballador, nom)


@gestor_login.user_loader
def carrega_usuari(login):
    treballador = comptes.per_login(g.mag, login)
    if treballador is None or not treballador.actiu:
        return None
    return Usuari(treballador)


# -- confinaments -----------------------------------------------------------
@auth.before_app_request
def _confina():
    """Qui té la contrasenya provisional o li falta el segon factor no pot
    anar enlloc més fins que ho arregli."""
    if not current_user.is_authenticated:
        return None
    if request.endpoint in LLIURES or (request.endpoint or "").startswith("static"):
        return None

    doc = comptes.document(g.mag, current_user.get_id()) or {}
    if doc.get("canvi_pendent"):
        flash("Abans de res, has de canviar la contrasenya provisional.", "avis")
        return redirect(url_for("auth.canvia_contrasenya"))

    # El segon factor és obligatori per als comptes que veuen dades d'altres.
    if current_user.rol in (ROL_ADMIN, ROL_RESPONSABLE) and not doc.get("totp_actiu"):
        flash("El teu rol necessita la verificació en dos passos. "
              "Activa-la per continuar.", "avis")
        return redirect(url_for("auth.totp"))
    return None


# -- entrada ----------------------------------------------------------------
def _comptador() -> dict:
    return current_app.extensions.setdefault("intents_login", {})


def _massa_intents(ip: str) -> bool:
    comptador = _comptador()
    ara = time.time()
    intents = [t for t in comptador.get(ip, []) if ara - t < FINESTRA_INTENTS]
    comptador[ip] = intents
    if len(comptador) > 500:      # poda: la memòria no pot créixer sense fre
        for clau in [k for k, v in comptador.items()
                     if not v or ara - max(v) > FINESTRA_INTENTS]:
            comptador.pop(clau, None)
    return len(intents) >= MAXIM_INTENTS


def _apunta_intent(ip: str) -> None:
    _comptador().setdefault(ip, []).append(time.time())


def _desti_segur(desti: str | None) -> str:
    """Només rutes internes. Rebutja `//`, els URL absoluts i tot el que
    porti host: és l'open redirect clàssic."""
    if not desti or not desti.startswith("/") or desti.startswith("//"):
        return url_for("fitxatge.inici")
    return desti


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("fitxatge.inici"))

    if request.method == "POST":
        ip = request.remote_addr or "?"
        usuari = (request.form.get("usuari") or "").strip().lower()

        if _massa_intents(ip):
            registra("LOGIN_FALLIT", usuari, "massa intents", ip)
            flash("Hi ha hagut massa intents fallits. Espera uns minuts.", "error")
            return render_template("auth/login.html"), 429

        hash = comptes.hash_de(g.mag, usuari)
        treballador = comptes.per_login(g.mag, usuari)
        correcte = regles_comptes.verifica(hash, request.form.get("contrasenya", ""))

        if not correcte or treballador is None or not treballador.actiu:
            _apunta_intent(ip)
            registra("LOGIN_FALLIT", usuari, "", ip)
            # El MATEIX missatge tant si el compte no existeix com si la
            # contrasenya és dolenta.
            flash("L'usuari o la contrasenya no són correctes.", "error")
            return render_template("auth/login.html"), 401

        doc = comptes.document(g.mag, usuari) or {}
        if doc.get("totp_actiu"):
            # Encara NO entra: primer el segon factor.
            session.clear()
            session["pendent_totp"] = usuari
            session["pendent_des_de"] = time.time()
            session["pendent_desti"] = request.form.get("next") or ""
            return redirect(url_for("auth.login_totp"))

        session.clear()                       # sessió nova: anti-fixació
        login_user(Usuari(treballador))
        comptes.actualitza(g.mag, usuari, ultim_acces=ara_utc().isoformat())
        registra("LOGIN", usuari, "", ip)
        activitat.registra(g.mag, "LOGIN", usuari, "", ip)
        return redirect(_desti_segur(request.form.get("next")))

    return render_template("auth/login.html")


@auth.route("/login/totp", methods=["GET", "POST"])
def login_totp():
    login_pendent = session.get("pendent_totp")
    des_de = session.get("pendent_des_de", 0)
    if not login_pendent or time.time() - des_de > MINUTS_SEGON_FACTOR * 60:
        session.pop("pendent_totp", None)
        flash("Has trigat massa. Torna a entrar-hi.", "avis")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        ip = request.remote_addr or "?"
        doc = comptes.document(g.mag, login_pendent) or {}
        codi = request.form.get("codi", "")

        valid = regles_totp.verifica(doc.get("totp_secret"), codi)
        if not valid:
            # Si no és un codi de l'aplicació, potser és un de recuperació.
            ha_valgut, actualitzats = regles_totp.consumeix_codi(
                doc.get("codis_recuperacio") or [], codi)
            if ha_valgut:
                comptes.desa_codis_recuperacio(g.mag, login_pendent, actualitzats)
                registra("TOTP", login_pendent, "codi de recuperació usat", ip)
                valid = True

        if not valid:
            _apunta_intent(ip)
            registra("LOGIN_FALLIT", login_pendent, "codi incorrecte", ip)
            flash("El codi no és correcte.", "error")
            return render_template("auth/login_totp.html"), 401

        treballador = comptes.per_login(g.mag, login_pendent)
        desti = session.get("pendent_desti")
        session.clear()
        login_user(Usuari(treballador))
        comptes.actualitza(g.mag, login_pendent, ultim_acces=ara_utc().isoformat())
        registra("LOGIN", login_pendent, "amb segon factor", ip)
        activitat.registra(g.mag, "LOGIN", login_pendent, "amb segon factor", ip)
        return redirect(_desti_segur(desti))

    return render_template("auth/login_totp.html")


@auth.route("/logout")
@login_required
def logout():
    registra("LOGOUT", current_user.get_id(), "", request.remote_addr or "")
    logout_user()
    session.clear()
    flash("Has sortit de l'aplicació.", "ok")
    return redirect(url_for("auth.login"))


# -- contrasenya ------------------------------------------------------------
@auth.route("/canvia-contrasenya", methods=["GET", "POST"])
@login_required
def canvia_contrasenya():
    if request.method == "POST":
        login = current_user.get_id()
        actual = request.form.get("actual", "")
        nova = request.form.get("nova", "")
        repeticio = request.form.get("repeticio", "")

        try:
            if not regles_comptes.verifica(comptes.hash_de(g.mag, login), actual):
                raise ErrorHorari("La contrasenya actual no és correcta.")
            if nova != repeticio:
                raise ErrorHorari("Les dues contrasenyes noves no coincideixen.")
            regles_comptes.valida_politica(nova, provisional=actual)
        except ErrorHorari as e:
            flash(str(e), "error")
            return render_template("auth/canvia_contrasenya.html")

        comptes.actualitza(g.mag, login,
                           hash_contrasenya=regles_comptes.hash_contrasenya(nova),
                           canvi_pendent=False)
        registra("CANVI_CONTRASENYA", login, "", request.remote_addr or "")
        activitat.registra(g.mag, "CANVI_CONTRASENYA", login)
        flash("Contrasenya canviada.", "ok")
        return redirect(url_for("fitxatge.inici"))

    return render_template("auth/canvia_contrasenya.html")


@auth.route("/recupera", methods=["GET", "POST"])
def recupera():
    if request.method == "POST":
        correu = (request.form.get("correu") or "").strip()
        treballador = comptes.per_correu(g.mag, correu)
        if treballador is not None and treballador.actiu:
            token = regles_comptes.token_recuperacio(
                treballador.login, current_app.config["SECRET_KEY"])
            enllac = url_for("auth.recupera_nova", token=token, _external=True)
            notifica.envia_recuperacio(current_app.config["APP"], treballador, enllac)
            registra("RECUPERACIO", treballador.login, "", request.remote_addr or "")
        # La MATEIXA resposta tant si el correu existeix com si no.
        flash("Si aquest correu té compte, hi rebràs un enllaç d'aquí a un "
              "moment.", "ok")
        return redirect(url_for("auth.login"))
    return render_template("auth/recupera.html")


@auth.route("/recupera/<token>", methods=["GET", "POST"])
def recupera_nova(token):
    login = regles_comptes.obre_token(token, current_app.config["SECRET_KEY"])
    if login is None or comptes.per_login(g.mag, login) is None:
        flash("Aquest enllaç ha caducat o no és vàlid. Torna-ho a demanar.",
              "error")
        return redirect(url_for("auth.recupera"))

    if request.method == "POST":
        nova = request.form.get("nova", "")
        try:
            if nova != request.form.get("repeticio", ""):
                raise ErrorHorari("Les dues contrasenyes no coincideixen.")
            regles_comptes.valida_politica(nova)
        except ErrorHorari as e:
            flash(str(e), "error")
            return render_template("auth/recupera_nova.html", token=token)

        comptes.actualitza(g.mag, login,
                           hash_contrasenya=regles_comptes.hash_contrasenya(nova),
                           canvi_pendent=False)
        registra("CANVI_CONTRASENYA", login, "per recuperació",
                 request.remote_addr or "")
        flash("Contrasenya canviada. Ja pots entrar-hi.", "ok")
        return redirect(url_for("auth.login"))

    return render_template("auth/recupera_nova.html", token=token)


# -- segon factor -----------------------------------------------------------
@auth.route("/totp")
@login_required
def totp():
    login = current_user.get_id()
    doc = comptes.document(g.mag, login) or {}
    if doc.get("totp_actiu"):
        return render_template("auth/totp.html", actiu=True,
                               queden=regles_totp.queden(
                                   doc.get("codis_recuperacio") or []))

    secret = session.get("totp_provisional")
    if not secret:
        secret = regles_totp.genera_secret()
        session["totp_provisional"] = secret
    return render_template("auth/totp.html", actiu=False, secret=secret,
                           qr=regles_totp.qr_svg(secret, login),
                           obligatori=current_user.rol in (ROL_ADMIN, ROL_RESPONSABLE))


@auth.route("/totp/confirma", methods=["POST"])
@login_required
def totp_confirma():
    login = current_user.get_id()
    secret = session.get("totp_provisional")
    if not secret:
        flash("Torna a començar l'activació.", "avis")
        return redirect(url_for("auth.totp"))

    if not regles_totp.verifica(secret, request.form.get("codi", "")):
        flash("El codi no és correcte. Comprova que l'hora del mòbil sigui "
              "l'exacta i torna-ho a provar.", "error")
        return redirect(url_for("auth.totp"))

    codis = regles_totp.genera_codis_recuperacio()
    comptes.actualitza(g.mag, login, totp_secret=secret, totp_actiu=True,
                       codis_recuperacio=regles_totp.a_desar(codis))
    session.pop("totp_provisional", None)
    registra("TOTP", login, "activat", request.remote_addr or "")
    activitat.registra(g.mag, "TOTP", login, "activat")
    # Els codis s'ensenyen UNA sola vegada: el que es desa és el seu hash.
    return render_template("auth/totp.html", actiu=True, codis_nous=codis,
                           queden=len(codis))


@auth.route("/totp/regenera-codis", methods=["POST"])
@login_required
def totp_regenera_codis():
    login = current_user.get_id()
    codis = regles_totp.genera_codis_recuperacio()
    comptes.desa_codis_recuperacio(g.mag, login, regles_totp.a_desar(codis))
    registra("TOTP", login, "codis regenerats", request.remote_addr or "")
    return render_template("auth/totp.html", actiu=True, codis_nous=codis,
                           queden=len(codis))


@auth.route("/totp/desactiva", methods=["POST"])
@login_required
def totp_desactiva():
    if current_user.rol in (ROL_ADMIN, ROL_RESPONSABLE):
        flash("El teu rol no pot desactivar la verificació en dos passos.",
              "error")
        return redirect(url_for("auth.totp"))
    comptes.actualitza(g.mag, current_user.get_id(), totp_actiu=False,
                       totp_secret=None, codis_recuperacio=[])
    registra("TOTP", current_user.get_id(), "desactivat", request.remote_addr or "")
    flash("Verificació en dos passos desactivada.", "ok")
    return redirect(url_for("auth.totp"))


@auth.route("/avis-legal")
def avis_legal():
    """Pública SEMPRE: és la informació de l'article 13 del RGPD i s'ha de
    poder llegir abans d'entrar-hi."""
    return render_template("avis_legal.html")
