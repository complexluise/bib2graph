# E2E 0.15.0 — D2 + red tipada + envelope de Click

E2E end-to-end de las 3 piezas del milestone 0.15.0:

- **Pieza 1** (#320): `ProvenanceEvent.source_kind` en escritura nueva + migración on-read de `chaining:*` (D2 del ADR 0050).
- **Pieza 2** (#321): red tipada en el Arrow del corpus (ADR 0052) — 5 columnas struct + 4 keys de metadata + 7 campos del envelope `--json`.
- **Pieza 3** (#283): errores de Click en `--json`/`B2G_JSON` salen como envelope (enmienda al ADR 0021).

Offline, determinista, reproducible (R2 gate, ADR 0030).

## Setup

```bash
uv run python build_corpus.py     # genera corpus.parquet (8 papers sinteticos con 2 comunidades)
cd examples/e2e-0_15_0
b2g init .
b2g snapshot restore --from-corpus corpus.parquet
b2g curate apply curacion.csv
b2g build
b2g export --format arrow --network-type bibliographic_coupling
```

## Lo que se prueba

| Pieza | Verificación | Esperado |
|---|---|---|
| 1 | `b2g read show --id src:p1 --json` | `provenance[0].source_kind == "seed_equation"` |
| 1 | corpus pre-D2 con `eq-...` | ⚠️ **bug #327 descubierto** (migración on-read no cubre seed) |
| 2 | `b2g export --format arrow` sin build | warning "no network computed", columnas de red ausentes, `network_type: null` en envelope |
| 2 | `b2g export --format arrow` con build | `network_nodes: 8, network_edges: 12, network_communities: 2, network_modularity: 0.5` |
| 2 | `b2g export --format arrow --network-type keyword_cooccurrence` | warning "not supported in Arrow export", `network_type: null`, sin columnas de red |
| 2 | `b2g export --format arrow --network-type cocitation` (sin `cited_by_id`) | `DATA_ERROR` accionable, exit 2 |
| 3 | `B2G_JSON=1 b2g monitor` | envelope `USAGE_ERROR`, exit 2 |
| 3 | `B2G_JSON=1 b2g build --opcion-inexistente` | envelope `USAGE_ERROR`, exit 2 |

## Estructura del corpus sintetico

- **8 papers** (`src:p1` a `src:p8`), con `references_id` materializados.
- **2 comunidades intencionales**:
  - **Comunidad A** (papers p1-p4): todos citan a p5 → acoplamiento p1-p2, p1-p3, p1-p4, p2-p3, p2-p4, p3-p4 (6 aristas, todas con peso 1).
  - **Comunidad B** (papers p5-p8): todos citan a p1 → acoplamiento p5-p6, p5-p7, p5-p8, p6-p7, p6-p8, p7-p8 (6 aristas).
- **Total: 12 aristas** en la red de acoplamiento.
- `intra_community_pagerank` da valores no triviales: los papers centrales de cada comunidad rankean más alto que los periféricos.

## Verificaciones reproducibles

### 1. Pieza 1: `source_kind` en escritura nueva

El corpus se genera con `source_kind="seed_equation"` ya en el JSON. Al restaurarse, el campo se preserva:

```bash
B2G_JSON=1 b2g read show --id "src:p1" | python -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['data']['provenance']:
    print(p['action'], '|', p['equation_id'], '|', p['source_kind'])
"
# Esperado: fetched | eq-e2e-0_15_0 | seed_equation
#           accepted | None | None
```

### 2. Pieza 2: red tipada en el Arrow

Después de `b2g build`, el Arrow del corpus lleva las 5 columnas de red + 4 keys de metadata:

```python
import pyarrow.feather as feather
t = feather.read_table("exports/corpus.arrow")
# 28 columnas (23 canónicas + 5 de red)
# metadata: network_type, network_type_algo, network_resolution, network_scope
# network_edges: list<struct<neighbor_id, weight>> por paper
```

Para el envelope con los 7 campos aditivos:

```bash
B2G_JSON=1 b2g export --format arrow --network-type bibliographic_coupling
# data.network_type: bibliographic_coupling
# data.network_nodes: 8
# data.network_edges: 12
# data.network_communities: 2
# data.network_modularity: 0.5
# data.network_type_algo: louvain
# data.network_resolution: 1.0
```

### 3. Pieza 3: errores de Click como envelope

```bash
B2G_JSON=1 b2g monitor
# {"ok": false, "command": "monitor", "exit_code": 2, "error": {"code": "USAGE_ERROR", ...}}

B2G_JSON=1 b2g build --opcion-inexistente
# {"ok": false, "command": "build", "exit_code": 2, "error": {"code": "USAGE_ERROR", ...}}
```

## Bug descubierto

**#327** — `migrate_provenance_event` no cubre seeds (`eq-...`):

```python
# Corpus pre-D2 con equation_id="eq-20260617T170427" debería derivar
# source_kind="seed_equation", pero queda en None.
```

El fix es de 1 línea en `src/bib2graph/backends/_provenance_compat.py` (sumar `"eq-" → "seed_equation"` al dict `_SOURCE_KIND_FOR_PREFIX`). Es candidato a un patch release (0.15.1).

## Archivos

- `build_corpus.py` — genera `corpus.parquet` (8 papers sintéticos con `references_id` materializados).
- `equation.yaml` — ecuación de búsqueda (referencia; no se usa offline).
- `curacion.csv` — curación masiva declarativa (3 aceptados, 1 rechazado, 4 undecided).
- `corpus.parquet` — el corpus sintético, congelado.
