# PRD — bib2graph

> Documento de Requisitos de Producto de `bib2graph`: una **librería de Python** + **CLI delgada
> agente-native** que convierte una **ecuación de búsqueda** en una **biblioteca viva y curada** de
> literatura y la proyecta a **redes bibliométricas**. El **producto NO usa IA generativa** (ADR
> [0022](decisiones/0022-producto-sin-ia-generativa.md)): la asistencia del forrajeo es estructura
> bibliométrica determinista (*information scent*); el desarrollo sí es asistido por IA. Diseño en
> [`ARCHITECTURE.md`](ARCHITECTURE.md); contratos en [`API.md`](API.md); método en
> [`Notas/metodología.md`](Notas/metodología.md).

## 1. Qué es

`bib2graph` es una **librería de Python instalable** y una **CLI delgada agente-native** construida
sobre ella, que convierte una **ecuación de búsqueda** —el artefacto estándar y reproducible de la
ciencia— en una **biblioteca viva y curada** de literatura, y la proyecta a **redes bibliométricas**
listas para analizar (co-citación, acoplamiento bibliográfico, co-autoría, co-ocurrencia de palabras
clave, instituciones).

El **motor de extracción de referencia** es **OpenAlex** ([ADR 0007](decisiones/0007-openalex-backbone.md)),
pero es **intercambiable**: la identidad **no** se ancla en OpenAlex sino en el **DOI** (la columna es
**`source_id`** —id del motor, agnóstica— y el `id` interno se deriva del DOI; ADR
[0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md)), con apertura a **otros motores**
(p. ej. Semantic Scholar). El camino **no es un pipeline lineal** sino un **ciclo iterativo** (Bates /
Ellis / Kuhlthau, ver §2): se siembra desde la ecuación, se hace chaining rankeado por estructura, se
diferencia y cura, y **la ecuación y la idea mutan** — se vuelve a sembrar con otra pregunta. El corpus
**vive y persiste** entre esas iteraciones en **DuckDB** (no es el export de una sola corrida): es el
**sustrato que hace posible el lazo** — se acepta/rechaza, crece y se cultiva en el tiempo. Ese
sustrato es el **`DuckDBBackend` del `Corpus`** (el backend por defecto, no un `Store` aparte; ADR
[0015](decisiones/0015-corpus-tabular-backend.md)), y el lazo es una **máquina de estados explícita**
(`CycleState`: `SEEDED → FORAGED → FILTERED → BUILT → MONITORED`, ADR
[0016](decisiones/0016-maquina-estados-lazo.md)). **Una investigación = un workspace** (carpeta
`workspace.json` + `library.duckdb` + `networks/`/`snapshots/`/`exports/`; ADR
[0029](decisiones/0029-workspace-por-investigacion.md)), arrancado con `b2g init` y resuelto por
ambiente; su estado se consulta con `b2g status`.

*El final siguen siendo las redes; lo nuevo es **cómo se llega a ellas** (forrajeo asistido) y
que **la colección vive** (berry growing).*

## 2. Problema que resuelve

La exploración bibliográfica humana es **iterativa, no lineal** (Kuhlthau, Ellis, Bates,
Pirolli, Wohlin — ver [`Notas/05`](Notas/05-ciclo-investigacion-humano.md) y
[`metodología.md`](Notas/metodología.md)): se siembra, se hace *chaining*, la query y la idea
**mutan** al leer (berrypicking), y la colección **se cultiva** en el tiempo (berry growing). El
snowballing manual es mecánico y agota; documentarlo con rigor (PRISMA / vom Brocke) es trabajo.

Las herramientas existentes resuelven mal este ciclo:

- Los **asistentes con IA** (Elicit, Consensus) son **cajas negras** que ocultan la query: el
  investigador pierde consciencia de qué recupera y por qué, y el resultado no es reportable.
- Los **mapas de citación** (Connected Papers, ResearchRabbit) son **one-shot** desde una
  semilla y no conservan una biblioteca curada que crezca.
- Los **tools bibliométricos** clásicos (bibliometrix, VOSviewer, metaknowledge) parten de un
  export que hay que conseguir y limpiar a mano, sin forrajeo asistido.

Falta una herramienta **abierta, poseída por el investigador**, que parta de la **ecuación
consciente**, **asista el forrajeo** usando la estructura bibliométrica como *information scent*,
y conserve una **biblioteca viva reproducible**.

La contribución (y la tesis del paper, [`Notas/05`](Notas/05-ciclo-investigacion-humano.md) §5)
es **re-instrumentar el ciclo humano clásico** con un método donde la **estructura bibliométrica
funciona como *information scent*** (forrajeo asistido, **determinista y reproducible, sin IA
generativa**), **sin desplazar el juicio humano**. Mapeo del ciclo de 9 pasos (05 §3–4) sobre el
producto:

| Paso del ciclo | En bib2graph |
|---|---|
| **0** · Idea / pregunta difusa | **Humano** — no se automatiza |
| **1–3** · Semillas → chaining/forrajeo → browsing/diferenciar | **Núcleo** (asistencia algorítmica: bibliometría = *information scent*, **determinista, sin IA**) |
| **4** · La query y la idea **mutan** | **Humano**; la herramienta lo soporta (re-sembrar, ecuaciones que evolucionan) |
| **5** · Organizar en evidencia | **Parcial** — las redes/métricas son la organización estructural; la matriz concepto×paper (Webster & Watson) no está |
| **6** · Sensemaking / tensiones | **Humano**, asistido por las redes (comunidades/centralidad/acoplamiento). La "máquina de tensiones" asistida por IA quedó **fuera del producto** (ADR 0008/0022) |
| **7** · Curar la biblioteca | **Sí** — biblioteca viva en DuckDB (berry growing); el *juicio* de qué curar es humano |
| **8** · Monitoreo / alertas de lo nuevo | **`chain --since`** (forrajeo incremental → `MONITORED`); alertas más ricas son futuro |

La **no-linealidad** (el lazo chain→curar→mutar→seed) es propiedad de primera clase: la biblioteca
viva existe precisamente para que la idea pueda mutar y volver a sembrarse sin perder lo acumulado. Se
modela como **máquina de estados explícita** (`CycleState`, con transiciones permisivas; ADR
[0016](decisiones/0016-maquina-estados-lazo.md)), que vive en el `library.duckdb` y se expone con
`b2g status`: humanos e IAs comparten el mismo mapa del lazo.

## 3. Para quién

bib2graph es **CLI / agente-native, sin GUI ni servicio web**. Su forma de uso por defecto es a través
de un agente (Claude Code u otro) que corre el ciclo; la skill de Claude Code (`b2g skill add`, ADR
[0039](decisiones/0039-skill-comando-meta-distribucion.md)) materializa el mensaje *"la mejor forma de
usar bib2graph es pedirle a Claude que lo use"*. Dos perfiles, en este orden:

- **Investigador/a no-técnico vía IA (primero).** Hace revisión de literatura o estudia la estructura
  intelectual de un campo, pero **no programa**: le pide a un agente que corra bib2graph por él. La
  superficie agéntica (10 verbos que mapean el ciclo, `--json`, exit codes, mensajes accionables) está
  diseñada para que el agente conduzca el ciclo end-to-end y entregue redes reproducibles para
  Gephi/VOSviewer (GraphML) o pandas (CSV), **sin montar infraestructura**.
- **Técnico que hurga (segundo).** Cómodo con la línea de comandos y con leer/extender la librería:
  corre `b2g` a mano, scriptea el ciclo, o importa el paquete Python. **Fácil PERO consciente:** la
  ecuación de búsqueda es ciudadana de primera clase y queda registrada; la superficie por defecto es
  diminuta.

No es una herramienta con GUI ni servicio gestionado: el core es CLI/agente-native sobre la biblioteca
viva. La experiencia visual library-centric vive en un **producto separado**, fuera de bib2graph (ADR
[0040](decisiones/0040-retiro-gui-local.md)).

## 4. Propuesta de valor

- **Consciente, no caja negra.** La ecuación de búsqueda es **ciudadana de primera clase**: se
  traduce a una query OpenAlex, se **muestra la query exacta ejecutada** y un **reporte de
  traducción** (qué mapeó limpio, qué se aproximó, qué se descartó). Eso *es* el ejercicio
  bibliotecario y lo que hace el resultado reportable (PRISMA / vom Brocke). Las **exclusiones
  quirúrgicas** (`b2g seed --exclude`, negaciones `AND NOT …`) quedan en el reporte, no se aplican en
  silencio. `--max-results` acota el fetch para exploración con muestras chicas.
- **Biblioteca viva, no mapa one-shot.** El corpus se cura y crece en el tiempo (berry growing),
  persistido en DuckDB. El investigador **posee** su colección.
- **Forrajeo asistido.** Chaining backward/forward sobre OpenAlex, con candidatos **rankeados
  por estructura bibliométrica** (acoplamiento/co-citación, centralidad) — *information scent*,
  no una lista plana.
- **Abierta y reproducible.** Cada corrida registra ecuación, query OpenAlex, profundidad,
  filtros, conteos y hash; se puede **exportar un snapshot** (foto reproducible) desde el estado
  vivo. Reproducibilidad por **historia auditable + snapshot sellado**, no por inmutabilidad ni por
  recómputo: **reproducir = re-leer/re-sellar el snapshot, NO re-correr la ecuación** (ADR
  [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)). OpenAlex **cambia en el tiempo**, así
  que la misma ecuación en otra fecha devuelve otro corpus (eso es *re-investigar*); el
  `openalex_version` del Manifest **ancla la foto** a la versión/fecha usada.
- **Agente-native como columna** (no adorno): doble salida (`--json`, también vía `B2G_JSON=1`), exit
  codes claros, errores accionables, sin estado entre invocaciones.
- **Sin infraestructura pesada.** DuckDB embebido, sin servidores; OpenAlex **funciona sin clave**
  (pool cortés con email en config) **pero con límite** (tier gratis, ~100 créditos/día); una **API
  key opcional sube el límite** para uso intensivo (#124).

## 5. Alcance

### 5.1 Dentro de alcance

- **Sembrado de doble puerta** (ADR [0035](decisiones/0035-ingesta-multipuerta-resolucion-doi.md)):
  por **ecuación de búsqueda** (términos, campos, años, idioma, tipo) **o** por **ingesta de archivo
  `.bib`** (puerta primaria, no secundaria) y/o **papers semilla** (DOIs / IDs). La ingesta desde
  `.bib` resuelve **DOI→`source_id`** contra el motor de extracción (`seed --from-bib --resolve`) para
  reconciliar las *pearls* con el corpus.
- **Contrato `Source` agnóstico** (ADR [0018](decisiones/0018-source-agnostico-calidad.md)):
  separa el **mínimo universal** que todo corpus necesita (`id`, título, año, autores, keywords — ya
  habilita co-autoría y co-word) del **enriquecimiento opcional** (referencias, citantes, afiliaciones
  per-autor, instituciones — habilita acoplamiento, co-citación, instituciones y asortatividad). Una
  `Source` de solo-mínimo es **legítima**: **habilita fuentes regionales** (SciELO / Redalyc / La
  Referencia) sin obligarlas a entregar lo que no tienen; los proyectores de enriquecimiento producen
  redes parciales y lo **reportan** (no fallan).
- **Traducción** de la ecuación a query OpenAlex con **query ejecutada visible + reporte de
  traducción**, ambas **registradas**. Incluye **negaciones quirúrgicas** (`b2g seed --exclude`,
  repetible) reportadas en el reporte de traducción, y **`--max-results`** para acotar el fetch.
- **Chaining asistido** backward/forward sobre OpenAlex; **profundidad 1 por defecto**, con **preview
  de crecimiento** y **tope** configurable; **`chain --since`** para forrajeo incremental (paso de
  monitoreo).
- **Ranking por estructura** (acoplamiento/co-citación, centralidad) de los candidatos —
  *information scent* **bibliométrico determinista, sin IA** (ADR
  [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)/[0022](decisiones/0022-producto-sin-ia-generativa.md)).
  El "porqué" de un candidato lo explica la **estructura visible** (con qué del corpus se acopla/co-cita),
  no un LLM.
- **Ejercicio bibliotecario**: dedup/normalización de autores/instituciones apoyada en IDs de
  OpenAlex (DOI/ORCID/ROR); **normalización de keywords vía thesaurus multilingüe** (en/es/pt, curado y
  auditable, JSON portable — `build --thesaurus`); **filtros de inclusión/exclusión** (año, tipo,
  idioma, mínimo de citas) con **conteo en cada filtro** (estilo flujo PRISMA — `curate filter`).
- **Biblioteca viva en DuckDB**: aceptar/rechazar candidatos (`curate accept/reject`, o en lote vía
  CSV con `curate dump`/`curate apply`); el corpus **persiste entre corridas**, crece y se cura, con
  **log de procedencia**.
- **Redes**: co-citación, acoplamiento bibliográfico (sobre el **corpus completo**, no solo semillas),
  co-autoría, co-ocurrencia de keywords, instituciones → **métricas y comunidades** (densidad,
  centralidades, Louvain/propagación/voraz; **asortatividad** por un atributo categórico configurable y
  por grado; **composición de comunidades**) → **export GraphML/CSV**. Las métricas que dependen de un
  **proxy** se reportan **con el disclaimer del proxy** (fácil pero consciente).
- **Nota de costo (honestidad):** la **co-citación** es la red más cara — requiere traer los citantes
  de las semillas *con sus propias listas de citas* (segundo nivel de fetch en OpenAlex). El
  **acoplamiento bibliográfico** usa las referencias que las semillas ya traen, es más barato y mira
  hacia adelante; por eso es ciudadano de primera.
- **Snapshot exportable**: foto reproducible (ecuación, query, filtros, conteos, hash, fecha/versión de
  OpenAlex) derivada del estado vivo, para reportar y reproducir.
- **CLI agente-native**: superficie de **10 verbos del ciclo** (`init, seed, chain, curate, build,
  read, export, snapshot, status, validate`) + 3 grupos noun-verb (`read`/`curate`/`snapshot`) +
  `skill add` (meta), cada subcomando con `--json` y exit codes (ADR
  [0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md)/[0038](decisiones/0038-destino-verbos-huerfanos-0037.md);
  detalle en [`API.md`](API.md) §Convenciones CLI).

### 5.2 Fuera de alcance / futuro

- **Máquina de tensiones** (intención de cita asistida por IA: apoya / refuta / escuelas en conflicto)
  → **fuera del producto** (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)): el producto no
  usa IA generativa; el sensemaking de tensiones lo hace el **humano leyendo las redes**
  (comunidades/centralidad/acoplamiento). El diferenciador es la **biblioteca viva curada + estructura
  bibliométrica de primera clase + flujo abierto**, no una capa de IA.
- **GUI / web / servicio gestionado** → **fuera** (ADR [0040](decisiones/0040-retiro-gui-local.md)): el
  core es CLI/agente-native sobre la biblioteca viva; el camino de adopción es la **skill** de Claude
  Code (ADR 0039). La experiencia visual library-centric vive en el **producto separado**, fuera de
  bib2graph.
- **Costura Zotero** → **descartada** (PO, 2026): el corazón de la persistencia es DuckDB nativo.
  Reabrible solo si aparece demanda real, como hito nuevo con su propio encuadre.
- **Neo4j** → **descartado** como adaptador planificado; ya no es sustrato. Reabrible solo con demanda
  real.
- **Matriz concepto×paper** (Webster & Watson, paso 5) → futuro; la organización es vía redes/métricas.
- **Fallback fuzzy/semántico del thesaurus por LLM/embeddings** → **fuera** (ADR 0022/0011): el
  thesaurus es **curado y determinista**; lo que no matchea queda fuera, sin inventar conceptos. El
  **dedup fuzzy determinista** (`rapidfuzz`, **en el núcleo**, automático en la ingesta — ADR
  [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)) sí queda — no es semántico ni LLM.
- **Lectura de PDFs full-text** → futuro.
- **WoS / Scopus / RIS / CSV como backbone** → `Source` futura. **BibTeX NO es secundaria:** la
  ingesta `.bib` es **puerta primaria** (doble puerta, ADR 0035), con resolución DOI→`source_id`.
- **Enricher Semantic Scholar para co-citación** → innecesario: refs y citantes vienen de OpenAlex.
- **Concurrencia multi-escritor** → **limitación conocida, no defecto** (ADR
  [0019](decisiones/0019-concurrencia-diferida.md)): DuckDB es single-writer (1 archivo = 1 escritor;
  lecturas concurrentes OK; varias investigaciones = varios archivos). Abrir el mismo archivo para
  escribir desde dos procesos falla claro (exit code `5`), no corrompe. Se resuelve post-1.0 según
  demanda.

## 6. Principios de producto

1. **Fácil PERO consciente.** La ecuación es ciudadana de primera clase, explícita y registrada.
2. **Asistencia algorítmica determinista, NO IA en el producto** (ADR
   [0022](decisiones/0022-producto-sin-ia-generativa.md)). La única asistencia es el **scent
   bibliométrico** del forrajeo (acoplamiento/co-citación/centralidad, determinista, reproducible). El
   **juicio humano** (formular la idea, dejarla mutar, decidir qué curar, leer las tensiones) **no se
   automatiza**. "AI-in-the-loop" se refiere **solo** al *desarrollo* asistido por IA (ver
   [`AI_DISCLOSURE.md`](../AI_DISCLOSURE.md)).
3. **Núcleo puro, costuras opcionales.** La lógica bibliométrica no depende de servidores ni red.
4. **Configuración inyectada, nunca embebida.** Ningún secreto en el código, sin efectos de import.
5. **Contratos estables y tipados** entre costuras (sin *signature drift*).
6. **Solo se promete lo que existe** (nada de clientes que se inicializan y nunca se consultan).
7. **Agente-native como columna**, diseñada desde el primer comando — no un extra futuro.
8. **Reproducibilidad por historia auditable + snapshot exportable**, no por inmutabilidad.

## 7. Historias de usuario (épicas)

> Definición de producto en historias, para extraer features y dejar claro **qué esperar**.

### Épica A — Sembrar con ecuaciones de búsqueda (consciente y estándar)
- **A1** · Definir el corpus con una **ecuación de búsqueda** (términos, campos, años, idioma), para
  partir del artefacto estándar y reproducible.
- **A2** · Que la herramienta **traduzca la ecuación a una consulta OpenAlex y muestre exactamente qué
  se ejecutó** (y sus límites), para ser consciente de qué se recupera.
- **A3** · Alternativamente sembrar con **papers semilla** (DOIs / IDs / un export BibTeX), para
  cuando se parte de *pearls* conocidos.
- **A4** · Que la ecuación quede **registrada y versionada** con la corrida, para reportarla
  (PRISMA / vom Brocke) y reproducirla.
- **A5** · Que las **ecuaciones evolucionen entre iteraciones** (berrypicking) y que la **biblioteca
  viva acumule** a través de esas versiones, para que el lazo sea de primera clase.

### Épica B — Forrajear: chaining asistido por estructura bibliométrica (sin IA)
- **B1** · **Backward chaining** (las referencias de las semillas) y **forward chaining** (lo que las
  cita) automáticos sobre OpenAlex, para no hacer snowballing a mano (Wohlin).
- **B2** · **Controlar la profundidad** (1 por defecto) y ver un **preview de cuánto crece** el corpus
  antes de traer, para no hacerlo explotar.
- **B3** · Candidatos **rankeados por estructura bibliométrica** (*information scent*:
  acoplamiento/co-citación, centralidad — **determinista, sin IA**), para revisar primero lo más
  relevante. El "porqué" lo da la **estructura visible**, no un LLM.

### Épica C — Ejercicio bibliotecario y biblioteca viva (curar y conservar)
- **C1** · **Dedup y normalización** de autores/instituciones apoyada en los IDs de OpenAlex
  (ORCID/ROR/DOI), para no pelear con variantes de nombres.
- **C2** · **Normalizar keywords con un thesaurus multilingüe** (en/es/pt) curado y auditable, para
  que conceptos equivalentes en distintos idiomas colapsen en la red de co-ocurrencia (p. ej.
  *intercambio ecológico desigual* ≡ *unequal exchange*). *(Sin fallback semántico/LLM: el thesaurus es
  determinista; el dedup fuzzy determinista corre automático en la ingesta con `rapidfuzz`.)*
- **C3** · Aplicar **criterios de inclusión/exclusión** (año, tipo, idioma, mínimo de citas) y ver el
  **conteo en cada filtro**, para curar con trazabilidad (estilo flujo PRISMA).
- **C4** · **Aceptar/rechazar** candidatos y que lo aceptado quede en la **biblioteca viva persistida
  en DuckDB**, que **crece entre corridas** con su log de procedencia, para cultivar la colección.

### Épica D — Proyectar a redes (el final sigue siendo las redes)
- **D1** · Proyectar el corpus a **co-citación, acoplamiento bibliográfico, co-autoría, co-ocurrencia
  de keywords e instituciones**, para analizar la estructura intelectual del campo.
- **D2** · **Métricas y comunidades** (densidad, centralidades, Louvain/propagación/voraz) sobre cada
  red.
- **D3** · **Asortatividad** (por un atributo categórico definido por el usuario y por grado) y la
  **composición de cada comunidad** por ese atributo, **con el disclaimer de si el atributo es un
  proxy**, para leer asimetrías estructurales (Norte–Sur, escuelas) sin tomar el proxy por verdad.
- **D4** · **Exportar GraphML/CSV** para Gephi/VOSviewer y pandas.

### Épica E — Reproducibilidad y agente-native
- **E1** · **Exportar un snapshot reproducible** del estado vivo (ecuación, query, fecha/versión de
  OpenAlex, profundidad, filtros, conteos, hash), para auditar y reportar.
- **E2** · Como **agente/automatización**, invocar cada paso por **CLI con `--json`** y exit codes
  claros, para orquestar el ciclo completo (`init → seed → chain → curate → build → read → export`)
  sin GUI.

## 8. Modelo de datos

- El **`Corpus` se respalda en un `TabularBackend` (Protocol)** y **delega las mutaciones** (ADR
  [0015](decisiones/0015-corpus-tabular-backend.md)). La persistencia por defecto **no es un `Store`
  con estado aparte**, sino el **`DuckDBBackend` del propio `Corpus`** (archivo `.duckdb`, mutación por
  SQL `UPDATE`/`MERGE` por `id`), que conserva el corpus entre corridas con su **log de procedencia**.
  El **`InMemoryBackend`** puro es el backend de los tests y del working set efímero. El **`DuckDBStore`
  es la fachada de costura** (`persist`/`load`) y el punto de extensión para destinos externos.
- El **`CycleState`** (ADR [0016](decisiones/0016-maquina-estados-lazo.md)) vive en ese backend
  persistente: **una investigación = un workspace** con su estado del lazo.
- El **snapshot** es un **export sellado derivable del estado vivo** (foto reproducible para reportar).
  **Reproducir = re-leer ese snapshot, no re-correr la ecuación** (ADR
  [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)).

Detalle del schema de columnas + la API del wrapper en [`API.md`](API.md) §1.

## 9. Criterios de madurez

- De una **ecuación de búsqueda** a un **GraphML** de al menos una red, **sin escribir código** y
  **sin servidores**.
- El **chaining** rankea candidatos por estructura, no por lista plana, con preview de crecimiento.
- El corpus **persiste y crece entre corridas** en DuckDB, con log de procedencia.
- La corrida es **reportable**: se exporta un snapshot **sellado** (con la query OpenAlex visible y el
  `openalex_version` que ancla la foto) que **otro investigador reproduce releyéndolo**, sin volver a
  llamar a OpenAlex (ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)).
- Dedup/normalización funciona apoyada en OpenAlex **sin configuración manual de nombres**.
- Cada subcomando tiene `--json`; el ciclo completo lo puede conducir un agente.

## 10. Caso de uso de referencia: la herramienta usándose a sí misma

El caso de referencia de bib2graph es **el ciclo de investigación aplicado a la teoría que mejora
bib2graph**: la herramienta **se usa a sí misma como objeto de estudio** para iterar su propio diseño.
La literatura sobre **forrajeo de información, ciclo de investigación humano y bibliometría** (Bates,
Ellis, Kuhlthau, Pirolli, Wohlin, vom Brocke; ver [`Notas/05`](Notas/05-ciclo-investigacion-humano.md)
y [`metodología.md`](Notas/metodología.md)) es a la vez **el corpus que bib2graph procesa** y **la
fuente de los requisitos** del producto: sembrar la ecuación de esa teoría, forrajear sus referencias y
citantes, curar la biblioteca viva, proyectar las redes y leer las tensiones es **lo que valida que el
método sirve** — y cada vuelta del ciclo retroalimenta el diseño (qué falta en el forrajeo, qué red
falla, qué fricción tiene el flujo agéntico). El producto es honesto consigo mismo cuando su propio
desarrollo corre por el ciclo que predica.

Esto tiene una consecuencia de proceso: las decisiones de producto y los hallazgos teóricos que surgen
de usar la herramienta entran por el flujo de siempre (nota → Discussion → ADR/issue), y los **docs
vivos** reflejan el resultado, no el debate.

El caso **intercambio ecológico desigual (IED)** —el pipeline corrido end-to-end sobre papers reales de
OpenAlex, con redes con estructura, thesaurus multilingüe y asimetría Norte–Sur medible (ver
[`exploracion/informe_ied_lectura_2.md`](../exploracion/informe_ied_lectura_2.md))— queda como **caso
de validación interna histórico**: evidencia de que el método produce resultados con datos reales, **no
un criterio de release**. El estudio de semiconductores sigue como caso documentado en
[`metodología.md`](Notas/metodología.md).
