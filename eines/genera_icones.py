"""
eines/genera_icones.py — Genera les icones de la PWA.

Sense cap dependència: escriu els PNG a mà amb `zlib` i `struct`. Afegir
Pillow al `requirements.txt` per fer quatre icones no compensa, i cada
dependència nova és una cosa més per mantenir actualitzada en un servei
exposat a Internet.

El dibuix és un rellotge senzill sobre el color corporatiu. Es renderitza a
quatre vegades la mida i es redueix, que és la manera barata de tenir vores
suaus sense biblioteca de gràfics.

    python eines/genera_icones.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ARREL = Path(__file__).resolve().parents[1]
DESTI = ARREL / "static" / "icones"

FONS = (30, 64, 120)        # #1e4078, el blau de base.css
TINTA = (255, 255, 255)
MOSTRES = 4                 # supermostreig


def _dins_del_rellotge(x: float, y: float, mida: float, marge: float) -> bool:
    """Cert si el punt (x, y) forma part del dibuix del rellotge."""
    centre = mida / 2
    radi = (mida - 2 * marge) / 2
    dx, dy = x - centre, y - centre
    dist = math.hypot(dx, dy)

    gruix = mida * 0.055
    # Anella exterior.
    if abs(dist - radi) <= gruix / 2:
        return True
    # Busques: les 8 i 20 minuts, que és quan es fitxa de debò.
    for angle_graus, llarg in ((0, 0.60), (108, 0.42)):
        angle = math.radians(angle_graus - 90)
        fx, fy = math.cos(angle), math.sin(angle)
        # Projecció del punt sobre la busca.
        t = dx * fx + dy * fy
        if 0 <= t <= radi * llarg:
            perp = abs(-dx * fy + dy * fx)
            if perp <= gruix / 2:
                return True
    # Centre.
    return dist <= gruix * 0.8


def _pixels(mida: int, marge_relatiu: float) -> bytearray:
    """Files RGBA del PNG, amb el byte de filtre al davant de cada fila."""
    marge = mida * marge_relatiu
    dades = bytearray()
    pas = 1.0 / MOSTRES
    for fila in range(mida):
        dades.append(0)                       # filtre 0 (cap)
        for columna in range(mida):
            encerts = 0
            for sy in range(MOSTRES):
                for sx in range(MOSTRES):
                    x = columna + (sx + 0.5) * pas
                    y = fila + (sy + 0.5) * pas
                    if _dins_del_rellotge(x, y, mida, marge):
                        encerts += 1
            cobertura = encerts / (MOSTRES * MOSTRES)
            r = round(FONS[0] + (TINTA[0] - FONS[0]) * cobertura)
            g = round(FONS[1] + (TINTA[1] - FONS[1]) * cobertura)
            b = round(FONS[2] + (TINTA[2] - FONS[2]) * cobertura)
            dades += bytes((r, g, b, 255))
    return dades


def _tros(tipus: bytes, contingut: bytes) -> bytes:
    return (struct.pack(">I", len(contingut)) + tipus + contingut
            + struct.pack(">I", zlib.crc32(tipus + contingut) & 0xFFFFFFFF))


def escriu_png(desti: Path, mida: int, marge_relatiu: float) -> None:
    capcalera = struct.pack(">IIBBBBB", mida, mida, 8, 6, 0, 0, 0)  # RGBA
    png = (b"\x89PNG\r\n\x1a\n"
           + _tros(b"IHDR", capcalera)
           + _tros(b"IDAT", zlib.compress(bytes(_pixels(mida, marge_relatiu)), 9))
           + _tros(b"IEND", b""))
    desti.write_bytes(png)


def main() -> None:
    DESTI.mkdir(parents=True, exist_ok=True)
    # Les icones «maskable» necessiten marge: Android les retalla en cercle o
    # en gota, i el dibuix ha de cabre dins del 80 % central.
    feines = [
        ("icona-192.png", 192, 0.10),
        ("icona-512.png", 512, 0.10),
        ("icona-192-maskable.png", 192, 0.22),
        ("icona-512-maskable.png", 512, 0.22),
    ]
    for nom, mida, marge in feines:
        cami = DESTI / nom
        escriu_png(cami, mida, marge)
        print(f"  {nom:26} {mida}x{mida}  {cami.stat().st_size:>7} bytes")


if __name__ == "__main__":
    print("Generant les icones de la PWA:")
    main()
