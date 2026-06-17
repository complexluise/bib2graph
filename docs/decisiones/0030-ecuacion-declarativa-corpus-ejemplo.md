# 0030 — Ecuación declarativa (`equation.yaml`) + `restore` de corpus curado + corpus de ejemplo commiteado

- **Estado:** **Aceptada — AS-BUILT ✅** (9a + 9b + Ciclo 10 completos, 2026-06-17). 9a: `restore` +
  `equation.yaml` cargable; **9b: workspace de ejemplo `examples/valoraciones/` (corpus 137 filas)
  + gate de reproducibilidad R2** (7 tests; cierra el Ciclo #33). **Ciclo 10: `seed --from-bib`
  (3er modo, sin red) + filtro de año real (`min_year`/`max_year`) + `examples/bibtex/`** (cierra
  issue #50; el §Diferido del corte 9a queda superado). Ver §AS-BUILT Ciclo 10 al final.
- **Fecha:** 2026-06-17
- **Enmienda (de este ADR):** [0029](0029-workspace-por-investigacion.md) — el workspace
  (carpeta autocontenida) gana una variante **commiteable** como **caso real reproducible**:
  un workspace/corpus de ejemplo congelado en `examples/`, excepción explícita al gitignore
  de datos de usuario (materializa en **9b**).
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (`NetworkSpec` YAML +
  `load_specs`, **precedente directo** de la capa declarativa de este ADR),
  [0007](0007-openalex-backbone.md) (OpenAlex backbone; la ecuación normal pega a la red),
  [0017](0017-reproducibilidad-historia-snapshot.md) / [0022](0022-producto-sin-ia-generativa.md)
  (R2 — identidad ≠ procedencia, `corpus_hash` order-independent, Louvain seeded: lo que hace
  reproducible al ejemplo), [0016](0016-maquina-estados-lazo.md) (FSM permisiva; `restore` reusa
  la transición `filter` → `FILTERED`), [0018](0018-source-agnostico-calidad.md) (contrato
  `Source`: `seed()` por ecuación / `load()` por archivo, mínimo universal; **BibTeX = `Source`
  secundaria legítima**), [0013](0013-identidad-hash-merge-corpus.md) (identidad estable +
  `corpus_hash`), [0005](0005-dependencias-extras.md) (extra `[bibtex]` perezoso).
- **Prerequisito de:** Ciclo #33 ("caso real reproducido") → **gate de #34** (epic GUI).
- **Issues / contexto:** #14 (`--max-results`), #30 (`--exclude`), #25/#31 (redes legibles +
  `clusters.csv`), #26 (`curate --from-csv`), [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md)
  (sesión QA — ecología de valoraciones; agujero R2 de reproducibilidad de comunidades).

## Contexto

El Ciclo #33 pide un **caso real reproducido por CLI**, que sirva de gate para la epic GUI
(#34): un tercero (o el CI) debe poder correr el lazo end-to-end —semilla → curación → redes →
clusters— sobre un corpus real y obtener **el mismo resultado**, sin acceso a red. Hoy hay
tres huecos que lo impiden:

1. **La ecuación de búsqueda no es un artefacto.** `b2g seed --equation '<texto>'` recibe la
   ecuación como string suelto en la línea de comandos, junto con `--max-results` (#14),
   `--exclude` (#30, repetible) y `--native`. No hay forma de **versionar** la ecuación
   completa de una investigación como un archivo declarativo, ni de cargarla por el CLI. El
   Hito 9 ([ADR 0006](0006-tabla-canonica-y-networkspec.md) enmienda AS-BUILT) ya estableció el
   **precedente**: las redes pasaron de `Networks.quick` + flags a un `redes.yaml` cargable con
   `load_specs(path)` (esquema raíz `networks:`, validación Pydantic con `extra="forbid"`,
   errores accionables citando archivo + índice + campo, subcomando `b2g networks --spec`). La
   ecuación de búsqueda merece el mismo tratamiento declarativo.

2. **No hay convención para commitear un corpus de ejemplo.** El `.gitignore` excluye
   deliberadamente **todos los datos de usuario** (`*.duckdb`, `prueba/`, `redes/`,
   `snapshots/*.parquet`): "bibliotecas vivas, workspaces de prueba locales, redes exportadas
   — NUNCA al repo". Eso es correcto para datos de investigación reales, pero **deja al
   proyecto sin un caso real reproducible en el árbol**, que es justo lo que #33 necesita y lo
   que falta para congelar `1.0.0` (un caso real validado, ver `VERSIONING.md` y PRD §10).

3. **Rehidratar un corpus ya curado no tiene comando, y NO es "seed".** El gate #33 reproduce
   **sin red** un corpus que **ya pasó el lazo** (semilla → curación → `decision` marcada),
   congelado como parquet. Eso **no es sembrar** (sembrar = traer material nuevo y empezar el
   lazo, tras lo cual se forrajea/cura); es **restaurar estado ya procesado**. Hoy la capa Arrow
   ya soporta hidratar un corpus desde una tabla (`src/bib2graph/corpus.py:Corpus.from_arrow`;
   `CorpusSnapshot` ya es parquet+manifest sellado, `corpus.py:CorpusSnapshot.load`/`.corpus`),
   pero **no había un comando CLI** que tomara un parquet/snapshot y lo persistiera en el
   `library.duckdb` de un workspace. `b2g seed` siembra contra OpenAlex
   (`cli/commands/seed.py:run_seed` → `OpenAlexSource.seed`) y no debe usarse para esto:
   semánticamente, rehidratar el mismo corpus curado dentro de `seed` no tiene sentido (ya está
   curado, ya forrajeado). Faltaba el comando de **restore/import** de un export sellado.

> **Sobre el segundo camino de seed (BibTeX): RECONOCIDO pero DIFERIDO.** El producto reconoce
> desde los ADR [0007](0007-openalex-backbone.md)/[0018](0018-source-agnostico-calidad.md) que
> **BibTeX es una `Source` secundaria legítima**: el investigador con acceso institucional
> exporta un `.bib` desde la biblioteca de su universidad (con cobertura tras paywall que
> OpenAlex no ve). `BibtexSource.load(path) -> Corpus` **ya existe y funciona en el núcleo**
> (`src/bib2graph/sources/bibtex.py:BibtexSource.load`), pero **ningún subcomando del CLI lo
> cablea** (es función de librería, no camino de producto). Cablear `b2g seed --from-bib` es un
> trabajo legítimo, pero el PO lo **difiere a un issue futuro propio** (ver "Diferido"): **NO se
> construye ni se planifica en este ADR**, y su ejemplo `examples/bibtex/` también queda diferido.

El PO ya fijó las decisiones de datos (corpus real curado y reducido, congelado en parquet/CSV)
y de contrato (`equation.yaml` cargable por `b2g seed --spec`), y la **separación de
responsabilidades**: el **parquet es corpus curado** (rehidratación de estado, comando aparte
`restore`); el **`.bib` es semilla** (camino de `seed`, **diferido**). Este ADR baja las
decisiones del corte 9a, resuelve el hueco de diseño (cómo entra el corpus congelado sin red) y
fija el schema declarativo.

## Decisión

Se fija **la capa declarativa de la ecuación** y un **comando nuevo de rehidratación**, y se
registran acá. El segundo camino de seed (BibTeX) y la convención `examples/` quedan
encuadrados pero **diferidos / pendientes de 9b** (ver "Estado / fasing"):

1. **`equation.yaml` = contrato declarativo cargable (9a ✅).** Un subcomando-modo
   `b2g seed --spec equation.yaml` que carga la ecuación de búsqueda (query + parámetros) desde
   un YAML, **análogo a `b2g networks --spec redes.yaml`** del Hito 9. Es el artefacto
   versionable de "qué se busca" de una investigación.

2. **`b2g seed` tiene EXACTAMENTE DOS MODOS (9a ✅), mutuamente excluyentes:**
   - **`--equation '<texto>'`** — ecuación cruda en la línea de comandos (+ flags
     `--max-results`/`--exclude`/`--native`).
   - **`--spec equation.yaml`** — la misma siembra OpenAlex, parametrizada por el YAML.

   Ambos modos siembran contra OpenAlex y transicionan a `SEEDED`. **`seed` no tiene un modo
   `--from-corpus`** (la rehidratación de parquet es `restore`, abajo) **ni un modo `--from-bib`**
   (diferido).

3. **Comando NUEVO de rehidratación de corpus curado (9a ✅), NO un modo de `seed`:**
   `b2g restore --from-corpus <parquet>` (inverso de `snapshot`) carga un corpus **ya
   curado/sellado** (parquet, p. ej. el del ejemplo) en el `library.duckdb` del workspace,
   **sin red**. Es restaurar estado, no sembrar — por eso vive aparte de `seed`. El AS-BUILT
   fijó que `restore` transiciona el `CycleState` a **`FILTERED`** (ver sub-decisión
   "Reproducción sin red").

4. **Convención `examples/` = corpus de ejemplo commiteado (9b pendiente)**, como **excepción
   explícita** al gitignore de datos de usuario. Un corpus real curado y reducido (~100–150
   filas, con `decision` marcada) se congela como parquet bajo `examples/valoraciones/` y se
   versiona en git para servir de **caso real reproducible sin red** (gate #33 → #34). Se
   materializa en el **Ciclo 9b** (todavía no construido).

Y se **resuelve el hueco de diseño** de cómo el corpus congelado entra a un workspace sin red
(ver sub-decisión "Reproducción sin red").

### Estado / fasing (9a hecho · 9b hecho · Ciclo 10 hecho)

> **Actualizado 2026-06-17:** las dos piezas que 9a había dejado *diferidas* (`seed --from-bib`,
> `examples/bibtex/`) se **construyeron en el Ciclo 10**, junto con el **filtro de año real**. El
> §Diferido de más abajo es **historia superada** por el §AS-BUILT Ciclo 10 al final de este ADR.

| Pieza | Estado |
|-------|--------|
| `EquationSpec` + `load_equation_spec` (`sources/equation.py`) | **9a AS-BUILT ✅** |
| `b2g seed --spec equation.yaml` (2º modo de `seed`) | **9a AS-BUILT ✅** |
| `b2g restore --from-corpus <parquet>` (17º subcomando) | **9a AS-BUILT ✅** |
| `examples/valoraciones/` (corpus + `equation.yaml` + README) + gate R2 | **9b AS-BUILT ✅** |
| `b2g seed --from-bib <archivo.bib>` (3er modo de `seed`) | **Ciclo 10 AS-BUILT ✅** (cierra issue [#50](https://github.com/complexluise/bib2graph/issues/50)) |
| `examples/bibtex/` (ejemplo del camino BibTeX) | **Ciclo 10 AS-BUILT ✅** |
| `min_year`/`max_year` filtran de verdad contra OpenAlex | **Ciclo 10 AS-BUILT ✅** |

### Sub-decisiones resueltas

#### Schema de `equation.yaml` (9a AS-BUILT ✅)

Clave raíz **`equation:`** (objeto, **no** lista — una ecuación por archivo, a diferencia de
`networks:` que es lista). Validación Pydantic v2 con `model_config = ConfigDict(extra="forbid")`
y un loader `load_equation_spec(path)` (`src/bib2graph/sources/equation.py`) con el **mismo
patrón de errores accionables que `load_specs`** (`src/bib2graph/networks/spec.py:load_specs`):
YAML malformado → `ValueError` con el detalle; clave raíz ausente → `ValueError`; campo
desconocido / tipo incorrecto → `ValueError` citando archivo + campo extraído del
`ValidationError`.

```yaml
equation:
  query: '"unequal ecological exchange" OR "ecologically unequal exchange"'
  exclude:                # #30 — negaciones quirúrgicas (opcional, lista)
    - "stock exchange"
  max_results: 150        # #14 — tope de resultados (opcional)
  native: false           # query cruda OpenAlex sin traducción (opcional)
  min_year: 1990          # campo presente, AÚN NO filtra (ver nota)
  max_year: 2024          # campo presente, AÚN NO filtra (ver nota)
```

Modelo (`EquationSpec`, `BaseModel`, `extra="forbid"`):

| Campo | Tipo | Default | Origen |
|-------|------|---------|--------|
| `query` | `str` | requerido (no vacío) | ecuación de búsqueda |
| `exclude` | `list[str]` | `[]` | #30 — `AND NOT title_and_abstract.search:"…"` por término |
| `max_results` | `int \| None` | `None` (→ default del source, 200) | #14 |
| `native` | `bool` | `False` | passthrough crudo a OpenAlex |
| `min_year` / `max_year` | `int \| None` | `None` | **declarados, NO filtran aún** (ver nota) |

Los campos `query`/`exclude`/`max_results`/`native` mapean **1:1** a los argumentos que
`run_seed(...)` ya acepta — la capa declarativa **no agrega capacidad nueva al `Source`**, solo
empaqueta declarativamente lo que el seed ya hace. Esto mantiene una sola fuente de verdad:
`equation.yaml` no es un contrato paralelo, es la forma versionable de los flags existentes
(igual que `redes.yaml` ⇄ `Networks.quick`/flags).

> **`min_year` / `max_year` están en el modelo pero NO filtran hoy (lección 5).** El AS-BUILT de
> 9a acepta ambos campos en `EquationSpec` y los pasa por la firma de `run_seed` (para
> compatibilidad futura), pero **`OpenAlexSource.seed` no los aplica todavía** como filtro de
> año contra OpenAlex. El **filtro de año es trabajo futuro**; documentarlo así (en API.md §2 y
> en el README del ejemplo) para **no prometer una capacidad inexistente**.

#### Reproducción sin red — el hueco de diseño resuelto (comando `restore`, NO un modo de seed) — 9a AS-BUILT ✅

**Camino elegido: opción (ii) — un comando dedicado de rehidratación**, `b2g restore --from-corpus
<parquet>` (inverso de `snapshot`). El PO fijó que el parquet es **corpus curado**, no semilla:
rehidratarlo en `seed` no tiene sentido semántico (ya está curado, ya forrajeado). Por eso vive
en un comando aparte, no como modo de `seed`. Es **baja superficie** (un subcomando fino sobre
`Corpus.from_arrow`):

- **Mecanismo (AS-BUILT, `src/bib2graph/cli/commands/restore.py`):** `restore --from-corpus
  <parquet>` lee el parquet con el schema canónico
  (`pyarrow.parquet.read_table(..., schema=CORPUS_SCHEMA)`, como `CorpusSnapshot.corpus`), lo
  hidrata con `Corpus.from_arrow(table)` (`src/bib2graph/corpus.py:Corpus.from_arrow`), hace
  `existing.merge(incoming)` y lo persiste en el `library.duckdb` del workspace
  (`store.persist(...)`). El corpus parquet **ya trae** `curation_status`/`decision`/`is_seed` ⇒
  rehidratar **preserva el estado curado** (el merge respeta el `curation_status` más reciente,
  D3). **Cero llamadas a `OpenAlexSource`, cero red.**
- **`CycleState` tras `restore` = `FILTERED` (AS-BUILT).** El corpus restaurado ya pasó curación
  (equivalente a haber pasado `filter`/`curate`); `build` y `networks` están disponibles desde
  `FILTERED` (FSM permisiva, ADR [0016](0016-maquina-estados-lazo.md)), así que el lazo sigue
  **sin re-forrajeo ni re-filtrado**. No se fuerza `BUILT` (las redes no se construyeron aún en
  el store destino; sería mentirle al lazo) ni se deja en `SEEDED` (omitiría que los datos ya
  fueron revisados). `restore` **reusa la transición `filter`** de la FSM permisiva
  (`apply_transition(state, "filter", round)`), aceptable desde cualquier estado actual,
  incluido `None` (store vacío nuevo) — donde se sintetiza un `SEEDED` ficticio antes de aplicar
  `filter`. La ronda se **normaliza con `max(loop_round(), 1)`** para evitar persistir ronda 0
  en bases legacy (pre-R3, `round=NULL`) o stores vacíos.
- **Por qué un comando aparte y no un modo de `seed`:** decisión del PO (semántica). `seed` =
  traer material nuevo + empezar/continuar el lazo (lleva a forrajeo); `restore` = recuperar un
  corpus terminado. Mezclarlos confunde el contrato.
- **Por qué no una `Source` nueva (`ParquetSource`/`CsvSource`):** restaurar un export sellado no
  es "sembrar desde una fuente externa"; es el inverso de `snapshot` (`cli/commands/snapshot.py`).
  Conceptualmente `restore` es a `snapshot` lo que `load` es a `dump`. No se justifica una
  `Source`. (Un `CsvSource`/`ParquetSource` de primera clase sigue "futuro, no implementado",
  ADR 0018 / ROADMAP §costuras futuras; se promueve con su propio encuadre si aparece demanda.)
- **Por qué no `curate --from-csv` (#26):** `curate --from-csv`
  (`src/bib2graph/cli/commands/curate.py:run_curate_from_csv`) **no importa el corpus**, solo
  aplica `decision` sobre **papers que ya existen** (cuenta `not_found_count` los huérfanos). Es
  curación, no rehidratación. `restore` trae las filas; `curate` solo marca decisiones sobre
  filas presentes.

**El seed (OpenAlex) vs. la reproducción del ejemplo:**

- **Seed — ecuación → OpenAlex** (con red): `b2g seed --spec equation.yaml` o
  `b2g seed --equation '<texto>'`. Para empezar/continuar el lazo con cobertura OpenAlex.
- **Reproducción del ejemplo (gate #33, sin red, 9b):** NO usa `seed` — no re-siembra
  (re-sembrar cambiaría con el estado vivo de OpenAlex y requeriría red). Corre
  **`b2g restore --from-corpus examples/valoraciones/corpus.parquet`**, que rehidrata el corpus
  congelado **ya curado**. El `equation.yaml` del ejemplo queda junto al corpus como
  **documentación de procedencia** ("este corpus salió de esta ecuación"), no como el comando del
  gate.

El `equation.yaml` del ejemplo es **autodescriptivo** (ecuación + corpus + README) y
**reproducible offline** (el gate carga el corpus con `restore`, no re-busca la query).

#### Convención `examples/` (excepción al gitignore) — 9b pendiente

- **Un ejemplo = una carpeta de propósito ÚNICO.** `examples/<nombre>/` es **autocontenida**
  y demuestra **una** cosa. **No se mezclan tipos de artefacto** dentro de un mismo ejemplo.
  Cada carpeta lleva su **README** que declara qué demuestra y con qué comando se corre.
- **El ejemplo de este ciclo es solo `examples/valoraciones/`** — el **caso real reproducible
  del gate #33**: corpus curado y congelado (`corpus.parquet`, ~100–150 filas con `decision`
  marcada) + `equation.yaml` (procedencia) + `README.md` (+ script de regeneración documentado).
  Se corre con `b2g restore --from-corpus`. **No** contiene `.bib`. Se construye en **9b**
  (próximo ciclo, todavía no).
- **`examples/bibtex/` queda DIFERIDO** (acompaña al camino `seed --from-bib`, también diferido).
  No se crea en este ADR.
- **Formato de datos:** **parquet/CSV** para corpus congelado; **NUNCA `.duckdb`** (biblioteca
  viva, estado mutable no determinista bit-a-bit; el parquet es export sellado y diff-friendly,
  ADR 0006/0009/0017).
- **Excepción al `.gitignore` (en 9b):** se agrega `!examples/` (y las negaciones necesarias para
  que los parquet/CSV bajo `examples/` no sean atrapados por reglas como `snapshots/*.parquet`).
  El resto de la política de datos de usuario (`*.duckdb`, `prueba/`, `redes/`) **no cambia**:
  `examples/` es la **única** excepción, deliberadamente curada y reducida.

## Consecuencias

- (+) **Ecuación versionable (9a):** `equation.yaml` hace la búsqueda un artefacto de primera
  clase, completando la simetría declarativa con `redes.yaml` (Hito 9). Un investigador versiona
  "qué busca" y "qué redes calcula" como dos YAML junto a su workspace.
- (+) **Rehidratación offline (9a):** `b2g restore --from-corpus` rehidrata un corpus curado
  **sin red**, transiciona a `FILTERED` y deja correr `build`/`networks` sin re-forrajeo. Cierra
  el drift "rehidratar no tenía comando" y separa limpiamente `restore` (estado terminado) de
  `seed` (material nuevo).
- (+) **#33 desbloqueable (9b):** con el ejemplo congelado en el árbol (`examples/valoraciones/`),
  existirá un caso real reproducible **sin red** por CLI (`restore --from-corpus` → `build` →
  `networks`/`clusters`; la `decision` ya viene en el parquet), que sirve de gate para #34.
- (+) **Camino a `1.0.0`:** el "caso real validado" que `VERSIONING.md`/PRD §10 exigen para el
  congelamiento se materializa en 9b (no una promesa).
- (+) **Mínima superficie nueva:** `restore` es plumbing fino sobre `Corpus.from_arrow`; la capa
  declarativa reusa el patrón `load_specs` (loader + Pydantic + errores accionables). No se
  inventa `Store`/`Source`.
- (+) **Separación semántica limpia:** `seed` = traer material (ecuación/spec) → forrajeo;
  `restore` = recuperar corpus curado. El contrato de cada comando dice una cosa.
- (+) **Reproducibilidad bit-a-bit:** el ejemplo se **rehidrata** (no se re-busca), así que su
  `corpus_hash` es estable (R2: hash order-independent, sin timestamps; ADR 0017) y las
  comunidades de Louvain son deterministas (seeded). Esto **cierra el agujero R2** que la
  Nota 09 dejó abierto sobre estabilidad de la composición de comunidades (se valida en 9b).
- (−) **Dos modos en `b2g seed`** (`--equation`/`--spec`) **+ comando `restore` nuevo:** más
  ramas de validación de uso y un subcomando más (**17º**). Mitigación: el patrón de modos
  mutuamente excluyentes ya existe (`curate`, `--workspace`/`--store`); `restore` es inverso de
  `snapshot`.
- (−) **Datos en git (9b):** se romperá la regla "ningún dato al repo" con una excepción acotada
  (`examples/`). Mitigación: curado, reducido (~100–150 filas), parquet (no `.duckdb`), y una
  sola excepción documentada en `.gitignore`.
- (−) **Distinción sutil para el usuario:** `equation.yaml` describe la búsqueda en red, pero
  el gate no la ejecuta (rehidrata el corpus con `restore`). El README del ejemplo debe explicar
  la procedencia (ecuación → corpus congelado) y un **script de regeneración documentado** (cómo
  se obtuvo el parquet con red, para auditarlo), aunque el gate no lo corra.
- (−) **`--spec` no traduce WoS→OpenAlex** mejor que `--equation`: hereda el passthrough actual
  (ADR 0007). No es regresión; el YAML solo empaqueta los mismos flags. Además, `min_year`/
  `max_year` **no filtran aún** (trabajo futuro): no se promete capacidad inexistente.

## Diferido (reabrible, fuera de este ADR)

> **SUPERADO (2026-06-17):** los tres puntos de abajo fueron **revisados por el PO y construidos en
> el Ciclo 10** (ver §AS-BUILT Ciclo 10 al final). Se conservan como historia del corte 9a.

- **`b2g seed --from-bib <archivo.bib>` — segundo camino de seed (BibTeX).** Cablear el
  `BibtexSource.load` existente al CLI de siembra es trabajo legítimo (cierra el drift "BibTeX
  declarado como `Source` secundaria pero no en el CLI"; el investigador con acceso institucional
  tras paywall tendría un camino de producto). El PO lo **difiere a un issue futuro propio**: no
  se construye ni se planifica acá. **Reabrible** con su propio encuadre cuando se priorice.
- **`examples/bibtex/` — ejemplo del camino BibTeX.** Acompaña a `--from-bib`; también diferido.
- **`min_year`/`max_year` como filtro real contra OpenAlex.** Los campos existen en `EquationSpec`
  pero no filtran (ver nota del schema). Trabajo futuro.

## Bifurcación residual para el PO (9b)

- **¿`examples/valoraciones/` es un workspace completo commiteado (con `workspace.json`) o solo
  el corpus + `equation.yaml` + README?** La recomendación de este ADR es **solo el corpus
  congelado (parquet) + `equation.yaml` + README** (lo mínimo reproducible: el `library.duckdb`
  se materializa al correr `restore --from-corpus` en un workspace temporal del CI/usuario, no se
  commitea — es estado vivo). Si el PO prefiere commitear el workspace entero para que la GUI
  (#34) lo "abra" tal cual, habría que decidir qué del workspace es determinista y versionable
  (el `.duckdb` no lo es). **Se deja la elección al PO** para 9b; el ADR asume la opción mínima
  salvo indicación contraria.

## Decisiones del PO (2026-06-17)

El PO confirmó, vía pregunta directa, el alcance de este ADR (y corrigió un corte de una corrida
previa que había documentado lo contrario):

1. **`restore` es comando propio (construido en 9a).** La rehidratación del parquet curado vive
   en `b2g restore --from-corpus` (inverso de `snapshot`), no en `seed`.
2. **`b2g seed` tiene exactamente 2 modos (construidos en 9a):** `--equation` y `--spec
   equation.yaml`. El modo `--from-corpus` **se removió** de `seed` (la rehidratación es
   `restore`).
3. **`seed --from-bib` se DIFIERE** a un issue futuro propio: no se construye ni se planifica en
   este ADR.
4. **`examples/bibtex/` se DIFIERE** (va con `--from-bib`). El único ejemplo de este ciclo es
   **`examples/valoraciones/`**, que se construye en **9b**.

## AS-BUILT — Ciclo 9b (2026-06-17): convención `examples/` + gate R2 ✅

Cierra lo que 9a había dejado pendiente. El cuerpo histórico de arriba no cambia; esto registra
lo construido. **Gate verde, 571 tests; el verifier pasa.**

- **`examples/valoraciones/` — el caso real reproducible (gate #33).** Carpeta autocontenida de
  propósito único (no mezcla tipos de artefacto):
  - **`corpus.parquet`** (137 filas, 452 KB): reducción **determinista** del corpus real del PO
    (CC0/OpenAlex). Composición: **7 `accepted`, 130 `candidate`, 107 seeds**. (Los 7 `accepted`
    son los únicos de los 44 `accepted` del CSV de curación que existían en el corpus fuente; el
    README lo aclara para que no parezca contradicción.)
  - **`equation.yaml`**: cargable con `EquationSpec`; documenta que `min_year`/`max_year` están
    declarados pero **no filtran aún**.
  - **`README.md`**: receta reproducible (`init` → `restore --from-corpus` → `build` →
    `clusters.csv`), procedencia y limitaciones conocidas.
  - **`build_corpus.py`**: script determinista de procedencia (su fuente es data local del PO,
    `*.bak`/`valoraciones_*` gitignoreados; **no corre en CI**, no toca red).
- **`.gitignore`:** excepción **`!examples/`** (trackea el ejemplo) + regla defensiva
  **`examples/**/*.duckdb`** (un `.duckdb` nunca al repo, ni dentro de `examples/`). El resto de la
  política de datos de usuario (`*.bak`, `valoraciones_*`, `prueba/`, `redes/`) **no cambia**:
  `examples/` es la única excepción, curada y reducida.
- **Gate de reproducibilidad R2** (`tests/unit/test_example_r2_gate.py`, **7 tests**): sobre el
  corpus REAL de 137 filas asserta que el **`corpus_hash` es estable** (`91740646…`) y que la
  **composición de comunidades es estable entre corridas** (Louvain seeded); redes no vacías
  (coupling 132/3897, author_collab 327/729, institution_collab 136/300, keyword 483/5350;
  co-citación vacía omitida graceful porque `cited_by_id` está en blanco). **Cierra el agujero R2
  que la [Nota 09](../Notas/09-sesion-qa-prueba-ecologia-valoraciones.md) dejó abierto** sobre la
  estabilidad de la composición de comunidades.
- **Bifurcación residual del PO resuelta (opción mínima):** `examples/valoraciones/` commitea
  **solo el corpus + `equation.yaml` + README + script**, no un `workspace.json`/`library.duckdb`
  (el store se materializa al correr `restore --from-corpus` en un workspace temporal). Es lo que
  el ADR recomendaba.

Con 9b, **#33 queda cerrado**: existe un caso real reproducible sin red por CLI, que sirve de gate
para la epic GUI #34. (En 9b, `seed --from-bib` y `examples/bibtex/` quedaban **diferidos** —issue #50—;
ver §AS-BUILT Ciclo 10, donde el PO los des-difiere y se construyen.)

## AS-BUILT — Ciclo 10 (2026-06-17): segundo camino de seed (BibTeX) + filtro de año real ✅

El PO revisó el 2026-06-17 los puntos del §Diferido y **decidió construirlos** (revierte la
postergación del corte 9a): `b2g seed` vuelve a tener un camino BibTeX. **Gate verde, 594 tests
(571 base + 23 nuevos).** El cuerpo histórico de 9a/9b no cambia; esto registra lo construido y
supersede el §Diferido.

### Decisiones del PO (2026-06-17, corte Ciclo 10)

1. **Se construye `b2g seed --from-bib <archivo.bib>` (cierra #50).** `seed` vuelve a **TRES modos
   mutuamente excluyentes** (`--equation` / `--spec` / `--from-bib`). El parquet curado sigue siendo
   `restore`, no `seed` (sin cambio respecto a 9a).
2. **El flujo de armar/reproducir un workspace debe ser 100% por CLI, sin escribir código** (principio
   CLI-puro). Materializa en el Ciclo B (rework de `examples/valoraciones/`); en este Ciclo A se
   construye `examples/bibtex/` con receta CLI-pura.
3. **`min_year`/`max_year` deben FILTRAR de verdad** contra OpenAlex (corrige la nota de 9a "declarados,
   no filtran aún").

### Lo construido (AS-BUILT)

- **3er modo `b2g seed --from-bib <archivo.bib>` — siembra BibTeX local, sin red**
  (`cli/commands/seed.py:run_seed_from_bib` + `seed_cmd`). Usa `BibtexSource.load` (`sources/bibtex.py`,
  import perezoso de `bibtexparser`, extra `[bibtex]`), hace merge+persist y transiciona a `SEEDED`
  (o reseed → ronda++ si ya había estado, misma lógica que `run_seed`). Papers con `is_seed=True` /
  `curation_status='candidate'`. Envelope `--json` = `{papers_added, total_papers, round, reseeded}`
  (**sin** `executed_query`/`translation_report`: no aplican a BibTeX).
- **Frontera de errores (fallar fuerte, no en silencio):** `ImportError` de `bibtexparser` →
  **`DependencyError` (exit 3)** —no `NetworkError`, que es para la ruta httpx de OpenAlex—; `.bib`
  inexistente o mal formado → `DataError` (exit 2). Combinar `--from-bib` con **cualquier** flag de
  OpenAlex (`--exclude`/`--max-results`/`--native`/`--email`/`--min-year`/`--max-year`) → `UsageError`
  (exit 1): no se ignoran flags en silencio (AGENTS.md §Manejo de errores).
- **Mutua exclusión a 3 modos:** `sum([equation, spec, from_bib]) != 1` → exit 1 (reusa el patrón
  de 2 modos de 9a).
- **Filtro de año real (`OpenAlexSource._translate` + `.seed`):** `min_year`/`max_year` agregan
  `from_publication_date:<min_year>-01-01` y/o `to_publication_date:<max_year>-12-31` al `filter` de
  OpenAlex (concatenados con coma — AND idiomático de filtros, **no** texto libre dentro de
  `title_and_abstract.search:()`), y se reportan en el `translation_report`. Expuestos como **flags
  `--min-year`/`--max-year` en `--equation`** y como **campos del YAML en `--spec`** (paridad 1:1, igual
  que `--max-results`/`--exclude`). En modo `--native` no se aplican (nativo = sin traducción). Esto
  corrige la nota del §Schema de `equation.yaml` ("declarados pero NO filtran aún"): **ahora filtran.**
- **`examples/bibtex/` (segundo ejemplo de la convención `examples/`):** `sample.bib` (10 entradas,
  variedad deliberada de campos faltantes —sin abstract/keywords/DOI/autores/año, capítulo con
  `booktitle`— para ejercitar el parser defensivo / regresión T1) + `README.md` con receta **100% CLI**
  (`b2g init` → `b2g seed --from-bib examples/bibtex/sample.bib` → `b2g build`). El `.bib` queda
  trackeado por la excepción `!examples/` ya existente (9b); ningún cambio nuevo al `.gitignore`.
- **Tests:** `tests/unit/test_seed_from_bib.py` (23 tests): siembra/persistencia/estado, campos
  faltantes, entrada sin título omitida, exit 3 sin `bibtexparser`, `.bib` inexistente, reseed, mutua
  exclusión de 3 modos, filtro de año verificado con `MockTransport` capturante (afirma sobre el
  parámetro `filter` enviado), filtro vía `--spec`, envelope `--json`, carga del `sample.bib` real.

Con el Ciclo 10, **#50 queda cerrado** y `seed` tiene su segundo camino de datos (BibTeX
institucional tras paywall, ADR 0007/0018). Queda pendiente el **Ciclo B** (rework CLI-puro de
`examples/valoraciones/` + regen del parquet + ajuste del gate R2), que materializa el principio
CLI-puro sobre el ejemplo de valoraciones (ver §AS-BUILT Ciclo B al final).

## AS-BUILT — Ciclo B (2026-06-17): `examples/valoraciones/` rehecho 100% por CLI ✅

Materializa el principio **CLI-puro** del PO (corte Ciclo 10, decisión 2: "el flujo de armar/
reproducir un workspace debe ser 100% por CLI, sin escribir código") sobre el ejemplo de
valoraciones. El cuerpo histórico de 9a/9b/Ciclo 10 **no cambia**; esto registra lo construido y
**actualiza la convención `examples/`** (la procedencia ya no exige un script). **Gate verde, 598
tests por defecto** (+2 `network` fuera del gate; el verifier pasa).

### Decisión del PO que materializa (CLI-puro)

El script de procedencia `build_corpus.py` **se elimina**. El flujo de armar/reproducir el ejemplo
es **100% por CLI**, sin código: `b2g seed --spec equation.yaml` (`max_results: 80`) →
`b2g curate --from-csv curacion.csv` → `b2g enrich --max-citing 25` → `b2g snapshot`. La procedencia
de un ejemplo deja de ser un *script* y pasa a ser la **receta CLI documentada en el README** +
los artefactos declarativos congelados.

### Convención `examples/` ACTUALIZADA (procedencia = receta CLI, no script)

La regla de 9b/§2.1 que listaba un **"script de procedencia (`build_corpus.py`)"** como artefacto
requerido **queda superada**. Una carpeta de ejemplo de corpus contiene:

- **`corpus.parquet`** — corpus curado y congelado (schema `CORPUS_SCHEMA`; parquet, NUNCA `.duckdb`).
- **`equation.yaml`** — parámetros de búsqueda (procedencia de la ecuación, cargable con `EquationSpec`).
- **`curacion.csv`** — **artefacto congelado nuevo (B1):** las decisiones de curación versionadas
  que `b2g curate --from-csv` consume → **receta determinista** de curación (aplicar este CSV al
  corpus sembrado produce el mismo estado de curación, independiente de cuándo se corra).
- **`README.md`** — la **receta CLI** (armado con red + reproducción offline) que es la procedencia.

**No** hay script de regeneración. La procedencia es la receta CLI + `equation.yaml` + `curacion.csv`.

### Lo construido (AS-BUILT)

- **`examples/valoraciones/` regenerado 100% por CLI.** Corpus = **80 filas** (70 `candidate` +
  10 `accepted`), parquet 168 KB. Secuencia: `seed --spec equation.yaml` (`max_results 80`) →
  `curate --from-csv curacion.csv` (10 `accepted`, los de mayor `references_id`) →
  `enrich --max-citing 25` (pobla `cited_by_id` en los 10 `accepted`) → `snapshot`.
- **`build_corpus.py` ELIMINADO** (principio CLI-puro).
- **`curacion.csv` congelado (B1)** — receta determinista de curación.
- **Co-citación PRESENTE (B3)** aunque rala (2 nodos / 1 arista, `weight=9` real); las otras 4 redes
  sustanciales: coupling 50/157, author_collab 191/454, institution_collab 99/164,
  keyword_cooccurrence 287/3907.
- **Gate R2 ajustado** (`tests/unit/test_example_r2_gate.py`): piso `n>=50` (antes 100); nuevo
  `test_cocitacion_con_datos` afirma **5 redes** (la co-citación ya no se omite graceful);
  estabilidad de `corpus_hash`/comunidades Louvain intacta.
- **README reescrito** a recetas `b2g` (armado con red + reproducción offline), sin referencia a script.

Este Ciclo B **supersede** el AS-BUILT 9b en lo que respecta a la composición del corpus (137 →
80 filas), la co-citación (vacía → presente) y la procedencia (script → receta CLI).
