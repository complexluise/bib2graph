# 09 — Sesión de QA con `prueba/`: ecología de valoraciones en educación

> ⚠️ **NOTA DE SESIÓN — no es decisión ni ADR.** Captura el uso real del producto v0.3
> como QA / científica explorando un caso concreto. El objetivo es documentar lo que
> los scripts de `prueba/` pusieron en evidencia: bugs de la librería, huecos de UX,
> y patrones de uso que el producto debería absorber como features propios. Fecha:
> 2026-06-16. Documentos hermanos: [`01-lecciones-v0.md`](01-lecciones-v0.md) (postmortem
> de v0), [`06-critica-as-built-v0.2.md`](06-critica-as-built-v0.2.md) (red team del código),
> [`07-frontend-tool-for-thought.md`](07-frontend-tool-for-thought.md) (GUI como tool for thought).

## Tesis de la sesión

Probar el producto **no como test unitario** (eso lo hace `uv run pytest`), sino
como **investigadora que tiene una pregunta y quiere llegar a redes bibliométricas
explotables**. La pregunta fue: *ecología de valoraciones en educación y pedagogía,
poniendo el foco en cómo el pensamiento complejo piensa la evaluación, notas y
calificaciones*. La sesión cubrió el ciclo completo sembrar → forrajear → construir
redes, y todo el trabajo quedó en `prueba/` (scripts exploratorios locales,
gitignoreados — no van al repo). Esta nota documenta lo que aprendimos.

## Lo que se hizo (los 7 scripts en orden)

Todos los scripts son exploratorios, sin tests, sin red salvo cuando se aclara. El
corpus se acumuló en `valoraciones_v3.duckdb` (biblioteca viva, ADR 0009).

| # | Script | Qué prueba | Salida principal |
|---|---|---|---|
| 01 | `01_seed_basico.py` | `OpenAlexSource(max_results=100).seed(...)` | 100 papers con la query amplia "pensamiento complejo" — diagnosticó señal vs. ruido |
| 02 | `02_busq_refinada.py` | Tres variantes de la ecuación, una con AND de marco + (pedagogía OR evaluación) | Conteo y títulos top por variante — mostró que el ruido médico (lupus, inflamación) entra por `sistémico` y `saberes` |
| 03 | `03_busq_v3_quirurgica.py` | Ecuación con anclas precisas (Morin, Freire, transdisciplinariedad) + persistencia | 200 semillas en `valoraciones_v3.duckdb` — base para todo lo que vino después |
| 04 | `04_forrajear.py` | `Forager(direction="both", max_candidates=300)` con 200 semillas | TEOUT a 10+ min — descubrió que el forward chaining es O(♠semillas) y no tiene cap |
| 05 | `05_diagnostico_candidatos.py` | Heurística de señal/ruido sobre los 600 candidatos que persistió el 04 antes de morir | 38% señal pedagógica, 4.5% ruido ML explícito, 57% neutros — fundamentó la necesidad de curación humana |
| 06 | `06_redes_y_grafos.py` | `Networks.quick` + exportación GraphML con `label` inyectado (workaround local del issue #25) | 4 redes en `redes/<kind>/network.graphml` con labels legibles |
| 07 | `07_distribuciones_clusters.py` | Lee los GraphML y los cruza con el corpus para reportar tamaño, densidad, modularidad y composición por cluster | Top hubs por centralidad, histograma de tamaño de cluster, distribución de keywords por cluster |

El orden refleja el **ciclo de la herramienta** (PRD §7, [`05-ciclo-investigacion-humano.md`](05-ciclo-investigacion-humano.md)):
*ecuación → forrajeo → curación → redes → análisis*. Cada script se basó en el anterior
y expuso un problema distinto del producto.

## Hallazgos de la sesión (bugs y huecos detectados)

### B1. `--max-results` no existe en `b2g seed` (issue #14)

**Síntoma:** para explorar con muestras chicas (100 papers), el usuario tiene que
bajar a Python y armar un script. El CLI no acepta un tope de resultados.

**Causa:** `OpenAlexSource.__init__` acepta `max_results: int = 200` (default),
pero el wrapper CLI (`src/bib2graph/cli/commands/seed.py:109-142`) solo expone
`--equation`, `--email`, `--native`, `--json`.

**Por qué importa:** el producto se pensó para **explorar** (PRD §2, ciclo Bates/
Ellis/Kuhlthau), y el CLI es la API para LLM/agentes (ADR 0010). Un tool sin tope
no es composable.

### B2. `b2g chain --direction both` se cuelga con corpus grandes (issue #21)

**Síntoma:** timeout de 10+ minutos al hacer chaining forward con 200 semillas.

**Causa:** `forager.py:296-330` itera sobre TODAS las filas del corpus y llama
`self._source.fetch_citing(oa_id)` por cada una, secuencial, sin rate limit, sin
progreso, sin cap. Con 200 semillas son 200 requests HTTP secuenciales.

**Por qué importa:** el forrajeo es el corazón del ciclo. Si el comando se cuelga,
los usuarios van a sembrar corpus chiquitos (10-20 papers) para evitar el dolor, y
eso contradice la promesa de "biblioteca viva acumulable" (ADR 0009).

**Workaround en sesión:** matar el comando a los 10 min, aprovechar los 600
candidatos que se persistieron antes de morir. La persistencia es idempotente
(`merge`), así que la biblioteca quedó usable.

### B3. Las redes salen del proyector sin label legible (issue #25)

**Síntoma:** el `GraphMLExporter` produce un GraphML donde los nodos se llaman
`oa:005e7c0621bf7fda`, `I185261750`, `0000-0002-5608-5061`. Gephi/Cytoscape/
VOSviewer muestran el `id` crudo. El usuario no puede leer nada sin mapear a mano.

**Causa:** los 5 proyectores (`src/bib2graph/networks/projectors.py:188-353`) no
setean ningún atributo de nodo. `GraphMLExporter` y `CsvExporter` solo copian
lo que haya. Sin `label` en el grafo, las herramientas externas caen al `id`.

**Por qué importa:** el caso de uso principal del producto es **inspeccionar redes
visualmente** para tomar decisiones de curación. Sin labels, la red es inutilizable.

**Workaround en sesión:** `prueba/06_redes_y_grafos.py` inyecta `label` desde
el corpus antes de exportar, función `_label_for_kind` que mapea por `NetworkKind`
(paper → `title (year)`, autor → nombre, institución → nombre, keyword → la keyword).
Local; la librería sigue rota hasta que se arregle el issue #25.

### B4. No hay dump CSV de papers para curación offline (issue #22)

**Síntoma:** con 600 candidatos, la única forma de revisarlos es
`b2g inspect --id <id>`, uno por uno. Eso es inviable.

**Por qué importa:** la curación es **100% humana** por diseño (ADR 0022, R4). El
humano mira **una tabla**, no stdout. Sin CSV, cada investigador arma su propio
script ad-hoc (`prueba/05_diagnostico_candidatos.py` en esta sesión), y el producto
deja de ser reproducible.

### B5. `b2g accept`/`reject` no aceptan CSV (issue #26)

**Síntoma:** relacionado con B4. Aunque tuvieras el dump, no hay forma de reimportar
las marcas de curación en lote. Hoy hay que tipear IDs uno por uno o vía flag.

**Workaround en sesión:** no hubo — los 600 candidatos quedaron sin marcar al
cerrar la sesión. Esto explica la urgencia del issue #26.

### B6. Bug menor en mi propio script `07_distribuciones_clusters.py`

No es un bug de la librería, pero vale documentarlo porque me costó encontrarlo.
Tres iteraciones:

1. **Fórmula de densidad interna mal** (`internal_density` daba > 1.0 para cliques
   completos). Bug: usé `2*m / max_e` cuando `max_e` ya tenía el `/2`. Fórmula
   correcta: `m / max_e`.
2. **Cruce corpus↔nodo del grafo fallaba** porque usé `Col.OPENALEX_ID` (formato
   `W2194775991`) cuando el nodo del grafo tiene el **id canónico** (formato
   `oa:abab47f3...`). Bug: leer la columna equivocada. El cruce correcto es por
   `Col.ID`.
3. **`comms` se construía desde los nodos con `community` attribute**, no desde
   `g.nodes()` directamente. Bug: asumir que `comms` tiene todos los nodos.

Los tres son **lecciones sobre cómo leer el modelo canónico**: el `id` canónico
(D1, ADR 0006) y el `openalex_id` son cosas distintas, y el grafo puede tener
nodos sin el atributo que el caller espera.

## Patrones de uso que el producto debería absorber

Observando el flujo, hay **gests repetidos** que la herramienta podría hacer
sola. No son bugs, son features que el producto no tiene.

### P1. Curación con un campo editable

El usuario quiere una tabla con un campo booleano/textual editable, abrir en
Excel, marcar, reimportar. El producto debería tener un comando
`b2g accept --from-csv` con columna `decision: accepted|rejected|undecided`.
**Cubierto por issue #26.**

### P2. Diagnóstico automático de señal vs. ruido

La heurística de `prueba/05` (palabras clave en título que separan pedagogía de
ML/lupus) es un patrón natural. El producto podría tener un comando
`b2g diagnose` que devuelva para cada paper un score de "probabilidad de ser del
campo" basado en keywords/título/abstract, y permita filtrar.

### P3. Negaciones quirúrgicas en la query

En `prueba/02` vimos que `sistémico` y `sujeto` en abstract matchean lupus y
"subjects" médicos. La query debería poder negar `NOT "machine learning"`,
`NOT algorithm`, etc. sin que el usuario arme las ecuaciones a mano.

### P4. Vista de clusters como tabla

El cruce corpus↔cluster (`_coupling_cluster_corpus` en `prueba/07`) es un output
tan útil como las redes mismas. Hoy solo se imprime en consola; debería poder
exportarse a CSV con columnas `cluster, size, seed_count, candidate_count,
year_min, year_max, year_mean, top_authors, top_keywords`.

### P5. Diff entre rondas de seed

Cuando el usuario hace `reseed` con una ecuación mutada, hoy no hay forma fácil
de ver qué entró, qué salió, y cómo cambiaron las comunidades. La metáfora
"git de la investigación" (mencionada en la nota 07) se concreta con un
`b2g diff --round 1 --round 3` que muestre papers añadidos, quitados, y cómo
se movieron los hubs entre rondas.

## Lo que la sesión NO hizo (limitaciones honestas)

- **No se curó formalmente.** Los 600 candidatos quedaron como `candidate`. Sin
  issue #26 resuelto, el flujo de curación no es viable a esa escala.
- **No se iteró la query con negaciones** (P3). La query v3 quedó como base;
  un script `prueba/08_ajustar_query_v4.py` está en la lista de próximos
  pendientes pero no se escribió en esta sesión.
- **No se construyó la red de co-citación.** `Networks.quick` la omite cuando
  `cited_by_id` está vacío, que es nuestro caso (el Hito 8b requiere un
  segundo nivel de fetch). La red de acoplamiento, co-autoría, instituciones
  y keywords se exploraron; co-citación quedó para otra sesión.
- **No se validó la reproducibilidad del output.** No se corrió el mismo
  pipeline dos veces para verificar que el `corpus_hash` y la composición
  de comunidades son bit a bit idénticos. Es un DoD del producto (ADR 0022)
  que no se probó en uso real.
- **No se cruzó con datos de la investigadora.** No traje mis propias
  exportaciones BibTeX ni las comparé con lo que devolvió OpenAlex. La
  [`BibtexSource`](../../src/bib2graph/sources/bibtex.py) existe pero no se
  usó.

## Lecciones metodológicas (para QA y para futuras sesiones)

1. **El script ad-hoc es señal, no ruido.** Cuando el usuario tiene que
   armar un script de un solo uso para hacer algo, eso es **evidencia de un
   feature faltante** (P1, P2, P3, P4). Documentar el script, no borrarlo.
2. **El timeout del forward chaining no es aceptable.** Una herramienta
   interactiva que se cuelga 10+ minutos rompe la confianza del usuario.
   Aunque la persistencia idempotente salva los datos, la experiencia
   destruye el producto. Issue #21 es prioritario.
3. **El workaround local es deuda técnica.** Inyectar `label` en el script
   de prueba es razonable para salir del paso, pero la deuda hay que
   pagarla: el fix tiene que llegar al núcleo (issue #25).
4. **El CLI no es solo "una opción" — es la API.** El producto está diseñado
   para ser usado por humanos Y por agentes. Cada hueco en el CLI es un
   hueco en la frontera programática. Por eso los issues #14, #21, #22, #26
   son todos del CLI: ese es el contrato.
5. **El QA no es solo `pytest`.** Probar el producto desde el lugar del
   investigador (con una pregunta real, datos reales, sesiones largas) expone
   cosas que la suite de tests no ve: composición de clusters, distribución
   de keywords, decisiones de curación, comparación de redes. Vale la pena
   hacer estas sesiones con regularidad y documentarlas.

## Apéndice — Issues abiertos durante la sesión

Todos creados en GitHub durante la sesión. Son el **flujo de salida** del QA:
cada uno cierra un hueco detectado en uso real.

- **#14** `feat(cli): exponer --max-results en seed (exploracion con muestras
  chicas)` — cubrir B1.
- **#21** `feat(cli): cap de semillas en chain forward para evitar timeouts`
  — cubrir B2. **Urgente** (footgun real).
- **#25** `feat(networks): inyectar label legible por defecto en nodos para
  export` — cubrir B3.
- **#22** `feat(cli): dump CSV/JSON de papers para revision humana offline`
  — cubrir B4.
- **#26** `feat(cli): accept/reject desde CSV de curacion` — cubrir B5 y P1.

Estado de la sesión al cierre: 800 papers en `valoraciones_v3.duckdb`
(200 semillas + 600 candidatos), 4 redes exportadas en `redes/` con labels
legibles (workaround local), diagnóstico de clusters en stdout. Próxima
sesión: ajustar query con negaciones (P3), resolver curación cuando #22 y
#26 estén listos.
