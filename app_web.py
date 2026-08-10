"""
app_web.py — Fàbrica de l'aplicació Flask.

Com hi accedeixen els blueprints al magatzem:

    from flask import g
    treballador = magatzem.comptes.per_login(g.mag, 'treb01')

`g.mag` és el MATEIX objecte durant tota la petició, i el mateix per a tot el
procés: obrir-ne un de nou a cada petició costaria una connexió cada vegada.

Execució en local:  python app_web.py           (port 5004, magatzem en memòria)
Execució al núvol:  gunicorn 'app_web:crea_app()'
"""
from __future__ import annotations

from datetime import timedelta

from flask import Flask, g, render_template, request
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

import configuracio
from core import model
from core.registre import registra
from magatzem import rebost

csrf = CSRFProtect()

# Rutes que responen sense sessió. La resta les protegeix @login_required.
PUBLIQUES = ("/login", "/recupera", "/avis-legal", "/manifest.webmanifest",
             "/sw.js", "/instal-lacio", "/static")


def crea_app(config_extra: dict | None = None, magatzem=None) -> Flask:
    app = Flask(__name__)
    conf = configuracio.carrega()
    if config_extra:
        conf.update(config_extra)

    app.config.update(
        SECRET_KEY=conf["SECRET_KEY"],
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=conf["COOKIE_SECURE"],
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=conf["SESSIO_MINUTS"]),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,     # el mòdul no puja fitxers
        APP=conf,
    )
    if config_extra:
        app.config.update(config_extra)

    # Darrere de Cloud Run, sense això `request.remote_addr` és la IP del
    # balancejador: el límit d'intents de login comptaria tothom com un de sol.
    if conf["DARRERE_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # -- magatzem --------------------------------------------------------
    mag = magatzem if magatzem is not None else rebost.obre_rebost(conf["REBOST"])
    rebost.inicialitza(mag)

    # Dades sintetiques per a demostracions. Amb el magatzem en memoria, cada
    # arrencada comenca de zero: sense aixo no hi hauria res per ensenyar.
    if conf.get("DADES_PROVA") and not mag.consulta(rebost.TREBALLADORS, limit=1):
        from eines.dades_prova import pobla
        pobla(mag)

    # Purga per conservacio. Ve DESACTIVADA per defecte: esborrar un llibre
    # de registre legalment exigible ha de ser una decisio conscient.
    from core import purga
    purga.executa_si_toca(mag, conf)

    app.extensions["magatzem"] = mag

    @app.before_request
    def _posa_magatzem():
        g.mag = app.extensions["magatzem"]

    # -- seguretat -------------------------------------------------------
    csrf.init_app(app)

    from web.auth import gestor_login
    gestor_login.init_app(app)

    @app.before_request
    def _comprova_origen():
        """En producció, rebutja les peticions que no arriben pel domini
        públic. Els *rewrites* de Firebase Hosting obliguen que el servei de
        Cloud Run sigui invocable sense autenticar, o sigui que la seva URL
        directa també respon; això la tanca."""
        esperat = conf["DOMINI_PUBLIC"]
        if esperat and request.host.split(":")[0] != esperat:
            return render_template("error.html", codi=403,
                                   missatge="Aquesta adreça no és la correcta."), 403

    @app.before_request
    def _sessio_permanent():
        from flask import session
        session.permanent = True

    @app.after_request
    def _capceleres(resposta):
        resposta.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'")
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "same-origin")
        if conf["COOKIE_SECURE"]:
            resposta.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000")
        # Els estàtics SÍ que es poden cachejar: no hi ha dades de ningú i és
        # el que fa que la PWA carregui de pressa. Les pàgines, mai.
        if request.path.startswith("/static/"):
            resposta.headers.setdefault("Cache-Control", "public, max-age=86400")
        else:
            resposta.headers["Cache-Control"] = "no-store"
        return resposta

    # -- blueprints ------------------------------------------------------
    from web.absencies import absencies
    from web.auth import auth
    from web.configuracio import configuracio as bp_configuracio
    from web.fitxatge import fitxatge
    from web.gestio import gestio
    from web.hores import hores
    from web.informes import informes
    from web.pwa import pwa

    for bp in (auth, pwa, fitxatge, hores, absencies, gestio,
               bp_configuracio, informes):
        app.register_blueprint(bp)

    # -- errors ----------------------------------------------------------
    def _error(codi, missatge):
        def gestor(e):
            return render_template("error.html", codi=codi, missatge=missatge), codi
        return gestor

    app.register_error_handler(403, _error(403, "No tens permís per veure aquesta pàgina."))
    app.register_error_handler(404, _error(404, "Aquesta pàgina no existeix."))
    app.register_error_handler(413, _error(413, "El fitxer que has enviat és massa gros."))
    app.register_error_handler(500, _error(500, "Hi ha hagut un error inesperat."))

    @app.errorhandler(CSRFError)
    def _csrf_caducat(e):
        return render_template(
            "error.html", codi=400,
            missatge="El formulari ha caducat. Torna-ho a provar."), 400

    # -- context de les plantilles ---------------------------------------
    @app.context_processor
    def _context():
        return {"model": model, "any_actual": __import__("datetime").date.today().year}

    registra("ARRENCADA", detall=f"magatzem={conf['REBOST']}")
    return app


app = None   # el crea `crea_app()`; existeix per compatibilitat amb gunicorn


if __name__ == "__main__":
    aplicacio = crea_app()
    conf = aplicacio.config["APP"]
    print(f"\n  Control horari — http://127.0.0.1:{conf['PORT']}")
    print(f"  Magatzem: {conf['REBOST']}\n")
    aplicacio.run(host="127.0.0.1", port=conf["PORT"], debug=conf["FLASK_DEBUG"])
