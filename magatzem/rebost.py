"""
magatzem/rebost.py — El PORT del magatzem de documents. FITXER CONGELAT.

Tota l'aplicació desa i consulta documents a través d'aquestes vuit
operacions, i de cap altra. Hi ha dos adaptadors que les implementen:

  · RebostMemoria     (aquí)                 proves i desenvolupament
  · RebostFirestore   (rebost_firestore.py)  producció

Per què un port i no cridar Firestore directament: perquè els agents puguin
provar sense cap emulador ni cap connexió, i perquè sortir de Google algun dia
sigui escriure un tercer adaptador i res més. `core/` i `web/` no saben ni que
Firestore existeix; `magatzem/comptes.py` i companyia s'escriuen UNA vegada i
funcionen amb tots dos adaptadors.

La superfície és petita A PROPÒSIT. Si et cal una operació que no hi és, és una
INCIDÈNCIA: afegir-n'hi una vol dir implementar-la bé als dos adaptadors.
"""
from __future__ import annotations

import copy
import os
import threading
from typing import Any, Iterable, Sequence

from core.model import ErrorHorari

# --------------------------------------------------------------------------
# Col·leccions. L'identificador del document és significatiu quan es pot:
# així una lectura per identificador és una crida directa i no una consulta
# (a Firestore, una consulta costa una lectura per document trobat).
# --------------------------------------------------------------------------
PARAMETRES = "parametres"      # id fix: 'config'
SERVEIS = "serveis"            # id automàtic
TREBALLADORS = "treballadors"  # id = login (immutable: el login no es canvia mai)
FESTIUS = "festius"            # id = any en text; un document per any
PATRONS = "patrons"            # id automàtic; els trams van dins del document
ABSENCIES = "absencies"        # id = codi 'A-2026-0001'
SALDOS = "saldos"              # id = '<login>_<any>'
MARCATGES = "marcatges"        # id automàtic (és l'única col·lecció que creix)
COMPTADORS = "comptadors"      # id = clau del comptador
ACTIVITAT = "activitat"        # log d'activitat, amb caducitat automàtica

DOC_CONFIG = "config"

# Operadors admesos als filtres de `consulta`.
OPERADORS = ("==", "<", "<=", ">", ">=", "in", "array_conte")


class ErrorRebost(ErrorHorari):
    """Fallada del magatzem. Hereta d'ErrorHorari perquè les rutes ja el
    mostrin com un avís en català i no com un error 500."""


def _valida_filtres(filtres: Sequence[tuple]) -> None:
    for f in filtres:
        if len(f) != 3 or f[1] not in OPERADORS:
            raise ErrorRebost(
                f"Filtre no admès: {f!r}. Els operadors possibles són {OPERADORS}."
            )


# --------------------------------------------------------------------------
# Adaptador de memòria — proves i desenvolupament
# --------------------------------------------------------------------------
class RebostMemoria:
    """Magatzem de documents en memòria del procés.

    Es queda amb còpies profundes en desar i en llegir: qui rep un document no
    pot modificar el que hi ha desat sense passar per `actualitza`. Sense
    això, un error d'un mòdul es manifestaria com una dada corrupta en un
    altre, que és el pitjor error de trobar."""

    def __init__(self) -> None:
        self._dades: dict[str, dict[str, dict]] = {}
        self._seq = 0
        self._pany = threading.RLock()

    # -- lectura ----------------------------------------------------------
    def doc(self, colleccio: str, id: str) -> dict | None:
        with self._pany:
            trobat = self._dades.get(colleccio, {}).get(str(id))
            return self._amb_id(str(id), trobat) if trobat is not None else None

    def consulta(self, colleccio: str, filtres: Sequence[tuple] = (),
                 ordre: str | None = None, descendent: bool = False,
                 limit: int | None = None) -> list[dict]:
        _valida_filtres(filtres)
        with self._pany:
            resultat = [
                self._amb_id(id, dades)
                for id, dades in self._dades.get(colleccio, {}).items()
                if all(_compleix(dades, *f) for f in filtres)
            ]
        if ordre is not None:
            # Els documents als quals falta el camp van al final, sempre.
            manquen = [d for d in resultat if d.get(ordre) is None]
            tenen = [d for d in resultat if d.get(ordre) is not None]
            tenen.sort(key=lambda d: d[ordre], reverse=descendent)
            resultat = tenen + manquen
        return resultat[:limit] if limit else resultat

    # -- escriptura -------------------------------------------------------
    def desa(self, colleccio: str, id: str, dades: dict) -> None:
        """Substitueix el document sencer (o el crea)."""
        with self._pany:
            self._dades.setdefault(colleccio, {})[str(id)] = _net(dades)

    def actualitza(self, colleccio: str, id: str, camps: dict) -> None:
        """Fusiona els camps amb el document existent. Error si no hi és."""
        with self._pany:
            actual = self._dades.get(colleccio, {}).get(str(id))
            if actual is None:
                raise ErrorRebost(
                    f"No s'ha trobat el document {colleccio}/{id} per actualitzar."
                )
            actual.update(_net(camps))

    def afegeix(self, colleccio: str, dades: dict) -> str:
        """Crea un document amb identificador automàtic i el retorna."""
        with self._pany:
            self._seq += 1
            id = f"auto{self._seq:08d}"
            self._dades.setdefault(colleccio, {})[id] = _net(dades)
            return id

    def esborra(self, colleccio: str, id: str) -> None:
        with self._pany:
            self._dades.get(colleccio, {}).pop(str(id), None)

    def incrementa(self, colleccio: str, id: str, camp: str,
                   quantitat: int = 1) -> int:
        """Increment ATÒMIC d'un comptador; retorna el valor resultant.
        És el mecanisme correcte per als números de seqüència: no hi ha
        finestra entre llegir i escriure."""
        with self._pany:
            doc = self._dades.setdefault(colleccio, {}).setdefault(str(id), {})
            doc[camp] = int(doc.get(camp, 0)) + quantitat
            return doc[camp]

    def lot(self) -> "Lot":
        """Escriptures agrupades que s'apliquen totes alhora o cap."""
        return Lot(self)

    # -- intern -----------------------------------------------------------
    @staticmethod
    def _amb_id(id: str, dades: dict) -> dict:
        copia = copy.deepcopy(dades)
        copia["id"] = id
        return copia

    def _aplica(self, operacions: list[tuple]) -> None:
        with self._pany:
            for accio, colleccio, id, dades in operacions:
                if accio == "desa":
                    self.desa(colleccio, id, dades)
                elif accio == "actualitza":
                    self.actualitza(colleccio, id, dades)
                elif accio == "esborra":
                    self.esborra(colleccio, id)


class Lot:
    """Acumula escriptures i les aplica de cop en sortir del `with`.

    Si el bloc llança una excepció, NO s'aplica res. És el que fa que una
    correcció de marcatge (inserir la fila nova i anul·lar l'antiga) no pugui
    quedar a mitges.

    Limitació coneguda i acceptada: no és una transacció amb lectura. Si dues
    persones modifiquen el mateix document alhora, guanya l'última. Amb 24
    treballadors això no passa a la pràctica, i per als números de seqüència
    hi ha `incrementa`, que sí que és atòmic."""

    def __init__(self, rebost) -> None:
        self._rebost = rebost
        self._operacions: list[tuple] = []
        self._ids_pendents: dict[int, str] = {}

    def desa(self, colleccio: str, id: str, dades: dict) -> None:
        self._operacions.append(("desa", colleccio, str(id), dades))

    def actualitza(self, colleccio: str, id: str, camps: dict) -> None:
        self._operacions.append(("actualitza", colleccio, str(id), camps))

    def esborra(self, colleccio: str, id: str) -> None:
        self._operacions.append(("esborra", colleccio, str(id), None))

    def __enter__(self) -> "Lot":
        return self

    def __exit__(self, tipus, valor, traca) -> bool:
        if tipus is None:
            self._rebost._aplica(self._operacions)
        return False


def _net(dades: dict) -> dict:
    """Còpia profunda sense el camp 'id' (l'identificador viu a la clau del
    document, no a dins: tenir-lo als dos llocs és garantia de desincronia)."""
    copia = copy.deepcopy(dict(dades))
    copia.pop("id", None)
    return copia


def _compleix(dades: dict, camp: str, operador: str, valor: Any) -> bool:
    actual = dades.get(camp)
    if operador == "in":
        return actual in valor
    if operador == "array_conte":
        return isinstance(actual, (list, tuple)) and valor in actual
    if actual is None:
        return False          # com Firestore: sense el camp, no hi entra
    try:
        if operador == "==":
            return actual == valor
        if operador == "<":
            return actual < valor
        if operador == "<=":
            return actual <= valor
        if operador == ">":
            return actual > valor
        if operador == ">=":
            return actual >= valor
    except TypeError:
        return False          # tipus incomparables: no hi entra, no peta
    return False


# --------------------------------------------------------------------------
# Fàbrica
# --------------------------------------------------------------------------
def obre_rebost(mena: str | None = None):
    """Obre l'adaptador que toca.

    `REBOST=memoria` per a proves i desenvolupament sense connexió;
    `REBOST=firestore` a producció. **Sense valor explícit, memòria**: així
    cap prova no pot tocar mai dades de veritat per descuit. El contenidor de
    producció la posa explícitament (vegeu desplegament/FIREBASE.md)."""
    mena = (mena or os.environ.get("REBOST") or "memoria").lower()
    if mena == "memoria":
        return RebostMemoria()
    if mena == "firestore":
        from magatzem.rebost_firestore import RebostFirestore
        return RebostFirestore()
    raise ErrorRebost(f"Magatzem desconegut: {mena!r}. Ha de ser 'memoria' o 'firestore'.")


# --------------------------------------------------------------------------
# Valors inicials
# --------------------------------------------------------------------------
PARAMETRES_INICIALS = {
    "dies_vacances_defecte": 22,
    "dies_ap_defecte": 6,
    "codi_ine_municipi": "43152",       # la Torre de l'Espanyol
    "jornada_maxima_minuts": 600,       # avís d'anomalia per sobre de 10 h
    "pausa_maxima_minuts": 90,
    # Finestra antidoble-toc: dos marcatges seguits mes de pressa que
    # aixo son el mateix toc repetit a la pantalla del mobil.
    "segons_entre_marcatges": 60,
    "nom_ajuntament": "Ajuntament de la Torre de l'Espanyol",
    # Interruptor del fitxador. Ve engegat: aquesta aplicacio es, de
    # naixement, de control horari. Un ajuntament que nomes en vulgui la
    # part de vacances i permisos l'apaga des de Configuracio, i llavors
    # les pantalles de fitxar, hores i informes deixen d'existir. Apagar
    # NO esborra res: els marcatges que hi hagi es queden on son.
    "fitxatge_actiu": True,
}


def inicialitza(rebost) -> None:
    """Deixa el magatzem a punt per fer-se servir. Idempotent: es crida a
    cada arrencada i no pisa mai cap valor que l'administrador hagi canviat."""
    config = rebost.doc(PARAMETRES, DOC_CONFIG) or {}
    a_afegir = {c: v for c, v in PARAMETRES_INICIALS.items() if c not in config}
    if a_afegir:
        if config:
            rebost.actualitza(PARAMETRES, DOC_CONFIG, a_afegir)
        else:
            rebost.desa(PARAMETRES, DOC_CONFIG, a_afegir)
