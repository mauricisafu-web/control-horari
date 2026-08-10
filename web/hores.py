"""web/hores.py — Esquelet. L'omple una onada posterior."""
from flask import Blueprint, render_template
from flask_login import login_required

hores = Blueprint('hores', __name__)

@hores.route('/hores')
@login_required
def resum():
    return render_template('en_construccio.html', modul='Hores')

@hores.route('/el-meu-horari')
@login_required
def horari():
    return render_template('en_construccio.html', modul='El meu horari')
