# Escenarios BDD/Gherkin — bib2graph

> Especificación ejecutable-en-prosa del CLI `b2g`, anclada a la **verdad del código**
> (`src/bib2graph/cli/commands/*.py`) y a las historias de usuario del [`PRD.md`](../PRD.md) §7.
> Cada `.feature` cubre una épica; cada historia (A1…E2) tiene uno o más `Scenario`.
> Fecha: 2026-06-17. Realidad post-#75 (`--store` eliminada; workspace por `b2g init`).

Estos escenarios son hoy **recetas CLI reproducibles** (se corren a mano, ver abajo). A futuro se
vuelven **ejecutables con `pytest-bdd`** apuntando a este mismo directorio, sin mover archivos.

## Índice — qué historia cubre cada feature

| Feature | Épica (PRD §7) | Historias | Subcomandos anclados |
|---|---|---|---|
| [`A-sembrar.feature`](A-sembrar.feature) | A — Sembrar con ecuaciones | A1, A2, A3, A4, A5 | `seed` (`--equation`/`--spec`/`--from-bib`), `status`, `snapshot` |
| [`B-forrajear.feature`](B-forrajear.feature) | B — Forrajear (chaining) | B1, B2, ~~B3~~, ~~B4~~ | `chain` (`--direction`/`--depth`/`--max-citing`) |
| [`C-curar.feature`](C-curar.feature) | C — Ejercicio bibliotecario | ~~C1~~, ~~C2~~, C3, C4 | `filter`, `curate`, `accept`, `reject` |
| [`D-redes.feature`](D-redes.feature) | D — Proyectar a redes | D1, D2, ~~D3~~, D4 | `build`, `networks`, `export`, `enrich` |
| [`E-reproducibilidad-agente.feature`](E-reproducibilidad-agente.feature) | E — Reproducibilidad + agente | E1, E2 | `snapshot`, `restore`, todos con `--json` |

### Estado por historia (verde = soportado hoy por el CLI · `@pendiente` = gap honesto)

| Historia | Estado | Motivo / fuente del gap |
|---|---|---|
| A1 ecuación de búsqueda | verde | `seed --equation` |
| A2 query ejecutada + reporte | verde | `data.executed_query` + `data.translation_report` |
| A3 semillas / `.bib` | verde | `seed --from-bib` (Ciclo 10, #50) |
| A4 ecuación registrada/versionada | verde (parcial) | persistida en `provenance`/`Manifest`; el sello reproducible se ve en `snapshot` |
| A5 ecuaciones que mutan + acumular | verde | reseed: `seed` con estado previo → `round++`, acumula sobre lo curado |
| B1 back/forward chaining | verde | `chain --direction backward\|forward\|both` |
| B2 profundidad + preview | **parcial / `@pendiente`** | `--depth 1` OK; `depth>1` → `DependencyError` (exit 3). **No existe un comando de "preview de crecimiento" previo al fetch** (PRD §5.1 lo promete; el AS-BUILT lo dejó como `Forager.preview` de librería, no CLI). ROADMAP B2: "`depth>1` futuro" |
| B3 ranking por estructura | verde | `chain` devuelve `data.ranking_preview` (lista `{id, scent}` ordenada). El scent es **bibliométrico** (R4 hecho): `compute_backward_scent` usa `collect_item_to_papers` de los proyectores (acoplamiento hacia atrás = cuántos papers del corpus citan/referencian al candidato), determinista y sin IA |
| ~~B4~~ explicación por IA | **RETIRADA** | ADR 0022: el producto no usa IA generativa. `explain_candidate`/`[llm]` eliminados. Documentada como retirada, sin `Scenario` verde |
| C1 dedup/normalización autores+inst. | **`@pendiente`** | **No hay subcomando CLI**: `normalize`/`deduplicate_keywords` son API de librería (`preprocessors/`), no `b2g`. Instituciones diferidas (ROADMAP C1). El CLI no expone preprocesamiento |
| C2 thesaurus multilingüe | **`@pendiente`** | **No hay subcomando CLI**: `apply_thesaurus` es API de librería (`preprocessors/thesaurus.py`), no `b2g`. Determinista, sin fallback LLM (ADR 0022/0011) |
| C3 filtros incl/excl con conteo | verde | `filter` con `data.steps[].count_before/count_after/excluded` (flujo PRISMA) |
| C4 aceptar/rechazar + biblioteca viva | verde | `accept`/`reject --ids`, `curate --dump`/`--from-csv`; persiste y crece entre corridas |
| D1 cinco proyecciones | verde (parcial) | `build` da 4 redes; la 5ª (cocitación) requiere `enrich` previo (cited_by_id). Instituciones salen si hay `institutions_id` |
| D2 métricas y comunidades | verde | `metrics.json` (density, etc.) + comunidades Louvain; `clusters.csv` en redes de paper |
| D3 asortatividad + composición + proxy | **`@pendiente`** | **No hay camino CLI**: `assortativity()`/`community_composition()` existen como funciones puras en `networks/analyzer.py` y se re-exportan en `networks/__init__.py`, pero `facade._build_artifact` fija `assortativity=None` y **no consume** `NetworkSpec.assortativity_attribute`. Es API de librería, no de CLI |
| D4 export GraphML/CSV | verde | `build` (GraphML+metrics+clusters), `export --format graphml\|csv` |
| E1 snapshot reproducible | verde | `snapshot` (parquet + `manifest.json` con `corpus_hash`); `restore` re-lee sin red |
| E2 CLI `--json` + exit codes | verde | envelope `schema="1"` en todos; exit codes 0–5 |

## Cómo correr los escenarios a mano hoy (recetas CLI reproducibles)

Todo arranca con un **workspace** (post-#75: no existe `--store`; el estado vive en el
`library.duckdb` del workspace, resuelto por `b2g init` + cwd, `--workspace` o `B2G_WORKSPACE`).

```bash
# Setup (Background de cada feature)
uv run b2g init mi-investigacion
cd mi-investigacion          # a partir de acá los comandos resuelven el workspace por cwd

# A — sembrar (con red; recomendá --email para el polite pool de OpenAlex)
uv run b2g seed --equation "unequal exchange" --max-results 50 --json
uv run b2g seed --spec equation.yaml --json
uv run b2g seed --from-bib semillas.bib --json     # sin red

# B — forrajear
uv run b2g chain --direction both --depth 1 --max-citing 25 --json

# C — curar
uv run b2g filter --year-gte 2010 --language en --json
uv run b2g curate --dump --json                    # escribe exports/curacion.csv (solo candidatos)
# (editar la columna decision en exports/curacion.csv)
uv run b2g curate --from-csv exports/curacion.csv --json
uv run b2g accept --ids oa:abc123 --json

# D — redes
uv run b2g enrich --max-citing 25 --json           # puebla cited_by_id (habilita cocitación)
uv run b2g build --json                            # 4 o 5 redes en networks/<kind>/
uv run b2g networks --spec redes.yaml --json       # redes ad-hoc desde YAML
uv run b2g export --format graphml --json

# E — reproducibilidad / agente
uv run b2g snapshot --json                          # snapshots/<...>/corpus.parquet + manifest.json
uv run b2g status --json                            # mapa del lazo, conteos, workspace
uv run b2g restore --from-corpus corpus.parquet --json   # rehidrata sin red

# Caso real reproducible sin red (gate #33):
uv run b2g restore --from-corpus ../examples/valoraciones/corpus.parquet --json
uv run b2g build --json
```

Los pasos con red (`seed --equation/--spec`, `chain`, `enrich`, `monitor`) consultan OpenAlex; los
sin red (`seed --from-bib`, `filter`, `accept`/`reject`/`curate`, `build`, `networks`, `export`,
`snapshot`, `restore`, `status`) son deterministas y no requieren conexión.

## Nota sobre futura ejecutabilidad (pytest-bdd)

Cuando se cableen con `pytest-bdd`, la configuración va en `pyproject.toml`/`pytest.ini` sin mover
estos archivos:

```ini
[pytest]
bdd_features_base_dir = docs/features
```

Los `Then` ya están redactados contra **campos exactos del envelope** (`data.papers_added`,
`data.steps[].excluded`, `data.loop_state`, …), **exit codes exactos** (0–5) y **artefactos**
(`networks/<kind>/network.graphml`), de modo que los step-defs sean implementables sin reescribir
los `.feature`. Los escenarios marcados `@pendiente` quedan como documentación honesta del gap (se
saltarán con `@pytest.mark.skip` o un tag de skip hasta que el CLI los soporte).
