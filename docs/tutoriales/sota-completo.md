---
title: Tutorial completo — De la pregunta al reporte de SOTA
---

# Tutorial completo — De la pregunta al reporte de SOTA

Un recorrido paso a paso por un **estado del arte riguroso**: desde formular
la pregunta de investigación hasta redactar un análisis con tensiones,
escuelas de pensamiento y huecos sin explorar.

Este es el tutorial detallado (45 min de lectura + 2–3 horas de investigación).
Si acaba de descubrir bib2graph, empiece por el [tutorial corto](claude-code.md).

!!! info "Requisitos"
    - Una pregunta de investigación clara (no un tema genérico).
    - **bib2graph instalado** en tu máquina: `pip install bib2graph`
    - Un agente de IA (Claude, ChatGPT, MiniMax, etc.) con ejecución de código, o disposición a usar el CLI directamente.
    - Tiempo: 3–4 horas para el ciclo completo.
    - Opcional: API key de OpenAlex (gratuita, para corpus > 100 papers).

---

## Anatomía de un estado del arte

Un SOTA riguroso no es una lista de papers. Es un **mapa de cómo piensa un campo**:

```
pregunta ──► ecuación ──► corpus ──► curación ──► redes ──► comunidades
                                                                  │
                                        ◄──────────────────────── lectura
                                              (qué vemos en el mapa)
                                                  │
                                    tendencias, tensiones, huecos
                                                  │
                                            reporte
```

Vamos paso a paso.

---

## Paso 0 — Instala bib2graph

**Entrada:** Tu máquina con Python 3.10+.  
**Salida:** bib2graph funcionando y listo para usar.

Abre tu terminal y ejecuta:

```bash
pip install bib2graph
```

Verifica que funciona:

```bash
b2g --help
```

Deberías ver la lista de comandos de bib2graph. Si no, consulta [Instalación](../getting-started/installation.md).

### Entiende el flujo de comandos básicos

bib2graph usa un flujo de **comandos secuenciales**:

```bash
b2g init ./mi-sota          # Crea una carpeta de proyecto
cd mi-sota

b2g seed "tu_ecuacion"      # Trae papers desde OpenAlex
b2g chain                   # (Opcional) Expande por citaciones
b2g curate                  # Acepta/rechaza papers (curación)
b2g build                   # Construye redes
b2g read list               # Visualiza papers
b2g export --format graphml # Exporta redes
```

Cada comando transiciona el estado del corpus. Vamos a ver esto en detalle.

---

## Paso 1 — Afina tu pregunta de investigación

**Entrada:** Un tema que te interesa.  
**Salida:** Una pregunta clara, acotada, formulable.

### Cómo llegar de un tema a una pregunta

❌ *"Inteligencia artificial"* → Demasiado genérico. ¿Qué aspecto? ¿Qué dominio?

✅ *"¿Cómo se aborda el problema de alineación de valores en modelos de
lenguaje grandes, y cuáles son las tensiones entre eficiencia computacional
y robustez ética entre 2020 y hoy?"*

### Checklist para tu pregunta

1. **¿Específica?** ¿Puedo reducirla a 4–6 palabras clave?
2. **¿Temporal?** ¿Hay un rango de años relevante? (5–10 años suele ser ideal).
3. **¿Acotada?** ¿Espero 50 papers, 500, 5000?
4. **¿Contestable?** ¿Puedo responderla buscando en artículos científicos?

### Ejemplo: Desarrolla la pregunta

**Mi tema inicial:** "Métodos de recuperación de información."

**Mi pregunta después del refinamiento:**
> ¿Cuáles son los enfoques dominantes para recuperación de información en
> contextos multilingües, cuáles son sus tensiones (vocabulario vs. semántica,
> eficiencia vs. precisión), y cuáles son los huecos sin explorar entre 2015
> y 2024?

Eso es buscable, acotado, y con una tensión clara.

---

## Paso 2 — Elaborá una ecuación de búsqueda

**Entrada:** Tu pregunta de investigación.  
**Salida:** Una ecuación booleana que traduzca esa pregunta.

### La estructura

```
(concepto_A_términos)
AND (concepto_B_términos)
AND (concepto_C_términos)
[AND NOT (exclusiones)]
```

Cada paréntesis es un concepto; dentro, los términos están unidos por `OR`
(sinónimos). Los `AND` conectan conceptos (todos deben estar presentes).

### Para mi ejemplo

```
(information retrieval OR IR OR search)
AND (multilingual OR cross-lingual OR language-agnostic OR polyglot)
AND (method OR approach OR framework OR system OR architecture)
```

### Consejos prácticos

- **Un concepto = una dimensión de tu pregunta.** Aquí:
  - Concepto A: la tarea (recuperación).
  - Concepto B: la restricción (multilingüe).
  - Concepto C: el tipo de resultado (métodos, no papers de aplicación).

- **Evita genéricos.** "machine learning" sola atrapa cientos de miles de papers.

- **Testea:** Pídele a Claude que busque 50 papers con tu ecuación y revisa los
  títulos. ¿Ves ruido sistemático? Ajusta.

- **Excluye si hace falta:** `AND NOT (machine translation)` si hay mucho ruido
  ahí.

---

## Paso 3 — Siembra el corpus

**Entrada:** Ecuación de búsqueda, rango de años.  
**Salida:** Corpus inicial (~200–300 papers).

### Opción 1: Con CLI directo

```bash
cd mi-sota
b2g seed "(information retrieval OR IR) AND (multilingual OR cross-lingual) AND (method OR approach)" --min-year 2015 --max-results 250
```

bib2graph descarga papers desde OpenAlex y los guarda en `.duckdb` dentro de la carpeta.

### Opción 2: Con ayuda de un agente

Puedes pedirle al agente (Claude, ChatGPT, etc.) que:

1. Genere la ecuación de búsqueda a partir de tu pregunta.
2. Execute el comando `b2g seed` en tu máquina.
3. Verifique los resultados.

**Prompt:**

```text
Tengo mi pregunta de investigación:
[TU PREGUNTA]

Propón una ecuación de búsqueda para bib2graph.
Luego dame el comando exacto para ejecutar:
b2g seed "[ecuacion]" --min-year 2015 --max-results 250

Muestra qué debería ver después de ejecutarlo.
```

El agente genera la ecuación y tú ejecutas el comando en tu terminal. Luego:

```bash
b2g read stats --group-by year
```

Para ver la distribución temporal.

### Verificación

Revisa el corpus:

```bash
b2g read list --query "tus_palabras_clave" | head -20
```

¿Todos tienen relación directa con tu tema? Si hay ruido sistemático, ajusta la
ecuación y vuelve a ejecutar `b2g seed` en una carpeta nueva.

### Punto de decisión

- **Corpus muy pequeño (<50 papers)?** Abre la ecuación (menos `AND`, más sinónimos).
- **Corpus muy grande (>1000)?** Ciérrala (más `AND`, menos sinónimos, o agrega
  un concepto específico más).
- **Corpus bien (~200–400)?** Perfecto, seguimos.

---

## Paso 4 — Expande por citaciones (opcional)

**Entrada:** Corpus de siembra.  
**Salida:** Corpus expandido (~20–50% más) con más densidad de referencias.

El **forrajeo** (backward chaining) busca papers que no aparecieron en tu
búsqueda original, pero que son citados por los que sí están. Aumenta la
*sensibilidad* (no pierdes papers clave) sin agregar mucho ruido.

### Cuándo hacer esto

✅ **Hazlo si:** el tema es muy específico, querés máxima cobertura, o el corpus
inicial es pequeño.

❌ **No lo hagas si:** el corpus ya es grande (>500), no querés aumentarlo, o es
tu primer SOTA (primero lee la red de siembra, después decide).

### Con Claude

```text
Expandí el corpus usando forrajeo (backward chaining):
seguí una capa de referencias de los papers ya en el corpus
y agregá hasta 100 papers nuevos.

Muestra:
- Cuántos papers nuevos se agregaron
- Si hay papers muy antiguos (pre-2000): ¿los mantengo o descarto?
```

---

## Paso 5 — Curá el corpus (PRISMA)

**Entrada:** Corpus (siembra o expandido).  
**Salida:** Corpus curado, con decisiones criteriales explícitas y versionables.

La curación es **manual**. No se automatiza porque cada decisión es criterial.

### Flujo PRISMA simplificado

```
IDENTIFICACIÓN
├─ ¿Duplicado o retractado? → RECHAZAR
└─ ¿En el idioma adecuado? → si no, RECHAZAR

CRIBADO (título + resumen)
├─ ¿Título claramente fuera de scope? → RECHAZAR
└─ ¿Resumen no aporta al tema? → RECHAZAR

ELEGIBILIDAD (lectura de disponibilidad)
├─ ¿Texto completo inaccesible? → CANDIDATO (maybe later)
└─ ¿Métodos/resultados vagos o especulativos? → CANDIDATO

INCLUSIÓN (decisión final)
├─ ¿Relevancia alta? → ACEPTAR
└─ ¿Relevancia media pero aporta tensión? → ACEPTAR
```

### Con Claude

Pídele a Claude:

```text
Hacé curación PRISMA del corpus. Revisá cada paper:
1. Si es duplicado o retractado: RECHAZAR
2. Si el título no tiene relación directa: RECHAZAR
3. Si el resumen sugiere que no toca el tema: RECHAZAR
4. Si no hay texto completo: CANDIDATO (no rechaces)
5. En otro caso: ACEPTAR

Mostrá un resumen: cuántos ACCEPTED, REJECTED, CANDIDATE.
Lista 5 ejemplos de RECHAZADOS con razón.
```

### Checklist

- [ ] ¿Documenté mis criterios explícitamente?
- [ ] ¿El corpus ACCEPTED quedó entre 100–300 papers?
- [ ] ¿Revisaste una muestra de rechazados para asegurarme de que no falta algo obvio?
- [ ] ¿Hay equilibrio entre años (no es monocromático)?

---

## Paso 6 — Construí las redes

**Entrada:** Corpus curado (papers ACCEPTED).  
**Salida:** 3 redes + métricas.

Las tres redes que importan:

1. **Acoplamiento bibliográfico:** Papers que citan las mismas referencias.
   (Responde: ¿cuáles son los sub-temas?)
2. **Co-citación:** Papers que se citan mutuamente o son citados juntos.
   (Responde: ¿cuáles son los influentes?)
3. **Co-autoría:** Quién escribe con quién.
   (Responde: ¿cuáles son los colegios invisibles?)

### Con Claude

```text
Construí 3 redes del corpus ACCEPTED usando bib2graph:
1. Acoplamiento bibliográfico
2. Co-citación
3. Co-autoría

Para cada red:
- Detectá comunidades usando Louvain (clustering)
- Muestra una visualización coloreada por comunidad
- Reportá: # nodos, # aristas, # comunidades
- Lista los 3 papers más centrales (mayor grado) de cada comunidad
```

### Qué esperar

- **Acoplamiento:** es la "red primaria" — más densa, más comunidades. Aquí ves
  los sub-temas claros.
- **Co-citación:** a menudo es más dispersa; destaca papers que actúan como
  referencias canónicas (los "clásicos" del campo).
- **Co-autoría:** también dispersa, pero útil para ver equipos y colaboraciones
  persistentes.

---

## Paso 7 — Nombrá y caracterizá las comunidades

**Entrada:** Redes + corpus curado.  
**Salida:** Una tabla con comunidades, keywords, seminales, y tensiones.

Para cada comunidad en la red de acoplamiento (la principal):

1. **Nombre:** 1–3 palabras que capturen el enfoque (ej. "Métodos probabilísticos").
2. **Keywords:** 5–7 palabras clave dominantes en esa comunidad.
3. **Seminales:** Top 2–3 papers (mayor grado) dentro de la comunidad.
4. **Descripción:** 2–3 frases de qué hacen esos papers.
5. **Tensión:** ¿Qué los diferencia de otras comunidades? ¿Dónde discrepan?

### Con Claude

```text
Para la red de acoplamiento, analizá cada comunidad:

1. Nombre (síntesis del enfoque en 1–3 palabras)
2. Keywords principales (5–7 terms que definen esa comunidad)
3. Seminales: top 2 papers (por grado), con título, autores, año
4. Descripción: ¿qué hacen esos papers? ¿Cuál es el enfoque común?
5. Tensión: ¿en qué difieren de otras comunidades?

Armame una tabla: [Comunidad | Enfoque | Keywords | Seminales | Tensión]
```

### Ejemplo de salida

| Comunidad | Enfoque | Keywords | Seminales | Tensión |
|-----------|---------|----------|-----------|---------|
| **Probabilístico** | Modelos estadísticos, HMM | language model, smoothing, EM | [Smith 2008], [Brown 2010] | Eficiencia vs. cobertura |
| **Vectorial** | Embeddings, semántica latente | word embeddings, LSA, similarity | [Mikolov 2013], [Pennington 2014] | Interpretabilidad vs. performance |
| **Neuronal** | Deep learning, transformers | neural networks, attention, BERT | [Vaswani 2017], [Devlin 2019] | Costo computacional vs. generalización |

---

## Paso 8 — Analiza tendencias e influencias

**Entrada:** Redes, comunidades, corpus.  
**Salida:** Observaciones sobre evolución, actores clave, huecos.

Responde estas preguntas:

### 1. ¿Cómo evolucionó el campo?

```text
Muestra:
- Gráfico de # papers/año en el corpus
- Cómo cambiaron las comunidades (% de papers) año a año
- ¿Hay una comunidad que crecía y ahora decrece?
- ¿Hay una emergente (crecimiento exponencial últimos 3 años)?
```

### 2. ¿Quiénes son los influyentes?

```text
Top 10 autores por:
- Cantidad de papers (productividad)
- Grado en la red de co-citación (influencia)
- Betweenness (actúan de "puente" entre comunidades)
```

### 3. ¿Dónde están los huecos?

```text
Mirando las 3 redes, identificá:
- Comunidades o autores que no se conectan entre sí (fronteras vacías)
- Combinaciones de keywords que NO aparecen (gaps)
- Preguntas que nadie se hace (inferir de lo que sí hay)
```

### 4. ¿Quién lidera por institución?

```text
Co-autoría: top 10 instituciones por:
- Cantidad de papers
- Colaboraciones externas
```

---

## Paso 9 — Redactá el reporte

**Entrada:** Análisis anterior, comunidades, tendencias.  
**Salida:** Documento estructurado (Markdown, Word, Google Docs).

### Estructura recomendada

```
RESUMEN EJECUTIVO
├─ Pregunta de investigación
├─ Hallazgos principales (2–3 frases)
└─ Síntesis de una línea

INTRODUCCIÓN
├─ Contexto y motivación
├─ Pregunta de investigación
└─ Scope

METODOLOGÍA
├─ Ecuación de búsqueda
├─ Criterios PRISMA (en una frase)
├─ Tamaño final: X papers, años A–B
└─ Redes construidas (acoplamiento, co-citación, co-autoría)

MAPEO DEL CAMPO
├─ Tabla de comunidades (visto en Paso 7)
├─ Figura: red de acoplamiento coloreada
├─ Trabajos seminales por comunidad
└─ Descripción de cada enfoque (prosa)

TENDENCIAS Y EVOLUCIÓN
├─ Trayectoria temporal
├─ Shift de enfoques (cuál sube, cuál baja)
├─ Emergentes (keywords nuevas, comunidades nuevas)
└─ Actores clave (top autores, instituciones)

TENSIONES Y DEBATES
├─ Matriz: Enfoque A vs. Enfoque B, qué diferencia
├─ Dónde se superponen, dónde divergen
├─ Huecos de investigación
└─ Preguntas abiertas

CONCLUSIONES
├─ Síntesis de hallazgos
├─ Implicaciones para investigación futura
└─ Recomendaciones

APÉNDICES
├─ Tabla: todos los papers (corpus completo)
├─ CSV de papers → comunidad
└─ GraphML (red para abrir en Gephi/Cytoscape)
```

### Herramientas de escritura

- **Google Docs:** Colaboración y comentarios; exportás a .docx después.
- **Markdown + Pandoc:** Máximo control; exportás a PDF/DOCX/HTML.
- **Obsidian:** Integración con Zotero; bueno para notas de investigación.
- **Quarto/Jupyter:** Si querés reproducibilidad y código integrado.

### Tips de redacción

- **Cada comunidad merece un párrafo.** No amontonés.
- **Las figuras llevan leyendas explicativas.** "Red de acoplamiento bibliográfico
  con N nodos (papers), M aristas (referencias compartidas), K comunidades
  (detectadas por Louvain, resolution=1.0). Cada color = una comunidad.
  Los nodos más grandes = papers de mayor grado (más referencias compartidas)."
- **Tensiones no son "problemas abiertos".** Son donde dos enfoques dicen cosas
  diferentes. Ej. "La escuela probabilística prioriza eficiencia computacional,
  mientras que la neuronal prioriza generación de resultados. En corpus multilingües,
  esto afecta cómo se mapean traducciones."

---

## Paso 10 — Versiona tu trabajo

**Entrada:** Reporte, corpus, redes.  
**Salida:** Carpeta reproducible.

### Si usaste Claude web

Descarga:

- `corpus.parquet` — tu semilla guardada (subirla a Claude luego para continuar).
- `*.graphml` — networks para Gephi/Cytoscape.
- `clusters.csv` — papers → comunidad.
- `reporte.docx` o `reporte.md` — tu análisis final.

Guardalos en una carpeta: `sota-[tema]-[fecha]/`

### Si usaste bib2graph localmente

El corpus vive en `.duckdb`; las redes se exportan automáticamente:

```bash
# Exportá todo
b2g export --format graphml
b2g export --format csv

# Versioná
git add .
git commit -m "SOTA: [Tu Tema] — corpus, redes, reporte"
```

---

## Checklist final

- [ ] Pregunta de investigación clara y formulada
- [ ] Ecuación de búsqueda documentada y testeada
- [ ] Corpus de 100–300 papers ACCEPTED (curados por PRISMA)
- [ ] 3 redes construidas y visualizadas
- [ ] Comunidades nombradas, con keywords, seminales y tensiones identificadas
- [ ] Tendencias temporales e influencias (autores, instituciones) documentadas
- [ ] Huecos y fronteras vacías identificados
- [ ] Reporte redactado con estructura clara y figuras con leyendas
- [ ] Artefactos (GraphML, CSV, corpus) guardados y versionados
- [ ] ¿Se puede reproducir desde la ecuación de búsqueda? ✓

---

## Siguientes pasos

- **Análisis más profundo:** Elige una comunidad y haz un sub-SOTA acotado.
- **Integración con tu investigación:** Posicioná tu trabajo en el mapa — ¿dónde
  caés? ¿Dónde resolvés una tensión?
- **Publicación:** Convertí el SOTA en un paper, capítulo de tesis, o entrada de
  blog.

---

## Referencias

- [Guías (how-to)](../guias/index.md) — recetas acotadas que complementan cada
  paso: ecuación, forrajeo, curación PRISMA, lectura de redes y redacción del reporte.
- [Arquitectura de bib2graph](../ARCHITECTURE.md)
- [Referencia del CLI `b2g`](../reference/cli.md)
- [API Python](../reference/python-api.md)
