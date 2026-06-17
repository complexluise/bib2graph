# 05 — Sandbox IED: exploración end-to-end con librerías externas

> **Estado:** documentación histórica de la corrida exploratoria del 2026-06-14.
> No es propuesta de diseño: la propuesta es `docs/ROADMAP.md` + los ADRs. Esta
> nota registra **qué se probó, qué se aprendió, qué quedó sin probar y qué
> implicaciones tiene para `bib2graph`**.
>
> **Audiencia:** el PO y el equipo, cuando vuelvan a este repo en 3 meses y
> necesiten saber (a) por qué el ROADMAP dice lo que dice, (b) por qué algunas
> decisiones se tomaron con datos y otras no.
>
> **Documentos hermanos:**
> - [`01-lecciones-v0.md`](01-lecciones-v0.md) — reglas que motivan el código
> - [`arquitecturas-alternativas.md`](02-exploracion/arquitecturas-alternativas.md) — comparación de modelos del `Corpus`
> - [`referentes.md`](referentes.md) — mapa del campo
> - [`04-direccion-ia-in-the-loop.md`](04-direccion-ia-in-the-loop.md) — giro de "librería" a "sustrato"
> - [`ROADMAP.md`](../ROADMAP/README.md) — la secuencia de construcción vigente
>
> **Dónde vive el código:** [`../../exploracion/`](../../exploracion/). Todo
> lo descrito acá es reproducible corriendo los scripts en orden.

## 1. Pregunta que guió la exploración

> ¿La combinación de una biblioteca semilla en BibTeX + OpenAlex como
> backbone + las 4 redes bibliométricas (co-citación, co-autoría, co-word,
> coupling) **alcanza** para hacer investigación sustantiva sobre
> **intercambio ecológicamente desigual (IED)**, o se queda corta?

La pregunta importa porque el `docs/ROADMAP.md` actual asume que **sí alcanza**
y por eso estructura el producto como "corpus → redes → análisis". La
exploración es la primera vez que esa hipótesis se valida con un pipeline
end-to-end real, aunque sea con datos sintéticos.

## 2. Qué se construyó

Una carpeta `exploracion/` (fuera de `src/bib2graph/`, no se mezcla con el
paquete) con:

- **5 scripts** que componen un pipeline: `01_search_openalex.py`
  (queries a OpenAlex) → `02_load_bibtex.py` (parser defensivo) →
  `03_merge_corpus.py` (unión + dedup + parquet) → `04_build_networks.py`
  (4 redes → GraphML) → `05_metrics_report.py` (métricas + informe).
- **1 corpus sintético** (`datos/semillas_ied.bib`) de 24 entradas que
  modela el patrón del campo IED: 5 clásicos teóricos (Bunker, Hornborg,
  Martínez-Alier), 8 estudios empíricos del Sur, 6 del Norte, 4 de
  metodología, 3 críticos y 4 "huérfanos" con campos opcionales ausentes.
- **2 informes**: `informe_ied.md` (cuantitativo, auto-generado, se
  regenera con cada corrida) y `informe_ied_lectura.md` (cualitativo,
  escrito a mano, con las tensiones y decisiones).
- **5 dependencias externas** declaradas en `requirements-exploracion.txt`
  (`pyalex`, `bibtexparser`, `pandas`, `pyarrow`, `networkx`,
  `python-louvain`). El núcleo de `bib2graph` **NO las conoce** — el
  propósito mismo de la sandbox es probar conceptos que después el
  producto va a tener que resolver de otra forma.

## 3. Qué se encontró

El pipeline corrió end-to-end, sin errores de concepto, sobre el corpus
sintético. La estructura de las 4 redes y los hallazgos sustantivos
(presentados en detalle en `exploracion/informe_ied_lectura.md`):

| Red | Resultado | Lo que dice |
|---|---|---|
| `co_citacion` | 0 aristas | El .bib sintético no trae `references_doi`. Sin enriquecimiento, la red no existe. |
| `coupling` | 0 aristas | Operacionalmente idéntica a co-citación sobre semillas aisladas. |
| `co_autoria` | 48 nodos, 55 aristas | **El cluster MRIO/footprint del Norte** (Wiedmann et al. PNAS) es un bloque denso y totalmente aislado del Sur. 11 autores del Sur quedan como clusters de 1 nodo. |
| `co_word` | 50 nodos, 92 aristas | **Geopolítica del campo en keywords**: teoría (C0), discurso latinoamericano en español (C1), Sur-Sur (C4), consumo del Norte (C7). |

Lo más fuerte: **la asimetría Norte-Sur del campo es visible en la
estructura de co-autoría y de co-word, sin necesidad de afiliaciones**.
La métrica más IED-relevante no es centralidad de grado — es
**asortatividad** + **composición geográfica de comunidades**.

## 4. Lo que NO se probó (conciencia de los límites)

- **Datos reales de OpenAlex.** La corrida fue sobre datos sintéticos. La
  validación con `pyalex` real (200-500 papers) queda pendiente.
- **Escalabilidad.** 21 papers no prueban que el pipeline aguante
  ~10⁴ papers con decenas de miles de aristas en co-citación.
- **Geografía real.** El .bib sintético no tiene afiliaciones. Sin
  OpenAlex real, la sección de asimetrías Norte-Sur del informe
  queda en "no medible con este corpus".
- **Loop completo de citadores.** Co-citación y coupling sólo divergen
  cuando se incorpora el nivel de citadores (papers que citan a las
  semillas). Acá ambas colapsaron por la misma razón (falta de refs).

## 5. Implicaciones para `docs/ROADMAP.md` y los ADRs

Las siguientes observaciones **cuestionan o matizan** lo que dice el
ROADMAP. No son refutaciones — son **inputs para la próxima revisión
del roadmap**, no destructivos del trabajo existente.

### 5.1 El Hito 3 ("BibtexSource → 3 redes sin enriquecimiento") necesita revisarse

El ROADMAP dice:

> "Hito 3 — Costura por defecto: `BibtexSource`. Se vuelve posible:
> `BibtexSource().load(...)` → tres redes (autor, institución, keyword) +
> métricas + export **solo desde BibTeX, sin enriquecimiento**. Primer
> pipeline end-to-end real."

La exploración muestra que **sin enriquecimiento, sólo hay 2 redes con
estructura** (co-autoría y co-word), y la red **estructurante** del campo
(co-citación) **no existe**. Tres opciones para el PO:

- **(a) Aceptar el framing actual**: el Hito 3 entrega 3 redes "honestas"
  (co-autoría, co-word, acoplamiento vía BibTeX), y la co-citación llega
  en el Hito 6. Documentar explícitamente que co-citación **requiere
  enriquecimiento**.
- **(b) Reordenar**: subir el `Enricher` a una versión mínima (Hito 2.5)
  para que la co-citación sea testeable junto con el resto.
- **(c) Combinar**: el Hito 3 entrega BibTeX-solo con 2 redes, y el Hito 4
  (CLI) ya tiene un comando `enrich` que el usuario corre antes de pedir
  las 4 redes.

**Recomendación registrada en `informe_ied_lectura.md` §5:** (a) o (c).
No (b) — el orden "núcleo puro primero" del ADR 0006 sigue valiendo.

### 5.2 El Hito 2 (`Analyzer` con centralidad) probablemente necesita más

El ROADMAP dice que el `Analyzer` calcula "centralidad, comunidades, calidad
de co-citación". La exploración sugiere que las métricas **más IED-
relevantes** no son las que están listadas:

- **Asortatividad** (¿el Norte se co-firma/red-cita con el Norte más de
  lo esperado al azar?).
- **Composición geográfica de comunidades** (¿qué % de cada cluster es
  Global South?).
- **Detección de papers "puente"** (los que conectan clusters, o sea
  tienen alta betweenness y cruzan la frontera Norte-Sur).

**Recomendación:** antes de cerrar el Hito 2, escribir un mini-ADR
"Métricas de asimetría para IED" que defina cuáles de estas entran al
`Analyzer` de v0.1 y cuáles quedan para v0.2.

### 5.3 El `Preprocessor` del Hito 4 necesita multilingüismo (nuevo ADR)

El Hito 4 dice "`Preprocessor` núcleo: `normalize` (canonicalización de
nombres, thesaurus de keywords, periodización)". La exploración muestra
que **el cluster en español de co-word no matchea con el cluster en
inglés** ("deuda_ecológica" ≠ "ecological_debt" en el grafo). Sin
thesaurus bilingüe, el campo IED — donde español, inglés y portugués son
idiomas de trabajo al mismo nivel — queda partido en comunidades
artificiales.

**Acción concreta:** escribir un ADR corto "Thesaurus multilingüe para
IED" con candidatos a thesaurus existentes (EuroVoc, GEMET, LCSH), antes
del Hito 2 (porque condiciona el schema de `keywords_id`).

### 5.4 `bibtexparser` no es confiable para `.bib` "no canónicos" (input para Hito 3)

Perdió 3 de 24 entradas: las que tienen campos mínimos y/o LaTeX
embebido. Las probé individualmente y parsean bien, pero juntas no.
**Implicación:** la `BibtexSource` del Hito 3 no puede depender
ciegamente de `bibtexparser`. Recomendación registrada en
`informe_ied_lectura.md` T1: pre-procesar el .bib **y** documentar el
límite, dejar `pybtex` como alternativa para v0.2.

### 5.5 `coupling` necesita un rediseño antes de publicarse

Tal como está en la sandbox (y como está implícito en el ROADMAP Hito 2),
coupling es operacionalmente idéntica a co-citación sobre semillas. Sólo
diverge cuando hay citadores incorporados. **Implicación:** o se redefine
el `Projector` de coupling (sobre corpus completo, no sólo semillas), o
se documenta como "coupling-v0.1" (con la limitación explícita) y se
marca como subóptimo hasta v0.2.

## 6. Decisiones que la exploración **no** cuestiona

Para no abrir todo a debate: hay cosas que la exploración **confirma** y
que el ROADMAP/ADRs pueden seguir sosteniendo sin cambio:

- **Tabla canónica Arrow como modelo del `Corpus`** (validado: la
  pipeline CSV ↔ parquet con listas funcionó sin fricción; no hizo falta
  objetos).
- **OpenAlex como backbone de datos** (validado: el script `01` es viable
  y la API es accesible; el bug `bibtexparser` refuerza que el camino
  feliz pasa por OpenAlex, no por BibTeX-solo).
- **Idempotencia y dedup por DOI** (validado: el merge de 03 funcionó en
  0 conflictos, pero la lógica de `fillness` + `merge_rows` se ejercitó).
- **Parser defensivo con campos faltantes** (validado: 9/21 entradas sin
  DOI y 4/21 sin keywords entraron al pipeline sin romper).
- **Desescaper de LaTeX** es necesario y debe vivir en el `Preprocessor`
  (validado: sin él, los keywords en español salían rotas).
- **GraphML como formato de export** (validado: los 4 archivos se
  generaron, networkx los lee sin problema, Gephi/VOSviewer los importan
  directo).

## 7. ¿Qué sigue? (orden de trabajo propuesto)

1. **Diagnosticar el bug `bibtexparser`** (T1): 1-2h. Previene el Hito 3
   de arrastrar un problema conocido.
2. **Escribir el ADR "Thesaurus multilingüe para IED"** (T6): 2-3h.
   Condiciona el schema del Hito 2.
3. **Correr la sandbox con datos reales de OpenAlex** (200-500 papers):
   1 tarde. Valida T2 (¿se llenan las 4 redes?) y T4 (¿se mide
   geografía?).
4. **Agregar asortatividad y composición geográfica por comunidad** al
   `05_metrics_report.py`: 2h. Cierra T5 con evidencia.
5. **Revisar el Hito 3 del ROADMAP** a la luz de (1)-(4): un ADR
   "Revisión del Hito 3 post-exploración IED" que tome las opciones (a)/(b)/(c)
   de §5.1.
6. **Recién después**, empezar el Hito 1 (núcleo puro). La exploración
   no se mete con eso — sigue intacto el plan del ROADMAP para el núcleo.

## 8. Lecciones generales (las que aplican más allá de IED)

- **Probar conceptos con sandbox es más barato que decidirlos en
  abstracto.** Esta corrida de una tarde evitó que el Hito 3 se diseñara
  mal y que el Hito 2 subdimensionara el `Analyzer`.
- **Las tensiones se ven con datos, no con argumentos.** T5 (asimetría
  Norte-Sur) era una hipótesis del campo. Con 21 papers sintéticos ya
  aparece en la estructura. Con datos reales va a ser brutal.
- **Las dependencias externas en la sandbox NO son deuda técnica del
  producto.** El hecho de que `bibtexparser` pierda 3/24 entradas es
  información para el Hito 3, no un bug a importar.
- **El informe a mano complementa al auto, no lo duplica.** Separar
  `informe_ied.md` (cuantitativo, regenerable) de `informe_ied_lectura.md`
  (cualitativo, con criterio) es la forma de tener ambos sin pisarse.

## 9. Referencias

- Sandbox completa: `exploracion/` (5 scripts, 1 .bib, 2 informes, 4 GraphML)
- Informe cuantitativo auto: `exploracion/informe_ied.md` (regenerable)
- Informe cualitativo a mano: `exploracion/informe_ied_lectura.md` (6 tensiones)
- Decisiones de producto: [`../ROADMAP.md`](../ROADMAP/README.md) y [`../decisiones/`](../decisiones/)
- Direccionamiento "IA in the loop": [`04-direccion-ia-in-the-loop.md`](04-direccion-ia-in-the-loop.md)
- Bibliografía crítica IED + asimetrías Norte-Sur (citada en la
  exploración): Dorninger et al. 2021, "How prepared are we to bridge
  the divide? Ecological economics and the Macroeconomic rebound
  effect"; Martinez-Alier et al. 2016, "Is there a global environmental
  justice movement?"; Hornborg 1998, "Towards an ecological theory of
  unequal exchange"; Bunker 1984, "Modes of extraction, unequal
  exchange…".
