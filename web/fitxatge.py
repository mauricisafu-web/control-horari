"""web/fitxatge.py — Esquelet. L'omple una onada posterior."""
from flask import Blueprint, render_template
from flask_login import login_required

fitxatge = Blueprint('fitxatge', __name__)

@fitxatge.route('/')
@login_required
def inici():
    return render_template('en_construccio.html', modul='Fitxatge')

@fitxatge.route('/marcatges')
@login_required
def marcatges():
    return render_template('en_construccio.html', modul='Els meus marcatges')
