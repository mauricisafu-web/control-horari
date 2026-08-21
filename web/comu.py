"""
web/comu.py — Peces compartides pels blueprints.

Aquí hi viuen els decoradors d'accés i la càrrega de dades que fan servir
diverses pantalles. Res de regles de negoci: això és de `core/`.
"""
from __future__ import annotations

from datetime import date
from functools import wraps

from flask import abort, current_app, flash, g, redirect, request, url_for
from flask_login import current_user

from core import comput
from core.model import AMBIT_TOTS, ROL_ADMIN, ROL_RESPONSABLE
from magatzem import absencies, comptes, festius, marcatges, parametres


# -- accés ------------------------------------------------------------------
def cal_aprovar(f):
    """Exigeix rol d'administrador o de responsable."""
    @wraps(f)
    def envoltori(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if current_user.rol not in (ROL_ADMIN, ROL_RESPONSABLE):
            abort(403)
        return f(*args, **kwargs)
    return envoltori


def cal_admin(f):
    """Exigeix rol d'administrador. La superfície administrativa no és per a
    ningú més."""
    @wraps(f)
    def envoltori(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if current_user.rol != ROL_ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return envoltori


def fitxatge_actiu() -> bool:
    """Si el fitxador esta engegat.

    Es resol UNA vegada per peticio: cada consulta es una lectura de
    Firestore i aquesta la fa el menu de totes les pagines."""
    if not hasattr(g, "_fitxatge"):
        valor = parametres.tots(g.mag).get("fitxatge_actiu", True)
        # Un "0" o un "false" arribats com a text son certs si els passes
        # per bool(). Val mes enumerar el que vol dir apagat.
        g._fitxatge = valor not in (False, 0, "", "0", "false", "False", None)
    return g._fitxatge


def cal_fitxatge(f):
    """Tanca una pantalla mentre el fitxador estigui apagat.

    Amagar l'enllac del menu i deixar la ruta oberta no es amagar res: qui
    en sapiga l'adreca hi entraria igual. Per aixo la ruta ha de deixar
    d'existir, no nomes de veure's."""
    @wraps(f)
    def envoltori(*args, **kwargs):
        if not fitxatge_actiu():
            abort(404)
        return f(*args, **kwargs)
    return envoltori


def ambits_meus() -> list[str]:
    """Els serveis que puc aprovar. Es resol UNA vegada per petició: fer-ho
    tres cops són tres lectures del magatzem multiplicades per cada visita."""
    if not hasattr(g, "_ambits"):
        if current_user.rol == ROL_ADMIN:
            g._ambits = [AMBIT_TOTS]
        else:
            g._ambits = comptes.ambits_de(g.mag, current_user.get_id())
    return g._ambits


def puc_veure(treballador) -> bool:
    """Si puc veure les dades d'aquesta persona: si sóc jo, o si el seu servei
    és al meu àmbit."""
    if treballador is None:
        return False
    if treballador.login == current_user.get_id():
        return True
    ambits = ambits_meus()
    return AMBIT_TOTS in ambits or treballador.servei_id in ambits


# -- paràmetres i dates -----------------------------------------------------
def jornada_maxima() -> int:
    return parametres.enter(g.mag, "jornada_maxima_minuts", 600)


def any_i_mes(defecte: date | None = None) -> tuple[int, int]:
    """Llegeix `?any=` i `?mes=`. Res del que arribi per la URL pot petar."""
    defecte = defecte or date.today()
    try:
        any = int(request.args.get("any", defecte.year))
        mes = int(request.args.get("mes", defecte.month))
    except (TypeError, ValueError):
        return defecte.year, defecte.month
    if not (1 <= mes <= 12) or not (1900 <= any <= 2200):
        return defecte.year, defecte.month
    return any, mes


def limits_del_mes(any: int, mes: int) -> tuple[date, date]:
    import calendar
    return date(any, mes, 1), date(any, mes, calendar.monthrange(any, mes)[1])


def a_data(text, defecte=None) -> date | None:
    """Converteix el que arriba d'un formulari. Un `?data=demà` no ha de fer
    un 500."""
    try:
        return date.fromisoformat((text or "").strip())
    except (ValueError, AttributeError):
        return defecte


# -- càrrega de dades -------------------------------------------------------
def resum_del_periode(login: str, inici: date, fi: date):
    """Carrega tot el que cal per al còmput d'un període amb el mínim de
    lectures: una consulta de marcatges, una de festius, una d'absències i
    una d'assignacions. MAI res dins d'un bucle de dies."""
    return comput.resum_periode(
        inici, fi,
        marcatges.del_periode(g.mag, login, inici, fi),
        comptes.assignacions_de(g.mag, login),
        festius.entre(g.mag, inici, fi),
        absencies.de_treballador(g.mag, login),
        jornada_maxima(),
    )


def correus_dels_aprovadors(servei_id: str | None) -> list[str]:
    """Els correus de qui pot aprovar les absències d'un servei."""
    correus = []
    for treballador in comptes.llista(g.mag):
        if treballador.rol == ROL_ADMIN:
            correus.append(treballador.correu)
        elif treballador.rol == ROL_RESPONSABLE:
            ambits = comptes.ambits_de(g.mag, treballador.login)
            if AMBIT_TOTS in ambits or (servei_id and servei_id in ambits):
                correus.append(treballador.correu)
    return [c for c in correus if c]
