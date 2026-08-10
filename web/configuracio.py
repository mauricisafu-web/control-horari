"""web/configuracio.py — Esquelet. L'omple l'onada 3."""
from flask import Blueprint, render_template
from flask_login import login_required

configuracio = Blueprint('configuracio', __name__, url_prefix='/configuracio')


@configuracio.route('/')
@login_required
def index():
    return render_template('en_construccio.html', modul='Configuració')
