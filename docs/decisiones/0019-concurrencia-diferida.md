# 0019 — Concurrencia diferida: limitación conocida, 1 archivo = 1 escritor

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva en DuckDB),
  [0015](0015-corpus-tabular-backend.md) (`DuckDBBackend` por defecto),
  [0016](0016-maquina-estados-lazo.md) (una investigación = un archivo `.duckdb`)

## Contexto

La biblioteca viva se respalda en **DuckDB embebido** (ADR 0009 / 0015). DuckDB es
**single-writer**: un solo proceso puede tener el archivo abierto en modo escritura a la vez
(lecturas concurrentes sí se permiten). El ADR 0009 listó "concurrencia básica" como un costo
abierto sin resolverlo.

Con el modelo "una investigación = un archivo `.duckdb`" (ADR 0016), el caso de uso V1 es
**secuencial**: un investigador humano, o un agente, trabajando sobre su archivo. La concurrencia
multi-escritor (varios agentes escribiendo el mismo archivo a la vez) es un caso que **no aparece
en el wedge de la V1** y resolverlo ahora sería especular sobre una demanda que no existe.

## Decisión

La concurrencia multi-escritor es una **limitación conocida y declarada**, no un defecto a
resolver en V1. La V1 asume **uso secuencial**:

- **1 archivo `.duckdb` = 1 escritor** a la vez (un humano o un agente).
- **Lecturas concurrentes OK** (proyección/análisis/`b2g status` sobre el mismo archivo no
  bloquean).
- Varias investigaciones en paralelo = **varios archivos** (sin contención entre ellos, ADR 0016).

Se **resuelve post-v1.0 según demanda** (p. ej. lock cooperativo, cola de escritura, o un backend
servidor si aparece el caso multi-agente concurrente).

## Consecuencias

- **Honestidad sobre el límite** (lección de v0: no prometer lo que no existe). El usuario y el
  agente saben que no deben abrir el mismo archivo para escribir desde dos procesos a la vez.
- **Simplicidad en V1:** sin lógica de locking ni coordinación; el `DuckDBBackend` (Hito 3) abre,
  muta y cierra de forma secuencial.
- **El CLI agente-native** (ADR 0010) debe **fallar claro** (no corromper) si detecta el archivo
  bloqueado por otro escritor — mapea al exit code `5` (store/snapshot corrupto/no disponible).
- **Costo diferido:** si aparece el caso multi-agente concurrente, se reabre con un ADR nuevo
  post-v1.0; no se paga ahora.
- **Recomendación para el `coder`:** el `DuckDBBackend`/`DuckDBStore` del **Hito 3** documenta la
  asunción single-writer y traduce el error de archivo bloqueado de DuckDB a un error accionable
  con exit code `5` (a cablear en el CLI, Hito 6). No se implementa locking propio.

## Enmienda — la unidad pasa a "workspace/carpeta"; el single-writer sigue válido (AS-BUILT, 2026-06-16)

> **Implementado por [0029](0029-workspace-por-investigacion.md) (ver su AS-BUILT).** El cuerpo de
> este ADR queda como historia.

Este ADR razona sobre "1 archivo `.duckdb` = 1 escritor". El ADR
[0029](0029-workspace-por-investigacion.md) eleva la **unidad de persistencia** a un
**workspace = carpeta** (`workspace.json` + `library.duckdb` + `networks/`/`snapshots/`/`exports/`).
La conclusión de concurrencia **no cambia**: el `library.duckdb` dentro del workspace sigue siendo
**single-writer** (un escritor a la vez; lecturas concurrentes OK). Varias investigaciones en
paralelo = varios workspaces (varias carpetas, varios `.duckdb`) sin contención entre ellos. La
concurrencia multi-escritor sobre un mismo `.duckdb` sigue diferida post-v1.0. **Léase "1 archivo" ≡
"el `library.duckdb` del workspace".** (El `.duckdb` suelto = workspace degenerado, también
single-writer.)
