# Retroalimentación de agente — `bib2graph` v0.10.0

**De:** Claude (agente que corrió el ciclo completo en dos sesiones reales)
**Para:** mantenedor de bib2graph
**Contexto:** dos informes "estado del arte" generados de punta a punta — uno sobre EoS para gases (100 papers), otro sobre EoS para electrolitos (219 papers, 12 ecuaciones iterativas). El usuario quedó muy satisfecho con los informes, en particular las gráficas. Este documento responde dos cosas que pidió: **(1)** mi experiencia de usuario como agente usando la herramienta, y **(2)** el patrón reutilizable detrás de los informes, pensado para que lo agregues a la skill vendida (`b2g skill add`).

> Nota de transparencia sobre el modelo: la interacción la condujo **Sonnet 4.6**; esta síntesis la escribe **Opus 4.8**. Lo señalo porque puede ser relevante para calibrar qué tan "espontáneo" fue el patrón: gran parte del flujo que describo abajo lo improvisó Sonnet *sin* guía de la skill, lo cual es justamente la señal de que vale la pena codificarlo.

---

## Parte 1 — Experiencia de usuario (agente)

### 1.1 Lo que funcionó muy bien

**El modelo `Corpus` inmutable con factory `from_arrow` es excelente para un agente.** La semántica de valor (cada `accept`/`reject` devuelve un corpus nuevo) elimina toda una clase de errores de estado. Cuando exploré la API de Python antes de usar la CLI, esto me dio confianza para encadenar operaciones sin miedo a mutaciones sorpresa.

**La salida `--json` con envelope consistente (`{schema, ok, command, exit_code, data, warnings, error}`) es lo correcto.** Pude parsear todo programáticamente sin heurísticas frágiles. El campo `ok` booleano y `error.code` legible (`NETWORK_ERROR`, etc.) me dejaron construir reintentos limpios. **Esto es lo más importante que hace la herramienta agente-amigable** — por favor no lo cambien.

**`read top` recomputando en tiempo de lectura sin requerir `build` previo** es un detalle de diseño que se siente bien: bajé la barrera para "echar un vistazo" sin comprometerme a un pipeline completo.

**El patrón "honest-empty" (bloque vacío con `reason`/`fix_command` y exit 0)** lo vi en `read top` para co-citación. Es exactamente cómo una herramienta debería comunicarle a un agente "esto está vacío *por esta razón*, corré *este comando* para arreglarlo". Más comandos deberían hacer esto.

**La skill vendida acierta en el encuadre filosófico.** El "one-shot es un entregable real" + "mostrá que es el trabajo a la mitad" es un buen modelo mental. Me hizo ofrecer valor temprano en vez de exigir el ciclo completo.

### 1.2 Fricción real que viví (lo importante)

**(A) No hay forma de volcar abstracts en lote — esta fue mi mayor fricción, con diferencia.**
`read list --json` devuelve solo `{id, title, year, curation_status, is_seed}`. Para conseguir abstracts tuve que llamar `read show --id <X>` **una vez por paper**. Con 100–219 papers eso son cientos de invocaciones de subproceso, cada una con su overhead. Terminé escribiendo bucles en Python con `time.sleep()` para no saturar, y en la segunda sesión directamente **salté la CLI y pegué contra la API de OpenAlex con `urllib`** para reconstruir abstracts desde `abstract_inverted_index`. Eso es exactamente lo que la herramienta debería ahorrarme.

> **Pedido concreto #1:** un flag `read list --fields abstract,authors_raw,keywords_id,doi` (o un `read dump --json` que devuelva el corpus completo enriquecido en una sola llamada). Para un agente que va a sintetizar, leer todo el corpus de una vez es la operación más común, no la excepción.

**(B) `read top` da centralidad y comunidad, pero no puedo pedir "los top N *de cada comunidad*".**
Para los informes, la unidad de análisis natural fue *el cluster temático*. Tuve que traer un `read top -n 40` grande, cruzarlo manualmente con `networks/<kind>/clusters.csv`, agrupar por `community` en Python, y *luego* ir a buscar el abstract de cada uno (ver fricción A). Tres pasos manuales para algo que es el caso de uso central de "mapear un campo".

> **Pedido concreto #2:** `read top --by-community` (o `read clusters --top-per N`) que devuelva, por comunidad, los N papers más centrales **con sus abstracts**. Esto colapsaría ~80% del trabajo manual de ambos informes en una sola llamada.

**(C) Timeouts de OpenAlex con queries booleanas complejas.**
Las ecuaciones con muchos `AND`/`OR`/paréntesis anidados (`"equation of state" AND gas AND (thermodynamic OR properties OR PVT)`) daban `NETWORK_ERROR (ReadTimeout)` o `429` repetidamente. Las queries simples pasaban. Tuve que degradar la complejidad de la ecuación y meter esperas largas (60–120 s). No sé si el timeout de `seed` es configurable, pero un agente no tiene forma de saber que "la query es demasiado pesada para el endpoint" vs. "la red está caída" — ambos llegan como `NETWORK_ERROR`.

> **Pedido concreto #3:** (a) un `--timeout` configurable en `seed`/`chain`; (b) distinguir en `error.code` entre `RATE_LIMITED` (429, reintentable con backoff) y `QUERY_TOO_COMPLEX`/`UPSTREAM_TIMEOUT` (504, hay que simplificar). Con códigos distintos puedo reaccionar correctamente sin adivinar.

**(D) `read stats --group-by` solo acepta `status|year|is_seed`.**
Quise `--group-by source` (journal) y `--group-by community` y no existen. Para caracterizar un campo, "¿en qué revistas se publica esto?" y "¿qué tamaño tiene cada comunidad?" son preguntas de primer orden. Terminé calculándolas a mano desde los CSV exportados.

> **Pedido concreto #4:** ampliar `--group-by` a `source`, `language`, `community`, y `decade` (década, no solo año — para campos con 90 años de historia como electrolitos, agrupar por año es demasiado granular).

**(E) Pequeño tropiezo de aprendizaje: `apply_filters` (API Python) devuelve una tupla `(Corpus, list[FilterStep])`, no un `Corpus`.**
Me costó un error en tiempo de ejecución. No es un bug —es razonable querer los `FilterStep` para PRISMA— pero el docstring no lo telegrafía bien. La CLI no tiene este problema (es solo en la API Python).

### 1.3 Resumen de la experiencia en una línea

La herramienta es **excelente para forrajear y construir las redes**, pero **me suelta justo antes de la síntesis**: el último kilómetro (abstracts en lote, agrupar por comunidad, leer las redes para escribir algo) lo tuve que improvisar yo cada vez. Y como ese último kilómetro es donde está el entregable que el usuario realmente quería, vale la pena codificarlo. Eso es la Parte 2.

---

## Parte 2 — El patrón de informe (para agregar a la skill)

La skill vendida termina el ciclo en `read top` y el "mapa estás-acá". Pero en ambas sesiones el usuario no quería un listado de papers centrales: quería **un documento de síntesis con figuras tipo paper**. Ese paso —de "redes construidas" a "informe escrito"— no está en la skill, lo improvisé las dos veces, y es replicable. Aquí está destilado.

### 2.1 El patrón en una frase

> **Cluster como unidad de análisis → abstracts como evidencia → figuras como argumento → documento como entregable.**

La red de acoplamiento bibliográfico ya particiona el campo en comunidades (Louvain). Cada comunidad *es* un subtema. El informe se escribe **una sección por comunidad**, anclada en los abstracts de sus papers más centrales, e ilustrada con figuras que muestran estructura (no decoración).

### 2.2 El pipeline de síntesis (los pasos que faltan en la skill)

```
[la skill ya cubre hasta acá: seed → chain → build → read top]
        │
        ▼
6. EXTRAER  →  abstracts + autores + keywords de los top-N por comunidad
              (hoy: read show en bucle — debería ser read top --by-community)
        │
        ▼
7. CLASIFICAR → agrupar papers en "familias" temáticas. Dos vías:
              (a) usar las comunidades de Louvain directamente, o
              (b) clasificación por keywords/título cuando el usuario
                  ya tiene un marco mental del campo (ej. las 7 familias
                  de EoS para electrolitos)
        │
        ▼
8. FIGURAR  →  generar 4–6 figuras matplotlib "tipo paper" (ver 2.3)
        │
        ▼
9. ENSAMBLAR → documento Word: una sección por familia, cada afirmación
              anclada en un abstract, cada figura con caption interpretativo
```

Los pasos 6–9 son los que conviene que la skill describa. No hace falta que la herramienta los *ejecute* (siguen siendo juicio + generación), pero sí que **le diga al agente que el ciclo no termina en `read top`** y le dé la receta.

### 2.3 La receta de figuras (esto es lo que más gustó)

Seis arquetipos de figura cubrieron ambos informes. Cada uno responde una pregunta concreta sobre el campo:

| # | Figura | Pregunta que responde | Datos de bib2graph |
|---|--------|----------------------|--------------------|
| 1 | **Distribución temporal** (barras + tendencia) | ¿Cuándo creció el campo? ¿hay hitos? | `read stats --group-by year` |
| 2 | **Línea de tiempo histórica** (hitos por familia) | ¿Cómo evolucionaron los modelos/escuelas? | años + clasificación por familia |
| 3 | **Mapa de comunidades** (burbujas por cluster) | ¿En qué subtemas se parte el campo? | `clusters.csv` + tamaños |
| 4 | **Top papers por centralidad** (barras horizontales, color=comunidad) | ¿Cuáles son los trabajos pivote? | `read top` |
| 5 | **Landscape 2D** (scatter: eje X vs eje Y, tamaño=cobertura) | ¿Cómo se comparan los enfoques en 2 dimensiones clave? | síntesis de abstracts |
| 6 | **Red de co-ocurrencia** (grafo de keywords, top-N nodos) | ¿Cuál es el vocabulario y qué conecta los subtemas? | `exports/keyword_cooccurrence/` |

**Lo que hace que se vean "tipo paper" (los detalles que importan):**

- **Paleta sobria y consistente**: navy/azul/teal + acentos ámbar/rojo. Un color por familia, usado en *todas* las figuras (la comunidad 4 es azul en la fig 3, en la fig 4 y en la leyenda). La consistencia cromática entre figuras es lo que más "amarra" el documento.
- **Fondo `#f7f9fc`** (no blanco puro) — se lee como figura de revista, no como output de Jupyter.
- **`spines top/right` ocultos**, grid tenue (`alpha 0.3`) y por debajo (`set_axisbelow`).
- **Tamaño de burbuja = una tercera variable** (cobertura, versatilidad). Convierte un scatter 2D en uno 3D sin saturar.
- **Anotaciones con `arrowprops` finos** en vez de etiquetas pegadas — evita solapamiento y se ve intencional.
- **150 dpi, `bbox_inches='tight'`**, ancho ~7.5–9 in para que entren a página completa en el docx.
- **Captions interpretativos, no descriptivos.** No "Figura 1: publicaciones por año" sino "Figura 1: el pico de 2012 coincide con la publicación de GERG-2008". El caption *argumenta*, no rotula.

Hay un script de referencia con los seis arquetipos parametrizados que acompaña este documento (`figuras_tipo_paper.py`): es directamente adaptable y encapsula la paleta y los defaults de estilo.

### 2.4 La estructura de documento que funcionó

```
Portada (título + tabla de métricas del corpus: N papers, N familias, rango temporal)
0. El problema fundamental    ← por qué el campo es difícil (engancha al lector)
1. Línea de tiempo histórica  ← Figura 2
2. Distribución y evolución   ← Figuras 1, también barras por familia
3. Arquitectura/taxonomía     ← diagrama de cómo se organizan los enfoques
4. Análisis por familia       ← EL NÚCLEO: una subsección por comunidad,
                                 cada una con su cuadro-resumen + abstracts citados
5. Mapa de capacidades        ← Figura 4 (radar) + Figura 5 (landscape)
6. El debate central          ← la tensión viva del campo (donde está la acción)
7. Guía de selección          ← tabla maestra: qué modelo para qué caso
8. Respuesta a la pregunta    ← si el usuario tenía una pregunta de fondo, respondela aquí
9. Tendencias emergentes      ← hacia dónde va
Referencias                   ← top papers por centralidad, con DOI
Nota metodológica             ← cómo se armó el corpus (reproducibilidad/PRISMA)
```

La **sección 4 es el corazón** y mapea 1:1 con las comunidades de Louvain. Cada subsección usó un patrón fijo: un *cuadro-resumen de color* (familia, período, autores clave, términos) seguido de 2–3 párrafos donde cada afirmación técnica está anclada en un abstract concreto con su DOI. Eso es lo que da autoridad: no es opinión del agente, es síntesis de la evidencia recuperada.

La **nota metodológica al final no es opcional** — es lo que hace el informe defendible (PRISMA). Documenta las ecuaciones de búsqueda, el N, la fecha, el algoritmo de comunidades y su semilla. Encaja perfecto con la filosofía "reproducible, sin IA generativa" de la herramienta.

### 2.5 Sobre clasificación: comunidades de Louvain vs. marco del usuario

Un matiz que aprendí entre las dos sesiones: **a veces el usuario ya tiene un marco mental del campo** que no coincide con las comunidades de Louvain. En electrolitos, el usuario pensaba en términos de "familias de modelos" (Debye-Hückel, Pitzer, eNRTL, CPA, SAFT...) que son una taxonomía *conceptual*, no la partición *estructural* que da la bibliometría. Ahí clasifiqué por keywords/título contra esas familias conocidas, y usé las comunidades de Louvain como validación cruzada.

> **Implicación para la skill:** ofrecé las dos vías. Si el campo es nuevo para el usuario → comunidades de Louvain (deja que la estructura hable). Si el usuario ya tiene un marco → clasificá contra su marco y usá Louvain para verificar/sorprender. Esto conecta con el paso 6 del ciclo (sensemaking, irreductiblemente humano): la taxonomía es del humano, la estructura es de la herramienta.

---

## Parte 3 — Recomendaciones priorizadas para la skill

Ordenadas por impacto sobre la calidad del entregable final:

1. **Extender la skill más allá de `read top`** con el pipeline de síntesis (Parte 2.2). Hoy la skill describe cómo conseguir el material pero no cómo convertirlo en el documento que el usuario quería. Es el hueco más grande.

2. **Documentar la receta de figuras (2.3) como reference file** (`reference/figuras.md` + el script). Fue lo que más valoró el usuario y lo que un agente sin guía improvisa de forma inconsistente.

3. **Resolver la fricción de abstracts en lote (pedido #1)** a nivel herramienta. Sin esto, cada informe paga el costo de cientos de `read show` o, peor, el agente se salta la CLI y va directo a OpenAlex (perdiendo la trazabilidad que la herramienta provee).

4. **`read top --by-community` con abstracts (pedido #2)** — colapsa el caso de uso central de "mapear un campo" en una llamada.

5. **Códigos de error distinguibles (pedido #3)** — `RATE_LIMITED` vs `QUERY_TOO_COMPLEX` vs `UPSTREAM_TIMEOUT`. Sin esto, los reintentos del agente son a ciegas.

6. **Ampliar `read stats --group-by` (pedido #4)** a `source`, `community`, `decade`, `language`.

Los puntos 1 y 2 son de skill (puro contenido, los podés agregar ya). Los puntos 3–6 son de herramienta. Si tuviera que elegir **uno solo**: el #1, porque es lo que separa "tengo unas redes" de "tengo el informe que pedí".

---

*Documento generado como retroalimentación de uso real. Sin datos personales del usuario. Los dos temas de investigación (EoS para gases / para electrolitos) son de dominio público en ingeniería química y no sensibles.*
