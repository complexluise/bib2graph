# 0006 — Tabla canónica (Arrow) + NetworkSpec declarativa + snapshot inmutable

- **Estado:** Aceptada
- **Fecha:** 2026-06-14
- **Relacionada con:** [0001](0001-herramienta-reutilizable.md), [0002](0002-modelo-agnostico-backend.md), [0003](0003-persistencia-opcional.md), [0004](0004-enriquecimiento-opcional.md), [0005](0005-dependencias-extras.md)
- **Deroga parcialmente:** nada (los ADRs 1–5 son de producto y siguen vigentes).
- **Sustituye:** el modelo de datos implícito en `ARCHITECTURE.md` §3 (Corpus = 4
  dicts + dataclasses) y la API de `Corpus` en `API.md` §1.
- **Actualización (2026-06-15):** la sección **"Snapshot inmutable, sin in-memory store"** queda
  **supersedida por [0009](0009-biblioteca-viva-duckdb.md)** (biblioteca viva stateful en DuckDB;
  el snapshot pasa a ser un *export* derivable del estado vivo). El resto de este ADR (tabla
  canónica Arrow + Pydantic, `NetworkSpec`, versionado/tooling) **sigue vigente**.
- **Enmienda AS-BUILT (2026-06-17, Hito 9 — capa declarativa NetworkSpec):** la `NetworkSpec` de
  este ADR ganó su **carga declarativa desde YAML**. Construido: el loader **`load_specs(path)`**
  (`networks/spec.py`, re-exportado desde `bib2graph.networks`) con **esquema raíz `networks:`** (lista
  de entradas, cada una validada con `NetworkSpec(**entry)`); el campo **`resolution: float = 1.0`**
  (resolución de Louvain, fuera del `corpus_hash`); **`model_config = ConfigDict(extra="forbid")`**
  (campo desconocido → error accionable); el **16° subcomando `b2g networks --spec <yaml>`**; y
  **`pyyaml`** promovido a dependencia del núcleo (import perezoso). El cuerpo histórico abajo
  (`NetworkSpec` como hook mínimo) **sigue vigente**; esto solo registra el AS-BUILT. Ver API.md §10.
- **Enmienda (2026-06-15, 2º giro):** el punto "el `Corpus` es un *wrapper* delgado sobre la
  tabla" (sección A) queda **enmendado por [0015](0015-corpus-tabular-backend.md)**: el `Corpus`
  ya no envuelve una `pa.Table` cruda con semántica de valor, sino un **`TabularBackend`
  (Protocol)** que delega las mutaciones (`InMemoryBackend` puro / `DuckDBBackend` por defecto).
  La **tabla canónica Arrow sigue siendo la representación del contenido** (`corpus.to_arrow()`
  es el puente a los proyectores puros); solo cambia el *contenedor*. El resto de A (Arrow +
  Pydantic, vistas derivadas, columnas de estado) **sigue vigente**.

## Contexto

El diseño v1 (documentado en `ARCHITECTURE.md` y `API.md`) modelaba el `Corpus`
como cuatro `dict` indexados más dataclasses (`Paper`, `Author`, `Keyword`,
`Institution`). Esto funcionaba como contrato, pero tenía tres costos concretos
que aparecieron al planificar la implementación:

1. **Merge, dedup e idempotencia** requerían código a mano cuatro veces y luego
   reglas de reconciliación para listas anidadas (`author_ids`,
   `reference_dois`). Bibliometrix (R) lo resuelve con un data frame canónico y
   `groupby`.
2. **Normalización de campos** (parseo de nombres, canonicalización de keywords,
   thesaurus) se repetía entre `Source`, `Enricher` y `[dedup]`. No había un
   lugar único para decidir "cómo se ve un autor".
3. **No había artefacto serializable nativo** para el caso "herramienta
   interna repetible": el corpus no se podía guardar a disco y volver a leer
   sin reinventar un formato.

Una exploración más amplia (cuatro arquitecturas candidatas) está en
`exploracion/arquitecturas-alternativas.md`.
Las alternativas evaluadas y descartadas:

- **Event sourcing / log inmutable:** sobreingeniería; el mismo poder se
  obtiene con snapshot + manifest.
- **Grafo de primera (NetworkX como contrato):** revive la v0 que la lección 2
  de `lecciones-v0.md` justamente rechaza (núcleo dependiente del backend).
- **Solo A sin D:** la tabla canónica es necesaria pero no suficiente para el
  caso "investigador piensa por red" y para el futuro GUI.

## Decisión

Adoptar **A + D** de la exploración:

### A. Tabla canónica única (Arrow + Pydantic v2)

- **Una sola tabla Arrow** (`pa.Table`) con schema fijo por paper es la
  representación intermedia del pipeline. Validada en el wrapper público
  con **Pydantic v2**; si Pydantic se vuelve cuello de botella, se migra la
  capa de validación a `msgspec.Struct` sin tocar el contrato público.
- El `Corpus` es un *wrapper* delgado sobre la tabla, **no un grafo, no un
  set de entidades**. Tiene `table: pa.Table`, `manifest: Manifest`, y
  métodos puros (`add_paper`, `merge`, `seeds`, `seal`, `materialize`).
- `Paper`, `Author`, `Keyword`, `Institution` **dejan de ser entidades de
  primera clase** en el modelo. Son **vistas derivadas** vía `groupby +
  explode` sobre la tabla. Opcionalmente, dataclasses frozen *temporales*
  vía `Corpus.materialize(...)` para tests y debugging. **No son parte del
  contrato público.**
- `is_seed` y `provenance` son **columnas** de la tabla, no atributos de
  dataclass. Esto evita que el "estado de pipeline" contamine la entidad.

### D. `NetworkSpec` declarativa (capa v0.2)

- En v0.1: el hook `Networks.build(corpus, spec) -> NetworkArtifact` ya
  existe como función pura. La API pública de `NetworkSpec` se congela en
  v0.2.
- En v0.1: `Networks.quick(corpus)` arma las 4 specs razonables con
  defaults sensatos. Cubre el caso "investigador académico, baja fricción".
- En v0.2: se libera `NetworkSpec` como dataclass frozen con YAML loader
  (`b2g networks --spec redes.yaml`).

### Snapshot inmutable, sin in-memory store

- **No existe un `Store` in-memory como costura.** La persistencia por
  defecto es siempre un `CorpusSnapshot`: una carpeta con
  `corpus.parquet` + `manifest.json` (hash, schema_version, fuentes,
  parámetros, versión de la lib). DuckDB queda como store opcional en el
  extra `[duckdb]`.
- Cada corrida del pipeline deja un log estructurado (qué source, qué
  enricher, qué preprocess, qué specs). El log + el snapshot hacen que la
  corrida sea **reproducible a partir de los artefactos en disco**, no del
  estado de la sesión.

### Versionado, changelog, tooling

- **SemVer estricto** (`0.y.z` hasta `1.0.0`). Breaking changes en `0.y`
  documentados con `BREAKING:` en el CHANGELOG.
- **Changelog auto** vía `release-please` desde Conventional Commits, formato
  [Keep a Changelog](https://keepachangelog.com/).
- **CLI como API para LLM/agentes** desde v0.1: subprocess + JSON stdout,
  exit codes claros, sin estado. Tool schemas JSON y/o MCP son trabajo
  futuro (v0.3+) si la demanda lo justifica; el CLI ya es la frontera
  programática.
- **Tooling estándar desde Hito 0:** `ruff`, `mypy`, `pytest`, `pre-commit`,
  `commitizen`, `release-please`, GitHub Actions. Todo declarado en
  `pyproject.toml` + `.pre-commit-config.yaml` + `.github/workflows/`.

## Estructura nueva del núcleo

```
src/bib2graph/
  __init__.py
  corpus.py            # Corpus, Manifest, CorpusSnapshot, schema Arrow
  schemas.py           # modelos Pydantic v2 para validación
  sources/             # BibtexSource (v0.1); RIS, CSV (futuro, no publicar)
  enrichers/           # SemanticScholarEnricher (v0.1, extra [s2])
  preprocessors/       # normalize, dedup (v0.1 núcleo, fuzzy en [dedup])
  networks/            # Projector, Analyzer, NetworkSpec, NetworkArtifact
  exporters/           # GraphML, CSV
  stores/              # ParquetStore (v0.1 núcleo); DuckDBStore ([duckdb]);
                       # Neo4jStore ([neo4j], v0.2)
  cli.py               # Click, delgado. CLI = API para agentes.
tests/
  unit/                # tests puros, sin red ni I/O (default)
  integration/         # red / APIs externas / Neo4j; @pytest.mark.integration
```

## Consecuencias

- **Menos código, menos drift.** Merge y dedup dejan de ser cuatro funciones
  paralelas. Tests sobre tablas chiquitas con resultados conocidos son
  inmediatos.
- **Reproducibilidad casi gratis.** `parquet` + `manifest.json` se
  versionan en git-lfs o DVC. Una corrida se reproduce a partir de sus
  artefactos, no del estado de la sesión.
- **Interoperabilidad nativa.** Arrow es el denominador común de pandas,
  polars, duckdb. La lib no compite con ese ecosistema, se apoya.
- **El CLI es la frontera para agentes.** Cualquier agente (LLM hoy,
  automatización mañana) puede orquestar la lib sin reinventar wrappers.
- **Costo:** reescribir `ARCHITECTURE.md` §3 y `API.md` §1; reorganizar
  `ROADMAP.md`. No hay código todavía, así que el costo se paga una vez.
- **Tensiones resueltas** (antes abiertas en `ARCHITECTURE.md` §9):
  - §9.1 representación interna → tabla Arrow + Pydantic.
  - §9.4 driver Neo4j → irrelevante: Neo4j pasa de "sustrato" a
    "adaptador opcional" mapeando tabla → grafo. El driver se elige al
    implementar el adaptador.
  - §9.2 Publisher/ResearchArea → atributos opcionales en la tabla, no
    entidades. Se promueven a entidades solo si una red los necesita.
  - §9.3 RawAuthor/Author → un solo estado en una columna
    `author_normalized: bool`; la canonicalización es un Preprocessor.

## Próximos pasos (orden estricto)

1. Reescribir `ARCHITECTURE.md` §3, §6, §9 con esta decisión.
2. Reescribir `API.md` §1 (modelo), §5–7 (proyectores, analizadores,
   exportadores) y agregar §10 (NetworkSpec, v0.2).
3. Reorganizar `ROADMAP.md` con 9 hitos (ver `Notas/02-exploracion/...` §5).
4. Crear `CHANGELOG.md` (Unreleased), `CONTRIBUTING.md` (Conventional
   Commits), `VERSIONING.md`, plantilla de release.
5. Actualizar `AGENTS.md` con comandos de release, semver, changelog y
   notas sobre el CLI como API para agentes.
6. Recién entonces: `pyproject.toml` mínimo (Hito 0) y arrancar.
