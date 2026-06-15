# bib2graph

**bib2graph** es una librería de Python (con una CLI agente-native delgada encima) que
convierte una **ecuación de búsqueda** —el artefacto estándar y reproducible de la ciencia—
en una **biblioteca viva y curada** de literatura, y la proyecta a **redes bibliométricas**
listas para analizar: acoplamiento bibliográfico, co-citación, colaboración de autores,
colaboración de instituciones y co-ocurrencia de palabras clave.

El backbone de datos es **OpenAlex** (sin clave obligatoria). El flujo **no es un pipeline
lineal** sino el **ciclo iterativo** de la exploración bibliográfica (Bates / Ellis /
Kuhlthau): se siembra desde la ecuación, se forrajea (chaining rankeado por estructura), se
cura, **la idea muta** y se vuelve a sembrar — acumulando sobre lo curado. La colección
**vive y persiste** entre corridas en DuckDB.

> **Estado: v0.2 con capacidades completas** (Hitos 0–6 + 1.5 construidos y testeados). El flujo
> completo **de una ecuación a las redes** ya corre sobre la biblioteca viva, **desde código Python
> y desde el CLI `b2g`** (que **ya no es un placeholder**). Construido: el `Corpus` canónico sobre
> `TabularBackend`, los proyectores/analizadores/exportadores, el backend DuckDB (biblioteca viva),
> las fuentes `OpenAlexSource`/`BibtexSource`, el **forrajeo asistido** (`Forager`, chaining
> rankeado por *information scent*) + `Preprocessor`/thesaurus + filtros PRISMA, y la **CLI
> agente-native `b2g`** (11 subcomandos, `--json` versionado, exit codes; ADR
> [0021](docs/decisiones/0021-cli-agente-native-contrato.md)). **Todavía no** (v0.3+ → v1.0): dedup
> fuzzy (Hito 7), `Enricher` de co-citación (Hito 8), `NetworkSpec` YAML (Hito 9), visualización
> (Hito 10) y costuras Zotero/Neo4j (Hito 11). Ver el [roadmap](docs/ROADMAP.md).

## La arquitectura en un párrafo

bib2graph es **un núcleo puro rodeado de costuras**. El núcleo opera sobre un **`Corpus`**
—una **tabla canónica Arrow** validada con Pydantic v2 (`Paper`/`Author`/`Keyword`/
`Institution` son **vistas derivadas**, no tipos del modelo)— y produce las redes
(`networkx`), métricas, comunidades, asortatividad y exportaciones (GraphML/CSV) como
**funciones puras y testeables**, sin red ni servidores. El `Corpus` se respalda en un
**`TabularBackend`** (Protocol): `InMemoryBackend` (puro, tests) o `DuckDBBackend` (la
**biblioteca viva** por defecto, que muta por SQL y persiste entre corridas) — el núcleo
**no depende de DuckDB**, solo del contrato. Alrededor hay costuras enchufables: **`Source`**
(sembrar — *OpenAlex por defecto* desde una ecuación; BibTeX secundaria), el **forrajeo/
chaining** (expandir rankeando candidatos por *information scent*), **`Store`** (persistir —
`DuckDBStore` fachada de la biblioteca viva; Zotero/Neo4j opt-in) y **`Enricher`** (señal
extra opt-in, ya no estructural).

El **estudio de intercambio ecológico desigual (IED)** es el **caso validador** (corrió el
pipeline end-to-end sobre datos reales de OpenAlex); el de **semiconductores** queda como caso
documentado. Ninguno es el producto.

## Instalación

El proyecto se gestiona con [**uv**](https://docs.astral.sh/uv/) (Python 3.12;
`requires-python >=3.11`). El núcleo incluye OpenAlex (vía `httpx`) y la biblioteca viva
(DuckDB).

```bash
git clone https://github.com/<org>/bib2graph.git
cd bib2graph
uv sync                       # crea .venv e instala núcleo + dev-deps desde uv.lock
uv run pre-commit install     # hooks de pre-commit
```

Capacidades opcionales como extras (lección de v0: núcleo liviano): `uv sync --extra bibtex`
(sembrar desde un `.bib`, **ya construido**, Hito 4). Los extras `--extra dedup` (Hito 7) /
`--extra s2` (Hito 8) / `--extra viz` (Hito 10) / `--extra zotero`·`--extra neo4j` (Hito 11) /
`--extra llm` (`explain_candidate` + thesaurus fuzzy) están **declarados pero aún vacíos**: se
poblarán a medida que se construya cada hito.

## Uso

### Desde el CLI `b2g` (Hito 6 — construido)

De una ecuación a un GraphML, sobre la biblioteca viva, **sin escribir código**. `--store` es
global (una investigación = un archivo `.duckdb`); cada comando acepta `--json` (envelope
versionado) para orquestar desde un agente:

```bash
b2g --store biblioteca.duckdb seed --equation '"unequal ecological exchange" OR "intercambio ecológico desigual"' --email vos@tucorreo.com
b2g --store biblioteca.duckdb chain --direction both --max-candidates 300   # candidatos rankeados por scent
b2g --store biblioteca.duckdb filter --year-gte 2010 --language en --language es   # PRISMA: marca rejected, no borra
b2g --store biblioteca.duckdb build                                          # Networks.quick → artefactos
b2g --store biblioteca.duckdb export --format graphml --out-dir redes/       # serializa GraphML/CSV
b2g --store biblioteca.duckdb status --json                                  # LoopState + conteos por curation_status
```

Subcomandos: `seed`, `chain`, `filter`, `build`, `export`, `snapshot`, `status`, `inspect`,
`validate`, `accept`, `reject`. Exit codes `0` éxito · `1` uso · `2` datos · `3` dependencia ·
`4` red · `5` store bloqueado/corrupto.

### Desde código Python

El mismo flujo, componiendo la librería:

```python
from pathlib import Path
from bib2graph import OpenAlexSource, DuckDBStore, Networks, GraphMLExporter

# 1) Sembrar desde una ecuación consciente (muestra la query ejecutada + reporte de límites)
seed = OpenAlexSource(email="vos@tucorreo.com").seed(
    '"unequal ecological exchange" OR "intercambio ecológico desigual"')
print(seed.executed_query)
print("\n".join(seed.translation_report))

# 2) Persistir en la biblioteca viva (DuckDB; crece entre corridas)
store = DuckDBStore(Path("biblioteca.duckdb"))
store.persist(seed.corpus)

# 3) Proyectar a redes y exportar (acoplamiento sobre el corpus completo, co-autoría, etc.)
for art in Networks.quick(store.load()):
    GraphMLExporter().export(art.graph, art.metrics, out_dir=Path(f"redes/{art.spec.kind}"))
```

`Networks.quick` arma acoplamiento bibliográfico (corpus completo), co-autoría, instituciones
y co-ocurrencia de keywords. La **co-citación** completa requiere un segundo nivel de fetch
(la red más cara) y llega con el `Enricher` opt-in (Hito 8).

## Comandos de desarrollo

```bash
uv run pytest                 # toda la suite
uv run pytest -m unit         # núcleo puro, sin red ni I/O
uv run ruff check src tests && uv run mypy src
```

Las costuras de red se testean con respuestas **mockeadas** (`httpx.MockTransport`); **sin red
en CI**. Convenciones, commits (Conventional Commits) y release en
[`CONTRIBUTING.md`](CONTRIBUTING.md) y [`AGENTS.md`](AGENTS.md).

## Por qué se reescribió (y se giró)

La v0 tenía a **Neo4j como modelo de datos**: nada existía ni se podía probar sin un servidor
corriendo. La reescritura clean-room movió toda la lógica a un **núcleo puro** y dejó
persistencia y enriquecimiento como costuras. Después, **el giro** reorientó la entrada de
**BibTeX a OpenAlex** (que trae referencias y citantes gratis, habilitando el forrajeo) y la
persistencia a una **biblioteca viva en DuckDB**; **el 2º giro** abstrajo el `Corpus` sobre un
`TabularBackend` para escalar sin acoplar el núcleo a DuckDB. El postmortem de v0 (7 lecciones)
está en [`docs/Notas/01-lecciones-v0.md`](docs/Notas/01-lecciones-v0.md); el porqué de cada
decisión, en los [ADRs](docs/decisiones/).

## Documentación

| Documento | Qué cubre |
|-----------|-----------|
| [`docs/PRD.md`](docs/PRD.md) | Producto: usuarios, problema, valor, alcance, historias de usuario. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitectura objetivo: núcleo puro + costuras, `TabularBackend`, flujo iterativo. |
| [`docs/API.md`](docs/API.md) | Contratos públicos: `Corpus`/`TabularBackend`, `Source`, `Store`, proyectores, analizadores, exportadores. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Secuencia de construcción y mapa de releases (v0.1 → v1.0), con estado por hito. |
| [`docs/decisiones/`](docs/decisiones/) | ADRs (decisiones de arquitectura y su porqué) + `registro-ia.md` (decisiones tomadas por la IA). |
| [`docs/metodología.md`](docs/metodología.md) | Método bibliométrico (autoridad de dominio). |
| [`docs/referentes.md`](docs/referentes.md) | Mapa del ecosistema (OpenAlex, bibliometrix, VOSviewer…) y dónde está el hueco. |
| [`docs/critica-base.md`](docs/critica-base.md) · [`docs/Notas/`](docs/Notas/) | Red team del concepto, postmortem de v0, exploración y material de referencia. |
