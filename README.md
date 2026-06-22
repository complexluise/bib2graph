# bib2graph

> De una búsqueda bibliográfica a **redes de citación reproducibles** — una biblioteca de literatura que curás vos, sin servidores ni planillas.

[![PyPI](https://img.shields.io/pypi/v/bib2graph)](https://pypi.org/project/bib2graph/)
[![Python](https://img.shields.io/pypi/pyversions/bib2graph)](https://pypi.org/project/bib2graph/)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)
[![CI](https://github.com/complexluise/bib2graph/actions/workflows/ci.yml/badge.svg)](https://github.com/complexluise/bib2graph/actions/workflows/ci.yml)

**bib2graph** toma una ecuación de búsqueda (o un archivo `.bib`), arma un corpus de papers
desde [OpenAlex](https://openalex.org), te deja **curarlo** y lo proyecta a **redes
bibliométricas** listas para analizar en Gephi, Python o donde quieras: acoplamiento
bibliográfico, co-citación, co-autoría, colaboración institucional y co-ocurrencia de keywords.

El corpus **persiste y crece** entre sesiones, y el resultado es **reproducible**: mismo input,
mismas redes.

> ⚠️ **Alpha.** Mientras la versión sea `0.x`, la API puede cambiar entre releases menores.
> Úsalo para explorar y validar, no como dependencia estable de producción todavía.

## Instalación

```bash
pip install bib2graph
# o, con uv:
uv add bib2graph
```

Sembrar desde archivos BibTeX necesita un extra: `pip install "bib2graph[bibtex]"`.

## Quickstart

De una ecuación a un GraphML, sin escribir código:

```bash
b2g init mi-investigacion
cd mi-investigacion

b2g seed --equation '"unequal ecological exchange"' --max-results 50   # corpus desde OpenAlex
b2g build                                                              # construye las redes
b2g export --format graphml                                           # → redes en GraphML
```

Cada comando acepta `--json` para orquestarlo desde scripts o agentes. Lista completa de
comandos: `b2g --help`.

### Desde Python

```python
from pathlib import Path
from bib2graph import OpenAlexSource, DuckDBStore, Networks, GraphMLExporter

corpus = OpenAlexSource().seed('"unequal ecological exchange"').corpus
store = DuckDBStore(Path("biblioteca.duckdb"))
store.persist(corpus)

for red in Networks.quick(store.load()):
    GraphMLExporter().export(red.graph, red.metrics, out_dir=Path(f"redes/{red.spec.kind}"))
```

## Qué hace

- **Siembra** desde una ecuación de búsqueda (OpenAlex) o un archivo BibTeX.
- **Expande** el corpus siguiendo citaciones, rankeando candidatos por estructura — sin IA.
- **Curás vos:** aceptar/rechazar papers, filtros PRISMA, todo versionable en CSV.
- **5 redes bibliométricas:** acoplamiento, co-citación, co-autoría, instituciones, co-keywords.
- **Sub-redes temáticas** filtrando por keyword.
- **Biblioteca persistente** (DuckDB) que crece entre sesiones.
- **Reproducible:** mismo corpus → mismas redes y comunidades (hash de contenido).
- **Dos interfaces:** CLI scriptable (`b2g`, salida `--json`) y librería de Python.
- **Exporta** a GraphML/CSV para Gephi, Cytoscape, networkx, etc.

## Cómo se construye (y la IA)

bib2graph se desarrolla **con la IA en el lazo**: una persona plantea el problema, decide y
**aprueba cada cambio**; modelos de IA implementan el código, los tests y la documentación bajo
esa dirección. **El producto en sí no usa IA generativa** — el ranking del forrajeo es estructura
bibliométrica determinista (acoplamiento, co-citación, centralidad), sin LLM ni embeddings, y la
curación es 100% humana. El detalle está en [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md).

## Documentación

- **[Guía de contribución](CONTRIBUTING.md)** — setup de desarrollo, convenciones, cómo aportar.
- **[Arquitectura](docs/ARCHITECTURE.md)** — cómo está construido por dentro.
- **[Referencia de la API](docs/API.md)** — contratos públicos de la librería y el CLI.
- **[Decisiones de diseño](docs/decisiones/)** — los ADRs, para quien quiera el porqué.

## Licencia

[GPL-3.0-or-later](LICENSE) — software libre con copyleft fuerte: cualquier derivado que se
distribuya debe seguir siendo libre y de código abierto. Es deliberado: esta herramienta queda
para la comunidad y no puede cerrarse en un producto propietario.

Copyright (C) 2026 Equipo bib2graph (complexluise).
