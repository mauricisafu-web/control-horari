"""
Proves del PORT del magatzem.

El MATEIX joc de proves corre contra els dos adaptadors. És el que tanca el
risc estructural del projecte: les proves van contra memòria i producció
contra Firestore, i una divergència entre els dos passaria desapercebuda.

El de Firestore s'omet si no hi ha emulador (`FIRESTORE_EMULATOR_HOST`), que
és el cas normal fins a l'onada 5.
"""
from __future__ import annotations

import os

import pytest

from core.model import ErrorHorari
from magatzem import rebost as reb

COL = "proves"


def _fes_rebost(mena):
    if mena == "memoria":
        return reb.RebostMemoria()
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        pytest.skip("sense emulador de Firestore (s'engega a l'onada 5)")
    from magatzem.rebost_firestore import RebostFirestore
    return RebostFirestore()


@pytest.fixture(params=["memoria", "firestore"])
def r(request):
    magatzem = _fes_rebost(request.param)
    yield magatzem
    for doc in magatzem.consulta(COL):
        magatzem.esborra(COL, doc["id"])


def test_document_inexistent_dona_none(r):
    assert r.doc(COL, "no-hi-soc") is None


def test_desa_i_llegeix(r):
    r.desa(COL, "a", {"nom": "Anna", "edat": 30})
    doc = r.doc(COL, "a")
    assert doc["nom"] == "Anna" and doc["id"] == "a"


def test_l_identificador_no_es_desa_dins_del_document(r):
    """L'id viu a la clau del document; tenir-lo als dos llocs seria garantia
    de desincronia."""
    r.desa(COL, "a", {"id": "un-altre", "nom": "Anna"})
    assert r.doc(COL, "a")["id"] == "a"


def test_desa_substitueix_el_document_sencer(r):
    r.desa(COL, "a", {"nom": "Anna", "edat": 30})
    r.desa(COL, "a", {"nom": "Berta"})
    assert "edat" not in r.doc(COL, "a")


def test_actualitza_fusiona(r):
    r.desa(COL, "a", {"nom": "Anna", "edat": 30})
    r.actualitza(COL, "a", {"edat": 31})
    doc = r.doc(COL, "a")
    assert doc["nom"] == "Anna" and doc["edat"] == 31


def test_actualitza_un_document_inexistent_dona_error(r):
    with pytest.raises(ErrorHorari):
        r.actualitza(COL, "no-hi-soc", {"nom": "x"})


def test_afegeix_genera_identificador(r):
    id1 = r.afegeix(COL, {"nom": "Anna"})
    id2 = r.afegeix(COL, {"nom": "Berta"})
    assert id1 != id2 and r.doc(COL, id1)["nom"] == "Anna"


def test_esborra(r):
    r.desa(COL, "a", {"nom": "Anna"})
    r.esborra(COL, "a")
    assert r.doc(COL, "a") is None


def test_esborrar_el_que_no_hi_es_no_peta(r):
    r.esborra(COL, "no-hi-soc")


@pytest.mark.parametrize("operador,valor,esperats", [
    ("==", 30, {"a"}),
    ("<", 30, {"c"}),
    ("<=", 30, {"a", "c"}),
    (">", 30, {"b"}),
    (">=", 30, {"a", "b"}),
    ("in", [25, 40], {"b", "c"}),
])
def test_els_operadors_de_filtre(r, operador, valor, esperats):
    r.desa(COL, "a", {"edat": 30})
    r.desa(COL, "b", {"edat": 40})
    r.desa(COL, "c", {"edat": 25})
    trobats = {d["id"] for d in r.consulta(COL, [("edat", operador, valor)])}
    assert trobats == esperats


def test_filtre_array_conte(r):
    r.desa(COL, "a", {"ambits": ["s1", "s2"]})
    r.desa(COL, "b", {"ambits": ["s3"]})
    trobats = {d["id"] for d in r.consulta(COL, [("ambits", "array_conte", "s1")])}
    assert trobats == {"a"}


def test_un_operador_inventat_es_rebutja(r):
    with pytest.raises(ErrorHorari):
        r.consulta(COL, [("edat", "~=", 30)])


def test_ordenacio_i_limit(r):
    for id, edat in (("a", 30), ("b", 40), ("c", 25)):
        r.desa(COL, id, {"edat": edat})
    ascendent = [d["id"] for d in r.consulta(COL, ordre="edat")]
    assert ascendent == ["c", "a", "b"]
    descendent = [d["id"] for d in r.consulta(COL, ordre="edat", descendent=True)]
    assert descendent == ["b", "a", "c"]
    assert len(r.consulta(COL, ordre="edat", limit=2)) == 2


def test_el_comptador_es_atomic_i_creix(r):
    assert r.incrementa(COL, "seq", "n") == 1
    assert r.incrementa(COL, "seq", "n") == 2
    assert r.incrementa(COL, "seq", "n", 5) == 7


def test_un_lot_que_falla_no_escriu_res(r):
    """És el que fa que una correcció de marcatge no pugui quedar a mitges."""
    with pytest.raises(RuntimeError):
        with r.lot() as lot:
            lot.desa(COL, "a", {"nom": "Anna"})
            lot.desa(COL, "b", {"nom": "Berta"})
            raise RuntimeError("alguna cosa ha anat malament")
    assert r.doc(COL, "a") is None and r.doc(COL, "b") is None


def test_un_lot_correcte_ho_escriu_tot(r):
    r.desa(COL, "vell", {"anulat": False})
    with r.lot() as lot:
        lot.desa(COL, "nou", {"anul_la_id": "vell"})
        lot.actualitza(COL, "vell", {"anulat": True})
    assert r.doc(COL, "nou") is not None
    assert r.doc(COL, "vell")["anulat"] is True


def test_el_que_es_llegeix_es_una_copia(r):
    """Mutar el que has llegit no pot canviar el que hi ha desat: si no, un
    error d'un mòdul es manifestaria com una dada corrupta en un altre."""
    r.desa(COL, "a", {"nom": "Anna", "llista": [1, 2]})
    doc = r.doc(COL, "a")
    doc["nom"] = "Falsa"
    doc["llista"].append(3)
    tornat = r.doc(COL, "a")
    assert tornat["nom"] == "Anna" and tornat["llista"] == [1, 2]


def test_els_dos_adaptadors_tenen_la_mateixa_superficie():
    from magatzem.rebost_firestore import RebostFirestore
    memoria = sorted(o for o in dir(reb.RebostMemoria) if not o.startswith("_"))
    firestore = sorted(o for o in dir(RebostFirestore) if not o.startswith("_"))
    assert memoria == firestore


def test_per_defecte_s_obre_el_de_memoria(monkeypatch):
    """Cap prova ni cap sessió de desenvolupament ha de poder tocar dades de
    producció per haver-se descuidat una variable d'entorn."""
    monkeypatch.delenv("REBOST", raising=False)
    assert isinstance(reb.obre_rebost(), reb.RebostMemoria)


def test_un_magatzem_inventat_es_rebutja():
    with pytest.raises(ErrorHorari):
        reb.obre_rebost("mongodb")
