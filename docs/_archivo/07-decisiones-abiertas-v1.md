# 07 — Decisiones de diseño abiertas de la V1

> ⚠️ **ARCHIVADO (2026-06-15).** Las tres decisiones se resolvieron en los ADR
> [`0007`](../decisiones/0007-openalex-backbone.md) y
> [`0009`](../decisiones/0009-biblioteca-viva-duckdb.md) y en [`../PRD.md`](../PRD.md). Se
> conserva por historia; **mandan los ADR/PRD**. Ver [`README.md`](README.md) de este directorio.

> Resuelve los tres detalles que quedaron abiertos en
> [`06-definicion-producto-v1.md`](06-definicion-producto-v1.md) §7, **antes** de redactar ADRs
> y reconciliar PRD/ARQUITECTURA. Cada uno se plantea como **recomendación + porqué + qué queda
> por confirmar**. Son propuestas, no dogma. Fecha: 2026-06-14. **Por confirmar con el PO.**

## 1. Profundidad por defecto del chaining

**Recomendación: profundidad = 1 por defecto (un salto), con opt-in explícito a 2.** Y separar
dos usos del chaining que se confunden:

- **Chaining para *construir las redes*** (no agranda el set de semillas): el acoplamiento
  bibliográfico usa las **referencias de las semillas** (las comparten o no); la co-citación usa
  los **citantes**. Esto se computa sobre las semillas + su metadata de refs/citas — **no
  requiere "crecer" el corpus**.
- **Chaining para *crecer el corpus*** (snowballing à la Wohlin): agrega papers nuevos al set.
  **Aquí aplica la profundidad** y es donde explota.

**Por qué 1:** profundidad 2 hace explotar el corpus (cada paper trae decenas de refs/citas;
2 saltos = miles). El humano controla la expansión (historia B2). El **ranking por information
scent** (B3) hace que con 1 salto ya veas lo más relevante primero.

**Salvaguardas que esto implica:**
- **Preview de crecimiento antes de traer**: "esta expansión sumaría ~N papers; ¿seguir?".
- **Tope de candidatos** configurable.
- **Pool cortés de OpenAlex** (email/API key en config) para rate limit sano.

**Por confirmar:** ¿tope default de candidatos? ¿la expansión es global o por-semilla?

## 2. ¿Zotero en la primera entrega, o CLI pura?

**Recomendación: V1.0 = CLI pura; Zotero como costura opt-in en V1.1 (extra `[zotero]`).**

**Por qué:**
- El **camino de valor mínimo** (criterio "V1 hecha" de la nota 06) es **ecuación → GraphML**,
  y **no necesita Zotero**. Meterlo en 1.0 agranda el wedge justo lo que la crítica #8 (scope)
  advierte.
- Zotero es una **costura `Source`/`Store`** (leer semillas desde / devolver lo aceptado a la
  colección), no el núcleo. Encaja perfecto como extra opt-in (política build/integrate:
  `pyzotero` se integra como costura, no como dependencia del núcleo).
- En 1.0 las semillas entran por **ecuación de búsqueda** o por **DOIs/IDs/archivo**; eso ya
  cubre el flujo completo.

**Consecuencia:** la "biblioteca viva" (Zotero) llega en 1.1; en 1.0 la persistencia es el
**snapshot de corrida** (registro reproducible), que sí es núcleo.

**Por confirmar:** ¿1.1 inmediatamente después, o se valida 1.0 con usuarios antes?

## 3. Cómo se expresa la ecuación de búsqueda y su mapeo a OpenAlex (con límites)

Este es el punto delicado, porque la ecuación es **ciudadana de primera clase** (principio
"fácil pero consciente") y OpenAlex **no es WoS/Scopus**.

**Lo que OpenAlex SÍ soporta** (verificado en doc oficial):
- **Boolean** `AND` / `OR` / `NOT` en MAYÚSCULAS, con **paréntesis** y **frase exacta** entre
  comillas dobles.
- **Búsqueda por campo** como filtro: `title.search`, `abstract.search`,
  **`title_and_abstract.search`**, `fulltext.search` (cobertura parcial de fulltext).
- **Filtros facetados** independientes: año, tipo, idioma, open access, etc.
- Por detrás usa Elasticsearch `query_string`.

**Límites reales que hay que mostrarle al investigador (consciencia):**
- ⚠️ **Stemming + stop-words ON por defecto** (Kstem): `"possums"` también trae `"possum"`;
  se puede desactivar con `.no_stem`. El investigador **debe saberlo** (afecta precisión).
- ⚠️ **Sin proximidad** tipo WoS `NEAR/n` — no traducible; hay que avisarlo.
- ⚠️ **Truncación/comodines** (`*` de WoS) se comportan distinto; el stemming cubre parte.
- ⚠️ **Tags de campo** (`TS=`, `AB=`, `AU=`) **no mapean 1:1**: se traducen a `.search` por
  campo; autor/afiliación es más fiable por **ID OpenAlex (ORCID/ROR)** que por texto libre.
- ⚠️ **Cobertura distinta a WoS/Scopus**: la *misma* ecuación da resultados distintos. Es una
  advertencia de reproducibilidad, no un bug.

**Recomendación de diseño:**
1. El investigador escribe una **ecuación estructurada** (términos + boolean + alcance de campo
   + filtros año/tipo/idioma).
2. La herramienta la **traduce a la query OpenAlex** y **muestra la query exacta ejecutada**
   (historia A2) + un **"reporte de traducción"**: qué mapeó limpio, qué se aproximó, qué se
   descartó (p. ej. un `NEAR` no soportado).
3. Se **registran ambas** —ecuación humana y query OpenAlex— en el snapshot (historia A4,
   reproducibilidad PRISMA/vom Brocke).
4. Power-users pueden pasar **query OpenAlex nativa** directamente (escape hatch).

Ese "reporte de traducción" **es** el principio "consciente" hecho función: no ocultamos que
OpenAlex ≠ WoS; lo explicitamos.

**Por confirmar:** ¿la ecuación estructurada es una mini-DSL propia, o adoptamos una sintaxis
existente (p. ej. la booleana de OpenAlex directamente, documentada)? Recomendación tentativa:
**empezar con la booleana de OpenAlex documentada + filtros**, y considerar una DSL más amable
solo si hace falta (no inventar sintaxis antes de tiempo).

## 4. Resumen de lo decidido (a confirmar)

| Punto | Recomendación |
|---|---|
| Profundidad chaining | **1 por defecto**, opt-in a 2; preview de crecimiento + tope |
| Zotero | **CLI pura en 1.0**; Zotero extra `[zotero]` en 1.1 |
| Ecuación de búsqueda | **Boolean OpenAlex + filtros**, con **query ejecutada visible + reporte de traducción** registrados en el snapshot |

## 5. Próximo paso

Con esto confirmado, redactar los **ADRs** (`docs/decisiones/`) y reconciliar `../PRD.md` /
`../ARCHITECTURE.md` (tarea del **architect**).

## 6. Referencias

- OpenAlex — [search entities](https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/search-entities) ·
  [search works](https://docs.openalex.org/api-entities/works/search-works) ·
  [Fulltext search (blog)](https://blog.openalex.org/fulltext-search-in-openalex/) ·
  [cómo buscar en OpenAlex (Utrecht LibGuide)](https://libguides.library.uu.nl/openalex/search)
