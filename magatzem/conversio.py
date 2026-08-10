"""
magatzem/conversio.py — Frontera de tipus entre els documents i el domini.

Els documents desen text ISO; les dataclasses de `core.model` porten `date`,
`time` i `datetime` de debò. Tota la conversió passa per aquí, i tot
`datetime` que en surt porta `tzinfo=UTC` explícit: un instant sense zona és
una bomba de rellotgeria.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone


def a_data(text) -> date | None:
    if not text:
        return None
    if isinstance(text, date) and not isinstance(text, datetime):
        return text
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def a_moment(text) -> datetime | None:
    """Sempre amb zona UTC, vingui com vingui."""
    if not text:
        return None
    if isinstance(text, datetime):
        return text if text.tzinfo else text.replace(tzinfo=timezone.utc)
    net = str(text).strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(net)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def a_hora(text) -> time:
    if isinstance(text, time):
        return text
    hores, _, minuts = str(text or "0:0").partition(":")
    return time(int(hores or 0), int(minuts or 0))


def de_data(dia: date | None) -> str | None:
    return dia.isoformat() if dia else None


def de_moment(moment: datetime | None) -> str | None:
    """Text ISO en UTC acabat en 'Z'."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def de_hora(hora: time) -> str:
    return f"{hora.hour:02d}:{hora.minute:02d}"
