"""Capa web: un blueprint per fitxer.

Els blueprints són només adaptadors HTTP: llegeixen el formulari, criden el
domini (`core/`) o el magatzem, i trien la plantilla. Cap regla de negoci hi
viu, i cap consulta a Firestore tampoc."""
