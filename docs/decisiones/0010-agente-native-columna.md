# 0010 — CLI agente-native como columna primaria del diseño

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (§ CLI como API),
  [`../critica-base.md`](../critica-base.md) §6

## Contexto

`ARCHITECTURE.md` §6.3 y el ADR 0006 ya tienen las intuiciones correctas (`--json`, exit codes,
sin estado), pero las tratan como **"frontera programática"** sin jerarquía explícita, y el ADR
0006 posterga tool schemas/MCP a "v0.3+, si la demanda lo justifica". La **crítica #6** señala
que, si el flujo con agentes es un **objetivo declarado** del producto, entonces es una
**columna del diseño, no un extra futuro**, y debe moldear la API desde el primer comando.

## Decisión

La **CLI agente-native es superficie primaria desde el primer comando**. Cada subcomando cumple,
por contrato:

- **Doble salida**: humana legible por defecto + `--json` estructurado, estable y versionado.
- **Exit codes claros** (`0` éxito · `1` uso · `2` datos · `3` dependencia faltante · `4` red no
  disponible · `5` snapshot/store corrupto).
- **Errores accionables** (qué pasó + qué hacer), no trazas crudas.
- **Auto-documentación** (`--help` rico) y **eficiencia de tokens** en la salida JSON.
- **Sin estado entre invocaciones**: el estado vive en el `Store` DuckDB (ADR 0009), no en la
  sesión; cada llamada es independiente y reproducible.

Tool schemas JSON / servidor MCP siguen como trabajo posterior, pero la API se **diseña con
estos principios desde el hito 1**, no se adapta después.

## Consecuencias

- La forma de cada comando se decide pensando en **dos consumidores** (el humano "fácil pero
  consciente" y el agente orquestador), no solo en el humano.
- Habilita orquestar `bib2graph` vía subprocess + JSON sin reinventar wrappers — coherente con
  la visión "IA in the loop".
- **Costo**: disciplina de diseño de salida desde el inicio y **tests de contrato** de la salida
  JSON (que el `--json` no driftee entre versiones).
