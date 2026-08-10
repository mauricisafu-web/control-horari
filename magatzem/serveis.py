"""magatzem/serveis.py — Els serveis de l'ajuntament (Oficines, Brigada…)."""
from __future__ import annotations

from core.model import ErrorHorari
from magatzem.rebost import SERVEIS


def llista(mag) -> list[dict]:
    return sorted(mag.consulta(SERVEIS), key=lambda s: s.get("nom", ""))


def noms(mag) -> dict[str, str]:
    """{id: nom}. Una sola consulta; els blueprints la fan servir per no
    demanar el nom d'un servei una vegada per fila."""
    return {s["id"]: s.get("nom", "") for s in mag.consulta(SERVEIS)}


def per_id(mag, servei_id: str) -> dict | None:
    return mag.doc(SERVEIS, servei_id) if servei_id else None


def crea(mag, nom: str, color: str = "#1e4078") -> str:
    nom = (nom or "").strip()
    if not nom:
        raise ErrorHorari("El servei ha de tenir un nom.")
    if any(s.get("nom", "").lower() == nom.lower() for s in mag.consulta(SERVEIS)):
        raise ErrorHorari(f"Ja hi ha un servei que es diu «{nom}».")
    return mag.afegeix(SERVEIS, {"nom": nom, "color": color or "#1e4078"})


def desa(mag, servei_id: str, nom: str, color: str) -> None:
    if not mag.doc(SERVEIS, servei_id):
        raise ErrorHorari("Aquest servei no existeix.")
    mag.actualitza(SERVEIS, servei_id, {"nom": (nom or "").strip(),
                                        "color": color or "#1e4078"})


def elimina(mag, servei_id: str, treballadors_assignats: int = 0) -> None:
    """No s'esborra un servei que encara té gent: quedarien fitxes penjades
    apuntant a un servei que no existeix."""
    if treballadors_assignats:
        raise ErrorHorari(
            f"No pots esborrar aquest servei: encara hi ha "
            f"{treballadors_assignats} treballadors assignats.")
    mag.esborra(SERVEIS, servei_id)
