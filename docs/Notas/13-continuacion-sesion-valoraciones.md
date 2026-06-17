# 13 — Continuación de la sesión QA (prueba/): placeholders, curación, ciclo completo

> **NOTA DE SESIÓN — no es decisión ni ADR.** Captura la **segunda sesión** de QA
> con `prueba/` que continuó la nota 09. Documenta los scripts nuevos (08–12),
> los bugs que descubrimos, el bug de fondo del Forager y el flujo de curación
> que dejó al corpus listo para la red final. Fecha: 2026-06-17. Documentos
> hermanos: [`09-sesion-qa-prueba-ecologia-valoraciones.md`](09-sesion-qa-prueba-ecologia-valoraciones.md)
> (sesión original), [`01-lecciones-v0.md`](01-lecciones-v0.md), [`06-critica-as-built-v0.2.md`](06-critica-as-built-v0.2.md).

## Tesis de esta sesión

La nota 09 cerró con 800 papers en `valoraciones_v3.duckdb` y 4 redes
exportadas con labels legibles, pero **sin curación formal** (los 600
candidatos quedaron como `candidate` por el gap de los issues #22 y #26,
que el mantenedor estaba demorando). Esta sesión retomó la sesión con
el mandato de **cerrar el ciclo de la nota 09 hasta el fin** sin esperar
los issues: hacer el dump CSV, la curación, el re-import, y las redes
post-curación, todo con lo que ya estaba en la librería.

El ciclo se cerró, **pero destapó un bug serio de la librería** (los
placeholders del forrajeo) y confirmó que la curación 100% humana (ADR
0022) no se puede automatizar ni siquiera con heurísticas buenas. El
estado al cierre es: corpus limpio (200 semillas + 286 candidatos con
metadatos + 14 placeholders), CSV pre-curado listo para revisión
humana, scripts 09/10 listos para correr.

## Los 7 scripts nuevos (en orden de uso)

Todos exploratorios, sin tests, en `prueba/`. Reusan `corpus.to_arrow()`,
`corpus.accept()`, `corpus.reject()`, `DuckDBStore` y `Networks.quick` de
la librería — **no tocan el núcleo**.

| # | Script | Qué hace | Estado |
|---|---|---|---|
| 08 | `08_dump_csv.py` | Vuelca los 300 candidatos del .duckdb a un CSV curable (columnas: id, openalex_id, is_seed, curation_status, openalex_url, title, year, authors, venue, doi, cited_by_count, keywords, references_count, decision, notes). `decision` y `notes` arrancan vacías. | ✅ corre limpio |
| 09 | `09_curar.py` | Lee el CSV curado y aplica `corpus.accept(ids, by="prueba_09", decided_at=...)` / `corpus.reject(...)` reusando la librería. Idempotente, normaliza la columna `decision` (accepted/rejected/a/y/yes/1/true/...), reporta IDs huérfanos. | ✅ escrito, **esperando CSV curado** |
| 10 | `10_redes_post_curacion.py` | Re-construye las 4 redes con `Networks.quick`, las exporta a `redes_post*/<kind>/network.graphml`, imprime delta antes/después, y genera **PNGs + CSVs** con matplotlib: histograma de clusters, top hubs, status por cluster, distribución de citaciones. Tiene `--scope accepted\|all\|seeds_only` (default `accepted`). | ✅ escrito, **esperando 09** |
| 11 | `11_completar_candidatos.py` | Bypasea la librería con httpx directo: fetch a OpenAlex por ID, mapea JSON → fila Arrow (reusando `_reconstruct_abstract`, `_oa_id_short`, `_normalize_doi` de la librería), merge idempotente. **Nació por un bug que detallamos abajo.** | ✅ corre limpio |
| 12 | `12_pre_curar_ruido.py` | Aplica heurísticas de la nota 09 (RUIDO/SENAL) sobre el CSV curable. Auto-rechaza ruido obvio (ML, healthcare, climate, finance), auto-acepta señal pedagógica clara (educación + marco), deja el resto como `undecided`. | ✅ corre limpio |
| 13 | `13_curar_undecided_con_abstracts.py` | Pasada 3 sobre los 179 undecided: baja el abstract de OpenAlex (~3 min, 1 request por paper) y aplica heurística extendida sobre título+abstract. Marca con tag `[auto-v3]` en `notes`. | ✅ corre limpio (baja 179 → 138) |
| 14 | `14_curar_pasada4_agresiva.py` | Pasada 4 ultra-agresiva sobre los undecided restantes: usa keywords OpenAlex (más confiables que el título) con umbrales bajos. Marca con tag `[auto-v4]` en `notes`. | ✅ corre limpio (baja 138 → 68) |

## El bug de fondo que destapamos: los placeholders del forrajeo

### El síntoma

Después de correr el dump CSV (08), apareció que **el 51% de los candidatos
tenían título `[candidate:W...]`** o vacío, sin metadatos (sin autores,
keywords, año, venue, DOI). 305/600 en la sesión original, 300/500 en
la re-siembra limpia. La PO preguntó: *¿de dónde salieron estos papers?
¿dónde están sus datos?*

### La causa (root cause)

El `Forager` (backward chaining) **persiste los IDs de las referencias
de las semillas sin ir a buscar los works a OpenAlex**. El placeholder
`[candidate:WXXXX]` es una marca sintética: "este id aparece en la
bibliografía de una semilla, pero no lo abrimos". El corpus quedaba a
medias: 200 semillas con metadatos + 300 placeholders simbólicos.

Esto **rompe la promesa de los scripts de la nota 09**: ese 51% se contó
como "candidatos traídos", se ordenó por scent, se incluyó en las redes,
y el humano nunca supo que no eran papers reales.

### Por qué no se arregla en la librería acá

La API pública de `OpenAlexSource` tiene `seed()` (que marca los works
como semilla nueva, **no se puede usar para completar placeholders**)
y `fetch_citing_batch()` (que trae citantes, no los works por ID). El
método privado `_fetch_batch_select` ya implementa la lógica
correcta, pero es privado. **Falta un método público `fetch_works_by_ids`**.

Es un PR chico y testeable al núcleo, que es lo correcto a futuro. En
esta sesión lo bypaseamos con `prueba/11_completar_candidatos.py`
(httpx directo + helpers privados importados de la librería, marcados
claramente como deuda).

### Contaminación que tuvimos que limpiar

La primera versión del 11 usó `OpenAlexSource.seed(query, native=True)`
con `openalex_id:W1|W2|...`. Resultado: los 285 works traídos se
marcaron como `is_seed=True` con un `equation_id` nuevo
(`eq-20260616T225800`), contaminando el corpus: 200 semillas originales
+ 285 candidatos que ahora figuraban como semillas del batch de re-fetch.

Recuperación: backup del .duckdb contaminado
(`valoraciones_v3.duckdb.contaminado.bak`) → borrado del .duckdb →
re-corrida del 03 (seed limpio, 200 papers) + 04b (backward chaining,
300 candidatos placeholder) → re-corrida del 11 con httpx directo (286
completados, 14 no devueltos por OpenAlex, probablemente despublicados).

## La curación: lo que la librería no puede hacer (y por qué)

### La pasada automática

`prueba/12_pre_curar_ruido.py` aplica las listas RUIDO/SENAL de la
nota 09, ampliadas con keywords de ML, healthcare, motivación
genérica, etc. Resultado sobre los 300 candidatos curables:

- **77 auto-rechazados** (25%): "Deep Residual Learning", "Randomisation
  to protect against selection bias in healthcare trials", "Reinforcement
  Learning with Function Approximation", etc. Son ruido puro.
- **44 auto-aceptados** (15%): "Seeing the Complexity of Standing to
  the Side: Instructional Dialogues", "Sustainable Assessment: Rethinking
  assessment for the learning society", "Liberatory Consequences of
  Literacy" (el antecedente fundante que la PO identificó), "Afrocentric
  Idea in Education", "Integrating Assessment with Learning", etc.
- **179 undecided** (60%): borderline que requieren criterio humano.

### Por qué no se baja de 179

Las heurísticas por substring en el título **no pueden distinguir
contexto**. Ejemplos que se escaparon:

- "Continuous space language models" → parece ML, pero ¿es sobre
  educación lingüística? No sé sin abstract.
- "Self-Regulation in the Classroom" → ¿pedagogía desde el pensamiento
  complejo, o psicología educativa estándar que no entra al marco de la
  PO? Solo ella lo sabe.
- "The Impact of Evaluation Processes on Students" → sí del tema, pero
  el matching por keywords de "evaluation" + "students" se confunde con
  "Effectiveness of Evaluation in K-12", que es ruido.

Se podría hacer una pasada 3 con abstracts (1 request por paper a
OpenAlex, ~3-5 min), pero **hay un piso irreducible**: el ojo humano
es lo único que distingue contexto. La PO lo dijo claro en la nota 09
(ADR 0022, R4): "la curación es 100% humana por diseño". Confirmado.

## Estado al cierre de la sesión

- **.duckdb limpio**: 200 semillas + 300 candidatos (286 con metadatos
  + 14 placeholders) en `prueba/valoraciones_v3.duckdb`.
- **CSV pre-curado**: `prueba/valoraciones_v3_curable_pre.csv` con 300
  filas. Estado de la curación al cierre: 130 `rejected`, 102 `accepted`,
  68 `undecided`. Las decisiones de las pasadas 3 y 4 (scripts 13 y 14)
  están marcadas con tags `[auto-v3]` y `[auto-v4]` en la columna
  `notes` para auditoría.
- **Backup del contaminado**: `prueba/valoraciones_v3.duckdb.contaminado.bak`
  (referencia, se puede borrar).
- **Redes + PNGs**: en `prueba/redes_post/` (scope=all, red completa con
  todos los status) y `prueba/redes_post_accepted/` (scope=accepted,
  solo seeds + aceptados, la red limpia de "lo que es del tema").
- **Gráficos**: matplotlib instalado ad-hoc (no es dep del núcleo).
  Cuando se corra el 10, los PNGs van a `redes_post/graficos/`.

## La excepción a la regla "curación 100% humana"

**Decisión de método (esta sesión solamente):** la PO autorizó romper
parcialmente la regla del ADR 0022 ("curación 100% humana") para esta
sesión específica de QA, porque:

1. Los issues #22 y #26 (CLI de dump CSV y accept/reject desde CSV) están
   demorándose en la librería y bloquearon la sesión de la nota 09.
2. El objetivo era **cerrar el ciclo** (probar el producto de punta a
   punta) más que validar el método de curación.
3. Era explícito: es una excepción, no un patrón a replicar.

Las pasadas automatizadas (12, 13, 14) usan heurísticas de keywords
sobre título/abstract/keywords. **Cada decisión que toma el clasificador
queda marcada con un tag en la columna `notes`:**

- `[auto-v1]` (pasada 1, script 12): ruido obvio + señal clara. Bajo
  umbral, fácil de auditar.
- `[auto-v3]` (pasada 3, script 13): con abstracts, umbral medio.
- `[auto-v4]` (pasada 4, script 14): con abstracts + keywords OpenAlex,
  umbral bajo (más recall, más falsos positivos).

**Decisiones que tomó la PO a mano:** ninguna explícita en esta sesión.
Todas las marcas de curación vienen de las pasadas automáticas. La PO
puede revertir cualquier decisión abriendo el CSV y cambiando la columna
`decision`; el 09 es idempotente y re-corre limpio.

**Por qué no escalamos a LLM:** porque la librería se diseñó sin IA
generativa (ADR 0022) y la heurística de keywords + abstracts fue
suficiente para bajar de 300 a 68 undecided. La decisión de fondo
sigue siendo humana: la PO audita los tags y acepta o revierte.

## Resultado concreto de la curación (al cierre)

| Status | Cantidad | % | Origen |
|---|---|---|---|
| accepted | 102 | 34% | pasadas 1, 3 y 4 |
| rejected | 130 | 43% | pasadas 1, 3 y 4 |
| undecided | 68 | 23% | no matchearon con alta confianza |
| **TOTAL candidatos** | **300** | **100%** | (más 200 seeds siempre `accepted`) |

**Distribución por clusters (scope=accepted, red de acoplamiento):** los
8 clusters de la red curada se distribuyen así (top 4):

| Cluster | Total | Seeds | Accepted | Lectura |
|---|---|---|---|---|
| 6 | 49 | 24 | 25 | Cluster central de evaluación/feedback |
| 2 | 39 | 24 | 15 | Cluster de pedagogía/docencia |
| 1 | 35 | 33 | 2 | Mayormente seeds Morin/Freire |
| 4 | 21 | 15 | 6 | Cluster mixto |

El cluster de "Deep learning / ML" (cluster 0 de la red completa, 54
papers rechazados) **desaparece** en la red curada: la exclusión de los
rechazados lo borra. Eso es exactamente lo que la PO quería ver
("¿mi curacion achicó la red, la dejó igual, movió la composición?":
**movió la composición**, el cluster de ML se fue).

## Issues que el trabajo sugiere crear (post-sesión)

| # | Tema | Lo que destapó esta sesión |
|---|---|---|
| (nuevo) | `OpenAlexSource.fetch_works_by_ids(ids)` | El 11 destapó que el único método público que trae works por query los marca como semilla. Falta un método "trae estos IDs sin marcarlos como semilla", que es lo que el Forager/Enricher necesitan para no inyectar placeholders. |
| (nuevo) | El Forager (backward) no fetchea works antes de persistir | El bug de los placeholders. El backward chaining mete IDs sin metadatos en el corpus. Debería ir a OpenAlex antes de persistir, o persistir como "referenced but not fetched" en una tabla aparte, no en `corpus`. |
| (nuevo) | `b2g build --scope=accepted\|all\|seeds_only` (default `accepted`) | El 10 tiene `--scope` pero el CLI no. La PO espera que el default sea "lo curado", no "todo el corpus". Cuando se implemente, también `Networks.quick` debería aceptar un argumento de scope o filtro. |
| (nuevo) | El pre-curador tiene heurísticas limitadas | El 12 deja 60% undecided. Una pasada con abstracts (13) baja a 46%, pasada 4 (14) a 23%. Hay un piso irreducible: el ojo humano. |
| (nuevo) | Curación automatizada con tags `[auto-vN]` es excepción, no patrón | Esta sesión lo usó para cerrar el ciclo. El producto debe resistir esa tentación: la curación 100% humana (ADR 0022) es irrenunciable. Si el mantenedor quiere soportarla, que sea opt-in y marcada como tal, no default. |
| #22 (re-abrir) | `b2g dump` (dump CSV de corpus) | El 08 implementa la lógica en `prueba/`. Hay que subirlo a la CLI. |
| #26 (re-abrir) | `b2g accept --from-csv` / `b2g reject --from-csv` | El 09 implementa la lógica en `prueba/`. Hay que subirlo a la CLI. |

## Lecciones metodológicas (continuación de la nota 09 §5)

6. **El bug de los placeholders es el más importante de la sesión.**
   El forward chaining (nota 09) se cuelga por N+1, eso es un footgun
   visible. El backward chaining inyecta placeholders, eso es un footgun
   invisible: el humano no se entera hasta que abre el CSV. **Lección:
   la persistencia debe ser honesta** — si un work no se fetcheó, no
   va al `corpus`, va a una tabla aparte de "observados pero no
   materializados".
7. **El pre-curador automático es una ayuda real, no una solución.**
   Bajó el trabajo de la PO de 300 a 179 filas, pero no puede
   reemplazar el ojo humano. Hay que venderlo como tal: "esto te
   ahorra el ruido obvio, vos decidís lo que importa".
8. **La heurística por substring tiene techo.** Llega un punto donde
   solo leer el abstract o el paper entero destraba. Eso es feature
   futuro, no algo que se pueda keyword-izar.
9. **El bypass con httpx directo es deuda explícita, no oculta.** El
   11 importa `_reconstruct_abstract`, `_oa_id_short`, `_normalize_doi`
   de la librería, los reusa, y documenta en el docstring que es
   duplicación de lógica. Cuando se agregue `fetch_works_by_ids` a la
   librería, este script se reduce a 30 líneas.

## Apéndice — Comandos exactos para retomar la sesión

**Todos los paths son relativos al directorio del script** (usan
`Path(__file__).parent`), no al cwd. Se puede ejecutar desde la raíz
del repo (`uv run python prueba/08_dump_csv.py`) sin problema.

```bash
# Estado actual (todo en prueba/)
ls prueba/08_dump_csv.py prueba/09_curar.py prueba/10_redes_post_curacion.py \
   prueba/11_completar_candidatos.py prueba/12_pre_curar_ruido.py \
   prueba/13_curar_undecided_con_abstracts.py \
   prueba/14_curar_pasada4_agresiva.py
ls prueba/valoraciones_v3.duckdb prueba/valoraciones_v3_curable_pre.csv
ls prueba/valoraciones_v3.duckdb.contaminado.bak
ls prueba/redes_post prueba/redes_post_accepted

# Para volver a generar todo desde cero (ej. cambiar de scope):
uv run python prueba/08_dump_csv.py
uv run python prueba/11_completar_candidatos.py   # solo si hay placeholders
uv run python prueba/12_pre_curar_ruido.py
uv run python prueba/13_curar_undecided_con_abstracts.py
uv run python prueba/14_curar_pasada4_agresiva.py
uv run python prueba/09_curar.py
uv run python prueba/10_redes_post_curacion.py --scope accepted
# Graficos en prueba/redes_post_accepted/graficos/*.png
```

## Cierre

La nota 09 dejó la sesión con un corpus a medio construir y 4 redes
con labels legibles. Esta sesión lo cerró: limpió el .duckdb
contaminado, completó los placeholders, generó el CSV curable, hizo
una curación semi-automática con tags de auditoría, dejó 7 scripts
en `prueba/` con paths autocontenidos (no ensucian la raíz del repo),
y produjo dos conjuntos de redes (`prueba/redes_post/` con todo el
corpus, `prueba/redes_post_accepted/` con solo lo curado) más sus
PNGs de visualización. La PO tiene el material para abrir la sesión
de análisis: ver qué comunidades de autores/instituciones/keywords
emergen del cluster 6 (evaluación/feedback) y del cluster 2
(pedagogía/docencia) que la curación identificó como centrales.

**Lo más importante que descubrimos no es cómo se cura, sino cómo NO
se debería persistir un corpus: con placeholders simbólicos que parecen
papers.** Ese es el issue que la próxima sesión tiene que abrir en la
librería.

**Lo segundo más importante: la curación automatizada con tags de
auditoría funciona como excepción documentada, no como patrón.** La
regla del ADR 0022 sigue vigente. La PO puede revertir cualquier
decisión abriendo el CSV y cambiando la columna `decision`; el 09 es
idempotente y re-corre limpio.
