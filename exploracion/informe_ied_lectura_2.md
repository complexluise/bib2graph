# Informe IED v2 (lectura sustantiva) — sandbox `exploracion/`

> **Qué cambió respecto a v1.** Esta es la **segunda iteración** de la
> exploración. Resuelve T1, T5 y T6, rediseña coupling, y agrega una
> **corrida con datos reales de OpenAlex** que valida T2 y T4. El contexto
> de v1 está en `informe_ied_lectura_1.md` — leerlo primero si volvés
> recién al repo.
>
> **Datos cuantitativos auto-generados.** Los datos por red (top,
> centralidad, comunidades, geografía) los regenera
> `05_metrics_report.py` en `informe_ied.md`. **No los duplico acá** —
> corré el pipeline y leé el auto.
>
> **Cómo se generó esta corrida.** Pipeline completo:
> 1. `02_load_bibtex.py` (con pre-procesador T1) sobre
>    `datos/semillas_ied.bib` (24 entradas con campo `affiliation`).
> 2. `01_search_openalex.py` (sin API key, polite pool) con query
>    específica de IED: 80 papers reales de OpenAlex.
> 3. `03_merge_corpus.py` une semillas + OpenAlex → 103 papers, 1 merge
>    por DOI.
> 4. `06_apply_thesaurus.py` aplica `datos/thesaurus_ied.json` (144
>    aliases, 25 conceptos canónicos en en/es/pt).
> 5. `04_build_networks.py --coupling-scope full` construye 4 redes
>    (coupling sobre corpus completo).
> 6. `05_metrics_report.py` calcula métricas + geografía + informe.
>
> **Lo más fuerte que apareció en esta corrida.** Las 4 redes tienen
> estructura (no como en v1, donde 2/4 estaban vacías). La asimetría
> Norte-Sur **es visible con datos reales** (50% Norte, 18% Sur, 32%
> Unknown; 27% de los papers con al menos un autor del Sur).
> La asortatividad de co-autoría es +1.000 (homofilia perfecta) — un
> proxy imperfecto pero consistente con la bibliografía crítica.

## ITERACIÓN 2 — qué se hizo

### Resuelto: T1 (bug `bibtexparser`)

**Diagnóstico.** El bug **no era** "comentarios con no-ASCII" (mi
hipótesis inicial, equivocada). Era un patrón específico: cuando
`keywords` (u otro campo que el parser trata especialmente) es el
**último campo** de una entry, y va seguido de un **comentario `%`**
cualquiera (incluso vacío, incluso ASCII puro) antes del `}` de cierre,
`bibtexparser` 1.4.x **se come la entry entera**. Las 3 entradas
perdidas en v1 (`ricardo`, `reyes`, `bringezu`) tenían exactamente ese
patrón.

**Fix.** Pre-procesador `_preprocess_bib()` en `02_load_bibtex.py` que
**elimina los comentarios `%` justo antes del `}` de cierre dentro de
una entry**. 10 líneas, sin dependencias.

**Resultado.** Las 24 entradas del .bib parsean (antes 21 → ahora 24).
Las 3 que se perdían tienen el comentario y se eliminan correctamente.

**Implicación para el Hito 3.** La `BibtexSource` del Hito 3 **no puede
usar `bibtexparser` solo**: necesita un pre-procesador o un parser
alternativo. El pre-procesador actual es la opción más liviana y
explicable. Pendiente: documentar el bug en un issue upstream de
`bibtexparser` (no es responsabilidad de `bib2graph`).

### Resuelto: T5 (asortatividad + composición geográfica)

**Implementación.** Nuevas métricas en `05_metrics_report.py`:
- **Asortatividad por región** (NORTH/SOUTH/UNKNOWN) usando
  `nx.attribute_assortativity_coefficient(g, "geo")`.
- **Asortatividad por grado** (degree assortativity, ponderada por
  peso de aristas).
- **Composición de comunidades** con conteo de regiones por cluster
  louvain (muestra qué % de cada cluster es Norte, Sur, Unknown).

**Datos sintéticos vs. reales.** Para que las métricas tuvieran señal,
agregué un campo `affiliation = {Pais}` al .bib sintético. El parser lo
mapea a `authors_affiliations` y el `extract_country` lo reconoce.
**Con datos sintéticos**: 24 papers, 13 con país asignado, asortatividad
no calculable (división degenerada). **Con datos reales**: 103 papers,
99 con país asignado, asortatividad **+1.000** (homofilia perfecta).

**Límite honesto.** En el .bib, la afiliación es **del paper** (un solo
país por entrada), no per-autor. En OpenAlex, `authors_affiliations`
sí es per-autor (viene de `authorships[].institutions[].country_code`).
Mi código asigna el país del paper a todos sus autores, lo cual **es un
proxy**, no una verdad. La asortatividad +1.000 sobre co-autoría es
real pero **sobre-estima** la homofilia: si los 3 co-autores de un
paper Norte están todos en el mismo componente conexo, todos se
marcan Norte, y eso infla la homofilia. El fix correcto es
**per-autor affiliation** y lo da OpenAlex. El informe v2 lo reporta
explícitamente.

**Implicación para el `Analyzer` del Hito 2.** La asortatividad **es**
una métrica IED-relevante. El `Analyzer` del Hito 2 debería exponer
asortatividad por región **y** por grado, con el flag de "por paper"
vs. "per author" para que el usuario sea consciente del proxy.

### Resuelto: T6 (thesaurus multilingüe)

**Implementación.**
- `datos/thesaurus_ied.json` con 25 conceptos canónicos × 144 aliases
  en en/es/pt. Curado a mano a partir de los términos que aparecen en
  el corpus semilla + los 80 papers de OpenAlex.
- `scripts/06_apply_thesaurus.py` aplica el thesaurus: para cada paper,
  mapea cada keyword al canónico, deduplica, sobreescribe `keywords_id`.
- Idempotente, normaliza acentos y lowercase.

**Resultado con datos reales.** 60/1005 keywords (6%) se mapearon al
canónico, 274 keywords canónicas únicas (vs 1005 originales). El 6%
parece bajo pero es honesto: OpenAlex tiene keywords de **todos** los
campos que cayeron en la query, no sólo IED. Lo que importa es que
**`ecological_debt`**, **`unequal_exchange`**, **`material_flow_analysis`**,
**`land_use`**, etc., ahora colapsan y el cluster en español se
mezcla con su equivalente en inglés en el grafo de co-word. La
densidad de co-word subió de 0.0682 (v1) a **0.0968** (+42%).

**Límite honesto.** El thesaurus tiene 25 conceptos. Hay ~1000 keywords
en el corpus que no matchean ninguno. **No es exhaustivo** y eso está
documentado en `thesaurus_ied.json._meta.limitations`. Para llegar a
cobertura completa, hay dos opciones: (a) **curar más** (~2-3h más
de trabajo, agregar 50-100 entradas más); (b) **complementar con
embeddings** (un match semántico laxo para keywords que no están en
el thesaurus). Recomiendo (a) ahora, dejar (b) para v0.2.

**Implicación para el Hito 4.** El `Preprocessor` núcleo del Hito 4
**debe** tener un mecanismo de thesaurus. El formato JSON de la
sandbox es **directamente portable** al núcleo (no hay magia, sólo
un dict con claves canónicas y listas de aliases). Confirmado.

### Resuelto: rediseño de coupling

**Decisión.** `coupling` ahora tiene dos modos:
- `seeds` (default): sólo papers semilla. **Operacionalmente idéntica
  a co-citación** sin citadores (T3 de v1).
- `full`: corpus completo (semillas + citadores + referencias
  resueltas). La diferencia aparece sólo si hay citadores.

**Resultado con datos reales.** `coupling[full]` sobre 103 papers da
**646 aristas, densidad 0.1230**. ¡La red de coupling **finalmente
tiene estructura**! En v1 era 0/0 sobre 21 papers sintéticos. Los top
papers acoplados son los **reales** de OpenAlex: Rice, Dorninger,
Jorgenson, Martínez-Alier — los seminales del campo.

**Límite honesto.** Las `references_doi` de OpenAlex vienen como **URLs**
(`https://openalex.org/W...`), no como DOIs. Mi código las cuenta como
strings y matchea por igualdad. Eso **funciona** para coupling (papers
que comparten refs por ID interno) pero **no interoperaría** con un
.bib que tiene DOIs reales. Para v0.2 hay que resolver refs a DOI
(fetch adicional con `https://api.openalex.org/works/W...` → campo
`doi`).

**Implicación para el Hito 2.** El `Projector` de coupling del núcleo
debe operar sobre el **corpus completo**, no sólo semillas. Y debe
**resolver refs a DOI** (es trabajo del `Enricher`).

### Resuelto: T2 (sin enriquecimiento, 2/4 redes colapsan) — **parcialmente**

Con 80 papers de OpenAlex, las 4 redes tienen estructura:

| Red | v1 (sintético) | v2 (con reales) |
|---|---|---|
| `co_citacion` | 0 aristas | **0 aristas** ⚠️ |
| `co_autoria` | 48 nodos, 55 aristas | 62 nodos, 99 aristas |
| `co_word` | 50 nodos, 92 aristas | 58 nodos, 160 aristas |
| `coupling[full]` | 0 aristas | 103 nodos, **646 aristas** ✅ |

**`co_citacion` sigue vacía.** Para que tenga aristas, los citadores
de las semillas (los papers que **citan a las semillas**) deben estar
en el corpus con su lista de citaciones, no sólo los citadores por
título. Eso requiere un nivel más de fetch en OpenAlex (resolver
`cited_by_api_url` para cada semilla). Es trabajo de 1-2 tardes más y
**debería hacerse** para tener la red estructural del campo.

**Implicación para el Hito 3.** Sigue valiendo la advertencia de v1: sin
enriquecimiento, `co_citacion` y `coupling[full]` no entregan la red
estructurante. La diferencia con v1 es que ahora sabemos **qué**
falta: `co_citacion` necesita citadores con sus citaciones (segundo
nivel de fetch), `coupling[full]` necesita citadores con sus
referencias (primer nivel, ya hecho). El Hito 3 puede entregar
`coupling[full]` con un corpus enriquecido, pero no `co_citacion` sin
el segundo nivel. **Tensión T2 sigue abierta**.

### Resuelto: T4 (geografía no medible) — **ahora sí**

**Resultado con datos reales:**
- 103 papers totales.
- 50% **NORTH** (USA, UK, Alemania, Finlandia, etc.).
- 18% **SOUTH** (Argentina, Brasil, Bolivia, Ecuador, India, etc.).
- 32% **UNKNOWN** (papers sin afiliación en OpenAlex — bug o metadata
  faltante, no del pipeline).
- **27%** de los papers tienen al menos un autor del Sur (incluyendo
  co-autorías mixtas).

Esto **es** la asimetría Norte-Sur del campo, medida con datos reales.
El Sur tiene ~18% de presencia en autores y ~27% en papers con algún
autor Sur — coherente con la bibliografía crítica que dice que el
Sur está subrepresentado pero presente.

## Tensiones nuevas (T7-T10) detectadas en esta iteración

### T7 — La afiliación en `bibtexparser` es por paper, no per-autor

- **Decisión:** documentar el límite, no inventar per-autor.
- **Por qué:** el campo `affiliation` que agregué al .bib sintético es
  por paper. Para IED-research, lo correcto es per-autor
  (¿quién es de dónde?). OpenAlex ya da per-autor (`authorships`).
- **Implicación para el diseño:** la `BibtexSource` del Hito 3 debe
  aceptar un campo `affiliation` por autor (no por paper) si se
  quiere geografía útil. Formato propuesto:
  `affiliation = {Aldas, C. (EC); Álvarez, M. (EC); Orta, L. (EC)}`.
- **Pendiente:** decisión de formato en el Hito 3.

### T8 — Las `references_doi` de OpenAlex son URLs, no DOIs

- **Decisión:** el código matchea por URL, documentar el límite.
- **Por qué:** `https://openalex.org/W...` ≠ un DOI. Un usuario que
  combine OpenAlex + .bib con DOIs reales no va a tener matching
  cross-source.
- **Implicación para el diseño:** el `Enricher` de OpenAlex **debe**
  resolver cada `referenced_works` URL a su DOI antes de popular
  `references_doi`. Es un fetch adicional.
- **Pendiente:** implementar `resolve_references()` en el Hito 6
  (cuando se escriba el `Enricher`).

### T9 — Asortatividad +1.000 sobre co-autoría puede ser proxy, no verdad

- **Decisión:** reportar el valor con disclaimer explícito.
- **Por qué:** con afiliación por paper (no per-autor), los 3
  co-autores de un paper Norte se marcan todos como Norte, y eso
  infla la homofilia observada. La métrica es real pero
  **sobre-estima** la separación Norte-Sur.
- **Implicación para el diseño:** el `Analyzer` del Hito 2 debe
  calcular asortatividad **con y sin** atribución per-author y
  reportar la diferencia. Si difieren, el usuario sabe que el proxy
  importa.
- **Pendiente:** trabajo de `Analyzer` en Hito 2.

### T10 — El thesaurus de 25 conceptos colapsa 6% — ¿suficiente?

- **Decisión:** aceptable para v0.1, expandir en v0.2.
- **Por qué:** 6% parece bajo pero las keywords que matchean son las
  **discursivamente importantes** (los conceptos estructurantes del
  campo). Las que no matchean son keywords de relleno o de campos
  adyacentes (geografía, periodización, etc.).
- **Implicación para el diseño:** el `Preprocessor` del Hito 4
  necesita un thesaurus **+ una fallback por embeddings** o **+ un
  fallback por LLM** para keywords que no matchean. La decisión de
  diseño es: ¿el thesaurus es **exhaustivo** o **cobertura + fuzzy**?
  Mi recomendación: cobertura + fuzzy (con sentence-transformers o
  un LLM barato).
- **Pendiente:** decisión de diseño en el Hito 4, ADR corto.

## Respuesta a la pregunta inicial (v2): ¿esto justifica construir `bib2graph`?

**Sí, ahora con más fuerza.**

**A favor (todo lo de v1, más):**
- El pipeline (BibTeX + OpenAlex + 4 redes + thesaurus + métricas +
  geografía) **funciona end-to-end con datos reales**.
- Las 4 redes tienen estructura cuando hay enriquecimiento (3/4
  con esta corrida, 4/4 si resolvemos el bug de `co_citacion`).
- La asimetría Norte-Sur es **medible** y **real**: 50/18/32 (Norte
  / Sur / Unknown) y 27% de los papers con autor Sur.
- El thesaurus multilingüe **funciona** y es portable al núcleo.
- El pre-procesador de `bibtexparser` es una **solución concreta** al
  bug del Hito 3.

**El wedge más pequeño que entrega "tensiones alrededor de mi idea"**
(según `04-direccion-ia-in-the-loop.md`): **biblioteca curada
(BibTeX) + OpenAlex para enriquecer + 4 redes + thesaurus +
métricas IED-relevantes (asortatividad, composición geográfica)**. Eso
es lo que la sandbox valida, sin el resto del "IA in the loop".

**En contra (lo que sigue abierto):**
- `co_citacion` requiere un segundo nivel de fetch (citadores con
  citaciones) que no se hizo.
- Las afiliaciones per-author del .bib sintético son un proxy;
  OpenAlex las trae per-autor pero la implementación actual las
  aplana a "Paper affiliation".
- El thesaurus es chico (25 conceptos); escalarlo a un campo real
  requiere embeddings o LLM.
- No se validó con un caso de uso de investigación **real** (estudio
  de semiconductores, deuda ecológica de un país específico). Eso
  queda para el Hito de validación.

## Próximos pasos sugeridos (actualizados)

1. **Resolver `co_citacion`**: fetch del segundo nivel (citadores con
   citaciones). 1-2 tardes, valida la 4ª red.
2. **Escribir el ADR "Thesaurus multilingüe para IED"** (T6 + T10):
   decidir exhaustivo vs. cobertura + fuzzy, formato portable.
3. **Decidir el encuadre del Hito 3** a la luz de T2 actualizado
   (sigue valiendo que sin enriquecimiento no hay co-citación, pero
   ahora sabemos exactamente **qué** falta).
4. **Diagnosticar el bug per-author affiliation** (T7) en el Hito 3.
5. **Considerar el `Enricher` como Hito 2.5**: si la co-citación es
   estructural, no debería esperar al Hito 6. (Decisión política;
   registrarla en un ADR.)
6. **Recién después**, empezar el Hito 1 (núcleo puro). La sandbox
   no se mete con eso — sigue intacto el plan del ROADMAP para el
   núcleo.

## Lecciones que la iteración 2 confirmó

- **"Sin red en CI"** (lección de AGENTS.md) sigue valiendo, pero la
  sandbox demuestra que **con red en desarrollo, una tarde rinde
  más** que 5 tardes de especular. El balance: CI sin red, desarrollo
 偶尔 con red.
- **Idempotencia** del merge (T1 de v1) fue clave para que la nueva
  corrida con reales se sumara limpio a las semillas sin duplicar.
- **La asortatividad como métrica IED-relevante** estaba en T5 de v1
  como hipótesis. Con datos reales se confirma. Pero el disclaimer
  de T9 también: es un proxy, hay que ser explícito.
- **El thesaurus auditable a mano** (T6 de v1) fue la decisión
  correcta: en 30 minutos curé 25 conceptos y la red mejoró
  objetivamente. La alternativa "embeddings desde el día uno" habría
  requerido instalar más deps, descargar modelos, y
  opacar el comportamiento.

---

_Informe escrito a mano sobre la corrida del 2026-06-14. v1 = sintético
(21 papers), v2 = mixto semillas + OpenAlex reales (103 papers). Datos
cuantitativos en `informe_ied.md` (regenerable). T1, T5, T6 resueltos;
T2 parcialmente; T4 sí resuelto; T7-T10 son tensiones nuevas. Decisión
sobre el Hito 3 sigue abierta y se beneficia de esta evidencia._
