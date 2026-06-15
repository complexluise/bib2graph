# 0003 — Persistencia opcional, en memoria por defecto

- **Estado:** Aceptada
- **Fecha:** 2026-06-14
- **Relacionada con:** [0002](0002-modelo-agnostico-backend.md), [0005](0005-dependencias-extras.md)
- **Actualización (2026-06-15):** el *default* en memoria (`InMemoryStore`) queda **supersedido
  por [0009](0009-biblioteca-viva-duckdb.md)**: la persistencia por defecto de V1.0 pasa a ser un
  `Store` **stateful en DuckDB** (biblioteca viva). El principio "persistencia como costura, con
  credenciales inyectadas" sigue vigente; cambia cuál es el *default*.

## Contexto

Una vez que el modelo de dominio es agnóstico de backend (0002), persistir el corpus deja de
ser obligatorio para correr el pipeline. En v0, en cambio, persistir en Neo4j era la única
forma de operar: cada fase leía y escribía sobre la base. Para una herramienta reutilizable,
exigir montar y mantener un servidor solo para construir redes es una barrera de entrada
desproporcionada al valor que aporta.

## Decisión

La **persistencia es una costura opcional** (`Store`). El comportamiento por defecto es
**`InMemoryStore`**: el corpus vive en proceso y no se escribe a disco salvo la exportación
final (GraphML/CSV). **`Neo4jStore` es un adaptador opt-in** que se instala con el extra
`pip install bib2graph[neo4j]`.

## Consecuencias

- El pipeline mínimo (BibTeX → corpus → redes → métricas → export) corre **sin Neo4j y sin
  infraestructura**: instalar y ejecutar.
- Quien necesite consultas Cypher posteriores o persistencia en grafo instala el extra y usa
  Neo4j como destino, sin que eso afecte al resto del pipeline.
- Las credenciales del store se **inyectan**; no hay contraseñas por defecto ni efectos de
  import (corrige el config sprawl de v0).
- Costo: hay que definir y mantener el contrato `Store` y al menos dos implementaciones. El
  contrato debe ser lo bastante simple para que `InMemoryStore` sea trivial y `Neo4jStore`
  un mapeo directo corpus↔grafo.
