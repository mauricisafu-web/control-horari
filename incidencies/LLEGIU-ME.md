# incidencies/

Un fitxer per agent: `1B.md`, `3D.md`… **Cada agent només escriu el seu.**
(Un fitxer compartit seria el primer conflicte de fusió del projecte.)

Aquí s'anota tot xoc amb el contracte: una cosa que `DISSENY.md` no cobreix,
una signatura que no encaixa, una decisió que has hagut de prendre pel teu
compte, o una bona idea que queda fora del teu abast.

Format:

```markdown
## [1B] minuts teòrics amb dues assignacions solapades
**Què diu el contracte:** «guanya la de data_inici més recent» (§4.2)
**Què hi falta:** què passa si totes dues tenen la mateixa data_inici.
**Què he fet:** guanya la d'`id` més alt (l'última desada).
**Cost de canviar-ho:** una línia a `core/comput.py`.
```

Regla: **aplica la solució mínima i reversible que et desbloquegi, i anota-la.**
No modifiquis `DISSENY.md`, l'esquema de la base de dades ni `core/model.py`:
això ho decideix qui integra.

Si el bloqueig és una decisió de producte o de compliment (afegir un tipus
d'absència, desar una dada nova, canviar l'esquema), **atura't i pregunta**.
