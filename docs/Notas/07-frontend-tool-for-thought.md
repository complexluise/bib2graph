# 07 — Frontend como *tool for thought* (exploración)

> ⚠️ **NOTA EXPLORATORIA — NO es decisión ni ADR.** Captura una dirección de producto que
> estamos *contextualizando*, no comprometiendo. Nada acá fija stack ni alcance. Fecha: 2026-06-16.
> Documento hermano: [`08-referentes-frontend.md`](08-referentes-frontend.md) (revisión de referentes).

## De dónde viene esto

Surgió de una pregunta de accesibilidad: *"esto lo uso yo desde Claude Code, pero no toda la
gente lo va a usar así"*. La cadena de decisiones del PO en esa conversación:

- **Público primero:** investigadores **no técnicos**.
- **Infra:** **local-first** (sin servidor, sin hosting). Se **descartó** MCP / Claude Web /
  servicio gestionado: no es ese público ni ese modelo.
- **Entrega:** una **GUI web local** (`pip install bib2graph[gui]` + `b2g gui` → abre localhost).
- **Reencuadre clave del PO:** la UX **no es** "la más fácil", es **la que permite entender y
  avanzar en el problema, aprender, e ir por la no-linealidad**. El producto trata sobre
  **sistemas complejos** e implica *ir más allá de lo establecido*. → El framework se **deriva**
  de la visión de UX, no al revés.

Eso descartó (como *marco*, no como herramienta puntual) los frameworks de "data-app"
(Streamlit/Gradio/NiceGUI): sirven para formularios y dashboards lineales; **contradicen** un
producto cuya tesis es la no-linealidad.

## La tesis: un instrumento para pensar, no un panel de carga

bib2graph **ya es** no-lineal por diseño (PRD §2, [`05-ciclo-investigacion-humano.md`](05-ciclo-investigacion-humano.md),
`cycle.py`): el lazo **sembrar → forrajear → curar → la idea muta → re-sembrar** (Bates/Ellis/
Kuhlthau, *berrypicking*), la **biblioteca viva** que crece en el tiempo, las **redes** como
estructura intelectual de un campo. Una UX fiel a eso es una **superficie de exploración**, no
un wizard. La pregunta de diseño no es "qué pantallas", es **qué gesto hace el investigador todo
el rato** y cómo la herramienta lo ayuda a *ver* y *aprender*.

## Qué implica concretamente (hipótesis de interacción, a debatir)

- **El grafo como lienzo primario**, no un output final. Navegar la estructura (comunidades,
  centralidad, acoplamiento, asimetrías como Norte–Sur), seguir el *information scent*, y decidir
  **desde la estructura visible** — no desde una lista plana.
- **El lazo hecho visible y navegable**: las rondas / `reseed` como una **línea de tiempo
  ramificada del pensamiento** (un "git de la investigación"): ver cómo mutó la pregunta,
  comparar snapshots, volver, bifurcar. La no-linealidad como objeto de **primera clase** en
  pantalla, no como prosa.
- **Forrajeo como exploración, no como import**: candidatos que aparecen **con su porqué** (con
  qué del corpus se acoplan/co-citan), aceptar/rechazar en el lienzo, ver la biblioteca crecer.
- **Sensemaking humano asistido por la estructura** (coherente con ADR 0022, *sin IA generativa*):
  anotar, leer comunidades, los **disclaimers de proxy** — la herramienta ayuda a *ver*; el
  juicio lo pone el humano.

Familia de referencia: más cerca de **Connected Papers / ResearchRabbit / Litmaps**, de un
**Kumu/Gephi** para sistemas complejos, o de un canvas tipo **tldraw/Obsidian Canvas**, que de un
data-app. Ver [`08-referentes-frontend.md`](08-referentes-frontend.md).

## Consecuencia técnica (hipótesis, NO decisión)

Una UX así apunta a un **frontend web propio** (SPA: React/TS o Svelte) + una **librería de
grafos seria** (Cytoscape.js / Sigma.js / G6; deck.gl si hay escala) sobre una **API local**
(p. ej. FastAPI) que expone el núcleo. Propiedades que se preservan:

- **Local-first intacto**: `b2g gui` levanta server local + sirve la SPA en localhost; `.duckdb`
  en el disco; cero hosting.
- **Núcleo puro intacto**: el frontend es **otra costura/frontend** sobre las mismas funciones
  `run_<cmd>` y `Networks.quick` que usa el CLI; el núcleo no importa el framework (extra `[gui]`
  opt-in, import perezoso — patrón de `[bibtex]`).
- **Camino a escritorio**: **Tauri** (envuelve un frontend web) es el puente natural a una app de
  escritorio en una fase posterior — mejor que un framework Python para una UI custom.
- **El CLI agente-native NO se reemplaza** (ADR [0021](../decisiones/0021-cli-agente-native-contrato.md)):
  sigue siendo la columna para agentes/automación. La GUI es un frontend **adicional** para humanos.

## Tensiones y riesgos abiertos (honestos)

- **Costo del build**: un frontend rico (diseño de interacción + UX de grafos + ingeniería front)
  es **mucho** más que un data-app. Es el camino correcto para la ambición, pero caro.
- **Madurez**: el producto recién cableó co-citación end-to-end (Hito 8) y **no tiene un caso real
  reproducido por un tercero** (criterio 1.0, PRD §10). Riesgo de construir la superficie
  equivocada antes de validar. → Contextualizar bien ahora *es* la mitigación.
- **Pivote de posicionamiento**: el PRD §3/§5.2 hoy dice "sin GUI, usuario CLI". Apuntar a no
  técnicos lo cambia → requerirá un ADR (¿0027?) y enmiendas a PRD/ARCHITECTURE **cuando** se
  decida construir. Hoy seguimos en contextualización.
- **Usuario no-técnico concreto**: falta definir *quién* es (¿estudiante de posgrado? ¿docente?
  ¿analista de política?), su journey y su momento de "aprendí algo".

## Preguntas abiertas (para el modelo de interacción)

1. ¿Cuál es el **verbo central** que el usuario hace todo el rato? (navegar y "tirar del hilo" /
   comparar rondas / curar en el lienzo / …)
2. ¿Cuál es el **journey** del usuario no-técnico concreto, y dónde *aprende*?
3. ¿Cuánto MVP? (read/visualize primero vs flujo completo — sin decidir aún)
4. ¿Cómo conviven **GUI (humano) y CLI (agente)** sobre el mismo núcleo y la misma biblioteca?

## Estado y próximos pasos

**Fase: contextualización.** Secuencia propuesta: (1) revisión de referentes
[`08`](08-referentes-frontend.md) → (2) definir el **modelo de interacción** (el "verbo" + journeys)
→ (3) producir **conceptos de UX** (mockups/flujos) para reaccionar → (4) **recién ahí** elegir
stack y partir el build (con ADR + enmiendas de posicionamiento). No se construye nada hasta
cerrar (1)–(3).

Relación con docs: PRD §1–§2 (el lazo), [`05-ciclo-investigacion-humano.md`](05-ciclo-investigacion-humano.md),
`src/bib2graph/cycle.py` (FSM del ciclo), ADR [0021](../decisiones/0021-cli-agente-native-contrato.md)
(CLI agente-native), y `referentes.md` (referentes académicos/método — distinto de los de UX de la Nota 08).
