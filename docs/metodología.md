# Documento Metodológico: análisis de redes bibliométricas en bib2graph

> Autoridad de dominio sobre el **método bibliométrico** del AS-BUILT (v0.2). Reescrito al stack
> real (**OpenAlex** como backbone, **DuckDB** biblioteca viva, **Arrow** como tabla canónica,
> **networkx** para las redes) tras el red-team de la
> [`Notas/06-critica-as-built-v0.2.md`](Notas/06-critica-as-built-v0.2.md). El material previo
> (Neo4j/Cypher, Semantic Scholar/Scopus, BibTeX como entrada, estudio de semiconductores) se
> conserva como **anexo histórico** al final (§A), **sin** reescribirlo. Fecha: 2026-06-15.

## 1. Qué calcula bib2graph

bib2graph proyecta un **corpus** (tabla canónica Arrow, una fila por paper) a **cinco redes
bibliométricas**, las analiza (métricas, centralidad, comunidades, asortatividad) y las exporta a
GraphML/CSV. El método es **determinista y reproducible**: mismas entradas → mismas redes (ADR
[0017](decisiones/0017-reproducibilidad-historia-snapshot.md), Louvain seeded). **No hay IA
generativa** en el método (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)).

## 2. Fundamento teórico de las redes

Cada proyección revela una estructura distinta del campo. Las definiciones importan (la §3 corrige
un error histórico que confundía dos de ellas):

| Red | Definición | Qué revela |
|---|---|---|
| **Acoplamiento bibliográfico** | Dos papers están **acoplados** si **comparten referencias** (citan a los mismos trabajos). | Cercanía temática *desde la perspectiva de los autores citantes*; es estable en el tiempo (las referencias de un paper no cambian). |
| **Co-citación** | Dos papers están **co-citados** si **un tercero los cita a ambos** (comparten **citantes**). | Estructura intelectual *según la comunidad que cita*; evoluciona con el tiempo (acumula citantes nuevos). |
| **Colaboración de autores** | Autores que **co-firman** un paper. | Comunidades de coautoría. |
| **Colaboración de instituciones** | Instituciones vinculadas por co-firmas. | Geografía/estructura institucional (insumo de la asortatividad Norte–Sur). |
| **Co-ocurrencia de keywords** | Keywords que aparecen **juntas** en un paper (normalizadas por el thesaurus multilingüe). | Estructura conceptual/temática del campo. |

**Acoplamiento ≠ co-citación.** Acoplamiento = **referencias** compartidas (mira *hacia atrás*, hacia
lo que el paper cita). Co-citación = **citantes** compartidos (mira *hacia adelante*, hacia quién
cita al paper). Confundirlos es el error que la §3 corrige.

## 3. Cómo se construyen las redes (stack real)

El insumo viene de **OpenAlex** ya en el corpus: `references_id` (lo que el paper cita) llega
**inline** con el seed; `cited_by_id` (quién cita al paper) queda **vacío tras el seed** y requiere
un **segundo nivel de fetch** (forward chaining / `Enricher`, Hito 8). Las proyecciones son
**funciones puras sobre la tabla Arrow** (`networks/projectors.py`), no consultas a un servidor de
grafos.

- **Acoplamiento bibliográfico** (`BibliographicCouplingProjector`): para cada par de papers cuenta
  las referencias compartidas (`references_id`). Es **barato** (las refs ya están en el corpus) y
  opera sobre el **corpus completo**, no solo las semillas → es **ciudadano de primera**
  (`critica-base.md` §2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)).
- **Co-citación** (`CoCitationProjector`): para cada par de papers cuenta los **citantes
  compartidos** (`cited_by_id`). Es la red **más cara** (depende del 2º nivel de fetch); sobre un
  corpus recién sembrado da pocas o cero aristas hasta enriquecer.
- El **peso** de cada arista es el **conteo crudo** de ítems compartidos; `min_weight` (default 1)
  descarta aristas débiles. Sin normalización (Salton/Jaccard) en v1.

> **Corrección histórica (Nota 06, rigor):** el Cypher de ejemplo del anexo §A computaba
> *referencias compartidas* (= **acoplamiento**) bajo la etiqueta `CO_CITED_WITH`, contradiciendo su
> propio fundamento teórico. El **código del AS-BUILT está bien**: la co-citación usa
> `cited_by_id` = citantes compartidos. Esta §3 es la definición autoritativa; el Cypher del anexo
> queda solo como historia (erróneo, no reusar).

## 4. Evaluación de calidad de la red

`cocitation_quality_report` (`networks/analyzer.py`) declara criterios con **umbrales configurables**
(`QualityThresholds`), reportando por criterio `{valor, umbral, pasa}` + `overall_pass` (sin score
ponderado que oculte qué falló):

- **Volumen documental** (nº de documentos).
- **Completitud de DOI y referencias** (% con DOI / referencias).
- **Cobertura temporal** (rango de años).
- **Diversidad geográfica.** ⚠️ *AS-BUILT:* el proxy cuenta **instituciones únicas**
  (`institutions_id`), **no países** (no hay lookup ROR→país hasta el Hito 8), así que la métrica
  Norte–Sur que el caso IED necesita **casi siempre da verde**. El report incluye un campo `proxy`
  honesto, pero el criterio es **teatro de calidad** hasta resolver el lookup. Recomendación al
  `coder`: ROR→país en el Enricher (Hito 8).
- **Participación de autores recurrentes.**

## 5. Análisis de la red

Funciones puras sobre `networkx.Graph` (`networks/analyzer.py`):

- **Métricas básicas:** tamaño (nodos/aristas), densidad, componentes conexos, clustering promedio.
- **Centralidad:** grado e intermediación (puentes entre áreas).
- **Comunidades:** **Louvain** (por defecto), propagación de etiquetas, modularidad voraz. Louvain
  requiere `python-louvain` **declarado**; si falta, **falla explícito** (lección 7). Corre con
  `random_state` derivado del content-hash → **comunidades reproducibles** (ADR 0017 enmendado).
- **Asortatividad** (validada en el sandbox IED): por un **atributo categórico configurable** (p.
  ej. región) y por grado, más la **composición de cada comunidad** por ese atributo. Las métricas
  que dependen de un **proxy** se reportan **con el disclaimer del proxy** ("fácil pero consciente").

## 6. Desambiguación de autores (alcance honesto)

⚠️ *AS-BUILT:* la desambiguación es **parcial**. Con ORCID/ROR de OpenAlex se apoya en IDs; **sin
ORCID**, la identidad de autor cae al **display name normalizado** (lowercase/trim/acentos,
`preprocessors/normalize.py`), lo que puede producir **falsos merges/splits** en la red de
co-autoría. **No es** una resolución de identidad robusta — no debe presentarse como tal. El dedup
fuzzy **determinista** (`rapidfuzz`, extra `[dedup]`, Hito 7) refina, pero sigue sin ser identidad
canónica.

## 7. Visualización y exportación

GraphML (para Gephi/VOSviewer/Cytoscape) y CSV (nodos + aristas, para pandas). Salida pura y
determinista (orden de filas estable), sin servidores.

## 8. Limitaciones y consideraciones

1. **Calidad de la fuente:** la precisión de `references_id`/`cited_by_id` de OpenAlex condiciona las
   redes; OpenAlex **cambia en el tiempo** (de ahí la reproducibilidad por snapshot, no por
   recómputo, ADR 0017).
2. **Sesgo temporal:** los papers recientes acumulan menos co-citaciones.
3. **Sesgo de selección del forrajeo:** rankear candidatos por estructura ya presente refuerza lo
   central/popular (efecto Mateo). El scent **prioriza**; la exhaustividad la sostienen los filtros
   PRISMA, no el scent.
4. **Co-citación parcial sin enriquecer:** sin el 2º nivel de fetch, la co-citación es un artefacto
   de qué citantes se trajeron, no un subset fiel; debe marcarse como parcial.

---

## §A. Anexo histórico — diseño previo (Neo4j / Cypher / semiconductores)

> **Material histórico, NO reescrito y NO vigente.** Describe la **arquitectura previa al giro**
> (Neo4j como modelo de datos, enriquecimiento por Semantic Scholar/Scopus, BibTeX como entrada,
> estudio de la cadena de **semiconductores**) y un **Cypher de co-citación ERRÓNEO** (computa
> acoplamiento). Se conserva para trazar de dónde viene el proyecto y como caso documentado; **el
> método vigente es el de las §1–§8**. El giro a OpenAlex/DuckDB está en el ADR
> [0007](decisiones/0007-openalex-backbone.md) y la arquitectura objetivo en
> [`ARCHITECTURE.md`](ARCHITECTURE.md).

### A.1 Arquitectura previa

1. **Modelo de datos en Neo4j** (base orientada a grafos). → *Hoy:* tabla Arrow + DuckDB; Neo4j es
   un adaptador `Store` opt-in post-V1, ya **no** el modelo (ADR
   [0002](decisiones/0002-modelo-agnostico-backend.md)).
2. **Cargador desde BibTeX.** → *Hoy:* OpenAlex backbone; BibTeX es `Source` secundaria.
3. **Enriquecedor por Semantic Scholar/Scopus.** → *Hoy:* refs/citantes vienen de OpenAlex; el
   Enricher deja de ser estructural (ADR [0007](decisiones/0007-openalex-backbone.md)).
4. **Analizador de redes** sobre el grafo Neo4j. → *Hoy:* funciones puras sobre networkx.

### A.2 Cypher de co-citación (ERRÓNEO — computa acoplamiento, no reusar)

```cypher
// ⚠️ HISTÓRICO Y ERRÓNEO. Esto computa ACOPLAMIENTO BIBLIOGRÁFICO (refs compartidas), NO co-citación.
// Co-citación correcta = citantes compartidos: (p1)<-[:REFERENCES]-(citer)-[:REFERENCES]->(p2)
// El AS-BUILT lo implementa bien sobre cited_by_id (ver §3). Este bloque NO debe usarse.
MATCH (p1:Paper {is_seed: True})-[:REFERENCES]->(ref:Paper)<-[:REFERENCES]-(p2:Paper {is_seed: True})
WHERE p1 <> p2
WITH p1, p2, COUNT(ref) AS shared_refs
WHERE shared_refs > 0
MERGE (p1)-[r:CO_CITED_WITH]-(p2)
ON CREATE SET r.weight = shared_refs
```

### A.3 Umbrales hardcodeados previos

El diseño previo usaba umbrales fijos (volumen ≥200, DOI/refs ≥90%, ≥5 países, ≥10 autores,
2000–2024). → *Hoy:* los umbrales son **configurables** (`QualityThresholds`, crítica #5); no se
hardcodean conceptos de un estudio concreto.

### A.4 Caso de semiconductores

El estudio de la cadena de semiconductores fue el caso original sobre Neo4j/Cypher. Queda como
**caso documentado histórico**; el **caso validador vigente** es el de **intercambio ecológico
desigual (IED)**, corrido end-to-end sobre OpenAlex (ver
[`exploracion/informe_ied_lectura_2.md`](../exploracion/informe_ied_lectura_2.md)). Ninguno es el
producto.
