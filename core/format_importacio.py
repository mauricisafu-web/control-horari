"""
core/format_importacio.py — Contracte del fitxer d'importació. CONGELAT.

Vocabulari comú entre l'exportador (que viu al costat de nòmines) i la
càrrega (que viu al control horari). Cap agent el modifica: si hi falta
alguna cosa, és una INCIDÈNCIA.

Vegeu `desplegament/INTEGRACIO_NOMINES.md` per al perquè de cada decisió.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# --------------------------------------------------------------------------
# Format del fitxer
# --------------------------------------------------------------------------
SEPARADOR = ";"
CODIFICACIO = "utf-8-sig"      # amb BOM: l'Excel l'obre bé sense fer res

COLUMNES_OBLIGATORIES = ("usuari", "nom", "correu")
COLUMNES_OPCIONALS = ("servei", "rol", "data_alta", "contrasenya")
COLUMNES = COLUMNES_OBLIGATORIES + COLUMNES_OPCIONALS

# --------------------------------------------------------------------------
# Accions que pot proposar una càrrega
# --------------------------------------------------------------------------
CREAR = "crear"
ACTUALITZAR = "actualitzar"
SENSE_CANVIS = "sense_canvis"
BAIXA = "baixa"                # NOMÉS proposta: mai s'aplica sense confirmar
ERROR = "error"

ETIQUETA_ACCIO = {
    CREAR: "Crear",
    ACTUALITZAR: "Actualitzar",
    SENSE_CANVIS: "Sense canvis",
    BAIXA: "Ja no surt al fitxer",
    ERROR: "Error",
}


@dataclass(frozen=True)
class FilaImportada:
    """Una fila del CSV, ja validada i convertida."""
    linia: int                       # número de línia al fitxer, per als errors
    usuari: str
    nom: str
    correu: str
    servei: str | None = None        # NOM del servei, no identificador
    rol: str = "treballador"
    data_alta: date | None = None
    contrasenya: str | None = None   # només s'usa si el compte és NOU


@dataclass(frozen=True)
class Proposta:
    """Què es faria amb una persona. La previsualització n'ensenya una llista."""
    accio: str
    login: str
    nom: str
    detall: str = ""                 # explicació en català, per ensenyar
    fila: FilaImportada | None = None
    servei_id: str | None = None     # ja resolt del nom al identificador


@dataclass(frozen=True)
class Pla:
    """El resultat de la previsualització."""
    propostes: tuple[Proposta, ...] = ()

    def _de(self, accio: str) -> tuple[Proposta, ...]:
        return tuple(p for p in self.propostes if p.accio == accio)

    @property
    def crear(self): return self._de(CREAR)

    @property
    def actualitzar(self): return self._de(ACTUALITZAR)

    @property
    def sense_canvis(self): return self._de(SENSE_CANVIS)

    @property
    def baixes(self): return self._de(BAIXA)

    @property
    def errors(self): return self._de(ERROR)

    @property
    def hi_ha_res_a_fer(self) -> bool:
        return bool(self.crear or self.actualitzar)
