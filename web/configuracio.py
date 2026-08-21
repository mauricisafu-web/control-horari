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

from core import (
    comptes as regles_comptes, festius as importador, importa, notifica, regles,
)
from core.format_importacio import CODIFICACIO
from core.model import (
    AMBIT_TOTS, AMBITS_FESTIU, ASSUMPTES_PROPIS, DIES_SETMANA, ETIQUETA_ROL,
    ErrorHorari, ROL_ADMIN, ROLS, VACANCES,
)
from core.registre import registra
from magatzem import (
    absencies as mag_absencies, activitat, comptes, festius, horaris,
    parametres, serveis, subscripcions,
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


@configuracio.route("/fitxatge", methods=["POST"])
@cal_admin
def commuta_fitxatge():
    """Engega o apaga el fitxador.

    Va en una ruta propia i no amb la resta de parametres perque una
    casella desmarcada no envia res: alla, «no ve al formulari» vol dir
    «no el toquis», i aqui voldria dir «apaga'l»."""
    actiu = request.form.get("fitxatge_actiu") == "1"
    parametres.desa(g.mag, "fitxatge_actiu", actiu)
    registra("CONFIG", current_user.get_id(),
             f"fitxatge {'engegat' if actiu else 'apagat'}")
    flash("El fitxador queda engegat." if actiu else
          "El fitxador queda apagat. Els marcatges que hi hagi es "
          "conserven: tornar-lo a engegar es marcar aquesta casella.", "ok")
    return _torna("fitxatge")


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
            # Qui ja no hi treballa no ha de continuar rebent avisos al
            # mòbil, i el seu dispositiu deixa de ser una dada que
            # tinguem cap motiu per conservar.
            subscripcions.esborra_de(g.mag, login)

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


# -- càrrega de treballadors des d'un fitxer --------------------------------
# El fitxer el genera l'aplicació de nòmines i el puja un administrador. Vegeu
# `desplegament/INTEGRACIO_NOMINES.md`: la direcció és única (nòmines → control
# horari) i d'aquí no en surt mai cap contrasenya cap enrere.
LIMIT_FITXER = 2 * 1024 * 1024


def _llegeix_pujat(fitxer) -> str:
    """El contingut del CSV pujat, ja convertit a text.

    Pujar per error un `.xlsx`, un fitxer buit o cap fitxer és el cas NORMAL,
    no una fallada del programa: cada cas surt com un `ErrorHorari` amb un
    missatge que es pot ensenyar, mai com un 500."""
    if fitxer is None or not (fitxer.filename or "").strip():
        raise ErrorHorari("Cal triar un fitxer.")

    dades = fitxer.read()
    limit = current_app.config.get("MAX_CONTENT_LENGTH") or LIMIT_FITXER
    if len(dades) > limit:
        raise ErrorHorari(f"El fitxer és massa gros: el màxim són "
                          f"{limit // 1024} kB.")
    try:
        contingut = dades.decode(CODIFICACIO)
    except (UnicodeDecodeError, AttributeError):
        raise ErrorHorari("Això no sembla un CSV de text. Exporta'l des de "
                          "l'aplicació de nòmines i torna-ho a provar.")
    if not contingut.strip():
        raise ErrorHorari("El fitxer és buit.")
    return contingut


def _pla_importacio(contingut: str):
    """Analitza el text i el compara amb el que ja hi ha al magatzem.

    Els comptes es demanen amb `actius=False` a propòsit: qui està donat de
    baixa i torna a sortir al fitxer s'ha de reactivar, no tornar a crear."""
    files, errors = importa.analitza(contingut)
    noms_servei = {s["nom"]: s["id"] for s in serveis.llista(g.mag)}
    return importa.calcula_pla(files, comptes.llista(g.mag, actius=False),
                               noms_servei, errors)


def _crea_els_nous(pla, problemes: list[str]) -> tuple[int, dict[str, str]]:
    """Crea els comptes proposats. Retorna (quants, contrasenyes generades).

    La contrasenya que ve al fitxer NO es mostra ni es registra: nòmines ja
    l'ha enviada per correu i aquí només es xifra. Només s'ensenyen les que
    ha hagut de generar l'aplicació perquè la fila no en portava."""
    creats, generades = 0, {}
    for proposta in pla.crear:
        fila = proposta.fila
        if fila is None:
            continue
        provisional = (fila.contrasenya or "").strip()
        cal_ensenyar = not provisional
        if cal_ensenyar:
            provisional = regles_comptes.contrasenya_provisional()
        try:
            comptes.crea(g.mag, proposta.login, fila.nom, fila.correu,
                         regles_comptes.hash_contrasenya(provisional),
                         fila.rol, proposta.servei_id, fila.data_alta)
        except (ErrorHorari, ValueError) as e:
            problemes.append(f"{proposta.login}: {e}")
            continue
        creats += 1
        if cal_ensenyar:
            generades[proposta.login] = provisional
    return creats, generades


def _actualitza_els_existents(pla, problemes: list[str]) -> int:
    """Nom, correu, rol, servei i data d'alta. La contrasenya, MAI: una
    càrrega no pot canviar la de ningú que ja estigui fent servir l'app."""
    actualitzats = 0
    for proposta in pla.actualitzar:
        fila = proposta.fila
        if fila is None:
            continue
        # `actiu` i `data_baixa`: si tornava a sortir al fitxer, es reactiva.
        # `servei_id` ja ve resolt de la proposta, i quan el fitxer el porta
        # buit hi ve el que el compte ja tenia («buit = no es toca»).
        camps = {"nom": fila.nom, "rol": fila.rol, "actiu": True,
                 "data_baixa": None, "servei_id": proposta.servei_id}
        if fila.data_alta:
            camps["data_alta"] = fila.data_alta
        # El correu ha de ser únic: només es canvia si no és el d'una altra
        # persona. Si ho fos, quedarien dos comptes amb el mateix correu i la
        # recuperació de contrasenya no sabria a qui escriure.
        altre = comptes.per_correu(g.mag, fila.correu)
        if altre is None or altre.login == proposta.login:
            camps["correu"] = fila.correu

        try:
            comptes.actualitza(g.mag, proposta.login, **camps)
        except (ErrorHorari, ValueError) as e:
            problemes.append(f"{proposta.login}: {e}")
            continue
        actualitzats += 1
    return actualitzats


def _dona_de_baixa(pla, marcades: set[str], problemes: list[str]) -> int:
    """NOMÉS les que l'administrador ha marcat, una per una.

    Donar de baixa no esborra res: desactiva el compte i hi posa la data.
    Els marcatges es conserven els quatre anys que toca."""
    admins = {t.login for t in comptes.llista(g.mag) if t.rol == ROL_ADMIN}
    baixes = 0
    for proposta in pla.baixes:
        if proposta.login not in marcades:
            continue
        if proposta.login == current_user.get_id():
            problemes.append(f"{proposta.login}: no et pots donar de baixa a "
                             f"tu mateix.")
            continue
        if proposta.login in admins and len(admins) <= 1:
            problemes.append(f"{proposta.login}: no pots desactivar l'últim "
                             f"administrador.")
            continue
        try:
            comptes.desactiva(g.mag, proposta.login, date.today())
        except (ErrorHorari, ValueError) as e:
            problemes.append(f"{proposta.login}: {e}")
            continue
        admins.discard(proposta.login)
        baixes += 1
    return baixes


@configuracio.route("/importa", methods=["GET", "POST"])
@cal_admin
def pantalla_importa():
    """Càrrega de treballadors en dos passos: previsualitzar i aplicar.

    Aplicar torna a analitzar i a recalcular el pla a partir del contingut del
    fitxer: del formulari només se'n creu QUINES baixes s'han marcat. Si es
    confiés en la resta, qualsevol amb sessió d'administrador podria fabricar
    una petició que creï el compte que vulgui amb el rol que vulgui."""
    if request.method == "GET":
        return render_template("configuracio/importa.html",
                               pla=None, contingut="", resultat=None)

    aplica = request.form.get("accio") == "aplica"
    try:
        if aplica:
            contingut = request.form.get("contingut") or ""
            if not contingut.strip():
                raise ErrorHorari("S'ha perdut el contingut del fitxer. "
                                  "Torna'l a pujar.")
        else:
            contingut = _llegeix_pujat(request.files.get("fitxer"))
        pla = _pla_importacio(contingut)
    except (ErrorHorari, ValueError) as e:
        flash(str(e), "error")
        return redirect(url_for("configuracio.pantalla_importa"))

    if not aplica:
        return render_template("configuracio/importa.html",
                               pla=pla, contingut=contingut, resultat=None)

    marcades = {b.strip().lower() for b in request.form.getlist("baixa")}
    problemes: list[str] = []
    creats, generades = _crea_els_nous(pla, problemes)
    actualitzats = _actualitza_els_existents(pla, problemes)
    baixes = _dona_de_baixa(pla, marcades, problemes)

    # Al registre hi van els COMPTADORS, mai els noms ni les contrasenyes.
    resum = (f"importació: {creats} creats, {actualitzats} actualitzats, "
             f"{baixes} baixes")
    if creats:
        registra("ALTA_COMPTE", current_user.get_id(), f"importació: {creats}")
        activitat.registra(g.mag, "ALTA_COMPTE", current_user.get_id(),
                           f"importació: {creats}")
    registra("CONFIG", current_user.get_id(), resum)
    activitat.registra(g.mag, "CONFIG", current_user.get_id(), resum)

    flash(f"Càrrega feta: {creats} comptes creats, {actualitzats} "
          f"actualitzats i {baixes} donats de baixa.", "ok")
    return render_template("configuracio/importa.html",
                           pla=None, contingut="",
                           resultat={"creats": creats,
                                     "actualitzats": actualitzats,
                                     "baixes": baixes,
                                     "generades": generades,
                                     "problemes": problemes})
