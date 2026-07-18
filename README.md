# bib2graph

> De una búsqueda bibliográfica a **redes de citación reproducibles** — una biblioteca de literatura que curás vos, sin servidores ni planillas.

**Un antídoto al sesgo del *related work* escrito de memoria.** Cuando armás la revisión
de literatura recordando papers, repetís lo que ya conocés y dejás afuera lo que no.
bib2graph convierte una búsqueda en un **corpus + redes de citación + un orden de lectura
priorizado** —deterministas, reproducibles y con procedencia—. **Te lleva hasta la lectura
y se detiene ahí:** no interpreta, no gestiona tu investigación ni usa IA; el juicio queda tuyo.

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

Recomendamos [**uv**](https://docs.astral.sh/uv/) para gestionar el entorno:

```bash
uv add bib2graph
```

También funciona con pip:

```bash
pip install bib2graph
```

Sembrar desde archivos BibTeX necesita un extra: `bib2graph[bibtex]`.

## Quickstart

De una ecuación de búsqueda hasta un orden de lectura, sin escribir código:

```bash
b2g init mi-investigacion
cd mi-investigacion

b2g seed --equation '"unequal ecological exchange"' --max-results 50   # 1. corpus desde OpenAlex
b2g chain --direction both --max-candidates 300                        # 2. barrido: siguiendo citaciones
b2g curate dump && b2g curate apply curacion.csv                       # 3. curás vos (revisás el CSV)
b2g build                                                              # 4. construye las redes
b2g read top --kind bibliographic_coupling                            #    → orden de lectura (centrales primero)
b2g export --format graphml                                           # → redes en GraphML para Gephi
```

Ese es el hilo completo: **lista ingenua → barrido → curación → redes → lectura dirigida.**
La escritura de tu revisión narrativa —el paso 5— queda de tu lado. Cada comando acepta
`--json` para orquestarlo desde scripts o agentes. Lista completa: `b2g --help`.

### Con Claude Code: pedile a Claude que lo use

La forma más simple de usar bib2graph es **pedirle a Claude que lo use por vos**. bib2graph trae una
**skill de Claude Code** que entrevista tu pregunta de investigación y corre el ciclo completo
(`init → seed → chain → build → read`) sin que escribas comandos:

```bash
pip install bib2graph
b2g skill add            # instala la skill en ~/.claude/skills/bib2graph/
```

Después, en Claude Code: *"usá bib2graph para armar la red de citación de estos papers…"*. La skill
viaja **dentro del mismo paquete** que el CLI, así que **siempre está al día con tu versión** de
bib2graph. Usá `--project` para instalarla solo en el proyecto actual.

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
