# 17 — Validación con tercero (Gate #34): uso real de v0.7.0 desde TestPyPI

> ⚠️ **NOTA DE SESIÓN — no es decisión ni ADR.** Traduce a retroalimentación accionable el
> informe técnico de un **tercero** (agente IA `opencode`/minimax + colega) que usó
> `bib2graph==0.7.0` (instalado desde **test.pypi**) en un proyecto real —
> *"Pensamiento complejo en educación"* — corriendo el pipeline completo `init → seed
> --from-bib → enrich → chain → build → export` sobre 540 papers en Windows 11.
> Fecha: 2026-06-18. Es la primera **validación externa no asistida** → alimenta el **Gate
> #34**. Documento hermano: [`16-retroalimentacion-gui-mvp.md`](16-retroalimentacion-gui-mvp.md)
> (mi propia prueba de la GUI). Fuente: `pensamiento-complejo-en-educacion/.../analisis/`
> (`informe_tecnico_bib2graph.md`, `informe.md`).

## Veredicto del tercero (textual, resumido)

> "La librería es un buen esqueleto y los projectors están bien implementados, pero **necesita
> babysitting**: no es 'agente-native out of the box' como anuncia el CLI." El pipeline se
> completó **solo gracias a 5 scripts puente** que el colega tuvo que escribir
> (`resolve_dois.py`, `forward_chain.py`, `dedup.py`, `build_t4_t7.py`, `analisis/*`).

Lo importante: un tercero técnico **pudo** llegar a redes y figuras publicables, pero el flujo
**BibTeX-local** lo obligó a salirse de la herramienta en cinco puntos. Esa es la señal.

## Corroboración cruzada con la GUI (Nota 16)

La red `bibliographic_coupling` del colega es de **489 nodos / 20.535 aristas** — **exactamente**
la que cuelga la vista de grafo de la GUI (Nota 16 §H2). El mismo corpus real revienta el
render. Confirma que **489/20.535 es escala normal**, no un caso extremo: limitar el grafo es
requisito, no lujo.

---

## Triage de hallazgos

Clasificados honestamente: **BUG** (defecto de código real), **GAP** (falta de feature),
**FRICCIÓN** (entorno/empaquetado/expectativa), **NICE** (mejora opcional).

### 🔴 BUG-1 — `_enrich_cited_by`: mismatch de formato de `openalex_id` (CRÍTICO)

El corpus guarda `openalex_id` con prefijo URL (`https://openalex.org/Wxxx`), pero
`OpenAlexSource.fetch_citing_batch` devuelve el dict con keys en **formato corto** (`Wxxx`).
El lookup `citing_dict.get(url_completa)` **siempre falla → `[]`**, así que la pasada 8b del
Enricher (poblar `cited_by_id`) queda **inútil**: `citing_new=0` con `citing_targets=18`.

- **Severidad:** alta — rompe el forward chaining real (el colega lo reescribió en
  `forward_chain.py`, 130 líneas).
- **Repro mínimo del tercero:**
  ```python
  from bib2graph import OpenAlexSource
  src = OpenAlexSource(email='...')
  src.fetch_citing_batch(['https://openalex.org/W2528590784'])
  # → {'W2528590784': [...]}  ← key corta; el Enricher busca la URL completa → KeyError → []
  ```
- **Fix:** normalizar a un solo formato en el borde (o el lookup que tolere ambas keys).
  Es de una línea de política + un test de regresión. **Candidato a fix inmediato.**

### 🔴 BUG-2 — Schema DuckDB rígido rompe el casteo con columnas extra

`backends.duckdb._arrow_table_from_con` castea la tabla al `CORPUS_SCHEMA` oficial (23 cols).
Agregar columnas (el colega probó `cited_by_api_url`, `cited_by_count`) **rompe el casteo**
con `ValueError: field names not matching`. Tuvo que mover metadata a una tabla lateral.

- **Severidad:** media — anti-patrón de extensibilidad, no bloquea el flujo canónico.
- **Decisión de diseño (para el PO/ADR):** ¿el backend debe tolerar columnas extra, o el
  schema debe ser extensible por el usuario? Hoy es deliberadamente estricto. **No parchar sin
  decidir** — toca el contrato del store.

### 🟠 GAP-1 — `seed --from-bib` no resuelve DOIs → OpenAlex IDs (el gap que más duele)

`seed --from-bib` carga las entradas pero deja `openalex_id=NULL`. Sin ID, `enrich` y `chain`
(forward y backward) devuelven **0**. Es la causa raíz que encadena casi todo el dolor del
flujo BibTeX. El colega lo resolvió a mano (`resolve_dois.py`: itera `GET /works/doi:<doi>`).

- **Propuesta del tercero:** comando nativo `b2g from-bib-resolve` (o que `--from-bib` resuelva
  DOIs automáticamente como paso opcional). **Es lo que más necesita cualquier usuario BibTeX.**
- **Relacionado API:** falta `fetch_dois_to_openalex_ids(dois)` (existe `fetch_works_by_ids`,
  pero parte de IDs ya OpenAlex, no de DOIs).

### 🟠 GAP-2 — `--email` incompatible con `--from-bib`

El email del polite-pool de OpenAlex solo se acepta en modo ecuación, no en `--from-bib`. Pero
la resolución de DOIs **también** pega a OpenAlex → debería aceptar `--email`. Inconsistencia.

### 🟠 GAP-3 — No hay `b2g dedup`

Dedup por `openalex_id` normalizado lo escribió el colega a mano (`dedup.py`, normaliza
`https://openalex.org/Wxxx ↔ Wxxx` + `ROW_NUMBER()`). Operación universal que debería ser nativa.

### 🟡 GAP-4 — `NetworkSpec` no filtra por keyword

Para sub-redes temáticas (T4/T7) el `NetworkSpec` (Pydantic) no soporta `keyword_filter`; hubo
que invocar los projectors directo desde Python (`build_t4_t7.py`). Sub-redes por término es un
caso de uso obvio.

### 🟡 GAP-5 — GraphML export no preserva atributos legibles del nodo

Los nodos de `bibliographic_coupling` salen con ID canónico (`oa:<hash>` / `doi:<hash>`) **sin
`title`**; autores como ORCID sin nombre. Hay que reabrir en Gephi y hacer join con
`library.duckdb`. → Es el **issue #25** ya conocido (label injection). Confirma que sigue vivo
y duele en uso real.

### 🟡 GAP-6 — No hay `b2g stats` / `b2g quality` ni `b2g plot`

Métricas de completitud, centralidades, comunidades Louvain y las 7 figuras: todo desde cero
con scripts (`analisis/*`). El `metrics.json` de las redes es pobre (nodes/edges/density/top
degree/betweenness; **sin** eigenvector, clustering coeff ni comunidades). Reportería y
visualización quedan 100% fuera de la herramienta.

### 🟡 GAP-7 — API: falta `ingest`, provenance no introspectable

`fetch_works_by_ids` devuelve un `Corpus` pero **no inserta** en el store vivo (hay que hacer
SQL). No hay `source.ingest(corpus)`. El `loop_state_log`/provenance no tiene API de consulta
("dame los rechazados con motivo") → SQL directo sobre `corpus.provenance`.

### 🟠 FRICCIÓN-1 — Instalación desde TestPyPI (deps transitivas no resolubles)

`pip/uv install -i test.pypi bib2graph` **falla**: `httpx` (y otras deps) no están publicadas
en test.pypi. El colega tuvo que `--no-deps` + instalar deps a mano desde el índice principal.
El extra `[gui]` **tampoco** resuelve (instaló `fastapi`/`uvicorn[standard]` a mano). ~15 min de
fricción + ambiente roto en una segunda sesión.

- **Matiz importante (corregir la lectura del informe):** la metadata **sí** declara las deps;
  el problema es que **TestPyPI no hostea paquetes de terceros** (httpx, pydantic…) — es una
  limitación *conocida y esperada* de TestPyPI, no metadata incorrecta. El `--no-deps` + índice
  principal es el workaround estándar.
- **Fix real:** publicar en **PyPI estable** (issue #104, ya abierto, diferido a post-validación).
  Esta nota es parte de esa validación → **#104 sube de prioridad.** Mientras tanto: documentar
  el comando exacto de install desde TestPyPI (`--no-deps` + deps del índice real).

### 🟡 FRICCIÓN-2 — Sin README en el wheel; activación en Windows no documentada

El wheel no trae README; el flujo Windows+uv (`.venv/Scripts/b2g.exe` vs `uv run b2g` vs activar
venv) no está documentado. Quick-start de instalación/uso ausente. **Conecta con Nota 16 §H3**
(doc densa por dentro, pero **ausente en el punto de entrada del usuario nuevo**).

---

## Lo que funcionó bien (conservar — no romper en la iterada)

- ✅ **Flujo online** `seed --equation` (búsqueda directa OpenAlex): "funciona muy bien".
- ✅ `init`, `filter`, `status`, `build --corpus-scope all`, `export --format graphml`: 🟢.
- ✅ **Projectors** (`CoCitation`, `BibliographicCoupling`, …): "bien diseñados, fáciles de
  invocar desde Python".
- ✅ **Reproducibilidad**: `corpus_hash` sellado en redes + `loop_state_log` — "features que
  pocas libs tienen".
- ✅ La idea de **CLI agente-native con workspaces reproducibles**: "excelente".

---

## Priorización propuesta (para discutir con el PO)

| # | Item | Tipo | Esfuerzo | Prioridad |
|---|---|---|---|---|
| BUG-1 | `_enrich_cited_by` formato id | bug | bajo | **1 — ya** |
| GAP-1 | `from-bib` resuelve DOIs | feat | medio | **2** (BibTeX 1ª clase) |
| GAP-2 | `--email` en `--from-bib` | feat | trivial | **2** (BibTeX 1ª clase) |
| FRICCIÓN-1 | PyPI estable + doc install | empaq | medio | **3** (#104) |
| FRICCIÓN-2 / 16§H3 | README/quick-start + aligerar doc | docs | bajo | **4** |
| GAP-3 | `b2g dedup` nativo | feat | bajo | 5 |
| GAP-5 / #25 | label/title en GraphML | bug | bajo | 5 |
| BUG-2 | schema extensible | diseño | — | decidir (ADR) |
| (nuevo) | import multi-formato (RIS/EndNote/CSV) | feat | medio | backlog (BibTeX 1ª clase) |
| GAP-4/6/7 | spec keyword, stats/plot, ingest | feat | alto | backlog |

**Observación de fondo:** todo el dolor se concentra en el **flujo BibTeX-local** (sembrar desde
un `.bib` curado a mano). El flujo **online** (ecuación) está sano.

> **DECISIÓN DEL PO (2026-06-18): el flujo BibTeX es de PRIMERA CLASE.** Razón: el investigador
> **descarga el `.bib` (u otros formatos: RIS, EndNote, CSV) desde las páginas web
> institucionales** (bases de datos, bibliotecas, repositorios) — no todo está en OpenAlex ni
> todo arranca por una ecuación. La importación desde archivo es una **puerta de entrada real y
> primaria** al corpus, no un import de segunda. → Cerrar bien **BUG-1 + GAP-1 + GAP-2** es
> prioritario, y considerar **otros formatos de importación** además de BibTeX (RIS al menos).

## Próximos pasos (no decididos)

- [ ] **BUG-1** — fix de normalización de `openalex_id` + test de regresión (candidato inmediato).
- [x] **Decidido:** flujo BibTeX-local es **primera clase** (descarga desde fuentes institucionales).
- [ ] **GAP-1 + GAP-2** — `from-bib` resuelve DOIs→OpenAlex IDs (con `--email`); cerrar la cadena
      `--from-bib → enrich → chain`. Prioridad alta tras BUG-1.
- [ ] Evaluar **import multi-formato** (RIS / EndNote / CSV) además de BibTeX — mismo motivo
      (descarga desde páginas institucionales).
- [ ] **#104** — publicar en PyPI estable; documentar install desde TestPyPI mientras tanto.
- [ ] **BUG-2** — decisión de diseño sobre extensibilidad del schema (¿ADR?).
- [ ] Cerrar **#25** (label/title en GraphML) — confirmado en uso real.
- [ ] Quick-start de install/uso en el wheel (atado a Nota 16 §H3, aligerar doc).
