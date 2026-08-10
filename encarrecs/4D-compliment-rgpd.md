# Encàrrec 4D · Compliment normatiu (RGPD, ENS, control horari)

**Onada 4** · Depèn de: l'onada 3 sencera · Alhora que: 4A, 4C
· **Es pot començar el dia 1**: no depèn del codi i el tràmit amb el DPD és
llarg. Si vas bé de temps, avança'l a l'onada 1.

## Objectiu

Deixar preparada tota la documentació perquè el DPD pugui donar el vistiplau i
perquè es puguin posar dades reals a l'aplicació. **Sense això, l'aplicació no
es pot fer servir**, per bé que funcioni.

## Escrius

```
compliment/RAT.md                        compliment/ANALISI_RISCOS.md
compliment/NOTA_INFORMATIVA.md           compliment/ENCARREC_DPD.md
compliment/POLITICA_CONSERVACIO.md
templates/avis_legal.html
```

## Llegeixes

`DISSENY.md` §1 i §3.6, `desplegament/FIREBASE.md` §3, `CLAUDE.md` (regles
crítiques). De referència, a `expedients-nomines-beta/desplegament/`:
`ACCES_ONLINE_PERSONAL.md` §4 (taula de compliment), `ANALISI_ARQUITECTURA_
BICEFALA.md` (com s'analitza la qualificació de les dades) i
`NOTA_INFORMATIVA_TREBALLADORS.md`. **Només llegir.**

## Feina

### El punt de partida que has d'exposar amb honestedat

L'ajuntament tenia un principi escrit: «les dades no surten del servidor de
l'ajuntament», i amb aquest criteri va **descartar** un túnel de Cloudflare
perquè el tercer veia les dades. Ara s'ha decidit allotjar aquesta aplicació a
**Firebase**, on Google no només veu les dades: les **guarda**.

Aquest canvi s'ha de presentar al DPD **explícitament, com el que és**, amb els
arguments a favor i en contra. No l'amaguis dins d'un paràgraf tècnic. Els
arguments a favor són reals i sòlids:

- Aquesta aplicació **no toca mai nòmines ni factures**: la separació que
  justificava tot el disseny anterior es manté i, de fet, s'endureix (són dos
  sistemes diferents, no dues instàncies del mateix codi).
- **Cap categoria especial de l'art. 9**: ni salut, ni IT, ni permisos
  sensibles. És una frontera de disseny escrita al codi.
- **Ni ubicació ni biometria** al fitxatge, que és el que l'AEPD mira primer en
  un sistema de control horari.
- Xifratge en trànsit i en repòs, regió de la UE, DPA de Google signat.

I el que hi ha en contra, dit igual de clar:

- Un **encarregat del tractament nou** i internacional (art. 28 i cap. V).
- El registre de presència diària **és més revelador** que un saldo de
  vacances: diu qui arriba tard i quan.
- Dependència d'un proveïdor per a un servei que la plantilla necessita cada
  dia.

### Els documents

- **`RAT.md`** — Entrada per al registre d'activitats: responsable, finalitat
  («gestió del control horari i de les absències del personal municipal»), base
  jurídica (**art. 6.1.c** obligació legal, per l'art. 34.9 ET; i **6.1.b/e**
  per a la relació d'ocupació — **no consentiment**, que amb un empleat no és
  lliure), categories d'interessats i de dades, destinataris, **encarregat
  (Google Ireland/Cloud)**, transferències, terminis de conservació i mesures
  de seguretat.
- **`ANALISI_RISCOS.md`** — Riscos, probabilitat, impacte i mitigació.
  Inclou-hi el risc residual de manera honesta: exposar un servei a Internet
  no és risc zero, i el botí possible aquí és el patró de presència de 24
  persones. Valora si cal una **EIPD** completa: probablement no (no hi ha
  categories especials ni gran escala), **però ho ha de confirmar el DPD** —
  digues-ho així, no ho decideixis tu.
- **`NOTA_INFORMATIVA.md`** — La informació de l'art. 13 per als treballadors,
  en llenguatge planer: qui tracta les dades, per què, amb quina base, qui hi
  té accés (el seu responsable i l'administrador), quant temps es conserven,
  quins drets tenen i com exercir-los, i **on és el servidor**. Ha de dir
  clarament que es registra l'hora d'entrada i sortida i que **no** es registra
  la ubicació. Camps entre claudàtors per als que ha d'omplir l'usuari (data,
  URL, contacte del DPD).
- **`POLITICA_CONSERVACIO.md`** — La taula de `DISSENY.md` §3.3 amb la
  justificació de cada termini i com s'executa (`core/purga.py`, agent 4A).
- **`ENCARREC_DPD.md`** — El document de dues pàgines que se li envia al DPD:
  què és l'aplicació, què canvia respecte del que ja va aprovar, què se li
  demana exactament i per a quan. Amb una llista de decisions numerades i un
  espai per a la seva resposta, com la taula d'`ACCES_ONLINE_PERSONAL.md` §7.
- **`templates/avis_legal.html`** — Versió breu per al peu de l'aplicació,
  accessible **sense sessió**, enllaçada des del login.

### Requisit específic del control horari

Per a personal funcionari, el règim concret del registre de jornada el fixa la
normativa pròpia i l'acord de condicions de treball de l'ajuntament. **No ho
donis per resolt**: deixa'n un punt explícit a `ENCARREC_DPD.md` perquè
l'usuari confirmi quina norma local hi aplica i si cal informar-ne la
representació del personal abans de posar-lo en marxa. Això **no és una decisió
tècnica**.

## Acceptació

- [ ] Els cinc documents escrits, en català i entenedors per a algú que no és
      jurista.
- [ ] El canvi d'allotjament a Google, exposat de manera explícita, amb els
      arguments a favor i en contra.
- [ ] `ENCARREC_DPD.md` es pot enviar tal com està, amb els buits marcats.
- [ ] La nota informativa diu que **no** es recull la ubicació.
- [ ] `/avis-legal` respon sense sessió i s'entén.
- [ ] Cap dada real ni cap nom de persona real en cap dels documents.

## Paranys

- **Res d'això s'envia a ningú sense que l'usuari ho confirmi expressament.**
  És una instrucció que ja ha donat en aquest projecte i val igual aquí.
- **No inventis el nom ni el contacte del DPD.** Claudàtors.
- **No diguis que una cosa està aprovada si no ho està.** El vistiplau anterior
  del DPD era per a una altra aplicació i una altra arquitectura; no serveix.
- **No facis servir el consentiment com a base jurídica.** Amb una relació
  laboral no és lliure i l'AEPD el rebutja sistemàticament.
