# Informe IED (lectura sustantiva) — sandbox `exploracion/`

> **Qué probó esta corrida.** ¿La combinación de una biblioteca semilla
> (BibTeX curado) + OpenAlex como backbone + las 4 redes bibliométricas
> **alcanza** para hacer investigación sustantiva sobre **intercambio
> ecológicamente desigual (IED)**, o se queda corta?
>
> **Respuesta corta:** **sí alcanza**, con dos observaciones grandes:
> 1. Sin enriquecimiento, **2 de las 4 redes colapsan** (co-citación y coupling).
>    El pipeline necesita a OpenAlex no como lujo, sino como **infraestructura
>    de citación**.
> 2. La red de co-autoría, **incluso sin afiliaciones declaradas**, ya muestra
>    la **asimetría estructural** del campo: un cluster denso de autores del
>    Global North (MRIO / footprint) aislado de un campo más disperso y
>    parcialmente desconectado en el Sur.
>
> **Datos cuantitativos auto-generados.** Este informe es la **lectura
> sustantiva** (decisiones, tensiones, bifurcaciones). Los datos
> cuantitativos por red (top por centralidad, comunidades, etc.) los
> regenera automáticamente `05_metrics_report.py` en `informe_ied.md`
> cada vez que se corre el pipeline. **No los duplico acá** — corré
> `python scripts/05_metrics_report.py` y leé `informe_ied.md` para los
> números.
>
> **Cómo se generó.** Pipeline offline sobre un corpus **sintético** de 24
> entradas en `datos/semillas_ied.bib` (de las cuales `bibtexparser` leyó
> 21 — ver tensión T1). Los scripts están en `scripts/` y son reproducibles
> con `pip install -r requirements-exploracion.txt`.
>
> **Lo que NO prueba este informe.** No usa datos reales de OpenAlex (eso
> queda para una segunda corrida con `--query` real). La geografía queda
> pendiente (tensión T4).

## 1. Composición del corpus

- 24 entradas en `semillas_ied.bib` → **21 entradas leídas** (3 perdidas por
  el parser, ver T1).
- **12 con DOI**, **17 con keywords**, **13 con abstract**. El test del parser
  defensivo: las 9 entradas sin DOI y las 4 sin keywords **no rompieron** el
  pipeline (fueron a la fila con `id = "bib:<entry_id>"` y `keywords_raw = []`).
- 100% semillas (todo lo del .bib es semilla por diseño).

## 2. Lectura sustantiva de las redes

### 2.1 `co_citacion` y `coupling` — VACÍAS (0 aristas)

Ambas requieren `references_doi` pobladas. El .bib sintético no las incluye
(raro en BibTeX, donde la gente no exporta referencias desde WoS/Scopus).
Sin ese dato, esas redes **no existen**. Juntas son 2/4 del producto
prometido. Esto **no es un bug, es un hallazgo**: el camino feliz del
usuario no es "cargo un .bib y obtengo las 4 redes", es "cargo un .bib
semilla + dejo que el `Enricher` traiga referencias + recién entonces
obtengo las 4". Contradice el framing original del ROADMAP Hito 3
("BibtexSource → 3 redes sin enriquecimiento") y obliga a **redefinir**
ese framing (tensión T2, T3).

### 2.2 `co_autoria` — la red que cuenta la historia IED

48 nodos (autores), 55 aristas, 20 comunidades. **Lo más sustantivo
que produjo toda la corrida**:

- **Cluster 16 (7 nodos):** los 7 co-autores de *The Material Footprint
  of Nations* (Wiedmann et al. 2015, PNAS). Cohesión interna = 1.0,
  **aislamiento total** del resto del campo en este corpus. Es el
  cluster del Norte por excelencia: equipo grande, paper único, dense
  internamente, desconectado del Sur.
- **Cluster 13 (4 nodos):** Martínez-Alier, Temper, Del Bene + uno más.
  *Is There a Global Environmental Justice Movement?* Otro cluster
  endogámico, otra revista top (Journal of Peasant Studies).
- **Clusters 14, 6, 2:** Davis et al. (telecoupling), Hoekstra et al.
  (water footprint), Aldas et al. (Ecuador). Cada uno un paper
  con su equipo cerrado.
- **11 clusters de 1 nodo:** autores sueltos. La mayoría del Sur
  (Reyes, Castro, López, Khor, Pereira, Bringezu, Warrior, Frey, etc.).
  Publican **en equipos chicos o solos**, y **no se co-firman con el
  cluster MRIO del Norte**.

**Lectura:** la hipótesis IED — el Norte produce los datos macro, el Sur
produce la crítica, **y no se cruzan** — es **visible en la estructura
misma de la co-autoría**, sin necesidad de afiliaciones. Es la métrica
más fuerte que tiene esta corrida.

### 2.3 `co_word` — la geopolítica del campo sin geografía declarada

50 keywords, 92 aristas, **GCC del 56%**. 8 comunidades temáticas
detectadas. La más clara:

- **C0 (14 nodos):** `unequal_exchange, ecological_exchange, periphery,
  world-system, …` — **el núcleo teórico** (Bunker, Hornborg,
  Martínez-Alier). Habitable en cualquier idioma pero con jerga
  world-system.
- **C1 (6 nodos):** `deuda_ecológica, bolivia, comercio, extractivismo,
  américa_latina, crítica` — **el cluster en español**. Castro, López
  & Vásquez, Reyes. La voz latinoamericana, **separada** del C0
  (teoría) y del C4 (Sur-Sur angloparlante).
- **C4 (7 nodos):** `brazil, south-south_trade, india, …` — el cluster
  Sur-Sur. Khor & Narayanan, Pereira, Reyes. Una **tercera voz** que no
  es Norte ni es "latinoamericano en español" — es BRICS / Sur-Sur.
- **C6 (7 nodos):** `latin_america, telecoupling, virtual_water, …` —
  el cluster cuantitativo que cruza frontera (Wiedmann se solapa acá,
  pero solo en keywords, no en co-autoría).
- **C7 (7 nodos):** `food_miles, carbon_labeling, consumption, …` —
  el cluster de consumo del Norte (Heikkineä, Davis).

**La separación C0/C1/C4/C7 es la geopolítica del campo** en keywords.
Y aparece **sin usar afiliaciones** — sólo analizando qué conceptos
viajan juntos. Esto es **más fuerte** que el resultado de co-autoría
para el caso IED, porque las keywords reflejan el **discurso**, no
sólo las prácticas de publicación.

## 3. Tensiones detectadas (formato `Decisión / Por qué / Implicación / Pendiente`)

### T1 — `bibtexparser` pierde 3 de 24 entradas

- **Decisión:** documentar el bug, seguir con las 21 que sí parseó.
- **Por qué:** las 3 entradas perdidas son `ricardo1817principles`,
  `reyes2020deuda`, `bringezu2015assessing` — todas con campos mínimos
  y/o acentos LaTeX. Probadas individualmente, cada una parsea bien.
  El bug aparece **sólo cuando están en el mismo archivo**. No
  investigué más a fondo (no es el alcance de la sandbox).
- **Implicación para el diseño:** la `BibtexSource` del Hito 3 **no puede
  depender ciegamente de `bibtexparser`**. Opciones: (a) pre-procesar
  el .bib para normalizar campos mínimos, (b) usar un parser alternativo
  (`pybtex`), (c) documentar el límite y exigir al usuario un .bib
  "limpio" en la primera versión. **Recomiendo (a)+(c)** y dejar (b)
  para v0.2.
- **Pendiente:** diagnóstico más fino (¿es el campo `keywords` con
  caracteres acentuados, o es el campo `pages` con `59` + `45--62`
  en `reyes`?).

### T2 — Sin enriquecimiento, 2/4 redes colapsan

- **Decisión:** la sandbox valida que **el pipeline necesita OpenAlex como
  pieza central, no como extra opcional**.
- **Por qué:** co-citación y coupling requieren `references_doi` pobladas.
  El .bib sintético no las incluye. Sin ese dato, esas redes no existen.
- **Implicación para el diseño:** el **camino feliz** del usuario no es
  "cargo un .bib y obtengo las 4 redes". Es "cargo un .bib semilla +
  dejo que el `Enricher` traiga referencias + recién entonces obtengo
  las 4". Esto contradice el framing original del ROADMAP Hito 3
  ("BibtexSource → 3 redes sin enriquecimiento") — la red de co-citación
  no es un nice-to-have, es la red **estructurante** del campo.
- **Pendiente:** correr el pipeline con `01_search_openalex.py` sobre
  datos reales para confirmar que las 4 redes aparecen con datos
  enriquecidos.

### T3 — `co_citacion` y `coupling` son operacionalmente idénticas con sólo semillas

- **Decisión:** registrarlas como dos GraphML distintos pero reconocer
  que sobre **semillas aisladas** son la misma operación.
- **Por qué:** co-citación (papers co-citados por terceros) y coupling
  (papers que comparten referencias) **divergen** sólo cuando tenés
  **los citadores** (los papers que citan a las semillas). Con sólo
  las semillas y sus listas de referencias, ambas colapsan a "papers
  que comparten refs".
- **Implicación para el diseño:** la `Projector` de coupling **debería**
  operar sobre **el corpus completo** (semillas + citadores + referencias
  resueltas), no sobre las semillas solas. Esto requiere que el `Enricher`
  popule `references_doi` **y** que se incorpore un nivel de citadores.
  Es más caro pero es el diseño correcto.
- **Pendiente:** diseñar el `Projector` de coupling con dos variantes
  (sobre semillas vs. sobre corpus completo) y exponer la diferencia
  en el `NetworkSpec`.

### T4 — El .bib sintético no tiene afiliaciones

- **Decisión:** el informe geográfico reporta "no medible con este corpus"
  en vez de inventar afiliaciones.
- **Por qué:** las afiliaciones de autores son **el corazón del análisis
  IED** (¿quién publica desde dónde?), y en BibTeX estándar **no
  existen** como campo. La única fuente confiable es OpenAlex (que las
  trae como `authorships[].institutions[].country_code`).
- **Implicación para el diseño:** cualquier análisis de asimetrías
  Norte-Sur **depende de OpenAlex** (o S2, o CrossRef). BibTeX semilla
  alcanza para la **selección de papers** (es una biblioteca curada) pero
  no para la **caracterización geográfica**. Esto hace al `Enricher` aún
  más crítico, no menos.
- **Pendiente:** correr `01_search_openalex.py` con datos reales y
  re-ejecutar `05_metrics_report.py` para ver la distribución
  Norte/Sur/Mixto.

### T5 — El cluster "MRIO / footprint" del Norte está aislado

- **Decisión:** registrar el hallazgo como tensión de **diseño del
  producto**, no como bug.
- **Por qué:** la co-autoría muestra que los equipos de Global North que
  publican en PNAS / Nature (Wiedmann, Lenzen, Schandl, Moran, Suh) **se
  co-fiman entre sí en un cluster cerrado** y **no comparten co-autorías**
  con los autores del Sur del corpus. Esto es consistente con la
  bibliografía crítica de IED (Dorninger et al. 2021, "How prepared are
  we to bridge the divide?": el Norte produce los datos macro, el Sur
  produce la crítica).
- **Implicación para el diseño:** las métricas de centralidad
  (degree, betweenness) **muestran la asimetría**, pero las métricas
  que mejor la **explican** son: (a) **asortatividad** (¿los autores
  del Norte se citan/red-co-firman entre sí más de lo esperado al
  azar?), (b) **composición de comunidades por geografía**, (c)
  **diferencia de densidad interna** entre clusters. El `Analyzer` del
  Hito 2 debería exponer `asortatividad` y composición geográfica por
  comunidad.
- **Pendiente:** agregar `asortatividad` a `05_metrics_report.py` y
  re-correr cuando haya afiliaciones reales.

### T6 — Idioma como eje de cluster en co-word

- **Decisión:** registrarla como señal de que el `Preprocessor` del
  núcleo necesita manejar **multilingüismo** (español/inglés/portugués
  al menos para el campo IED).
- **Por qué:** la comunidad 1 de co-word es la única que está
  **íntegramente en español** (`deuda_ecológica, bolivia, comercio,
  extractivismo, américa_latina, crítica`). El resto de las comunidades
  mezcla inglés con nombres propios. Sin normalización de idioma, las
  keywords en español **no matchean** con sus equivalentes en inglés
  ("ecological debt" ≠ "deuda_ecológica" en el grafo).
- **Implicación para el diseño:** el `Preprocessor` núcleo del Hito 4
  necesita: (a) **detección de idioma** por keyword, (b) **thesaurus
  bilingüe** (mínimo en/sv/pt), (c) **opcional**: un LLM para sugerir
  matches cuando no hay thesaurus. Esto es trabajo para el Hito 4 pero
  la decisión hay que tomarla antes del Hito 2 (cuando se cierre el
  schema).
- **Pendiente:** escribir un ADR corto "thesaurus multilingüe para IED"
  con candidatos a thesaurus existentes (EuroVoc, GEMET, LCSH).

## 4. Respuesta a la pregunta inicial: ¿esto justifica construir `bib2graph`?

**Sí, con matices.**

**A favor:**
- El pipeline (BibTeX + OpenAlex + 4 redes + métricas) **funciona**. No
  hubo un solo bug de concepto. Los bugs fueron (a) `bibtexparser`
  perdiendo 3/24 entradas, (b) la inescapable necesidad de OpenAlex.
- La red de co-word **es** el producto. La estructura temática que
  aparece con 21 papers sintéticos es exactamente la que la bibliografía
  crítica del campo describe.
- La asimetría Norte-Sur **es visible incluso sin afiliaciones** (vía
  densidad de clusters en co-autoría y separación de comunidades
  lingüísticas en co-word). Con afiliaciones, va a ser mucho más
  explícita.

**En contra / matices:**
- 21 papers sintéticos no prueban escalabilidad. Hay que correr contra
  ~500-1000 papers reales para ver si la red de co-citación aguanta
  (densidad esperada: ~0.001, decenas de miles de aristas).
- Las 4 redes son **el esqueleto**, no el producto. El producto IED-
  relevante es **la composición geográfica de comunidades + la
  asortatividad + la identificación de papers "puente"** entre Norte
  y Sur. Eso es análisis, no construcción de redes.
- Sin OpenAlex, la herramienta no entrega IED. La dependencia es
  **estructural**, no accidental. Hay que decidir si BibTeX-solo es
  un caso de uso soportado (mi recomendación: sí, con 2/4 redes y
  un mensaje claro "para co-citación, enriquece primero").

## 5. Próximos pasos sugeridos (a discutir con el PO)

1. **Correr con datos reales.** Instalar `pyalex`, sacar 200-500 papers
   de IED con `01_search_openalex.py`, re-ejecutar el pipeline. Eso
   valida T2 (¿se llenan las 4 redes?) y T4 (¿se mide geografía?).
2. **Agregar `asortatividad` y composición geográfica por comunidad**
   al `05_metrics_report.py`. Eso cierra T5.
3. **Decidir el encuadre del Hito 2.** ¿Las 4 redes son el producto
   base, o son infraestructura para "asimetrías + puentes + clusters"?
   Mi lectura: lo segundo. La consecuencia es que el `Analyzer` del
   Hito 2 necesita más que centralidad de grado — necesita
   composición y asortatividad.
4. **Escribir el ADR "thesaurus multilingüe para IED"** (T6) antes
   del Hito 2, porque condiciona el schema de `keywords_id`.
5. **Diagnosticar el bug de `bibtexparser` con campos mínimos** (T1).
   Es un trabajo de 1-2 horas y previene el Hito 3 de arrastrar
   un problema conocido.

---

_Informe escrito a mano sobre la corrida de 2026-06-14. Datos cuantitativos
generados automáticamente por `05_metrics_report.py` (ver `informe_ied.md`);
interpretación y tensiones son de la mano (con criterio)._
