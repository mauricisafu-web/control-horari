"""
web/informes.py — Exportació del registre de jornada.

Obligació de l'article 34.9 de l'Estatut dels treballadors: el registre ha
d'estar a disposició dels treballadors, dels seus representants i de la
Inspecció de Treball.

ATENCIÓ AL COST: un informe és, per naturalesa, la pantalla que llegeix més
documents del magatzem, i el nivell gratuït en són 50.000 al dia. Per això hi
ha un LÍMIT DUR aplicat al servidor (no només amagat al formulari): com a
màxim un mes de tota la plantilla, o un any d'una sola persona.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from flask import (
    Blueprint, Response, flash, g, redirect, render_template, request, url_for,
)
from flask_login import current_user

from core import comput
from core.model import ETIQUETA_MARCATGE, a_local
from core.registre import registra
from magatzem import (
    absencies as mag_absencies, activitat, comptes, festius, marcatges,
)
from web.comu import a_data, cal_admin, jornada_maxima

informes = Blueprint("informes", __name__)

# Límit de disseny (DISSENY.md §3.5). Amb això, l'informe més car surt per
# unes 2.000 lectures i arribar al límit diari és impossible en l'ús normal.
MAXIM_DIES_TOTHOM = 31
MAXIM_DIES_UNA_PERSONA = 366


@informes.route("/informes")
@cal_admin
def index():
    avui = date.today()
    return render_template("informes/index.html",
                           plantilla=comptes.llista(g.mag, actius=False),
                           inici=avui.replace(day=1), fi=avui,
                           maxim_tothom=MAXIM_DIES_TOTHOM,
                           maxim_una=MAXIM_DIES_UNA_PERSONA)


def _comprova_limits(login: str, inici: date, fi: date) -> str | None:
    dies = (fi - inici).days + 1
    if dies <= 0:
        return "La data final no pot ser anterior a la inicial."
    if login and dies > MAXIM_DIES_UNA_PERSONA:
        return (f"Un informe d'una sola persona pot abastar com a màxim "
                f"{MAXIM_DIES_UNA_PERSONA} dies. Parteix-lo per anys.")
    if not login and dies > MAXIM_DIES_TOTHOM:
        return (f"Un informe de tota la plantilla pot abastar com a màxim "
                f"{MAXIM_DIES_TOTHOM} dies. Demana'l mes a mes.")
    return None


def _dades(login: str, inici: date, fi: date):
    """Carrega el mínim de vegades possible: una consulta de festius per a
    tot el període i una de marcatges per persona."""
    plantilla = ([comptes.per_login(g.mag, login)] if login
                 else comptes.llista(g.mag, actius=False))
    plantilla = [t for t in plantilla if t is not None]
    festius_periode = festius.entre(g.mag, inici, fi)
    maxim = jornada_maxima()

    files = []
    for treballador in plantilla:
        del_periode = marcatges.del_periode(g.mag, treballador.login, inici, fi)
        resum = comput.resum_periode(
            inici, fi, del_periode,
            comptes.assignacions_de(g.mag, treballador.login),
            festius_periode,
            mag_absencies.de_treballador(g.mag, treballador.login),
            maxim)
        files.append({"treballador": treballador, "resum": resum,
                      "marcatges": del_periode})
    return files


@informes.route("/informes/genera", methods=["POST"])
@cal_admin
def genera():
    login = (request.form.get("treballador") or "").strip()
    inici = a_data(request.form.get("inici"))
    fi = a_data(request.form.get("fi"))
    format = request.form.get("format", "csv")

    if inici is None or fi is None:
        flash("Les dates no són correctes.", "error")
        return redirect(url_for("informes.index"))

    problema = _comprova_limits(login, inici, fi)
    if problema:
        flash(problema, "error")
        return redirect(url_for("informes.index"))

    files = _dades(login, inici, fi)
    # L'accés al registre d'una altra persona deixa rastre, sempre.
    registra("INFORME", current_user.get_id(),
             f"{login or 'tothom'} {inici}..{fi} {format}",
             request.remote_addr or "")
    activitat.registra(g.mag, "INFORME", current_user.get_id(),
                       f"{login or 'tothom'} {inici}..{fi}")

    if format == "pdf":
        return _pdf(files, inici, fi)
    return _csv(files, inici, fi)


def _csv(files, inici: date, fi: date) -> Response:
    memoria = io.StringIO()
    escriptor = csv.writer(memoria, delimiter=";")
    escriptor.writerow(["Treballador", "Servei", "Data", "Hora", "Tipus",
                        "Origen", "Estat", "Compta", "Nota", "Registrat per"])
    for fila in files:
        t = fila["treballador"]
        for m in fila["marcatges"]:
            escriptor.writerow([
                t.nom, t.servei or "", m.data.strftime("%d/%m/%Y"),
                a_local(m.moment).strftime("%H:%M:%S"),
                ETIQUETA_MARCATGE.get(m.tipus, m.tipus), m.origen, m.estat,
                "sí" if m.compta else "no", m.nota, m.creat_per or ""])

    # BOM: perquè l'Excel obri els accents bé sense que ningú hi hagi de fer res.
    contingut = "﻿" + memoria.getvalue()
    nom = f"registre_jornada_{inici:%Y%m%d}_{fi:%Y%m%d}.csv"
    return Response(contingut, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


def _pdf(files, inici: date, fi: date) -> Response:
    """El document que es porta a una inspecció: llegible i complet, no maco.

    NOMÉS nom, servei i hores: ni NIF, ni adreça, ni correu."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    from magatzem import parametres

    memoria = io.BytesIO()
    document = SimpleDocTemplate(memoria, pagesize=A4, topMargin=18 * mm,
                                 bottomMargin=18 * mm, leftMargin=15 * mm,
                                 rightMargin=15 * mm,
                                 title="Registre de jornada")
    estils = getSampleStyleSheet()
    ajuntament = parametres.text(g.mag, "nom_ajuntament", "Ajuntament")
    contingut = []

    for i, fila in enumerate(files):
        t = fila["treballador"]
        resum = fila["resum"]
        if i:
            contingut.append(PageBreak())
        contingut += [
            Paragraph(f"<b>{ajuntament}</b>", estils["Normal"]),
            Paragraph("Registre de jornada", estils["Title"]),
            Paragraph(f"<b>{t.nom}</b> — {t.servei or 'sense servei'}",
                      estils["Normal"]),
            Paragraph(f"Període: del {inici:%d/%m/%Y} al {fi:%d/%m/%Y}",
                      estils["Normal"]),
            Spacer(1, 6 * mm),
        ]

        dades = [["Data", "Entrades i sortides", "Fetes", "Degudes", "Saldo"]]
        for dia in resum.dies:
            if not dia.marcatges and not dia.minuts_teorics:
                continue
            hores = " · ".join(
                f"{a_local(m.moment):%H:%M} {ETIQUETA_MARCATGE.get(m.tipus, '')[:3]}"
                for m in dia.marcatges)
            dades.append([
                f"{dia.data:%d/%m/%Y}", hores or "—",
                comput.formata_minuts(dia.minuts_fets),
                comput.formata_minuts(dia.minuts_teorics),
                comput.formata_minuts(dia.saldo)])
        dades.append(["TOTAL", "",
                      comput.formata_minuts(resum.minuts_fets),
                      comput.formata_minuts(resum.minuts_teorics),
                      comput.formata_minuts(resum.saldo)])

        taula = Table(dades, colWidths=[24 * mm, 76 * mm, 22 * mm, 22 * mm, 22 * mm])
        taula.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8ecf4")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8ecf4")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b9c2d4")),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        contingut += [taula, Spacer(1, 5 * mm),
                      Paragraph(f"<font size=7>Expedit el "
                                f"{date.today():%d/%m/%Y}.</font>",
                                estils["Normal"])]

    document.build(contingut)
    nom = f"registre_jornada_{inici:%Y%m%d}_{fi:%Y%m%d}.pdf"
    return Response(memoria.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})
