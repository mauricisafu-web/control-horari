"""
core/importa.py — Analitza el fitxer de treballadors i calcula què s'hi faria.

Funcions PURES: no llegeixen fitxers del disc, no toquen el magatzem, no
saben quin dia és. Reben text i llistes, retornen un `Pla`. Es proven sense
servidor.

Qui aplica el pla és `web/configuracio.py`; qui el genera, aquest mòdul.

ESTAT: signatures congelades pel contracte. Els cossos els implementa l'agent
INT-A (vegeu `encarrecs/INT-A-analitzador.md`).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date
from typing import Mapping, Sequence

from core.format_importacio import (
    ACTUALITZAR, BAIXA, COLUMNES_OBLIGATORIES, CREAR, ERROR, SENSE_CANVIS,
    SEPARADOR, FilaImportada, Pla, Proposta,
)
from core.model import ETIQUETA_ROL, ROLS, ROL_TREBALLADOR, Treballador

# La data d'alta s'exigeix en ISO estricte. `date.fromisoformat` accepta més
# formes (per exemple «20260101») i aquí no les volem: qui munta el fitxer ha
# d'escriure AAAA-MM-DD, que és el que diu la capçalera.
_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------
# Utilitats internes
# --------------------------------------------------------------------------
def _text(valor) -> str:
    """El contingut d'una cel·la, net. El mòdul `csv` dona `None` quan la fila
    té menys camps que la capçalera, i una llista per als camps de més."""
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        valor = SEPARADOR.join(str(v) for v in valor if v)
    return str(valor).strip()


def _clau_columna(nom: str) -> str:
    """Nom de columna comparable: sense BOM, sense espais i en minúscules."""
    return (nom or "").replace("\ufeff", "").strip().lower()


def _data_vista(dia: date | None) -> str:
    """Una data per ensenyar a la persona: dd/mm/aaaa, o «(cap)» si no n'hi ha."""
    return dia.strftime("%d/%m/%Y") if dia else "(cap)"


def _login_de(treballador: Treballador) -> str:
    """El login amb què es compara un compte existent amb una fila del fitxer."""
    return (treballador.login or treballador.id or "").strip().lower()


def normalitza_nom_servei(nom: str) -> str:
    """Clau de comparació d'un nom de servei: sense accents, minúscules i
    sense espais sobrers, perquè «Oficines» i «oficines » siguin el mateix."""
    descompost = unicodedata.normalize("NFKD", (nom or "").strip().lower())
    sense_accents = "".join(c for c in descompost if not unicodedata.combining(c))
    # `split()` sense argument parteix per qualsevol espai i n'ignora els
    # repetits: «  Serveis   Socials » i «serveis socials» acaben igual.
    return " ".join(sense_accents.split())


def analitza(contingut: str) -> tuple[list[FilaImportada], list[Proposta]]:
    """Llegeix el CSV sencer i retorna (files vàlides, propostes d'ERROR).

    Una fila dolenta NO atura la importació: es reporta i la resta continua.
    Si falta una columna obligatòria a la capçalera, això sí que és fatal i
    es retorna un únic error explicant-ho."""
    files: list[FilaImportada] = []
    errors: list[Proposta] = []

    # El fitxer arriba com a text ja descodificat. Si qui l'ha llegit no ha
    # fet servir `utf-8-sig`, el BOM encara hi és i embrutaria la primera
    # columna: es treu aquí i s'acaba el problema.
    text = (contingut or "").lstrip("\ufeff")
    lector = csv.DictReader(io.StringIO(text, newline=""), delimiter=SEPARADOR)

    capcalera = lector.fieldnames
    if not capcalera:
        errors.append(Proposta(
            accio=ERROR, login="", nom="",
            detall="El fitxer és buit: hi falta la capçalera amb les columnes "
                   + ", ".join(COLUMNES_OBLIGATORIES) + "."))
        return [], errors

    lector.fieldnames = [_clau_columna(c) for c in capcalera]
    falten = [c for c in COLUMNES_OBLIGATORIES if c not in lector.fieldnames]
    if falten:
        quines = ", ".join(f"«{c}»" for c in falten)
        detall = (f"A la capçalera del fitxer hi falta la columna obligatòria {quines}."
                  if len(falten) == 1 else
                  f"A la capçalera del fitxer hi falten les columnes obligatòries {quines}.")
        errors.append(Proposta(accio=ERROR, login="", nom="", detall=detall))
        return [], errors

    # {clau: línia on va sortir}, per poder dir a l'usuari on és el duplicat.
    usuaris_vistos: dict[str, int] = {}
    correus_vistos: dict[str, int] = {}

    for cru in lector:
        # `line_num` és la línia REAL del fitxer (capçalera = 1) i compta bé
        # els camps entre cometes que ocupen més d'una línia.
        linia = lector.line_num

        # Una fila totalment buida (per exemple «;;;» al final del full) no és
        # un error de ningú: se salta en silenci.
        if not any(_text(v) for v in cru.values()):
            continue

        problemes: list[str] = []

        usuari = "".join(_text(cru.get("usuari")).lower().split())
        nom = _text(cru.get("nom"))
        correu = _text(cru.get("correu"))
        servei = _text(cru.get("servei")) or None
        rol = _text(cru.get("rol")).lower() or ROL_TREBALLADOR
        cru_data = _text(cru.get("data_alta"))
        cru_contrasenya = cru.get("contrasenya")
        # La contrasenya no es toca (els espais hi podrien ser a propòsit);
        # només es decideix si n'hi ha o no.
        contrasenya = (cru_contrasenya if isinstance(cru_contrasenya, str)
                       and cru_contrasenya.strip() else None)

        if not usuari:
            problemes.append("hi falta l'usuari")
        elif usuari in usuaris_vistos:
            problemes.append(f"l'usuari «{usuari}» ja surt a la línia "
                             f"{usuaris_vistos[usuari]}")
        if not nom:
            problemes.append("hi falta el nom")
        if not correu:
            problemes.append("hi falta el correu")
        elif correu.lower() in correus_vistos:
            problemes.append(f"el correu «{correu}» ja surt a la línia "
                             f"{correus_vistos[correu.lower()]}")
        if rol not in ROLS:
            problemes.append(f"el rol «{rol}» no és cap dels vàlids "
                             f"({', '.join(ROLS)})")

        data_alta = None
        if cru_data:
            try:
                if not _DATA_ISO.match(cru_data):
                    raise ValueError
                data_alta = date.fromisoformat(cru_data)
            except ValueError:
                problemes.append(f"la data d'alta «{cru_data}» no té el format "
                                 "AAAA-MM-DD")

        fila = FilaImportada(linia=linia, usuari=usuari, nom=nom, correu=correu,
                             servei=servei, rol=rol, data_alta=data_alta,
                             contrasenya=contrasenya)

        if problemes:
            # La fila s'adjunta encara que sigui incorrecta: és l'única manera
            # que la pantalla pugui dir en quina línia del fitxer mirar.
            errors.append(Proposta(
                accio=ERROR, login=usuari, nom=nom, fila=fila,
                detall=f"Línia {linia}: " + "; ".join(problemes) + "."))
            continue

        usuaris_vistos[usuari] = linia
        correus_vistos[correu.lower()] = linia
        files.append(fila)

    return files, errors


def _detall_creacio(fila: FilaImportada, nom_servei: str | None) -> str:
    """Què es crearà, en una frase que es pugui ensenyar tal qual."""
    parts = [f"rol {ETIQUETA_ROL.get(fila.rol, fila.rol)}"]
    parts.append(f"servei {nom_servei}" if nom_servei else "sense servei assignat")
    if fila.data_alta:
        parts.append(f"data d'alta {_data_vista(fila.data_alta)}")
    return (f"Es crearà el compte «{fila.usuari}» per a {fila.nom} "
            f"({fila.correu}): " + ", ".join(parts) + ".")


def _canvis(actual: Treballador, fila: FilaImportada, servei_id: str | None,
            nom_servei: str | None, noms_per_id: Mapping[str, str]) -> list[str]:
    """Llista, en català, de què canviaria d'un compte que ja existeix."""
    canvis: list[str] = []

    if not actual.actiu:
        canvis.append("es reactivarà el compte, que estava donat de baixa")
    if fila.nom and fila.nom != (actual.nom or ""):
        canvis.append(f"nom: {actual.nom or '(cap)'} -> {fila.nom}")
    # Un servei buit al fitxer NO esborra el que ja hi ha: és la regla del
    # format («Buit = no es toca»).
    if servei_id is not None and servei_id != actual.servei_id:
        anterior = noms_per_id.get(actual.servei_id) or actual.servei or "(cap)"
        canvis.append(f"servei: {anterior} -> {nom_servei}")
    if fila.rol != actual.rol:
        canvis.append(f"rol: {ETIQUETA_ROL.get(actual.rol, actual.rol)} -> "
                      f"{ETIQUETA_ROL.get(fila.rol, fila.rol)}")
    if fila.data_alta is not None and fila.data_alta != actual.data_alta:
        canvis.append(f"data d'alta: {_data_vista(actual.data_alta)} -> "
                      f"{_data_vista(fila.data_alta)}")
    return canvis


def calcula_pla(files: Sequence[FilaImportada],
                existents: Sequence[Treballador],
                serveis: Mapping[str, str],
                errors: Sequence[Proposta] = ()) -> Pla:
    """Compara el que ve al fitxer amb el que ja hi ha i decideix.

    `serveis` és {nom del servei: identificador}; les claus es comparen
    normalitzades. Un servei que no existeix és un ERROR de la fila, no una
    creació silenciosa: crear serveis és una decisió d'administració.

    Les persones que són a `existents` i NO al fitxer surten com a BAIXA, que
    és una PROPOSTA: no s'aplica mai sense que l'administrador la confirmi
    una per una."""
    propostes: list[Proposta] = list(errors)

    per_clau: dict[str, tuple[str, str]] = {}
    noms_per_id: dict[str, str] = {}
    for nom_servei, servei_id in (serveis or {}).items():
        per_clau[normalitza_nom_servei(nom_servei)] = (nom_servei, servei_id)
        noms_per_id.setdefault(servei_id, nom_servei)

    existents_per_login = {_login_de(t): t for t in (existents or ())}

    # Qui surt al fitxer, encara que la seva fila acabi en error: si algú s'ha
    # equivocat escrivint el servei d'una persona, no li proposem la baixa.
    al_fitxer = {p.login for p in errors if p.login}

    for fila in files:
        login = fila.usuari
        al_fitxer.add(login)

        servei_id = nom_servei = None
        if fila.servei:
            trobat = per_clau.get(normalitza_nom_servei(fila.servei))
            if trobat is None:
                propostes.append(Proposta(
                    accio=ERROR, login=login, nom=fila.nom, fila=fila,
                    detall=f"Línia {fila.linia}: el servei «{fila.servei}» no "
                           "existeix al control horari. Crea'l primer a "
                           "Configuració i torna a carregar el fitxer."))
                continue
            nom_servei, servei_id = trobat

        actual = existents_per_login.get(login)
        if actual is None:
            propostes.append(Proposta(
                accio=CREAR, login=login, nom=fila.nom, fila=fila,
                servei_id=servei_id, detall=_detall_creacio(fila, nom_servei)))
            continue

        canvis = _canvis(actual, fila, servei_id, nom_servei, noms_per_id)
        if canvis:
            propostes.append(Proposta(
                accio=ACTUALITZAR, login=login, nom=fila.nom, fila=fila,
                servei_id=servei_id if servei_id is not None else actual.servei_id,
                detall="; ".join(canvis) + "."))
        else:
            propostes.append(Proposta(
                accio=SENSE_CANVIS, login=login, nom=actual.nom, fila=fila,
                servei_id=actual.servei_id,
                detall="Tot coincideix amb el que ja hi ha."))

    # Un fitxer que no s'ha pogut llegir (capçalera invàlida, fitxer buit) NO
    # pot proposar la baixa de tothom: seria un CSV mal exportat convertint-se
    # en la desactivació de tota la plantilla d'un sol clic. Sense cap fila
    # vàlida, no es proposa cap baixa.
    if not files:
        return Pla(propostes=tuple(propostes))

    for treballador in (existents or ()):
        if not treballador.actiu or _login_de(treballador) in al_fitxer:
            continue
        propostes.append(Proposta(
            accio=BAIXA, login=treballador.login, nom=treballador.nom,
            detall="Ja no surt al fitxer. Si ho confirmes, se li posarà data de "
                   "baixa i el compte quedarà desactivat; els marcatges es "
                   "conserven."))

    return Pla(propostes=tuple(propostes))
