# 0004 — Enriquecimiento opcional (verdad de dependencias)

- **Estado:** Aceptada
- **Fecha:** 2026-06-14
- **Relacionada con:** [0005](0005-dependencias-extras.md)

## Contexto

En v0 el enriquecimiento (consultar Semantic Scholar por cada paper con DOI) era una **fase
del pipeline**, presentada casi como obligatoria. Pero al analizar qué redes dependen
realmente de datos externos surge una verdad clara:

- Las redes de **colaboración de autores**, **colaboración de instituciones** y
  **co-ocurrencia de palabras clave** se construyen **solo desde el BibTeX** (autores,
  afiliaciones y keywords ya vienen en el export).
- **Solo la red de co-citación** necesita una fuente externa de citas/referencias, porque el
  BibTeX **no incluye listas de referencias**.

Además, el enriquecimiento de v0 cargaba con varios problemas: clave de API embebida en el
código, ramas muertas (institutions/keywords que nunca se rellenaban), y manejo primitivo de
rate limit que descartaba papers.

## Decisión

El **enriquecimiento es una costura opt-in** (`Enricher`), **no una fase obligatoria**. Se
ejecuta únicamente cuando el usuario quiere construir la red de co-citación (o completar
metadatos). La implementación de referencia es **Semantic Scholar**; CrossRef y Scopus
quedan como costuras futuras, no implementadas. Las API keys se **inyectan**; nunca hay un
literal por defecto.

## Consecuencias

- Tres de las cuatro redes funcionan **sin red de internet ni claves de API**: menor
  fricción y mejor reproducibilidad para la mayoría de los análisis.
- La co-citación documenta explícitamente su prerrequisito (un `Enricher` que provea
  referencias), en vez de fallar de forma confusa.
- El contrato `Enricher` debe especificar manejo de rate limit y reintentos sin perder
  datos, y prohibir ramas que rellenen claves que la fuente no provee (corrige el código
  muerto de v0).
- Costo: el usuario debe entender cuándo necesita enriquecer. Se mitiga documentándolo en
  `PRD.md`, `ARCHITECTURE.md` y `API.md`.
