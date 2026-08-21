"""
web/gestio.py — El que ha de resoldre un responsable.

És la part amb més control d'accés de tota l'aplicació: cada ruta d'aquí
ensenya o modifica dades d'altres persones. Regla sense excepcions: **cada
consulta es filtra pels àmbits de qui la fa**, i cada acció torna a carregar
l'objecte del magatzem per comprovar-ho, encara que l'identificador vingui
del formulari (o precisament per això).
"""
from __future__ import annotations

from datetime import date

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template,
    request, url_for,
)
from flask_login import current_user

from core import calendari, comput, fitxatge as regles_fitxatge, notifica, regles
from core.model import (
    AMBIT_TOTS, APROVADA, DENEGADA, ETIQUETA_ESTAT, ETIQUETA_MARCATGE,
    ETIQUETA_TIPUS, ErrorHorari, PENDENT, VACANCES, ASSUMPTES_PROPIS,
    a_local,
)
from core.registre import registra
from magatzem import (
    absencies as mag_absencies, activitat, comptes, festius, marcatges,
    parametres,
)
from web.comu import (
    ambits_meus, any_i_mes, avisa_al_mobil, cal_aprovar, cal_fitxatge,
    fitxatge_actiu, jornada_maxima, limits_del_mes, resum_del_periode,
)

gestio = Blueprint("gestio", __name__)


def _saldo_de(treballador, tipus, any):
    assignat = mag_absencies.saldo_assignat(g.mag, treballador.login, any, tipus)
    if assignat is None:
        clau = "dies_vacances_defecte" if tipus == VACANCES else "dies_ap_defecte"
        assignat = parametres.enter(g.mag, clau, 22 if tipus == VACANCES else 6)
    return regles.calcula_saldo(
        tipus, any, assignat, mag_absencies.de_treballador(g.mag, treballador.login),
        treballador.data_alta, treballador.data_baixa)


@gestio.route("/gestio")
@cal_aprovar
def index():
    ambits = ambits_meus()
    any, mes = any_i_mes()
    inici, fi = limits_del_mes(any, mes)

    # -- absències pendents del meu àmbit, amb saldo i solapaments ---------
    pendents = []
    for absencia in mag_absencies.pendents(g.mag, ambits):
        treballador = comptes.per_login(g.mag, absencia.treballador_id)
        if treballador is None:
            continue
        altres = mag_absencies.solapaments_servei(
            g.mag, treballador.servei_id, absencia.data_inici, absencia.data_fi,
            excloent_treballador=treballador.login)
        noms = []
        for a in altres:
            company = comptes.per_login(g.mag, a.treballador_id)
            if company:
                noms.append(f"{company.nom} ({a.data_inici.strftime('%d/%m')}"
                            f"–{a.data_fi.strftime('%d/%m')})")
        pendents.append({
            "absencia": absencia, "treballador": treballador,
            "saldo": _saldo_de(treballador, absencia.tipus, absencia.data_inici.year),
            "solapaments": noms,
            "meva": absencia.treballador_id == current_user.get_id(),
        })

    # -- correccions de marcatge pendents ---------------------------------
    # Amb el fitxador apagat no s'hi consulta: a mes de no tenir sentit, cada
    # visita a aquesta pantalla seria una consulta a Firestore per a res.
    correccions = []
    for marcatge in (marcatges.pendents_validacio(g.mag, ambits)
                     if fitxatge_actiu() else ()):
        treballador = comptes.per_login(g.mag, marcatge.treballador_id)
        original = (marcatges.per_id(g.mag, marcatge.anul_la_id)
                    if marcatge.anul_la_id else None)
        correccions.append({
            "marcatge": marcatge, "treballador": treballador,
            "original": original,
            "puc": regles_fitxatge.pot_validar(current_user.treballador, marcatge),
        })

    # -- calendari general de l'àmbit --------------------------------------
    esdeveniments: dict[date, list] = {}
    for a in mag_absencies.aprovades_en(g.mag, inici, fi, ambits):
        treballador = comptes.per_login(g.mag, a.treballador_id)
        dia = max(a.data_inici, inici)
        while dia <= min(a.data_fi, fi):
            esdeveniments.setdefault(dia, []).append({
                "text": treballador.nom.split()[0] if treballador else "?",
                "estat": a.estat, "codi": a.codi})
            dia = date.fromordinal(dia.toordinal() + 1)

    return render_template(
        "gestio/index.html", pendents=pendents, correccions=correccions,
        graella=calendari.graella_mes(any, mes, esdeveniments,
                                      festius.del_any(g.mag, any)),
        etiqueta_tipus=ETIQUETA_TIPUS, etiquetes_marcatge=ETIQUETA_MARCATGE,
        a_local=a_local)


@gestio.route("/gestio/resol", methods=["POST"])
@cal_aprovar
def resol():
    codi = request.form.get("codi", "")
    accio = request.form.get("accio", "")
    motiu = request.form.get("motiu", "")

    absencia = mag_absencies.per_codi(g.mag, codi)
    if absencia is None:
        abort(404)
    treballador = comptes.per_login(g.mag, absencia.treballador_id)

    # Comprovació d'àmbit ABANS de res. Inclou el cas de la sol·licitud
    # PRÒPIA, que no pot resoldre ningú, ni sent administrador.
    if not regles.pot_resoldre(current_user.treballador, absencia,
                               ambits_meus(),
                               treballador.servei_id if treballador else None):
        abort(403)

    estat = APROVADA if accio == "aprova" else DENEGADA
    if estat == APROVADA:
        # Entre la sol·licitud i l'aprovació poden haver passat coses.
        saldo = _saldo_de(treballador, absencia.tipus, absencia.data_inici.year)
        if absencia.dies > saldo.disponibles:
            flash(f"No es pot aprovar: a {treballador.nom} només li queden "
                  f"{saldo.disponibles} dies i en demana {absencia.dies}.", "error")
            return redirect(url_for("gestio.index"))

    try:
        mag_absencies.resol(g.mag, codi, estat, current_user.get_id(), motiu)
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("gestio.index"))

    registra("ABSENCIA_RESOL", current_user.get_id(), f"{codi} {estat}",
             request.remote_addr or "")
    activitat.registra(g.mag, "ABSENCIA_RESOL", current_user.get_id(),
                       f"{codi} {estat}")

    resolta = mag_absencies.per_codi(g.mag, codi)
    # L'avís al mòbil és la via principal; el correu queda per si algun dia hi
    # ha SMTP. Cap dels dos pot tombar una resolució que ja està desada.
    avisa_al_mobil([absencia.treballador_id], "avisa_resolucio",
                   aprovada=(estat == APROVADA))
    notifica.avisa_resolucio(current_app.config["APP"], resolta, treballador)
    flash(f"Sol·licitud {codi} {ETIQUETA_ESTAT[estat].lower()}.", "ok")
    return redirect(url_for("gestio.index"))


@gestio.route("/gestio/marcatge", methods=["POST"])
@cal_aprovar
@cal_fitxatge
def marcatge():
    marcatge_id = request.form.get("marcatge", "")
    accepta = request.form.get("accio") == "valida"

    fila = marcatges.per_id(g.mag, marcatge_id)
    if fila is None:
        abort(404)
    treballador = comptes.per_login(g.mag, fila.treballador_id)

    ambits = ambits_meus()
    dins_ambit = (AMBIT_TOTS in ambits
                  or (treballador and treballador.servei_id in ambits))
    # Ningú valida una correcció que ha fet ell mateix.
    if not dins_ambit or not regles_fitxatge.pot_validar(current_user.treballador, fila):
        abort(403)

    try:
        marcatges.valida(g.mag, marcatge_id, current_user.get_id(), accepta)
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("gestio.index"))

    registra("VALIDA_CORRECCIO", current_user.get_id(),
             f"{marcatge_id} {'validada' if accepta else 'rebutjada'}",
             request.remote_addr or "")
    activitat.registra(g.mag, "VALIDA_CORRECCIO", current_user.get_id(),
                       marcatge_id)
    flash("Correcció validada." if accepta
          else "Correcció rebutjada. El marcatge original torna a comptar.", "ok")
    return redirect(url_for("gestio.index"))


@gestio.route("/gestio/hores")
@cal_aprovar
@cal_fitxatge
def hores():
    ambits = ambits_meus()
    any, mes = any_i_mes()
    inici, fi = limits_del_mes(any, mes)

    plantilla = comptes.de_serveis(g.mag, ambits)
    # UNA consulta per a tot l'àmbit, no una per persona: al magatzem de
    # producció cada document llegit compta contra el límit gratuït diari.
    per_treballador = marcatges.del_periode_serveis(g.mag, ambits, inici, fi)
    festius_del_mes = festius.entre(g.mag, inici, fi)
    maxim = jornada_maxima()

    files = []
    for treballador in plantilla:
        resum = comput.resum_periode(
            inici, fi, per_treballador.get(treballador.login, []),
            comptes.assignacions_de(g.mag, treballador.login),
            festius_del_mes,
            mag_absencies.de_treballador(g.mag, treballador.login, any),
            maxim)
        files.append({
            "treballador": treballador, "resum": resum,
            "incidencies": sum(1 for d in resum.dies if d.anomalies),
        })
    files.sort(key=lambda f: f["resum"].saldo)

    return render_template("gestio/hores.html", files=files, any=any, mes=mes,
                           formata=comput.formata_minuts,
                           anterior=(any - 1, 12) if mes == 1 else (any, mes - 1),
                           seguent=(any + 1, 1) if mes == 12 else (any, mes + 1))
