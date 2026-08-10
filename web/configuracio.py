"""
web/configuracio.py — Manteniment de l'aplicació. NOMÉS administradors.

Amb un magatzem buit, un administrador ha de poder deixar l'aplicació llesta
sense sortir del navegador: crear serveis, importar els festius, fer un patró
d'horari, donar d'alta la gent i assignar-li l'horari.
"""
from __future__ import annotations

from datetime import date

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request,
    url_for,
)
from flask_login import current_user

from core import comptes as regles_comptes, festius as importador, notifica, regles
from core.model import (
    AMBIT_TOTS, AMBITS_FESTIU, ASSUMPTES_PROPIS, DIES_SETMANA, ETIQUETA_ROL,
    ErrorHorari, ROL_ADMIN, ROLS, VACANCES,
)
from core.registre import registra
from magatzem import (
    absencies as mag_absencies, activitat, comptes, festius, horaris,
    parametres, serveis,
)
from web.comu import a_data, cal_admin

configuracio = Blueprint("configuracio", __name__, url_prefix="/configuracio")

PARAMETRES_EDITABLES = ("dies_vacances_defecte", "dies_ap_defecte",
                        "jornada_maxima_minuts", "pausa_maxima_minuts",
                        "codi_ine_municipi", "nom_ajuntament")


def _torna(ancora: str = ""):
    return redirect(url_for("configuracio.index") + (f"#{ancora}" if ancora else ""))


# -- general ----------------------------------------------------------------
@configuracio.route("/")
@cal_admin
def index():
    any = date.today().year
    try:
        any = int(request.args.get("any", any))
    except (TypeError, ValueError):
        pass
    plantilla = comptes.llista(g.mag, actius=False)
    per_servei: dict[str, int] = {}
    for t in plantilla:
        if t.actiu and t.servei_id:
            per_servei[t.servei_id] = per_servei.get(t.servei_id, 0) + 1

    return render_template(
        "configuracio/index.html",
        serveis=serveis.llista(g.mag), per_servei=per_servei,
        festius=festius.detall_del_any(g.mag, any), any=any,
        ambits=AMBITS_FESTIU, parametres=parametres.tots(g.mag),
        editables=PARAMETRES_EDITABLES)


@configuracio.route("/servei", methods=["POST"])
@cal_admin
def servei():
    accio = request.form.get("accio")
    try:
        if accio == "crea":
            serveis.crea(g.mag, request.form.get("nom", ""),
                         request.form.get("color", "#1e4078"))
        elif accio == "desa":
            serveis.desa(g.mag, request.form.get("id", ""),
                         request.form.get("nom", ""),
                         request.form.get("color", "#1e4078"))
        elif accio == "elimina":
            servei_id = request.form.get("id", "")
            ocupats = sum(1 for t in comptes.llista(g.mag)
                          if t.servei_id == servei_id)
            serveis.elimina(g.mag, servei_id, ocupats)
    except ErrorHorari as e:
        flash(str(e), "error")
        return _torna("serveis")

    registra("CONFIG", current_user.get_id(), f"servei {accio}")
    flash("Serveis actualitzats.", "ok")
    return _torna("serveis")


@configuracio.route("/festiu", methods=["POST"])
@cal_admin
def festiu():
    accio = request.form.get("accio")
    any = date.today().year
    try:
        if accio == "afegeix":
            dia = a_data(request.form.get("data"))
            if dia is None:
                raise ErrorHorari("La data no és correcta.")
            festius.afegeix(g.mag, dia, request.form.get("nom", ""),
                            request.form.get("ambit", "propi"))
            any = dia.year
        elif accio == "elimina":
            dia = a_data(request.form.get("data"))
            if dia is not None:
                festius.elimina(g.mag, dia)
                any = dia.year
        elif accio == "importa":
            any = int(request.form.get("any") or any)
            codi_ine = (request.form.get("codi_ine")
                        or parametres.text(g.mag, "codi_ine_municipi", "43152"))
            parametres.desa(g.mag, "codi_ine_municipi", codi_ine)
            trobats = importador.importa(any, codi_ine)
            nous, repetits = festius.fusiona(g.mag, trobats)
            flash(f"Importació feta: {nous} festius nous i {repetits} que ja "
                  f"hi eren (aquests no s'han tocat).", "ok")
            registra("CONFIG", current_user.get_id(), f"festius importats {any}")
            return redirect(url_for("configuracio.index", any=any) + "#festius")
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("configuracio.index", any=any) + "#festius")

    registra("CONFIG", current_user.get_id(), f"festiu {accio}")
    flash("Calendari de festius actualitzat.", "ok")
    return redirect(url_for("configuracio.index", any=any) + "#festius")


@configuracio.route("/parametre", methods=["POST"])
@cal_admin
def parametre():
    for clau in PARAMETRES_EDITABLES:
        if clau in request.form:
            parametres.desa(g.mag, clau, request.form[clau].strip())
    registra("CONFIG", current_user.get_id(), "paràmetres")
    flash("Paràmetres desats.", "ok")
    return _torna("parametres")


# -- horaris ----------------------------------------------------------------
@configuracio.route("/horaris")
@cal_admin
def pantalla_horaris():
    llista_patrons = horaris.patrons(g.mag)
    plantilla = comptes.llista(g.mag)
    assignacions = {t.login: comptes.assignacions_de(g.mag, t.login)
                    for t in plantilla}
    totals = {p.id: sum(t.minuts for t in p.trams) for p in llista_patrons}
    return render_template("configuracio/horaris.html", patrons=llista_patrons,
                           totals=totals, plantilla=plantilla,
                           assignacions=assignacions,
                           dies_setmana=DIES_SETMANA)


@configuracio.route("/patro", methods=["POST"])
@cal_admin
def patro():
    try:
        if request.form.get("accio") == "elimina":
            horaris.elimina_patro(g.mag, request.form.get("id", ""))
        else:
            trams = horaris.trams_des_de_formulari(
                request.form.getlist("dia"), request.form.getlist("hora_inici"),
                request.form.getlist("hora_fi"))
            horaris.desa_patro(g.mag, request.form.get("nom", ""),
                               request.form.get("descripcio", ""), trams,
                               request.form.get("id") or None)
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("configuracio.pantalla_horaris"))

    registra("CONFIG", current_user.get_id(), "patró d'horari")
    flash("Patró d'horari desat.", "ok")
    return redirect(url_for("configuracio.pantalla_horaris"))


@configuracio.route("/assignacio", methods=["POST"])
@cal_admin
def assignacio():
    login = request.form.get("login", "")
    try:
        if request.form.get("accio") == "elimina":
            comptes.desassigna(g.mag, login, int(request.form.get("index", -1)))
        else:
            inici = a_data(request.form.get("data_inici"))
            if inici is None:
                raise ErrorHorari("Cal una data d'inici.")
            fi = a_data(request.form.get("data_fi"))

            # Avís de solapament: si no es tanca la vigència anterior, el
            # còmput es queda amb la més recent i el resultat desconcerta.
            for a in comptes.assignacions_de(g.mag, login):
                if a.data_fi is None or a.data_fi >= inici:
                    flash(f"Compte: «{a.patro.nom}» encara és vigent des del "
                          f"{a.data_inici.strftime('%d/%m/%Y')}. Posa-hi una "
                          f"data de fi perquè el còmput no es confongui.", "avis")
                    break

            comptes.assigna(g.mag, login, request.form.get("patro", ""), inici,
                            fi, int(request.form.get("coeficient") or 100))
    except (ErrorHorari, ValueError) as e:
        flash(str(e), "error")
        return redirect(url_for("configuracio.pantalla_horaris"))

    registra("CONFIG", current_user.get_id(), f"assignació {login}")
    flash("Assignació desada.", "ok")
    return redirect(url_for("configuracio.pantalla_horaris"))


# -- comptes ----------------------------------------------------------------
@configuracio.route("/comptes")
@cal_admin
def pantalla_comptes():
    any = date.today().year
    plantilla = comptes.llista(g.mag, actius=False)
    files = []
    for t in plantilla:
        saldos = []
        for tipus in (VACANCES, ASSUMPTES_PROPIS):
            assignat = mag_absencies.saldo_assignat(g.mag, t.login, any, tipus)
            if assignat is None:
                clau = ("dies_vacances_defecte" if tipus == VACANCES
                        else "dies_ap_defecte")
                assignat = parametres.enter(g.mag, clau, 22 if tipus == VACANCES else 6)
            saldos.append(regles.calcula_saldo(
                tipus, any, assignat,
                mag_absencies.de_treballador(g.mag, t.login),
                t.data_alta, t.data_baixa))
        files.append({"treballador": t, "saldos": saldos,
                      "ambits": comptes.ambits_de(g.mag, t.login)})

    return render_template("configuracio/comptes.html", files=files, any=any,
                           serveis=serveis.llista(g.mag), rols=ROLS,
                           etiqueta_rol=ETIQUETA_ROL, ambit_tots=AMBIT_TOTS)


@configuracio.route("/compte", methods=["POST"])
@cal_admin
def compte():
    accio = request.form.get("accio")
    login = (request.form.get("login") or "").strip().lower()

    try:
        if accio == "alta":
            provisional = regles_comptes.contrasenya_provisional()
            comptes.crea(g.mag, login, request.form.get("nom", ""),
                         request.form.get("correu", ""),
                         regles_comptes.hash_contrasenya(provisional),
                         request.form.get("rol", "treballador"),
                         request.form.get("servei") or None,
                         a_data(request.form.get("data_alta")))
            registra("ALTA_COMPTE", current_user.get_id(), login)
            activitat.registra(g.mag, "ALTA_COMPTE", current_user.get_id(), login)

            nou = comptes.per_login(g.mag, login)
            if notifica.envia_provisional(current_app.config["APP"], nou, provisional):
                flash(f"Compte «{login}» creat. La contrasenya provisional ha "
                      f"anat al seu correu.", "ok")
            else:
                # Bloquejar l'alta per un SMTP mal configurat seria pitjor:
                # es crea igualment i s'ensenya UNA vegada.
                flash(f"Compte «{login}» creat, però el correu no ha sortit. "
                      f"Contrasenya provisional: {provisional} — fes-la "
                      f"arribar per un canal segur; no es tornarà a mostrar.",
                      "avis")

        elif accio == "rol":
            nou_rol = request.form.get("rol", "")
            # Un administrador no es pot degradar ell mateix: l'ajuntament es
            # quedaria sense ningú que pugui administrar l'aplicació.
            if login == current_user.get_id() and nou_rol != ROL_ADMIN:
                raise ErrorHorari("No et pots treure a tu mateix el rol "
                                  "d'administrador.")
            if nou_rol not in ROLS:
                raise ErrorHorari("El rol no és vàlid.")
            comptes.actualitza(g.mag, login, rol=nou_rol,
                               servei_id=request.form.get("servei") or None)

        elif accio == "ambits":
            marcats = request.form.getlist("ambit")
            comptes.desa_ambits(g.mag, login, marcats)

        elif accio == "saldo":
            # `l_any` i no `any`: anomenar-la `any` taparia la funcio
            # incorporada del mateix nom a TOTA la funcio, i la branca de
            # baixa peta amb UnboundLocalError.
            l_any = int(request.form.get("any") or date.today().year)
            for tipus in (VACANCES, ASSUMPTES_PROPIS):
                if tipus in request.form:
                    mag_absencies.desa_saldo(g.mag, login, l_any, tipus,
                                             int(request.form[tipus]))

        elif accio == "baixa":
            if login == current_user.get_id():
                raise ErrorHorari("No et pots donar de baixa a tu mateix.")
            actius = [t for t in comptes.llista(g.mag) if t.rol == ROL_ADMIN]
            if len(actius) <= 1 and any(t.login == login for t in actius):
                raise ErrorHorari("No pots desactivar l'últim administrador.")
            comptes.desactiva(g.mag, login, a_data(request.form.get("data_baixa")))

        elif accio == "alta_de_nou":
            comptes.actualitza(g.mag, login, actiu=True, data_baixa=None)

        elif accio == "totp_reset":
            comptes.actualitza(g.mag, login, totp_actiu=False, totp_secret=None,
                               codis_recuperacio=[])
            registra("TOTP", current_user.get_id(), f"reiniciat a {login}")

    except (ErrorHorari, ValueError) as e:
        flash(str(e), "error")
        return redirect(url_for("configuracio.pantalla_comptes"))

    if accio != "alta":
        registra("CONFIG", current_user.get_id(), f"compte {accio} {login}")
        flash("Compte actualitzat.", "ok")
    return redirect(url_for("configuracio.pantalla_comptes"))
