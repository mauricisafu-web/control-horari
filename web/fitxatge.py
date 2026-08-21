"""
web/fitxatge.py — La pantalla principal: fitxar.

És la raó de ser de la PWA. Es mira tres segons, dues vegades al dia, sovint
al carrer i amb el mòbil a una mà. Per això només hi ha un botó gran amb
l'ÚNICA acció que toca ara, i tota la resta és secundari.
"""
from __future__ import annotations

from datetime import date

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request,
    url_for,
)
from flask_login import current_user, login_required

from core import comput, fitxatge as regles, notifica
from core.model import (
    ETIQUETA_MARCATGE, ErrorHorari, ORIGEN_WEB, a_local, ara_utc, data_local,
)
from core.registre import registra
from magatzem import (
    absencies as mag_absencies, activitat, comptes, festius as mag_festius,
    marcatges, parametres,
)
from web.comu import (
    any_i_mes, cal_fitxatge, correus_dels_aprovadors, fitxatge_actiu,
    jornada_maxima, limits_del_mes, resum_del_periode,
)

fitxatge = Blueprint("fitxatge", __name__)

ACCIO_ETIQUETA = {
    "entrada": "Fitxa l'ENTRADA",
    "sortida": "Fitxa la SORTIDA",
    "pausa_inici": "Comença la PAUSA",
    "pausa_fi": "Torna de la PAUSA",
}


@fitxatge.route("/")
@login_required
def inici():
    # Aquesta es l'arrel de l'aplicacio. Amb el fitxador apagat no pot
    # respondre 404 com les altres pantalles: qui entra ha d'anar a parar
    # a alguna banda, i aquella banda son les absencies.
    if not fitxatge_actiu():
        return redirect(url_for("absencies.index"))
    login = current_user.get_id()
    avui = date.today()

    del_dia = marcatges.del_dia(g.mag, login, avui)
    estat = regles.estat_actual(del_dia)
    accions = regles.accions_possibles(estat)

    resum_avui = comput.resum_dia(
        avui, del_dia, comptes.assignacions_de(g.mag, login),
        mag_festius.entre(g.mag, avui, avui),
        mag_absencies.de_treballador(g.mag, login, avui.year),
        jornada_maxima())

    inici_mes, fi_mes = limits_del_mes(avui.year, avui.month)
    resum_mes = resum_del_periode(login, inici_mes, min(fi_mes, avui))

    ultim = [m for m in del_dia if m.compta]
    return render_template(
        "fitxatge/inici.html",
        estat=estat, accions=accions, etiquetes=ACCIO_ETIQUETA,
        des_de=a_local(ultim[-1].moment).strftime("%H:%M") if ultim else None,
        ara=a_local(ara_utc()).strftime("%H:%M"),
        resum=resum_avui, resum_mes=resum_mes, formata=comput.formata_minuts)


@fitxatge.route("/fitxa", methods=["POST"])
@login_required
@cal_fitxatge
def fitxa():
    login = current_user.get_id()
    tipus = request.form.get("tipus", "")
    moment = ara_utc()
    avui = data_local(moment)

    try:
        del_dia = marcatges.del_dia(g.mag, login, avui)
        regles.valida_marcatge(
            tipus, moment, del_dia,
            parametres.enter(g.mag, 'segons_entre_marcatges', 60))
        marcatges.afegeix(g.mag, login, tipus, moment, ORIGEN_WEB, login,
                          servei_id=current_user.servei_id,
                          ip=request.remote_addr or "")
    except ErrorHorari as e:
        # Un fitxatge que no toca és un avís, mai un error 500.
        flash(str(e), "avis")
        return redirect(url_for("fitxatge.inici"))

    registra("FITXATGE", login, tipus, request.remote_addr or "")
    activitat.registra(g.mag, "FITXATGE", login, tipus, request.remote_addr or "")
    # El rebut del treballador: l'hora EXACTA que ha quedat registrada.
    flash(f"{ETIQUETA_MARCATGE[tipus]} registrada a les "
          f"{a_local(moment).strftime('%H:%M')}.", "ok")
    return redirect(url_for("fitxatge.inici"))


@fitxatge.route("/marcatges")
@login_required
@cal_fitxatge
def llista():
    login = current_user.get_id()
    any, mes = any_i_mes()
    inici, fi = limits_del_mes(any, mes)

    resum = resum_del_periode(login, inici, fi)
    tots = marcatges.del_periode(g.mag, login, inici, fi)
    per_dia: dict[date, list] = {}
    for m in tots:
        per_dia.setdefault(m.data, []).append(m)

    return render_template(
        "fitxatge/marcatges.html", resum=resum, per_dia=per_dia,
        any=any, mes=mes, formata=comput.formata_minuts,
        anterior=(any - 1, 12) if mes == 1 else (any, mes - 1),
        seguent=(any + 1, 1) if mes == 12 else (any, mes + 1),
        etiquetes=ETIQUETA_MARCATGE, a_local=a_local)


@fitxatge.route("/marcatges/corregeix", methods=["POST"])
@login_required
@cal_fitxatge
def corregeix():
    login = current_user.get_id()
    from datetime import datetime, timezone

    from core.model import ZONA

    original_id = request.form.get("original") or None
    original = marcatges.per_id(g.mag, original_id) if original_id else None

    # L'identificador ve del formulari: torna a carregar-lo i comprova que
    # és seu. Sense això, qualsevol podria corregir el marcatge d'un altre.
    if original is not None and original.treballador_id != login:
        from flask import abort
        abort(403)

    dia = date.fromisoformat(request.form.get("data") or date.today().isoformat())
    hora = request.form.get("hora") or "00:00"
    try:
        local = datetime.combine(dia, datetime.strptime(hora, "%H:%M").time(),
                                 tzinfo=ZONA)
    except ValueError:
        flash("L'hora no té el format correcte (per exemple, 08:30).", "error")
        return redirect(url_for("fitxatge.llista"))

    try:
        camps = regles.prepara_correccio(
            original, request.form.get("tipus", ""),
            local.astimezone(timezone.utc), request.form.get("nota", ""),
            current_user.treballador)
        marcatges.afegeix(g.mag, login, camps["tipus"], camps["moment"],
                          camps["origen"], login,
                          servei_id=current_user.servei_id,
                          ip=request.remote_addr or "", nota=camps["nota"],
                          anul_la_id=camps["anul_la_id"], estat=camps["estat"])
    except ErrorHorari as e:
        flash(str(e), "error")
        return redirect(url_for("fitxatge.llista"))

    registra("CORRECCIO", login, camps["tipus"], request.remote_addr or "")
    activitat.registra(g.mag, "CORRECCIO", login, camps["tipus"])

    # Primer es desa, després s'avisa: si el correu falla, la correcció ja hi és.
    notifica.avisa_correccio_pendent(
        current_app.config["APP"], current_user.treballador,
        correus_dels_aprovadors(current_user.servei_id))

    flash("Correcció desada. Un responsable l'ha de validar perquè compti.", "ok")
    return redirect(url_for("fitxatge.llista"))
