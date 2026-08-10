"""web/informes.py — Esquelet. L'omple una onada posterior."""
from flask import Blueprint, render_template
from flask_login import login_required

informes = Blueprint('informes', __name__)

@informes.route('/informes')
@login_required
def index():
    return render_template('en_construccio.html', modul='Informes')
