# 05 — El ciclo de investigación humano (exploración bibliográfica)

> Modelo del **ciclo humano de exploración bibliográfica** (el "ejercicio bibliotecario" +
> exploración), fundamentado en tres tradiciones teóricas, con el **punto donde la herramienta
> asiste** marcado. Es la base metodológica que va al paper y el ancla del diseño. Fecha original:
> 2026-06-14.
>
> **Actualización 2026-06-15 (decisión del PO, tras la [Nota 06](06-critica-as-built-v0.2.md)):** el
> producto **no usa IA generativa** (ADR [0022](../decisiones/0022-producto-sin-ia-generativa.md)).
> Donde la versión original hablaba de **dos inserciones de IA** (forrajeo + máquina de tensiones),
> ahora hay **una inserción algorítmica** —el forrajeo asistido por **estructura bibliométrica como
> *information scent*** (acoplamiento/co-citación/centralidad, **determinista**, sin LLM)— y el
> **sensemaking de tensiones vuelve a ser humano** (asistido por las redes, no por IA): la "máquina
> de tensiones" **se retiró del producto**. Las §4 y §5 abajo ya están reescritas a esto; la §6
> (próximos pasos) quedó saldada y se anota como histórica.

## 1. Por qué tres tradiciones (y no una)

La exploración bibliográfica se ha modelado desde tres campos que **rara vez se cruzan**.
Citar a través de los tres es lo que da rigor a la metodología del paper:

- **A. Information Seeking Behavior (LIS) — *descriptivo*:** cómo la gente busca de verdad.
- **B. Information Foraging + Sensemaking (HCI/cognitivo) — *cómo razonamos* al buscar.**
- **C. Revisión sistemática (metodología) — *prescriptivo*:** cómo hacerlo riguroso y
  reproducible.

## 2. Referentes

### A. Information Seeking Behavior (biblioteconomía)
| Referente | Aporte clave | Cita |
|---|---|---|
| **Kuhlthau — Information Search Process (ISP)** | 6 etapas (iniciación, selección, exploración, formulación, colección, presentación) + **dimensión afectiva** (incertidumbre→claridad). | Kuhlthau 1991 |
| **Ellis — modelo conductual** | 6 conductas: *starting, chaining, browsing, differentiating, monitoring, extracting*. "**Chaining**" = citation chaining. | Ellis 1989 |
| **Bates — Berrypicking** | La búsqueda **no es lineal**: necesidad y query *mutan* al leer; "berries" recogidas en el camino. | Bates 1989 |

### B. Information Foraging + Sensemaking (HCI/cognitivo, PARC)
| Referente | Aporte clave | Cita |
|---|---|---|
| **Pirolli & Card — Information Foraging Theory** | Maximizar ganancia/costo; **"information scent"** = señales (citas, links) que guían qué "parche" explorar. | Pirolli & Card 1999 |
| **Sensemaking loop** | Dos bucles: **foraging loop** (hallar→organizar en evidencia) + **sensemaking loop** (esquematizar→hipótesis→relato). | Pirolli & Card 2005 |

### C. Revisión sistemática (metodología)
| Referente | Aporte clave | Cita |
|---|---|---|
| **Wohlin — Snowballing** | *Backward* (refs) + *forward* (citantes), iterar hasta saturación. Reproducible. | Wohlin 2014 |
| **Pearl growing / citation mining** | Misma familia; ~51% de las refs de una revisión se hallan así. | — |
| **SALSA** | Search → AppraisaL → Synthesis → Analysis. | Grant & Booth 2009 |
| **Webster & Watson — concept matrix** | Revisión **concept-centric**: matriz concepto×paper. | Webster & Watson 2002 |
| **vom Brocke — "Reconstructing the Giant"** | **Rigor en documentar el proceso de búsqueda** (= reproducibilidad). | vom Brocke et al. 2009 |
| **PRISMA** | Reporte/flujo estándar de selección. | Page et al. 2021 |

**Bonus 2026:** *"Information Farming: From Berry Picking to Berry Growing"* (arXiv 2601.12544)
— extiende a Bates de **recolectar** a **cultivar** la colección. Respaldo teórico directo de
la "biblioteca viva y curada".

## 3. El ciclo sintetizado (iterativo, NO lineal)

```
(0) IDEA / pregunta difusa        ── Kuhlthau: iniciación; alta incertidumbre afectiva
        │
(1) SEMILLAS                       ── Ellis: starting · pearl growing: el "grano"
        │
(2) CHAINING / FORRAJEO  ◄──────┐  ── Ellis: chaining · Wohlin: back/forward snowballing
        │                       │     Pirolli: seguir el "information scent" (las citas)
(3) BROWSING / DIFERENCIAR       │  ── Ellis: browsing+differentiating · foraging loop
        │                       │
(4) LA QUERY Y LA IDEA MUTAN ───┘  ── Bates: berrypicking (volvés a 1/2 con otra pregunta)
        │
(5) ORGANIZAR EN EVIDENCIA         ── Webster & Watson: concept matrix · foraging→evidencia
        │
(6) SENSEMAKING / TENSIONES        ── Pirolli: sensemaking loop (esquema→hipótesis→relato)
        │
(7) CURAR LA BIBLIOTECA  ──────────── Berry *growing*: la colección se cultiva, no se descarta
        │
(8) MONITOREAR                     ── Ellis: monitoring (alertas de lo nuevo)
```

La no-linealidad (el lazo 2→3→4→1) es la propiedad central: cualquier diseño que asuma un
pipeline lineal "query → resultados → fin" contradice a Bates, Ellis y Kuhlthau a la vez.

## 4. Dónde asiste la herramienta (el punto puntual) y dónde mapea bib2graph

> **Reescrita 2026-06-15** — ver la nota de cabecera. El producto **no usa IA generativa** (ADR
> [0022](../decisiones/0022-producto-sin-ia-generativa.md)).

La disciplina: **el humano hace todo el ciclo; la herramienta lo asiste en UN cuello de botella**,
con un método **determinista y reproducible**, no con IA.

- **Inserción algorítmica única — forrajeo/chaining (pasos 2-3).** El snowballing manual es mecánico
  y agota. Aquí la **bibliometría ES el "information scent"**: el candidato se prioriza por cuánto se
  **acopla / co-cita / es central** respecto del corpus curado (los **proyectores** de bib2graph),
  no por un conteo plano ni por embeddings ni por un LLM. Es **estructura, no IA** — y por eso es
  reproducible. *(Trade-off honesto: rankear por estructura ya presente sesga hacia lo central/
  popular —efecto Mateo—; el scent **prioriza**, la exhaustividad la sostienen los filtros PRISMA.)*
- **Sensemaking / tensiones (paso 6) — HUMANO, asistido por las redes.** Ver *quién discute con
  quién* lo hace el investigador **leyendo las redes** (comunidades, centralidad, acoplamiento), no
  un modelo. La "máquina de tensiones" asistida por IA **se retiró del producto** (ADR
  [0008](../decisiones/0008-wedge-forrajeo.md) / [0022](../decisiones/0022-producto-sin-ia-generativa.md)):
  no hay clasificación automática de apoya/refuta.

**Irreductiblemente humanos:** pasos **0, 4, 7** (formular la idea, dejar que mute, decidir qué
curar) **y 6** (interpretar las tensiones). La herramienta **no automatiza el juicio**: asiste el
forrajeo con estructura y le da al humano el material para el sensemaking.

## 5. El argumento del paper

> **Reescrita 2026-06-15.**

Los modelos clásicos (Kuhlthau / Ellis / Bates / Pirolli) describían un ciclo de exploración
bibliográfica **manual**. La contribución es **re-instrumentar ese ciclo** con un método donde la
**estructura bibliométrica funciona como *information scent*** (forrajeo asistido), **determinista y
reproducible**, **sin desplazar el juicio humano** (pasos 0/4/6/7) **y sin IA generativa**. La
metodología documenta el proceso con el rigor reproducible de vom Brocke / Wohlin / PRISMA — pero
asistido por bibliometría, no manual ni por caja negra. El diferenciador frente a los asistentes con
IA (Elicit, Scite, Undermind, ResearchRabbit) no es "más IA": es una **biblioteca viva curada que el
investigador posee**, con la **estructura de citación de primera clase** y un flujo **abierto y
auditable**.

## 6. Próximos pasos (saldados — histórico)

> Esta sección era de exploración (2026-06-14) y ya quedó **resuelta**; se conserva como historia.

- ~~Decidir el **wedge** (Inserción 1 forrajeo vs Inserción 2 tensiones).~~ **Saldado:** el wedge es
  el **forrajeo asistido por estructura bibliométrica**; la máquina de tensiones se **retiró** del
  producto (ADR 0008/0022), no es un wedge alternativo.
- Granularidad del "ejercicio bibliotecario" en pasos 1-3 → realizada en `Preprocessor`/`Source`/
  filtros PRISMA (ADR [0020](../decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)).
- Tensión "biblioteca viva vs snapshot inmutable" (paso 7) → resuelta a favor de la **biblioteca
  viva en DuckDB** (ADR [0009](../decisiones/0009-biblioteca-viva-duckdb.md)/[0015](../decisiones/0015-corpus-tabular-backend.md)).

## 7. Referencias (URLs)

- Bates — [Information Behavior](https://pages.gseis.ucla.edu/faculty/bates/articles/information-behavior.html)
- Kuhlthau ISP — [ELIS chapter](https://wp.comminfo.rutgers.edu/ckuhlthau/wp-content/uploads/sites/185/2016/01/ELIS-3E.pdf)
- Pirolli & Card — [Information Foraging (tech report)](https://act-r.psy.cmu.edu/wordpress/wp-content/uploads/2012/12/280uir-1999-05-pirolli.pdf) ·
  [Information Foraging (NN/g)](https://www.nngroup.com/articles/information-foraging/)
- Wohlin — [Snowballing guidelines](https://dl.acm.org/doi/10.1145/2601248.2601268)
- Pearl growing — [Wikipedia](https://en.wikipedia.org/wiki/Pearl_growing)
- vom Brocke — [Reconstructing the Giant](https://www.researchgate.net/publication/259440652_Reconstructing_the_Giant_On_the_Importance_of_Rigour_in_Documenting_the_Literature_Search_Process)
- Webster & Watson — [concept matrix](https://www.researchgate.net/figure/Basic-concept-matrix-for-literature-reviewing_tbl2_255856903)
- Berry Growing — [arXiv 2601.12544](https://arxiv.org/pdf/2601.12544)
