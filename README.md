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

> **Estado: Hitos 1–9 construidos + remediación R1–R5 + workspace + ejemplos CLI-puros.** El flujo
> **de una ecuación a las redes** corre sobre la biblioteca viva, **desde código Python y desde el CLI
> `b2g`**. Construido: el `Corpus` canónico sobre `TabularBackend`, los proyectores/analizadores/
> exportadores, el backend DuckDB (biblioteca viva), las fuentes `OpenAlexSource`/`BibtexSource`, el
> **forrajeo** (`Forager`, chaining rankeado por *information scent*) + `Preprocessor`/thesaurus +
> filtros PRISMA, el **dedup fuzzy** determinista (Hito 7, `rapidfuzz`), el **`Enricher` de co-citación
> end-to-end** (Hito 8, refs→DOI + citantes vía `b2g enrich`), **`NetworkSpec` YAML** (Hito 9,
> `b2g networks --spec`), el **workspace por investigación** (ADR
> [0029](docs/decisiones/0029-workspace-por-investigacion.md): una investigación = una carpeta,
> `b2g init`) y la **CLI agente-native `b2g`** (`--json` versionado, exit codes; ADR
> [0021](docs/decisiones/0021-cli-agente-native-contrato.md)).
>
> **Remediación completa (Hitos R1–R5):** tras un red-team del código construido
> ([Nota 06](docs/Notas/06-critica-as-built-v0.2.md)) el PO bloqueó un modelo nuevo (ADR
> [0022](docs/decisiones/0022-producto-sin-ia-generativa.md)/[0023](docs/decisiones/0023-capa-constants-modelos-schema.md))
> y la tanda **ya está construida**: el **producto no usa IA generativa**; el *information scent* pasó
> de una heurística de frecuencia de enlace a **scent bibliométrico determinista vía proyectores**
> (acoplamiento/co-citación/centralidad, **sin LLM**, R4); la **reproducibilidad bit a bit** del
> snapshot se arregló con **content-hash determinista** identidad-vs-procedencia (R2); el ciclo es un
> **FSM cíclico** de dominio (`cycle.py`) con `reseed`/ronda y curación visible (R3); se **eliminó**
> `explain_candidate` + el extra `[llm]` (R4); y se endureció la robustez (bulk-load, UTF-8 en la
> frontera, `except` acotados — R5). Ver el [roadmap](docs/ROADMAP/README.md).
>
> **Pendiente hacia v1.0:** la **GUI local** (epic [#34](https://github.com/complexluise/bib2graph/issues/34),
> gateada: núcleo → caso real → GUI), que absorbe la visualización (ex-Hito 10). Las costuras
> Zotero/Neo4j (ex-Hito 11) quedaron **descartadas** (decisión del PO; reabribles solo si aparece
> demanda real). Ver el [roadmap](docs/ROADMAP/04-lo-que-viene.md).

## ⚠️ Experimental · construido con IA (AI-in-the-loop)

**bib2graph es software experimental (alpha).** Mientras la versión mayor sea `0`, la API
pública puede cambiar entre releases `MINOR` sin previo aviso (ver
[`VERSIONING.md`](VERSIONING.md)). Usalo para explorar y validar, **no** como dependencia
estable de producción todavía.

**Declaración de uso de IA.** Este proyecto se construye con un proceso **AI-in-the-loop /
humano-en-el-lazo**: una persona (Product Owner) plantea el problema, toma las decisiones y
**revisa y aprueba** cada cambio; modelos de IA implementan el código, los tests y la
documentación bajo esa dirección. Cada decisión de arquitectura queda en los
[ADRs](docs/decisiones/) y las que tomó la IA en
[`registro-ia.md`](docs/decisiones/registro-ia.md). El detalle del proceso y sus límites
está en [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md).

> **Un solo sentido de "AI-in-the-loop"** (ADR
> [0022](docs/decisiones/0022-producto-sin-ia-generativa.md)): el *desarrollo* de la librería es
> asistido por IA; el *producto* **no usa IA generativa**. La "inteligencia" que asiste el forrajeo es
> **estructura bibliométrica como *information scent*** —acoplamiento/co-citación/centralidad,
> **determinista y reproducible, sin LLM ni embeddings**—, no IA. La **curación es 100% humana** y el
> **sensemaking** (leer tensiones en las redes) también lo hace la persona, asistida por las redes —
> no por un modelo. `explain_candidate` y el extra `[llm]` **se eliminaron** (R4); la antigua "máquina
> de tensiones" **se retiró del producto** (no se difirió). El diferenciador no es "más IA": es una
> **biblioteca viva curada que el investigador posee**, abierta y reproducible.

Como cualquier salida asistida por IA, **verificá los resultados** antes de usarlos en
investigación: la reproducibilidad es un objetivo del diseño, pero la responsabilidad
científica es de quien usa la herramienta.

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
`DuckDBStore` fachada de la biblioteca viva) y **`Enricher`** (señal extra opt-in, ya no
estructural; co-citación end-to-end vía `b2g enrich`).

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
(sembrar desde un `.bib`, Hito 4) y `uv sync --extra dedup` (dedup fuzzy `rapidfuzz`, Hito 7).
*(El extra `[llm]` **se eliminó** en la remediación (R4): el producto no usa IA generativa — ADR
[0022](docs/decisiones/0022-producto-sin-ia-generativa.md).)*

## Uso

### Desde el CLI `b2g`

De una ecuación a un GraphML, sobre la biblioteca viva, **sin escribir código**. Una investigación
= un **workspace** (carpeta autocontenida): se arranca con `b2g init <nombre>` (o `b2g init .`) y,
trabajando **dentro** de ella, los comandos resuelven el store por ambiente. La carpeta con
`workspace.json` es la **única** unidad canónica; un `.duckdb` legacy se adopta con `b2g init .` en su
carpeta (la opción `--store` y el modo degenerado fueron eliminados en #75, ver ADR
[0029](docs/decisiones/0029-workspace-por-investigacion.md)). Cada comando acepta `--json` (envelope
versionado) para orquestar desde un agente:

```bash
b2g init mi-investigacion && cd mi-investigacion
b2g seed --equation '"unequal ecological exchange" OR "intercambio ecológico desigual"' --email vos@tucorreo.com
b2g chain --direction both --max-candidates 300   # candidatos rankeados por scent
b2g filter --year-gte 2010 --language en --language es   # PRISMA: marca rejected, no borra
b2g build                                          # Networks.quick → artefactos
b2g export --format graphml --out-dir redes/       # serializa GraphML/CSV
b2g status --json                                  # estado del ciclo + ronda + curación + conteos
```

Los subcomandos disponibles (**fuente de verdad: `b2g --help`**):

```
accept    Marca papers como accepted en el corpus.
build     Computa las 4 redes con Networks.quick y escribe artefactos.
chain     Expande el corpus con candidatos rankeados por information scent.
curate    Curación en lote: exporta papers a CSV y reimporta decisiones.
enrich    Enriquece el corpus: references→DOI (8a) y cited_by_id (8b).
export    Serializa artefactos de build al formato pedido (GraphML o CSV).
filter    Aplica filtros PRISMA al corpus (marca rejected, no borra).
init      Inicializa una carpeta como workspace de investigación.
inspect   Inspecciona el manifest o un paper específico (read-only).
monitor   Re-chequea OpenAlex por nuevos citantes del corpus.
networks  Construye redes bibliométricas desde una especificación YAML.
reject    Marca papers como rejected en el corpus.
restore   Rehidrata el corpus desde un parquet curado sin tocar la red.
seed      Siembra el corpus.
snapshot  Exporta una foto sellada del corpus actual (parquet + manifest).
status    Muestra el estado del lazo (CycleState) y conteos de curación.
validate  Valida el schema y consistencia del store.
```

Exit codes `0` éxito · `1` uso · `2` datos · `3` dependencia · `4` red · `5` store bloqueado/corrupto.

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
(la red más cara): la cubre el `Enricher` opt-in vía `b2g enrich` (Hito 8, construido).

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
| [`docs/ROADMAP/`](docs/ROADMAP/README.md) | Secuencia de construcción y mapa de releases (v0.1 → v1.0), con estado por hito. |
| [`docs/decisiones/`](docs/decisiones/) | ADRs (decisiones de arquitectura y su porqué) + `registro-ia.md` (decisiones tomadas por la IA). |
| [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) | Estado experimental y declaración de uso de IA (AI-in-the-loop): cómo se construye y qué implica. |
| [`docs/Notas/metodología.md`](docs/Notas/metodología.md) | Método bibliométrico (autoridad de dominio). |
| [`docs/Notas/referentes.md`](docs/Notas/referentes.md) | Mapa del ecosistema (OpenAlex, bibliometrix, VOSviewer…) y dónde está el hueco. |
| [`docs/Notas/critica-base.md`](docs/Notas/critica-base.md) · [`docs/Notas/`](docs/Notas/) | Red team del concepto, postmortem de v0, exploración y material de referencia. |

## Licencia

bib2graph es **software libre**, licenciado bajo la **GNU General Public License v3.0 o
posterior** (`GPL-3.0-or-later`) — ver [`LICENSE`](LICENSE).

```
bib2graph — de una ecuación de búsqueda a redes bibliométricas reproducibles.
Copyright (C) 2026  Equipo bib2graph (complexluise)

Este programa es software libre: podés redistribuirlo y/o modificarlo bajo los
términos de la GNU General Public License publicada por la Free Software
Foundation, ya sea la versión 3 de la Licencia o (a tu elección) cualquier
versión posterior.

Se distribuye con la esperanza de que sea útil, pero SIN NINGUNA GARANTÍA; ni
siquiera la garantía implícita de COMERCIABILIDAD o IDONEIDAD PARA UN PROPÓSITO
PARTICULAR. Ver la GNU General Public License para más detalles.
```

Es **copyleft fuerte**: cualquier obra derivada que se distribuya debe seguir siendo libre y de
código abierto bajo la misma licencia. Esto es deliberado — **esta herramienta queda para la
humanidad** y no puede ser cerrada en un producto propietario. Ver también
[`AI_DISCLOSURE.md`](AI_DISCLOSURE.md).
