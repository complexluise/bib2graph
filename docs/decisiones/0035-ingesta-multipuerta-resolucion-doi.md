# 0035 — Ingesta de doble puerta (online + archivo) y resolución DOI→OpenAlex ID como servicio

- **Estado:** Aceptada
- **Fecha:** 2026-06-18
- **Relacionada con:** [0007](0007-openalex-backbone.md) (OpenAlex backbone; BibTeX secundaria —este
  ADR la **promueve a primera clase**), [0018](0018-source-agnostico-calidad.md) (contrato `Source`
  agnóstico: mínimo universal vs enriquecimiento), [0030](0030-ecuacion-declarativa-corpus-ejemplo.md)
  (`seed --from-bib`, 3er modo BibTeX sin red), [0032](0032-capa-servicios-duena-del-flujo.md) (ingesta
  y resolución viven en `service/`), [0031](0031-preprocesamiento-automatico-en-ingesta.md) (ambas
  puertas comparten `normalize_and_dedup`).
- **Encuadre:** Nota 17 §GAP-1/§GAP-2 + DECISIÓN DEL PO +
  Nota 18. **Decidido por el PO (2026-06-18): el flujo
  BibTeX/archivo es de PRIMERA CLASE.**
- **Epic:** GUI local [#34](https://github.com/complexluise/bib2graph/issues/34).
- **AS-BUILT (0.8, 2026-06-22):** se grada a Aceptada y se implementa el **core de resolución**
  (issues [#110](https://github.com/complexluise/bib2graph/issues/110) flujo BibTeX e2e +
  [#112](https://github.com/complexluise/bib2graph/issues/112) `--email`): `OpenAlexSource.fetch_dois_to_openalex_ids`,
  el servicio `resolve`, el subcomando `b2g resolve` y el flag `seed --from-bib --resolve`, con
  `--email`. **Ajuste por ADR 0036:** la resolución puebla **`source_id`** (no `openalex_id`); como el
  DOI ya es el ancla de identidad (0036), un paper de `.bib` con DOI tiene `id` estable sin resolver —
  la resolución solo habilita `enrich`/`chain` (que necesitan el id de motor). **Diferido a issues
  aparte:** el **import multi-formato** (`RisSource`/`CsvSource`, punto 4) — scope mayor, se prioriza
  según demanda.

## Contexto

La validación del tercero (Nota 17) mostró que el flujo **online** (`seed --equation`) está sano, pero
**todo el dolor se concentra en el flujo de archivo** (sembrar desde un `.bib` curado a mano): el
pipeline solo se completó gracias a **5 scripts puente** que el colega tuvo que escribir
(`resolve_dois.py`, `forward_chain.py`, `dedup.py`, …).

La causa raíz que encadena casi todo el dolor (GAP-1): **`seed --from-bib` carga las entradas pero deja
`openalex_id=NULL`.** Sin OpenAlex ID, `enrich` y `chain` (forward y backward) devuelven **0** — el
corpus de archivo queda inerte. El colega lo resolvió a mano iterando `GET /works/doi:<doi>`. Además
(GAP-2): `--email` (polite-pool) solo se acepta en modo ecuación, no en `--from-bib`, aunque la
resolución de DOIs **también** pega a OpenAlex.

La **decisión del PO** (Nota 17): el investigador **descarga `.bib` / RIS / EndNote / CSV de páginas
web institucionales** (bases de datos, bibliotecas, repositorios) — no todo está en OpenAlex ni
arranca por una ecuación. La importación desde archivo es una **puerta de entrada real y primaria** al
corpus, **no un import de segunda**. Esto revisa el "BibTeX es `Source` secundaria" del ADR 0007.

El contrato `Source` agnóstico (ADR 0018) ya separa el **mínimo universal** del **enriquecimiento
opcional**: una fuente de archivo entrega el mínimo (title/year/authors/doi); el enriquecimiento
(references/cited_by) llega vía OpenAlex **una vez resuelto el ID**. La pieza que falta es la
**resolución DOI→OpenAlex ID** como operación compartida.

## Decisión

**Las dos puertas de ingesta (online por ecuación y archivo descargado) convergen en el MISMO corpus
vivo por la MISMA cadena, y la resolución DOI→OpenAlex ID es una operación de servicio compartida.**

1. **Ingesta de doble puerta, misma clase.** Online (`seed_from_equation`) y archivo
   (`seed_from_file`) son **dos entradas a la misma cadena de servicio**: `*Source.load/seed` →
   `existing.merge(incoming)` → `normalize_and_dedup` (cross-biblioteca, ADR 0031) → `persist_replace`
   → `loop_state_log`. El archivo deja de ser "import de segunda": es **primera clase** (revisa la
   jerarquía de 0007, sin tocar que OpenAlex sigue siendo el backbone del **enriquecimiento**).

2. **Resolución DOI→OpenAlex ID = operación de servicio compartida** `service.resolve.dois_to_openalex_ids`
   (ADR 0032). Toma los papers del corpus con `doi` y `openalex_id=NULL`, pega a OpenAlex
   (`GET /works/doi:<doi>` batcheado) y puebla `openalex_id`. **Acepta `--email` polite-pool** (cierra
   GAP-2). Requiere un método nuevo en `OpenAlexSource`: **`fetch_dois_to_openalex_ids(dois)`** — hoy
   solo existe `fetch_works_by_ids` (parte de IDs ya OpenAlex, no de DOIs).

3. **La resolución la consumen ambas puertas y la GUI.** Adaptadores: como **flag `--resolve`** de
   `seed --from-bib` (paso opcional encadenado) **Y** como subcomando independiente **`b2g resolve`**
   (mismo servicio, dos adaptadores; Nota 17 propone ambas, Nota 18 §3 lo recomienda). En la GUI: paso
   del wizard de import / botón "resolver DOIs". **Sin la resolución, la cadena
   `--from-bib → enrich → chain` no produce nada** (es la causa raíz GAP-1).

4. **Import multi-formato (más allá de BibTeX).** El motivo del PO (descarga institucional) aplica a
   **RIS, EndNote, CSV**, no solo `.bib`. `seed_from_file` despacha por formato a la `Source`
   correspondiente (`BibtexSource` existe; `RisSource`/`CsvSource` son nuevas, sobre el contrato 0018).
   **RIS al menos** entra en el alcance; EndNote/CSV se priorizan según demanda. Se publica solo lo que
   existe (ADR 0007 §regla): la GUI no ofrece un formato hasta que su `Source` esté construida.

## Consecuencias

- (+) **El flujo de archivo deja de necesitar babysitting:** `seed --from-bib → resolve → enrich →
  chain` se cierra dentro de la herramienta (elimina `resolve_dois.py` del tercero). Cierra GAP-1+GAP-2.
- (+) **Una sola cadena de ingesta** para ambas puertas: el corpus vivo es el mismo, deduplicado
  cross-biblioteca, sin importar por dónde entró el paper. La GUI ingesta por drag-and-drop con la misma
  garantía que el CLI.
- (+) **OpenAlex sigue siendo el backbone del enriquecimiento** (0007 intacto en lo estructural): la
  resolución DOI→ID es justamente el puente que conecta el corpus de archivo con ese backbone.
- (+) **Multi-formato sobre el contrato `Source` agnóstico** (0018) sin re-arquitectura: cada formato
  es una `Source` más que entrega el mínimo universal.
- (−) **Más superficie de fuentes** (`RisSource`/`CsvSource` nuevas + método de resolución en
  `OpenAlexSource`) y un paso de red nuevo (`/works/doi:`). Acotado: la resolución reusa el cliente
  httpx, retry y polite-pool existentes.
- (−) **La resolución pega a OpenAlex** → un corpus de archivo grande implica N requests de resolución
  (batcheadas). Sujeto al polite-pool; el tope/preview se diseña como en el resto del forrajeo.
- (−) **Revisar el claim de 0007** ("BibTeX secundaria"): este ADR lo promueve a primera clase en la
  **ingesta** (no en el enriquecimiento). 0007 queda como historia con esta enmienda referenciada.
