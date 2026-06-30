---
title: Curación PRISMA paso a paso
---

# Curación PRISMA paso a paso

La **curación** es donde TÚ decides qué papers quedan. PRISMA es una estructura
que ordena esa decisión en 4 fases, sin arbitrariedad.

Esta guía: cómo aplicar PRISMA con bib2graph.

!!! info "Alcance"
    - Para alguien que tiene un corpus de siembra/forrajeo (~200–500 papers)
    - Toma: 2–3 horas (depende del corpus)
    - Herramienta: bib2graph CLI, Excel, Google Sheets
    - Salida: corpus curado (100–300 ACCEPTED papers)

---

## Las 4 fases PRISMA

```
IDENTIFICACIÓN
├─ ¿Duplicado?
├─ ¿Retractado?
└─ ¿Idioma?

CRIBADO (Screening)
├─ Título relevante?
└─ Resumen toca el tema?

ELEGIBILIDAD
├─ ¿Acceso al texto completo?
└─ ¿Métodos/resultados claros?

INCLUSIÓN (Decisión final)
├─ ¿Relevancia alta?
└─ ¿Contribuye al SOTA?
```

Cada fase es un filtro. Al final: papers **ACCEPTED** (sí, quedan),
**REJECTED** (no, descartar), **CANDIDATE** (quizá más tarde).

---

## Paso 1 — Extrae el corpus a CSV

### Con CLI

```bash
b2g curate dump --scope all > curate.csv
```

Abre el CSV en Excel o Google Sheets. Columnas:

| id | title | authors | year | abstract | status |
|----|-------|---------|------|----------|--------|
| 1 | "Multilingual..." | Smith et al | 2020 | "This paper..." | PENDING |

Nota: el CSV tiene campos adicionales (DOI, source_id, etc.), pero esos 6 te interesan.

### Con agente

```text
Exportá mi corpus a CSV con:
- id
- title
- authors
- year
- abstract
- Una columna "status" donde pueda escribir ACCEPTED/REJECTED/CANDIDATE

Dame el CSV para descargarlo.
```

---

## Paso 2 — Criterios explícitos por fase

Antes de curar, **documentá tus criterios**. Esto es clave para reproducibilidad.

### IDENTIFICACIÓN

| Criterio | Acción |
|----------|--------|
| ¿Título exactamente idéntico a otro? | REJECTED (duplicado) |
| ¿DOI retractado según Retraction Watch? | REJECTED (retractado) |
| ¿Idioma ≠ inglés? | REJECTED (si tu scope es inglés) |

### CRIBADO

| Criterio | Acción |
|----------|--------|
| Título no menciona ningún término clave de tu pregunta | REJECTED |
| Resumen sugiere que toca el tema pero tangencialmente | REJECTED |
| Título + resumen = claramente relevante | ACEPTA para elegibilidad |

### ELEGIBILIDAD

| Criterio | Acción |
|----------|--------|
| Texto completo no disponible (paywall, pdf no existe) | CANDIDATE (revisás después) |
| Métodos o resultados vagos/especulativos | CANDIDATE (quizá sirva) |
| Métodos/resultados claros y reproducibles | ACEPTA para inclusión |

### INCLUSIÓN

| Criterio | Acción |
|----------|--------|
| Relevancia alta + aporta al SOTA | ACCEPTED |
| Relevancia media pero aporta una perspectiva diferente | ACCEPTED |
| Baja relevancia + poco aporte | REJECTED |

---

## Paso 3 — Cura el CSV

### Estrategia: **dos pasadas**

**Pasada 1 (rápida):** Título + abstract, sin pensar mucho. REJECTED o ACCEPTED.  
**Pasada 2 (lenta):** Los PENDING. Aquí pensás, decidís CANDIDATE o ACCEPTED.

### Proceso manual

Abre el CSV en Excel/Sheets. Para cada fila:

1. Lee **título**
2. Lee **abstract** (si hay)
3. Aplica **criterios de tu fase actual** (IDENTIFICACIÓN → CRIBADO → ELEGIBILIDAD → INCLUSIÓN)
4. Escribe en columna `status`: `ACCEPTED`, `REJECTED`, o `CANDIDATE`

### Con agente (semi-automático)

```text
Ayudame a curar este corpus. Para cada paper, dame un recomendación:

Criterios:
- REJECTED si: título fuera de [TU TEMA], no hay métodos claros, es un duplicado
- CANDIDATE si: texto completo no disponible, relevancia media
- ACCEPTED si: relevancia alta, aporta al SOTA

Paper 1:
- Título: "Multilingual Search in Social Networks"
- Año: 2015
- Abstract: "We propose a method..."
- Tu recomendación: ?

[Y así con los demás...]
```

El agente propone, tú tomas la decisión final.

---

## Paso 4 — Aplica en bib2graph

Cuando termines el CSV con tus decisiones:

```bash
b2g curate apply curate.csv
```

bib2graph actualiza el corpus: ACCEPTED quedan en el corpus, REJECTED se marcan,
CANDIDATE quedan pero como "en revisión".

### Verificación

```bash
b2g read stats
```

Debería mostrar algo así:

```
Status breakdown:
- ACCEPTED: 245 papers (main corpus)
- REJECTED: 95 papers
- CANDIDATE: 30 papers
```

---

## Paso 5 — Revisa outliers

Después de curar, revisa:

### Papers más antiguos ACCEPTED

```bash
b2g read list --status ACCEPTED | sort -k3 | head -5
```

¿Son fundacionales o ruido? Si ruido, marca como REJECTED.

### Papers sin abstract

```bash
b2g read list --status ACCEPTED | grep "abstract: null"
```

Sin resumen, es más riesgo. CANDIDATE o REJECTED.

### Gráfico temporal

```bash
b2g read stats --group-by year
```

¿El corpus está concentrado en 3 años o distribuido? (Distribuido = más robusto)

---

## Paso 6 — Documenta tu decisión

Guardá un archivo `CURATION_NOTES.md`:

```markdown
# Curación PRISMA — [Tu tema]

## Decisión tomada: 2024-06-30

### Criterios de Identificación
- Duplicados: rechazados sin revisar
- Idioma: solo inglés
- Retractados: 0 encontrados

### Criterios de Cribado
- Título debe mencionar "recuperación de información" O "multilingual"
- Resumen debe proponer un método/enfoque (no solo reseña)

### Criterios de Elegibilidad
- Texto completo disponible = más peso que CANDIDATE
- Métodos reproducibles = ACCEPTED

### Criterios de Inclusión
- Relevancia media + aporta perspectiva nueva = ACCEPTED
- Relevancia baja = REJECTED (sin excepciones)

### Resultado
- Comenzamos con: 315 papers
- Rechazados: 70
- Candidatos (para revisar después): 20
- Aceptados (corpus final): 225

### Nota
Si después encontramos papers clave en los CANDIDATE,
los movemos a ACCEPTED. La curación es iterativa.
```

---

## Checklist

- [ ] Extraje corpus a CSV (`b2g curate dump`)
- [ ] Documenté criterios PRISMA de cada fase
- [ ] Curé el CSV: cada paper tiene status (ACCEPTED/REJECTED/CANDIDATE)
- [ ] Apliqué cambios: `b2g curate apply curate.csv`
- [ ] Verifiqué con `b2g read stats` — corpus final es 100–300 papers
- [ ] Documenté notas de curación en CURATION_NOTES.md

---

## Errores comunes

❌ **"Voy a curar rápido, sin criterios."**  
→ Resultado: decisiones inconsistentes, imposible reproducir.

✅ **Documentá criterios primero, cura segundo.**

---

❌ **"Si una paper parece remotamente relevante, la acepto."**  
→ Resultado: corpus con ruido, análisis de redes confuso.

✅ **Sé estricto. Es OK rechazar.**

---

❌ **"Curación es para perfeccionistas."**  
→ Curación define la calidad del análisis que sigue. No es opcionable.

✅ **Invierte 2–3 horas aquí, ahorra 10 después.**

---

## Siguiente

Cuando tengas un corpus ACCEPTED limpio:
- [Guía: Leer las 5 redes](leer-redes.md)
