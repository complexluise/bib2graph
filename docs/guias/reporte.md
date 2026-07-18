---
title: Del corpus al reporte — Estructura y redacción
---

# Del corpus al reporte — De datos a prosa

Tienes redes, comunidades, papers clave. Ahora: cómo convertir eso en un **reporte
coherente** que otros lean de principio a fin.

Esta guía: estructura, qué escribir en cada sección, y tips de redacción.

!!! info "Alcance"
    - Para alguien que ya leyó las redes y tienes anotaciones
    - Toma: 3–4 horas de redacción
    - Herramienta: Google Docs, Word, Obsidian, o Markdown + Pandoc
    - Salida: Documento de 8–15 páginas, legible

---

## La estructura (template)

```
1. RESUMEN EJECUTIVO (1 página)
2. INTRODUCCIÓN (1–2 páginas)
3. METODOLOGÍA (1 página)
4. MAPEO DEL CAMPO (3–5 páginas)
5. TENDENCIAS E INFLUENCIA (2–3 páginas)
6. TENSIONES Y DEBATES (2–3 páginas)
7. CONCLUSIONES (1–2 páginas)
8. REFERENCIAS (autogenerado)

Total: 12–20 páginas
```

---

## 1. RESUMEN EJECUTIVO

**Largo:** 1 página. **Escritura:** densísima, sin fluff.

**Qué incluir:**

- Pregunta de investigación (1 frase)
- Metodología en 1 línea: "SOTA de X papers, 3 redes, PRISMA curation"
- 3 hallazgos principales (bullet points)
- Conclusión de 1 frase

### Ejemplo

> **Pregunta:** ¿Cuál es el estado del arte en recuperación de información multilingüe?
>
> **Método:** Corpus de 250 papers (2015–2024) desde OpenAlex, curado con PRISMA, analizado con 3 redes bibliométricas.
>
> **Hallazgos:**
> - El campo tiene 3 enfoques dominantes: estadístico, vectorial, neuronal. Los tres coexisten sin consenso.
> - Papers influentes (clásicos) son del 2008–2013; nuevos líderes emergentes post-2019 con enfoque neuronal.
> - Hay un hueco: recuperación multilingüe en contextos de baja disponibilidad de datos.
>
> **Conclusión:** El campo está en transición de enfoques estadísticos a neurales, pero cada enfoque tiene ventajas sin resolver.

---

## 2. INTRODUCCIÓN

**Largo:** 1–2 páginas. **Propósito:** planta el contexto y la pregunta.

**Estructura:**

1. **Hook:** Por qué el tema importa (1–2 frases)
2. **Contexto:** Dónde cae este tema en la disciplina (3–4 frases)
3. **Pregunta de investigación:** Explicitada (1 frase)
4. **Scope:** Qué cubre este SOTA y qué no (1 frase)

### Ejemplo

> **Hook:** La recuperación de información (IR) es fundamental para cualquier herramienta de búsqueda, pero el contexto multilingüe agrega complejidad: vocabularios diferentes, grammatical structures, y semánticas culturales.
>
> **Contexto:** Históricamente, IR se basaba en matching estadístico (TF-IDF). Los últimos 10 años vieron un giro hacia embeddings y modelos neurales. En contextos multilingües, esto es aún más reciente.
>
> **Pregunta:** ¿Cuáles son los enfoques dominantes en IR multilingüe hoy, cuáles son sus tensiones, y qué queda sin explorar?
>
> **Scope:** Analizamos papers 2015–2024 en ingles; enfoque: métodos y frameworks (no aplicaciones específicas).

---

## 3. METODOLOGÍA

**Largo:** 1 página. **Propósito:** reproducibilidad.

**Incluir:**

- Ecuación de búsqueda (cópiala)
- Rango de años y fuente (OpenAlex)
- Criterios PRISMA (en una frase por fase)
- Corpus final: # papers, rango años
- Redes construidas (acoplamiento, co-citación, co-autoría)
- Tool: bib2graph

### Ejemplo

> **Búsqueda:** "(information retrieval OR search OR IR) AND (multilingual OR cross-lingual) AND (method OR approach OR framework)" en OpenAlex, años 2015–2024.
>
> **Curation:** PRISMA de 4 fases.
> - Identificación: duplicados, retractados, no-inglés → rejected
> - Cribado: título + abstract relevancia → rejected
> - Elegibilidad: texto completo accesible → candidate
> - Inclusión: relevancia alta → accepted
>
> **Corpus:** 315 papers buscados → 250 tras curación PRISMA → 245 aceptados + 5 candidatos.
> **Años:** 2015–2024 (con 3 foundational 2008–2010).
>
> **Redes:** Acoplamiento bibliográfico (comunidades), co-citación (influentes), co-autoría (colaboraciones).
> **Herramienta:** bib2graph (indicá la versión con `b2g --version`) + Louvain clustering (resolution=1.0).

---

## 4. MAPEO DEL CAMPO

**Largo:** 3–5 páginas. **Propósito:** mostrar la estructura del campo.

**Estructura:**

1. **Tabla de comunidades** (1 página)
   - Comunidad | Keywords | Top papers | Descripción

2. **Descripción de cada comunidad** (1–2 párrafos por comunidad, máx 3–4 comunidades)

3. **Figura: Red coloreada** (inserta el PNG de la red de acoplamiento)

### Ejemplo — Tabla

| Comunidad | Keywords | Top Papers | Enfoque |
|-----------|----------|-----------|---------|
| **Estadístico** | TF-IDF, probabilistic, language model | [Smith 2008], [Brown 2010] | Ranking por frecuencia de términos |
| **Vectorial** | embedding, word2vec, LSA, similarity | [Mikolov 2013], [Pennington 2014] | Espacios semánticos densos |
| **Neuronal** | neural network, transformer, BERT, attention | [Vaswani 2017], [Devlin 2019] | Aprendizaje de representaciones |

### Ejemplo — Prosa

> **Enfoque Estadístico:** 85 papers, principalmente 2015–2018.
> Usan modelos probabilísticos (HMM, LM) y ranking por frecuencia (TF-IDF).
> Ventaja: eficiencia, interpretabilidad. Desventaja: no captura semántica.
> Papers influyentes: Smith et al (2008), Brown et al (2010).
>
> **Enfoque Vectorial:** 92 papers, principalmente 2013–2020.
> Generan embeddings densos (word2vec, FastText) y miden similaridad coseno.
> Ventaja: captura semántica, escalable. Desventaja: computacionalmente costoso, menos interpretable.
> Transición: muchos papers de 2015–2017 vuelven a embeddings, desafiando TF-IDF.
>
> **Enfoque Neuronal:** 68 papers, principalmente 2017–2024.
> Transformers (BERT, mBERT para multilingüe). Ventaja: SOA performance. Desventaja: black box, caro.
> Emergente: multilingüe especializado (XLM-R).
>
> **Dinámicas:** Los 3 enfoques coexisten sin desplazamiento total. Hay papers híbridos (probabilístico + neural).
> Frontera sin explorar: eficiencia en contextos de baja disponibilidad de datos.

### Qué evitar

❌ "Enfoque A es mejor que enfoque B."  
→ Los 3 conviven, cada uno tiene trade-offs.

✅ "Enfoque A prioriza X, enfoque B prioriza Y. Entran en tensión sobre Z."

---

## 5. TENDENCIAS E INFLUENCIA

**Largo:** 2–3 páginas. **Propósito:** mostrar evolución temporal y actores clave.

**Incluir:**

1. **Gráfico temporal:** # papers/año por comunidad
2. **Shift de enfoque:** cuál crecía, cuál decrecía
3. **Papers y autores influyentes:** top 10 por co-citación
4. **Labs líderes:** qué universidades/labs dominan (co-autoría)
5. **Emergentes:** keywords o autores con crecimiento exponencial últimos 3 años

### Ejemplo

> **Evolución temporal:** 2015–2017 fue era "vectorial" (92 papers, 60% de nuevos). 2018–2020, equilibrio.
> 2021–2024, giro a neuronal (68% nuevos). Estadístico declina (5% nuevos en 2024).
>
> **Influyentes globales:** Smith et al (2008) sigue siendo más citado, pero Vaswani et al (2017) "Attention is All You Need"
> alcanzó en 2022. Post-2020, mBERT (Google) es hub de co-citación en multilingüe.
>
> **Labs líderes:** Stanford (25 papers), Google Brain (18), FAIR (15).
> Colaboración: Google + Stanford (12 co-author papers). FAIR aislado (pocas colaboraciones externas).
>
> **Emergentes:** Keyword "low-resource" crece 3x desde 2020. Autores nuevos en este sub-tema.
> Nuevas partnerships: Google + universidades en Asia (multilingüe sobre lenguas de baja disponibilidad).

### Cómo pedírselo a tu asistente

Si estás operando bib2graph vía un [asistente de IA](../reference/glosario.md#asistente-de-ia),
no necesitas calcular esto a mano. Pídeselo directamente:

```text
Muestra:
- Gráfico de # papers/año en el corpus, y cómo cambiaron las comunidades
  (% de papers) año a año. ¿Hay una comunidad que crecía y ahora decrece?
  ¿Hay una emergente (crecimiento exponencial últimos 3 años)?

Top 10 autores por:
- Cantidad de papers (productividad)
- Grado en la red de co-citación (influencia)
- Betweenness (actúan de "puente" entre comunidades)

Mirando las 3 redes, identifica:
- Comunidades o autores que no se conectan entre sí (fronteras vacías)
- Combinaciones de keywords que NO aparecen (gaps)

Co-autoría: top 10 instituciones por cantidad de papers y colaboraciones externas.
```

---

## 6. TENSIONES Y DEBATES

**Largo:** 2–3 páginas. **Propósito:** tensiones = investigación activa.

**Qué es una tensión:** Dos enfoques dicen cosas opuestas o incompatibles.

**Estructura:** Para cada tensión:

1. **Nombre** (Eficiencia vs. Precisión)
2. **Quién está de cada lado** (Enfoque A vs. Enfoque B)
3. **Por qué divergen** (Presupuestos, objetivos, contexto)
4. **Ejemplo concreto** (Paper A dice X, Paper B dice ¬X)
5. **Estado actual** (Se resolvió? Abierto? Evolucionó?)

### Ejemplo

> **Tensión 1: Interpretabilidad vs. Performance**
>
> - **Lado A (Estadístico):** Un modelo entendible es mejor. TF-IDF, si devuelves top 5, puedo explicar por qué.
> - **Lado B (Neuronal):** Performance > interpretabilidad. Si BERT devuelve 99% accuracy, ¿importa que sea black box?
> - **Ejemplo:** Smith (2010) "Statistical IR is superior for transparent systems". Devlin (2019) "BERT outperforms all baselines", no explora interpretabilidad.
> - **Estado:** Abierto. Hay intentos de interpretable neural (attention visualization), pero la mayoría ignora esto.
>
> **Tensión 2: Escalabilidad vs. Contexto**
>
> - **Lado A:** Escalable a millones de documentos (vectorial, estadístico).
> - **Lado B:** Contexto fino, semantic precision (neuronal, aunque lento).
> - **Ejemplo:** Google's neural retrieval es 10x más lento que TF-IDF, por eso siguen usando TF-IDF en producción.
> - **Estado:** En evolución. Recientes (2023–2024) buscan solución: retrieval neuronal comprimido (destilación).

---

## 7. CONCLUSIONES

**Largo:** 1–2 páginas. **Propósito:** síntesis + implicaciones.

**Estructura:**

1. **Síntesis de hallazgos:** qué vimos en el mapa
2. **Implicaciones:** qué significa para investigación futura
3. **Huecos:** qué no existe, qué falta
4. **Recomendación:** si fueras investigador, dónde irías

### Ejemplo

> **Síntesis:** El campo de IR multilingüe está en transición. Tres enfoques coexisten: estadístico (maduro, eficiente, interpretable),
> vectorial (en declive, pero servicios web lo usan), neuronal (ascendente, SOA, caro). No hay consenso de paradigma.
>
> **Para futura investigación:** Hay dos caminos abiertos.
> 1. Resolver Interpretabilidad en modelos neurales multilingües.
> 2. Explorar IR eficiente en lenguas de baja disponibilidad (hueco claro).
>
> **Huecos principales:**
> - No hay estudios comparativos rigurosos de los 3 enfoques en el mismo benchmark multilingüe.
> - Contextos code-switching (mezcla de lenguas) es casi inexplorado.
> - Retrieval offline/sin internet: abandonado por la industria.
>
> **Recomendación:** Si entrás al campo hoy, sugiero: caracterizar la brecha de eficiencia en multilingüe (hay plata aquí),
> o resolver low-resource (hay impacto social + papers de alto valor).

---

## Tips de redacción

### 1. No expliques QUÉ, explica QUÉ SIGNIFICA

❌ "Paper A propone un método estadístico usando TF-IDF para IR. Paper B propone redes neurales."

✅ "Paper A (estadístico) y Paper B (neural) entran en tensión sobre trade-off entre eficiencia e inteligencia. A es rápido, B es inteligente."

### 2. Las figuras NO hablan solas

Cada figura necesita:
- Título claro
- Leyenda que explique qué ves
- 2–3 frases de texto que señalen qué observar

❌ Figura: Red coloreada (sin leyenda)

✅ Figura 1: Red de acoplamiento bibliográfico. Nodos = papers. Líneas = referencias compartidas (acoplamiento). Colores = comunidades (Louvain). Observar: la comunidad azul (estadístico) es densa pero aislada; la roja (neuronal) es más dispersa pero conecta todas las demás.

### 3. Transiciones entre secciones

Conectá secciones:

```
[...fin de Metodología]
"Con este corpus de 245 papers, ahora examinamos la estructura del campo.

[Inicio de Mapeo del Campo]
El análisis de acoplamiento bibliográfico revela 3 comunidades principales..."
```

### 4. Cita los papers

Cuando menciones una idea, cita: (Smith et al, 2008). Esto hace el texto reproducible.

### 5. Redacta para que entienda alguien fuera del tema

No asumas jerga. Explica conceptos:

❌ "TF-IDF es el baseline obvio."

✅ "TF-IDF (Term Frequency-Inverse Document Frequency) es un scoring que ranquea documentos por términos raros en el corpus (raro = más informativo). Es eficiente pero no entiende significado."

---

## Herramientas de escritura

- **Google Docs:** Colaboración, comentarios, fácil de compartir. Exportá a DOCX.
- **Markdown + Pandoc:** Control total, versionable con git, exportá a PDF/DOCX.
- **Obsidian:** Bueno para notas conectadas, integra con Zotero.
- **Word:** Si necesitás templates corporativos.

---

## Checklist de escritura

- [ ] Resumen ejecutivo: 3 hallazgos clave en 5 frases
- [ ] Introducción: pregunta clara, scope explícito
- [ ] Metodología: reproducible (ecuación, criterios, final corpus)
- [ ] Mapeo: tabla + prosa, cada comunidad explicada
- [ ] Tendencias: gráfico temporal + top papers/labs
- [ ] Tensiones: 3–5 tensiones principales con ejemplos
- [ ] Conclusiones: huecos identificados, recomendaciones futuras
- [ ] Figuras: todas con leyendas claras + 2–3 frases de interpretación
- [ ] Redacción: sin jerga sin explicar, citas presentes, transiciones claras

---

## Guarda y versiona tus artefactos

**Si trabajaste con un asistente de IA:** su entorno de ejecución es efímero.
Antes de cerrar la conversación, descarga `corpus.parquet` (o el `.duckdb`),
los `.graphml` de cada red, el `clusters.csv` (papers → comunidad) y tu
reporte final. Guárdalos juntos en una carpeta: `sota-[tema]-[fecha]/`.

**Si trabajaste con bib2graph localmente:** exporta y versiona con git:

```bash
b2g export --format graphml
b2g export --format csv

git add .
git commit -m "SOTA: [tu tema] — corpus, redes, reporte"
```

Esto es lo que hace tu SOTA **reproducible**: alguien (incluida tu versión
futura) puede volver a la misma ecuación y llegar a las mismas redes.

---

## Siguiente

Cuando termines el reporte:
- Comparte para feedback (peer-review light)
- Itera: ¿hay tensiones sin explicar? ¿hay huecos claros?
- Publica o presentá (conferencia, seminario, blog)
