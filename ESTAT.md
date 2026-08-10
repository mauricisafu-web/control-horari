# ESTAT.md — Taulell de progrés

> L'actualitza **només qui integra**, al final de cada tasca. Els agents no
> l'escriuen: ells escriuen `incidencies/<ID>.md`.

**Versió del contracte**: 1.0 · **Última actualització**: 2026-08-05

---

## Resum

| Onada | Estat | Tasques |
|---|---|---|
| Preparació (cervell) | ✅ **FETA** | Contracte, esquema, fixtures i encàrrecs |
| 0 · Esquelet | ⬜ pendent | 0A |
| 1 · Domini i magatzem | ⬜ pendent | 1A 1B 1C 1D 1E |
| 2 · Transversals | ⬜ pendent | 2A 2B 2C 2D |
| 3 · Web dels mòduls | ⬜ pendent | 3A 3B 3C 3D 3E |
| 4 · Tancament | ⬜ pendent | 4A 4B 4C 4D |
| 5 · Desplegament real | ⬜ pendent | 5A 5B 5C |

Llegenda: ⬜ pendent · 🟨 en curs · ✅ feta · ⛔ bloquejada

---

## Detall

| ID | Tasca | Estat | Agent | Data | Notes |
|---|---|---|---|---|---|
| 0A | Esquelet executable | ⬜ | | | |
| 1A | Magatzem | ⬜ | | | camí crític |
| 1B | Còmput horari | ⬜ | | | |
| 1C | Fitxatge (domini) | ⬜ | | | |
| 1D | Absències (domini) | ⬜ | | | |
| 1E | Calendari i festius | ⬜ | | | |
| 2A | Autenticació i TOTP | ⬜ | | | desbloqueja l'onada 3 |
| 2B | PWA | ⬜ | | | |
| 2C | Desplegament (Docker) | ⬜ | | | |
| 2D | Correus i eines | ⬜ | | | |
| 3A | Web fitxatge | ⬜ | | | pantalla principal |
| 3B | Web hores | ⬜ | | | |
| 3C | Web absències | ⬜ | | | |
| 3D | Web gestió | ⬜ | | | més control d'accés |
| 3E | Web configuració | ⬜ | | | |
| 4A | Informes i purga | ⬜ | | | |
| 4B | UI i accessibilitat | ⬜ | | | va sola |
| 4C | Auditoria de seguretat | ⬜ | | | |
| 4D | Compliment RGPD | ⬜ | | | es pot avançar al dia 1 |
| 5A | Prova Docker local | ⬜ | | | |
| 5B | Desplegament a Firebase | ⬜ | | | |
| 5C | Posada en marxa | ⬜ | | | |

---

## Ja fet a la preparació

Escrit i **verificat executant-lo** (esquema idempotent, claus foranes
actives, índex d'àmbit únic, conversió UTC↔local correcta):

- `CLAUDE.md` · `DISSENY.md` · `FLUX_DE_TREBALL.md` · `ESTAT.md`
- `core/model.py` **(congelat)**
- `magatzem/rebost.py` **(congelat)** — el port de 8 operacions + adaptador
  de memòria
- `magatzem/rebost_firestore.py` **(congelat)** — adaptador de producció
- `tests/conftest.py` **(congelat)**
- `requirements.txt` · `pytest.ini` · `.gitignore`
- `desplegament/FIREBASE.md`
- Els 20 fitxers d'`encarrecs/`

Verificat executant-ho: els dos adaptadors tenen la **mateixa superfície
exacta** (8 operacions), les lectures retornen còpies aïllades, un `lot()` que
falla no escriu res, el comptador és atòmic i la conversió UTC↔local és
correcta.

---

## Tràmits externs (no depenen del codi — començar el dia 1)

| # | Tràmit | Responsable | Estat |
|---|---|---|---|
| T1 | Projecte de Firebase amb pla Blaze i regió de la UE | Usuari | ⬜ |
| T2 | **Alerta de pressupost a 1 €** i quotes de peticions | Usuari | ⬜ |
| T3 | DPA de Google Cloud acceptat | Usuari + DPD | ⬜ |
| T4 | Vistiplau del DPD (documents de l'agent 4D) | DPD | ⬜ |
| T5 | Confirmar la normativa local de registre de jornada per a personal funcionari i si cal informar-ne la representació del personal | Usuari | ⬜ |
| T6 | Node.js, Java i `gcloud` instal·lats (cap dels tres hi és ara) | Usuari | ⬜ |

**T3, T4 i T5 bloquegen les dades reals, no el desenvolupament.** Tot es
construeix i es prova amb dades sintètiques.

**T1, T2 i T6 no calen fins a l'onada 5**: fins llavors tot corre contra
l'adaptador de memòria, sense cap compte ni cap eina externa.

---

## Decisions preses

| Data | Decisió |
|---|---|
| 2026-08-05 | Abast: **fitxatge + horari teòric + saldo**, més vacances i festius |
| 2026-08-05 | Aplicació **TOTALMENT independent**: cap fitxer, compte, magatzem ni configuració compartits amb cap altra aplicació de l'usuari |
| 2026-08-05 | Allotjament: **Firebase** (Hosting + Cloud Run) |
| 2026-08-05 | **Cost zero, requisit dur.** Escalat a zero (`min-instances 0`) i pressupost de lectures a `DISSENY.md` §3.5 |
| 2026-08-05 | **El NAS queda descartat** i no es contempla en cap escenari |
| 2026-08-05 | Persistència: **Firestore** darrere d'un port intercanviable. SQLite es va descartar perquè amb cost zero obliga a escalar a zero i obre una finestra de pèrdua de marcatges |
| 2026-08-05 | Proves contra un adaptador **en memòria**: cap agent necessita Node, Java, emulador ni compte de Google per treballar |
| 2026-08-05 | Sense quadrants de torns, sense fitxatge fora de línia, sense geolocalització ni biometria, sense permisos de l'art. 9 |

---

## Registre de desplegaments

| Data | Versió | On | Verificat per | Notes |
|---|---|---|---|---|
| | | | | |
