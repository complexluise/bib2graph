# 08 — Revisión de referentes: frontend/UX de exploración bibliográfica

> ⚠️ **NOTA EXPLORATORIA — material de trabajo, no decisión.** Mapea herramientas comparables para
> destilar **qué tomar** y **qué hacer distinto** en la UX de bib2graph. Fecha: 2026-06-16.
> Hermana de [`07-frontend-tool-for-thought.md`](07-frontend-tool-for-thought.md).
>
> 📌 Las descripciones son de las **características durables** de cada herramienta (lo estable). Los
> detalles volátiles (precios, features puntuales del momento) **conviene corroborarlos** antes de
> usar esto para decidir — ofrezco una revisión con investigación web/citada si se quiere rigor.

## Para qué sirve esta revisión

bib2graph compite (y se diferencia) en un espacio ya poblado. El PRD §2 ya argumenta el hueco:
*consciente (no caja negra) · biblioteca viva (no mapa one-shot) · forrajeo asistido · abierto y
reproducible*. Acá lo aterrizamos a **referentes concretos de UX**, para que el diseño tome lo
bueno y no reinvente lo establecido — y para ver dónde **ir más allá** (la no-linealidad / *tool
for thought*).

## A. Mapas de citación / descubrimiento (los competidores directos)

| Herramienta | Qué hace (durable) | Fortaleza UX | Límite (vs la tesis de bib2graph) |
|---|---|---|---|
| **Connected Papers** | Grafo de "papers similares" desde **una semilla** (similitud por co-citación/acoplamiento), layout fuerza. | Grafo lindo, inmediato, lectura visual de vecindario. | **One-shot** desde una semilla; no hay biblioteca que crezca ni curación persistente; no expone la query; no reproducible. |
| **ResearchRabbit** | "Spotify for papers": **colecciones** + exploración por citas/co-autoría/similares; alertas. | Colecciones como objeto de primera clase; exploración iterativa; descubrir por autor/red. | Caja relativamente cerrada (no expone la ecuación/scent de forma reportable); no es local/propiedad; redes limitadas a las suyas. |
| **Litmaps** | **Seed maps** + **monitoreo** de literatura nueva sobre tu mapa; eje temporal. | Map + alertas (el "paso 8" del ciclo); incorporar papers al mapa iterando. | Hosteado; no biblioteca viva exportable/reproducible al estilo PRISMA; no múltiples redes bibliométricas. |
| **Inciteful** | Construye **redes de citación** desde semillas (paper graph / literature connector). | Rápido, orientado a red; sin fricción de cuenta. | Exploratorio one-shot; sin curación/biblioteca persistente; sin reporte reproducible. |
| **Open Knowledge Maps** | **Mapas de conocimiento** por clustering de temas desde una búsqueda. | Vista de "campos" temáticos; bueno para orientarse al inicio. | Es panorama temático, no biblioteca curada ni redes de citación profundas. |

**Qué tomar:** el **grafo como superficie de exploración** (Connected Papers/Inciteful), las
**colecciones iterativas** (ResearchRabbit), el **monitoreo de lo nuevo** (Litmaps, = paso 8 del
ciclo), la **orientación temática inicial** (OKM).
**Qué hacer distinto:** **exponer la ecuación y el *scent*** (consciente, reportable PRISMA);
**biblioteca viva local y propia** que crece y se cura entre rondas (no one-shot, no hosteado);
**la no-linealidad/rondas como objeto navegable** (ninguno modela explícitamente "la idea mutó").

## B. Análisis y viz de redes bibliométricas (las herramientas "expertas")

| Herramienta | Qué hace | Qué tomar | Límite |
|---|---|---|---|
| **VOSviewer** | Mapas de co-citación / co-word / co-autoría desde exports; clustering, densidad. | El **vocabulario de redes** que el usuario académico ya conoce; layouts de densidad. | App de escritorio experta; parte de exports a limpiar a mano; estática; no living library. |
| **Gephi** | Exploración/viz de redes general, métricas, layouts. | Interacción de grafo a escala, filtros, métricas in-situ. | Curva de aprendizaje alta; general-purpose; no bibliométrico ni iterativo. |
| **CiteSpace** | Co-citación + detección de *bursts*/frentes de investigación, evolución temporal. | La **dimensión temporal/evolución** de un campo. | Experto, denso, Java; lejos de "no técnico". |
| **bibliometrix / biblioshiny** | Suite R de bibliometría con GUI Shiny. | Cobertura analítica amplia; es el "estado del arte" académico. | Shiny = data-app (justo lo que queremos superar en UX); parte de datos cargados. |

**Qué tomar:** redes **serias** (no decorativas), métricas y comunidades in-situ, la **dimensión
temporal**, y el **léxico académico** familiar.
**Qué hacer distinto:** que la viz sea **exploratoria e iterativa dentro del lazo** (no un reporte
final estático), accesible a **no expertos**, y **sin** el paso de "conseguir y limpiar el export"
(bib2graph siembra desde la ecuación).

## C. *Tool for thought* / canvas / sistemas (de dónde robar la no-linealidad)

| Herramienta | Idea a robar | Cómo aplica a bib2graph |
|---|---|---|
| **Obsidian Canvas / tldraw** | Lienzo **espacial libre**: agrupar, conectar, anotar; pensar moviendo cosas. | El corpus/redes como cosas que el investigador **organiza espacialmente** y anota; sensemaking. |
| **Kumu** | Mapeo de **sistemas complejos**: actores, loops, influencia; vistas/filtros. | Leer el campo como sistema (comunidades, asimetrías, feedback); narrar estructura. |
| **Tinderbox** | Notas + atributos + vistas múltiples del mismo material; "incremental formalization". | Mismo corpus, **múltiples vistas** (red, tabla, mapa, timeline) según la pregunta. |
| **Roam/Logseq** | Pensamiento en red, no jerárquico; *backlinks*. | La no-linealidad y la trazabilidad (procedencia) como navegación. |
| **git / control de versiones** | **Historia ramificada** navegable. | Las **rondas/`reseed`** como timeline ramificado de la investigación. |

**Qué tomar:** la **no-linealidad como navegación** (no un wizard), **múltiples vistas del mismo
corpus**, **lienzo espacial** para sensemaking, e **historia ramificada** del pensamiento.
**Riesgo a evitar:** la libertad total del canvas puede volverse caos sin estructura — bib2graph
tiene una ventaja: la **estructura bibliométrica** (redes, scent, el FSM del ciclo) da el andamiaje.

## D. Asistentes con IA (referente de qué NO hacer)

**Elicit, Consensus, scite, etc.**: responden/resumen con LLM. El PRD §2 ya los critica como
**cajas negras** que ocultan la query. bib2graph es deliberadamente lo opuesto (ADR 0022, *sin IA
generativa*): **consciente, determinista, el juicio es humano**. → Referente de **contraste**: la UX
debe hacer *visible y reportable* lo que estos esconden. No imitar su "magia".

## Tabla de diferenciación (las dimensiones que importan)

Leyenda: ✅ lo hace · ◑ parcial · ❌ no.

| Dimensión | Connected P. | ResearchRabbit | Litmaps | VOSviewer/Gephi | **bib2graph (objetivo)** |
|---|---|---|---|---|---|
| Biblioteca viva que **crece y se cura** | ❌ | ◑ | ◑ | ❌ | ✅ |
| **No-linealidad / rondas** explícitas | ❌ | ◑ | ◑ | ❌ | ✅ (objetivo) |
| **Ecuación + scent** transparentes (PRISMA) | ❌ | ❌ | ◑ | ◑ | ✅ |
| **Reproducible/exportable** (snapshot) | ❌ | ❌ | ◑ | ◑ | ✅ |
| **Local / propiedad del usuario** | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Múltiples redes** bibliométricas | ◑ | ◑ | ◑ | ✅ | ✅ |
| **Monitoreo** de lo nuevo (paso 8) | ❌ | ◑ | ✅ | ❌ | ◑ (`monitor`) |
| **Accesible a no-técnicos** | ✅ | ✅ | ✅ | ❌ | ⟵ *lo que la GUI busca cerrar* |

## Síntesis: el hueco y cómo la UX lo materializa

El hueco que nadie llena junto: **biblioteca viva + propia/local + consciente/reportable +
múltiples redes + no-linealidad de primera clase + accesible**. Los mapas de citación son
accesibles pero one-shot y cerrados; las herramientas expertas son potentes pero offline y para
expertos; los *tools for thought* tienen la no-linealidad pero no la bibliometría.

**bib2graph puede ser "el workbench que piensa con vos sobre la estructura de un campo, que es
tuyo, transparente y reproducible".** La UX debería materializar eso con: (1) **grafo como
lienzo** explorable; (2) **el lazo/rondas navegable** (historia ramificada del pensamiento);
(3) **forrajeo con scent visible** (consciente, no caja negra); (4) **múltiples vistas** del mismo
corpus; (5) **export/snapshot** a un clic (reportable). Todo **local**.

## Qué alimenta el modelo de interacción (próximo paso)

De esta revisión, candidatos a "verbo central" y vistas para el modelo de interacción (Nota 07,
próximo paso): *navegar el grafo y tirar del hilo* (Connected Papers/Inciteful) · *curar
colecciones iterando* (ResearchRabbit) · *comparar rondas en una timeline ramificada* (git/Roam) ·
*leer el campo como sistema* (Kumu/CiteSpace) · *organizar/anotar en un lienzo* (Obsidian/tldraw).

## Para profundizar (pendiente, si se quiere rigor)

Esta revisión es desde conocimiento general de las herramientas. Para una versión **citada y
verificada** (features actuales, capturas, qué cambió) conviene una pasada de investigación web
(p. ej. el harness `deep-research`). Avisar si se quiere ese upgrade antes de usar esto para
decidir.
