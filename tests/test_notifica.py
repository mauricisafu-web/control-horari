"""
Proves de core/notifica.py.

CAP prova envia cap correu de debò: `smtplib` se substitueix sencer. La regla
que es comprova una vegada i una altra és que **res no llança mai**: un SMTP
mal configurat no pot tombar una sol·licitud de vacances ja desada.
"""
from __future__ import annotations

import smtplib
from datetime import date

import pytest

from core import notifica
from core.model import APROVADA, Absencia, Treballador

CONFIG = {"SMTP_HOST": "smtp.exemple.cat", "SMTP_PORT": 587,
          "SMTP_USUARI": "app@exemple.cat", "SMTP_PASSWORD": "x",
          "SMTP_TLS": True, "SMTP_REMITENT": "app@exemple.cat"}

TREBALLADOR = Treballador(id="treb01", login="treb01", nom="Aina Prova",
                          correu="treb01@exemple.cat", rol="treballador")

ABSENCIA = Absencia(id="A-2026-0001", codi="A-2026-0001",
                    treballador_id="treb01", tipus="vacances",
                    data_inici=date(2026, 8, 3), data_fi=date(2026, 8, 7),
                    dies=5, estat=APROVADA)


class ServidorFals:
    enviats: list = []

    def __init__(self, *args, **kwargs):
        ServidorFals.enviats = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self):
        pass

    def login(self, usuari, contrasenya):
        pass

    def send_message(self, missatge):
        ServidorFals.enviats.append(missatge)


@pytest.fixture
def smtp_fals(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", ServidorFals)
    monkeypatch.setattr(smtplib, "SMTP_SSL", ServidorFals)
    return ServidorFals


def test_sense_smtp_configurat_no_hi_ha_correu():
    assert notifica.hi_ha_correu({}) is False
    assert notifica.envia({}, "algu@exemple.cat", "Hola", "Cos") is False


def test_enviament_correcte(smtp_fals):
    assert notifica.envia(CONFIG, "algu@exemple.cat", "Hola", "Cos") is True
    assert len(smtp_fals.enviats) == 1
    assert smtp_fals.enviats[0]["Subject"] == "Hola"


def test_sense_destinatari_no_s_intenta_res(smtp_fals):
    assert notifica.envia(CONFIG, "", "Hola", "Cos") is False
    assert notifica.envia(CONFIG, [], "Hola", "Cos") is False


def test_un_servidor_que_no_respon_no_llanca(monkeypatch):
    def peta(*args, **kwargs):
        raise OSError("connexió refusada")
    monkeypatch.setattr(smtplib, "SMTP", peta)
    assert notifica.envia(CONFIG, "algu@exemple.cat", "Hola", "Cos") is False


def test_una_autenticacio_fallida_no_llanca(monkeypatch):
    class Rebutja(ServidorFals):
        def login(self, usuari, contrasenya):
            raise smtplib.SMTPAuthenticationError(535, b"no")
    monkeypatch.setattr(smtplib, "SMTP", Rebutja)
    assert notifica.envia(CONFIG, "algu@exemple.cat", "Hola", "Cos") is False


def test_el_correu_de_resolucio_no_filtra_dades_de_mes(smtp_fals):
    notifica.avisa_resolucio(CONFIG, ABSENCIA, TREBALLADOR)
    cos = smtp_fals.enviats[0].get_content()
    assert "aprovada" in cos and "A-2026-0001" in cos
    # Ni saldos, ni motius personals, ni res que el correu no hagi de dir.
    assert "saldo" not in cos.lower()
    assert "vacances" not in cos.lower() or "dies" not in cos.lower()


def test_el_correu_de_la_provisional_avisa_del_risc(smtp_fals):
    notifica.envia_provisional(CONFIG, TREBALLADOR, "Provisional-123")
    cos = smtp_fals.enviats[0].get_content()
    assert "Provisional-123" in cos
    assert "no és un canal segur" in cos


def test_avis_de_nova_solicitud_als_aprovadors(smtp_fals):
    notifica.avisa_nova_solicitud(CONFIG, ABSENCIA, TREBALLADOR,
                                  ["resp01@exemple.cat", "resp02@exemple.cat"])
    assert "resp01@exemple.cat" in smtp_fals.enviats[0]["To"]
    assert "resp02@exemple.cat" in smtp_fals.enviats[0]["To"]


def test_el_port_465_fa_servir_ssl(monkeypatch):
    vistos = []
    monkeypatch.setattr(smtplib, "SMTP_SSL",
                        lambda *a, **k: vistos.append("ssl") or ServidorFals())
    monkeypatch.setattr(smtplib, "SMTP",
                        lambda *a, **k: vistos.append("clar") or ServidorFals())
    notifica.envia({**CONFIG, "SMTP_PORT": 465}, "a@exemple.cat", "H", "C")
    assert vistos == ["ssl"]
