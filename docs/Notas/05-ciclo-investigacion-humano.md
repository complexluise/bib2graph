# 05 — El ciclo de investigación humano (exploración bibliográfica)

> Modelo del **ciclo humano de exploración bibliográfica** (el "ejercicio bibliotecario" +
> exploración), fundamentado en tres tradiciones teóricas, con los **puntos de inserción de
> IA** marcados. Es la base metodológica que va al paper y el ancla para decidir el wedge del
> rediseño. Aplica la inversión "IA in the loop, NOT human in the loop" de
> [`04-direccion-ia-in-the-loop.md`](04-direccion-ia-in-the-loop.md). Fecha: 2026-06-14.

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

## 4. Dónde entra la IA (los puntos puntuales) y dónde mapea bib2graph

La disciplina "IA in the loop": **el humano hace todo el ciclo; la IA entra en 2 cuellos de
botella**, no en todo.

- **Inserción 1 — forrajeo/chaining (pasos 2-3).** El snowballing manual es mecánico y agota.
  Aquí la **bibliometría ES el "information scent"**: las redes de citación/coupling le dan a
  la IA mejor olfato que los embeddings planos. Mapea a los **proyectores** de bib2graph.
- **Inserción 2 — sensemaking/tensiones (paso 6).** Donde el humano necesita ver *quién
  discute con quién*. Es la **máquina de tensiones** ([`04-...`](04-direccion-ia-in-the-loop.md)).
  Máximo valor, menos resuelto.

**Irreductiblemente humanos:** pasos **0, 4, 7** (formular la idea, dejar que mute, decidir qué
curar). Esto valida la inversión: no se automatiza el juicio, se asiste forrajeo y sensemaking.

## 5. El argumento del paper

Los modelos clásicos (Kuhlthau / Ellis / Bates / Pirolli) describían un ciclo de exploración
bibliográfica **sin IA**. La contribución es **re-instrumentar ese ciclo** insertando IA en
los dos puntos donde la **estructura bibliométrica funciona como information scent** (forrajeo
y sensemaking de tensiones), **sin desplazar el juicio humano** (pasos 0/4/7). La metodología
documenta el proceso con el rigor reproducible de vom Brocke / Wohlin / PRISMA — pero
asistido, no manual.

## 6. Próximos pasos (abiertos)

- Decidir el **wedge**: ¿la primera versión ataca la Inserción 1 (forrajeo asistido) o la
  Inserción 2 (tensiones)? La 2 es más valiosa y diferenciada; la 1 es prerequisito.
- Granularidad del "ejercicio bibliotecario" en pasos 1-3 (criterios de inclusión, dedup,
  normalización) — conecta con `Preprocessor`/`Source` del diseño actual.
- Reconciliar con la tensión "biblioteca viva vs snapshot inmutable" (paso 7) de
  [`04-...`](04-direccion-ia-in-the-loop.md) §6.

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
