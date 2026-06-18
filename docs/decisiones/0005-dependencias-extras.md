# 0005 — Dependencias por extras + núcleo liviano

- **Estado:** Aceptada
- **Fecha:** 2026-06-14
- **Relacionada con:** [0002](0002-modelo-agnostico-backend.md), [0003](0003-persistencia-opcional.md), [0004](0004-enriquecimiento-opcional.md)

## Contexto

v0 forzaba la instalación de **todo**: el ODM de Neo4j (`neomodel`), clientes de tres APIs
externas (S2, CrossRef, Scopus), librerías de visualización y de fuzzy matching, aunque el
usuario solo quisiera construir una red de keywords desde un BibTeX. Al mismo tiempo
arrastraba un defecto opuesto: `python-louvain` se **importaba sin estar declarado** en
`pyproject.toml`, degradando Louvain a modularidad voraz en silencio cuando faltaba.

Con el núcleo agnóstico (0002) y las costuras opcionales (0003, 0004), la mayoría de esas
dependencias solo hacen falta para capacidades específicas.

## Decisión

Definir un **núcleo liviano** y mover lo opcional a **extras** de instalación:

- **Núcleo (siempre):** `pandas`, `networkx`, `click`, `tqdm`.
- **Extras:**
  - `[neo4j]` → persistencia Neo4j.
  - `[s2]` / `[crossref]` / `[scopus]` → enriquecedores (crossref/scopus, futuros).
  - `[viz]` → `matplotlib`, `seaborn`.
  - `[dedup]` → `fuzzywuzzy`, `python-levenshtein`.

Regla transversal: **se declara todo lo que se importa** y se **falla fuerte, no en
silencio** cuando falta una dependencia requerida (Louvain incluido). **`notebook`/Jupyter
es solo dependencia de desarrollo, nunca de runtime.**

## Consecuencias

- Instalación mínima rápida y reproducible; el usuario paga (en dependencias) solo por lo
  que usa.
- `pip install bib2graph[neo4j,s2]` expresa explícitamente las capacidades requeridas.
- Si falta una dependencia de un extra activado, el error es claro y temprano, no una
  degradación silenciosa.
- Costo: hay que mantener la matriz de extras y verificar que cada capacidad importe sus
  deps de forma perezosa, con mensaje útil si el extra no está instalado.

## Enmienda — 2026-06-16 (`[dedup]` = `rapidfuzz`; `splink` diferido)

> AS-BUILT del Hito 7 (ver ADR [0026](0026-dedup-fuzzy-determinista.md)). El cuerpo de arriba lista
> `[dedup] → fuzzywuzzy, python-levenshtein` (legado v0). **`fuzzywuzzy` está abandonado** (GPL, sin
> releases); su sucesor mantenido y permisivo (MIT) es **`rapidfuzz`**. El extra queda:
> **`[dedup] = rapidfuzz>=3,<4`** (import perezoso, `ImportError` accionable → `uv sync --extra
> dedup`). `splink` (record-linkage probabilístico, pesado, no-determinista) **queda diferido a
> post-V1** (ADR 0026). El resto de la matriz de extras no cambia.

## Enmienda — 2026-06-18 (`[dedup]` ELIMINADO; `rapidfuzz` al núcleo — supersede la enmienda anterior)

> AS-BUILT de #88 (ver ADR [0031](0031-preprocesamiento-automatico-en-ingesta.md)). Al volverse el
> dedup **automático en cada ingesta** (ya no opt-in), `rapidfuzz` es requerido siempre: el extra
> `[dedup]` se **elimina** y `rapidfuzz>=3,<4` pasa a **`[project.dependencies]`** (núcleo). El import
> en `preprocessors/dedup.py` deja de ser perezoso. Esto supersede la enmienda 2026-06-16 de arriba
> (ya no hay `uv sync --extra dedup`). Coherente con la regla "se declara todo lo que se importa": una
> dependencia del camino caliente va en el núcleo, no en un extra que produciría un corpus sin
> deduplicar en silencio. El resto de la matriz de extras no cambia.
