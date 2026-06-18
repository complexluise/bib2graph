# 0027 — Pivote de posicionamiento: GUI local opt-in para semi-técnicos

- **Estado:** Propuesta — pendiente de firma del PO ([Nota 12](../Notas/12-arquitectura-gui-encuadre.md))
- **Fecha:** 2026-06-18
- **Gatea a:** [0028](0028-arquitectura-gui-api-capa-servicios.md) (arquitectura GUI/API). La
  arquitectura no se baja a `ARCHITECTURE.md` ni se escribe código hasta que este pivote se firme.
- **Enmienda a:** `PRD.md` §3 (alcance/no-objetivos) y §5.2 (interfaces) — hoy dicen "sin GUI / fuera",
  lo que contradice la dirección de producto. La enmienda concreta del PRD (bloque fechado) se aplica
  **al firmar** este ADR.
- **Relacionada con:** [0010](0010-agente-native-columna.md) (CLI agente-native = columna),
  [0021](0021-cli-agente-native-contrato.md) (contrato del CLI),
  [0029](0029-workspace-por-investigacion.md) (workspace = unidad de proyecto, prerequisito ya hecho).
- **Epic:** GUI local [#34](https://github.com/complexluise/bib2graph/issues/34). Dirección en
  Notas [07](../Notas/07-frontend-tool-for-thought.md)/[08](../Notas/08-referentes-frontend.md)/
  [10](../Notas/10-sintesis-contextualizacion-gui.md).

## Contexto

El producto nació **CLI-first, agente-native** (ADR 0010): el CLI `b2g` es la frontera programática
para humanos y LLMs, y el `PRD.md` declara explícitamente **"sin GUI"** entre los no-objetivos (§3) y
deja las interfaces gráficas **fuera** (§5.2). Esa postura fue correcta para V0–V0.6.

La dirección de producto cambió (Notas 07/08/10, epic #34): se decidió construir una **GUI local
"tool for thought"** —la lectura visual no-lineal de la estructura intelectual— como **4º frontend**,
sin abandonar el CLI. La epic ya fijó las decisiones de producto (Nota 10): audiencia = **investigador
semi-técnico** (tesista/docente); canal **pip/uv** aceptable en v1, binario/Tauri diferido a v2;
diferenciador = **"diff de rondas / git de la investigación"** sobre la biblioteca viva local;
**hosting/MCP/Claude-Web descartados**.

Hay entonces una **contradicción de posicionamiento** entre el PRD vigente ("sin GUI") y la dirección
real. La arquitectura de la GUI (ADR 0028) y su bajada a `ARCHITECTURE.md`/`PRD.md` **no deben
escribirse sobre una contradicción sin resolver**: primero se firma *qué* es el producto ahora, después
*cómo* se construye. Este ADR resuelve el *qué* y **gatea** el *cómo*.

## Decisión

**El producto incorpora una GUI local opt-in para investigadores semi-técnicos, sin desplazar al CLI.**
El CLI sigue siendo la columna agente-native (ADR 0010/0021); la GUI es un frontend **adicional y par**,
no un sucesor.

Sub-decisiones (heredadas de la Nota 10, fijadas acá):

- **Audiencia v1:** investigador motivado **semi-técnico** (tesista/docente). Explícito: **no** es para
  el no-técnico-de-verdad en v1.
- **Canal v1:** instalación por **pip/uv** (opt-in, extra `[gui]`); **binario/Tauri diferido a v2**.
- **Local-first, sin hosting.** La GUI corre en `127.0.0.1` sobre el workspace local (ADR 0029).
  **Hosting, servidor MCP y Claude-Web quedan FUERA** (no diferidos: descartados; reabribles solo con
  demanda real y ADR nuevo).
- **Diferenciador comunicado con honestidad:** el "git de la investigación" (diff de rondas) sostenido
  por la **biblioteca viva local+propia**; se comunica como **integración**, no como feature mágica.
- **Gate de validación (criterio de éxito/descarte, de #34):** la GUI se valida con un **caso real
  reproducido por un tercero** (un tesista/docente distinto del autor curando el caso `valoraciones`).
  **Descarte:** si el tercero no reproduce el caso o no usa la GUI sin ayuda, se revisa la dirección
  antes de promover la GUI a oficial. Este ADR **no** declara el gate cumplido; lo deja como condición.

## Consecuencias

- (+) **Desbloquea la arquitectura GUI** (ADR 0028) sobre una base de posicionamiento firmada, sin
  contradecir el PRD.
- (+) **El CLI no pierde su rol:** sigue siendo la columna agente-native; la GUI se apoya en la misma
  lógica (ver 0028), no la reemplaza.
- (+) **Alcance acotado y honesto:** semi-técnicos, local-first, pip/uv; lo que queda fuera
  (hosting/MCP/Tauri) está declarado, no ambiguo.
- (−) **Enmienda al contrato de producto (PRD §3/§5.2):** hay que reescribir esas secciones como bloque
  fechado al firmar; el "sin GUI" deja de ser cierto.
- (−) **Compromiso de validación:** asumir el gate del tercero como criterio real (no cosmético) implica
  que la inversión en la GUI puede frenarse/revisarse si la validación falla.
- (−) **Más superficie de producto que mantener** (un frontend más, su empaquetado y su CI), detallada y
  asumida en [0028](0028-arquitectura-gui-api-capa-servicios.md).
