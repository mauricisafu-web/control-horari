# Encàrrec 3B · Web d'hores i horari propi

**Onada 3** · Depèn de: 1A, 1B, 2A · Alhora que: 3A, 3C, 3D, 3E

## Objectiu

Que un treballador pugui respondre dues preguntes sense trucar a ningú:
«quantes hores he fet aquest mes?» i «quin horari tinc assignat?».

## Escrius

```
web/hores.py                 templates/hores/resum.html
templates/hores/horari.html  static/css/hores.css
tests/test_web_hores.py
```

## Llegeixes

`DISSENY.md` §6 (blueprint `hores`). `core/comput.py` (1B),
`magatzem/{marcatges,horaris,festius,absencies}.py` (1A).

## Feina

### `/hores` (GET, `?any=&mes=`)

Resum mensual propi. Estructura:

1. **Capçalera amb els quatre números del mes**: hores teòriques, hores fetes,
   hores d'absència i **saldo**, amb `formata_minuts`. El saldo, en verd si és
   positiu i en vermell si és negatiu — **i sempre amb el signe escrit**, que
   no depengui del color (accessibilitat).
2. **Saldo acumulat de l'any** fins al final del mes que es mira. És el número
   que la gent realment vol saber.
3. **Taula dia a dia**: data i dia de la setmana, teòriques, fetes, saldo del
   dia, i una columna d'estat (festiu, vacances, assumptes propis, incidència).
   Els dies festius i de cap de setmana, atenuats.
4. Navegació de mesos amb enllaços `?any=&mes=`, i un enllaç per anar al
   detall de marcatges d'aquell dia (`/marcatges`, de l'agent 3A).

A mòbil, la taula ha de ser llegible: o bé desplaçament horitzontal **dins de
la taula** (mai de la pàgina sencera), o bé una fila per dia apilada. Tria una
i fes-la bé.

**Cost**: carrega les dades del mes **d'un sol cop** (una crida a
`marcatges.del_periode`, una a `festius.del_any`, una a
`absencies.de_treballador`, una a `comptes.assignacions_de`) i passa-ho tot a
`comput.resum_periode`. **Cap consulta dins d'un bucle de dies**: al magatzem
de producció cada document llegit compta contra el límit gratuït diari
(`DISSENY.md` §3.5), i 30 consultes en lloc d'una és multiplicar el consum per
30. El pressupost d'aquesta pàgina és d'unes 90 lectures; si te'n vas molt,
anota-ho a `incidencies/3B.md`.

### `/el-meu-horari` (GET)

El patró vigent amb els trams de cada dia de la setmana en una taula clara, el
total setmanal, el coeficient de jornada si no és del 100 %, i l'historial de
vigències (des de quan, fins quan). Si no hi ha cap assignació, un missatge que
digui a qui s'ha de demanar, no una pàgina buida.

## Acceptació

- [ ] Els números quadren amb els de la pantalla de fitxatge per al mateix dia.
- [ ] Un mes sense cap marcatge es veu bé (saldo negatiu, no error).
- [ ] `?any=2026&mes=13`, `?mes=abril` i `?any=` buit cauen al mes actual.
- [ ] Un treballador **només** veu les seves dades: no hi ha cap paràmetre a la
      URL que permeti veure les d'un altre. Prova-ho explícitament.
- [ ] A 375 px, la pàgina no es desplaça horitzontalment.
- [ ] `pytest -q` verd.

Cobertura mínima: mes complet amb dades sintètiques; mes buit; mes amb
vacances aprovades (saldo del dia 0); mes amb un canvi de patró d'horari a
mig mes; paràmetres invàlids; sense sessió → login; intent d'accedir a les
hores d'un altre → no hi ha cap manera de demanar-ho, i si algú afegeix un
`?treballador=`, s'ignora.

## Paranys

- **El saldo acumulat de l'any pot ser car de calcular** si es fa dia a dia des
  de l'1 de gener a cada càrrega. Amb 24 persones i un any va bé, però
  mesura-ho: si passa d'un segon, calcula'l només fins al mes demanat i
  documenta-ho.
- **Un canvi de patró a mig mes** és el cas que trenca els càlculs ingenus.
  `comput.minuts_teorics_dia` ja tria l'assignació vigent de cada dia: passa-li
  **totes** les assignacions, no només la vigent avui.
- **No inventis un «horari flexible»** ni marges de tolerància. No hi són al
  contracte.
- **No afegeixis cap exportació aquí.** Els informes són de l'agent 4A.
