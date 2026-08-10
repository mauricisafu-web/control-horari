"""
magatzem/comptes.py — Comptes i fitxes dels treballadors.

L'identificador del document ÉS el login: llegir un compte és una crida
directa (una lectura), no una consulta amb filtre. Per això el login no es
canvia mai.

Dins del mateix document hi viuen també els àmbits d'aprovació i les
assignacions d'horari: són poques i sempre es llegeixen amb el treballador,
o sigui que agrupar-les estalvia lectures.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from core.model import (
    Assignacio, ErrorHorari, Patro, ROLS, Treballador, ara_utc,
)
from magatzem import horaris, serveis as mag_serveis
from magatzem.conversio import a_data, de_data, de_moment
from magatzem.rebost import TREBALLADORS

# Els ÚNICS camps que `actualitza` deixa tocar. Mai s'hi passa directament el
# que arriba d'un formulari.
CAMPS_MODIFICABLES = frozenset({
    "nom", "correu", "correu_norm", "rol", "servei_id", "data_alta",
    "data_baixa", "actiu", "canvi_pendent", "hash_contrasenya",
    "totp_secret", "totp_actiu", "ultim_acces", "ambits", "assignacions",
    "codis_recuperacio",
})


def _a_treballador(doc: dict, noms_servei: dict | None = None) -> Treballador:
    servei_id = doc.get("servei_id")
    return Treballador(
        id=doc["id"], login=doc.get("login", doc["id"]),
        nom=doc.get("nom", ""), correu=doc.get("correu", ""),
        rol=doc.get("rol", "treballador"),
        servei_id=servei_id,
        servei=(noms_servei or {}).get(servei_id),
        data_alta=a_data(doc.get("data_alta")),
        data_baixa=a_data(doc.get("data_baixa")),
        actiu=bool(doc.get("actiu", True)),
        totp_actiu=bool(doc.get("totp_actiu", False)),
    )


def per_login(mag, login: str) -> Treballador | None:
    doc = mag.doc(TREBALLADORS, login) if login else None
    return _a_treballador(doc, mag_serveis.noms(mag)) if doc else None


def per_correu(mag, correu: str) -> Treballador | None:
    net = (correu or "").strip().lower()
    if not net:
        return None
    trobats = mag.consulta(TREBALLADORS, [("correu_norm", "==", net)], limit=1)
    return _a_treballador(trobats[0], mag_serveis.noms(mag)) if trobats else None


def hash_de(mag, login: str) -> str | None:
    doc = mag.doc(TREBALLADORS, login) if login else None
    return doc.get("hash_contrasenya") if doc else None


def document(mag, login: str) -> dict | None:
    """El document cru. Només per a l'autenticació (secret TOTP, codis de
    recuperació): la resta de l'aplicació treballa amb `Treballador`."""
    return mag.doc(TREBALLADORS, login) if login else None


def llista(mag, actius: bool = True, servei_id: str | None = None
           ) -> list[Treballador]:
    filtres = []
    if actius:
        filtres.append(("actiu", "==", True))
    if servei_id:
        filtres.append(("servei_id", "==", servei_id))
    noms = mag_serveis.noms(mag)
    trobats = [_a_treballador(d, noms) for d in mag.consulta(TREBALLADORS, filtres)]
    return sorted(trobats, key=lambda t: t.nom.lower())


def de_serveis(mag, ambits: Sequence[str]) -> list[Treballador]:
    """Els treballadors dels serveis d'un àmbit. Amb `'*'`, tots."""
    from core.model import AMBIT_TOTS
    if AMBIT_TOTS in (ambits or ()):
        return llista(mag)
    tots = llista(mag)
    return [t for t in tots if t.servei_id in set(ambits or ())]


def crea(mag, login: str, nom: str, correu: str, hash_contrasenya: str,
         rol: str, servei_id: str | None = None,
         data_alta: date | None = None) -> str:
    login = (login or "").strip().lower()
    if not login:
        raise ErrorHorari("Cal un nom d'usuari.")
    if rol not in ROLS:
        raise ErrorHorari("El rol no és vàlid.")
    if mag.doc(TREBALLADORS, login):
        raise ErrorHorari(f"Ja hi ha un compte que es diu «{login}».")
    if per_correu(mag, correu):
        raise ErrorHorari(f"Ja hi ha un compte amb el correu «{correu}».")

    mag.desa(TREBALLADORS, login, {
        "login": login, "nom": (nom or "").strip(),
        "correu": (correu or "").strip(),
        "correu_norm": (correu or "").strip().lower(),
        "hash_contrasenya": hash_contrasenya, "rol": rol,
        "servei_id": servei_id,
        "data_alta": de_data(data_alta), "data_baixa": None,
        "actiu": True, "canvi_pendent": True,
        "totp_secret": None, "totp_actiu": False,
        "creat_el": de_moment(ara_utc()), "ultim_acces": None,
        "ambits": [], "assignacions": [], "codis_recuperacio": [],
    })
    return login


def actualitza(mag, login: str, **camps) -> None:
    desconeguts = set(camps) - CAMPS_MODIFICABLES
    if desconeguts:
        raise ErrorHorari(f"Camps que no es poden modificar: {sorted(desconeguts)}")
    if "correu" in camps:
        camps["correu_norm"] = (camps["correu"] or "").strip().lower()
    for clau in ("data_alta", "data_baixa"):
        if clau in camps and isinstance(camps[clau], date):
            camps[clau] = de_data(camps[clau])
    mag.actualitza(TREBALLADORS, login, camps)


def desactiva(mag, login: str, data_baixa: date | None = None) -> None:
    """Mai s'esborra un compte: el registre de jornada s'ha de conservar
    quatre anys i els marcatges hi apunten."""
    actualitza(mag, login, actiu=False, data_baixa=de_data(data_baixa))


def ambits_de(mag, login: str) -> list[str]:
    """Serveis que pot aprovar. Conté `'*'` (model.AMBIT_TOTS) si els té tots.

    És una comprovació de SEGURETAT: els blueprints hi confien per decidir
    què pot veure cadascú."""
    doc = mag.doc(TREBALLADORS, login) or {}
    return list(doc.get("ambits") or [])


def desa_ambits(mag, login: str, serveis: Sequence[str]) -> None:
    mag.actualitza(TREBALLADORS, login, {"ambits": list(serveis or [])})


# -- horari assignat --------------------------------------------------------
def assignacions_de(mag, login: str,
                    patrons: dict[str, Patro] | None = None) -> list[Assignacio]:
    """Amb el `Patro` sencer a dins, ordenades per data d'inici.

    Els patrons es llegeixen UNA vegada i es reutilitzen: demanar-ne un per
    assignació multiplicaria les lectures sense cap motiu."""
    doc = mag.doc(TREBALLADORS, login) or {}
    brutes = doc.get("assignacions") or []
    if not brutes:
        return []
    if patrons is None:
        patrons = {p.id: p for p in horaris.patrons(mag)}

    resultat = []
    for i, a in enumerate(brutes):
        patro = patrons.get(a.get("patro_id"))
        if patro is None:
            continue          # patró esborrat: l'assignació s'ignora
        inici = a_data(a.get("data_inici"))
        if inici is None:
            continue
        resultat.append(Assignacio(
            patro=patro, data_inici=inici, data_fi=a_data(a.get("data_fi")),
            coeficient=int(a.get("coeficient", 100)), id=str(i)))
    return sorted(resultat, key=lambda a: a.data_inici)


def assigna(mag, login: str, patro_id: str, data_inici: date,
            data_fi: date | None = None, coeficient: int = 100) -> None:
    if not mag.doc(horaris.PATRONS, patro_id):
        raise ErrorHorari("Aquest patró d'horari no existeix.")
    if not 1 <= int(coeficient) <= 100:
        raise ErrorHorari("El percentatge de jornada ha d'anar de 1 a 100.")
    doc = mag.doc(TREBALLADORS, login)
    if not doc:
        raise ErrorHorari("Aquest treballador no existeix.")
    llistat = list(doc.get("assignacions") or [])
    llistat.append({"patro_id": patro_id, "data_inici": de_data(data_inici),
                    "data_fi": de_data(data_fi), "coeficient": int(coeficient)})
    mag.actualitza(TREBALLADORS, login, {"assignacions": llistat})


def desassigna(mag, login: str, index: int) -> None:
    doc = mag.doc(TREBALLADORS, login) or {}
    llistat = list(doc.get("assignacions") or [])
    if not 0 <= index < len(llistat):
        raise ErrorHorari("Aquesta assignació no existeix.")
    llistat.pop(index)
    mag.actualitza(TREBALLADORS, login, {"assignacions": llistat})


# -- codis de recuperació del TOTP ------------------------------------------
def codis_recuperacio(mag, login: str) -> list[dict]:
    doc = mag.doc(TREBALLADORS, login) or {}
    return list(doc.get("codis_recuperacio") or [])


def desa_codis_recuperacio(mag, login: str, codis: Sequence[dict]) -> None:
    mag.actualitza(TREBALLADORS, login, {"codis_recuperacio": list(codis)})
