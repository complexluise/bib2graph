# AGENTS.md — bib2graph

> Guía para agentes que operen en este repositorio. El proyecto está en **reescritura
> clean-room desde cero** (Hito 0 del `docs/ROADMAP.md`): primero docs, luego núcleo puro y
> tests, luego costuras. El diseño objetivo vive en `docs/ARCHITECTURE.md`; los contratos
> públicos en `docs/API.md`; las reglas que motivan este código en `docs/Notas/01-lecciones-v0.md`.
> La decisión arquitectónica vigente es el [ADR 0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md)
> (tabla canónica Arrow + NetworkSpec + snapshot inmutable).

## Estado actual

- **No hay código todavía.** La estructura `src/`, `tests/` y `pyproject.toml` aún no existen;
  el primer paso de Hito 0 es crearlos.
- Toda la información del producto, la arquitectura, los contratos y la secuencia de
  construcción está en `docs/`. **Leer `docs/ROADMAP.md` antes de tocar nada** para entender
  el orden deliberado (núcleo → costuras por defecto → plugins opcionales → capa D).
- **No hay Cursor rules** (`.cursor/`, `.cursorrules`) ni Copilot rules
  (`.github/copilot-instructions.md`).
- **El modelo de dominio es una tabla Arrow** (no 4 dicts + dataclasses). Las "entidades"
  son vistas derivadas. Validación con Pydantic v2. Detalle en `docs/API.md` §1.
- **No hay `InMemoryStore` como costura.** La persistencia por defecto es `ParquetStore` +
  `CorpusSnapshot` (parquet + `manifest.json`). DuckDB queda como extra `[duckdb]`.
- **El CLI es la API para LLM/agentes** (Hito 4). Subprocess + JSON stdout, exit codes
  claros, sin estado.

## Comandos de build / lint / test

El proyecto aún no tiene scripts. Cuando se cree `pyproject.toml`, los comandos canónicos
serán:

- **Instalación editable (núcleo):** `pip install -e .`
- **Instalación con extras:** `pip install -e ".[s2]"` / `.[neo4j]` / `.[duckdb]` /
  `.[dedup]` / `.[viz]` / `.[dev]`
- **Setup dev completo:** `pip install -e ".[dev]"` y `pre-commit install`
- **Tests (toda la suite):** `pytest`
- **Un solo test:** `pytest tests/test_<archivo>.py::TestClase::test_nombre -xvs`
- **Un solo archivo:** `pytest tests/test_corpus.py -x`
- **Por marcador:** `pytest -m unit` / `pytest -m integration` (los tests que toquen red o
  Neo4j deben marcarse `integration` y usar Testcontainers o mocks; el núcleo va en `unit`).
- **Lint:** `ruff check src tests` y `ruff format --check src tests`
- **Tipos:** `mypy src`
- **Todo en uno (sugerido para CI):** `ruff check src tests && mypy src && pytest`

Regla de Hito 0: **linter, formatter, hooks, CI y tooling de release quedan configurados
desde el día uno** (ADR 0006).

## Comandos de release

- **Hacer un commit conventional:** `cz commit` (interactivo, recomendado).
- **Previsualizar el bump de versión:** `cz bump --dry-run`.
- **Bumpear la versión localmente** (no suele ser necesario, lo hace
  `release-please`): `cz bump`.
- **Generar el PR de release** lo hace automáticamente `release-please` desde
  los Conventional Commits mergeados a `main`. Revisá el CHANGELOG antes de
  mergear.

Detalle en [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`VERSIONING.md`](VERSIONING.md).

## Convenciones de código (Python)

### Estilo y formato

- **PEP 8 + `ruff format`** (ancho 88). Sin debates de estilo: el formatter decide.
- **Docstrings** en español (la doc y los comentarios de los ADRs están en español; mantener
  el idioma del proyecto). Una línea para funciones triviales, multilínea con secciones
  `Args:` / `Returns:` / `Raises:` para lo demás.
- **Sin comentarios innecesarios.** El código se explica solo. Los docstrings justifican el
  *por qué*, no el *qué*.
- `from __future__ import annotations` en todos los módulos del paquete.

### Imports

- **No hay efectos de import** (lección 6 de v0). Importar un módulo nunca debe tocar config,
  red, disco ni estado global.
- Dependencias opcionales (extras) se importan de forma **perezosa** dentro de la función que
  las usa, con un mensaje de error claro que apunte al extra faltante.
- Orden: stdlib → third-party → local, separados por línea en blanco. `ruff` lo enforce.

### Tipos

- **Tipado estático en todas las firmas públicas** (`docs/API.md` §Convenciones). El núcleo
  y las costuras son `Protocol` o ABC; las implementaciones concretas los cumplen.
- **Modelos de datos serializables** (`Manifest`, `NetworkSpec`, configs) son **Pydantic
  v2** (`BaseModel`), no dataclasses. Esto da validación, serialización JSON nativa y
  compatibilidad con el CLI/JSON-schema.
- Para entidades internas efímeras (ej. dataclasses para vistas materializadas en tests),
  usar `dataclass(frozen=True)`. **No** son parte del contrato público.
- Para campos opcionales: `str | None`, nunca `Optional[str]` (mypy + ruff lo prefieren).
- Colecciones mutables en dataclasses: `field(default_factory=list)` o `dict`.

### Naming

- **snake_case** para funciones, métodos, variables, módulos.
- **PascalCase** para clases (`Corpus`, `BibtexSource`, `CoCitationProjector`).
- **UPPER_SNAKE** solo para constantes reales (`MIN_WEIGHT_DEFAULT = 1`).
- Costuras terminan con su rol: `XxxSource`, `XxxEnricher`, `XxxStore`, `XxxProjector`,
  `XxxExporter`, `XxxPreprocessor`. Esto las hace localizables con grep y respeta el
  vocabulario del `docs/API.md`.
- **No nombrar cosas como v0** (`enriquecimiento.py`, `analisis/`, scripts ad-hoc). El
  producto es genérico; los nombres deben reflejar el dominio, no el estudio que valida.

### Estructura de paquetes (fijada en ADR 0006)

```
src/bib2graph/
  __init__.py
  corpus.py            # Corpus, Manifest, CorpusSnapshot (wrapper sobre tabla Arrow)
  schemas.py           # modelos Pydantic v2 (validación de schema)
  sources/             # BibtexSource (v0.1); RIS, CSV (futuro, no publicar)
  enrichers/           # SemanticScholarEnricher (v0.1, extra [s2])
  preprocessors/       # normalize, dedup (v0.1 núcleo, fuzzy en [dedup])
  networks/            # Projector, Analyzer, NetworkSpec, NetworkArtifact, Networks
  exporters/           # GraphML, CSV
  stores/              # ParquetStore (v0.1 núcleo); DuckDBStore ([duckdb]);
                       # Neo4jStore ([neo4j], post-v0.2)
  cli.py               # Click, delgado, CLI = API para LLM y agentes
tests/
  unit/                # tests puros, sin red ni I/O (default)
  integration/         # red / APIs externas / Neo4j; @pytest.mark.integration
```

### Manejo de errores

- **Fallar fuerte, no en silencio** (lección 7 de v0). Si falta una dependencia requerida
  (p. ej. `python-louvain` para `detect_communities(method="louvain")`), lanzar un error
  **explícito y temprano** con un mensaje que diga qué instalar. Nunca degradar a otra
  estrategia en silencio.
- **Nada de `try/except` que oculte incompatibilidades de contrato** (lección 3 de v0). Si
  una función recibe una firma distinta, la llamada debe fallar ruidosamente, no
  enmascararse.
- **Acceso defensivo a campos de entrada** (lección de v0 con `research-areas`): usar
  `entry.get("author")` o `entry.get("author", [])`, no acceso directo. En BibTeX con
  `bibtexparser`, los campos opcionales faltan seguido.
- **Idempotencia.** `Corpus.merge` y los `Enricher.enrich` deben ser idempotentes:
  re-ejecutarlos sobre el mismo corpus no debe duplicar datos.
- **Exit codes del CLI** (Hito 4): `0` éxito, `1` error de uso, `2` error de datos, `3`
  dependencia faltante, `4` red no disponible, `5` snapshot corrupto. Sin estado entre
  invocaciones.

### Configuración y secretos

- **Una sola fuente de configuración**, construida explícitamente y pasada a quien la use.
  **Ningún secreto embebido como literal** (lección 1 de v0). API keys de S2, credenciales de
  Neo4j, etc., se inyectan por config / CLI / entorno; **nunca** un default secreto en
  código.
- **Sin contraseñas por defecto.** Si falta una credencial requerida, error claro.
- Sin `os.environ.get("X", "default_literal")` para secretos. Para lo no-secreto, defaults
  explícitos y documentados.

### Modelado de dominio (tabla canónica)

- El `Corpus` se documenta **una sola vez** (`docs/API.md` §1): el schema de columnas de la
  tabla Arrow + la API del wrapper + el `Manifest` + el `CorpusSnapshot`. Los docstrings
  del código deben coincidir con esa sección. Nada de columnas divergentes con campos
  inexistentes (lección 4 de v0: `Institution.address`, `Paper(note=...)`, `CITED_BY`).
- Las "entidades" (`Paper`, `Author`, `Keyword`, `Institution`) **no son tipos del
  modelo**. Si el código define dataclasses con esos nombres, son **vistas temporales**
  para tests/debugging vía `Corpus.materialize(...)`, no contrato público.
- **Relaciones derivadas** (`CO_CITED_WITH`, `COLLABORATED_WITH`, `CO_OCCURS_WITH`) **no
  viven en el corpus**: son salida de un `Projector`. Si aparecen como columna de la
  tabla, está mal.
- `is_seed` distingue el corpus original del traído por enriquecimiento. La red de
  co-citación se construye **solo entre semillas**.

### Funciones puras en el núcleo

- Proyectores, analizadores y la lógica de deduplicación son **funciones puras** sobre
  `pa.Table` o `nx.Graph`. Sin I/O, sin red, sin estado global, sin servidor. Esto es lo
  que permite tests rápidos y reproducibles (la victoria de v0 que faltaba en v0).
- Los `Store`, `Source`, `Enricher` y `Preprocessor` **sí** pueden tener I/O y red; ese es
  su trabajo. Pero las interfaces se inyectan, no se construyen dentro del núcleo.
- `Networks.build(corpus, spec)` y `Networks.quick(corpus)` son funciones puras: mismo
  corpus + mismo spec → mismo `NetworkArtifact`.

### CLI como API para LLM y agentes

- Cada subcomando expone `--json` con salida estructurada (un objeto por corrida,
  estable y versionado).
- Exit codes claros (ver §Manejo de errores).
- Sin estado entre invocaciones: cada llamada es independiente. El agente orquesta
  orquestando subprocess.
- Tool schemas JSON y/o servidor MCP son trabajo futuro (post-v0.2). El CLI ya
  alcanza como frontera programática.

### Publicar solo lo que existe

- Las costuras futuras (`RisSource`, `CsvSource`, `CrossRefEnricher`, `ScopusEnricher`,
  tool schemas JSON, MCP) **no se mencionan en el README ni en `__init__.py` hasta que
  existan** (lección 5 de v0). Documentarlas en `docs/API.md` con estado "futuro — no
  implementado" es válido; importarlas o listarlas en extras sin código real, no.
- Si un cliente de una API externa se inicializa, debe usarse. No cablear imports muertos.

## Tests

- **El núcleo se testea primero, sin red ni servidores** (Hito 1 y 2). Tests sobre
  `Corpus`, proyectores y analizadores con datos sintéticos pequeños y resultados
  conocidos.
- **Tests para `Source`** sobre archivos `.bib` de ejemplo, incluyendo entradas con
  campos opcionales ausentes (el caso que rompía v0 con `KeyError`).
- **Tests para `Enricher`** con respuestas de la API **mockeadas** (`responses`,
  `httpx.MockTransport` o similar). **Sin red en CI.**
- **Tests para `Neo4jStore`** contra una Neo4j efímera (Testcontainers) o mockeando el
  driver. Marcados como `integration`.
- **Tests para `CorpusSnapshot`**: sellar, recargar, comparar `corpus_hash` estable,
  detectar `schema_version` incompatible.
- Cada test debe poder correr en aislamiento: nada de orden implícito, nada de
  fixtures que compartan estado mutable entre tests.

## Estructura de un commit / PR (Conventional Commits)

Mensajes en español, imperativo, formato
[Conventional Commits](https://www.conventionalcommits.org/) estricto:

```
<tipo>(<alcance>): <descripción corta en imperativo, español, sin punto final>

<cuerpo opcional: por qué, no qué>

<footer opcional: BREAKING CHANGE: ... o referencia a issue>
```

Tipos: `feat` (Added), `fix` (Fixed), `refactor` (Changed), `perf` (Changed),
`docs` (no release), `test` (no release), `chore` (no release), `build` (no
release), `ci` (no release), `style` (no release). Alcance sugerido:
`corpus`, `sources`, `enrichers`, `preprocessors`, `networks`, `exporters`,
`stores`, `cli`. Detalle completo en [`CONTRIBUTING.md`](CONTRIBUTING.md).

- Cambios de código van con su test en el mismo commit/PR.
- Cambios a contratos públicos (`docs/API.md`) se discuten en un ADR nuevo en
  `docs/decisiones/` antes de mergear.
- Breaking changes: `BREAKING CHANGE:` en el footer del commit. Bumpea MINOR
  (o MAJOR si estamos en `1.x+`). Ver [`VERSIONING.md`](VERSIONING.md).

## Versionado

**SemVer estricto** (`MAJOR.MINOR.PATCH`). Mientras la mayor sea `0`, la API
se considera inestable: cualquier cambio visible al usuario (no bugfix) bumpa
MINOR. El congelamiento en `1.0.0` requiere API pública estable, cobertura de
tests razonable y un caso real validado (estudio de semiconductores
reproducido). Detalle y tabla de ejemplos en
[`VERSIONING.md`](VERSIONING.md).

## Changelog

**Keep a Changelog** auto-generado por `release-please` desde Conventional
Commits. El PR de release se revisa antes de mergear. Plantilla en
[`docs/RELEASE_TEMPLATE.md`](docs/RELEASE_TEMPLATE.md).

## Dónde mirar primero según la tarea

- Tocar el modelo de datos → `docs/API.md` §1, `docs/ARCHITECTURE.md` §3,
  [ADR 0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md).
- Añadir una red nueva → `docs/ARCHITECTURE.md` §3.2, tabla de proyectores en
  `docs/API.md` §5.
- Añadir una costura (`Source` / `Enricher` / `Store` / `Preprocessor`) →
  `docs/API.md` §2-4 + §11 (preprocessors), ADR correspondiente,
  `docs/Notas/01-lecciones-v0.md` (reglas 1, 3, 5, 6, 7).
- Capa D / `NetworkSpec` → `docs/API.md` §10, se libera en v0.2 (Hito 8).
- Decisiones de dependencias / extras → `docs/decisiones/0005-...`.
- Cambios al método bibliométrico (qué cuenta como co-citación, umbrales) →
  `docs/metodología.md`.
