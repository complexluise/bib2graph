---
title: API de Python
---

# API de Python

Referencia de la **superficie pública de la librería** `bib2graph`, agrupada por
tema. Se **autogenera desde los docstrings** del código (mkdocstrings): si cambia
el código, cambia esta página.

Para usar la herramienta desde la terminal, mira la [referencia del CLI `b2g`](../cli.md).

!!! tip "Cómo leer esta referencia"
    Cada objeto muestra un **índice de sus miembros** al principio (haz clic para
    saltar) y un **ícono de tipo** —clase, método o atributo— en la tabla de
    contenidos de la derecha. Los tipos en las firmas son **enlaces**: haz clic
    para ir a su definición.

## Mapa de la API

<div class="grid cards" markdown>

-   :material-database: **[Corpus y persistencia](corpus.md)**

    El `Corpus` (tabla canónica en memoria), su `Manifest`, snapshots sellados y
    los backends (memoria / DuckDB) que lo respaldan.

-   :material-seed: **[Fuentes (siembra)](fuentes.md)**

    `Source` y sus implementaciones (OpenAlex, BibTeX): de una ecuación de
    búsqueda o un `.bib` al corpus inicial.

-   :material-graph-outline: **[Forrajeo y curación](forrajeo.md)**

    `Forager`, preview de crecimiento, preprocesamiento y filtros PRISMA para
    expandir y curar el corpus.

-   :material-vector-triangle: **[Redes (proyección)](redes.md)**

    `Networks` y los cinco proyectores: acoplamiento, co-citación, co-autoría,
    colaboración institucional y co-ocurrencia de keywords.

-   :material-chart-scatter-plot: **[Análisis de redes](analisis.md)**

    Métricas, centralidad, detección de comunidades, asortatividad y el informe
    de calidad de co-citación.

-   :material-export: **[Exportadores](exportadores.md)**

    `GraphMLExporter` y `CsvExporter` para llevar las redes a Gephi, Cytoscape o
    networkx.

</div>
