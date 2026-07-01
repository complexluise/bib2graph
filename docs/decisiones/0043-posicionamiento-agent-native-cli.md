# 0043 — bib2graph implementa deliberadamente el contrato CLI-para-agentes: las relajaciones de trust son por bajo blast radius; tres grietas son roadmap explícito

- **Estado:** Aceptada
- **Fecha:** 2026-06-30
- **Decidido por:** mixto. Las decisiones de fondo —**(1)** ratificar que el CLI `b2g`
  **implementa deliberadamente** el contrato CLI-para-agentes (postura de diseño, no accidente),
  **(2)** declarar que las relajaciones de los principios de *trust & safety* (4–7) son **decisión
  por bajo blast radius**, no huecos, y **(3)** nombrar tres grietas como **roadmap reconocido** sin
  resolverlas en este ADR— son **decisiones del Product Owner humano**. El **encuadre** que las
  ordena —la auditoría del CLI contra el *Rubric for Agent-Native CLI Design* (nueve principios),
  separando *hueco* de *decisión de diseño*— es **síntesis de la IA (architect) validada por el PO**.
- **Extiende [0021](0021-cli-agente-native-contrato.md)** (Contrato del CLI agente-native). 0021 fijó
  el **contrato concreto** (set de subcomandos, envelope `schema="1"`, exit codes 0–5 por tipo de
  excepción, estado en el archivo y no en la sesión). Este ADR **no cambia ese contrato**: lo
  **ratifica como postura de diseño explícita** y le agrega dos capas que 0021 no declaraba — el
  *porqué* de las relajaciones de trust y la *deuda de roadmap* nombrada. Es un ADR-paraguas de
  **posicionamiento** anclado en 0021, no una enmienda que toque el envelope, los exit codes ni la FSM.
- **Relacionada con:** [0010](0010-agente-native-columna.md) (la CLI agente-native como **columna
  primaria** — este ADR explicita la postura que 0010 fijó como principio),
  [0037](0037-superficie-cli-10-verbos-ciclo.md)/[0038](0038-destino-verbos-huerfanos-0037.md) (la
  superficie de **10 verbos** del ciclo; la grieta (9) abajo se resuelve, si se aborda, como **comando
  meta fuera de los 10** —patrón de [0039](0039-skill-comando-meta-distribucion.md)—, no como 11° verbo
  del ciclo), [0039](0039-skill-comando-meta-distribucion.md) (precedente de comando meta auto-descriptivo
  fuera del ciclo), [0041](0041-documentacion-por-superficie-de-entrega.md) (`docs/API.md` y el `llms.txt`
  **publican** el mismo contrato que este ADR posiciona; la grieta (9) reduciría el *hop* a la doc en prosa).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): es **postura de
  diseño y deuda declarada** sobre un CLI determinista. bib2graph no embebe ni invoca ningún modelo;
  el "para agentes" describe al **consumidor** del contrato (un LLM por subprocess + JSON), no una
  capacidad generativa del motor.
- **No cambia ningún contrato público.** El envelope `schema="1"`, los exit codes 0–5 y la FSM del
  ciclo ([0021](0021-cli-agente-native-contrato.md)/[0016](0016-maquina-estados-lazo.md)) quedan
  **intactos**. Las tres grietas, si se abordan, lo hacen de forma **aditiva** (campos nuevos en `data`,
  un `error.subcode`, un comando meta) — cada una **exige su propio ADR/issue** antes de tocar `API.md`.
- **Origen:** unificación de **dos auditorías independientes** (PO + un agente) del CLI `b2g` contra
  el *Rubric for Agent-Native CLI Design*, reconciliadas **contra el código** (verificadas as-built
  con `archivo:línea`). Encuadre empírico de uso real: un agente que, ante un error de red opaco,
  **abandonó la CLI y pegó directo contra OpenAlex con `urllib`**, perdiendo la procedencia que es la
  razón de ser de la herramienta. *(Las notas de auditoría son trabajo local; este ADR se sostiene
  solo: las afirmaciones falsables van ancladas con `archivo:línea`.)*

## Contexto

El ADR [0010](0010-agente-native-columna.md) fijó el **principio** ("la CLI agente-native es
superficie primaria") y el [0021](0021-cli-agente-native-contrato.md) fijó el **contrato concreto**.
Lo que **ninguno de los dos registró** es una cosa que en la práctica ya está decidida y conviene
volver inmutable: que ser *agent-native* es una **postura de diseño deliberada y verificable**, no un
subproducto del estilo de implementación — y, sobre todo, **dónde el contrato deliberadamente se
relaja y por qué**.

Una auditoría del CLi contra los nueve principios de un rubric de diseño agent-native (legibilidad ·
trust & safety · composabilidad/estabilidad) arrojó, verificado as-built:

- **Legibilidad (1–3): sólida.** Salida estructurada por un único envelope versionado
  (`{schema, ok, command, exit_code, data, warnings, error}`, `ENVELOPE_SCHEMA_VERSION = "1"`,
  `service/envelope.py:26`), una sola flag de salida estructurada (`--json`, `cli/_options.py:85`; o
  `B2G_JSON` por entorno), y exit codes 0–5 mapeados por tipo de excepción con una función pura
  (`service/errors.py:71-97`). **Caveat:** dentro de `NETWORK_ERROR`/exit 4, no se distingue un `429`
  reintentable de un `504` no-reintentable (`sources/openalex.py:150`, `cli/_errors.py:140-145`).
- **Trust & safety (4–7): relajada.** No hay `--dry-run` universal, ni *tagging* de canal de confianza
  en los inputs (`seed.py:215`), ni *grading* legible de blast radius por comando (no hay `--force` ni
  confirmación). El extremo destructivo del espectro —borrado de recursos— **directamente no existe**.
- **Composabilidad/estabilidad (8–9): sólida con dos caveats.** Cada comando es invocable en frío y el
  canal entre invocaciones es **el archivo** (`library.duckdb` del workspace), no memoria de sesión —
  la propiedad que hace a `b2g` sobrevivir la compactación de contexto. *Caveat (8):* **cuál** workspace
  se resuelve por ambiente (precedencia `--workspace` > `B2G_WORKSPACE` > walk-up del cwd,
  `workspace.py:246-286`); un agente que cambia de cwd sin flag puede operar en silencio sobre otra
  investigación. *Caveat (9):* la **salida** está versionada, pero **no hay auto-descripción por el mismo
  canal de invocación** (no existe `b2g schema`/introspección); el agente en frío debe ir a `docs/API.md`
  en prosa — el *hop* débil.

El rubric pide **no sumar** los nueve en un puntaje, sino mirar dónde **dos grietas juntas** crean
riesgo. La pregunta que este ADR cierra no es "¿cuántos principios cumple?", sino **qué es decisión y
qué es deuda** — para que la próxima auditoría (humana o de agente) no reabra lo ya decidido ni pierda
de vista lo que sigue abierto.

## Decisión

### (1) bib2graph implementa deliberadamente el contrato CLI-para-agentes

El CLI `b2g` **implementa, por postura de diseño y no por accidente**, el contrato CLI-para-agentes
que [0021](0021-cli-agente-native-contrato.md) fijó: **envelope JSON versionado** (`schema="1"`),
**exit codes 0–5 tipados** por clase de error, **comandos self-contained** (estado en el archivo, no
en la sesión) e **identidad de recurso explícita** (papers por `--id` con resolución
`id > doi > source_id`, `read.py:205`, ADR [0036](0036-identidad-source-id-agnostica-doi-ancla.md)).
Esto **ratifica y se apoya en 0021**: aquel ADR decidió *qué* es el contrato; éste registra que
**sostenerlo es un objetivo de diseño de primera clase**, falsable con `archivo:línea`, y por tanto un
criterio contra el cual se evalúan cambios futuros de superficie. Un PR que erosione la legibilidad
estructurada (p. ej. reintroducir prosa en stdout en modo `--json`, o partir el contrato de salida en
variantes `--output`/`--pretty`) **contradice este ADR** y exige justificarse.

### (2) Las relajaciones de los principios 4–7 son decisión por bajo blast radius, no huecos

Las relajaciones de *trust & safety* (reversibilidad parcial, sin *tagging* de canal, riesgo plano sin
*grading* legible) son **decisión deliberada**, coherente con el *fail-open advisory* de 0021. El
fundamento es el **bajo blast radius** de esta herramienta, verificable: es un CLI de **analítica
local** sobre un store **DuckDB local single-writer** ([0009](0009-biblioteca-viva-duckdb.md)/[0019](0019-concurrencia-diferida.md)),
**sin borrado de recursos** (no hay `delete/reset/purge`), **sin estado multi-tenant ni credenciales
compartidas**, y con **daño recuperable por snapshot** (`snapshot restore` como red). El propio rubric
lo dice en su *worked example*: un CLI de analítica local no necesita la misma postura de trust que uno
que borra producción.

**No se adopta fricción de confirmación interactiva** (`--force`, prompts, gates) porque **mataría la
autonomía del agente** —el `b2g` está pensado para correrse por subprocess sin humano en el loop— y el
daño que evitaría es local y reversible. Esta es la decisión explícita: la planicie de riesgo es
**benigna por construcción**, no un descuido a corregir. Quien proponga sumar fricción de confirmación
a un verbo del ciclo está **reabriendo esta decisión** y debe traer un ADR.

> **Frontera de la decisión (2):** "relajado por diseño" cubre el espectro **actual** del CLI (lectura
> · escritura idempotente que transiciona el FSM · curación transversal persistente · `restore`
> irreversible-pero-local). **No** es licencia para introducir un blast radius nuevo (borrado remoto,
> multi-tenant, mutación destructiva no recuperable) sin reevaluar la postura de trust. Si el espectro
> cambia, este ADR no lo ampara.

### (3) Tres grietas se declaran roadmap explícito (deuda reconocida, no resuelta acá)

Las tres se nombran como **deuda reconocida**; **ninguna se resuelve en este ADR** y cada una, al
tocarse, **exige su propio ADR/issue** porque toca `docs/API.md`. Caben las tres **sin romper** el
contrato de 0021 ni la superficie de 10 verbos de [0037](0037-superficie-cli-10-verbos-ciclo.md):

- **(3a) Subcódigo de error de red — `RATE_LIMITED` (429) vs `UPSTREAM_TIMEOUT`/`QUERY_TOO_COMPLEX`
  (504).** Hoy todo cae en `NETWORK_ERROR`/exit 4 (`cli/_errors.py:140-145`), aunque el status code se
  distingue **internamente** (`openalex.py:150`, `_RETRY_STATUS_CODES` en `openalex.py:70`). Un *retry
  loop* del agente no puede separar transitorio (reintentable con backoff) de permanente (hay que
  simplificar la query). Es la **única grieta con daño documentado en uso real**: el desenlace fue un
  agente ruteando **alrededor** del motor (directo a OpenAlex con `urllib`), perdiendo la trazabilidad.
  Fix aditivo (un `error.subcode` en el envelope; la información ya existe puertas adentro), efecto grande.
- **(3b) Volver legible el workspace resuelto.** La identidad del *recurso* es explícita, pero **cuál**
  workspace se eligió por ambiente es implícito (`workspace.py:246-286`). Recomendación: **eco del
  workspace en el envelope** (p. ej. en `data`) o **warning** cuando se resolvió por walk-up del cwd
  (no por flag ni env explícitos), para que un agente que cambió de cwd no opere en silencio sobre otra
  investigación. Aditivo; no cambia la precedencia.
- **(3c) `b2g schema` — introspección versionada de la superficie.** Un comando **meta** que vuelque
  comandos, flags por comando y el JSON-schema del envelope con su `ENVELOPE_SCHEMA_VERSION`, por el
  **mismo canal de invocación** que el agente ya usa para actuar — cerrando el *hop* a `docs/API.md` en
  prosa. Debe modelarse como **comando meta fuera de los 10 verbos del ciclo** (no transiciona FSM, no
  toca workspace), siguiendo el precedente de `skill` ([0039](0039-skill-comando-meta-distribucion.md)):
  conteo "10 + `skill` + `schema`", no "11 verbos del ciclo".

## Consecuencias

**Lo que se gana**

- **La postura agent-native deja de ser folclore.** Pasa a ser **decisión registrada e inmutable**: la
  próxima auditoría parte de "esto ya está decidido" en vez de re-litigar si `b2g` "es de verdad"
  agent-native. El criterio para evaluar cambios de superficie queda explícito.
- **Las relajaciones de trust dejan de leerse como huecos.** Cualquier revisor (o agente) que mida `b2g`
  contra un rubric genérico y reporte "fallan 4–7" tiene la respuesta registrada: **es por blast
  radius**, con la frontera de cuándo deja de valer. Se evita el churn de "arreglar" no-problemas.
- **La deuda real queda nombrada y acotada.** Tres grietas con *archivo:línea*, ordenadas por palanca,
  cada una aditiva y sin romper contrato — listas para abrir issues sin re-descubrir el análisis.

**Lo que cuesta**

- **Disciplina de coherencia en cada cambio de superficie.** Este ADR es ahora un criterio: un PR que
  erosione legibilidad estructurada o sume fricción de confirmación a un verbo del ciclo lo **contradice**
  y debe justificarse con ADR. Es trabajo de revisión que antes no existía explícitamente.
- **Las tres grietas siguen abiertas hasta que alguien las tome.** Declararlas roadmap **no** las cierra;
  en particular (3a) tiene daño documentado y cada ronda que pase sin subcódigo de red mantiene el riesgo
  de que un agente vuelva a rutear alrededor del motor.
- **Cada grieta abierta arrastra su propio ADR/issue.** Por tocar `docs/API.md`, ninguna se mergea "de
  paso": el costo de cerrar (3a)/(3b)/(3c) incluye su registro de decisión, aunque el código sea chico.

## Alternativas

- **Dejarlo como nota-mapa, sin graduar a ADR.** **Descartada:** las notas de auditoría son trabajo
  local que no se commitea; la postura y la separación hueco/decisión se perderían y la próxima auditoría
  re-litigaría lo ya decidido. El valor está precisamente en volver la decisión **inmutable y citable**.
- **Enmendar 0021 en vez de un ADR nuevo.** **Descartada:** 0021 fija el **contrato** (envelope/exit/FSM);
  este ADR no lo cambia, agrega una capa de **posicionamiento + deuda**. Meterlo como enmienda de 0021
  mezclaría "qué es el contrato" con "por qué la postura y qué falta", y 0021 ya carga varias enmiendas
  de superficie. Un ADR-paraguas que **extiende** 0021 mantiene cada decisión legible por separado.
- **Resolver las tres grietas en este mismo ADR.** **Descartada:** cada una toca `docs/API.md` (contrato
  público) y por regla del repo exige su propio ADR/issue con su DoD y tests. Mezclarlas acá produciría un
  ADR que decide cinco cosas a la vez y un PR imposible de revisar. Este ADR **nombra** la deuda; no la salda.
- **Adoptar fricción de confirmación (`--force`/prompts) para "cumplir" trust 4–7.** **Descartada:** es
  exactamente lo que (2) rechaza — mataría la autonomía del agente para prevenir un daño local y reversible.
  El rubric mismo desaconseja imponer postura de producción a una herramienta de analítica local.
- **Cerrar el caveat de red (3a) re-exponiendo `--api-key` o tocando el retry interno.** Fuera de alcance:
  la grieta es de **legibilidad del outcome** (subcódigo en el envelope), no del retry —que ya existe
  interno (`openalex.py:70`)— ni de la credencial —que ya entra solo por env `OPENALEX_API_KEY`
  (`openalex.py:413`); el único `--api-key` literal vive en el alias deprecado `enrich` que se retira en
  0.11.0 ([0038](0038-destino-verbos-huerfanos-0037.md)). El footgun de la credencial **se cierra solo**
  con esa deprecación; la acción mínima es **no re-introducir** `--api-key` en los verbos vivos.
