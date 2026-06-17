# 10 — Síntesis de contextualización: descomposición de las Notas 07/08/09

> ⚠️ **NOTA EXPLORATORIA — no es decisión ni ADR.** Consolida las Notas
> [07](07-frontend-tool-for-thought.md) (visión GUI), [08](08-referentes-frontend.md) (referentes)
> y [09](09-sesion-qa-prueba-ecologia-valoraciones.md) (QA con caso real) descomponiendo la
> información en **redundante / único / tensionante / sinergético**, para decidir desde una base
> clara. Fecha: 2026-06-16.

Las tres notas miran el mismo objeto desde tres ángulos: **visión (07)**, **mercado (08)** y
**práctica real (09)**. El método: separar señal de eco.

## 🔁 Redundante (núcleo confirmado por triangulación)

Que visión + mercado + práctica converjan es la señal más fuerte de verdad:

- **Lazo no-lineal / "git de la investigación" / comparar rondas** — 07 (lazo navegable) · 08
  (git/Roam, historia ramificada) · 09 (P5 `diff` de rondas; *"el 'aprendí algo' está en comparar
  rondas, no en la búsqueda inicial"*).
- **El grafo como superficie de exploración, no output final** — 07 · 08 (Connected/Inciteful) · 09
  (exportó GraphML y exploró en Gephi: la "versión pobre").
- **Read-only / visualizar primero como MVP** — 07 (candidata a MVP) · 09 (la sesión *fue* eso) ·
  08 (lo mínimo que alguien usaría).
- **Curación = humana; sensemaking asistido por estructura** — 07 (ADR 0022) · 09 (B4/P1).
- **El CLI *es* la API; cada hueco del CLI es un hueco de la frontera** — 07 · 09 (lección #4).
- **Madurez insuficiente / sin caso reproducido por un tercero** — 07 · 09 (no se curó formalmente,
  no se validó reproducibilidad).

→ **Núcleo confirmado:** workbench local, no-lineal, grafo-lienzo, rondas como historia navegable,
curación humana. Ya no está en duda.

## 💠 Único (aporte irreemplazable de cada nota)

- **07 (visión):** el marco (UX-first no "lo fácil"); el **"verbo central"**; el **journey** (día 1
  → mes 3); la hipótesis técnica (SPA + graph lib + API local + Tauri); el **pivote de
  posicionamiento** (PRD dice "sin GUI"); huecos meta (qué NO es, criterios de éxito/descarte, caso
  narrado).
- **08 (referentes):** el mapa competitivo + **tabla de diferenciación**; qué tomar de cada uno y
  qué evitar (IA caja-negra); el insight del **andamiaje** (el canvas se vuelve caos salvo que la
  estructura bibliométrica lo sostenga).
- **09 (práctica):** la **evidencia empírica** — qué se rompe de verdad: **#21** (forward chaining
  se cuelga 10+ min, sin cap = *blocker*), **#25** (redes sin label = ilegibles), **#22/#26** (sin
  CSV no hay curación a escala), **P2** (diagnóstico señal/ruido), **P3** (negaciones), **P4**
  (clusters como tabla); y el hecho operativo: **co-citación sale vacía** en uso real. Es lo único
  anclado en uso real, no en hipótesis.

## ⚡ Tensionante (lo que tira en direcciones opuestas)

1. **"No técnico" ↔ `pip install bib2graph[gui]`** — el público objetivo no hace `uv sync`.
2. **Construir GUI rica ↔ el núcleo no cierra el flujo end-to-end** (blockers #21/#25/#22/#26).
3. **Grafo-lienzo como superficie primaria ↔ el grafo es ilegible hoy** (#25).
4. **Forrajeo "en el lienzo" ↔ el forrajeo se cuelga** (#21).
5. **Read-only MVP ↔ el dolor real es la curación** (600 candidatos sin marcar).
6. **"Ir más allá de lo establecido" ↔ lo establecido ya hace mucho** — la novedad es la
   **integración**, no una feature suelta.
7. **Local/propio ↔ accesible** — lo que lo hace fuerte (local+reproducible) es lo que hoy lo hace
   inaccesible; quiere las dos a la vez.

## 🔗 Sinergético (1+1+1 > 3)

1. **Los bugs de 09 SON el esqueleto de API que necesita la GUI de 07.** #14/#22/#25/#26 son a la
   vez *bugs del core* y *la superficie que la GUI consumiría*. Arreglar el núcleo **es** el cimiento
   de la GUI. → **Disuelve la tensión #2.**
2. **Triangulación: P1–P5 (09) = "qué tomar" (08) = visión (07).** Las tres describen el mismo
   producto desde teoría, mercado y práctica.
3. **09 prueba que el MVP read-only es real:** la "versión pobre" (scripts + Gephi) ya entregó valor.
4. **La estructura bibliométrica es contenido Y andamiaje** (los clusters de 09 = el lienzo de 07 =
   el andamiaje de 08).

## 🎯 Resolución de la contextualización

La tensión central (GUI vs núcleo) es **falsa**: la sinergía #1 muestra que el próximo trabajo
correcto es **cerrar los huecos que el uso real expuso** (#14, #21, #25, #22, #26), porque eso es
a la vez (a) destrabar el flujo, (b) construir la API que la GUI consumiría, y (c) validar el modelo
de interacción con un caso real *antes* de pagar el frontend.

Y matiza el MVP: **"visualizar" valida la interacción; "curar a escala" (CSV, #22/#26) vuelve la
herramienta usable** — y es barato (CLI), sin lienzo. Secuencia honesta: **núcleo (huecos de 09) →
caso real reproducido → recién GUI**; dentro de la GUI, *visualizar primero pero con curación-CSV
ya resuelta debajo*.

## 🔧 Tensiones a resolver (preguntas clave → issues)

> Resolver cada tensión genera **issues concretos** para arreglar la superficie. Las decisiones del
> PO se irán anotando acá y bajando a issues de GitHub. (Estado: **abiertas** al 2026-06-16.)

- **T1 — audiencia/canal:** ¿quién es el no-técnico v1? ¿pip/uv aceptable o binario requisito?
  ¿canal intermedio (pipx/instalador)?
- **T2 — secuencia:** ¿se confirma "núcleo → caso real → GUI"? ¿cuál es el gate de "caso real
  reproducido"?
- **T3 — labels (#25):** ¿label por defecto por tipo de nodo? ¿qué atributos extra inyectar? ¿en
  proyector o exporter?
- **T4 — forrajeo (#21):** ¿política de cap/batching/preview/progreso/timeout? ¿defaults?
- **T5 — curación (#22/#26):** ¿CSV dump+import entra junto al MVP? ¿formato? ¿`diagnose` (P2) sí/no?
- **T6 — diferenciador:** ¿cuál es LA punta de lanza (no-linealidad/diff de rondas, transparencia
  PRISMA, biblioteca viva)? ¿se comunica como integración?
- **T7 — accesible sin perder local:** ¿onboarding/plantillas/workspace de ejemplo? ¿modo demo?
- **Meta:** criterios de éxito/descarte de la dirección; quién valida (beta tester/docente).

Las respuestas y los issues derivados se registran en la próxima iteración de esta nota.
