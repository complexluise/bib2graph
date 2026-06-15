# 0002 — Modelo de dominio agnóstico de backend; Neo4j demotado a adaptador

- **Estado:** Aceptada
- **Fecha:** 2026-06-14
- **Relacionada con:** [0001](0001-herramienta-reutilizable.md), [0003](0003-persistencia-opcional.md)

## Contexto

El defecto fatal de v0 fue que **Neo4j era el modelo de datos**: `models.py` definía todo
como `StructuredNode` de neomodel, y cada módulo operaba sobre una base viva configurada por
efectos de import (`config.DATABASE_URL`). Consecuencias directas:

- Nada existía ni se podía probar sin un servidor Neo4j corriendo (el único test del repo
  era "¿el paquete importa?").
- La lógica bibliométrica (proyección, métricas, comunidades) estaba enredada con consultas
  Cypher y con el ciclo de vida de la conexión.

## Decisión

Introducir un **modelo de dominio en memoria, agnóstico de backend**: un `Corpus` de datos
planos (`Paper` / `Author` / `Keyword` / `Institution` y sus relaciones, como dataclasses
y/o DataFrames) sobre el que opera **todo** el pipeline. La lógica del núcleo (proyectores,
analizadores, exportadores) es pura: sin I/O, sin servidor. **Neo4j deja de ser el sustrato
y pasa a ser un adaptador de persistencia** entre otros posibles (ver 0003).

## Consecuencias

- El núcleo se vuelve **unitariamente testeable** con datos sintéticos, sin infraestructura.
  Esta es la victoria de testabilidad de la reescritura.
- El `Corpus` se convierte en la **única fuente de verdad del modelo**, documentada una sola
  vez (`API.md` §1), eliminando el drift docs↔código de v0.
- Las relaciones de red (`CO_CITED_WITH`, etc.) dejan de materializarse en una base antes de
  analizarse: son **salida de funciones puras** (proyectores) sobre el corpus.
- Costo: hay que diseñar la representación interna del corpus y un adaptador Neo4j que mapee
  corpus↔grafo. Se asume a cambio de testabilidad y reutilización.
- Decisión de implementación pendiente: representación interna (dataclasses vs DataFrames) y
  si el adaptador Neo4j usa `neomodel` o el driver oficial (ver `ARCHITECTURE.md` §9).
