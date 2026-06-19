# 14 — Sesión e2e con `prueba_e2e/`: detección de anomalías ML (interpretabilidad + teoría de la información)

> ⚠️ **NOTA DE SESIÓN — no es decisión ni ADR.** Captura un uso real del producto v0.6
> como investigador con una pregunta concreta, ejecutando el ciclo **100% por el CLI `b2g`**
> hasta donde el CLI alcanzó, y bajando a Python solo donde el CLI no llegó. El objetivo
> de esta nota es **registrar exactamente dónde hubo que bajar a Python y por qué** — eso es
> el feedback valioso: cada bajada a Python es un hueco del CLI. Fecha: 2026-06-18.
> Documentos hermanos: [`09-sesion-qa-prueba-ecologia-valoraciones.md`](09-sesion-qa-prueba-ecologia-valoraciones.md)
> (la sesión QA análoga sobre `prueba/`, que motivó #14/#21/#22/#25/#26),
> [`13-continuacion-sesion-valoraciones.md`](13-continuacion-sesion-valoraciones.md).

## Tesis de la sesión

A diferencia de la sesión 09 —donde casi todo se hizo con scripts Python porque el CLI
todavía no existía o estaba incompleto—, acá el CLI **ya cubre la columna vertebral del
ciclo** (init → seed → build → snapshot, todo verde, sin un solo script). La pregunta de
investigación fue: *¿cuáles son los métodos más actuales de detección de anomalías en ML,
especialmente los que tienen interpretabilidad y usan teoría de la información?* El corpus
quedó en `prueba_e2e/ml-anomalias/` (workspace gitignoreado, ADR 0029).

El hallazgo metodológico de la sesión: **lo que quedó en Python ya no es el ciclo, es la
lectura del corpus**. Todos los gestos de "sembrar y construir" son CLI puro; todos los
gestos de "mirar qué hay adentro" siguen exigiendo Python. Ese es el hueco que esta nota
documenta.

## Lo que se hizo (el flujo real)

| Paso | Comando / código | Frontera | Resultado |
|---|---|---|---|
| 1 | `b2g init ml-anomalias --name "…"` | **CLI** | workspace creado (v0.6.0) |
| 2 | `b2g seed --email … --max-results 200 --min-year 2018 --equation '(…) AND (…) AND (…)'` | **CLI** | 199 papers (`candidate`), query traducida a `title_and_abstract.search:(…)` + `from_publication_date:2018-01-01` |
| 3 | `b2g status --json` | **CLI** | `SEEDED`, 199 candidatos, round 1 |
| 4 | *listar títulos por año + histograma* | **Python** ⚠️ | 138/199 son 2025–26; 30 títulos más recientes |
| 5 | `b2g build --json` | **CLI** | 4 redes (acoplamiento, co-autoría, instituciones, keywords) + `clusters.csv` por red |
| 6 | *leer `clusters.csv`* | **CLI (output)** | clusters legibles, pero keywords genéricos de OpenAlex |
| 7 | *conteo de familias de método sobre los 199 abstracts* | **Python** ⚠️ | tabla de frecuencias (entropy 120, MI 38, SHAP 27, IB 10, causal 19, …) |
| 8 | *títulos ejemplares por método (regex sobre título)* | **Python** ⚠️ | papers concretos por familia |
| 9 | `b2g snapshot --json` | **CLI** | foto sellada en `snapshots/` |

La ecuación fue la intersección AND de tres bloques (anomaly/outlier/OOD detection) ∧
(interpretable/explainable/XAI) ∧ (information theory/MI/entropy/information bottleneck).
La intersección casi llenó el cap de 200 → el cruce de los tres conceptos está bien poblado
en la literatura 2024–2026.

## El feedback central: para qué se usó Python y por qué no estaba en el CLI

Tres bajadas a Python (pasos 4, 7, 8), y **las tres son la misma raíz: el CLI puede
*producir* el corpus pero no puede *leerlo* salvo un paper a la vez**.

### G1. No hay forma de listar/ojear el corpus desde el CLI

**Síntoma:** después de sembrar 199 papers, para ver *qué se trajo* (títulos, años) hubo que
escribir Python que abre `DuckDBStore`, carga la tabla Arrow y la recorre.

**Causa:** el inventario read-only del CLI es:
- `b2g status` → conteos por `curation_status` y por `CycleState`, **nada de contenido**.
- `b2g inspect` sin `--id` → manifest + conteos; con `--id` → **un** paper. No hay listado.

No existe un `b2g list` / `b2g ls` que devuelva las filas (id, título, año, status) con
límite, orden y filtro. El humano (o el agente LLM, que es el usuario primario del CLI según
ADR 0010) está ciego sobre su propio corpus a menos que baje a Python o conozca los IDs de
antemano.

**Lo más cercano que sí existe:** `b2g curate --dump --all` escribe un CSV de todo el corpus.
Sirve para *abrir en Excel*, pero (a) está enmarcado como "curación", no como "ojear", y
(b) no responde preguntas rápidas ("dame los 30 más recientes") sin abrir la planilla.

**Por qué importa:** el CLI es la API para agentes (ADR 0010). Un agente que siembra y no
puede leer el resultado en el mismo lenguaje (subprocess + JSON) no puede cerrar el lazo de
exploración: tiene que salir a Python, y ahí el CLI deja de ser la frontera.

### G2. No hay facetado / distribución desde el CLI

**Síntoma:** el histograma por año (paso 4) y los conteos por familia de método (paso 7) se
calcularon a mano en Python.

**Causa:** `status` cuenta por `curation_status` y nada más. No hay `--group-by year`,
`--group-by language`, ni nada equivalente. La distribución temporal —la pregunta más
básica de "¿qué tan actual es mi corpus?"— no tiene comando.

**Por qué importa:** la pregunta del PO era explícitamente sobre **lo más actual**. "138 de
199 son 2025–26" es la métrica que respondió eso, y salió de Python. Es exactamente el tipo
de faceta que debería ser un flag, no un script.

### G3. No hay búsqueda/filtro de texto sobre el corpus ya traído

**Síntoma:** "dame los papers de Information Bottleneck / Mutual Information" (paso 8) se
resolvió con regex sobre títulos en Python.

**Causa:** una vez en la biblioteca viva, no hay forma de filtrar localmente por término
(`b2g list --grep "information bottleneck"`). El único filtrado del CLI es **PRISMA**
(`b2g filter`, que marca `rejected`, no consulta) y la query de OpenAlex en el `seed` (red,
no local).

**Por qué importa:** la síntesis temática —el verdadero deliverable de una investigación—
se construye iterando "mostrame X, ahora mostrame Y". Sin filtro local, cada iteración es
un script. Esto es la versión 2026 del P2/P4 de la nota 09: el patrón "diagnóstico/vista de
tabla" sigue sin estar absorbido.

### G4 (menor). `seed --native` es un footgun: exige el prefijo de campo

**Síntoma:** el primer `seed --native '("…") AND (…)'` devolvió **400 Bad Request** de
OpenAlex (exit 4, `NETWORK_ERROR`).

**Causa:** `--native` pasa la ecuación **cruda como el `filter` entero**, sin envolverla en
`title_and_abstract.search:(…)`. OpenAlex necesita el campo; sin él, el filtro es inválido.
Sin `--native`, el traductor agrega el prefijo y funciona perfecto.

**Por qué importa:** el error 400 se reporta como `NETWORK_ERROR` ("Verificá tu conexión a
internet"), lo cual **despista**: no es la red, es la query. `--native` debería (a) validar
que la query trae un campo o (b) documentar en el `--help` que el usuario es responsable del
prefijo `title_and_abstract.search:`, y el 400 debería mapearse a error de datos (exit 2),
no de red (exit 4).

## Lo que el CLI hizo bien (contraste con la sesión 09)

Vale registrarlo porque es el progreso desde la nota 09:

- **El ciclo seed → build → snapshot es CLI puro.** En 09, sembrar, exportar redes con
  labels y todo lo demás necesitaba scripts. Hoy no. Los issues #14 (`--max-results`),
  #21 (cap de chaining), #25 (labels legibles) están cerrados y se nota: las redes salieron
  con labels y el seed aceptó `--max-results`/`--min-year` sin tocar Python.
- **`clusters.csv` lo escribe `b2g build`** (issue #31, P4 de la nota 09 absorbido). La
  "vista de clusters como tabla" que en 09 era un script (`07_distribuciones_clusters.py`)
  ahora es un artefacto del CLI. El único pero: los `top_keywords` son concepts genéricos de
  OpenAlex (`computer-science`, `artificial-intelligence`), poco útiles para *nombrar* el
  método del cluster.
- **El workspace por carpeta (ADR 0029)** hizo que todos los comandos se resolvieran por
  ambiente desde dentro de `ml-anomalias/`, sin `--store` ni paths. Limpio.

## Patrones que el producto debería absorber (continuación de la nota 09)

### P6. `b2g list` — el comando que falta

Un read-only que devuelva filas del corpus con `--limit`, `--sort-by year|title`,
`--status candidate|accepted|…`, `--grep <term>` y `--json`. Cubre G1 + G3 de un saque.
Es, probablemente, el hueco más sentido del CLI hoy: sin él, el agente LLM no puede inspeccionar
lo que sembró.

### P7. Facetas en `status` (o un `b2g stats`)

`--group-by year|language|type` para responder "qué tan actual / en qué idiomas / qué tipos
de documento" sin Python. Cubre G2.

### P8. Co-ocurrencia de keywords con vocabulario real, no concepts de OpenAlex

El `clusters.csv` y la red de keywords usan los `concepts` de OpenAlex (jerarquía genérica).
Para *nombrar* un cluster ("Information Bottleneck", "Shapley/SHAP") sirve más el vocabulario
extraído del título/abstract. Esto cruza con el thesaurus (ADR 0011) — quizás la red de
keywords debería poder construirse sobre términos del corpus, no solo concepts.

## Hallazgos de investigación (el deliverable, breve)

Para que la nota sea autocontenida: sobre 199 papers (138 de 2025–26), la intersección
**interpretabilidad + teoría de la información** la dominan cuatro líneas, todas
interpretables por construcción (no post-hoc):

1. **Information Bottleneck (IB)** — comprime reteniendo solo la información relevante a la
   anomalía → detección + representación mínima interpretable en un principio (VIB, IB
   multimodal, 2026).
2. **Mutual Information como score y atribución** — MI para puntuar y explicar la variable
   responsable (MGAD, MI ~ GLRT, weighted MI para OOD).
3. **Frameworks entropy-driven XAI** — la familia más poblada (120 mencionan entropía);
   entropía como score y explicación a la vez; combinaciones con flujos normalizadores +
   causalidad (CCEFiNF, 2026).
4. **Causal / counterfactual anomaly detection** — emergente, el "por qué" es el camino
   causal (19 papers).

**SHAP/Shapley** (27) es la capa de interpretabilidad **post-hoc** más usada sobre detectores
existentes — fundamento teórico-informacional, pero explicación añadida, no detección
interpretable nativa.

## Lo que la sesión NO hizo (limitaciones honestas)

- **No se enriqueció** (`b2g enrich`): la red de co-citación quedó fuera (necesita
  `cited_by_id`, 2º nivel de fetch). Solo 4 de las 5 redes posibles.
- **No se curó**: los 199 quedaron `candidate`. Se observaron títulos duplicados ×3 (mismo
  trabajo de varias fuentes) — candidato a curación + dedup `[dedup]`.
- **No se verificó reproducibilidad** corriendo el pipeline dos veces (mismo `corpus_hash`).

## Lecciones metodológicas

1. **La frontera se movió, pero no desapareció.** En 09 el script ad-hoc cubría el *ciclo*;
   en 14 cubre la *lectura*. El producto absorbió producir el corpus; falta absorber leerlo.
2. **Cada `import` de `DuckDBStore` en un script de sesión es un issue de CLI.** La regla de
   la nota 09 sigue valiendo: el script ad-hoc es señal, no ruido. Hoy señala G1/G2/G3 → P6/P7.
3. **El agente LLM es el caso de prueba más duro.** Un humano puede abrir Python; un agente
   que orquesta por subprocess no debería tener que. Que el CLI no pueda *listar* su propio
   corpus es el hueco más visible desde la óptica ADR 0010.
4. **Mapear bien los exit codes importa.** Un 400 de query reportado como `NETWORK_ERROR`
   (exit 4) manda a debuggear la red cuando el problema es la query (G4).
