---
description: >-
  Retrospectiva metacognitiva de fin de ciclo — mide dónde se fue el tiempo (examina
  los transcripts de los subagentes), reflexiona sobre la estrategia y APLICA mejoras al
  proceso (.claude/agents/, AGENTS.md, hooks). Usala al cerrar un epic, un feature-cycle
  grande, un release o una sesión con mucho fan-out. Cierra el lazo de aprendizaje.
argument-hint: "[qué ciclo cerrás: epic #N / release / sesión]"
---

# /retro-ciclo — retrospectiva del proceso de los agentes

Sos el **orquestador/tech-lead**. Acaba de cerrarse un ciclo de trabajo
($ARGUMENTS). Corré la retrospectiva **del proceso de los agentes** (no del producto:
eso es `/cosechar-sesion`) para responder con DATOS: *¿qué nos tardó más? ¿la forma de
trabajar fue la correcta? ¿en qué falla hoy y cómo lo mejoramos?* — y dejar el proceso
mejor que como lo encontraste.

## Procedimiento

1. **Medí — datos duros, no impresiones.** Los transcripts de los subagentes de esta
   sesión están como JSONL en el task dir (`…/tasks/<agentId>.output`). **NO los leas
   enteros** (overflow). Despachá un subagente `general-purpose` que los procese con
   Bash/python línea por línea y devuelva **métricas, no dumps**:
   - Wall-clock por agente (`duration_ms` de las notificaciones) y por rol
     (coder/verifier/architect).
   - Para los coders más lentos: #Bash/#Edit/#Read; **cuántas veces corrió el suite
     completo de pytest vs subconjuntos**; ruff/mypy/uv sync; y **qué fracción del tiempo
     fue esperando tests** (gaps tras `pytest`).
   - Reintentos, loops editar→test→fallar, errores de formato/CRLF/encoding, timeouts,
     conflictos de merge, y **trabajo perdido/rehecho** (p.ej. agentes que escribieron en
     el worktree equivocado).
   - **Avisá si faltan transcripts** (vacíos / no capturados): punto ciego de auditoría.

2. **Reflexioná — honesto, incluí tus propios errores de orquestación.**
   - ¿Cuál fue el cuello de botella dominante? Cuantificalo.
   - ¿La estrategia fue la correcta? ¿hubo cambio (p.ej. secuencial→paralelo) y valió la
     pena? ¿qué fricción introdujo?
   - Separá **desperdicio** de **inversión valiosa** (el rework que nace de un verifier que
     cazó un bug real NO es desperdicio).
   - Clasificá las lecciones: (a) generales, (b) específicas del repo (suite lento,
     archivos calientes como `build.py`/`cli/__init__.py`), (c) errores puntuales de la sesión.

3. **Traé el veredicto al PO y esperá su OK.** Top 3 cuellos de botella con evidencia +
   3-5 mejoras accionables. No cambies el proceso sin confirmar el rumbo.

4. **Aplicá las mejoras DONDE VIVEN** (una retro que no cambia nada es un informe, no una
   mejora):
   - **Comportamiento de un rol** (cómo testea el coder, qué corre el verifier) →
     `.claude/agents/<rol>.md`.
   - **Convención de orquestación** (paralelizar con prudencia, worktrees, batchear
     decisiones) → `AGENTS.md` §"Ejecución concurrente y testing".
   - **Mapa/fases del flujo** → la skill `flujo`.
   - **Guardarraíl** que conviene volver imposible de violar → `.claude/hooks/`.
   - Va por **PR a `dev`** (`chore(proceso): …`), porque `.claude/agents/`,
     `.claude/commands/` y `AGENTS.md` están versionados.

5. **Cerrá con seguimientos.** Lo que no se baka ahora → issue (no nota suelta). Si una
   lección amerita decisión de fondo → ADR vía `/graduar-adr`.

## No-negociables
- **Datos antes de opinar.** Cuantificá el cuello de botella.
- **Honestidad sobre los errores de orquestación** — la fuente más rica de mejora.
- **La retro debe cambiar algo** (bakear ≥1 lección o abrir seguimiento), o no terminó.
- No leas transcripts enteros en tu contexto; delegá la medición.

## Lecciones ya bakeadas (extender, no re-litigar)
- **Epic 0.10.0 / #167:** el suite completo de pytest (~6 min) usado como bucle de
  feedback fue ~50% del tiempo de los coders → testing por capas (coder con subconjunto;
  verifier+CI con el suite) en `.claude/agents/coder.md` y `verifier.md`. Paralelizar solo
  archivos disjuntos; los agentes escriben en el worktree de la sesión, no en la ruta del
  prompt → `AGENTS.md` §"Ejecución concurrente y testing".
