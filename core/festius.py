"""
core/festius.py — Importació dels festius de les dades obertes de la
Generalitat.

És l'ÚNICA crida de xarxa de tota l'aplicació. Només SURT, i només a dades
públiques: s'hi envien un any i un codi INE, cap dada de ningú.

La importació és una COMODITAT, no una dependència: si un dia la Generalitat
canvia l'API, l'aplicació ha de continuar funcionant i l'alta manual de
festius sempre hi és.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from core.model import AMBIT_GENERAL, AMBIT_LOCAL, ErrorHorari

SERVIDOR = "https://analisi.transparenciacatalunya.cat/resource"
DATASET_GENERALS = "8qnu-agns"      # festes generals de Catalunya
DATASET_LOCALS = "b4eh-r8up"        # festes locals per municipi
ESPERA = 10                          # segons


def _obre(url: str):
    """Obre l'URL. En un mòdul a part perquè els tests el puguin substituir:
    cap prova no ha de sortir a Internet."""
    peticio = urllib.request.Request(url, headers={"Accept": "application/json"})
    return urllib.request.urlopen(peticio, timeout=ESPERA)


def _a_data(text) -> date | None:
    """Les dates arriben com a text i de vegades amb hora."""
    if not text:
        return None
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _consulta(dataset: str, parametres: dict, obre=None) -> list[dict]:
    url = f"{SERVIDOR}/{dataset}.json?{urllib.parse.urlencode(parametres)}"
    try:
        with (obre or _obre)(url) as resposta:
            dades = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorHorari(
            "No s'ha pogut connectar amb les dades obertes de la Generalitat. "
            "Torna-ho a provar més tard; mentrestant pots afegir els festius "
            "a mà.") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErrorHorari(
            "Les dades obertes de la Generalitat han respost en un format "
            "inesperat. Afegeix els festius a mà i avisa'n qui manté "
            "l'aplicació.") from e
    return dades if isinstance(dades, list) else []


def importa(any: int, codi_ine: str = "43152",
            obre=None) -> list[tuple[date, str, str]]:
    """(data, nom, àmbit) de les festes generals i locals d'un any."""
    resultat: list[tuple[date, str, str]] = []
    vistes: set[date] = set()

    # Els dos datasets NO tenen el mateix esquema, tot i venir del mateix
    # portal: el de festes generals filtra per `any` i el de locals per
    # `any_calendari`. Enviar-hi el camp equivocat dona un HTTP 400.
    for dataset, ambit, camp_any, extra in (
        (DATASET_GENERALS, AMBIT_GENERAL, "any", {}),
        (DATASET_LOCALS, AMBIT_LOCAL, "any_calendari",
         {"codi_municipi_ine": str(codi_ine)}),
    ):
        parametres = {camp_any: str(any), "$limit": "200", **extra}
        for fila in _consulta(dataset, parametres, obre):
            if not isinstance(fila, dict):
                continue
            # Tolerant en llegir (els noms dels camps dels datasets oberts
            # canvien), estricte en validar: sense data, s'ignora la fila i
            # la importació continua.
            dia = _a_data(fila.get("data") or fila.get("data_festiu")
                          or fila.get("dia"))
            if dia is None or dia in vistes:
                continue
            # `nom_del_festiu` a les generals; `festiu` a les locals (que hi
            # posa sempre «Festiu local»). La resta de noms son alternatives
            # tolerants per si el portal els torna a canviar.
            nom = (fila.get("nom_del_festiu") or fila.get("nom_festiu")
                   or fila.get("festiu") or fila.get("nom") or "Festiu")
            vistes.add(dia)
            resultat.append((dia, str(nom).strip()[:120], ambit))

    resultat.sort(key=lambda f: f[0])
    return resultat
