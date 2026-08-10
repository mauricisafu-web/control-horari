"""web/gestio.py — Esquelet. L'omple una onada posterior."""
from flask import Blueprint, render_template
from flask_login import login_required

gestio = Blueprint('gestio', __name__)

@gestio.route('/gestio')
@login_required
def index():
    return render_template('en_construccio.html', modul='Gestió')

@gestio.route('/gestio/hores')
@login_required
def hores():
    return render_template('en_construccio.html', modul='Hores del servei')
