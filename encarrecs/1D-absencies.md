# Encàrrec 1D · Absències (domini)

**Onada 1** · Depèn de: 0A · Alhora que: 1A, 1B, 1C, 1E

## Objectiu

`core/regles.py`: dies hàbils, saldos amb prorrateig per alta i baixa,
validació de sol·licituds i àmbit d'aprovació. Funcions **pures**.

> **Aquesta lògica ja existeix provada** al mòdul de vacances de
> `C:\Users\secretari\expedients-nomines-beta` (`core/vacances/regles.py` i
> `magatzem.py`). **Llegeix-la i adapta-la**: el criteri d'arrodoniment i el
> tractament del saldo negatiu venen d'allà i estan validats contra casos
> reals. **No escriguis res en aquella carpeta**: només s'hi llegeix.

## Escrius

```
core/regles.py     tests/test_regles.py
```

## Llegeixes

`DISSENY.md` §4.3 (signatures) i §3.2 (saldo assignat vs. gastat).
`core/model.py`. De referència: `expedients-nomines-beta/core/vacances/regles.py`.

## Feina

### `dies_habils(inici, fi, festius) -> int`

Dies laborables (dilluns a divendres) entre les dues dates **incloses**,
excloent-ne els festius. `ErrorHorari` si `fi < inici`.

### Prorrateig — el punt delicat

```
dies_de_relacio(any, alta, baixa) -> int
arrodoneix_prorrata(valor) -> int
prorrata_saldo(assignacio_anual, dies_relacio) -> int
```

- `dies_de_relacio`: dies de l'any en què hi ha relació laboral, **comptant el
  dia d'alta**. Sense cap de les dues dates dins de l'any, 365 (o 366).
- `arrodoneix_prorrata`: criteri de l'Administració pública, **fracció ≥ 0,4
  amunt**. NO és el 0,5 habitual. `14,16 → 14` · `3,86 → 4` · **`14,4 → 15`**.
  Aquest últim cas és el que distingeix aquesta funció de `round()`: que hi
  hagi una prova amb el nom explícit.
- `prorrata_saldo`: `dies_relacio × assignacio_anual ÷ 365`, arrodonit amb
  l'anterior. Es prorrateja **l'assignació desada**, no la de configuració: si
  algú té 26 dies per conveni, es prorrategen els 26.

Cas de referència, que ha de ser un test amb aquests números:
alta l'11/05/2026 → 235 dies de relació → vacances `235×22/365 = 14,16 → 14`;
assumptes propis `235×6/365 = 3,86 → 4`.

### `calcula_saldo(...) -> Saldo`

Omple tots els camps de `model.Saldo`:

- `anual`: l'assignació desada (o la de configuració si no n'hi ha).
- `assignats`: després de prorratejar, si hi ha alta o baixa dins de l'any.
- `gastats`: suma de `dies` de les absències **APROVADES** de l'any i el tipus.
- `pendents`: el mateix, però de les **PENDENT** (informatiu; no descompta).
- `disponibles = assignats − gastats`.
- `a_liquidar`: `assignats − gastats` quan hi ha `data_baixa`; 0 si no.

**El saldo negatiu és volgut i no s'arrodoneix mai a zero.** Qui plega el 31/08
merita `243×22/365 = 14,64 → 15` dies; si ja n'havia gaudit 20, `disponibles`
val **−5**, i són cinc dies cobrats de més que s'han de descomptar a la
quitança. Que hi hagi un test amb aquests números exactes.

### `valida_solicitud(...)`

`ErrorHorari`, amb missatge en català, si:

- `data_fi < data_inici`;
- la sol·licitud **creua l'any natural** → missatge que demani partir-la en
  dues (i que digui per què: els saldos són anuals);
- `dies > disponibles` del tipus i l'any → missatge que digui quants en queden;
- **se solapa** amb una altra sol·licitud pròpia `PENDENT` o `APROVADA` → que
  digui amb quina (el codi i les dates).

Amb saldo ja negatiu, el missatge ha d'explicar el deute en lloc de dir «en
queden −5 de disponibles», que no s'entén.

### `pot_resoldre(qui, absencia, ambits) -> bool`

- Mai la pròpia: si `qui.id == absencia.treballador_id`, **fals sempre**,
  encara que sigui administrador.
- `admin` → cert (llevat de la pròpia).
- `responsable` → cert si `'*'` (`model.AMBIT_TOTS`) és a `ambits`, o si hi és
  el servei del sol·licitant.

Aquesta funció és una comprovació de seguretat. Prova-la com si ho fos.

## Acceptació

- [ ] Les set funcions de `DISSENY.md` §4.3 amb la signatura exacta.
- [ ] `grep -n "import flask\|magatzem\|google" core/regles.py` buit.
- [ ] `pytest tests/test_regles.py -q` verd.

Cobertura mínima: dies hàbils amb i sense festius i amb cap de setmana als
extrems; `fi < inici`; **els tres casos d'arrodoniment**, amb el 14,4 → 15
pel seu nom; el cas de l'alta de l'11/05/2026; el cas de la baixa amb saldo
−5; els quatre errors de `valida_solicitud` comprovant-ne **el text**;
`pot_resoldre` amb els cinc casos (propi essent admin, admin d'un altre,
responsable amb àmbit, responsable sense àmbit, responsable amb `'*'`).

## Paranys

- **Els dies gastats no es desen mai.** Es calculen. Si en algun moment penses
  «i si actualitzo el saldo en aprovar», atura't: el disseny ho prohibeix
  expressament perquè sigui idempotent i auditable (anul·lar una absència
  retorna els dies tot sol, sense fer res).
- **`round()` de Python fa arrodoniment bancari**: `round(14.5)` val 14. No la
  facis servir per a `arrodoneix_prorrata`.
- **L'any de traspàs**: `dies_de_relacio` d'un any sencer pot ser 366, però el
  divisor de la prorrata és **365** segons el criteri heretat. Deixa-ho escrit
  amb un comentari perquè no sembli un error.
- **No comprovis permisos de servei web aquí.** Tu reps `ambits` ja resolts;
  qui els consulta és el blueprint.
