# 29 — Backlog, sinergias y plan 0.12.0: agent-native de verdad, listo para cualquier agente

> **Género:** nota de planificación (encuadre antes de abrir sub-issues / ADR; no es ADR ni doc canónico).
> **Origen:** revisión del backlog de GitHub (junio 2026) en torno al eje *"experiencia de uso + agent-native"*: cómo cerrar el lazo end-to-end para que un investigador (humano o agente, en Claude Code / OpenCode / otro cliente) pueda correr el ciclo completo sin ayuda y obtener un entregable defendible.
> **Para qué:** dejar por escrito el mapa del backlog, las sinergias detectadas, las decisiones del PO (qué entra, qué se difiere) y el orden de merge propuesto para 0.12.0. Insumo para abrir sub-issues, escribir las ADR nuevas y secuenciar el trabajo.
> **Auditoría as-built (2026-06-30):** las afirmaciones sobre superficie CLI / ADR vigentes están contrastadas contra `docs/API.md`, `docs/decisiones/0043-posicionamiento-agent-native-cli.md`, `docs/decisiones/0044-precedencia-inclusion-manual-en-curate.md`, el milestone activo en GitHub y las ramas locales. Las dependencias duras están verificadas.
> **Relacionadas:** `22-frontera-y-alcance-de-bib2graph.md` (la frontera que no se cruza), `23-RETROALIMENTACION_bib2graph_agente.md` (fricciones P1/P2/P3 desde un agente), `26-retroalimentacion-cli-agent-native.md`, `28-marco-software-donde-nos-paramos.md` (el marco de software que sostiene el producto), ADR [0021](docs/decisiones/0021-cli-agente-native-contrato.md), ADR [0037](docs/decisiones/0037-superficie-cli-10-verbos-ciclo.md), ADR [0038](docs/decisiones/0038-destino-verbos-huerfanos-0037.md), ADR [0039](docs/decisiones/0039-skill-comando-meta-distribucion.md), ADR [0043](docs/decisiones/0043-posicionamiento-agent-native-cli.md).

---

## TL;DR

El backlog tiene **bastante trabajo**, pero no todo cabe y no todo tiene el mismo retorno. Si el eje es **experiencia de uso + agent-native**, hay un subconjunto cuya sinergia es grande y se puede entregar junto en **0.12.0**. La propuesta, ya validada con el PO:

> **0.12.0 = "agent-native de verdad, listo para cualquier agente".**
> Tres olas: (1) cerrar el lazo end-to-end que hoy se rompe; (2) cerrar las 3 grietas que el ADR [0043](docs/decisiones/0043-posicionamiento-agent-native-cli.md) declaró como roadmap; (3) hacer amable el último kilómetro + democratizar la skill + abrir la puerta a investigadores no-técnicos.

Lo que queda fuera: multi-proveedor / DOAJ (#256, #252 — scope-future), colaboración por Git como flujo de primera clase (#205 — necesita ADR de bordes, 0.13.0), back-merge automático de release-please (#245 — toil manual documentado por ahora).

---

## 1. Estado del repo y de GitHub

- **Rama actual:** `feat/233-curate-precedencia-manual` (clean). Tiene el fix de #233 + ADR [0044](docs/decisiones/0044-precedencia-inclusion-manual-en-curate.md) mergeados en la historia reciente (commits `3417c68`, `40d9f7c`, `2f58ab5`). Lista para PR a `dev`.
- **ADR 0043** (Aceptada, 2026-06-30) — **posiciona el CLI como agent-native deliberadamente** y declara **3 grietas como roadmap**: (3a) `error.subcode` para 429 vs 504, (3b) eco del workspace resuelto, (3c) `b2g schema`.
- **ADR 0044** (Aceptada) — cierra #233: `curate filter` no rechaza `accepted`.
- **Milestone activo:** `0.12.0` (vence 2026-07-05), 8 issues abiertos.
- **0.11.0** cerrado (5 issues cerrados).
- **Backlog sin milestone:** ~12 issues abiertos relevantes para el eje "experiencia de uso + agente-native".

## 2. Mapa del backlog (issues vivos, agrupados por eje)

### Eje A — Cerrar el lazo end-to-end (P1 de #204 + #233 + #221)

- **#233** `curate filter` pisa `accepted` sin avisar — *cerrado en rama actual, listo para PR*.
- **#204** (P1) `chain --direction backward` reporta "0 candidatos" con output contradictorio pese a `--preview`列出 miles — *rompe el lazo*.
- **#204** (P1) Co-citación inalcanzable: tres comandos tocan `cited_by_id` y ninguno solo lo completa; `enrich` está deprecado y solo puebla sobre `accepted`; `chain forward` no puebla `cited_by_id`. Sin camino feliz único.
- **#221** Split de #207 — grupo `read {list,stats,top,show}` con `read top --by-community`, abstracts en lote, `group-by` ampliado. Aterriza la fricción #1 de la [Nota 23](23-RETROALIMENTACION_bib2graph_agente.md).
- **#207** Poda 0038 + cierre de la ventana de deprecación (breaking). El propio cuerpo del issue dice *"el conteo '20 subcomandos' tiene que dejar de ser falso"*.

### Eje B — Agent-native real: las 3 grietas del ADR 0043

- **#258** `error.subcode` (3a) — `RATE_LIMITED` (429) vs `UPSTREAM_TIMEOUT` (504). Única con daño documentado en uso real: el agente ruteó alrededor del motor y perdió procedencia.
- **#259** (3b) Eco del workspace resuelto en el envelope + warning en walk-up.
- **#260** (3c) `b2g schema` — introspección versionada del contrato. Cierra el *hop* a `docs/API.md` en prosa.

### Eje C — Salida amable + skill multi-proveedor + docs para no-técnicos

- **#203** CSV: URL al paper + campos faltantes + encoding i18n. Cierra el feedback hispano (mojibake de tildes en Excel-Windows).
- **#188 + #193** Skill distribuida en el wheel (✅ `b2g skill add` para Claude Code en 0.10.0) **+ skill agnóstica del proveedor** (Claude Code → OpenCode, etc.). Sin esto, bib2graph queda atado a un cliente.
- **#187** Propuesta de visión: posicionar bib2graph como *"revisión narrativa asistida por bibliometría"* (antídoto contra el sesgo del related work escrito de memoria).
- **#134 (cierre)** + **#208** Documentación de usuario en el tono del investigador, no del bibliómetra. Diátaxis: tutorial + how-tos.
- **#196** Epic 0.12.0 / Nota 22 — responder a la frontera bib2graph/producto (paraguas, auditoría contra la frase-ancla).

### Eje D — Diferido (con justificación)

- **#256** Epic multi-proveedor post-S2 hacia 0.12/0.13 — superficie multi-source es enorme y se cruza con ADR 0042. **Fuera** de 0.12.0.
- **#252** DOAJ como fuente Sur-global — reentra cuando haya demanda real + capacidad.
- **#205** Colaboración por Git como flujo de primera clase — viable pero necesita ADR de bordes (`curate merge`, `curate diff`, gitignore default, hidratación). Diferir a 0.13.0.
- **#245** Back-merge automático de release-please — bug de CI/infra. **Diferido** (toil manual documentado en `CONTRIBUTING.md`).
- **#251, #253, #254, #255** Wiring de Semantic Scholar / Doaj / decisiones de identidad cross-proveedor — acoplados a #256; no entran solos.
- **#235** Benchmark `@slow` huérfano — housekeeping de CI, no bloqueante.

## 3. Sinergias detectadas (lo que hace que esto *cabe junto*)

### Sinergia A — Cerrar la grieta agent-native (ADR 0043, 3 grietas)
Las 3 grietas (#258, #259, #260) son **aditivas, pequeñas y comparten el mismo contrato** (`docs/API.md`). Una sola sub-práctica + **un ADR paraguas** las cierra juntas. Esa conversión de "lo declarado/roadmap" a "lo implementado" hace que cualquier otra mejora de AX se apoye sobre un envelope honesto.

### Sinergia B — P1 de #204 + #207 + #221
El epic 0.12.0 contiene 3 P1 que el agente operativo topó: `chain --direction backward` reporta "0 candidatos"; co-citación inalcanzable; podas de deprecación que no driftean con el contrato. Juntas son **un mismo arco: hacer que el lazo se cierre sin help humano**.

### Sinergia C — Polish ofensivo: encoding CSV i18n + GraphML enriquecido
El feedback de usuario (#203: encoding i18n + URL + campos) converge con los patrones de BibGraph (#206: errores honestos, GraphML rico). Baja la fricción del **último kilómetro**: el artefacto que el investigador abre ya está listo.

### Sinergia D — Distribución de la skill agnóstica del proveedor (#188 + #193)
El epic skill ya está prácticamente hecho (ADR [0039](docs/decisiones/0039-skill-comando-meta-distribucion.md)); solo falta la **abstracción por proveedor** (Claude Code → OpenCode → otros). Esto desbloquea *"lo pueden usar desde cualquier agente"* en una sola entrega.

### Sinergia E — Documentación de usuario / quickstart no-técnico (#134 cierre + Nota 22 + #187)
Toda la potencia construida está, pero **faltan los manuales en el tono del investigador** (no del bibliómetra). El quickstart *"5 pasos para no repetir tu related work de memoria"* (#187) cierra el ciclo *"que la pueda usar alguien curioso, no técnico"*.

## 4. Decisiones del PO (validadas en sesión)

| Decisión | Valor | Por qué |
|---|---|---|
| **Alcance 0.12.0** | Ola 1 + Ola 2 + Ola 3 completas | Eje único: agent-native + experiencia de uso. Las tres olas convergen sobre el mismo entregable. |
| **Poda de deprecación (#207)** | Romper en 0.12.0 (breaking) | Ya hubo una ventana 0.10.0→0.11.0; cerrarla limpia el conteo de "10 verbos" y elimina drift. |
| **Back-merge release-please (#245)** | Diferido (toil manual documentado) | Pequeño pero de infra; no compite por archivos con el resto del release. |
| **ADR nuevas** | Una ADR paraguas para las 3 grietas + ADR para skill multi-proveedor | Regla del repo: cada cambio del contrato arrastra su ADR. Las 3 grietas juntas justifican un paraguas; skill multi-proveedor es cambio de contrato aparte. |
| **Multi-proveedor (#256, #251-#255)** | Diferido a 0.13.0 | Toca decisiones de identidad cross-proveedor (ADR 0042) que merecen su propio encuadre. |
| **Colaboración por Git (#205)** | Diferido a 0.13.0 | Necesita ADR de bordes; no bloqueante para "experiencia de uso". |
| **Visión #187** | Entra como docs (no como feature) | El quickstart se materializa como tutorial Diátaxis; el "motor de revisión narrativa asistida" es posicionamiento del README, no código nuevo. |

## 5. Plan consolidado: 3 olas dentro de 0.12.0

### Ola 1 — Cerrar el lazo (P1 + structural)

**Objetivo:** que el lazo end-to-end corra sin help humano. Subtareas:

1. **Cerrar #233** — la rama `feat/233-curate-precedencia-manual` ya tiene el fix + ADR 0044. PR a `dev`.
2. **#204 P1a — Backward chain bug.** Fix: `chain --direction backward` no debe reportar "0 candidatos" cuando `--preview`列出 miles y hay refs observadas. Separar el conteo del output de top-candidatos. Issue propio.
3. **#204 P1b — Co-citación con camino feliz único.** Decisión de diseño: `chain forward` puebla `cited_by_id` además de la metadata del citante. O un comando explícito `b2g build --cocitation` que orquesta el camino completo (`accept` → `chain forward --mode cite` → `build`). ADR de camino único antes de mergear.
4. **#221 grupo `read {list,stats,top,show}`** con `read top --by-community`, abstracts en lote (`read list --fields abstract,…` o `read dump --json`), `group-by` ampliado (source/community/decade/language). Split de #207 según el cuerpo del propio issue.
5. **#207 poda 0038 + cierre de ventana de deprecación** (breaking). `BREAKING CHANGE:` footer. `b2g --help` debe listar exactamente los 10 verbos del ciclo + meta + aliases-con-warning. `inspect`/`enrich`/`thesaurus`/`restore`/`resolve` se retiran sin alias-cortesía (P1 0038) o con alias+warning (P1 #207).

### Ola 2 — Agent-native real (ADR 0043, 3 grietas)

**Objetivo:** cerrar la deuda declarada en ADR 0043. Subtareas:

6. **ADR 0045 (paraguas)** — cierra las 3 grietas del ADR 0043 como una sola decisión registrada: (3a) `error.subcode`, (3b) eco del workspace resuelto, (3c) `b2g schema`. *Debe existir antes del primer PR de Ola 2.*
7. **#258 `error.subcode`** — campo aditivo `error.subcode` en el envelope. Mapeo `RATE_LIMITED` (429) / `UPSTREAM_TIMEOUT` (504). Tests que sellan el mapeo.
8. **#259 eco del workspace resuelto** — `data.workspace` aditivo en el envelope + warning accionable cuando se resolvió por walk-up. Tests.
9. **#260 `b2g schema`** — comando meta (fuera de los 10 verbos del ciclo, patrón `skill` de ADR [0039](docs/decisiones/0039-skill-comando-meta-distribucion.md)). Emite envelope-schema + exit codes + versión. Conteo "10 + `skill` + `schema`".
10. **#204 P2 — Deprecaciones visibles en `--help`.** Marca `[DEPRECATED → X]` en la 1ª línea del `--help` y en el listado de comandos. Barato, gran delta de AX.

### Ola 3 — Salida amable + skill multi-proveedor + docs no-técnicas

**Objetivo:** democratizar el acceso y abrir la puerta a investigadores no-técnicos. Subtareas:

11. **#203 CSV — URL + encoding i18n + campos faltantes.** Cierra el feedback hispano (mojibake de tildes en Excel-Windows). Sumar columna URL canónica al landing.
12. **ADR 0046 + #193 skill multi-proveedor.** `--provider claude-code|opencode`. Mapa proveedor → ruta + formato. El **version-lock skill==cli** se preserva. `b2g skill providers`/`list` para descubrir lo soportado.
13. **Quickstart "5 pasos para revisión narrativa asistida por bibliometría" (#187)** + **docs Diátaxis (#134 cierre, #208).** README no-técnico. Tutorial de los 5 pasos del #187: lista ingenua → barrido → diff → lectura dirigida → escritura narrativa.
14. **#245 back-merge release-please** → **diferido**, documentar como toil en `CONTRIBUTING.md`.

## 6. Dependencias duras y orden de merge

```
[Ola 1]
#233 ─┐
       ├─ #204 P1a (backward) ─ #204 P1b (camino único co-citación)
       ├─ #221 read group (split de #207, aditivo)
       └─ #207 poda deprecación (BREAKING; va al final de Ola 1)

[Ola 2]
ADR 0045 (paraguas, previa) ─ #258 ─ #259 ─ #260 (serializados: envelope compartido)
                                          └─ #204 P2 (deprecaciones visibles, baratísimo)

[Ola 3]
#203 CSV ─────────────────┐
ADR 0046 + #193 skill ────┤  (paralelos: archivos disjuntos)
#187 + #134/#208 docs ────┘
```

**Reglas de serialización (single-writer + archivos calientes):**
- #221 y #207 tocan `cli/__init__.py` → **serializar**.
- Las 3 grietas comparten envelope → **serializar** (un PR chiquito revisable > un PR grande mezclado).
- #203 CSV y ADR 0046/#193 skill tocan archivos disjuntos → pueden ir **en paralelo**.
- La rama actual `feat/233-curate-precedencia-manual` se mergea primero (sin conflicto con nadie).

## 7. Riesgos identificados

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | **#207 es breaking.** Va tarde en Ola 1 para que el último PR de Ola 1 antes de Ola 2 no quede con alias deprecados. Si rompe el flujo de alguien, queda en el CHANGELOG con `BREAKING CHANGE:` footer. | Anunciar en el PR; coordinar con quien use los aliases. |
| 2 | **#221 read group + #207** ambos tocan `cli/__init__.py` → riesgo de conflicto. | Serializar. Mergear uno, rebasar el siguiente. |
| 3 | **ADR 0045 paraguas** debe existir ANTES del primer PR (#258). | Escribirla primero como PR independiente; mergear antes de tocar el envelope. |
| 4 | **#193 skill multi-proveedor** es investigación (formato OpenCode a relevar). | ADR 0046 con diseño + DoD + decisión de abstracción antes de implementar. |
| 5 | **#203 CSV i18n** puede requerir reproducir el bug de encoding en Excel-Windows primero. | Repro mínimo como issue previo; el fix puede esperar confirmación. |
| 6 | **Ventana de release ajustada** (2026-07-05). Si una ola se atrasa, no todo entra. | Recortar Ola 3 si hace falta; Ola 1+Ola 2 son el core. |

## 8. Métricas de cierre del release 0.12.0

- ADR 0045 mergeada (paraguas 3 grietas).
- ADR 0046 mergeada (skill multi-proveedor).
- Suite del gate verde (target: **700+ tests**, hoy ~645).
- **El lazo end-to-end corre sin help humano:** `seed → chain forward → curate accept → build → read top --by-community` produce un resumen investigable en **una** llamada.
- **`b2g schema` funciona** y los agentes pueden introspectar el contrato por el mismo canal.
- **`b2g skill add --provider opencode`** instala la skill en OpenCode; `--provider claude-code` sigue funcionando.
- **CSV abre sin mojibake en Excel-Windows** y trae URL/landing.
- `b2g --help` lista **exactamente** los 10 verbos del ciclo + meta + aliases-con-warning.
- README/quickstart "5 pasos para revisión narrativa asistida" publicado.

## 9. Próximo paso inmediato

Pasar a modo ejecución. Empezar por mergear la rama actual `feat/233-curate-precedencia-manual` (lista, sin conflictos), luego abrir la ADR 0045 paraguas como PR independiente para que Ola 2 tenga su base contractual.

---

*Auditoría as-built: 2026-06-30. Inconsistencias detectadas durante la revisión → ver §6-riesgos y §7-dependencias.*