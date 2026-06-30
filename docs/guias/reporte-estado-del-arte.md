---
title: Cómo elaborar un reporte de estado del arte
---

# Cómo elaborar un reporte de estado del arte

Esta guía es una receta para construir, analizar y reportar un **estado del arte (SOTA)** riguroso
sobre un tema de investigación, utilizando bib2graph como herramienta central. El resultado es un
documento estructurado con identificación de tensiones, escuelas de pensamiento, huecos de
investigación y una síntesis de tendencias.

Es para alguien que ya sabe qué quiere investigar y busca los pasos concretos; si en cambio
se quiere aprender desde cero, véase el [Tutorial: Tu primera red bibliométrica](../tutoriales/claude-code.md).

!!! info "Scope"
    - Corpus de 200–500 papers (ajustable según el tema).
    - Redes bibliométricas: acoplamiento, co-citación, co-autoría.
    - Análisis de comunidades y tendencias.
    - Tiempo estimado: 4–6 horas (de investigador; el código: 30 min).
    - Salida: reporte .docx/.md con figuras, matriz de tensiones y conclusiones.

!!! warning "Requisitos"
    - **Un flujo de bib2graph** (CLI en máquina local **o** Claude Code con ejecución).
    - **Una pregunta de investigación clara** — no un tema genérico.
    - **Opcional:** API key de OpenAlex (gratuita, para más de ~100 papers).
    - **Herramienta de escritura:** Obsidian, Google Docs, Word o markdown + pandoc.

---

## El flujo en síntesis

```
1. Pregunta → Ecuación de búsqueda (3 conceptos)
2. Siembra (OpenAlex, 200–500 papers)
3. Expansión por citaciones (forrajeo) — opcional, para corpus más denso
4. Curación manual (PRISMA filters, decisiones criterio)
5. Construcción de redes (acoplamiento, co-citación, co-autoría)
6. Lectura de comunidades (nombrado, keywords, tensiones)
7. Análisis de tendencias (temporal, institucional, autores influyentes)
8. Redacción del reporte
```

---

## Paso 1 — Afina tu pregunta de investigación

**Entrada:** Una idea amplia sobre un tema.  
**Salida:** Una pregunta de investigación clara y acotada.

Una buena pregunta de investigación tiene esta forma:

> ¿Cómo se ha abordado [**problema específico**] en el contexto de [**dominio**],
> entre [**rango temporal**]? ¿Cuáles son los enfoques dominantes, sus tensiones
> y los huecos sin explorar?

### Ejemplo

❌ *"Quiero estudiar inteligencia artificial."*  
✅ *"¿Cómo se abordan los problemas de alineación de valores en modelos de lenguaje
grandes, y cuáles son las tensiones entre eficiencia computacional y robustez ética?"*

### Preguntas de refinamiento

1. **¿Es específica?** ¿Puedo traducirla a 3–5 palabras clave que filtren el ruido?
2. **¿Es temporal?** ¿Hay un rango de años que tenga sentido? (últimos 5–10 años suele ser lo adecuado para un SOTA).
3. **¿Es acotada?** ¿Espero 50 papers, 500 o 5000? (Ajusta la precisión de la ecuación).

---

## Paso 2 — Elabora una ecuación de búsqueda

**Entrada:** Pregunta de investigación.  
**Salida:** Ecuación booleana con ~3 conceptos y sinónimos controlados.

Una ecuación de búsqueda tiene esta estructura:

```
(término_A1 OR término_A2 OR término_A3)
AND (término_B1 OR término_B2)
AND (término_C1 OR término_C2)
```

Cada paréntesis es un **concepto**; los `OR` capturan sinónimos; los `AND` son obligatorios juntos.

### Ejemplo

Pregunta: *"¿Cómo se diseñan sistemas de recuperación de información en contextos multilingües?"*

```
(information retrieval OR IR OR search engines)
AND (multilingual OR cross-lingual OR language-agnostic)
AND (design OR architecture OR framework OR system)
```

### Consejos

- **Evita genéricos.** "machine learning" sola atrapa decenas de miles de papers.
- **Sé específico en el cuarto concepto si hace falta.** Agrega un delimitador:
  `AND (neural OR deep learning)` para descartar SOTA pre-2012.
- **Testa la ecuación.** Corre una búsqueda rápida de 50 papers y revisa los títulos.
  Si ves ruido sistemático, ajusta.

---

## Paso 3 — Siembra el corpus desde OpenAlex

**Entrada:** Ecuación de búsqueda, rango de años.  
**Salida:** Corpus inicial de ~200–300 papers.

Usa bib2graph (CLI o Claude) para traer papers desde OpenAlex.

### Con CLI local

```bash
b2g init ./mi-sota
cd mi-sota
b2g seed "tu_ecuacion_aqui" --min-year 2015
```

Verificá el corpus:

```bash
b2g read list --query "your_keywords"
b2g read stats --group-by year
```

### Con Claude Code

Envía un prompt como:

```text
Sembrá un corpus desde OpenAlex usando esta ecuación:
(información retrieval OR IR)
AND (multilingüe OR cross-lingual)
Traé hasta 250 papers desde 2015.
Mostrame un resumen: cuántos papers, rango de años, top 5 autores por citaciones.
```

### Checklist

- [ ] ¿El corpus tiene papers desde diferentes años (no es monocromático)?
- [ ] ¿Reconozco algunos autores o papeles influyentes en el rango?
- [ ] ¿El tamaño es manejable (200–500, no 5000)?

Si el corpus es muy pequeño, abre la ecuación (menos `AND`, más `OR`).  
Si es muy grande, ciérrala (agrega un concepto específico más).

---

## Paso 4 — Expande por citaciones (opcional pero recomendado)

**Entrada:** Corpus de siembra.  
**Salida:** Corpus expandido (+20–50% papers nuevos) con mayor densidad de referencias.

El forrajeo (o "chaining") busca papers no encontrados en la búsqueda inicial pero
citados por los que sí están. Aumenta la sensibilidad sin ruido.

### Con CLI

```bash
b2g chain --depth 1 --limit 100
```

### Con Claude

```text
Expandí el corpus usando forrajeo de citaciones: seguí una capa de referencias
de los papers ya en el corpus (backward chaining) y límítate a 100 papeles nuevos.
Mostrame los papers nuevos y el gráfico de crecimiento por año.
```

### Cuándo hacer esto

- ✅ Si buscás sensibilidad alta (no querés perderte trabajos clave).
- ✅ Si el tema es muy específico (forrajeo agrega relevancia).
- ❌ Si el corpus ya es grande (>500) — aumenta significativamente el tamaño.
- ❌ Si es la primera vez: puedes hacer esto después de leer la red inicial.

---

## Paso 5 — Curá el corpus (filtros PRISMA)

**Entrada:** Corpus (inicial o expandido).  
**Salida:** Corpus curado, con decisiones explícitas y versionables.

La curación es manual y criterial. Trae estructura (PRISMA) a lo que normalmente es
un basurero de decisiones ad-hoc.

### Flujo PRISMA simplificado

```
IDENTIFICACIÓN
├─ Duplicados y retractaciones: RECHAZAR
└─ Idioma no inglés (si procede): RECHAZAR

CRIBADO
├─ Título fuera de scope: RECHAZAR
└─ Resumen no relevante: RECHAZAR

ELEGIBILIDAD
├─ Texto completo inaccesible: CANDIDATO (no rechazar, quizá disponible más tarde)
└─ Métodos/resultados vagos: RECHAZAR o CANDIDATO

INCLUSIÓN
├─ Relevancia alta: ACEPTAR
└─ Relevancia media pero útil para tensiones: ACEPTAR
```

### Con CLI

```bash
b2g curate dump --scope all > curate.csv
# Editá curate.csv en Excel/Sheets: status = 'ACCEPTED' / 'REJECTED' / 'CANDIDATE'
b2g curate apply curate.csv
```

### Con Claude

```text
Hacé una curación manual del corpus usando criterios PRISMA:
1. Rechazá duplicados y papers sin resumen.
2. Rechazá papers cuyo título no tenga relación directa con [TU TEMA].
3. Marcá como CANDIDATO los papers con acceso restringido al texto completo.
4. Aceptá papers con relevancia alta o media que aporten tensiones metodológicas.

Mostrame un resumen curado: accepted/rejected/candidate counts, y listame los
papers rechazados con razón.
```

### Checklist

- [ ] ¿Documenté mis criterios de aceptación/rechazo?
- [ ] ¿Quedó un corpus de 100–300 ACCEPTED papers?
- [ ] ¿Revisé una muestra de rechazados para asegurarme de que no falta algo obvio?

---

## Paso 6 — Construí las redes bibliométricas

**Entrada:** Corpus curado (ACCEPTED papers).  
**Salida:** 3 redes + análisis de comunidades.

bib2graph proyecta el corpus a tres redes:
1. **Acoplamiento bibliográfico:** Papers que citan las mismas referencias.
2. **Co-citación:** Papers citados juntos (identifican "clusters de influencia").
3. **Co-autoría:** Relaciones entre investigadores.

### Con CLI

```bash
# Especificar via YAML es lo robusto
cat > networks.yaml << 'EOF'
networks:
  - kind: bibliographic_coupling
    clustering: louvain
    resolution: 1.0
    
  - kind: co_citation
    clustering: louvain
    resolution: 1.0
    
  - kind: co_authorship
    clustering: louvain
    resolution: 1.0
EOF

b2g build --spec networks.yaml
```

Exportá artefactos:

```bash
b2g export --format graphml
b2g read top --kind bibliographic_coupling --top 20
```

### Con Claude

```text
Construí 3 redes del corpus curado:
1. Acoplamiento bibliográfico, comunidades con Louvain.
2. Co-citación, comunidades con Louvain.
3. Co-autoría, comunidades con Louvain.

Para cada red mostrame:
- Visualización coloreada por comunidad.
- Métricas: # nodos, # aristas, # comunidades.
- Top 3 papers más centrales (mayor grado).
```

### Qué esperar

- **Acoplamiento:** es la red "primaria" — más densa, más comunidades. Es donde ves sub-temas.
- **Co-citación:** es la red "influyentes" — documenta qué papers/autores actúan como referencias canónicas.
- **Co-autoría:** a menudo es más dispersa; útil para ver colegios invisibles.

---

## Paso 7 — Leé y nombra las comunidades

**Entrada:** Redes + corpus curado.  
**Salida:** Descripción de cada comunidad, sus keywords, enfoque y tensiones.

Para cada comunidad en la red de acoplamiento (la principal):

1. **Extraé keywords dominantes** de los papers en la comunidad.
2. **Nombra la comunidad** con un sustantivo que capture el enfoque (ej. "Recuperación jerárquica", "Enfoque probabilístico").
3. **Identifica papers seminales** (máximo grado dentro de la comunidad).
4. **Identifica tensiones** (dónde difiere esta comunidad de las demás).

### Con Claude

```text
Para la red de acoplamiento, nombra cada comunidad según sus keywords y
el contenido de sus papers.

Para cada comunidad:
1. Nombre (1–3 palabras).
2. Keywords principales (5–7).
3. Top 2 papers (mayor grado).
4. Descripción breve (2–3 frases) del enfoque.
5. ¿Qué tensión metodológica los diferencia de otras comunidades?
```

### Ejemplo de salida

| Comunidad | Enfoque | Keywords | Seminales | Tensión |
|-----------|---------|----------|-----------|---------|
| Enfoque estadístico | Probabilidad, modelos generativos | language models, HMM, smoothing | [2010], [2008] | Eficiencia vs. cobertura |
| Enfoque neuronal | Deep learning, word embeddings | neural networks, embeddings, LSTM | [2016], [2013] | Interpretabilidad vs. performance |

---

## Paso 8 — Analiza tendencias e influencias

**Entrada:** Redes, comunidades nombradas.  
**Salida:** Observaciones sobre evolución temporal, actores influyentes, huecos.

### Preguntas a responder

1. **¿Cómo evolucionó el campo?**  
   Gráficos: # papers por año, shift de keywords a lo largo del tiempo.

2. **¿Quiénes son los autores/papeles más influyentes?**  
   Listá por centralidad en la red de co-citación.

3. **¿Hay huecos evidentes?**  
   ¿Qué combinaciones de keywords no aparecen? ¿Qué fronteras entre comunidades están vacías?

4. **¿Qué instituciones lideren la investigación?**  
   Co-autoría: qué universidades/laboratorios coaparecer más.

### Con Claude

```text
Analizá tendencias en el corpus:
1. Gráficos: # papers/año, distribución por comunidad año a año.
2. Autores más citados (top 10 por centralidad en co-citación).
3. Instituciones más colaborativas (co-autoría).
4. Identificá 3–5 huecos o fronteras sin explorar entre comunidades.
5. ¿Qué palabras clave son emergentes (crecimiento exponencial últimos 3 años)?
```

---

## Paso 9 — Redactá el reporte

**Entrada:** Análisis anterior, comunidades nombradas, tendencias.  
**Salida:** Documento estructurado (.md, .docx, .pdf).

### Estructura recomendada

```
1. Resumen ejecutivo
   - Pregunta de investigación
   - Hallazgos principales (2–3 frases)
   - Conclusión de una línea

2. Introducción
   - Contexto y motivación
   - Pregunta de investigación
   - Scope y exclusiones

3. Metodología
   - Ecuación de búsqueda
   - Criterios PRISMA
   - Tamaño final del corpus
   - Redes construidas

4. Mapeo del campo
   - Descripción de cada comunidad (tabla + prosa)
   - Figuras: red coloreada, gráficos temporales
   - Actores clave y trabajos seminales

5. Tendencias y evolución
   - Trayectoria del campo (temporal)
   - Shift de enfoques
   - Emergentes

6. Tensiones y debates abiertos
   - Matriz: enfoque A vs. enfoque B, qué diferencia, cuál prevalece
   - Huecos de investigación
   - Preguntas abiertas

7. Conclusiones y prospectiva
   - Síntesis de hallazgos
   - Implicaciones para investigación futura
   - Recomendaciones

8. Apéndices
   - CSV de corpus (metadatos)
   - GraphML de redes (para Gephi/Cytoscape)
   - Lista completa de referencias
```

### Herramientas recomendadas

- **Obsidian + Zotero:** flujo de investigación integrado.
- **Google Docs:** colaboración y comentarios; convertís a .docx después.
- **Markdown + Pandoc:** máxima control; exportás a PDF/DOCX con cite.
- **Quarto/Jupyter:** si querés reproducibilidad y código integrado.

### Checklist antes de publicar

- [ ] ¿Cada comunidad tiene descripción, keywords y seminales claramente nombrados?
- [ ] ¿Las figuras tienen leyendas que expliquen qué se ve?
- [ ] ¿Se documentó la ecuación de búsqueda y criterios PRISMA?
- [ ] ¿Se mencionan huecos y se invita a investigación futura?
- [ ] ¿Alguien externo leyó el reporte y entendió sin preguntar?

---

## Paso 10 — Guardá y versioná

**Entrada:** Reporte final, corpus, redes.  
**Salida:** Carpeta reproducible.

Si usaste bib2graph CLI localmente:

```bash
# El corpus vive en .duckdb; las redes en outputs/
# Exportá todo:
b2g export --format graphml
b2g export --format csv

# Guardá el reporte y su metadata:
tree . > structure.txt
git add .
git commit -m "SOTA: [Tu Tema] — corpus, redes, reporte"
```

Si usaste Claude web, **descargá:**

- `corpus.parquet` — tu semilla para la próxima sesión.
- `*.graphml` — networks para Gephi.
- `clusters.csv` — papers → comunidad.
- Reporte final (.docx/.pdf).

Guardalos en una carpeta nominada `sota-[tema]-[fecha]` en tu repositorio de investigación.

---

## Checklist final

- [ ] Pregunta de investigación clara
- [ ] Ecuación de búsqueda documentada
- [ ] Corpus de 100–300 papers ACCEPTED (curados)
- [ ] 3 redes construidas y visualizadas
- [ ] Comunidades nombradas y descritas
- [ ] Tendencias temporales e influyentes identificadas
- [ ] Reporte redactado con estructura clara
- [ ] Artefactos (GraphML, CSV, corpus) guardados y versionados
- [ ] ¿Se puede reproducir el análisis desde la ecuación de búsqueda?

---

## Siguientes pasos

- **Análisis más profundo:** Ahora que mapeaste el campo, profundizá en una
  comunidad; usa bib2graph para iterar (nuevo corpus sobre esa comunidad,
  nuevas redes, nuevo SOTA acotado).
  
- **Integración con tu investigación:** Usa el mapa como **diagrama de
  posicionamiento** para tu propio trabajo — ¿dónde caés? ¿dónde hay tensión
  que tu trabajo resuelve?

- **Tutorial:** Si querés aprender el CLI o la librería de Python a fondo,
  véase el [Quickstart](../getting-started/quickstart.md) y la [Referencia](../reference/cli.md).

- **Comunidad:** Compartí tu SOTA en el repo (crea un issue); feedback de otros
  investigadores enriquece el análisis.

---

## Referencias internas

- [Arquitectura de bib2graph](../ARCHITECTURE.md)
- [API Python](../reference/python-api.md)
- [CLI `b2g`](../reference/cli.md)
- [ADR sobre SOTA y investigación](../decisiones/) — cómo bib2graph encaja en el ciclo de investigación.
