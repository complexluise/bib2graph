# AGENTS.md — bib2graph

> Guía para agentes que operen en este repositorio. El proyecto es una **reescritura
> clean-room** construida de adentro hacia afuera (docs → núcleo puro y tests → costuras).
> **Estado (v0.3): Hitos 0–6 + 1.5 construidos y tanda de remediación R1–R5 COMPLETA** tras el
> red-team de la Nota 06 y el modelo nuevo (ADR 0022/0023; el producto **no usa IA generativa** —
> el desarrollo SÍ es asistido por IA, pero el scent es bibliométrico determinista). **Próximo:
> Hito 7 (dedup fuzzy).** Ver `docs/ROADMAP.md` y "Estado actual" abajo. El diseño objetivo vive en
> `docs/ARCHITECTURE.md`; los contratos
> públicos en `docs/API.md`; el producto en `docs/PRD.md`; las reglas que motivan este código en
> `docs/Notas/01-lecciones-v0.md`. Las decisiones vigentes tras **el giro** son los ADR
> [0007](docs/decisiones/0007-openalex-backbone.md) (OpenAlex backbone),
> [0008](docs/decisiones/0008-wedge-forrajeo.md) (wedge = forrajeo),
> [0009](docs/decisiones/0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
> [0010](docs/decisiones/0010-agente-native-columna.md) (agente-native columna) y
> [0011](docs/decisiones/0011-thesaurus-multilingue.md) (thesaurus), sobre la base del
> [0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md) (tabla canónica Arrow).

## Estado actual

- **Hitos 0–6 + 1.5 CONSTRUIDOS y remediación R1–R5 COMPLETA** (v0.3, 2026-06-16): de una
  ecuación de búsqueda a las redes bibliométricas, desde código Python **o** desde el CLI `b2g`,
  sobre una biblioteca viva en DuckDB. El árbol `src/bib2graph/` tiene ~30 módulos: `constants.py`
  y `models.py` (capa base, R1), `corpus.py`, `schemas.py`, `cycle.py` (FSM cíclico de dominio, R3),
  `backends/` (`TabularBackend` + `InMemoryBackend` + `DuckDBBackend`), `stores/`
  (`DuckDBStore`), `sources/` (`OpenAlexSource`, `BibtexSource`), `foraging/` (`Forager`,
  scent bibliométrico), `preprocessors/` (normalize + thesaurus), `filters/` (PRISMA),
  `networks/` (proyectores, analyzer, spec, facade), `exporters/` (GraphML, CSV) y `cli/`.
  El **CLI `b2g` es real** —paquete `cli/` con 12 subcomandos en `cli/commands/`, no un
  placeholder—. **327 tests verdes** (mypy/ruff limpios; el núcleo importa sin `duckdb`).
- **Tanda de remediación R1–R5 COMPLETA** (v0.3, 2026-06-16). Tras el red-team del AS-BUILT
  ([`docs/Notas/06-critica-as-built-v0.2.md`](docs/Notas/06-critica-as-built-v0.2.md)) el PO bloqueó
  un **modelo nuevo** (ADR [0022](docs/decisiones/0022-producto-sin-ia-generativa.md)/
  [0023](docs/decisiones/0023-capa-constants-modelos-schema.md) + enmiendas), ya construido:
  **R1** — **capa base** `constants.py`/`models.py`/`schemas.py` única; **R2** — **identidad ≠
  procedencia** (el `corpus_hash` excluye timestamps, reloj en la frontera, Louvain seeded);
  **R3** — **FSM cíclico de dominio** `cycle.py` (sale del backend) con `reseed`/ronda + curación
  transversal en `status`; **R4** — **scent bibliométrico vía proyectores**, **el producto NO usa
  IA generativa** (se eliminaron `foraging/explain.py`, `explain_candidate`, el extra `[llm]` y la
  "máquina de tensiones"); **R5** — robustez (bulk-load, UTF-8 en la frontera, retry, footguns).
  Ver `docs/ROADMAP.md` (Hitos R1–R5). **PRÓXIMO: Hito 7** (dedup fuzzy `[dedup]`). El entorno se
  levanta con `uv sync`.
- Toda la información del producto, la arquitectura, los contratos y la secuencia de
  construcción está en `docs/`. **Leer `docs/ROADMAP.md` antes de tocar nada**: cada hito declara
  qué historias del PRD §7 cumple, sus criterios de aceptación (DoD) y los tests TDD que se
  escriben. El orden es deliberado (núcleo puro → costura local DuckDB → costura red OpenAlex →
  forrajeo → CLI → opcionales).
- **No hay Cursor rules** (`.cursor/`, `.cursorrules`) ni Copilot rules
  (`.github/copilot-instructions.md`).
- **El modelo de dominio es una tabla Arrow** (no 4 dicts + dataclasses). Las "entidades"
  son vistas derivadas. Validación con Pydantic v2. Detalle en `docs/API.md` §1.
- **La persistencia por defecto es `DuckDBStore` stateful** — la **biblioteca viva** (ADR 0009):
  acumula entre corridas, con tablas de procedencia/curación. Es **núcleo**, no extra. El
  **snapshot** (`CorpusSnapshot`: parquet + `manifest.json`) es un **export sellado** derivable
  del estado vivo, no la persistencia en sí; `ParquetStore` es solo formato de export.
- **OpenAlex es el backbone de datos** (ADR 0007): trae refs + citantes + afiliaciones per-autor.
  BibTeX es `Source` secundaria. El enricher S2 ya **no es estructural**.
- **El CLI es la API para LLM/agentes** (Hito 6). Subprocess + JSON stdout, exit codes
  claros, sin estado entre invocaciones (el estado vive en DuckDB).

## Comandos de build / lint / test

El proyecto se gestiona con **uv** (entorno + lockfile + versión de Python). **No** uses
`pip install` ni edites `[project.dependencies]` a mano: uv mantiene `pyproject.toml` y
`uv.lock` sincronizados. Comandos canónicos (siempre `uv run`, sin activar el venv):

- **Setup dev completo:** `uv sync` (crea `.venv`, instala núcleo + dev-deps desde `uv.lock`)
  y `uv run pre-commit install`.
- **Con una capacidad opcional:** `uv sync --extra s2` / `--extra zotero` / `--extra neo4j` /
  `--extra dedup` / `--extra viz`. Sin dev-deps: `uv sync --no-dev`. *(No hay extra `[llm]`:
  **se eliminó** en la remediación R4 — el producto no usa IA generativa, ADR 0022.)*
- **Agregar dependencias:** `uv add <pkg>` (núcleo) · `uv add --dev <pkg>` (desarrollo) ·
  `uv add --optional <extra> <pkg>` (capacidad opcional).
- **Tests (toda la suite):** `uv run pytest`
- **Un solo archivo:** `uv run pytest tests/unit/test_corpus.py -x`
- **Un solo test:** `uv run pytest tests/unit/test_corpus.py::test_merge_idempotente -xvs`
- **Por marcador:** `uv run pytest -m unit` / `uv run pytest -m integration` (los tests que
  toquen red o Neo4j se marcan `integration` y usan Testcontainers o mocks; el núcleo va en
  `unit`).
- **Lint:** `uv run ruff check src tests` y `uv run ruff format --check src tests`
- **Tipos:** `uv run mypy src`
- **Todo en uno (gate de CI):** `uv run ruff check src tests && uv run mypy src && uv run pytest`

Regla de Hito 0: el **tooling LOCAL** —uv, linter (`ruff`), tipos (`mypy`), tests
(`pytest`), hooks (`pre-commit`) y **commitizen** (linter de Conventional Commits +
`cz bump --dry-run` para previsualizar el bump)— quedó configurado desde el día uno
(ADR 0006/0010). El gate de calidad corre en local (`ruff` + `mypy` + `pytest`). En
cambio, **la automatización de releases (release-please + CI/PyPI) está DISEÑADA pero
AÚN NO conectada**: no existe `.github/` ni CI/GitHub Actions (ver §Comandos de release).
La versión de Python la fija `.python-version` (3.12; `requires-python >=3.11`).

## Comandos de release

El **mecanismo de release DISEÑADO es `release-please`** (PR de release → bump +
`CHANGELOG.md` → tag + publicación a PyPI; ver [`VERSIONING.md`](VERSIONING.md) y
[ADR 0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md)). **Pero AÚN NO está
conectado**: no existe `.github/` ni CI. Hasta conectarlo, el versionado/tag se hace
**manual/local**. `commitizen` **no** es el publicador de releases: es (a) el linter de
Conventional Commits (hook de `pre-commit`) y (b) la herramienta para **previsualizar**
el bump localmente con `cz bump --dry-run`.

- **Hacer un commit conventional:** `uv run cz commit` (interactivo, recomendado).
- **Previsualizar qué versión saldría:** `uv run cz bump --dry-run` (solo preview, no publica).
- **Tags actuales (locales, anotados, sin push):** `v0.1.0` (cierre Hitos 1–4) y `v0.2.0`
  (Hitos 5–6), creados a mano. El **`v0.3.0`** (remediación R1–R5) está **por taguearse** sobre
  HEAD. El **release publicado** (push de tags + artefactos a PyPI) queda **pendiente de conectar
  `release-please` + CI**.

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
  constants.py         # CAPA BASE (ADR 0023, Hito R1): Col/CurationStatus/NetworkKind (StrEnum),
                       # fuente única de literales. Todo lo demás depende de esta capa.
  models.py            # CAPA BASE (ADR 0023): ProvenanceEvent(BaseModel), parseo que falla ruidoso
  corpus.py            # Corpus, Manifest, CorpusSnapshot (wrapper sobre tabla Arrow)
  schemas.py           # PaperRow (Pydantic) ÚNICA fuente; CORPUS_SCHEMA (Arrow) derivado/verificado
  cycle.py             # FSM CÍCLICO de dominio puro (ADR 0016 enmendado, Hito R3): SEEDED→…→
                       # MONITORED + reseed/ronda. Sale del backend; el backend solo lo persiste.
  sources/             # OpenAlexSource (núcleo, backbone); BibtexSource (secundaria);
                       # RIS, CSV (futuro, no publicar)
  backends/            # TabularBackend (Protocol) + InMemoryBackend (núcleo puro) +
                       # DuckDBBackend (biblioteca viva, carga perezosa de duckdb; persiste cycle)
  foraging/            # Forager (chaining + ranking por scent BIBLIOMÉTRICO vía proyectores, Hito R4).
                       # SIN explain.py / explain_candidate / [llm] (eliminados, ADR 0022)
  preprocessors/       # normalize + thesaurus multilingüe DETERMINISTA, sin fallback LLM (núcleo);
                       # dedup fuzzy DETERMINISTA en [dedup]
  filters/             # filtros de inclusión/exclusión con conteo PRISMA (núcleo)
  enrichers/           # FUTURO (Hito 8): OpenAlexEnricher opt-in (refs→DOI, 2º nivel); S2 ([s2])
  networks/            # Projector, Analyzer, NetworkSpec, NetworkArtifact, Networks
  exporters/           # GraphML, CSV
  stores/              # DuckDBStore (núcleo, por defecto: biblioteca viva);
                       # ParquetStore (export); ZoteroStore ([zotero], V1.1);
                       # Neo4jStore ([neo4j], post-V1)
  cli/                 # paquete de 3 capas (Click → run_<cmd>() núcleo → envelope/errores);
                       # cli/commands/ = 12 subcomandos (incl. monitor, FSM→MONITORED). CLI = API
                       # para LLM y agentes (Hito 6, ARCHITECTURE.md §6.3). No es un cli.py plano.
tests/
  unit/                # tests puros, sin red ni I/O (default)
  integration/         # red / APIs externas / Neo4j; @pytest.mark.integration
```

La estructura es orientativa (ADR 0006): un módulo plano (`corpus.py`) o un paquete
(`sources/`) es decisión del implementador según crezca. Lo fijo son los **nombres del
dominio** y los **contratos de `docs/API.md`**.

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
- **Exit codes del CLI** (Hito 6): `0` éxito, `1` error de uso, `2` error de datos, `3`
  dependencia faltante, `4` red no disponible, `5` store/snapshot corrupto. Sin estado entre
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
- `is_seed` distingue el corpus original (ecuación/semillas) del traído por el **forrajeo/
  chaining**. El **acoplamiento bibliográfico** se proyecta sobre el **corpus completo** (no solo
  semillas; ciudadano de primera, crítica #2); la **co-citación** usa `scope="seeds_only"` y
  requiere el 2º nivel de fetch (el más caro). Ver `docs/API.md` §7.

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
- Tool schemas JSON y/o servidor MCP son trabajo futuro (post-v0.3). El CLI ya
  alcanza como frontera programática.

### Publicar solo lo que existe

- Las costuras futuras (`RisSource`, `CsvSource`, `CrossRefEnricher`, `ScopusEnricher`,
  tool schemas JSON, MCP) **no se mencionan en el README ni en `__init__.py` hasta que
  existan** (lección 5 de v0). Documentarlas en `docs/API.md` con estado "futuro — no
  implementado" es válido; importarlas o listarlas en extras sin código real, no.
- Si un cliente de una API externa se inicializa, debe usarse. No cablear imports muertos.

## Tests

> **TDD selectivo.** En el núcleo, el test va **antes** del código. Pero **no se testea cada
> cosa**: se testea donde hay lógica, un contrato o riesgo de regresión; no wrappers finos,
> plumbing de Click, ni el cliente HTTP de terceros. La disciplina completa (qué SÍ / qué NO) y
> los tests concretos por hito están en `docs/ROADMAP.md` (§"Disciplina de tests" + cada hito).

- **El núcleo se testea primero, sin red ni servidores** (Hitos 1 y 2). Tests sobre
  `Corpus`, proyectores y analizadores con datos sintéticos pequeños y **resultados
  conocidos** calculados a mano.
- **Tests para `Source`**: `OpenAlexSource` contra respuestas **mockeadas**
  (`httpx.MockTransport`), incluyendo el parser defensivo del `abstract_inverted_index`;
  `BibtexSource` sobre `.bib` con campos opcionales ausentes (regresión del bug T1 / `KeyError`).
- **Tests para `Forager`**: orden del ranking por *information scent*, preview/tope sin mutar el
  corpus.
- **Tests para `DuckDBStore`**: persistir → releer en instancia nueva (acumulación entre
  corridas), idempotencia de `persist`, procedencia/curación recuperables — DuckDB en proceso.
- **Tests para `Enricher`** con respuestas de la API **mockeadas**. **Sin red en CI.**
- **Tests para `Neo4jStore`** contra una Neo4j efímera (Testcontainers) o mockeando el
  driver. Marcados como `integration`.
- **Tests para `CorpusSnapshot`**: sellar, recargar, comparar `corpus_hash` estable,
  detectar `schema_version` incompatible.
- **Tests de contrato `--json` del CLI** (Hito 6): la forma de la salida no driftea; mapeo de
  errores a exit codes.
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
`corpus`, `sources`, `foraging`, `preprocessors`, `filters`, `enrichers`,
`networks`, `exporters`, `stores`, `cli`. Detalle completo en
[`CONTRIBUTING.md`](CONTRIBUTING.md).

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

**Keep a Changelog**. Cuando se conecte `release-please` (mecanismo diseñado, ADR 0006 /
[`VERSIONING.md`](VERSIONING.md)), el PR de release actualizará el `CHANGELOG.md` desde los
Conventional Commits. Como ese tooling **aún no está conectado** (no hay `.github/`/CI), por
ahora las secciones se mantienen **a mano** antes de cada tag (con `cz bump --dry-run` como
ayuda de preview local). Plantilla en [`docs/RELEASE_TEMPLATE.md`](docs/RELEASE_TEMPLATE.md).

## Dónde mirar primero según la tarea

- Empezar cualquier hito → `docs/ROADMAP.md`: historias (PRD §7), criterios de
  aceptación (DoD) y los tests TDD a escribir.
- Tocar el modelo de datos → `docs/API.md` §1, `docs/ARCHITECTURE.md` §3,
  [ADR 0006](docs/decisiones/0006-tabla-canonica-y-networkspec.md).
- Añadir una red nueva → `docs/ARCHITECTURE.md` §3.2, tabla de proyectores en
  `docs/API.md` §7.
- Sembrar / forrajear → `docs/API.md` §2 (`Source`/OpenAlex) y §5 (`Forager`),
  [ADR 0007](docs/decisiones/0007-openalex-backbone.md),
  [ADR 0008](docs/decisiones/0008-wedge-forrajeo.md).
- Persistencia / biblioteca viva → `docs/API.md` §4,
  [ADR 0009](docs/decisiones/0009-biblioteca-viva-duckdb.md).
- Normalización / thesaurus → `docs/API.md` §6,
  [ADR 0011](docs/decisiones/0011-thesaurus-multilingue.md).
- Añadir una costura (`Source` / `Enricher` / `Store`) → `docs/API.md` §2-4, ADR
  correspondiente, `docs/Notas/01-lecciones-v0.md` (reglas 1, 3, 5, 6, 7).
- CLI agente-native → `docs/API.md` §convenciones, `docs/ARCHITECTURE.md` §6.3,
  [ADR 0010](docs/decisiones/0010-agente-native-columna.md) (Hito 6).
- Capa D / `NetworkSpec` → `docs/API.md` §10, se libera en v0.3+ (Hito 9).
- Decisiones de dependencias / extras → `docs/decisiones/0005-...`.
- Cambios al método bibliométrico (qué cuenta como co-citación, umbrales) →
  `docs/metodología.md`.
