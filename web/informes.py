"""web/informes.py — Exportacions. L'omple l'onada 4."""
from flask import Blueprint, render_template

from web.comu import cal_admin

informes = Blueprint("informes", __name__)


@informes.route("/informes")
@cal_admin
def index():
    return render_template("en_construccio.html", modul="Informes")
