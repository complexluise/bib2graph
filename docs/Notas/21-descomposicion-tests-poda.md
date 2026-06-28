# 21 — Descomposición de información de la suite de tests (hacia una poda)

> ⚠️ **NOTA DE ANÁLISIS — no es decisión ni ADR.** Diagnóstico de la suite de tests del 2026-06-28,
> motivado por que la suite cruzó las **~1238 pruebas recolectadas** (68 archivos). El objetivo es
> entender *qué información aporta cada test* para decidir **qué se puede quitar sin perder cobertura
> real**. El análisis se hizo leyendo los 68 archivos por clúster temático (6 lecturas paralelas).
> Las eliminaciones concretas listadas son **candidatas**: cada una se confirma borrando el test,
> corriendo el gate y verificando que `--cov` no pierde líneas/ramas únicas (ver §6). Documentos
> hermanos: [`06-critica-as-built-v0.2.md`](06-critica-as-built-v0.2.md), [`19-qa-cli-superficie-limites.md`](19-qa-cli-superficie-limites.md).

## 0. El dato que dispara la nota

La suite pasó de **645 tests verdes (v0.3, 2026-06-16)** a **~1238 recolectados hoy** —casi el doble—
mientras la superficie pública se **consolidó** (10 verbos CLI, ADR 0038/0037). Cuando los tests
crecen al doble y la superficie *baja*, la diferencia no es cobertura nueva: es **acumulación**. La
mayor parte de ese exceso tiene una causa estructural identificable (§4), no es ruido aleatorio.

## 1. El marco: descomposición parcial de información aplicada a tests

Tomo prestado el lente de la *partial information decomposition* (único / redundante / sinérgico) y le
agrego un cuarto eje propio del software, **tensión**. Cada test, frente al conjunto, cae en:

- **ÚNICO** — es el único que cubre un invariante. Si lo borrás, una rama/contrato queda sin red.
  **No se toca.** Es la mayoría sana de la suite (`dedup`, `decorate`, `preprocessors`, `projectors`,
  `analyzer`, `compute_id`, `r1`/`r4` puros, contratos de backend).
- **REDUNDANTE** — verifica *el mismo invariante* que otro(s), en la misma o distinta capa. El segundo
  ejemplar no agrega información; agrega costo de runtime y de mantenimiento. **Candidato a poda o
  fusión.**
- **SINÉRGICO** — *parece* duplicado pero solo tiene valor **en conjunto**: un par aislamiento↔integración,
  o una guarda negativa que sola no dice nada. **No se toca aunque tiente** — borrar la mitad rompe la
  garantía sin que ningún test se ponga rojo (peor que un duplicado: un falso ahorro).
- **EN TENSIÓN** — acoplado a implementación frágil (strings de copy, internals privados, versión de
  Click, IDs de OpenAlex, paths de import para `patch`). Pasa hoy pero **pelea contra cada refactor**.
  No es candidato a *borrar* sino a **refactorizar** (extraer constantes, testear contrato no forma);
  algunos —las "lápidas"— sí a borrar.

La poda barata vive en **REDUNDANTE**. La poda peligrosa (la que hay que *evitar*) es confundir
**SINÉRGICO** con redundante. La deuda que conviene saldar de paso es **TENSIÓN**.

## 1.bis Criterio del PO (adoptado 2026-06-28)

El PO fijó la política que gobierna la poda. **No es DRY ciego.**

1. **Defensa en profundidad SELECTIVA.** Un invariante = un test *en general*, **pero se conserva la
   redundancia en capas** (unit + backend + e2e) donde el invariante es el corazón del producto:
   **`corpus_hash`/reproducibilidad y la FSM del ciclo**. → De §2.4 solo se eliminan las copias
   *byte-idénticas*; la cobertura en capas de lo crítico **se mantiene**. La reproducibilidad es la
   tesis de un tool de investigación: ahí la redundancia es seguro, no desperdicio.
2. **Tests de forma → conservar consolidados.** Neutralidad-AST, reloj inyectado, pureza del núcleo se
   **mantienen** como guardia de arquitectura (ADR 0028, R2), pero se **fusionan en 1 parametrizado** y se
   hacen menos frágiles (§2.7). Las "lápidas" (asserts de ausencia de símbolos viejos) son lo de menor valor.
3. **Deprecación: la migración cerró.** ADR 0038 consolidó los verbos → retirar los `*_corre_y_delega`,
   dejar **solo** el test del aviso de deprecación (§2.1).
4. **Mocks de red → adelgazar + promover.** Recortar los asserts de forma-de-query duplicados y mover la
   cobertura real a más tests `@network` fuera del gate (§4.5).

## 2. Redundante — el inventario de poda (lo accionable)

Agrupado por patrón, con cita `archivo::test`. Estimación gruesa: **~70–100 tests** podables/fusionables
(~6–8% de la suite) sin perder un solo invariante.

### 2.1 Migración noun-verb (ADR 0038) duplicada: el viejo verbo + el nuevo conviven
La epic de huérfanos #37 ya consolidó los verbos. Los tests que protegían la transición ahora **duplican
al verbo canónico**:
- `test_deprecation_aliases.py` — los `test_*_corre_y_delega` (accept/reject/filter/restore/networks)
  re-ejercen funcionalidad ya cubierta por `test_cli.py` y `test_cli_read.py`. **Lo único con valor
  propio es el aviso de deprecación** (stderr + `warnings[]`). El resto (~15-20 de ~40) es poda directa
  una vez aceptada la deprecación.
- Transición `restore → FILTERED` triplicada: `test_restore.py::test_run_restore_transiciona_a_filtered`
  + `test_snapshot_grp.py::test_snapshot_restore_transiciona_a_filtered` (+ su variante `_desde_seeded`,
  que no siembra estado previo → idéntica).
- `run_snapshot` con `out_dir` por tres lados: `test_snapshot_grp.py::test_snapshot_create_crea_archivos`
  ≈ `::test_run_snapshot_importable_desde_cli_snapshot` ≈
  `test_workspace_remanentes.py::test_snapshot_sin_outdir_usa_workspace_snapshots_dir`.

### 2.2 El mismo invariante repetido por cada superficie (helper puro + N copias)
Cuando hay un helper puro bien testeado, repetir su semántica en cada comando que lo usa es redundante;
basta **un test de "presencia + forma" por superficie**:
- **`maturity`**: `TestComputeMaturity` ya cubre `curated`/`saturated` a fondo; `TestBuildMaturity`,
  `TestSnapshotMaturity`, `TestReadTopMaturity` repiten casi literal `curated_false/true`,`saturated_false`
  (~6 tests podables).
- **`next_best_action`**: el FSM puro (`test_status_10.py::TestNextBestAction`, 6 casos) y luego
  `TestRunStatusCamposAditivos::test_next_best_action_*` (4 casos) re-mapean lo mismo vía `run_status`.
  Dejar 1 smoke de cableado.

### 2.3 "stdout = una sola línea JSON" (#151) y `schema=="1"` re-aseverados
Hay un guard parametrizado canónico (`test_cli_json_option.py::test_anti_regresion_stdout_max_una_linea_con_json`,
16 comandos) y además el helper `_assert_one_json_line` ya valida "1 línea" en *cada* test de read. Los
tests dedicados son duplicado del helper:
- `test_cli_read.py::test_cli_read_{list,show,stats}_stdout_una_linea_json`,
  `test_cli_read_top.py::test_cli_read_top_stdout_una_linea_json` **y su gemelo `_cocitacion_vacia`**
  (mismo assert, el "vacía" no cambia nada).
- `test_build_absorber_networks.py::test_json_stdout_una_sola_linea` ≈ `::test_json_warnings_en_envelope_no_en_stdout`.
- `schema=="1"`: los 5 `test_schema_1_intacto` de `test_deprecation_aliases.py` ya los cubre
  `_assert_one_json_stdout` en cada test de su clase.

### 2.4 `corpus_hash`/reproducibilidad verificado en 5 capas
El invariante de identidad es el más sobre-cubierto del repo (señal de que es el más importante — sano
tener red unitaria + e2e, pero no 5 copias):
- contrato unitario: `test_r2_reproducibility.py`; a nivel backend: `test_backends.py::test_corpus_hash_estable`
  / `::test_corpus_hash_order_independent`; e2e sobre parquet real: `test_example_r2_gate.py::test_corpus_hash_estable_entre_cargas`
  ≈ `test_idempotencia_pipeline_bitabit.py::test_corpus_hash_identico_en_dos_cargas_arrow` (**idénticos** → uno sobra).
- "Louvain reproducible" duplicado: `test_r2…::test_networks_build_louvain_reproducible` ≈
  `test_example_r2_gate…::test_comunidades_estables_entre_corridas`.
- Recomendación: **conservar 1 unitario (r2) + 1 e2e (gate del corpus real); fusionar el resto.**

### 2.5 La familia `enrich` (la mayor concentración de deuda)
Co-citación probada en memoria, vía store, y absorbida en chain/build — con los mismos invariantes
repetidos 3-4 veces:
- Idempotencia triplicada (`test_enrichers_8b::test_enrich_cited_by_idempotente` el más débil → eliminable;
  lo subsume `test_enrich_cocitacion_integrado::…_idempotente_corpus_hash…`).
- Tope `max_citing` ×4, "sin seeds → no-op" ×3, "no pierde papers" ×3, conteo de redes 4-vs-5 en ≥4 sitios,
  contrato de claves de `run_enrich` ×3.
- **Estrategia**: concentrar co-citación en `test_enrich_cocitacion_integrado.py` (store) +
  `test_enrich_absorb.py` (chain/build), y recortar de `test_enrichers_8b.py` lo ya cubierto end-to-end
  (~6-8 tests).

### 2.6 Contrato `BibtexSource.load` repartido en 3 archivos
`test_sources.py::test_bibtex_load_{is_seed_true,curation_status_candidate,campos_faltantes_none,sin_keyerror}`
son **subconjunto estricto** de `test_bibtex_source_contrato.py::test_campos_…_persisten` (que ya asevera
`is_seed`, `curation_status` y todos los campos). + mutua-exclusión de modos `seed` duplicada literal entre
`test_seed_from_bib.py` y `test_equation_spec.py`.

### 2.7 Tests de neutralidad-AST copiados textualmente
El mismo `ast.walk` buscando `click`/`fastapi`/`sys.exit`/`print` está copiado en
`test_service.py`, `test_service_reads.py`, `test_api.py`, `test_cli_read.py` y `test_cli_read_top.py`.
**Consolidar en un único test parametrizado sobre todos los módulos de `service/`** (~4 tests → 1).

### 2.8 Misceláneos cross-archivo
`NetworkKind` como fuente única: `test_r1_constants` vs `test_r5_robustness` (mismo contrato) ·
paridad build≡networks doble (`test_build_absorber_networks::test_paridad_artefactos…` ⊂ `…_multiples_redes`) ·
"networks no toca el FSM" en `test_build_absorber_networks` y `test_networkspec_yaml` · scope-token CLI
duplicado dentro de `test_build_absorber_networks` · `status` cache fresca vs sin-cache (mismo assert final).

## 3. Sinérgico — lo que NO hay que tocar aunque parezca duplicado

Estos pares/tríos **se sostienen mutuamente**; borrar la mitad deja un agujero que ningún rojo delata:
- **Aislamiento ↔ integración**: `Forager.preview` con MagicMock + `run_chain(preview=True)` con DuckDB;
  `predict_build_preview` puro + `TestNoDivergenciaPreviewVsBuild` (ata la predicción al `Networks.build`
  real); co-citación en memoria (`8b`) + persistencia store (`cocitacion_integrado`, lo dice su docstring).
- **Paridad de backends** (`test_external_ids.py`, `test_backends.py`): los bloques memory/duckdb *parecen*
  espejo, pero el contrato del ADR 0036/0013 **es** "ambos backends, mismo comportamiento" — la clase
  `Paridad` no existe sin los dos lados.
- **Guardas negativas**: `test_clusters.py::test_cruce_por_col_id_no_openalex_id` (detecta cruce por la
  columna equivocada) solo vale junto a los `test_cluster_table_*_count`.
- **Capstone + gates**: `test_oneshot_readiness.py` (e2e, prueba que el ciclo *fluye*) + `r1-r5` (prueban
  *por qué* cada paso es correcto). El e2e sin gates no localiza la causa de un fallo; los gates sin e2e
  no garantizan la integración. **Los `r1-r5` NO se solapan entre sí** (r1 tipos, r2 identidad, r3 FSM,
  r4 scent, r5 robustez) — son cinco capas distintas, todas únicas.
- **Paridad seed+resolve** (`test_parity_resolve_paths.py`): no prueba comportamiento, prueba
  *no-divergencia* entre dos caminos — su valor es ser la red antes de retirar el verbo. (Pero ver §4.5:
  está en tensión con su propio destino.)

## 4. Tensión — las causas sistémicas (refactor, no solo borrado)

Las redundancias de §2 no son casuales: salen de **cinco patrones** que conviene atacar en la raíz.

1. **Aserciones por substring sobre copy en español.** `"deprecad" in stderr`, `"50" in reason`,
   `"ignora" in stderr`, `"0 papers" in warning`, y los `fix_command == "b2g build --thesaurus <archivo>"`
   literales repetidos en ~6 sitios de `test_status_10.py`. Cualquier reescritura del mensaje los rompe
   sin que cambie el comportamiento. → **comparar contra constantes exportadas, no literales.**
2. **Acoplamiento a la separación stdout/stderr de Click 8.4.1.** ~6 tests de
   `test_build_absorber_networks.py` dependen de ese comportamiento de versión; un bump de Click los
   rompe en bloque.
3. **`patch()` sobre rutas de import internas.** `test_r3_commands_domain.py`,
   `test_cli.py::test_exit_code_*`, `test_r5_robustness.py` parchean
   `bib2graph.networks.facade.Networks.quick`, `…sources.openalex.OpenAlexSource`, `_projector_for_kind`.
   Mover un import interno rompe el test sin cambiar comportamiento observable. `test_oneshot_readiness.py`
   es el caso extremo: exige que `chain.py`/`resolve.py` importen `OpenAlexSource` *dentro* de la función
   y replica la firma del constructor — frágil y caro (el test más lento del repo).
4. **"Lápidas" (tests que aseveran ausencia).** `test_foraging.py::test_build_forward_candidate_row_eliminado`,
   `TestExplainCandidateRetirado`, `::test_modulo_explain_no_existe`. Verifican que algo *ya no existe*:
   valor decreciente, fricción permanente con cualquier refactor. Candidatos a borrar tras un ciclo.
5. **Mocks que dan falsa confianza.** Toda la familia de exclusiones de OpenAlex aseverando sobre la query
   *mockeada* — el propio `test_openalex_exclude_integration.py` documenta que el mock **no detecta** el
   bug real (campo repetido → 0 resultados) y solo el test `@network` (fuera del gate) protege de verdad.
   La query-forma está además duplicada unit+integración, acoplada al string exacto de `_translate`.

Contradicciones puntuales a resolver:
- **§4.5** `test_parity_resolve_paths.py` y los `test_resolve.py::*_resolve_envelope` importan `run_resolve`
  de un verbo **en retirada** (#164/#165). El test que *guarda* la retirada se romperá *con* la retirada.
- `test_example_r2_gate.py` (`assert exists`, falla duro) vs `test_idempotencia_pipeline_bitabit.py`
  (`pytest.skip`) ante **el mismo** parquet faltante → comportamiento contradictorio; y ambos con asserts
  de tamaño (`50 ≤ n ≤ 200`) que rompen si se regenera el corpus aunque el código esté bien.
- `_seed_store` definido dos veces en `test_clusters.py`; docstrings que aún mencionan `--store` (eliminado
  #75) en `test_smoke.py`/`test_r5`.

## 5. Síntesis: ¿de dónde salieron los ~600 tests de más?

No de cobertura nueva. De **tres acumuladores**:
- **migraciones que dejaron el test viejo + el nuevo** (noun-verb ADR 0038, retiro de verbos #164/#165),
- **el reflejo de "un test por superficie"** cuando el invariante ya vive en un helper puro (maturity,
  json-una-línea, schema, next_best_action, neutralidad-AST),
- **el invariante estrella sobre-cubierto** (`corpus_hash` en 5 capas, co-citación ×4).

La poda sana es **fusionar/parametrizar**, no recortar a ciegas: cada patrón de §2 colapsa N tests en 1
parametrizado conservando todos los casos. Y el ahorro real de mantenimiento no está en el conteo sino en
**§4**: extraer constantes y dejar de testear forma de implementación rinde más que borrar 80 tests.

## 6. Cómo ejecutar la poda con seguridad (DoD por candidato)

Por cada test marcado en §2, antes de borrar:
1. `uv run pytest --cov=bib2graph --cov-report=term-missing` **antes** (línea base de líneas/ramas).
2. Borrar/fusionar el candidato.
3. Re-correr: **si la cobertura de líneas/ramas no baja**, el test era redundante → eliminar. **Si baja**,
   era único (o sinérgico) → revertir, era un falso positivo del análisis.
4. Gate completo verde: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`.

Orden sugerido (mayor ahorro / menor riesgo primero): §2.7 (neutralidad-AST, 4→1) · §2.3 (json/schema) ·
§2.2 (maturity/next_best_action) · §2.5 (familia enrich) · §2.1 (noun-verb, tras confirmar deprecación) ·
§2.4 y §2.6 al final (tocan invariantes sensibles, confirmar caso por caso). **§3 no se toca. §4 es
trabajo aparte (refactor), no poda.**

---

*Nota generada a partir de una lectura por clústeres de los 68 archivos de `tests/`. Las citas
`archivo::test` son verificables; los conteos son estimaciones para priorizar, no cifras exactas.*
