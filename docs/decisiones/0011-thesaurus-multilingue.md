# 0011 — Thesaurus multilingüe determinista para normalización de keywords

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (`Preprocessor`),
  [0007](0007-openalex-backbone.md)
- **Validado en:** [`../exploracion/informe_ied_lectura_2.md`](../../exploracion/informe_ied_lectura_2.md)
  (T6 y T10)

## Contexto

El corpus es **multilingüe** (en/es/pt en el sandbox de intercambio ecológico desigual). Las
keywords equivalentes en distintos idiomas (*intercambio ecológico desigual* ≡ *unequal
exchange*; *deuda ecológica* ≡ *ecological debt*) quedan **dispersas** en la red de
co-ocurrencia si no se normalizan. El sandbox validó un **thesaurus JSON curado** (25 conceptos
canónicos, 144 aliases) que subió la densidad de co-word **+42%**.

Pregunta abierta (T10): ¿el thesaurus debe ser **exhaustivo**, o **cobertura curada + fallback
fuzzy** (embeddings / LLM barato) para las keywords que no matchean?

## Decisión

La **V1 usa un thesaurus multilingüe curado y determinista**: un diccionario
`concepto_canónico → [aliases]` en **JSON portable**, aplicado por el `Preprocessor` núcleo de
forma **idempotente** (normaliza acentos y *case*). El **fallback fuzzy/semántico** (embeddings
o LLM barato) se **difiere a v0.2**.

El thesaurus es **configuración del usuario**, no un thesaurus de dominio fijo en el núcleo (no
hardcodear conceptos de un estudio concreto — crítica #5): la herramienta provee el **mecanismo**.

## Consecuencias

- **Determinista, auditable, sin dependencias pesadas** ni descarga de modelos en V1 — coherente
  con núcleo liviano y reproducibilidad.
- **Cobertura limitada** por lo curado (en el sandbox, ~6% de las keywords matchean, pero son
  las **discursivamente importantes** del campo). Aceptable para V1.
- El **fallback fuzzy queda declarado como futuro**, no prometido (lección 5 de v0).
- El **formato JSON de la sandbox es portable directo** al núcleo: no hay magia, solo un dict.
