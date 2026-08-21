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

from typing import Mapping, Sequence

from core.format_importacio import FilaImportada, Pla, Proposta
from core.model import Treballador


def normalitza_nom_servei(nom: str) -> str:
    """Clau de comparació d'un nom de servei: sense accents, minúscules i
    sense espais sobrers, perquè «Oficines» i «oficines » siguin el mateix."""
    raise NotImplementedError


def analitza(contingut: str) -> tuple[list[FilaImportada], list[Proposta]]:
    """Llegeix el CSV sencer i retorna (files vàlides, propostes d'ERROR).

    Una fila dolenta NO atura la importació: es reporta i la resta continua.
    Si falta una columna obligatòria a la capçalera, això sí que és fatal i
    es retorna un únic error explicant-ho."""
    raise NotImplementedError


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
    raise NotImplementedError
