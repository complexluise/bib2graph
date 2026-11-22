# 0042 — Semantic Scholar como 2º motor de extracción: siembra exige key, forrajeo no; query nativa sin traducción

- **Estado:** Aceptada (2026-11-21, decisión del PO: S2 como 2º backbone — Nota 25; wiring end-to-end en ADR 0053)
- **Fecha:** 2026-06-30
- **Encuadre:** síntesis de la IA (architect) a partir de un probe empírico de la Academic Graph
  API de S2 + deep-research citado; **la decisión la toma el PO**. Este ADR **no** re-decide la
  intercambiabilidad de motores (ya decidida en [0036](0036-identidad-source-id-agnostica-doi-ancla.md));
  registra solo lo que es **nuevo y específico de S2** y que 0036 no resolvió.
- **Realiza:** [0036](0036-identidad-source-id-agnostica-doi-ancla.md) (que redefinió OpenAlex como
  **un** motor intercambiable y **difirió explícitamente** "el hito del 2º motor (Semantic Scholar),
  follow-up [#120](https://github.com/complexluise/bib2graph/issues/120)": población de `external_ids`
  y selector CLI `--source`). Este ADR es ese hito.
- **Enmienda el linaje de:** [0012](0012-openalex-credenciales.md) (su principio "el primer flujo de
  10 min corre sin claves obligatorias" se cumple en OpenAlex pero **no** en la **siembra** de S2 —
  ver D2).
- **Refuerza:** [0018](0018-source-agnostico-calidad.md) (otra `Source` que solo se acopla en la
  costura, sin tocar el núcleo) y [0007](0007-openalex-backbone.md) (S2, antes "costura futura
  opcional", entra como 2º backbone real).

## Contexto

ADR 0036 desacopló el núcleo del nombre del motor y dejó la infraestructura lista para enchufar un
2º motor: `_compute_id` ancla en DOI (`doi > source_id > tt`), el `source_id` es genérico, el motor
vive en `provenance.source`, y existe la tabla lateral `external_ids(paper_id, engine, id)` (infra
ya en `backends/base.py`: `add_external_id`, `external_ids_for`, `all_external_ids`). Lo que 0036
difirió "hasta que exista un 2º motor" llegó: **Semantic Scholar (S2)**.

Hechos del probe empírico (Academic Graph API, base `https://api.semanticscholar.org/graph/v1`,
gratuita) que **cambian la ecuación** respecto de OpenAlex:

- **Asimetría de credenciales por rol.** Los endpoints de **grafo de citas**
  (`/paper/{id}/references`, `/paper/{id}/citations`, `POST /paper/batch`) responden **200 sin key**.
  Pero `/paper/search` da **429 sostenido sin key** (aun con backoff de 8 s). Es decir: el rol
  **sembrador** de S2 **prácticamente exige** la API key (gratuita, carril ~1 RPS); el rol
  **forrajeador/materializador** funciona **sin key** a bajo volumen. En OpenAlex ambos roles corren
  sin key (ADR 0012). Esto **dobla** —no rompe— el principio de 0012 y hay que hacerlo **consciente**.
- **Sintaxis de búsqueda propia.** S2 **no** es WoS y **no** comparte la sintaxis de OpenAlex: no hay
  capa de traducción WoS→S2 análoga a `_translate` de OpenAlex. Hay que **decidir** cómo se mapea la
  ecuación del usuario.
- **El grafo de citas viene directo.** `/paper/{id}/citations` devuelve los **papers citantes** como
  objetos (`citingPaper`), con paridad de campos. No hace falta el truco de OpenAlex
  (`cites:W1|W2|…` + cruzar `references_id` del citante para atribuir). Es una divergencia de
  **implementación** del forward chaining, no de contrato.
- **Identidad cross-motor gratis.** S2 expone `externalIds.DOI`. Un paper de S2 con DOI obtiene el
  **mismo `id`** que en OpenAlex (D1' de 0036) → **deduplica cross-motor sin trabajo extra**, y su
  `paperId` se puede registrar en `external_ids(engine="semanticscholar")`.

> Nota de frontera (PO): la **licencia de los datos** del proveedor no es criterio de bib2graph (es
> del consumidor programático). Este ADR es solo contrato técnico; el motor es agnóstico a la fuente.

## Decisión

### D1 — `SemanticScholarSource` implementa `Source` (paridad de costura con OpenAlex)

Una `Source` nueva en `src/bib2graph/sources/semanticscholar.py` que cumple el Protocol `Source`
(`seed`/`load`) y entrega el **mínimo universal** (ADR 0018: `id`, `title`, `year`, `authors_raw`,
`keywords_raw`) más el enriquecimiento que S2 sí trae (`doi`, `source_id`=`paperId`, `references_id`,
`references_doi`, `cited_by_id`, `abstract`). Replica los métodos **duck-typed** que el `Forager`
consume por `hasattr` —`fetch_citing_batch` / `fetch_citing_batch_with_works`— y
`fetch_works_by_ids`. El **núcleo no se toca** (criterio PRD §10 / 0018). El `paperId` de S2 se mapea
a `source_id` **en el límite** del adaptador; el motor se registra como `provenance.source =
"semanticscholar"`.

### D2 — Credenciales: misma política inyectada que 0012, con asimetría declarada por rol

`SemanticScholarSource` acepta `api_key` **inyectada** (argumento → entorno `S2_API_KEY` → ausencia),
**nunca embebida** (lección 1, igual que 0012). Asimetría **declarada y avisada** (lección 7):

- **`seed()` sin key** → el 429 de `/paper/search` aflora como **`NetworkError`** (exit 4) accionable
  que nombra el remedio: **obtener una API key gratuita de S2** (carril dedicado). No se reintenta en
  silencio hasta el infinito: paralelo al `_MSG_RATE_LIMIT_429` de OpenAlex, pero el remedio es la
  key, no el polite pool.
- **forrajeo/materialización sin key** → funciona a bajo volumen; con key, mejor rate limit.

Esto **dobla** el principio de 0012 ("primer flujo de 10 min sin key obligatoria"): para S2 la
siembra sí la pide. Es un trade-off **consciente**, no una degradación silenciosa.

### D3 — La ecuación se pasa **nativa** a S2; el `translation_report` lo declara honesto

No se construye una capa de traducción WoS→S2. `seed(query)` pasa la `query` como **sintaxis nativa
de S2** a `/paper/search` (relevance). `SeedResult.executed_query` = la query exacta enviada;
`SeedResult.translation_report` declara **explícitamente** que **no hubo traducción** (la ecuación se
interpreta con la sintaxis de S2, distinta de WoS y de OpenAlex) — misma honestidad de "consciencia
de traducción" de 0007, aplicada al caso "sin traducción". *(Una traducción WoS→S2 más rica, si se
quiere, es trabajo futuro separado; no es de este hito.)*

### D4 — Población de `external_ids` (cierra la mitad de #120)

Cuando S2 entrega `paperId` y el paper tiene DOI (mismo `id` cross-motor), el adaptador registra
`external_ids(paper_id, engine="semanticscholar", id=paperId)` usando la infra ya existente. Esto es
lo que 0036 difirió "sin consumidor con OpenAlex único"; S2 es el consumidor. *(Cablear la
**escritura** de `external_ids` puede recortarse a un PR aparte si el primer PR queda grande — ver
Consecuencias; lo que NO se difiere es que el `paperId` viva en `source_id`.)*

### D5 — Fuera de este ADR / hito: el selector CLI `--source`

El **selector `--source <engine>`** (D-CLI de 0036, la otra mitad de #120) **no** entra acá. Hoy el
CLI instancia `OpenAlexSource` hardcodeado en 4 comandos (`seed`/`enrich`/`chain`/`build`). Exponer el
motor en la CLI es su **propio PR** (toca contrato `docs/API.md` → puede requerir su propia
enmienda/ADR de superficie CLI, linaje 0037/0038) y depende de que esta `Source` exista primero. Una
idea por PR (regla del repo).

## Consecuencias

- **(+) S2 entra como 2º backbone real** sin tocar el núcleo: valida empíricamente la tesis de 0036
  (motores intercambiables) y de 0018 (acople solo en la costura). Si 0036 funcionó, agregar S2 es
  "una `Source` nueva".
- **(+) Dedup cross-motor gratis** vía DOI (D1' de 0036): un paper con DOI traído por OpenAlex y por
  S2 colapsa al mismo `id`; ambos `paperId`/`openalex_id` quedan en `external_ids` (D4).
- **(− contrato, diferido) `docs/API.md` §2** gana una 2ª `Source` documentada (mínimo vs
  enriquecimiento que S2 cubre, política de credenciales D2). El **selector `--source`** y su cambio
  de convención CLI quedan para el PR de D5.
- **(− consciencia) La siembra de S2 pide key.** Hay que documentarlo en `--help`/README/API cuando
  llegue, y **testear ambos caminos** (con y sin key) contra API mockeada, sin red en CI.
- **(riesgo) Divergencias S2↔OpenAlex** que el coder debe cuidar (no son decisiones, son cuidado de
  implementación): IDs de citantes vienen directos (no por cruce de `references_id`); `paperId` es
  hash propio, no URL; consulta por DOI vía prefijo `DOI:10.…`; `keywords` de S2 es pobre/ausente
  (puede caer a `fieldsOfStudy`/`s2FieldsOfStudy` → `research_areas`/`keywords_raw`, declararlo);
  paginación y límites de campos por endpoint distintos (`batch` ≤500 vs `cites:` ≤50 de OpenAlex).

## Alternativas

- **No hacer ADR, basta el contrato `Source` + 0036.** Rechazada: 0036 decidió la *intercambiabilidad*
  pero **no** la asimetría de credenciales por rol (D2, que dobla 0012) ni el mapeo de query nativa
  (D3). Son decisiones reales nuevas; sin registrarlas, el coder las improvisa y se pierde el "porqué".
- **Capa de traducción WoS→S2 en este hito.** Rechazada por alcance: infla el PR y mezcla dos ideas.
  La query nativa + reporte honesto (D3) entrega valor ya; la traducción rica es trabajo futuro.
- **Meter el selector `--source` en el mismo PR.** Rechazada: dos ideas (motor nuevo + cambio de
  superficie CLI/contrato). Viola "una idea por PR" y mezcla un cambio de `docs/API.md` con la costura.

## Enmienda (2026-11-21) — alineación con contratos 0.15.x al rebasar #250

Al rebasar el PR sobre la rama de integración (0.13→0.15.1) el adaptador se alineó con contratos
posteriores, sin revertir el principio de D2 ("no reintentar en silencio hasta el infinito"):

- **Retry acotado en `seed()`** (como el `seed` de OpenAlex desde #287): hasta 3 intentos con
  backoff 1 s / 2 s ante 429/5xx, en `/paper/search`, `/paper/batch` y `/citations`. Al agotarse,
  `NetworkError` con `subcode` tipado (`RATE_LIMITED` / `UPSTREAM_TIMEOUT`, ADR 0045). El mensaje
  de 429 distingue si ya hay API key (no pide una key a quien ya la pasó).
- **Provenance:** las semillas llevan `source_kind="seed_equation"` (ADR 0050 D2).
- **`EquationRef`:** `engine="semanticscholar"`, `created_at` y `params` (`raw_query`,
  `max_results`, `executed_query`, `translation_report`) (ADR 0050 D1/D3).
- **`max_results` ∈ 1..1000** (límite offset+limit de `/paper/search`): fuera de rango → `ValueError`.
- **Límite conocido:** la siembra no pide `references` (no verificado que `/paper/search` lo acepte);
  las semillas quedan sin `references_*` hasta materializarlas por ID. Follow-up con llamada real.

El wiring end-to-end (`--source`, Forager) lo fija el ADR 0053 (multi-proveedor).

## Enmienda (2026-11-21) — token `s2` y selector `--source` realizados (ADR 0053, #251)

Append-only. ADR [0053](0053-multiproveedor-seleccion-coexistencia-identidad.md) D1.6 fija un token por
proveedor en todo el sistema: donde este ADR dice `"semanticscholar"` (D1 `provenance.source`, D4
`external_ids(engine=…)` y la enmienda anterior `EquationRef.engine`) el valor vigente es **`s2`**
(`Provider.S2`), igual que en `--source s2` y `workspace.json.source`. Desde #251 el adaptador emite
`engine="s2"` y `source_tag="s2"`. Sin datos con la etiqueta vieja: S2 no era usable por CLI antes.

**D5 realizado:** el selector `--source {openalex,s2}` existe en `init`/`seed`/`chain`/`build` (ADR
0053 D1). Las capacidades de S2 se declaran en `sources/registry.py`: `seed`, `backward`, `forward`,
`enrich_cited_by`; **no** `seed_filters` (coherente con D3: la query va nativa, así que
`--native`/`--exclude`/`--min-year`/`--max-year` → exit 3), `enrich_refs_doi` ni `resolve_doi`. La
credencial (D2) entra solo por el entorno `S2_API_KEY`; `--email` con `s2` → exit 1.
**D4 sigue pendiente:** la escritura de `external_ids` es el Corte 2 de 0053 (#255).
