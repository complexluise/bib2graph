---
title: Inicio
---

# bib2graph

> De una búsqueda bibliográfica a **redes de citación reproducibles** — una
> biblioteca de literatura que curás vos, sin servidores ni planillas.

**bib2graph** toma una ecuación de búsqueda (o un archivo `.bib`), arma un corpus
de papers desde [OpenAlex](https://openalex.org), te deja **curarlo** y lo
proyecta a **redes bibliométricas** listas para analizar en Gephi, Cytoscape,
networkx o donde quieras: acoplamiento bibliográfico, co-citación, co-autoría,
colaboración institucional y co-ocurrencia de keywords.

El corpus **persiste y crece** entre sesiones, y el resultado es **reproducible**:
mismo input, mismas redes.

!!! warning "Alpha"
    Mientras la versión sea `0.x`, la API puede cambiar entre releases menores.
    Úsalo para explorar y validar, no como dependencia estable de producción
    todavía.

## Empezá acá

<div class="grid cards" markdown>

-   :material-download: **[Instalación](getting-started/installation.md)**

    Instalá `bib2graph` con `uv` o `pip` en un minuto.

-   :material-rocket-launch: **[Quickstart](getting-started/quickstart.md)**

    De una ecuación a un GraphML, sin escribir código.

-   :material-book-open-variant: **[Tutoriales](tutoriales/index.md)**

    Desde tu primer mapa en 5 minutos hasta un reporte de SOTA riguroso.

-   :material-silverware-fork-knife: **[Guías](guias/index.md)**

    Recetas para tareas concretas de investigación.

-   :material-api: **[Referencia](reference/cli.md)**

    El CLI `b2g` y la API de Python, autogeneradas desde el código.

</div>

## Qué hace

- **Siembra** desde una ecuación de búsqueda (OpenAlex) o un archivo BibTeX.
- **Expande** el corpus siguiendo citaciones, rankeando candidatos por
  estructura — sin IA.
- **Curás vos:** aceptar/rechazar papers, filtros PRISMA, todo versionable en CSV.
- **5 redes bibliométricas:** acoplamiento, co-citación, co-autoría,
  instituciones, co-keywords.
- **Sub-redes temáticas** filtrando por keyword.
- **Biblioteca persistente** (DuckDB) que crece entre sesiones.
- **Reproducible:** mismo corpus → mismas redes y comunidades (hash de contenido).
- **Dos interfaces:** CLI scriptable (`b2g`, salida `--json`) y librería de Python.
- **Exporta** a GraphML/CSV para Gephi, Cytoscape, networkx, etc.

## Cómo se construye (y la IA)

bib2graph se desarrolla **con la IA en el lazo**: una persona plantea el problema,
decide y **aprueba cada cambio**; modelos de IA implementan el código, los tests y
la documentación bajo esa dirección. **El producto en sí no usa IA generativa** —
el ranking del forrajeo es estructura bibliométrica determinista (acoplamiento,
co-citación, centralidad), sin LLM ni embeddings, y la curación es 100% humana. El
detalle está en [IA en el desarrollo](ai-disclosure.md).

## Licencia

[GPL-3.0-or-later](https://github.com/complexluise/bib2graph/blob/main/LICENSE) —
software libre con copyleft fuerte: cualquier derivado que se distribuya debe
seguir siendo libre y de código abierto. Es deliberado: esta herramienta queda
para la comunidad y no puede cerrarse en un producto propietario.
