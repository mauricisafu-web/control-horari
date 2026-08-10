# Com es llegeix un encàrrec

Tots els encàrrecs tenen la mateixa forma:

- **Objectiu** — què ha d'existir quan acabis. Una frase.
- **Escrius** — la llista TANCADA de fitxers que pots crear o modificar. Fora
  d'aquí no escrius res, ni un `import`. És la regla que fa possible que
  diversos agents treballin alhora.
- **Llegeixes** — el que has de consultar per fer-ho bé.
- **Feina** — el detall.
- **Acceptació** — la llista que ha de sortir tota marcada. Qui integra la
  comprova.
- **Proves** — les ordres exactes.
- **Paranys** — el que ja sabem que et pot sortir malament.

## Prompt per llançar l'agent

```
Ets l'agent <ID> d'aquest projecte. Treballa a C:\Users\secretari\control-horari.

Llegeix sencers, en aquest ordre, abans de tocar res:
  1. CLAUDE.md
  2. DISSENY.md
  3. encarrecs/<ID>-<nom>.md

Fes NOMÉS el que diu el teu encàrrec i escriu NOMÉS els fitxers de la seva
llista. Quan acabis, executa la suite sencera i informa del resultat REAL: si
falla alguna cosa, digues-ho; no ho amaguis ni ho arreglis tocant fitxers que
no són teus. Si trobes una incoherència del contracte, aplica la solució
mínima i anota-la a incidencies/<ID>.md.
```

## Recordatori curt (val per a tots)

1. Català a tot arreu: codi, comentaris, missatges, interfície.
2. Cap dada real. Mai. Ni per provar una cosa un moment.
3. `core/` no importa `flask`, ni `magatzem`, ni res de Google.
4. No ampliïs l'abast. Les bones idees van a `incidencies/<ID>.md`.
5. No toquis `expedients-nomines-beta` ni `expedients-nomines-v2`.
6. Informa del que ha passat de debò.
