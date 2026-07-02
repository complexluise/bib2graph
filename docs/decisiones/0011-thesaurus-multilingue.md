# 0011 — Thesaurus multilingüe determinista para normalización de keywords

- **Estado:** Aceptada · **enmendada 2026-06-15** (el fallback fuzzy/LLM se retira; el thesaurus
  queda solo curado y determinista — ver "Enmienda" al final)
- **Fecha:** 2026-06-15
- **Relacionada con:** [0006](0006-tabla-canonica-y-networkspec.md) (`Preprocessor`),
  [0007](0007-openalex-backbone.md)
- **Validado en:** `../exploracion/informe_ied_lectura_2.md`
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
- El **fallback fuzzy queda declarado como futuro**, no prometido (lección 5 de v0). *(Ver enmienda:
  el fallback **semántico/LLM** se retira; un fallback fuzzy **determinista** —`rapidfuzz`— podría
  vivir en `[dedup]`, pero no es LLM.)*
- El **formato JSON de la sandbox es portable directo** al núcleo: no hay magia, solo un dict.

## Enmienda — 2026-06-15 (sin fallback semántico/LLM del thesaurus)

> Consecuencia de la decisión del PO de que **el producto no usa IA generativa** (ADR
> [0022](0022-producto-sin-ia-generativa.md)). La pregunta abierta T10 ("¿exhaustivo o
> cobertura+fuzzy con embeddings/LLM?") se cierra: **no hay fallback con embeddings ni LLM**. El
> thesaurus es **curado y determinista**; lo que no matchea queda fuera, sin inventar conceptos con
> un modelo. Si se quisiera ampliar cobertura, el único camino aceptado es **fuzzy determinista**
> (`rapidfuzz`, extra `[dedup]`), no semántico. Esto no contradice el cuerpo del ADR (que ya elegía
> el thesaurus determinista para V1); solo **elimina** la rama LLM que quedaba como "futuro".
