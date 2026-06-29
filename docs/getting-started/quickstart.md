---
title: Quickstart
---

# Quickstart

De una ecuación de búsqueda a un GraphML, sin escribir código.

## Desde el CLI

```bash
b2g init mi-investigacion
cd mi-investigacion

b2g seed --equation '"unequal ecological exchange"' --max-results 50   # corpus desde OpenAlex
b2g build                                                              # construye las redes
b2g export --format graphml                                           # → redes en GraphML
```

Cada comando acepta `--json` para orquestarlo desde scripts o agentes. Para la
lista completa de comandos y opciones, corré `b2g --help` o mirá la
[referencia de la API](../API.md).

!!! tip "Workspace por investigación"
    `b2g init` crea una carpeta autocontenida (`workspace.json` + base de datos +
    redes/snapshots/exports). Todos los comandos resuelven el workspace desde el
    directorio actual — por eso el `cd` después de `init`.

## Desde Python

```python
from pathlib import Path
from bib2graph import OpenAlexSource, DuckDBStore, Networks, GraphMLExporter

corpus = OpenAlexSource().seed('"unequal ecological exchange"').corpus
store = DuckDBStore(Path("biblioteca.duckdb"))
store.persist(corpus)

for red in Networks.quick(store.load()):
    GraphMLExporter().export(red.graph, red.metrics, out_dir=Path(f"redes/{red.spec.kind}"))
```

## Siguiente paso

- Profundizá en flujos concretos en las [Guías](../guias/index.md).
- Entendé el modelo por dentro en [Arquitectura](../ARCHITECTURE.md).
