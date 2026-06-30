---
title: Inicio
---

# bib2graph

> De una búsqueda bibliográfica a **redes de citación reproducibles** — una
> biblioteca de literatura que curas tú, sin servidores ni planillas.

**bib2graph** toma una ecuación de búsqueda (o un archivo `.bib`), trae papers
desde [OpenAlex](https://openalex.org), te deja **curarlo** y lo proyecta a
**redes bibliométricas** listas para analizar en Gephi, Cytoscape, networkx o donde quieras:
acoplamiento bibliográfico, co-citación, co-autoría, colaboración institucional y co-ocurrencia de keywords.

El corpus **persiste y crece** entre sesiones, y el resultado es **reproducible**:
mismo input, mismas redes.

!!! warning "Alpha"
    Mientras la versión sea `0.x`, la API puede cambiar entre releases menores.
    Úsalo para explorar y validar, no como dependencia estable de producción
    todavía.

---

## Elige tu camino

¿Cómo quieres usar bib2graph? Cada flujo es válido.

<div class="grid cards" markdown>

-   :material-robot: **Sin instalar nada (5 min)**

    Cuéntale a Claude, ChatGPT o MiniMax tu tema de investigación.
    El agente trae papers, construye redes, tú descargas resultados.
    
    👉 [Tutorial: Usuario no técnico](tutoriales/claude-code.md)

-   :material-code-braces: **Aprendiendo paso a paso (3–4 horas)**

    Instala bib2graph. Sigue 10 pasos: desde pregunta hasta reporte.
    Ejecutas cada comando, entiendes cómo funciona todo.
    
    👉 [Tutorial completo: De la pregunta al reporte](tutoriales/sota-completo.md)

-   :material-hammer-wrench: **Hibrido: CLI + agente (1–2 horas)**

    Instala bib2graph. El agente te ayuda con las partes difíciles.
    Tú ejecutas comandos. Usa guías rápidas para decisiones.
    
    👉 [Guías prácticas](guias/index.md)

</div>

---

## Primeros pasos

<div class="grid cards" markdown>

-   :material-download: **[Instalación](getting-started/installation.md)**

    Instala `bib2graph` con `uv` o `pip` en un minuto.

-   :material-rocket-launch: **[Quickstart](getting-started/quickstart.md)**

    El ciclo mínimo en 2 minutos — desde ecuación a GraphML.

-   :material-api: **[Referencia](reference/cli.md)**

    El CLI `b2g`, API de Python, y glosario de términos.

</div>

## Qué hace

- **Siembra** desde una ecuación de búsqueda (OpenAlex) o un archivo BibTeX.
- **Expande** el corpus siguiendo citaciones, rankeando candidatos por
  estructura — sin IA.
- **Curas tú:** acepta/rechaza papers, filtros PRISMA, todo versionable en CSV.
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
