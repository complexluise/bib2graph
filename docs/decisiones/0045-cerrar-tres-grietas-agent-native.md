# 0045 — Cerrar las tres grietas agent-native del 0043 como una sola decisión aditiva: `error.subcode`, eco del workspace resuelto y `b2g schema`

- **Estado:** Propuesta · **Implementada en 0.12.0** (#258/#259/#260, aditivo, sin bump de contrato;
  `error.subcode`, `data.workspace` universal + warning de walk-up, comando meta `b2g schema` — ver
  `docs/API.md` §Envelope y §`schema`).
- **Fecha:** 2026-07-18
- **Decidido por:** mixto. La decisión de fondo —**abordar ahora las tres grietas que el
  [0043](0043-posicionamiento-agent-native-cli.md) dejó como roadmap, juntas, como un solo
  ADR-paraguas** (una decisión coherente en vez de tres ADR sueltos)— es **decisión del Product
  Owner humano** (Nota 29 §4). El **encuadre** —que las tres comparten forma (aditivas sobre el
  envelope `schema="1"`), que ninguna rompe el contrato de 0021 y que cada una mapea 1:1 a un issue
  del Bloque B del 0.12.0— es **síntesis de la IA (architect) validada por el PO**.
- **Extiende [0043](0043-posicionamiento-agent-native-cli.md).** El 0043 **nombró** las tres grietas
  como *"roadmap explícito"* y exigió que *"cada una, si se aborda, lo haga de forma aditiva (campos
  nuevos en `data`, un `error.subcode`, un comando meta) y exija su propio ADR/issue antes de tocar
  `API.md`"*. **Este ADR es ese ADR** — pero paraguas: registra la **decisión de cerrar las tres**,
  su forma aditiva concreta y sus invariantes. **No** resuelve la implementación (cada issue trae su
  DoD/tests y el cambio de `docs/API.md` en su hito); registra que **se abordan** y **cómo**.
- **Extiende [0021](0021-cli-agente-native-contrato.md)** (contrato del CLI agente-native) y
  **[0016](0016-maquina-estados-lazo.md)** (FSM del lazo) **sin cambiarlos**. Las tres decisiones son
  **estrictamente aditivas**: (3a) suma un campo opcional dentro de `error`; (3b) suma la clave
  `data.workspace` (ya existente en `status`) al resto de los comandos + un warning; (3c) suma un
  comando **meta** fuera del ciclo. El envelope `schema="1"`
  (`service/envelope.py:26`), los exit codes 0–5 y la FSM **quedan intactos** — sin bump de versión
  de contrato.
- **Relacionada con [0037](0037-superficie-cli-10-verbos-ciclo.md)/[0038](0038-destino-verbos-huerfanos-0037.md)**
  (superficie de **10 verbos del ciclo**) y **[0039](0039-skill-comando-meta-distribucion.md)**
  (precedente del **comando meta fuera del ciclo**): (3c) `b2g schema` se modela como comando meta
  con el **mismo patrón que `skill`** —no transiciona la FSM, no resuelve workspace— así que el
  conteo pasa de *"10 verbos + `skill`"* a *"10 verbos + `skill` + `schema`"*, **sin** tocar los 10
  verbos.
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): las tres son
  legibilidad/introspección de un CLI **determinista**. `b2g schema` vuelca metadatos estáticos del
  contrato; el `error.subcode` deriva de un status HTTP ya conocido puertas adentro; el eco del
  workspace refleja la resolución de ambiente ya existente. bib2graph no embebe ni invoca ningún
  modelo.

## Contexto

El [0043](0043-posicionamiento-agent-native-cli.md) cerró el posicionamiento agent-native del CLI y
dejó, verificadas as-built, **tres grietas como deuda reconocida** — explícitamente **sin
resolverlas**, delegando a un ADR/issue posterior por regla del repo (tocan `docs/API.md`). La
Nota 29 §4 fijó la forma de saldarlas: **no** tres ADR aislados, sino **un ADR-paraguas** que las
registre como una decisión coherente, porque comparten la misma propiedad —son **aditivas sobre el
mismo envelope `schema="1"`**— y se ejecutan juntas en el **Bloque B del release 0.12.0**
(issues #258/#259/#260).

Las tres grietas, re-verificadas contra el código antes de este ADR:

- **(3a) El envelope de error no distingue reintentable de permanente.** El error del envelope hoy
  es solo `{"code", "message"}` (el parámetro `error: dict[str, str] | None` de `build_envelope`,
  `service/envelope.py:29-59`). Un `429` de OpenAlex se mapea a `NetworkError`
  (`sources/openalex.py:540-542`), pero el decorador `handle_errors` **colapsa todo**
  `httpx.HTTPError` a `NETWORK_ERROR`/exit 4 (`cli/_errors.py:140-146`). Un *retry loop* del agente
  no puede separar un `429` transitorio (reintentable con backoff) de un `504`/timeout que exige
  otra acción (simplificar la query). Es la **única grieta con daño documentado en uso real** (0043,
  §Origen): un agente que ante el error opaco **abandonó el CLI y pegó directo contra OpenAlex**,
  perdiendo la procedencia.
- **(3b) Cuál workspace se resolvió es implícito en casi todos los comandos.** El workspace se
  resuelve por precedencia `--workspace` > `B2G_WORKSPACE` > walk-up del cwd
  (`Workspace.resolve`, `workspace.py:239-286`), y el `Workspace` lleva `source` ∈
  `{flag, env, cwd, init}`. **Ya existe el patrón bueno** en `status`, que emite
  `data["workspace"] = {"root", "source"}` (`cli/commands/status.py:193-196`) y lo verbaliza en modo
  humano (`status.py:244`). El resto de los comandos **no lo ecoan**: un agente que cambia de cwd sin
  flag puede operar **en silencio** sobre otra investigación.
- **(3c) La salida está versionada pero no es auto-descriptiva por el mismo canal.** El envelope
  lleva `ENVELOPE_SCHEMA_VERSION = "1"` (`service/envelope.py:26`), pero **no hay introspección por
  el canal de invocación**: el agente en frío debe ir a `docs/API.md` **en prosa** para conocer la
  forma del envelope y los exit codes — el *hop* débil del principio 9 del rubric.

## Decisión

Se **abordan las tres grietas en el Bloque B del 0.12.0**, cada una **aditiva** y con su **issue
propio**. Este ADR registra la decisión y la forma; la implementación (incluido el cambio de
`docs/API.md`) vive en cada hito.

### (3a) Campo aditivo `error.subcode` para el error de red — issue #258

Se agrega un campo **opcional** `subcode` **dentro** del objeto `error` del envelope (junto a `code`
y `message`), poblado **solo** para el `NETWORK_ERROR`/exit 4, con valores tipados:

- **`RATE_LIMITED`** — el upstream devolvió `429` (transitorio; el agente puede reintentar con
  backoff). La información ya existe puertas adentro (`sources/openalex.py:540-542`).
- **`UPSTREAM_TIMEOUT`** — el upstream devolvió `504`/timeout (no reintentable sin cambiar la
  petición; p. ej. simplificar la query).

`error.subcode` es **aditivo y opcional**: los consumidores que solo leen `code`/`exit_code` no se
enteran; `code` sigue siendo `NETWORK_ERROR` y `exit_code` sigue siendo 4. **No** cambia el mapeo de
exit codes ni introduce un exit code nuevo. La ausencia de `subcode` (o `null`) es válida para todo
error que no sea de red o cuyo status no esté tipado.

### (3b) `data.workspace` en todos los comandos + warning cuando la resolución fue por cwd — issue #259

Se **generaliza** al resto de los comandos el patrón que `status` ya implementa
(`cli/commands/status.py:193-196`): cada envelope lleva `data["workspace"] = {"root", "source"}`
con `source` ∈ `{flag, env, cwd, init}`. Además, cuando la resolución fue **implícita** —walk-up del
cwd, `source == "cwd"`— se emite un **warning accionable** en `warnings` (p. ej. *"workspace
resuelto por walk-up del cwd; usá --workspace o B2G_WORKSPACE para fijarlo"*), para que un agente
que cambió de cwd **no opere en silencio** sobre otra investigación.

Es **aditivo**: **no** cambia la precedencia de resolución (`workspace.py:239-286` queda intacto),
solo la **hace legible por el mismo canal**. Los comandos meta que corren **sin** workspace
(`init` cuando crea, `skill`, y el propio `schema` de (3c)) **no** ecoan `data.workspace`.

### (3c) Comando meta `b2g schema` — introspección versionada de la superficie — issue #260

Se agrega `b2g schema`, un comando **meta** que emite por el **mismo canal `--json`** una descripción
legible por máquina de la superficie: el **JSON-schema del envelope**, la **lista de exit codes 0–5**
con su significado y la **versión del contrato** (`ENVELOPE_SCHEMA_VERSION`), cerrando el *hop* a
`docs/API.md` en prosa.

`schema` sigue el **patrón de comando meta de `skill`** ([0039](0039-skill-comando-meta-distribucion.md)):
**no transiciona la FSM**, **no resuelve workspace**, vive **fuera de los 10 verbos del ciclo**. El
conteo de la superficie pasa a *"10 verbos del ciclo + `skill` + `schema`"* — **no** es un 11.º verbo
del ciclo. Emite el envelope estándar con `data` auto-descriptivo.

## Consecuencias

**Lo que se gana**

- **La deuda del 0043 pasa de "nombrada" a "planificada con forma decidida".** Las tres grietas
  tienen ahora su ADR previo (exigido por el propio 0043) y su issue 1:1, listas para el Bloque B sin
  re-litigar el análisis.
- **(3a) cierra el único daño documentado.** El agente distingue `RATE_LIMITED` (reintentar) de
  `UPSTREAM_TIMEOUT` (cambiar la petición) sin rutear alrededor del motor — recuperando la
  procedencia que es la razón de ser de la herramienta.
- **(3b) elimina el fallo silencioso de workspace.** Todo comando ecoa cuál investigación tocó; el
  walk-up implícito deja de ser invisible.
- **(3c) vuelve la superficie auto-descriptiva.** Un agente en frío aprende el contrato por el mismo
  canal que usa para actuar, sin salir a la prosa.
- **Coherencia registrada.** Al ser un solo ADR-paraguas, las tres comparten invariantes explícitos
  (envelope `schema="1"`/exit/FSM intactos, sin IA, `schema` como meta) — no hay tres decisiones que
  puedan derivar por separado.

**Lo que cuesta**

- **Tres cambios a `docs/API.md` en el 0.12.0.** Cada issue debe documentar su forma aditiva
  (`error.subcode`, `data.workspace` universal, comando `schema`) al mergear; el contrato publicado
  crece aunque el schema del envelope **no** bumpee versión.
- **Disciplina de "aditivo, no rompé".** Cada PR del Bloque B debe verificar que consumidores que
  ignoran los campos nuevos siguen funcionando; un cambio que altere `code`/`exit_code`/FSM
  **contradice este ADR** y exige reabrirlo.
- **El conteo de la superficie vuelve a moverse.** *"10 + skill + schema"* debe reflejarse en
  `docs/API.md`, el `llms.txt` y la skill ([0041](0041-documentacion-por-superficie-de-entrega.md))
  cuando (3c) se implemente.

## Alternativas

- **Tres ADR aislados (uno por grieta).** **Descartada** por el PO (Nota 29 §4): las tres comparten
  forma (aditivas sobre el mismo envelope) y se ejecutan en el mismo bloque; un paraguas mantiene los
  invariantes comunes en un solo lugar y evita tres encabezados que repiten "no rompe el contrato".
  Cada grieta conserva su **issue propio** para el DoD/tests — el paraguas es de **decisión**, no de
  implementación.
- **Resolver la implementación en este ADR.** **Descartada:** tocar `docs/API.md` y el código es el
  trabajo de cada hito (#258/#259/#260) con su DoD y tests TDD; este ADR **registra la decisión**, no
  la codea (regla del repo).
- **(3a) con un exit code nuevo en vez de `subcode`.** **Descartada:** rompería el contrato de exit
  codes 0–5 de 0021 (deja de ser aditivo). El status ya se distingue **dentro** de exit 4; el campo
  aditivo lo expone sin tocar el mapeo.
- **(3b) cambiar la precedencia de resolución o exigir `--workspace` siempre.** **Descartada:**
  mataría la resolución por ambiente que hace a `b2g` ergonómico dentro de una carpeta de
  investigación (0029). La grieta es de **legibilidad** del resultado, no de la precedencia; se cierra
  ecoando + avisando, sin cambiar cómo se resuelve.
- **(3c) `b2g schema` como 11.º verbo del ciclo.** **Descartada:** no mapea ningún estado de la FSM;
  es introspección meta. Modelarlo como verbo del ciclo contradiría 0037/0038 (los 10 verbos **son**
  el ciclo). Sigue el precedente meta de `skill` (0039).
- **(3c) dejar la auto-descripción solo en `docs/API.md`/`llms.txt`.** **Descartada:** es
  exactamente el *hop* débil que la grieta señala — el agente en frío no debería salir del canal de
  invocación para conocer el contrato. `llms.txt` (0041) **complementa**, no reemplaza, la
  introspección por el mismo canal.
