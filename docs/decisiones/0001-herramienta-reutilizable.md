# 0001 — Herramienta reutilizable en vez de pipeline de un solo uso

- **Estado:** Aceptada
- **Fecha:** 2026-06-14

## Contexto

La v0 de `bib2graph` se construyó como el pipeline de investigación de un estudio concreto
(la cadena de suministro de semiconductores). Estaba publicada en PyPI pero su diseño era el
de una herramienta a medida: comandos en español acoplados a un flujo de tres fases, scripts
de análisis ad-hoc en `analisis/`, y un acoplamiento total a Neo4j. Reutilizarla en otro
corpus o integrarla en otro código era difícil, y su lógica no era testeable de forma
aislada.

## Decisión

Reescribir `bib2graph` como una **librería de Python instalable y reutilizable por
terceros**, con una CLI delgada construida encima. El producto es la **herramienta
genérica**; el estudio de semiconductores pasa a ser el **ejemplo validador / caso de
referencia**, no el producto.

## Consecuencias

- El diseño se orienta a una **superficie pública estable** (contratos de costuras y del
  núcleo; ver `API.md`) en vez de a un flujo único.
- La documentación se reorganiza: PRD para el producto reutilizable, arquitectura objetivo,
  contratos de API, ADRs y roadmap de construcción.
- El estudio de semiconductores se mantiene como prueba de que la librería reproduce un
  análisis real y publicable, pero deja de dictar el diseño.
- Obliga a las decisiones 0002–0005 (núcleo agnóstico, persistencia y enriquecimiento
  opcionales, dependencias por extras), que son lo que hace a la herramienta reutilizable.
