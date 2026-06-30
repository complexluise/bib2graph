# 0040 — Retirar la GUI local de la librería: el core es CLI/agente-native sobre la biblioteca viva

- **Estado:** Aceptada
- **Fecha:** 2026-06-28
- **Decidido por:** **Product Owner humano** (decisión tomada 2026-06-28). El retiro de la GUI local
  (subcomando `b2g gui`, API local FastAPI, SPA `frontend/`, extra `[gui]`, vendoreo del frontend en
  el wheel) y su carácter **BREAKING** son **decisiones del PO**. El **encuadre** —*"la GUI no es el
  foco; el core es CLI/agente-native sobre la biblioteca viva, y el camino de adopción es la skill
  (ADR 0039), no una SPA local"*— es **síntesis de la IA (architect) validada por el PO**.
- **Supersede a:** [0027](0027-pivote-posicionamiento-gui-local.md) (pivote de posicionamiento: GUI
  local opt-in) y [0028](0028-arquitectura-gui-api-capa-servicios.md) (arquitectura GUI/API/frontend +
  empaquetado `[gui]`). Ambos quedan como **historia inmutable** (no se reescriben ni se borran): este
  ADR revierte la **dirección** que fijaron, no su registro. El pivote del 0027 (GUI como 4º frontend)
  y la arquitectura de tres frontends del 0028 dejan de ser el TARGET del proyecto.
- **Enmienda a:** [0038](0038-destino-verbos-huerfanos-0037.md) (destino de los verbos huérfanos del
  0037). El 0038 fijó que `gui` *"se mantiene, fuera del set de 10"* como **excepción meta gobernada
  por su propio ADR** (0027/0028). Este ADR **retira** esa excepción: `gui` deja de existir como verbo.
  El conteo del 0037 **no se debilita** —los 10 verbos del ciclo siguen siendo verdad—; la superficie
  pasa a leerse como **"10 verbos del ciclo + `skill` (meta/distribución)"**, sin `gui`.
- **No revierte el contrato del lazo:** el **envelope `schema="1"`, los exit codes y el FSM** se
  preservan (ADR [0021](0021-cli-agente-native-contrato.md) §C/§D/§F). La **capa de servicios neutral
  `service/`** —que el 0028 introdujo y elevó al contrato (envelope/errores/exit-code)— **se conserva**:
  es la fuente única que usa el CLI. Lo que se retira es el **adaptador de transporte HTTP** (la API) y
  su frontend, no la capa neutral.
- **Relacionada con:** [0010](0010-agente-native-columna.md)/[0021](0021-cli-agente-native-contrato.md)
  (CLI agente-native como columna primaria: queda como la **única** frontera),
  [0037](0037-superficie-cli-10-verbos-ciclo.md) (la superficie ES el ciclo de 10 verbos),
  [0039](0039-skill-comando-meta-distribucion.md) (la skill de Claude Code es el **camino de adopción**
  que reemplaza el rol que el 0027 daba a la GUI; tras este ADR, `skill` queda como la **única**
  excepción meta, no la "2.ª junto a `gui`"),
  [0005](0005-dependencias-extras.md) (matriz de extras: el extra `[gui]` = `fastapi` + `uvicorn` se
  elimina, como antes `[llm]`/`[dedup]`),
  [0032](0032-capa-servicios-duena-del-flujo.md)/[0033](0033-producto-library-centric-grafo-proyeccion.md)
  /[0034](0034-etiquetado-tabla-tags-lateral.md) (propuestas library-centric que colgaban de la GUI:
  quedan **fuera del alcance de la librería**; viven en el producto separado, no en bib2graph).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): es retiro de
  superficie; no toca el núcleo determinista.
- **Origen:** issue [#190](https://github.com/complexluise/bib2graph/issues/190) (*"retirar la GUI
  local (BREAKING) — fuera del foco"*). Encuadre de frontera bib2graph (motor determinista) vs.
  producto (Zotero/Mendeley + IA-asiste). La limpieza **profunda** de la documentación (los ~53
  marcadores AS-BUILT de la epic GUI) se trata aparte en
  [#191](https://github.com/complexluise/bib2graph/issues/191).

## Contexto

El ADR [0027](0027-pivote-posicionamiento-gui-local.md) (firmado 2026-06-18) pivoteó el
posicionamiento: una **GUI local "tool for thought"** opt-in para el investigador semi-técnico, como
**4º frontend** sobre la biblioteca viva. El ADR [0028](0028-arquitectura-gui-api-capa-servicios.md)
bajó la arquitectura: una **capa de servicios neutral** (`service/`) con **tres frontends de
frontera** —CLI, **API local FastAPI** (`src/bib2graph/api/`) y **SPA** (`frontend/`)— más el
empaquetado del frontend en el wheel (extra `[gui]`, `force-include` de `gui/static/`). La epic
[#34](https://github.com/complexluise/bib2graph/issues/34) llegó a **AS-BUILT G1–G5** (API + SPA +
empaquetado), gateada por la validación de un tercero sobre el caso real.

Esa validación no llegó, y el foco del proyecto se aclaró por otro lado. El posicionamiento de
0.10.0 es **agents-first**: la superficie CLI de 10 verbos (ADR [0037](0037-superficie-cli-10-verbos-ciclo.md))
mapea el ciclo de investigación para que **un agente lo corra one-shot**, y la **skill de Claude
Code** (ADR [0039](0039-skill-comando-meta-distribucion.md)) es la puerta de adopción —*"la mejor
forma de usar bib2graph es pedirle a Claude que lo use"*—. En ese marco, la GUI local:

- **Compite por foco con el core CLI/agente-native** sin un caso validado que la justifique.
- **Carga superficie pesada**: una API HTTP de larga vida (que tensiona el single-writer del ADR
  [0019](0019-concurrencia-diferida.md)), un subárbol JS (`frontend/`, único Node del monorepo, con su
  toolchain `pnpm`/Vite/CI propio) y un empaquetado especial (`force-include` del frontend gitignored,
  jobs de build de Node en `ci.yml`/`publish-*.yml`).
- **Pertenece al otro lado de la frontera de producto.** bib2graph es el **motor determinista** sin
  IA; la experiencia visual library-centric (las propuestas 0032/0033/0034 que colgaban de la GUI) es
  del **producto separado** (Zotero/Mendeley + IA-asiste), no de la librería.

La pregunta de este ADR no es de diseño: es de **alcance**. *¿La GUI local es parte de la librería
bib2graph?* La respuesta del PO es **no**.

## Decisión

**bib2graph retira la GUI local de la librería.** Se eliminan el subcomando `b2g gui`, la API local
FastAPI (`src/bib2graph/api/`), la SPA `frontend/`, el extra `[gui]` y el vendoreo del frontend en el
wheel. El **core de bib2graph es la CLI/agente-native `b2g`** (ADR 0010/0021/0037) sobre la
biblioteca viva DuckDB. Es retiro de **superficie**; el contrato de salida (envelope `schema="1"` /
exit codes / FSM) y la **capa de servicios neutral `service/`** **no cambian**.

### Qué se retira (BREAKING, pre-1.0 → bump minor)

1. **El subcomando `b2g gui`** (`cli/commands/gui.py`) — sin alias de retrocompat (no es un renombre,
   es un retiro de capacidad).
2. **La API local FastAPI** (`src/bib2graph/api/**`: `app`, `deps`, `security`, `envelopes`, `routers/`).
3. **La SPA `frontend/**`** (subárbol JS) y el prototipo `app/**`.
4. **El extra `[gui]`** (`fastapi` + `uvicorn`) y todo su andamiaje de empaquetado: `force-include` de
   `gui/static/`, el directorio `src/bib2graph/gui/`, los `per-file-ignores` de `api/` y el override
   de mypy `uvicorn.*` en `pyproject.toml`.
5. **El job `frontend` de `ci.yml`** y los pasos de build de Node de `publish-pypi.yml` /
   `publish-testpypi.yml` (el wheel pasa a ser **Python puro**, construible con `uv build` sin Node).

### Qué se conserva (NO es GUI; lo usa el CLI)

- **La capa de servicios neutral `service/`** completa: `envelope.py`, `errors.py`, `resolve.py`,
  `curate.py`, `maturity.py`, `snapshot.py` y **`reads.py`**. El 0028 la introdujo como contrato
  compartido; el CLI (`read`/`curate`/`snapshot`/…) **depende** de ella. **`service/reads.py` no es
  exclusiva de la API** —el grupo `read` (#156/#157) la consume (`list_papers`/`corpus_stats`/
  `get_paper`/`get_top`)—, así que **se queda**.
- **El entry point `b2g`** y los 10 verbos del ciclo + `skill` intactos.

### El conteo de superficie tras el retiro

La superficie 0.10.0 pasa de *"10 verbos del ciclo + `gui` + `skill`"* (estado del ADR 0039) a
**"10 verbos del ciclo + `skill` (meta/distribución)"**. `skill` queda como la **única excepción
meta**, ya no "la 2.ª junto a `gui`". El conteo de 10 verbos del 0037 sigue siendo **verificable
contra `b2g --help`**.

## Consecuencias

**Lo que se gana**

- **Foco.** El core vuelve a ser una sola frontera: la CLI/agente-native. Menos superficie que
  documentar, testear y mantener; el camino de adopción es la skill (0039), no una SPA local.
- **Wheel Python puro.** Sin Node en el build: `uv build` produce el wheel sin `pnpm`, sin
  `force-include`, sin jobs de frontend en CI/publish. Empaquetado más simple y reproducible.
- **Sin la tensión de concurrencia del 0019.** Desaparece el server HTTP de larga vida; el modelo
  single-writer (1 archivo = 1 escritor) deja de estar tensionado por la API.
- **Frontera de producto nítida** (memoria del PO): bib2graph = motor determinista sin IA; la
  experiencia visual library-centric vive en el producto separado, no en la librería.

**Lo que cuesta**

- **BREAKING para quien usaba `b2g gui` o instalaba `bib2graph[gui]`.** Pre-1.0, se absorbe como bump
  **minor**; release-please lo corta desde el commit BREAKING (`feat!`/footer `BREAKING CHANGE`). No
  hay ruta de migración: la capacidad se retira.
- **Documentación a depurar.** Este ADR limpia los docs **activos** mínimos para que el retiro sea
  coherente (AGENTS, API §0.1/§0.2/`gui`, ARCHITECTURE §4.4, PRD, ROADMAP/05-gui banner). La limpieza
  **profunda** —los ~53 marcadores AS-BUILT de la epic GUI repartidos por API/ARCHITECTURE/AGENTS— se
  trata en [#191](https://github.com/complexluise/bib2graph/issues/191), no aquí.
- **Trabajo descartado.** G1–G5 estaban AS-BUILT. Se retira código que funcionaba. El registro
  (Notas 07/08/10/12/16/17, ADR 0027/0028) queda como **historia**: el porqué de haberlo construido y
  el porqué de retirarlo conviven.
- **Las propuestas 0032/0033/0034 quedan sin destino en la librería.** Colgaban de la GUI
  (library-centric, tags, flujo canónico vía `service/`). No se revierten —siguen como **Propuesta**
  histórica— pero su materialización ya no es de bib2graph: es del producto separado.

## Alternativas

- **Mantener la GUI como extra opt-in dormido** (código presente, sin promocionar). **Descartada:** el
  código vivo carga mantenimiento (deps `fastapi`/`uvicorn`, toolchain Node, CI, empaquetado especial)
  aunque nadie lo use, y mantiene la ambigüedad de alcance que este ADR quiere cerrar. Un extra
  "dormido" sigue siendo superficie pública que el contrato declara.
- **Mover la GUI a un repo/paquete aparte ahora.** **Descartada como parte de este issue:** el foco es
  **retirarla de la librería**, no relanzarla. Si el producto separado la necesita, partirá de cero con
  su propio gobierno; la historia (0027/0028 + Notas) queda disponible como referencia. Extraer y
  mantener un paquete espejo hoy es trabajo que nadie pidió.
- **Borrar también `service/reads.py`** (como sugería el inventario inicial, asumiéndola API-only).
  **Descartada:** es **incorrecto** —el grupo `read` del CLI la usa (`list_papers`/`corpus_stats`/
  `get_paper`/`get_top`)—. Borrarla rompería `b2g read`. Las funciones de `reads.py` que **solo** usaba
  la API (`get_workspace`/`list_rounds`/`get_scent`/`get_network`/`compare_rounds`) quedan como código
  inerte; su poda es **opcional** y se difiere a la limpieza profunda (#191), no a este retiro.
- **No marcarlo BREAKING** (retiro silencioso). **Descartada:** retira capacidad pública
  (`b2g gui`, extra `[gui]`); el contrato exige señalarlo. Pre-1.0 = minor, pero **BREAKING** explícito
  en el commit para que release-please y el CHANGELOG lo registren.
</content>
</invoke>
