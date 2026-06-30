---
title: Cómo armar una ecuación de búsqueda que NO trae basura
---

# Cómo armar una ecuación de búsqueda que NO trae basura

Una **ecuación de búsqueda** es cómo le dices a OpenAlex exactamente qué buscar.
Si la haces mal, traes 50.000 papers. Si la haces bien, traes 200 relevantes.

Esta guía es una receta para llegar a una ecuación acotada, testeada, sin ruido.

!!! info "Alcance"
    - Para alguien que tiene una pregunta de investigación clara
    - Toma: 30 minutos de escritura + testing
    - Herramienta: lápiz/papel, OpenAlex (o bib2graph), un agente opcional

---

## La estructura de una ecuación

```
(concepto_A1 OR concepto_A2 OR concepto_A3)
AND (concepto_B1 OR concepto_B2)
AND (concepto_C1 OR concepto_C2)
```

**Cada paréntesis = un concepto central de tu pregunta.**
**Dentro del paréntesis = sinónimos unidos por OR.**
**Entre paréntesis = AND (todos deben estar presentes).**

### Ejemplo real

**Tu pregunta:** "¿Cómo se abordan los problemas de recuperación de información
en contextos multilingües?"

**Desglose en 3 conceptos:**

1. **Concepto A (la tarea):** recuperación de información, IR, search, retrieval
2. **Concepto B (la restricción):** multilingual, cross-lingual, polyglot, language-independent
3. **Concepto C (el tipo de artefacto):** method, approach, framework, system, architecture

**Tu ecuación:**

```
(information retrieval OR IR OR search OR retrieval)
AND (multilingual OR cross-lingual OR language-independent OR polyglot)
AND (method OR approach OR framework OR system)
```

---

## Paso 1 — Identifica 3 conceptos clave

Desde tu pregunta de investigación, extrae **3 dimensiones**:

| Pregunta | Concepto A | Concepto B | Concepto C |
|----------|-----------|-----------|-----------|
| ¿Cómo se abordan problemas de IR en contextos multilingües? | IR/recuperación | Multilingüe | Métodos/enfoques |
| ¿Cuál es el estado del arte en alineación de valores en LLMs? | Alineación/alignment | LLM/lenguaje grande | Enfoques/métodos |
| ¿Qué métodos existen para detección de fake news en redes sociales? | Fake news/desinformación | Redes sociales/social media | Detección/identificación |

**Checklist:**

- [ ] ¿Cada concepto es una dimensión clara de mi pregunta?
- [ ] ¿Están en orden de especificidad (A = más genérico, C = más acotado)?
- [ ] ¿Me falta un cuarto concepto que quite mucho ruido?

---

## Paso 2 — Genera sinónimos para cada concepto

Para cada concepto, escribe **2–4 sinónimos** que un paper podría usar.

### Truco: búsqueda rápida

Abre Google Scholar o bib2graph y busca directamente un término de cada concepto.
Mira los títulos de los primeros 10 papers: ¿qué palabras ves repetidas?

### Ejemplo

**Concepto A (IR):**
- information retrieval ✓
- information seeking ✓
- search ✓
- retrieval ✗ (demasiado genérico, traería biología)

**Concepto B (Multilingüe):**
- multilingual ✓
- cross-lingual ✓
- language-agnostic ✓
- polyglot ✓

**Concepto C (Métodos):**
- method ✓
- approach ✓
- framework ✓
- system ✓
- algorithm ✗ (muy específico, traería solo papers de algoritmos)

---

## Paso 3 — Arma la ecuación

Copia el template:

```
(concepto_A1 OR concepto_A2 OR concepto_A3)
AND (concepto_B1 OR concepto_B2)
AND (concepto_C1 OR concepto_C2)
```

Reemplaza con tus sinónimos:

```
(information retrieval OR information seeking OR search)
AND (multilingual OR cross-lingual)
AND (method OR approach OR framework)
```

---

## Paso 4 — TESTEA (esto es crítico)

**Nunca** lances una ecuación sin testear. Trae 50 papers y revisa los títulos.

### Con bib2graph CLI

```bash
b2g init test-ecuacion
cd test-ecuacion
b2g seed "tu_ecuacion_aqui" --max-results 50
b2g read list | head -20
```

### Con agente

```text
Ejecuta esta ecuación en bib2graph y trae 50 papers.
Muestra los títulos. ¿Todos tienen relación directa con [TU TEMA]?
```

### Revisa los títulos

```
✓ "Multilingual Information Retrieval: A Cross-lingual Approach"
✓ "Polyglot Search Methods for Heterogeneous Document Collections"
✓ "Language-agnostic Retrieval in Multilingual Corpora"

✗ "Semantic Retrieval Algorithms" (no menciona multilingüe)
✗ "Social Media Search Optimization" (no es recuperación de info)
```

---

## Paso 5 — Ajusta según el ruido

### Si trae MUY POCO (<50 papers)

**Abre la ecuación:**

- Quita un `AND` o reemplázalo por `OR`.
- Agrega más sinónimos a cada concepto.
- Usa palabras más genéricas.

```
Antes:  (information retrieval) AND (multilingual) AND (method)
Después: (information retrieval OR search) AND (multilingual OR cross-lingual)
         [sacamos el tercer AND]
```

### Si trae MUCHO (>1000 papers)

**Cierra la ecuación:**

- Agrega un cuarto concepto `AND NOT` que excluya ruido.
- Usa más sinónimos específicos.
- Agrega delimitadores temporales o de dominio.

```
Antes:  (information retrieval) AND (multilingual)
Después: (information retrieval) AND (multilingual)
         AND (method OR framework) AND NOT (machine translation)
         [añadimos Concepto C + exclusión]
```

### Si trae RUIDO sistemático

Si ves que muchos papers son sobre "X" pero no te importan, excluye:

```
AND NOT (machine translation OR neural machine translation)
AND NOT (social media OR sentiment analysis)
```

---

## Paso 6 — Documentá tu decisión

**Importante:** guarda tu ecuación final CON comentarios.

```
# Pregunta: ¿Cómo se abordan problemas de IR en contextos multilingües?
# Rango: 2015–2024 (últimos 10 años)
# Objetivo: ~250 papers, sensibilidad alta

# Concepto A: IR (recuperación, búsqueda)
# Concepto B: Multilingüe (cross-lingual, polyglot)
# Concepto C: Métodos/enfoques (no solo algoritmos teóricos)
# Exclusión: Machine translation (tema relacionado pero diferente)

(information retrieval OR information seeking OR search)
AND (multilingual OR cross-lingual OR language-agnostic OR polyglot)
AND (method OR approach OR framework OR system)
AND NOT (machine translation OR neural translation)
```

---

## Checklist final

- [ ] Mi ecuación tiene 3–4 conceptos, cada uno con 2–4 sinónimos
- [ ] Testeé con 50 papers y revisé títulos
- [ ] Entre 100–500 papers traídos (ajusté si estaba fuera de rango)
- [ ] Documenté mis decisiones (para reproducibilidad)
- [ ] ¿Todos los papers traídos son relevantes? (sin ruido sistemático)

---

## Tip: Interactuar con un agente

Si usas Claude, ChatGPT o similar:

```text
Mi pregunta de investigación es:
[TU PREGUNTA]

Propón una ecuación de búsqueda en OpenAlex/bib2graph:
1. Con 3 conceptos claros (sintaxis: (A1 OR A2) AND (B1 OR B2) AND (C1 OR C2))
2. Con sinónimos relevantes
3. Con exclusiones si hay ruido conocido

Luego, dame el comando exacto para testear:
b2g seed "[tu_ecuacion]" --max-results 50
```

El agente genera, tú testeas. Esto es más rápido que hacerlo solo.

---

## Siguiente

Cuando tu ecuación traiga papers relevantes sin ruido:
- [Guía: ¿Expando el corpus? (Forrajeo)](forrajeo.md)
- [Guía: Curación PRISMA paso a paso](curacion-prisma.md)
