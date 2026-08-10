"""
web/hores.py — «Quantes hores he fet aquest mes?» i «Quin horari tinc?».

Dues preguntes que un treballador ha de poder respondre sense trucar a ningú.
"""
from __future__ import annotations

from datetime import date

from flask import Blueprint, g, render_template
from flask_login import current_user, login_required

from core import comput
from core.model import DIES_SETMANA, MESOS
from magatzem import comptes
from web.comu import any_i_mes, limits_del_mes, resum_del_periode

hores = Blueprint("hores", __name__)


@hores.route("/hores")
@login_required
def resum():
    login = current_user.get_id()
    any, mes = any_i_mes()
    inici, fi = limits_del_mes(any, mes)

    # NOMÉS les meves dades. Aquesta ruta no accepta cap paràmetre de
    # treballador: no hi ha manera de demanar les d'un altre.
    del_mes = resum_del_periode(login, inici, fi)

    # Saldo acumulat de l'any fins al final del mes que es mira: és el número
    # que la gent realment vol saber.
    del_any = resum_del_periode(login, date(any, 1, 1), fi)

    return render_template(
        "hores/resum.html", resum=del_mes, acumulat=del_any.saldo,
        any=any, mes=mes, nom_mes=MESOS[mes - 1], dies_setmana=DIES_SETMANA,
        formata=comput.formata_minuts,
        anterior=(any - 1, 12) if mes == 1 else (any, mes - 1),
        seguent=(any + 1, 1) if mes == 12 else (any, mes + 1))


@hores.route("/el-meu-horari")
@login_required
def horari():
    login = current_user.get_id()
    assignacions = comptes.assignacions_de(g.mag, login)
    avui = date.today()
    vigent = comput.assignacio_vigent(avui, assignacions)

    setmanal = 0
    per_dia = {}
    if vigent is not None:
        for dia in range(1, 8):
            trams = vigent.patro.trams_del_dia(dia)
            per_dia[dia] = trams
            setmanal += sum(t.minuts for t in trams)
        if vigent.coeficient != 100:
            setmanal = round(setmanal * vigent.coeficient / 100)

    return render_template("hores/horari.html", assignacions=assignacions,
                           vigent=vigent, per_dia=per_dia, setmanal=setmanal,
                           dies_setmana=DIES_SETMANA,
                           formata=comput.formata_minuts)
