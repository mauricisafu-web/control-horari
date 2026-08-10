"""
core/model.py — Contracte de dades del domini.

FITXER CONGELAT. És el vocabulari comú de tots els agents: constants, tipus
de dades i l'error de domini. Si hi falta alguna cosa, és una INCIDÈNCIA, no
una modificació (vegeu FLUX_DE_TREBALL.md §7).

Aquest mòdul no importa flask, ni `magatzem`, ni res de Google, i no en pot
importar mai.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

# La zona de l'ajuntament. Els instants es DESEN en UTC i es MOSTREN aquí:
# així el càlcul no depèn mai de com estigui configurat el contenidor.
ZONA = ZoneInfo("Europe/Madrid")


# --------------------------------------------------------------------------
# Absències
# --------------------------------------------------------------------------
VACANCES = "vacances"
ASSUMPTES_PROPIS = "assumptes_propis"
RECUPERACIO = "recuperacio"
TIPUS_ABSENCIA = (VACANCES, ASSUMPTES_PROPIS, RECUPERACIO)

# ATENCIÓ: aquesta llista NO s'amplia mai amb permisos de salut, naixement,
# cura o violència de gènere. Entrarien a l'art. 9 del RGPD i canviarien tota
# l'avaluació de riscos de l'aplicació (vegeu CLAUDE.md, regla crítica 3).
ETIQUETA_TIPUS = {
    VACANCES: "Vacances",
    ASSUMPTES_PROPIS: "Assumptes propis",
    RECUPERACIO: "Recuperació d'hores",
}

PENDENT = "PENDENT"
APROVADA = "APROVADA"
DENEGADA = "DENEGADA"
ANULADA = "ANULADA"
ESTATS_ABSENCIA = (PENDENT, APROVADA, DENEGADA, ANULADA)

ETIQUETA_ESTAT = {
    PENDENT: "Pendent",
    APROVADA: "Aprovada",
    DENEGADA: "Denegada",
    ANULADA: "Anul·lada",
}


# --------------------------------------------------------------------------
# Marcatges (registre de jornada)
# --------------------------------------------------------------------------
ENTRADA = "entrada"
SORTIDA = "sortida"
PAUSA_INICI = "pausa_inici"
PAUSA_FI = "pausa_fi"
TIPUS_MARCATGE = (ENTRADA, SORTIDA, PAUSA_INICI, PAUSA_FI)

ETIQUETA_MARCATGE = {
    ENTRADA: "Entrada",
    SORTIDA: "Sortida",
    PAUSA_INICI: "Inici de pausa",
    PAUSA_FI: "Fi de pausa",
}

# Estat d'una fila del llibre de registre.
VALID = "VALID"
PENDENT_VALIDACIO = "PENDENT_VALIDACIO"
REBUTJAT = "REBUTJAT"
ESTATS_MARCATGE = (VALID, PENDENT_VALIDACIO, REBUTJAT)

# Com ha entrat el marcatge.
ORIGEN_WEB = "web"
ORIGEN_MANUAL = "manual"
ORIGEN_IMPORTAT = "importat"
ORIGENS = (ORIGEN_WEB, ORIGEN_MANUAL, ORIGEN_IMPORTAT)

# Estat de la persona en un moment donat (màquina d'estats de core/fitxatge).
FORA = "FORA"
DINS = "DINS"
EN_PAUSA = "EN_PAUSA"


# --------------------------------------------------------------------------
# Rols
# --------------------------------------------------------------------------
ROL_ADMIN = "admin"
ROL_RESPONSABLE = "responsable"
ROL_TREBALLADOR = "treballador"
ROLS = (ROL_ADMIN, ROL_RESPONSABLE, ROL_TREBALLADOR)

# Valor especial dins de `treballador.ambits`: àmbit sobre TOTS els serveis.
# És text i no `None` a propòsit: així els àmbits són una llista homogènia que
# es pot consultar directament al magatzem (`array_conte`).
AMBIT_TOTS = "*"

ETIQUETA_ROL = {
    ROL_ADMIN: "Administrador",
    ROL_RESPONSABLE: "Responsable",
    ROL_TREBALLADOR: "Treballador",
}


# --------------------------------------------------------------------------
# Calendari
# --------------------------------------------------------------------------
DIES_SETMANA = ("dilluns", "dimarts", "dimecres", "dijous",
                "divendres", "dissabte", "diumenge")
MESOS = ("gener", "febrer", "març", "abril", "maig", "juny", "juliol",
         "agost", "setembre", "octubre", "novembre", "desembre")

AMBIT_GENERAL = "general"
AMBIT_LOCAL = "local"
AMBIT_PROPI = "propi"
AMBITS_FESTIU = (AMBIT_GENERAL, AMBIT_LOCAL, AMBIT_PROPI)


class ErrorHorari(Exception):
    """Error de domini amb un missatge en català apte per ensenyar a l'usuari.

    La capa web el converteix SEMPRE en un `flash`, mai en un 500: que algú
    demani unes vacances impossibles no és una fallada del programa."""


# --------------------------------------------------------------------------
# Tipus de dades
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Treballador:
    # Els identificadors són TEXT: són claus de document del magatzem, no
    # números autoincrementals. El del treballador és el seu `login`.
    id: str
    login: str
    nom: str
    correu: str
    rol: str
    servei_id: str | None = None
    servei: str | None = None
    data_alta: date | None = None
    data_baixa: date | None = None
    actiu: bool = True
    totp_actiu: bool = False

    @property
    def es_admin(self) -> bool:
        return self.rol == ROL_ADMIN

    @property
    def pot_aprovar(self) -> bool:
        return self.rol in (ROL_ADMIN, ROL_RESPONSABLE)


@dataclass(frozen=True)
class Tram:
    """Una franja d'un patró d'horari. dia_setmana: 1 = dilluns … 7 = diumenge."""
    dia_setmana: int
    hora_inici: time
    hora_fi: time

    @property
    def minuts(self) -> int:
        inici = self.hora_inici.hour * 60 + self.hora_inici.minute
        fi = self.hora_fi.hour * 60 + self.hora_fi.minute
        return max(0, fi - inici)


@dataclass(frozen=True)
class Patro:
    id: str
    nom: str
    trams: tuple[Tram, ...] = ()
    descripcio: str = ""

    def trams_del_dia(self, dia_setmana: int) -> tuple[Tram, ...]:
        return tuple(t for t in self.trams if t.dia_setmana == dia_setmana)


@dataclass(frozen=True)
class Assignacio:
    """Vigència d'un patró per a un treballador. data_fi None = vigent."""
    patro: Patro
    data_inici: date
    data_fi: date | None = None
    coeficient: int = 100
    id: str | None = None

    def vigent_el(self, dia: date) -> bool:
        if dia < self.data_inici:
            return False
        return self.data_fi is None or dia <= self.data_fi


@dataclass(frozen=True)
class Marcatge:
    id: str
    treballador_id: str
    moment: datetime          # SEMPRE amb tzinfo=UTC
    data: date                # data LOCAL a què pertany la jornada
    tipus: str
    origen: str = ORIGEN_WEB
    estat: str = VALID
    anulat: bool = False
    anul_la_id: str | None = None
    nota: str = ""
    creat_per: str | None = None

    @property
    def compta(self) -> bool:
        """Només les files vàlides i no anul·lades entren al còmput."""
        return (not self.anulat) and self.estat == VALID

    @property
    def hora_local(self) -> time:
        return self.moment.astimezone(ZONA).time()


@dataclass(frozen=True)
class Absencia:
    id: str                   # coincideix amb el codi
    codi: str
    treballador_id: str
    tipus: str
    data_inici: date
    data_fi: date
    dies: int
    estat: str
    motiu: str = ""
    creada_el: datetime | None = None
    resolta_per: str | None = None
    resolta_el: datetime | None = None
    motiu_resolucio: str = ""

    def cobreix(self, dia: date) -> bool:
        return self.data_inici <= dia <= self.data_fi


@dataclass(frozen=True)
class ResumDia:
    data: date
    minuts_teorics: int = 0
    minuts_fets: int = 0
    minuts_pausa: int = 0
    minuts_absencia: int = 0
    saldo: int = 0                 # fets + absència − teòrics
    festiu: str | None = None
    absencia: str | None = None    # etiqueta del tipus, si n'hi ha
    anomalies: tuple[str, ...] = ()
    marcatges: tuple[Marcatge, ...] = ()

    @property
    def te_incidencies(self) -> bool:
        return bool(self.anomalies)


@dataclass(frozen=True)
class ResumPeriode:
    inici: date
    fi: date
    minuts_teorics: int = 0
    minuts_fets: int = 0
    minuts_absencia: int = 0
    saldo: int = 0
    dies: tuple[ResumDia, ...] = ()


@dataclass(frozen=True)
class Saldo:
    """Saldo d'un tipus d'absència per a un any.

    `disponibles` pot ser NEGATIU a propòsit quan hi ha data de baixa: són
    dies gaudits per damunt del meritat, que s'han de descomptar a la
    quitança. Mai s'arrodoneix a zero."""
    tipus: str
    any: int
    anual: int = 0            # assignació anual sencera
    assignats: int = 0        # després de prorratejar per alta/baixa
    gastats: int = 0          # suma de dies de les absències APROVADES
    pendents: int = 0         # dies en sol·licituds PENDENT
    disponibles: int = 0      # assignats − gastats
    prorratejat: bool = False
    dies_relacio: int = 365
    baixa: bool = False
    a_liquidar: int = 0       # >0 li deuen dies; <0 se li han de descomptar


# --------------------------------------------------------------------------
# Utilitats de temps compartides (part del contracte)
# --------------------------------------------------------------------------
def ara_utc() -> datetime:
    """L'instant actual en UTC, amb tzinfo. És l'única manera correcta
    d'obtenir el moment d'un marcatge."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def a_local(moment: datetime) -> datetime:
    """Converteix un instant UTC a hora local de l'ajuntament."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZONA)


def data_local(moment: datetime) -> date:
    """La data LOCAL a què pertany un instant. És el valor de `marcatge.data`."""
    return a_local(moment).date()
