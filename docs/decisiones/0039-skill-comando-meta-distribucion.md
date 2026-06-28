# 0039 — Distribución de la skill de Claude Code: `b2g skill add` como 2.º comando meta (junto a `gui`), vendoreada en el wheel con version-lock skill==cli

- **Estado:** Aceptada
- **Fecha:** 2026-06-28
- **Decidido por:** **Product Owner humano** (decisión acordada 2026-06-28). El mecanismo de
  distribución (vendoring en el wheel como fuente del paquete, comando `b2g skill add` con
  `--user|--project|--force`, version-lock skill==cli) y el descarte del extra `[skill]` y del
  camino plugin+marketplace como primario son **decisiones del PO**. El **encuadre** —*"la mejor
  forma de usar bib2graph es pedirle a Claude que lo use; la skill es esa puerta, y es un comando
  **meta/admin**, no un paso del ciclo"*— y la categorización como **2.ª excepción meta junto a
  `gui`** son **síntesis de la IA (architect) validada por el PO**.
- **Enmienda a:** [0038](0038-destino-verbos-huerfanos-0037.md) (destino de los huérfanos del 0037).
  El 0038 estableció la categoría *"verbo fuera del set de 10, gobernado por su propio ADR"* para
  `gui` (excepción explícita, no un paso del ciclo). Este ADR **agrega una 2.ª excepción de la misma
  clase**: `skill` es un comando **meta/distribución**, no un verbo del ciclo de investigación. **No
  revierte** el 0037 ni el 0038: el conteo de **10 verbos del ciclo sigue siendo verdad**; la
  superficie pasa a leerse como *"10 verbos del ciclo + `gui` (GUI) + `skill` (meta/distribución)"*.
  El **envelope `schema="1"`, los exit codes y el FSM del lazo se preservan** (ADR
  [0021](0021-cli-agente-native-contrato.md) §C/§D/§F).
- **Relacionada con:** [0037](0037-superficie-cli-10-verbos-ciclo.md) (la superficie ES el ciclo:
  `skill` **no** compite con `status` ni con ningún verbo del ciclo; vive **al lado**, no dentro),
  [0028](0028-arquitectura-gui-api-capa-servicios.md) (precedente del **vendoring de assets en el
  wheel**; `gui/static` usa `force-include` por ser artefacto **gitignored** — la skill **no** lo
  necesita, ver §Mecanismo),
  [0010](0010-agente-native-columna.md)/[0021](0021-cli-agente-native-contrato.md) (CLI
  agente-native: la skill **enseña los 10 verbos** del 0037 a un agente end-user),
  [0029](0029-workspace-por-investigacion.md) (`skill add` es un comando **meta global** que
  funciona **sin workspace**, igual que `init` cuando crea uno).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): la skill es
  **markdown** (instrucciones + `reference/`) que un agente Claude Code lee; bib2graph no embebe ni
  invoca ningún modelo. La IA está en el **cliente del usuario** (su Claude Code), no en el producto.
- **Origen:** epic [#188](https://github.com/complexluise/bib2graph/issues/188). Encuadre de
  posicionamiento: *"el antídoto al sesgo del related work"* (#187) — la skill es la forma en que un
  usuario hispano corre el ciclo one-shot pidiéndole a Claude que use bib2graph.

## Contexto

El 0037 dejó la superficie CLI consolidada en **10 verbos que mapean el ciclo de investigación**,
legibles por un agente sin manual. El 0038 cerró el conteo despachando los huérfanos y fijó la
categoría de la **excepción meta**: `gui` se mantiene **fuera del set de 10** porque es una
**superficie distinta** (lanzador de la GUI local), gobernada por su propio ADR (0027/0028), no un
paso del ciclo agents-first.

Falta una pieza del posicionamiento *"la mejor forma de usar bib2graph es pedirle a Claude que lo
use"*: una **skill de Claude Code para el usuario final** que (1) **entreviste** al investigador
sobre su pregunta y sus fuentes, y (2) le **enseñe al agente la mejor forma de manejar bib2graph**
—es decir, los 10 verbos del 0037 y la historia one-shot `init→seed→chain→build→read`, leyendo
`status` como mapa—. La skill es **markdown sin dependencias Python**: un `SKILL.md` + una carpeta
`reference/`.

El problema es de **distribución y de versionado**, no de diseño del ciclo:

- **¿Dónde vive la skill?** Si se publica como un paquete/extra aparte, su versión **desacopla** de
  la del CLI: una skill v0.10 podría quedar instruyendo a un agente que corre un CLI v0.11 con la
  superficie ya cambiada (los 9 aliases del 0038 retirados en 0.11.0). La skill **enseña los 10
  verbos**; si enseña verbos que ya no existen, miente.
- **¿Cómo se instala?** Claude Code descubre skills en `~/.claude/skills/<nombre>/` (user) o
  `.claude/skills/<nombre>/` (project). Un `pip install` **no escribe** en esas rutas; instalar una
  skill es **copiar archivos** a un directorio del cliente, no resolver dependencias Python.

La pregunta de este ADR es: **¿cómo se empaqueta y se instala la skill de modo que su versión quede
amarrada a la del CLI, sin agregar superficie al ciclo?**

## Decisión

**bib2graph distribuye una skill de Claude Code end-user, vendoreada dentro del wheel bajo
`src/bib2graph/skill/`, y la instala con un comando meta nuevo `b2g skill add` que la copia al
directorio de skills del cliente.** `skill` es la **2.ª excepción meta explícita** (junto a `gui`):
un comando **meta/distribución**, NO un paso del ciclo de investigación. El contrato de salida
(envelope `schema="1"`/exit/FSM) **no cambia**.

### `skill` es comando meta, no un verbo del ciclo (2.ª excepción junto a `gui`)

- **No mapea ningún paso del ciclo** INIT→SEED→CHAIN→CURATE→BUILD→READ→EXPORT/SNAPSHOT. No produce
  ni transforma corpus ni redes. **No compite con `status`** (el mapa del ciclo) ni con ningún verbo
  del 0037: vive **al lado** de la superficie, no dentro.
- Es de la **misma clase que `gui`**: una superficie distinta gobernada por su propio ADR (este).
  El 0038 categorizó `gui` como *"se mantiene, fuera del set de 10"*; `skill` reusa esa categoría.
- **Reconciliación del conteo:** los **10 verbos del ciclo del 0037 siguen siendo verdad**. La
  superficie pasa a leerse como **"10 verbos del ciclo + `gui` (GUI) + `skill` (meta/distribución)"**.
  El conteo de 10 es **verificable contra `b2g --help`**; las dos excepciones meta están
  **documentadas**, no disimuladas (mismo criterio de honestidad del 0038: excluir explícitamente es
  más honesto que omitir).

### Mecanismo: vendoring + version-lock skill==cli

- **(M1) La skill vive vendoreada en el wheel bajo `src/bib2graph/skill/`** (`SKILL.md` +
  `reference/`). Como es **fuente commiteada bajo el paquete**, la incluye `packages =
  ["src/bib2graph"]` **sin** `force-include`. (El frontend `gui/static/` **sí** necesita
  `force-include` por ser un artefacto **gitignored**, ADR 0028 G5; la skill no — y meterla ahí la
  **duplicaría y rompería el build**.) *(El `pyproject.toml` es trabajo del `coder`; este ADR fija el
  mecanismo, no la sintaxis.)*
- **(M2) Garantía central: skill-version == cli-version.** Como la skill viaja **en el mismo wheel**
  que el CLI, instalar `bib2graph==X.Y.Z` trae una skill que **enseña exactamente los verbos de esa
  versión**. El vendoring en el mismo artefacto **es** el version-lock; no hay forma de tener una
  skill v0.10 sobre un CLI v0.11. Esto es lo que cierra el riesgo de "la skill miente".
- **(M3) `b2g skill add [--user|--project] [--force]`** copia la skill vendida al directorio de
  skills del cliente:
  - **`--user`** (default) → `~/.claude/skills/bib2graph/`.
  - **`--project`** → `.claude/skills/bib2graph/` (relativo al cwd).
  - **`--force`** → pisa una instalación existente; sin él, el comando es **idempotente** (si ya
    está en la versión vendida, no hace nada y lo reporta).
  - **Funciona sin workspace:** es un comando **meta global**, no requiere `workspace.json` ni
    resolución de ambiente (como `init` al crear, o como `gui`/`resolve` que no transicionan).
  - **Emite el envelope `--json` `schema="1"` SIN transición de FSM** (igual que `gui`/`resolve`):
    es ortogonal al lazo. *(El `data` emitido es `{install_path, scope, installed, already_present}`,
    `schema="1"` intacto; documentado en `docs/API.md`.)*

### La historia de uso (cómo llega la skill al investigador)

```text
$ pip install bib2graph        # trae el CLI + la skill vendoreada (mismo wheel, misma versión)
$ b2g skill add                # copia la skill a ~/.claude/skills/bib2graph/ (--user default)
# en Claude Code: "usá bib2graph para armar la red de citación de estos papers…"
# el agente lee la skill, entrevista al investigador y corre el ciclo one-shot del 0037
```

La skill es la materialización del mensaje *"la mejor forma de usar bib2graph es pedirle a Claude
que lo use"*: enseña el ciclo (`init→seed→chain→build→read`, `status` como mapa) que el 0037 hizo
legible para un agente.

## Consecuencias

**Lo que se gana**

- **Version-lock por construcción.** La skill y el CLI **no pueden** divergir: viajan en el mismo
  wheel. La skill siempre enseña los verbos que el CLI realmente expone (incluido el corte de los 9
  aliases en 0.11.0, ADR 0038 P1).
- **Instalación de un paso, sin Node ni deps extra.** `pip install bib2graph && b2g skill add`:
  markdown copiado a `~/.claude/skills/`, sin tocar `[project.dependencies]`.
- **El conteo del ciclo se mantiene honesto.** 10 verbos + 2 excepciones meta **documentadas**
  (`gui`, `skill`). El 0037/0038 no se debilita: `skill` no entra al ciclo, lo **acompaña**.
- **Reusa un precedente probado, más simple.** El ADR 0028 (G5) ya vendorea assets en el wheel; la
  skill se monta sobre la misma idea pero al ser **fuente commiteada** entra por `packages`, sin tocar
  `force-include` ni infraestructura nueva.

**Lo que cuesta**

- **`docs/API.md` documenta una 2.ª excepción meta**: `skill` con `skill add` y sus flags, la
  reconciliación del conteo ("10 + gui + skill") y la nota de empaquetado (la skill entra por
  `packages`, **no** por `force-include`). El `data` del envelope es `{install_path, scope, installed,
  already_present}` (`schema="1"` intacto).
- **El wheel engorda con la skill** (markdown, peso menor); al ser fuente del paquete entra por
  `packages` sin config extra. *(`pyproject.toml`/CI son del `coder`.)*
- **Mantener la skill al día con el ciclo.** Si el ciclo del 0037 cambia (futuro ADR), la skill
  —que lo enseña— debe actualizarse en el mismo cambio. El version-lock lo hace **detectable** (van
  juntas) pero no **automático**: editar el ciclo sin editar la skill es drift a vigilar.

## Alternativas

- **El extra `pip install bib2graph[skill]`.** **Descartada.** Un extra de pip solo agrega
  **dependencias Python**; **no escribe** en `~/.claude/skills/`. La skill es **markdown sin deps**:
  no hay nada que un extra resuelva. El acto de instalar una skill es **copiar archivos** al
  directorio del cliente —eso lo hace `b2g skill add`, no `pip`—. Un extra `[skill]` daría la falsa
  impresión de que instalarlo deja la skill lista, cuando no toca el directorio de Claude Code.
- **Plugin + marketplace de Claude Code (`/plugin install`).** **Descartada como primaria** (dejada
  como **ruta futura mencionable**). Un plugin distribuido por marketplace **desacopla el
  versionado**: la skill viviría en un repo/marketplace con su propia cadencia de release, y volvería
  el riesgo que M2 cierra (skill v0.10 sobre CLI v0.11). El vendoring en el wheel da el version-lock
  gratis; el plugin lo rompería. Si en el futuro se quiere descubribilidad vía marketplace, puede
  convivir **como espejo** de la skill vendoreada, no como su fuente de verdad.
- **Meter `skill` dentro del set de 10.** **Descartada** (mismo criterio que el 0038 rechazó para
  `gui`): `skill add` no es un paso del ciclo de investigación; es distribución/admin. Forzarlo al
  set mezcla dos contratos. Excluirlo **explícitamente** —2.ª excepción meta documentada— es más
  honesto que disimularlo en el conteo.
- **Publicar la skill en un repo aparte / como descarga manual.** **Descartada:** rompe el
  version-lock (M2) y agrega un paso de instalación que `b2g skill add` resuelve en uno. El usuario
  que ya tiene el CLI ya tiene la skill correcta.
