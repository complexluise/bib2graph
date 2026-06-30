---
title: Leer las 5 redes — Qué significan
---

# Leer las 5 redes — Qué significan

Después de construir redes, comes a interpretarlas. Cada red responde una pregunta
diferente sobre tu campo. Esta guía: qué mirar en cada una.

!!! info "Alcance"
    - Para alguien que ejecutó `b2g build` y tiene las redes visualizadas
    - Toma: 1–2 horas (explorando + anotando)
    - Herramienta: Gephi, Cytoscape, o `b2g read top`
    - Salida: Entendimiento del campo + anotaciones para redacción

---

## Las 5 redes que bib2graph construye

bib2graph crea 5 proyecciones del corpus. **No uses las 5 — típicamente usa 2–3.**

```
1. Acoplamiento bibliográfico (papers)
2. Co-citación (papers)
3. Co-autoría (autores)
4. Co-ocurrencia de keywords
5. Colaboración institucional
```

La **más importante es la 1** (Acoplamiento). Empezá ahí.

---

## 1. RED DE ACOPLAMIENTO BIBLIOGRÁFICO

**Pregunta que responde:** ¿Cuáles son los sub-temas del campo?

### Qué es

Dos papers se **acoplan** si citan las mismas referencias.

```
Paper A cita: [Ref 1, Ref 2, Ref 3]
Paper B cita: [Ref 2, Ref 3, Ref 4]

Similitud: comparten 2 referencias
Acoplamiento: fuerte → aparecen cerca en la red
```

### Qué buscas

**Comunidades** (clusters de colors). Cada comunidad = un sub-tema.

### Cómo interpretarla

| Elemento | Significa |
|----------|-----------|
| **Nodo** | Un paper |
| **Tamaño del nodo** | Grado (cuántos otros papers lo citan) |
| **Línea entre nodos** | Acoplamiento (comparten referencias) |
| **Color** | Comunidad (detectada por Louvain) |
| **Densidad local** | Subgrupo temático (si hay clusters densos) |

### Preguntas clave

1. **¿Cuántas comunidades ves?** (típicamente 3–8)
   - Pocas (1–2) → campo homogéneo, enfoque único
   - Muchas (10+) → campo fragmentado, múltiples escuelas

2. **¿Qué hace cada comunidad?**
   - Lee 2–3 papers de mayor grado en cada comunidad
   - Escribe: "Comunidad 1: Enfoques neurales"

3. **¿Hay comunidades aisladas?**
   - Sí → campo fragmentado, sin diálogo
   - No → comunidades conectadas, debate activo

4. **¿Una comunidad domina?**
   - Sí → tendencia clara, escuela hegemónica
   - No → equilibrio de enfoques

### Tip: Extrae top papers por comunidad

Con CLI:

```bash
b2g read top --kind bibliographic_coupling --top 20
```

Esto te da los 20 papers más centrales (mayor grado). Son buenas "referencias canónicas".

Con Gephi:

1. Abre el `.graphml` en Gephi
2. Filtra por color (comunidad)
3. Ordena nodos por tamaño (grado)
4. Anota los top 3 de cada comunidad

---

## 2. RED DE CO-CITACIÓN

**Pregunta que responde:** ¿Cuáles son los papers / autores / trabajos más influyentes?

### Qué es

Dos papers se **co-citan** si aparecen juntos en las referencias de otros papers.

```
Paper A refiere a: [Clásico1, Clásico2, Nuevo1]
Paper B refiere a: [Clásico1, Clásico2, Nuevo2]

Clásico1 y Clásico2 se co-citan frecuentemente
→ Son referencias canónicas
```

### Qué buscas

**Papers que actúan como "hubs" de la red.** Estos son influyentes.

### Cómo interpretarla

| Elemento | Significa |
|----------|-----------|
| **Nodo** | Un paper |
| **Tamaño del nodo** | Co-citación (cuántos otros lo citan juntos) |
| **Línea fuerte** | Frecuentemente citados juntos |
| **Hub central** | Paper/autor/trabajo canónico |

### Preguntas clave

1. **¿Hay un hub central claro?**
   - Sí → hay un "clásico" que todos citan
   - No → múltiples referencias, no hay consenso

2. **¿Qué papers están en el hub?**
   - Anota: estos son obligatorios para tu SOTA
   - Leelos: dan contexto de la escuela

3. **¿Hay papers recientes en el hub?**
   - Sí → el campo evoluciona, hay nuevas referencias
   - No → campo estancado, solo cita clásicos antiguos

4. **¿Qué autores o labs aparecen repetidamente?**
   - Estos son actores clave del campo

### Comparación Acoplamiento vs. Co-citación

| Aspecto | Acoplamiento | Co-citación |
|--------|---|---|
| **Responde** | ¿Sub-temas (presente)? | ¿Influentes (pasado)? |
| **Densidad** | Más densa | Más dispersa |
| **Utilidad** | Entender estructura actual | Entender genealogía intelectual |
| **Nodos** | Papers en tu corpus | Papers citados por tu corpus |

---

## 3. RED DE CO-AUTORÍA

**Pregunta que responde:** ¿Quiénes trabajan juntos? ¿Dónde están los equipos?

### Qué es

Dos autores se **co-autorizan** si escriben papers juntos.

### Qué buscas

**Clusters de autores que colaboran persistentemente.**

### Cómo interpretarla

| Elemento | Significa |
|----------|-----------|
| **Nodo** | Un autor |
| **Línea** | Colaboración (escribieron juntos) |
| **Cluster** | Equipo o laboratorio |
| **Tamaño del nodo** | Productividad (cuántos papers) |

### Preguntas clave

1. **¿Hay equipos cohesivos (clusters densos)?**
   - Sí → campos maduros, labs establecidos
   - No → trabajo más individual o colaboraciones puntuales

2. **¿Qué autores aparecen en múltiples equipos (hubs)?**
   - Estos son "conectores" entre grupos

3. **¿Hay colaboración internacional?**
   - Sí → campo globalizado
   - No → investigación regional/aislada

### Tip: Menos importante que Acoplamiento

Co-autoría es útil pero secundaria. Si tienes poco tiempo, **prioriza Acoplamiento + Co-citación.**

---

## 4. RED DE CO-OCURRENCIA DE KEYWORDS

**Pregunta que responde:** ¿Qué términos se usan juntos? ¿Cuál es el vocabulario del campo?

### Qué es

Dos keywords se **co-ocurren** si aparecen en el mismo abstract.

### Qué buscas

**Clusters de vocabulario.**

### Preguntas clave

1. **¿Qué keywords son centrales?** (muchas conexiones)
   - Estos definen el core del campo

2. **¿Qué keywords son periféricas?** (pocas conexiones)
   - Estos definen sub-especialidades

3. **¿Hay vocabulario que esperabas pero no aparece?**
   - Eso es un hueco de investigación

---

## 5. RED DE COLABORACIÓN INSTITUCIONAL

**Pregunta que responde:** ¿Qué universidades/labs colaboran?

### Qué es

Dos instituciones **colaboran** si sus investigadores co-autorizan papers.

### Preguntas clave

1. **¿Hay universidades dominantes?** (muchos papers)
2. **¿Hay colaboración: local, regional, global?**
3. **¿Qué institutions lideran?** (grado más alto)

---

## Flujo recomendado de lectura

1. **Acoplamiento primero** (20 min)
   - Entiende sub-temas
   - Anota comunidades

2. **Co-citación después** (20 min)
   - Identifica papers canónicos
   - Anotalos como "obligatorios"

3. **Co-autoría opcional** (10 min si tienes tiempo)
   - Entiende quién trabaja con quién

4. **Keywords + Instituciones (skip si no tienes tiempo)**

---

## Qué documentar

Mientras lees, crea una tabla:

```markdown
# Lectura de Redes

## Acoplamiento Bibliográfico

| Comunidad | Keywords | Top Papers | Tensión |
|-----------|----------|-----------|---------|
| Enfoque A | [kw1, kw2] | [Paper1, Paper2] | vs. Enfoque B: diferencia en [aspecto] |
| Enfoque B | [kw3, kw4] | [Paper3, Paper4] | vs. Enfoque A: diferencia en [aspecto] |

## Co-citación

| Paper Canónico | Autores | Año | Por qué influyente |
|---|---|---|---|
| "Seminal Work..." | Smith et al | 2005 | Define el paradigma |

## Notas

- Comunidad 1 y 2 no se conectan → hay un debate abierto
- Keyword "X" está ausente → hueco de investigación
```

---

## Checklist

- [ ] Abrí Acoplamiento en Gephi o visualicé con `b2g read top`
- [ ] Identifiqué 3–5 comunidades, las nombré
- [ ] Extraje top 2–3 papers de cada comunidad
- [ ] Abrí Co-citación, identifiqué papers canónicos
- [ ] Documenté en una tabla: comunidades + papers clave
- [ ] Identifiqué 2–3 tensiones entre comunidades

---

## Siguiente

Con las redes entendidas, listo para redactar:
- [Guía: Del corpus al reporte](reporte.md)
