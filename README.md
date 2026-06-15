# bib2graph

**bib2graph** es una librería de Python (con una CLI delgada encima) para transformar
corpus bibliográficos en **redes bibliométricas** listas para analizar: co-citación,
colaboración de autores, colaboración de instituciones y co-ocurrencia de palabras clave.

> Estado: **reescritura clean-room en curso.** Este repositorio contiene primero la
> documentación de diseño; el código se construye según el [roadmap](docs/ROADMAP.md).

## La arquitectura en un párrafo

bib2graph es **un núcleo puro rodeado de cuatro costuras opcionales**. El núcleo opera
siempre sobre un **`Corpus` en memoria** (datos planos: `Paper`, `Author`, `Keyword`,
`Institution` y sus relaciones), nunca sobre una base de datos viva, y produce las redes
(`networkx`), métricas, comunidades y exportaciones (GraphML/CSV) como **funciones puras y
testeables**. Alrededor hay cuatro puntos de extensión enchufables: **`Source`** (cargar un
corpus; BibTeX de referencia), **`Enricher`** (aumentarlo, opt-in; Semantic Scholar de
referencia), **`Store`** (persistir, opcional; en memoria por defecto, Neo4j como adaptador)
y el conjunto **proyector → analizador/exportador** del núcleo. El pipeline mínimo corre
**en memoria, sin servidores ni claves de API**.

El estudio sobre la **cadena de suministro de semiconductores** es el **caso validador**, no
el producto.

## Por qué se reescribió

La v0 tenía a Neo4j como modelo de datos: nada existía ni se podía probar sin un servidor
corriendo. La reescritura mueve toda la lógica a un núcleo puro y deja persistencia y
enriquecimiento como costuras opcionales. El postmortem completo (con las 7 lecciones y las
reglas de diseño que las responden) está en [`docs/Notas/01-lecciones-v0.md`](docs/Notas/01-lecciones-v0.md).

## Documentación

| Documento | Qué cubre |
|-----------|-----------|
| [`docs/PRD.md`](docs/PRD.md) | Producto: usuarios, problema, valor, alcance. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitectura objetivo: núcleo + cuatro costuras, flujo de datos. |
| [`docs/API.md`](docs/API.md) | Contratos públicos: `Corpus`, `Source`, `Enricher`, `Store`, proyectores, analizadores, exportadores. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Secuencia de construcción desde cero (núcleo y tests primero). |
| [`docs/referentes.md`](docs/referentes.md) | Mapa del ecosistema (metaknowledge, bibliometrix, VOSviewer, OpenAlex…) y dónde está el hueco. |
| [`docs/critica-base.md`](docs/critica-base.md) | Red team del concepto actual: qué se rompe y hacia dónde rediseñar. |
| [`docs/decisiones/`](docs/decisiones/) | ADRs: decisiones de arquitectura y su porqué. |
| [`docs/Notas/01-lecciones-v0.md`](docs/Notas/01-lecciones-v0.md) | Postmortem de v0 y reglas de diseño adoptadas. |
| [`docs/metodología.md`](docs/metodología.md) | Método bibliométrico (autoridad de dominio). |
| [`docs/Notas/03-referencia/`](docs/Notas/03-referencia/) | Material de v0 (as-built, resultados, APIs) — referencia, no objetivo. |
| [`docs/Notas/`](docs/Notas/) | Notas no productivas: postmortem v0, exploración, material de referencia. |
