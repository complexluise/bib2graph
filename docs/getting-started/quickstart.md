---
title: Quickstart
---

# Quickstart

De una ecuación de búsqueda a un GraphML, sin escribir código.

## Desde el CLI

<!-- termynal -->

```
$ b2g init mi-investigacion
Workspace creado en ./mi-investigacion
$ cd mi-investigacion
$ b2g seed --equation '"unequal ecological exchange"' --max-results 50
Sembrando desde OpenAlex...
---> 100%
52 papers en el corpus
$ b2g build
Construyendo las redes...
---> 100%
Listas: acoplamiento · co-citación · co-autoría · instituciones · co-keywords
$ b2g export --format graphml
Exportadas a ./redes/*.graphml
```

En tres pasos pasaste de una ecuación a redes en GraphML, sin escribir código.

Cada comando acepta `--json` para orquestarlo desde scripts o agentes. Para la
lista completa de comandos y opciones, corré `b2g --help` o mirá la
[referencia del CLI `b2g`](../reference/cli.md).

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
