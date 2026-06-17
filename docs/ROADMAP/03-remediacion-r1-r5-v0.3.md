> ← Volver al [índice del ROADMAP](README.md)

# TANDA DE REMEDIACIÓN (Hitos R1–R5) — cerrar la brecha AS-BUILT ↔ TARGET

> **Va ANTES de los Hitos 7–11.** El red-team de la [Nota 06](../Notas/06-critica-as-built-v0.2.md)
> y el modelo nuevo bloqueado por el PO (ADR [0022](../decisiones/0022-producto-sin-ia-generativa.md)/
> [0023](../decisiones/0023-capa-constants-modelos-schema.md) + enmiendas a 0008/0011/0016/0017/0020/0021)
> dejaron una brecha entre lo construido (v0.2) y el diseño objetivo (`ARCHITECTURE.md`, bloques
> `TARGET`). Esta tanda la cierra, **secuenciada por dependencia** (no por gravedad): nada de arriba
> se construye sobre cimientos que aún no existen.
>
> **Disciplina de la tanda:** es **refactor con la suite verde como red de seguridad** (214 tests al
> entrar). Cada hito R **preserva el comportamiento observable** salvo donde el ADR enmendado dice lo
> contrario (p. ej. R2 **cambia** el `corpus_hash` a propósito; R4 **elimina** `explain_candidate`).
> El núcleo sigue importando **sin `duckdb`**. El contrato `--json` externo del CLI **no driftea**
> (salvo el campo nuevo de curación en `status`, R3). Los tests viejos que codifican el AS-BUILT roto
> (p. ej. un test que espera `corpus_hash` distinto por timestamps) se **actualizan** al TARGET.

---

## Hito R1 — Cimientos: capa `constants` / `schemas` (con `ProvenanceEvent`) única · ✅ TERMINADO (2026-06-16)

> Primero porque **todo lo demás depende de esto** (ADR
> [0023](../decisiones/0023-capa-constants-modelos-schema.md)): `constants/schemas` es la capa más baja
> del grafo de dependencias (`constants/schemas` → núcleo puro → costuras → CLI). Cierra CONSTANTS y
> MODELS de la [Nota 06](../Notas/06-critica-as-built-v0.2.md). Es un refactor transversal **sin cambio
> de comportamiento observable** (la base segura sobre la que se apoyan R2–R4).

**Alcance**

- **`bib2graph/constants.py`** (capa base): `class Col(StrEnum)` con **todos** los nombres de columna
  del schema (§1.1 de API.md), `class CurationStatus(StrEnum)` (`candidate`/`accepted`/`rejected`) y
  `class NetworkKind(StrEnum)` (los 5 tipos de red). Reemplazar los **~62 string-literals** de columna
  (14 archivos) y los literales de `curation_status` (11 archivos) por referencias a estos enums.
- **`ProvenanceEvent(BaseModel)` definido en `src/bib2graph/schemas.py`** (consolidado ahí, no en un
  `models.py` separado) — fuente única del evento de procedencia:
  `{action, equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`, con
  construcción y **parseo que falla ruidoso** ante JSON corrupto (cierra el `_parse_provenance` que
  hoy hace `except … : return []` en silencio).
- **`schemas.py` como única definición de fila:** `PaperRow` (Pydantic) autoritativa; `CORPUS_SCHEMA`
  (Arrow) **derivado/verificado** de ella (no duplicado a mano en paralelo). Test que falla si
  driftean.
- **`Manifest.model_copy(update=...)`** en los 5+ sitios que hoy lo reconstruyen campo a campo.
- **Se mantiene** "`Paper`/`Author`/`Keyword`/`Institution` = vistas derivadas, no tipos" (ADR 0023):
  **no** se crean clases-entidad.

**Historias:** ninguna nueva (deuda de base); **habilita** R2 (excluir `ProvenanceEvent`/timestamps
del hash limpiamente) y blinda A4/C4 (procedencia honesta).

**Criterios de aceptación (DoD)**

- Un **typo de columna falla en import/type-check** (mypy), no en runtime tardío.
- No quedan string-literals de columna ni de `curation_status` fuera de `constants.py` (verificable
  con un grep en CI/local; el patrón ya existe para los exit codes en `cli/_errors.py`).
- `PaperRow` ⇄ `CORPUS_SCHEMA` provienen de **una** fuente: un test verifica que no driftean.
- `ProvenanceEvent` **falla ruidoso** ante JSON corrupto (no `return []`).
- La suite del Hito 1–6 pasa **sin cambios de expectativa** (refactor sin cambio de comportamiento).

**Tests (TDD — los justos)**

- `PaperRow` ⇄ `CORPUS_SCHEMA`: un test de equivalencia de campos/tipos (falla si se desincronizan).
- `ProvenanceEvent`: round-trip + **falla explícita** ante JSON corrupto (reemplaza el swallow).
- *No testear* cada enum miembro por separado (trivial); sí un test de que el schema usa `Col`.

**Recomendaciones para el `coder`** (`archivo:símbolo`):

- Crear `src/bib2graph/constants.py` (`Col`, `CurationStatus`, `NetworkKind`) y definir
  `ProvenanceEvent` en `src/bib2graph/schemas.py` (consolidado ahí, no en un `models.py` separado).
  Reemplazar literales en `schemas.py`,
  `backends/memory.py`, `backends/duckdb.py`, `filters/prisma.py`, `cli/commands/validate.py` y los
  demás (Nota 06 CONSTANTS: 11 archivos con literales de estado, 14 con literales de columna).
- `backends/memory.py:78-95` (`_parse_provenance`): el `except (json.JSONDecodeError, TypeError):
  return []` debe **fallar** (o registrar y relanzar), no tragarse el corrupto.
- `schemas.py`: derivar/verificar `CORPUS_SCHEMA` desde `PaperRow` (hoy 22 campos duplicados a mano).
- `Manifest`: `model_copy(update=...)` en `sources/openalex.py:462`, `foraging/forager.py:259`,
  `filters/prisma.py:198`, `preprocessors/preprocessor.py:58,107`, `corpus.py:462`.

**Se vuelve posible:** una base de vocabulario que el type-checker protege; el refactor de R2–R4 se
apoya en `Col`/`CurationStatus`/`ProvenanceEvent` en vez de literales.

---

## Hito R2 — Reproducibilidad / identidad: content-hash vs procedencia + Louvain seeded · ✅ TERMINADO (2026-06-16)

> Segundo porque **necesita `ProvenanceEvent` (R1)** para separar identidad de procedencia con
> limpieza. Cierra la RAÍZ 2 de la [Nota 06](../Notas/06-critica-as-built-v0.2.md) y la enmienda
> 2026-06-15 del ADR [0017](../decisiones/0017-reproducibilidad-historia-snapshot.md). Es el hito que
> **cambia el `corpus_hash` a propósito** (breaking interno): dos corridas que aceptan los mismos ids
> pasan a dar el **mismo** hash.
>
> ✅ **As-built (2026-06-16):** `compute_corpus_hash` excluye `provenance` (sigue incluyendo
> `curation_status`); el reloj se inyecta desde las **tres** fronteras de curación (`accept`,
> `reject` y **`filter`** vía `apply_filters(decided_at=…)`); el núcleo conserva un **fallback
> `datetime.now(UTC)`** documentado para uso como **librería** sin `decided_at` (no afecta la
> identidad, que excluye provenance — ver ADR 0017 enmienda punto 3); Louvain seeded con
> `random_state` derivado del content-hash (`_louvain_seed_from_hash`). **247 tests** verdes
> (13 nuevos en `test_r2_reproducibility.py`), mypy strict / ruff limpios. **`resolution`
> diferido a Hito 9** (NetworkSpec declarativo) — ver DoD abajo y ADR 0017 punto 4.

**Alcance**

- **Identidad (contenido) ≠ procedencia (auditoría):** `compute_corpus_hash` se computa **solo sobre
  contenido bibliográfico**, **excluyendo** `provenance` (`ProvenanceEvent`/timestamps). La
  procedencia es un **log append-only fuera de la identidad** (auditar, no identificar).
- **Reloj en la frontera, no en el núcleo:** `accept`/`reject`/`filter` **reciben el instante**
  (`decided_at`) como parámetro inyectado desde el CLI. El núcleo conserva un **fallback
  `datetime.now(UTC)`** documentado para uso como librería sin `decided_at` (no afecta la identidad,
  que excluye provenance) — ADR 0017 enmendado, punto 3.
- **Louvain seeded:** `detect_communities(method="louvain")` corre con `random_state` **derivado del
  content-hash** → comunidades **reproducibles** entre corridas. (`resolution` **diferido a Hito 9**,
  NetworkSpec — ver DoD.)

**Historias:** cierra **E1** de verdad (el snapshot **sí** se reproduce bit a bit) y endurece **A4**
(procedencia auditable separada de la identidad).

**Criterios de aceptación (DoD)**

- ✅ **Dos corridas que aceptan los mismos ids producen el mismo `corpus_hash`** (antes diferían por
  los timestamps) → el snapshot es reproducible bit a bit (cumple el ADR 0017 y `facade.py:6`).
  `test_corpus_hash_estable_ante_timestamps_distintos`.
- ✅ `accept`/`reject`/`filter` inyectan `decided_at` desde la **frontera** (CLI). **Reconciliado:** el
  núcleo conserva un **fallback `datetime.now(UTC)`** cuando se usa como **librería** sin `decided_at`
  (ergonomía de `corpus.accept(ids)`); el fallback **no** rompe el DoD porque el `decided_at` no entra
  al hash (identidad ≠ procedencia, ADR 0017 punto 3). El contrato honesto: "el reloj se inyecta en la
  frontera; el núcleo solo usa `datetime.now()` como fallback de librería, fuera de la identidad". El
  path real de la CLI nunca toca el fallback.
- ✅ `detect_communities(..., method="louvain", random_state=…)` da **la misma partición** entre
  corridas para el mismo grafo (seed derivado del content-hash, `_louvain_seed_from_hash`).
  ⚠️ **`resolution` DIFERIDO a Hito 9** (NetworkSpec): el punto 4 del ADR 0017 / el alcance original
  pedían exponer `resolution`; se difiere al hito donde `NetworkSpec` gana parámetros por algoritmo
  vía YAML. R2 entrega la pata reproducible (el `random_state` seeded), que es la que importa para
  la identidad; `resolution` queda en el default de `python-louvain`. Diferimiento aditivo.
- ✅ La suite pasa (247 verdes); no había test viejo que esperara hashes distintos por timestamps.

**Tests (TDD — los justos)**

- **Hash estable bajo curación:** aceptar los mismos ids en dos corridas → mismo `corpus_hash`
  (regresión directa de RAÍZ 2).
- Reloj inyectado: `accept(ids, decided_at=…)` registra el instante recibido; el núcleo no toca el
  reloj de sistema (un test que pasa un instante fijo y verifica el evento).
- Louvain determinista: misma partición en dos corridas sobre un grafo sintético.

**As-built (`archivo:símbolo`):**

- ✅ `backends/memory.py` (`compute_corpus_hash`): **excluye** la columna `provenance` del hash
  (sigue incluyendo `curation_status`); order-independent intacto.
- ✅ `backends/memory.py` (`_apply_curation_to_rows`, `apply_curation`) y `corpus.py`
  (`accept`/`reject` con `decided_at: datetime | None`): reciben `decided_at` desde la frontera;
  **fallback `datetime.now(UTC)`** cuando es `None` (uso como librería).
- ✅ `filters/prisma.py` (`apply_filter`/`apply_filters` con `decided_at`) + `cli/commands/filter.py`
  (inyecta un único `datetime.now(UTC)` para todos los pasos PRISMA de la invocación).
- ✅ `cli/commands/accept.py`, `reject.py` inyectan `datetime.now(UTC)`.
- ✅ `networks/facade.py` (`_louvain_seed_from_hash`, threadeado por `_build_artifact`) +
  `networks/analyzer.py` (`detect_communities(..., random_state=…)`): Louvain seeded con el
  content-hash. ⚠️ `resolution` **NO** expuesto — **diferido a Hito 9** (ver DoD).

**Se volvió posible:** la promesa central del producto —**reproducir bit a bit** un snapshot— deja de
ser falsa. El forrajeo/curación/análisis son deterministas de punta a punta.

---

## Hito R3 — Ciclo: FSM cíclico de dominio (`cycle.py`) + `reseed`/ronda + curación transversal · ✅ TERMINADO (2026-06-16)

> Tercero porque el ciclo se apoya en los cimientos (R1) y conviene que la identidad ya sea estable
> (R2) antes de modelar `reseed`/acumulación. Cierra la RAÍZ 1 (la parte del lazo) de la
> [Nota 06](../Notas/06-critica-as-built-v0.2.md) y la enmienda 2026-06-15 de los ADR
> [0016](../decisiones/0016-maquina-estados-lazo.md)/[0021](../decisiones/0021-cli-agente-native-contrato.md).
>
> ✅ **As-built (2026-06-16):** `src/bib2graph/cycle.py` es el **dominio puro** (sin DuckDB):
> `CycleState` (`SEEDED/FORAGED/FILTERED/BUILT/MONITORED`), `apply_transition(state, action, round)
> → (state, round)`, `available_transitions(state)`, `CURATION_ACTIONS`. El enum de estados **salió**
> del backend; `backends/duckdb.py` solo persiste (columna `round` en `loop_state_log` por migración
> liviana; `loop_round()` / `set_loop_state(state, *, cycle_round=...)`) y mantiene el **alias
> transicional `LoopState = CycleState`** (a retirar pre-1.0). `reseed` es de primera clase
> (loop-back a `SEEDED` + ronda++): lo cablea `seed.py` (estado previo ⇒ re-sembrado, acumula).
> **Fuente única de verdad:** `chain`/`filter`/`build` **derivan** su estado destino de
> `apply_transition` (gap del verifier cerrado; test domain-tied en `test_r3_commands_domain.py`).
> `status` expone `curation_available`/`round` **aditivos** manteniendo `schema="1"`. `MONITORED`
> está en el modelo pero **sin comando que lo dispare** (futuro). **275 tests** verdes (R3 + 9
> domain-tied del fix), mypy strict / ruff limpios. Decisiones de implementación de la IA en
> [`decisiones/registro-ia.md`](../decisiones/registro-ia.md) (Hito R3).
>
> ✅ **Seguimientos de R3 CERRADOS en el cleanup pre-v0.3 (2026-06-16):** (a) el **alias
> `LoopState = CycleState` se RETIRÓ** (el código usa solo `CycleState`); (b) **`MONITORED` ya es
> alcanzable**: el comando **`b2g monitor`** (12° subcomando) lo dispara (forward chaining → merge →
> transición). Ver registro-ia "Cleanup pre-v0.3" y ADR 0016 §Cleanup.

**Alcance**

- **`bib2graph/cycle.py` — FSM cíclico como concepto de dominio puro** (el enum y las reglas de
  transición salen del backend; el backend **solo lo persiste**): estados
  `SEEDED → FORAGED → FILTERED → BUILT → MONITORED`.
- **`reseed` como transición de primera clase** ("la idea muta"): vuelve a `SEEDED`, **incrementa un
  contador de RONDA** y **acumula** sobre lo curado (no es solo "transición permisiva"). Es lo que el
  ADR 0016 prometía y el AS-BUILT no cumplía.
- **`MONITORED`** modela el paso 8 del ciclo (Nota 05 §3). *(El comando que lo dispara puede ser
  futuro; el estado existe en el modelo.)* **✅ Cerrado:** el comando **`b2g monitor`** se construyó en
  el cleanup pre-v0.3 (2026-06-16) — `MONITORED` ya no es solo modelo.
- **Curación TRANSVERSAL:** `accept`/`reject` están disponibles **en cualquier estado**, **no
  transicionan**, pero `b2g status` **debe** mostrarlas como **acción siempre-disponible** (hoy las
  oculta) y exponer el **contador de ronda**. Humanos e IAs ven en el mapa lo único irreductiblemente
  humano.

**Historias:** cierra **A5** de verdad (re-sembrar que acumula con contador de ronda, no una corrida
tirada) y **C4** (la curación aparece en el mapa del lazo); refuerza **E2** (el `status` agente-native
no miente sobre el ciclo).

**Criterios de aceptación (DoD)**

- El modelo de estados + transiciones vive en `cycle.py` (núcleo puro, testeable **sin** DuckDB); el
  `DuckDBBackend` **solo lo persiste** (log append-only, ya existente).
- `reseed` vuelve a `SEEDED`, **incrementa la ronda** y conserva lo curado (un test de acumulación
  entre rondas).
- `b2g status` (humano y `--json`) muestra: estado actual, **transiciones disponibles**, **`accept`/
  `reject` como acción siempre-disponible**, **contador de ronda** y conteos por `curation_status`.
- El campo nuevo del envelope `--json` de `status` (`curation_available`/`round`) es **aditivo** y
  **mantiene `schema="1"`** (decisión del PO 2026-06-16: campos nuevos no rompen a los agentes, no se
  bumpea).

**Tests (TDD — los justos)**

- `cycle.py` puro: secuencia de transiciones válidas + `reseed` (loop-back a `SEEDED`, ronda++),
  **sin** DuckDB.
- Acumulación entre rondas: re-sembrar tras `BUILT` no pierde lo aceptado.
- Contrato `--json` de `status`: incluye `curation_available`/`round`/transiciones (golden/schema);
  no driftea.
- *No testear* el plumbing de Click de `status` (se testea `run_status`).

**Recomendaciones para el `coder`** (`archivo:símbolo`):

- Crear `src/bib2graph/cycle.py` y **mover** el enum `LoopState` (hoy `backends/duckdb.py:67-78`) +
  las reglas de transición al núcleo; el backend persiste, no define el dominio. (Renombrar a
  `CycleState`/`cycle` según prefiera el `coder`; el comando sigue siendo `status`.)
- `cli/commands/status.py:19-34`: agregar `accept`/`reject` como acción siempre-disponible y exponer
  el contador de ronda (hoy `transitions_available` nunca los lista).
- `cli/commands/accept.py:104` / `reject.py`: documentar explícitamente "curación transversal, no
  transiciona" (alineado con `status`).
- Cablear `reseed` (loop-back + ronda) en el flujo de `seed` cuando ya hay estado previo (acumula).

**Se vuelve posible:** el "ciclo no lineal" deja de ser solo prosa: `reseed`/ronda son de primera
clase y la curación —lo irreductiblemente humano— por fin figura en el mapa del lazo.

---

## Hito R4 — Scent bibliométrico vía proyectores + retiro de `explain`/`[llm]`/tensiones · ✅ TERMINADO (2026-06-16)

> **AS-BUILT (2026-06-16):** R4 reescribió `foraging/scent.py` para consumir el primitivo público
> `collect_item_to_papers` de `networks/projectors.py` (el forrajeo **depende del núcleo de
> proyección**, nunca al revés), y **eliminó** `foraging/explain.py`/`explain_candidate` y el extra
> `[llm]` (ADR 0022). **291 tests** verdes, mypy strict / ruff limpios. El **steering arquitectónico
> (2026-06-16)** resolvió tres cuestiones de método: **backward = fuerza de co-citación con el corpus**
> (ratificado), **forward = fuerza de citación directa al corpus** (señal primaria; el AS-BUILT inicial
> midió *acoplamiento puro* —que **degenera a 0** con referencias ralas— y se **corrigió a citación
> directa dentro de R4**) y **centralidad diferida** (no es requisito de cierre; el DoD "y/o" se cumple
> con co-citación + citación-directa). Ver AS-BUILT del ADR
> [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) (fórmulas + recomendación de código
> del forward, **implementada**). **Cierre total:** `compute_forward_scent` calcula
> `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|` (citación directa, emite con
> `direct > 0`); la elimina-IA, el scent-vía-proyectores y el forward robusto **están cerrados**. R4 no
> deja seguimiento abierto.
>
> Cuarto porque el scent-vía-proyectores **consume el núcleo de proyección** (Hito 2, ya construido) y
> conviene tener identidad estable (R2) para que el ranking sea reproducible. Cierra la RAÍZ 1 (la
> parte de IA) de la [Nota 06](../Notas/06-critica-as-built-v0.2.md) y las enmiendas 2026-06-15 de los
> ADR [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md) (scent = proyectores),
> [0022](../decisiones/0022-producto-sin-ia-generativa.md) (el producto no usa IA) y
> [0008](../decisiones/0008-wedge-forrajeo.md) (tensiones retiradas).

**Alcance**

- **El *information scent* pasa de frecuencia de enlace a proyectores:** un candidato rankea por
  cuánto se **acopla / co-cita / es central** respecto del corpus curado (consume `networks/` — el
  núcleo de proyección puro). Sigue siendo **función pura y determinista** (mismo corpus → mismo
  ranking); el forrajeo (costura) **depende del núcleo de proyección**, nunca al revés.
- **Eliminar la rama de IA del producto** (ADR 0022): borrar `foraging/explain.py` y `explain_candidate`
  de la superficie pública; **eliminar el extra `[llm]`** de `pyproject.toml`; quitar el fallback
  semántico/LLM del thesaurus (ADR 0011 enmendado: el thesaurus es curado y determinista, lo que no
  matchea queda fuera).
- **Retirar la "máquina de tensiones"** del alcance (ADR 0008/0022): **no se difiere a v2, se borra**
  del producto y de las "Costuras futuras". El sensemaking es **humano**, asistido por las redes.
- **Arreglar los docstrings de scent** que mienten sobre la dirección (Nota 06, secundarios).

**Historias:** **re-define B3** (ranking por estructura bibliométrica real, no por conteo plano);
**retira B4** (explicación opcional de IA) — deja de ser historia del producto.

**Criterios de aceptación (DoD)**

- `chain` rankea por **estructura bibliométrica** del candidato con el corpus (consume el primitivo
  `collect_item_to_papers` de `networks/`), **determinista** (mismo corpus → mismo orden). El DoD
  listaba "acoplamiento **/** co-citación **/** centralidad" (un **"y/o"**: pide señal estructural de
  red, no las tres). **AS-BUILT R4:** backward = **co-citación** (cuántos corpus-papers co-citan al
  candidato); forward = **citación directa al corpus** (señal primaria robusta) con acoplamiento como
  secundario. **Centralidad diferida** a viz (excede el olfato barato y determinista). Espíritu del
  DoD cumplido. *(El forward as-built fue acoplamiento puro y se corrigió a citación directa dentro de
  R4: `compute_forward_scent` emite con `direct > 0`.)*
- **No existe** `explain_candidate`, `foraging/explain.py` ni el extra `[llm]` (verificable: import
  falla, el extra no está en `pyproject.toml`). El thesaurus no tiene fallback LLM.
- El **sesgo de confirmación** (efecto Mateo) del scent queda documentado: el scent **prioriza**; la
  exhaustividad la sostienen los filtros PRISMA y el conteo de exclusiones, no el scent.
- La suite pasa; los tests de `explain_candidate`/`[llm]` se **retiran** (la capacidad ya no existe).

**Tests (TDD — los justos)**

- Ranking por scent-vía-proyectores: candidatos con acoplamiento/centralidad conocidos salen en el
  **orden** esperado, sobre un corpus sintético con resultado calculado a mano.
- Determinismo: mismo corpus → mismo ranking (regresión).
- Que `import` de `explain_candidate` **falle** (la superficie ya no lo expone).
- *No testear* la calidad bibliométrica del clustering en sí (ya cubierto en Hito 2).

**Recomendaciones para el `coder`** (`archivo:símbolo`):

- `foraging/scent.py:27-125`: reescribir `compute_backward/forward_scent` para consumir los
  **proyectores** (`networks/projectors.py`) en vez de `Counter`/`sum` sobre `references_id`/
  `cited_by_id`. El forrajeo depende del núcleo de proyección (no al revés).
- **Borrar** `foraging/explain.py` (`explain_candidate`, `NotImplementedError` en `:47`); quitarlo de
  la superficie pública (`bib2graph.foraging`).
- `pyproject.toml`: **eliminar el extra `[llm]`** (vacío). Quitar cualquier gate `[llm]` en
  `preprocessors/` (thesaurus sin fallback semántico).
- `foraging/scent.py:11,80` vs `:114`: corregir los docstrings que invierten la dirección.

**Se vuelve posible:** el scent **es** la bibliometría que la Nota 05 promete (no un conteo), y el
producto queda **honesto: sin IA generativa** (ADR 0022). Un solo sentido de "AI-in-the-loop": el
desarrollo es asistido por IA; el producto no.

---

## Hito R5 — Robustez / escala: bulk-load, UTF-8 en la frontera, footguns de la Nota 06 · ✅ TERMINADO (2026-06-16)

> Último de la tanda: no cambia el modelo conceptual, **endurece** lo construido. Cierra la RAÍZ 3 y
> el catálogo de secundarios de la [Nota 06](../Notas/06-critica-as-built-v0.2.md). Independiente de
> R1–R4 en su mayoría; se ubica al final para no mezclar refactor de modelo con hardening.
>
> **AS-BUILT (2026-06-16):** R5 reemplazó el loop `add_paper`/`_clone` por **bulk-load**
> (`Corpus.from_arrow` + helper `corpus._rows_with_ids`) en los cuatro loaders (seed/load OpenAlex,
> BibTeX, Forager), forzó **UTF-8 en la frontera** (`cli/__init__.py:main` → `_force_utf8()` antes de
> que Click lea nada) y agregó **retry/backoff** ante 429/5xx en `fetch_citing`
> (`_fetch_all_with_retry`, exp backoff, 3 intentos). Cerró los **8 footguns** del catálogo de
> secundarios. **319 tests** verdes (`test_r5_robustness.py` + ajustes), mypy strict / ruff
> check+format limpios. **Verifier: APRUEBA** (reservas cerradas).
>
> **DoD reconciliado honestamente — el batching-por-OR quedó DIFERIDO.** El DoD pedía que
> `fetch_citing` *"batchee y reintente 429/5xx"*; el AS-BUILT entrega **solo retry/backoff** (la pata
> de correctitud/robustez: un rate-limit ya no pierde papers). El **batching por OR** (agrupar varios
> `cites:` en una sola query para matar el N+1) **NO se implementó** — el spec lo pedía "si es
> factible" y queda como **mejora de PERFORMANCE futura** (el N+1 persiste, pero ahora es resiliente).
> Distinguir: el retry SÍ se hizo; el batching NO. (Ver registro-ia R5.3 y "Decisiones de seguimiento".)
> **➡ Encuadrado por el arquitecto (cleanup pre-v0.3, 2026-06-16): el batching-por-OR pasa al Hito 8**
> (`Enricher` de co-citación), que es donde se hace el **2º nivel de fetch** a escala — ver Hito 8 §Alcance.
> **✅ RESUELTO también para el `Forager` (#21, 2026-06-16):** el forward del Forager (`b2g chain`/
> `monitor`) reusa `fetch_citing_batch` (cap por semilla + preview sin red, scope `is_seed`) — el N+1
> del forrajeo desaparece. Ver [04 · Lo que viene](04-lo-que-viene.md) §Hito 8 y ADR 0020 AS-BUILT #21.
>
> **Cierre de la tanda:** con R5 la **remediación R1–R5 queda COMPLETA** — la brecha AS-BUILT↔TARGET
> del red-team (Nota 06: RAÍZ 1, 2, 3 + secundarios) está cerrada. Lo que sigue son los Hitos 7–11
> (capacidades nuevas hacia v1.0), no remediación.

**Alcance**

- **Fin del O(n²) en carga:** los loaders (seed/load OpenAlex, BibTeX, forager) usan el bulk
  `Corpus.from_arrow` en vez del loop `add_paper`/`_clone` que re-upserta la tabla entera por fila.
- **UTF-8 en la frontera CLI:** forzar `sys.stdout`/`stderr` a UTF-8 (o `encoding="utf-8"` explícito)
  en el entry point, para que el envelope `--json` (`ensure_ascii=False`) y `--help` no corrompan
  acentos en Windows (cp1252). **Arreglo de mayor impacto/menor costo**; restaura el contrato
  agente-native (ADR 0010/0021) en Windows.
- **Batching + retry/backoff en forward chaining:** `fetch_citing` deja de hacer N+1 requests
  seriales sin reintento ante 429/5xx.
- **Footguns de la Nota 06 (catálogo de secundarios):**
  - **rama muerta en `_errors.py`** (manejo de `OSError`: el `if isinstance(..., StoreLockedError)`
    y el `else` hacen lo mismo) → simplificar; y `AttributeError`→"Capacidad no disponible" es
    **engañoso** (un bug real se reporta como dependencia faltante) → distinguir.
  - **auto-creación del store** ante typo en `--store` (`status`/`validate`) → no auto-crear en
    comandos de solo lectura.
  - **`.bib` roto / filtros PRISMA con campo-op desconocido = no-op silencioso** → warning o error
    accionable (no tragar).
  - **param muerto `g`** en `cocitation_quality_report` → quitarlo (anti-patrón que ARCHITECTURE §8
    dice evitar).
  - **`_lib_version` fallback `"0.0.0"`** mete versión falsa en el `Manifest` → fallar o marcar
    `unknown`, no inventar versión.
  - **`except Exception` en `detect_communities`** (`facade.py`) que traga el fallo → no enmascarar.
  - **`_QUICK_KINDS` duplica el `Literal` de `NetworkSpec.kind`** → fuente única (usar `NetworkKind`
    de R1).

**Historias:** ninguna nueva; **endurece** E2 (el contrato agente-native funciona en Windows) y todo
el flujo a escala mediana.

**Criterios de aceptación (DoD)**

- Cargar un corpus mediano no es O(n²) (los loaders usan `from_arrow`); un test/benchmark de no
  regresión razonable.
- En Windows, `b2g ... --json` y `--help` devuelven acentos correctos (UTF-8 forzado) — regresión del
  bug verificado de la Nota 06.
- ~~`fetch_citing` batchea y~~ **reintenta 429/5xx sin perder papers** (sobre cliente mock).
  **AS-BUILT:** la pata de **retry/backoff** se cumple (`_fetch_all_with_retry`, exp backoff, 3
  intentos); el **batching por OR queda DIFERIDO** (mejora de performance — el spec lo pedía "si es
  factible"; el N+1 persiste pero ahora es resiliente al rate-limit, que era la falla de correctitud).
- Cada footgun del catálogo: el comportamiento silencioso pasa a **fallar/avisar accionable** o se
  elimina la rama muerta/param muerto/versión falsa. Sin no-ops silenciosos.

**Tests (TDD — los justos)**

- **UTF-8:** el envelope con un acento se decodifica bien forzando UTF-8 (regresión directa).
- `@handle_errors`: un caso por exit code **incluido `4`** (hoy sin assert) y el `5` real (no la
  rama muerta).
- `.bib` roto / filtro con campo-op desconocido → **warning/raise** (no no-op).
- Retry de `fetch_citing` ante 429/5xx sobre cliente mock (no en tiempo real).
- *No testear* el rate limiter en tiempo real ni el motor DuckDB.

**Recomendaciones para el `coder`** (`archivo:línea`, de la Nota 06):

- Loaders → bulk `Corpus.from_arrow` en vez de `add_paper`/`_clone` (`backends/duckdb.py:319,368`).
- UTF-8 en el entry point del CLI (`cli/_envelope.py:67` usa `ensure_ascii=False` sin forzar stdout).
- `foraging/forager.py:307` → `sources/openalex.py:394-425`: ~~batch +~~ retry/backoff para
  `fetch_citing`. **AS-BUILT:** retry/backoff implementado (`_fetch_all_with_retry`); batch-por-OR diferido.
- `cli/_errors.py:139-147` (rama muerta `OSError`), `:155-159` (`AttributeError` engañoso);
  `corpus.py:46-53` (`_lib_version` fallback `"0.0.0"`); `networks/facade.py:104` (`except Exception`
  en `detect_communities`); `sources/bibtex.py:206,210` (`.bib` silencioso);
  `filters/prisma.py:115` (filtro no-op); `networks/analyzer.py:277` (param muerto `g`);
  `networks/facade.py:39` vs `spec.py:42-48` (`_QUICK_KINDS` duplica `NetworkKind`);
  `backends/duckdb.py:417,423` (SQL por interpolación de strings en `merge` — hoy seguro, frágil).
  **✅ RESUELTO en el cleanup pre-v0.3 (2026-06-16):** el `merge` ya no interpola ids (lee filas,
  ordena en Python por orden de aparición, reinserta; D3 preservado; la alternativa CTE descartada).
- `status`/`validate` auto-crean el store ante typo en `--store` → no auto-crear en solo-lectura.

**Se vuelve posible:** bib2graph corre a escala mediana, el contrato agente-native funciona en
Windows, y desaparecen los no-ops silenciosos que esconden bugs.

---
