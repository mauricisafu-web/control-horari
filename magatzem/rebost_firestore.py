"""
magatzem/rebost_firestore.py — Adaptador de Firestore. FITXER CONGELAT.

Implementa exactament el mateix port que `RebostMemoria` (vegeu `rebost.py`).
Si un dia les dues implementacions divergeixen, els tests passaran i
producció fallarà: per això la superfície és mínima i per això
`tests/test_rebost.py` (agent 1A) ha de provar les DUES amb el MATEIX joc de
proves.

Notes de Firestore que expliquen les decisions d'aquest fitxer:

· **Cada document que retorna una consulta és una lectura facturada.** El
  nivell gratuït permanent són 50.000 lectures al dia, que amb 24
  treballadors sobra molt — però només si no es fan consultes que arrosseguin
  col·leccions senceres. D'aquí que els identificadors siguin significatius
  (el login, la data, el codi) i que els festius i els saldos vagin en un sol
  document per any: llegir-los és UNA lectura, no cinquanta.

· **Les consultes amb desigualtat només poden ser sobre UN camp.** Per això
  `marcatges` es consulta per `treballador_id ==` + `data >= <=`, mai per dos
  rangs alhora.

· **Els índexs compostos s'han de declarar** a `firestore.indexes.json`
  (agent 2C). Sense l'índex, la consulta falla en producció amb un enllaç per
  crear-lo. Els necessaris estan documentats a DISSENY.md §5.

· **L'SDK d'administrador se salta les regles de seguretat.** Les regles han
  de ser «denega-ho tot»: cap navegador parla mai amb Firestore directament,
  tota l'autorització viu al servidor, a `web/`. Vegeu FIREBASE.md §4.
"""
from __future__ import annotations

import os

from magatzem.rebost import ErrorRebost, Lot, _valida_filtres

# Traducció dels operadors del port als de Firestore.
_OPERADORS = {
    "==": "==", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
    "in": "in", "array_conte": "array_contains",
}


class RebostFirestore:
    """Adaptador de producció. Un sol client per procés (obrir-ne un per
    petició costaria una connexió gRPC nova cada vegada)."""

    def __init__(self, client=None) -> None:
        if client is not None:
            self._db = client
            return
        try:
            from google.cloud import firestore
        except ImportError as e:      # pragma: sense cobertura
            raise ErrorRebost(
                "Falta la biblioteca google-cloud-firestore. Instal·la les "
                "dependències amb `pip install -r requirements.txt`."
            ) from e
        projecte = os.environ.get("PROJECTE_FIREBASE")
        base = os.environ.get("BASE_FIRESTORE", "(default)")
        # Amb FIRESTORE_EMULATOR_HOST definida, el client hi va sol: és el
        # que fa que les proves d'integració no toquin dades de veritat.
        self._db = (firestore.Client(project=projecte, database=base)
                    if projecte else firestore.Client(database=base))

    # -- lectura ----------------------------------------------------------
    def doc(self, colleccio: str, id: str) -> dict | None:
        instantania = self._db.collection(colleccio).document(str(id)).get()
        if not instantania.exists:
            return None
        return self._amb_id(instantania)

    def consulta(self, colleccio: str, filtres=(), ordre: str | None = None,
                 descendent: bool = False, limit: int | None = None) -> list[dict]:
        _valida_filtres(filtres)
        from google.cloud.firestore_v1.base_query import FieldFilter

        consulta = self._db.collection(colleccio)
        for camp, operador, valor in filtres:
            consulta = consulta.where(
                filter=FieldFilter(camp, _OPERADORS[operador], valor))
        if ordre is not None:
            from google.cloud import firestore
            direccio = (firestore.Query.DESCENDING if descendent
                        else firestore.Query.ASCENDING)
            consulta = consulta.order_by(ordre, direction=direccio)
        if limit:
            consulta = consulta.limit(limit)
        return [self._amb_id(d) for d in consulta.stream()]

    # -- escriptura -------------------------------------------------------
    def desa(self, colleccio: str, id: str, dades: dict) -> None:
        self._db.collection(colleccio).document(str(id)).set(_net(dades))

    def actualitza(self, colleccio: str, id: str, camps: dict) -> None:
        from google.api_core.exceptions import NotFound
        try:
            self._db.collection(colleccio).document(str(id)).update(_net(camps))
        except NotFound as e:
            raise ErrorRebost(
                f"No s'ha trobat el document {colleccio}/{id} per actualitzar."
            ) from e

    def afegeix(self, colleccio: str, dades: dict) -> str:
        referencia = self._db.collection(colleccio).document()
        referencia.set(_net(dades))
        return referencia.id

    def esborra(self, colleccio: str, id: str) -> None:
        self._db.collection(colleccio).document(str(id)).delete()

    def incrementa(self, colleccio: str, id: str, camp: str,
                   quantitat: int = 1) -> int:
        """Increment atòmic al servidor (`firestore.Increment`): dues
        peticions simultànies MAI no obtenen el mateix número. És el que
        garanteix que no hi hagi dos codis d'absència repetits."""
        from google.cloud import firestore
        referencia = self._db.collection(colleccio).document(str(id))
        referencia.set({camp: firestore.Increment(quantitat)}, merge=True)
        return int(referencia.get().to_dict()[camp])

    def lot(self) -> Lot:
        return Lot(self)

    # -- intern -----------------------------------------------------------
    @staticmethod
    def _amb_id(instantania) -> dict:
        dades = instantania.to_dict() or {}
        dades["id"] = instantania.id
        return dades

    def _aplica(self, operacions: list[tuple]) -> None:
        """Aplica les escriptures d'un `Lot` amb un WriteBatch: totes o cap."""
        if not operacions:
            return
        lot = self._db.batch()
        for accio, colleccio, id, dades in operacions:
            referencia = self._db.collection(colleccio).document(str(id))
            if accio == "desa":
                lot.set(referencia, _net(dades))
            elif accio == "actualitza":
                lot.update(referencia, _net(dades))
            elif accio == "esborra":
                lot.delete(referencia)
        lot.commit()


def _net(dades: dict) -> dict:
    """Treu el camp 'id': l'identificador viu a la clau del document."""
    copia = dict(dades)
    copia.pop("id", None)
    return copia
