---
title: "¿Expando el corpus? — Guía sobre forrajeo"
---

# ¿Expando el corpus? — Cuándo y cómo hacer forrajeo

El **forrajeo** (backward chaining) busca papers que no aparecieron en tu búsqueda
inicial, pero que son citados por los papers que sí encontraste.

Esta guía: ¿CUÁNDO hacerlo? ¿CUÁNDO NO? ¿CÓMO sin perderse?

!!! info "Alcance"
    - Para alguien que ya tiene un corpus de siembra (~100–300 papers)
    - Toma: 15 minutos de decisión + 30 min de ejecución
    - Herramienta: bib2graph CLI o agente

---

## Qué es el forrajeo

```
Corpus inicial:
├─ Paper A
├─ Paper B (cita a Paper X, Y, Z)
└─ Paper C

Forrajeo (1 capa):
└─ Busca Papers X, Y, Z (citados por B pero no en corpus inicial)
   └─ Trae ~20–50 papers nuevos
```

**Ventaja:** Aumenta sensibilidad sin ruido (los nuevos fueron citados por relevantes).

**Riesgo:** Trae papers muy antiguos, de dominios tangenciales, o que no aplican.

---

## Paso 1 — Decide si forrajear

### Forrajea SÍ si:

✅ Tu tema es **muy específico** (no "machine learning", sino "alineación de valores en LLMs").  
✅ Tu corpus inicial es **pequeño** (<100 papers) y quieres más densidad.  
✅ Buscas **máxima cobertura** — no quieres perderte trabajos clave aunque sean antiguos.  
✅ Tienes **tiempo** — forrajeo agrega 30 min de ejecución + revisión.

### No forrajees si:

❌ Tu tema es **genérico** — forrajeo podría traer decenas de miles de papers.  
❌ Tu corpus inicial ya es **grande** (>500 papers) — probablemente alcanza.  
❌ Necesitas un SOTA **rápido** — la prueba de concepto sin forrajeo es suficiente.  
❌ El tiempo es crítico — aprioriza curación sobre expansión.

### Tu decisión

Responde:

1. **¿Es mi tema altamente específico?** Sí/No
2. **¿Mi corpus inicial es < 100 papers?** Sí/No
3. **¿Tengo 1–2 horas extras?** Sí/No

**Si respondiste SÍ a 2+ preguntas → forrajea.**  
**Si respondiste No a la mayoría → salta directo a curación.**

---

## Paso 2 — Ejecuta el forrajeo

### Con CLI

```bash
cd tu-sota
b2g chain --depth 1 --limit 100
```

**Opciones:**

- `--depth 1`: Una capa de referencias (recomendado).
- `--limit 100`: Trae máximo 100 papers nuevos (ajusta según necesidad).
- Sin opciones: trae todo lo que encuentre.

### Con agente

```text
Expandí mi corpus usando forrajeo (backward chaining):
- Corpus actual: [X papers]
- Límite: trae máximo 100 papers nuevos
- Profundidad: una capa (citados directamente por mis papers)

Mostrame:
- Cuántos papers nuevos se agregaron
- Rango de años (¿muy antiguos?)
- Si hay clusters temáticos nuevos
```

---

## Paso 3 — Revisa lo que trajo

Después de ejecutar `b2g chain`, **revisa lo nuevo antes de seguir**.

### Inspecciona los papers nuevos

```bash
b2g read list --status candidate | head -20
```

### Preguntas clave

1. **¿Hay papers muy antiguos (pre-2000)?**
   - Sí → Probablemente foundational, mantenlos.
   - No → Bien, son contemporáneos.

2. **¿Hay clusters temáticos que NO esperabas?**
   - Sí → Revisa si son tangenciales (y rechaza luego en curación).
   - No → Buen señal.

3. **¿El tamaño es manejable?**
   - Corpus total < 1000 papers → adelante.
   - Corpus total > 2000 papers → considera rechazar duplicados o muy antiguos.

---

## Paso 4 — Ajusta si hace falta

### Si trajo MUY POCO (<20 papers nuevos)

Probablemente tu búsqueda inicial fue muy acotada. Es OK — no fuerces forrajeo.
Pasa a curación con lo que tienes.

### Si trajo MUCHO (>500 papers nuevos)

Probablemente tu búsqueda inicial fue genérica. Opciones:

1. **Rechaza papers muy antiguos:** `b2g curate filter --min-year 2010`
2. **Rechaza dominios tangenciales:** marca como REJECTED en curación
3. **Usa keywords para sub-seleccionar:** `b2g read list --query "tu_keyword"`

### Si trajo papers fuera de scope

Marca como REJECTED en la curación siguiente. No son un problema, solo ruido.

---

## Paso 5 — Documentá tu decisión

Antes de pasar a curación, documentá:

```
# DECISIÓN DE FORRAJEO
Fecha: 2024-06-30
Corpus antes: 250 papers
Forrajeo ejecutado: sí (depth=1, limit=100)
Corpus después: 315 papers (+65 nuevos)
Observación: Papers nuevos son relevantes, años 2008–2023
Decisión: Mantener todos para curación (PRISMA filtrará)
```

---

## Checklist

- [ ] Decidí conscientemente si forrajear (no por defecto)
- [ ] Ejecuté `b2g chain --depth 1 --limit 100`
- [ ] Revisé los papers nuevos (años, temas)
- [ ] Corpus final es manejable (< 2000 papers)
- [ ] Documenté la decisión

---

## Siguiente

Después de forrajeo (o decisión de no forrajear):
- [Guía: Curación PRISMA paso a paso](curacion-prisma.md)
