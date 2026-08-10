"""
web/absencies.py — Vacances i assumptes propis, des del punt de vista del
treballador.

Aquesta pantalla NO ensenya mai les absències de ningú altre, ni al
calendari: el calendari general és de la pantalla de gestió i té un altre
control d'accés.
"""
from __future__ import annotations

from datetime import date

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from core import calendari, notifica, regles
from core.model import (
    ANULADA, APROVADA, ETIQUETA_ESTAT, ETIQUETA_TIPUS, ErrorHorari, PENDENT,
    TIPUS_ABSENCIA, VACANCES, ASSUMPTES_PROPIS,
)
from core.registre import registra
from magatzem import absencies as mag, activitat, festius, parametres
from web.comu import a_data, any_i_mes, correus_dels_aprovadors

absencies = Blueprint("absencies", __name__)

# `recuperacio` no té assignació anual i encara no s'ha decidit com funciona:
# de moment el formulari només ofereix els dos tipus amb saldo.
TIPUS_DEMANABLES = (VACANCES, ASSUMPTES_PROPIS)


def _saldos(login: str, any: int, treballador):
    """El saldo de cada tipus, calculat (mai desat)."""
    meves = mag.de_treballador(g.mag, login)
    resultat = []
    for tipus in TIPUS_DEMANABLES:
        assignat = mag.saldo_assignat(g.mag, login, any, tipus)
        if assignat is None:
            clau = ("dies_vacances_defecte" if tipus == VACANCES
                    else "dies_ap_defecte")
            assignat = parametres.enter(g.mag, clau, 22 if tipus == VACANCES else 6)
        resultat.append(regles.calcula_saldo(
            tipus, any, assignat, meves,
            treballador.data_alta, treballador.data_baixa))
    return resultat, meves


@absencies.route("/absencies")
@login_required
def index():
    login = current_user.get_id()
    any, mes = any_i_mes()
    saldos, meves = _saldos(login, any, current_user.treballador)

    # Calendari NOMÉS amb les meves absències.
    esdeveniments: dict[date, list] = {}
    for a in meves:
        if a.estat in (PENDENT, APROVADA):
            dia = a.data_inici
            while dia <= a.data_fi:
                esdeveniments.setdefault(dia, []).append({
                    "text": ETIQUETA_TIPUS.get(a.tipus, a.tipus),
                    "estat": a.estat, "codi": a.codi})
                dia = date.fromordinal(dia.toordinal() + 1)

    return render_template(
        "absencies/index.html", saldos=saldos, meves=meves,
        graella=calendari.graella_mes(any, mes, esdeveniments,
                                      festius.del_any(g.mag, any)),
        any=any, tipus=[(t, ETIQUETA_TIPUS[t]) for t in TIPUS_DEMANABLES],
        etiqueta_estat=ETIQUETA_ESTAT, etiqueta_tipus=ETIQUETA_TIPUS,
        avui=date.today())


@absencies.route("/absencies/solicita", methods=["POST"])
@login_required
def solicita():
    login = current_user.get_id()
    tipus = request.form.get("tipus", "")
    inici = a_data(request.form.get("inici"))
    fi = a_data(request.form.get("fi"))
    motiu = request.form.get("motiu", "")

    if tipus not in TIPUS_DEMANABLES or inici is None or fi is None:
        flash("Falten dades o les dates no són correctes.", "error")
        return redirect(url_for("absencies.index"))

    try:
        # Els dies els calcula el SERVIDOR amb els festius reals. Si es
        # confiessin al formulari, qualsevol es regalaria vacances.
        dies = regles.dies_habils(inici, fi,
                                  festius.entre(g.mag, inici, fi).keys())
        saldos, _ = _saldos(login, inici.year, current_user.treballador)
        saldo = next(s for s in saldos if s.tipus == tipus)
        regles.valida_solicitud(
            tipus, inici, fi, dies, saldo,
            mag.solapaments(g.mag, login, inici, fi))
        codi = mag.crea(g.mag, login, current_user.servei_id, tipus, inici, fi,
                        dies, motiu)
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("absencies.index"))

    registra("ABSENCIA_SOL", login, codi, request.remote_addr or "")
    activitat.registra(g.mag, "ABSENCIA_SOL", login, codi)

    # Primer es desa, després s'avisa: si l'SMTP falla, la sol·licitud hi és.
    absencia = mag.per_codi(g.mag, codi)
    if not notifica.avisa_nova_solicitud(
            current_app.config["APP"], absencia, current_user.treballador,
            correus_dels_aprovadors(current_user.servei_id)):
        flash("La sol·licitud s'ha desat, però no s'ha pogut enviar l'avís "
              "per correu. Avisa el teu responsable.", "avis")

    flash(f"Sol·licitud {codi} desada: {dies} dies. Queda pendent d'aprovació.",
          "ok")
    return redirect(url_for("absencies.index"))


@absencies.route("/absencies/anula", methods=["POST"])
@login_required
def anula():
    login = current_user.get_id()
    codi = request.form.get("codi", "")
    absencia = mag.per_codi(g.mag, codi)

    # L'identificador ve del formulari: comprovació de propietat obligatòria.
    if absencia is None or absencia.treballador_id != login:
        abort(403)
    # Una APROVADA només la pot anul·lar un responsable, des de /gestio.
    if absencia.estat != PENDENT:
        flash("Aquesta sol·licitud ja no és pendent: parla-ho amb el teu "
              "responsable.", "avis")
        return redirect(url_for("absencies.index"))

    try:
        mag.anula(g.mag, codi, login)
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("absencies.index"))

    registra("ABSENCIA_ANULA", login, codi, request.remote_addr or "")
    activitat.registra(g.mag, "ABSENCIA_ANULA", login, codi)
    flash(f"Sol·licitud {codi} anul·lada. Els dies tornen a estar disponibles.",
          "ok")
    return redirect(url_for("absencies.index"))
