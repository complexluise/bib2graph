# 0046 — Distribución de la skill agnóstica del proveedor: `b2g skill add --provider ...` con el provider modelado como dato, no como ramas `if`

- **Estado:** Propuesta
- **Fecha:** 2026-07-18
- **Decidido por:** mixto. El **alcance** —qué providers entran en la 1.ª iteración
  (`claude-code`, `opencode`) y qué se difiere a fase 2 (`agents-md` y los que exigen
  transformación de frontmatter)— es **decisión del Product Owner humano**. El **encuadre**
  —modelar el provider como un **dato** `{skills_subdir, project_root, user_root, transform}`
  que encaja en el `run_skill_add` que **ya** parametriza `scope`/`dest`, en vez de ramas
  `if provider == ...`— y el **hallazgo de interop** (OpenCode lee `.claude/skills/` tal cual, sin
  transformación) son **síntesis de la IA (architect) validada por el PO**.
- **Enmienda a [0039](0039-skill-comando-meta-distribucion.md).** El 0039 dejó la distribución
  **atada a Claude Code** como *"limitación DELIBERADA de 0.10.0"* y nombró la distribución
  agnóstica del proveedor como *"prioridad"* con `skill add` que *"ganaría `--provider`"* — este ADR
  **es esa enmienda**. Concreta el `--provider`, fija los providers de la 1.ª iteración y **preserva
  el version-lock skill==cli** (M2 del 0039): el `--provider` cambia **dónde** se copia (y, en fase
  2, **cómo** se transforma), nunca **qué versión** de la skill viaja — sigue siendo la vendida en el
  mismo wheel. No revierte nada del 0039: el comando sigue siendo **meta** (fuera de los 10, sin
  FSM, sin workspace) y la skill sigue **vendoreada** en `src/bib2graph/skill/` incluida por
  `packages`.
- **Relacionada con [0037](0037-superficie-cli-10-verbos-ciclo.md)/[0038](0038-destino-verbos-huerfanos-0037.md)**
  (superficie de **10 verbos del ciclo**): `skill` sigue siendo el **comando meta** fuera del set de
  10; `--provider` no agrega un verbo nuevo. Y con **[0041](0041-documentacion-por-superficie-de-entrega.md)**
  (documentación por superficie de entrega): la skill es **doc operativa mediada por IA**, fuera del
  sitio; ampliar los clientes que la consumen **amplía la superficie mediada por IA** sin forkear el
  sitio.
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): la skill sigue
  siendo **markdown** que un agente del cliente lee. bib2graph no embebe ni invoca ningún modelo; el
  `--provider` solo copia archivos a la ruta correcta de cada cliente.
- **Origen:** issue [#193](https://github.com/complexluise/bib2graph/issues/193), **Bloque C del
  release 0.12.0**.

## Contexto

El [0039](0039-skill-comando-meta-distribucion.md) estableció que bib2graph **distribuye una skill
vendoreada** en el wheel (`src/bib2graph/skill/`: `SKILL.md` + `reference/`) y la **instala con un
comando meta** `b2g skill add`, que la copia al directorio de skills del cliente. Ese comando —
`run_skill_add` en `src/bib2graph/cli/commands/skill.py` — **ya** parametriza el destino por `scope`
(`--user` → `~/.claude/skills/bib2graph/`, `--project` → `.claude/skills/bib2graph/`), usa
`shutil.copytree` y decide idempotencia con `_trees_identical` (comparación por contenido). Todo el
mecanismo está atado a **una** ruta y **un** formato: los de **Claude Code**.

El 0039 declaró esa limitación como **deliberada de 0.10.0** y anticipó su cierre: *"la
distribución agnóstica al proveedor —el usuario/agente declara su cliente (Claude Code, OpenCode, …)
y `skill add` instala en su formato— es prioridad de 0.11.0 ([#193]), probable enmienda a este ADR
(`skill add` ganaría `--provider`)"*. Atar la distribución a un solo proveedor **repite el
gatekeeping que el producto quiere evitar** (que solo quien tiene Claude pueda pedirle a su agente
que use bib2graph). #193 pide, por fin, soportar otros clientes de agentes empezando por
**OpenCode**.

### Hallazgo que decide el diseño: OpenCode ya lee el formato de Claude Code, sin transformación

La investigación arrojó un hecho que simplifica radicalmente la 1.ª iteración: **OpenCode tiene
"Agent Skills" de primera clase** —un `SKILL.md` con frontmatter `name`/`description`, una carpeta
por skill— **y sus rutas de búsqueda incluyen `.claude/skills/` y `~/.claude/skills/`
directamente** (fuente oficial: <https://opencode.ai/docs/skills/>). Es decir: **la skill que
`b2g skill add --provider claude-code` ya instala funciona en OpenCode de facto**, sin ninguna
transformación. El `name: bib2graph` de la skill vendida además **cumple el validador de OpenCode**
(`^[a-z0-9]+(-[a-z0-9]+)*$`).

La consecuencia es que la 1.ª iteración de la distribución agnóstica **no requiere transformar
nada**: es solo elegir **dónde copiar** el mismo `SKILL.md`. El costo real —degradar/transformar el
formato para clientes que **no** hablan el formato de skill de Anthropic— es una fase 2 con mucha
menos urgencia.

## Decisión

**`b2g skill add` gana la opción `--provider`, y el provider se modela como un dato
`{skills_subdir, project_root, user_root, transform}`, no como ramas `if provider == ...`.** Esto
encaja limpiamente en el `run_skill_add` que **ya** resuelve `dest` a partir de `scope`: en vez de
`scope → dest` hardcodeado a `.claude/skills/`, es `(provider, scope) → dest` derivado del dato del
provider, y `transform` decide si se copia el árbol tal cual (`copytree`) o se degrada primero.

### El provider como dato

Cada provider soportado es una entrada de datos (una tabla/registro, no código de control de flujo):

- **`skills_subdir`** — subcarpeta bajo la raíz donde vive la skill (p. ej. `skills/bib2graph`).
- **`project_root`** — raíz del scope `--project` (relativa al cwd).
- **`user_root`** — raíz del scope `--user` (global, relativa al home/config del usuario).
- **`transform`** — función de transformación del contenido. En la 1.ª iteración es **identidad**
  (copia el mismo `SKILL.md` + `reference/`, la vía `copytree`/`_trees_identical` que ya existe).

Agregar un provider de copia-identidad es **agregar una fila de datos**, no una rama nueva. Esto es
lo que mantiene `run_skill_add` sin crecer en complejidad ciclomática y hace la extensión barata.

### Providers de la 1.ª iteración (transform = identidad)

| Provider | Scope `--project` | Scope `--user` (global) |
|----------|-------------------|-------------------------|
| **`claude-code`** (default, el del 0039) | `.claude/skills/bib2graph/` | `~/.claude/skills/bib2graph/` |
| **`opencode`** | `.opencode/skills/bib2graph/` | `~/.config/opencode/skills/bib2graph/` |

- **`claude-code`** sigue siendo el **default** (compat 0039: `b2g skill add` sin `--provider` se
  comporta exactamente como hoy).
- **`opencode`** es una **comodidad**: como OpenCode **ya** lee `.claude/skills/` de todos modos, el
  provider existe para quien **no quiera depender del path de interop** y prefiera la ruta nativa de
  OpenCode. La **transformación es identidad** — es el mismo `SKILL.md`, copiado a otra carpeta.

### Descubribilidad: `b2g skill providers`

Se suma un subcomando `b2g skill providers` (o `list`) que **enumera los providers soportados** —
para que un agente descubra qué clientes puede targetear sin leer el código ni la doc. Es coherente
con el patrón agent-native: la superficie es **introspectable**.

### Fase 2 (diferida — transform ≠ identidad)

Fuera de la 1.ª iteración, con menos urgencia y explícitamente **no decididos aquí en su forma
final**:

- **`agents-md`** — el estándar **`AGENTS.md`** lo leen ~20 clientes (Codex, Cursor, Copilot,
  Gemini CLI, Aider, Windsurf, Zed, RooCode, OpenCode, …; <https://agents.md>). **No es copia
  identidad**: requiere **degradar** el `SKILL.md` a markdown **sin frontmatter** o **linkear**
  desde un `AGENTS.md`. Alto alcance (un solo provider destraba muchos clientes), pero exige la
  primera `transform` real.
- **Providers con transformación de frontmatter** (Cursor `.mdc`, Continue, Copilot
  `.instructions.md`): mapean con **keys de frontmatter distintas**. **Baja prioridad, frágiles**
  (formatos que cambian seguido), **fuera de la 1.ª iteración**.

El modelo del provider-como-dato es lo que permite que fase 2 sea **agregar filas con `transform`
distinto de identidad**, sin reabrir el diseño de `run_skill_add`.

### Se preserva el version-lock skill==cli

El `--provider` **no toca** la garantía central del 0039 (M2): la skill viaja en el **mismo wheel**
que el CLI. Cambiar de proveedor cambia el **destino** (y, en fase 2, la **forma**) del `SKILL.md`,
pero **siempre** parte de la versión vendida bajo `src/bib2graph/skill/`. No hay forma de instalar,
por ningún provider, una skill que no sea la de la versión instalada del CLI.

## Consecuencias

**Lo que se gana**

- **Se cierra el gatekeeping del 0039.** Un investigador que usa OpenCode (u otro cliente que lea el
  formato de Claude Code) puede instalar la skill en su ruta nativa, no solo en `.claude/skills/`.
- **Extensión barata por diseño.** Sumar un provider de copia-identidad es **una fila de datos**, no
  una rama `if`. La complejidad de `run_skill_add` no crece con la cantidad de providers.
- **La 1.ª iteración es de bajo riesgo.** Todo es `transform = identidad`: reusa `copytree` +
  `_trees_identical` (idempotencia por contenido) tal cual. Ningún parser de frontmatter, ninguna
  degradación de formato en el camino crítico.
- **Version-lock intacto.** El invariante que el 0039 protegía se preserva en **todos** los
  providers.

**Lo que cuesta**

- **`docs/API.md` documenta `--provider` y `skill providers`.** El envelope `--json` `schema="1"`
  sigue **intacto**; el `data` de `skill add` gana el provider elegido (la ruta ya se reporta en
  `install_path`). *(El cambio de `docs/API.md` va en el hito de #193, con su DoD/tests; este ADR
  fija el contrato, no la sintaxis.)*
- **Riesgo de drift: medio.** OpenCode **evoluciona rápido** (ya deprecó `tools`→`permission`), así
  que atar bib2graph a su superficie podría envejecer. **Pero** el subconjunto que importa acá —el
  **formato `SKILL.md`** y la **lectura de `.claude/skills/`**— está anclado a la **compatibilidad
  con Anthropic**, el punto **menos probable** de romperse (OpenCode lo sostiene como su puente de
  interop). El drift vive en **commands/agents** de OpenCode, que bib2graph **no necesita**. Si esa
  compat se rompiera, el fallback sigue siendo el provider `claude-code` + la ruta de interop.
- **La fase 2 arrastra la primera `transform` real.** `agents-md` (degradar frontmatter / linkear
  desde `AGENTS.md`) y los mapeos `.mdc`/`.instructions.md` son trabajo genuino, frágil y aún **no
  decidido en forma final** — quedan como deuda reconocida, no como promesa cerrada.

## Alternativas

- **Ramas `if provider == "opencode": ...` dentro de `run_skill_add`.** **Descartada.** Cada
  provider nuevo agregaría una rama y crecería la complejidad ciclomática; el modelo
  provider-como-dato mantiene el flujo único y vuelve la extensión una fila de tabla. (El 0039 ya
  había dejado el terreno preparado parametrizando `scope`/`dest`.)
- **No agregar `opencode` porque OpenCode ya lee `.claude/skills/`.** **Descartada como única
  respuesta.** Es cierto que la interop lo hace redundante *funcionalmente*, pero el provider nativo
  es una **comodidad legítima** para quien no quiera depender del path de interop de OpenCode — y su
  costo es **una fila de datos con transform identidad**, prácticamente cero.
- **Empezar por `agents-md` (mayor cobertura de clientes).** **Descartada para la 1.ª iteración.**
  Es el provider de **mayor alcance** pero también el de **mayor costo**: exige la primera `transform`
  no-identidad (degradar frontmatter / linkear). El hallazgo de interop hace que
  `claude-code`+`opencode` entreguen valor **hoy, sin transformar nada**; `agents-md` queda como
  **siguiente** paso, no como el primero.
- **Providers `.mdc`/`.instructions.md` (Cursor/Continue/Copilot) en la 1.ª iteración.**
  **Descartada.** Formatos con keys de frontmatter propias, que cambian seguido: alta fragilidad,
  baja prioridad. Se difieren a fase 2.
