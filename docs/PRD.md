# PRD — bib2graph

> Documento de Requisitos de Producto de la **V1** de `bib2graph`. Reescribe el PRD anterior
> (que describía una librería BibTeX→redes con Semantic Scholar como enricher estructural y
> Neo4j como preocupación central) tras el **giro** documentado en `Notas/04`–`07` y la
> demolición de [`critica-base.md`](Notas/critica-base.md). Fecha: 2026-06-15 (reconciliado con el 2º
> giro).
>
> Documentos hermanos: la dirección "IA in the loop" en
> [`Notas/04-direccion-ia-in-the-loop.md`](Notas/04-direccion-ia-in-the-loop.md), el ciclo de
> investigación humano en [`Notas/05-ciclo-investigacion-humano.md`](Notas/05-ciclo-investigacion-humano.md),
> el método bibliométrico en [`metodología.md`](Notas/metodología.md), y las decisiones en
> [`decisiones/`](decisiones/) — en particular [ADR 0007](decisiones/0007-openalex-backbone.md)
> (OpenAlex backbone).
>
> ✅ **Reconciliación hecha:** `ARCHITECTURE.md`, `API.md` y `ROADMAP.md` ya están alineados con
> este PRD y los ADR 0007–0011 (OpenAlex backbone, biblioteca viva en DuckDB, forrajeo,
> agente-native, thesaurus). El `ROADMAP.md` ata cada hito a las historias del §7 con criterios
> de aceptación. Los ADR 0001–0006 son **registro histórico** (inmutables): los puntos superados
> quedan marcados como tales por los ADR 0007–0011, no se reescriben.
>
> ⚠️ **Reconciliación pendiente con el modelo nuevo (2026-06-15, ADR
> [0022](decisiones/0022-producto-sin-ia-generativa.md)/[0023](decisiones/0023-capa-constants-modelos-schema.md)):**
> tras el red-team del AS-BUILT ([Nota 06](Notas/06-critica-as-built-v0.2.md)) el PO bloqueó que el
> **producto NO usa IA generativa**: el *information scent* es **bibliométrico determinista vía
> proyectores** (sin LLM/embeddings); la **"máquina de tensiones" se RETIRA** (no se difiere a v2: se
> borra); `explain_candidate`/`[llm]` se **eliminan**; el sensemaking de tensiones es **humano**
> (asistido por las redes). Donde abajo este PRD aún dice "inserción de IA", "paso opcional de IA",
> "máquina de tensiones a v2" o "fallback fuzzy `[llm]`", **leerlo bajo esta corrección** (las §2/§5/§6/§7
> marcan los puntos afectados). El principio "IA in the loop, NOT human in the loop" se reencuadra a
> **"asistencia algorítmica determinista, no IA; el juicio humano no se automatiza"**.
>
> ✅ **Reconciliado con el 2º giro (2026-06-15):** este PRD incorpora los ADR
> [0015](decisiones/0015-corpus-tabular-backend.md)–[0019](decisiones/0019-concurrencia-diferida.md)
> (breaking change). En síntesis: la persistencia por defecto es el **`DuckDBBackend` del `Corpus`**
> (no un `Store` aparte), con `DuckDBStore` como **fachada de costura** (0015); el lazo es una
> **máquina de estados explícita** (`LoopState`, 0016); **reproducir = re-leer el snapshot, no
> re-correr la ecuación** (0017); el contrato `Source` es **agnóstico** (mínimo universal vs
> enriquecimiento opcional, habilita fuentes regionales, 0018); y la **concurrencia single-writer**
> es límite conocido (0019). El §8 ("modelo de datos") deja de ser una reconciliación *pendiente* y
> pasa a registrar la decisión adoptada.

## 1. Qué es

`bib2graph` V1 es una **librería de Python instalable** y una **CLI delgada agente-native**
construida sobre ella, que convierte una **ecuación de búsqueda** —el artefacto estándar y
reproducible de la ciencia— en una **biblioteca viva y curada** de literatura, y la proyecta a
**redes bibliométricas** listas para analizar (co-citación, acoplamiento bibliográfico,
co-autoría, co-ocurrencia de palabras clave, instituciones).

El backbone de datos es **OpenAlex** ([ADR 0007](decisiones/0007-openalex-backbone.md)). El
camino **no es un pipeline lineal** sino un **ciclo iterativo** (Bates / Ellis / Kuhlthau, ver
§2): se siembra desde la ecuación, se hace chaining rankeado por estructura, se diferencia y
cura, y **la ecuación y la idea mutan** — se vuelve a sembrar con otra pregunta. Asumir un flujo
lineal "query → resultados → fin" contradice a Bates/Ellis/Kuhlthau a la vez
([`Notas/05`](Notas/05-ciclo-investigacion-humano.md) §3). El corpus **vive y persiste** entre
esas iteraciones en **DuckDB** desde la V1.0 (no es el export de una sola corrida): es el
**sustrato que hace posible el lazo** — se acepta/rechaza, crece y se cultiva en el tiempo. Tras
el 2º giro, ese sustrato es el **`DuckDBBackend` del `Corpus`** (el backend por defecto, no un
`Store` aparte; ADR [0015](decisiones/0015-corpus-tabular-backend.md)), y el lazo es una **máquina
de estados explícita** (`LoopState`: `SEEDED → FORAGED → FILTERED → BUILT`, ADR
[0016](decisiones/0016-maquina-estados-lazo.md)): **una investigación = un archivo `.duckdb`**, su
estado se consulta con `b2g status`.

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
generativa**), **sin desplazar el juicio humano**.
Mapeo del ciclo de 9 pasos (05 §3–4) sobre la V1:

| Paso del ciclo | En la V1 |
|---|---|
| **0** · Idea / pregunta difusa | **Humano** — no se automatiza |
| **1–3** · Semillas → chaining/forrajeo → browsing/diferenciar | **Núcleo de V1** (asistencia algorítmica nº1: bibliometría = *information scent*, **determinista, sin IA**) |
| **4** · La query y la idea **mutan** | **Humano**; la herramienta lo soporta (re-sembrar, ecuaciones que evolucionan) |
| **5** · Organizar en evidencia | **Parcial** — las redes/métricas son la organización estructural; la matriz concepto×paper (Webster & Watson) no está en V1 |
| **6** · Sensemaking / tensiones | **Humano**, asistido por las redes (comunidades/centralidad/acoplamiento). La "máquina de tensiones" asistida por IA se **retiró** del producto (ADR 0008/0022), no es v2 |
| **7** · Curar la biblioteca | **V1** — biblioteca viva en DuckDB (berry growing); el *juicio* de qué curar es humano |
| **8** · Monitoreo / alertas de lo nuevo | **Futuro** (encaja sobre la biblioteca viva) |

La **no-linealidad** (el lazo 2→3→4→1) es propiedad de primera clase, no un detalle: la
biblioteca viva existe precisamente para que la idea pueda mutar y volver a sembrarse sin perder
lo acumulado. Tras el 2º giro esa no-linealidad **deja de ser solo prosa** y se modela como una
**máquina de estados explícita** (`LoopState`: `SEEDED → FORAGED → FILTERED → BUILT`, con
**transiciones permisivas** —se puede re-sembrar desde casi cualquier estado; ADR
[0016](decisiones/0016-maquina-estados-lazo.md)). El `LoopState` vive en el archivo `.duckdb` (no
en el `Corpus` efímero) y se expone con `b2g status`: humanos e IAs comparten el mismo mapa del
lazo en vez de inferir el punto del ciclo a partir del contenido.

## 3. Para quién

- **Investigadoras/es y analistas** que hacen revisión de literatura o estudian la estructura
  intelectual de un campo y quieren redes reproducibles para Gephi/VOSviewer (GraphML) o pandas
  (CSV), **sin montar infraestructura**.
- **Fácil PERO consciente** (crítica #3): cómodo con la línea de comandos, pero **el primer
  flujo de 10 minutos (ecuación → redes) es contrato de diseño**, no un tutorial posterior. La
  superficie por defecto es diminuta.
- **Agentes / automatizaciones** que orquestan `bib2graph` por CLI (`--json`, exit codes), sin
  GUI.

No es una herramienta para usuario final no técnico: no hay GUI ni servicio web en V1.

## 4. Propuesta de valor

- **Consciente, no caja negra.** La ecuación de búsqueda es **ciudadana de primera clase**: se
  traduce a una query OpenAlex, se **muestra la query exacta ejecutada** y un **reporte de
  traducción** (qué mapeó limpio, qué se aproximó, qué se descartó). Eso *es* el ejercicio
  bibliotecario y lo que hace el resultado reportable (PRISMA / vom Brocke).
- **Biblioteca viva, no mapa one-shot.** El corpus se cura y crece en el tiempo (berry growing),
  persistido en DuckDB. El investigador **posee** su colección.
- **Forrajeo asistido.** Chaining backward/forward sobre OpenAlex, con candidatos **rankeados
  por estructura bibliométrica** (acoplamiento/co-citación, centralidad) — *information scent*,
  no una lista plana.
- **Abierta y reproducible.** Cada corrida registra ecuación, query OpenAlex, profundidad,
  filtros, conteos y hash; se puede **exportar un snapshot** (foto reproducible) desde el estado
  vivo. Reproducibilidad por **historia auditable + snapshot sellado**, no por inmutabilidad ni por
  recómputo: **reproducir = re-leer/re-sellar el snapshot, NO re-correr la ecuación** (ADR
  [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)). OpenAlex **cambia en el tiempo**,
  así que la misma ecuación corrida en otra fecha devuelve otro corpus (eso es *re-investigar*, no
  reproducir); el `openalex_version` del Manifest **ancla la foto** a la versión/fecha de OpenAlex
  usada.
- **Agente-native como columna** (no adorno): doble salida (`--json`), exit codes claros,
  errores accionables, sin estado entre invocaciones.
- **Sin infraestructura pesada.** DuckDB embebido, sin servidores; OpenAlex sin clave
  obligatoria (pool cortés con email en config).

## 5. Alcance

### 5.1 Dentro de alcance (V1)

- **Sembrado** por **ecuación de búsqueda** (términos, campos, años, idioma, tipo) y/o por
  **papers semilla** (DOIs / IDs / un export BibTeX).
- **Contrato `Source` agnóstico** (ADR [0018](decisiones/0018-source-agnostico-calidad.md)):
  separa el **mínimo universal** que todo corpus necesita para existir (`id`, título, año, autores,
  keywords — ya habilita co-autoría y co-ocurrencia de keywords) del **enriquecimiento opcional**
  (referencias, citantes, afiliaciones per-autor, instituciones — habilita acoplamiento,
  co-citación, instituciones y asortatividad). Una `Source` que solo da el mínimo es **ciudadana
  legítima**: esto **habilita fuentes regionales** (SciELO / Redalyc / La Referencia) sin
  obligarlas a entregar lo que no tienen; los proyectores de enriquecimiento producen redes
  parciales y lo **reportan** (no fallan). El **reporte de cobertura/calidad** por seed/source se
  **declara** como contrato en V1 y se concreta en **v0.2+**.
- **Traducción** de la ecuación a query OpenAlex con **query ejecutada visible + reporte de
  traducción**, ambas **registradas** con la corrida.
- **Chaining asistido** backward/forward sobre OpenAlex; **profundidad 1 por defecto**, opt-in a
  2, con **preview de crecimiento** ("esta expansión sumaría ~N papers") y **tope** configurable.
- **Ranking por estructura** (acoplamiento/co-citación, centralidad) de los candidatos —
  *information scent* **bibliométrico determinista, sin IA** (ADR
  [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)/[0022](decisiones/0022-producto-sin-ia-generativa.md)).
- *(RETIRADO, ADR 0022:)* el "paso opcional de IA que explica por qué un candidato es relevante"
  (`explain_candidate`/`[llm]`) **se elimina** del producto. El "porqué" de un candidato lo explica la
  **estructura visible** (con qué del corpus se acopla/co-cita), no un LLM.
- **Ejercicio bibliotecario**: dedup/normalización de autores/instituciones apoyada en IDs de
  OpenAlex (DOI/ORCID/ROR); **normalización de keywords vía thesaurus multilingüe** (en/es/pt,
  curado y auditable, formato JSON portable); **filtros de inclusión/exclusión** (año, tipo,
  idioma, mínimo de citas) con **conteo en cada filtro** (estilo flujo PRISMA).
- **Biblioteca viva en DuckDB**: aceptar/rechazar candidatos; el corpus **persiste entre
  corridas**, crece y se cura, con **log de procedencia** (qué ecuación, qué chaining, qué
  decisión humana, cuándo).
- **Redes**: co-citación, acoplamiento bibliográfico (sobre el **corpus completo**, no solo
  semillas), co-autoría, co-ocurrencia de keywords, instituciones → **métricas y comunidades**
  (densidad, centralidades, Louvain/propagación/voraz; **asortatividad** por un atributo
  categórico configurable y por grado; **composición de comunidades** por ese atributo) →
  **export GraphML/CSV**. Las métricas que dependen de un **proxy** (p. ej. afiliación por-paper
  vs per-autor) se reportan **con el disclaimer del proxy** (fácil pero consciente).
- **Nota de costo (honestidad):** la **co-citación** es la red más cara — requiere traer los
  citantes de las semillas *con sus propias listas de citas* (un segundo nivel de fetch en
  OpenAlex). El **acoplamiento bibliográfico** usa las referencias que las semillas ya traen, es
  más barato y mira hacia adelante; por eso es ciudadano de primera (crítica #2). Validado con
  datos reales en [`exploracion/informe_ied_lectura_2.md`](../exploracion/informe_ied_lectura_2.md)
  (coupling sobre corpus completo = 646 aristas; co-citación aún requiere ese segundo nivel).
- **Snapshot exportable**: foto reproducible (ecuación, query, filtros, conteos, hash,
  fecha/versión de OpenAlex) derivada del estado vivo, para reportar y reproducir.
- **CLI agente-native**: cada subcomando con `--json` y exit codes.

### 5.2 Fuera de alcance / futuro (marcado explícito, NO en V1)

- **Máquina de tensiones** (intención de cita asistida por IA: apoya / refuta / escuelas en
  conflicto) → **RETIRADA del producto** (ADR
  [0022](decisiones/0022-producto-sin-ia-generativa.md), 2026-06-15): **no se difiere a v2, se
  borra**. El producto no usa IA generativa; el sensemaking de tensiones lo hace el **humano leyendo
  las redes** (comunidades/centralidad/acoplamiento). Era el candidato a *moat*
  ([`Notas/04`](Notas/04-direccion-ia-in-the-loop.md) §5); el diferenciador pasa a ser la **biblioteca
  viva curada + estructura bibliométrica de primera clase + flujo abierto**, no una capa de IA.
- **Costura Zotero** (biblioteca viva externa) → **V1.1**, extra opt-in `[zotero]`. El **corazón
  de la persistencia en V1.0 es DuckDB nativo**, no Zotero.
- **Monitoreo / alertas de literatura nueva** (paso 8 del ciclo, estilo Litmaps) → futuro;
  encaja sobre la biblioteca viva, pero no en V1.
- **Matriz concepto×paper** (Webster & Watson, paso 5) → futuro; en V1 la organización es vía
  redes/métricas.
- **Fallback fuzzy/semántico del thesaurus por LLM/embeddings** → **RETIRADO** (ADR
  [0022](decisiones/0022-producto-sin-ia-generativa.md)/[0011](decisiones/0011-thesaurus-multilingue.md)
  enmendado): el thesaurus es **curado y determinista**; lo que no matchea queda fuera, sin inventar
  conceptos con un modelo. El **dedup fuzzy determinista** (`rapidfuzz`, extra `[dedup]`, Hito 7) sí
  queda — no es semántico ni LLM.
- **Resolución de `references_doi` a DOI canónico** (OpenAlex las entrega como URLs internas) y
  fetch de **citantes-con-citas** para co-citación → trabajo del `Enricher`, fuera del primer
  flujo de V1.
- **Lectura de PDFs full-text** → futuro.
- **GUI / web / servicio gestionado** → fuera.
- **WoS / Scopus / RIS / CSV / BibTeX como backbone** → OpenAlex primero; el resto, `Source`
  futura. BibTeX queda como `Source` **secundaria** para sembrar desde *pearls*.
- **Neo4j** → adaptador `Store` opt-in post-V1; **ya no es sustrato**.
- **Enricher Semantic Scholar como camino para co-citación** → innecesario: las referencias y
  citantes vienen de OpenAlex ([ADR 0007](decisiones/0007-openalex-backbone.md)).
- **Concurrencia multi-escritor** → **limitación conocida, no defecto** (ADR
  [0019](decisiones/0019-concurrencia-diferida.md)): DuckDB es single-writer, así que la V1 asume
  **1 archivo `.duckdb` = 1 escritor** a la vez (lecturas concurrentes OK; varias investigaciones =
  varios archivos). Abrir el mismo archivo para escribir desde dos procesos falla claro (exit code
  `5`), no corrompe. Multi-escritor concurrente se resuelve post-v1.0 según demanda.

## 6. Principios de producto

1. **Fácil PERO consciente.** La ecuación es ciudadana de primera clase, explícita y registrada.
2. **Asistencia algorítmica determinista, NO IA en el producto** (ADR
   [0022](decisiones/0022-producto-sin-ia-generativa.md)). El producto **no usa IA generativa**: la
   única asistencia es el **scent bibliométrico** del forrajeo (acoplamiento/co-citación/centralidad,
   determinista, reproducible). El **juicio humano** (formular la idea, dejarla mutar, decidir qué
   curar, leer las tensiones) **no se automatiza**. "AI-in-the-loop" se refiere **solo** al
   *desarrollo* asistido por IA (ver [`AI_DISCLOSURE.md`](../AI_DISCLOSURE.md)).
3. **Núcleo puro, costuras opcionales.** La lógica bibliométrica no depende de servidores ni red.
4. **Configuración inyectada, nunca embebida.** Ningún secreto en el código, sin efectos de
   import (lecciones 1 y 6 de v0).
5. **Contratos estables y tipados** entre costuras (sin *signature drift*).
6. **Solo se promete lo que existe** (lección 5: nada de clientes que se inicializan y nunca se
   consultan).
7. **Agente-native como columna**, diseñada desde el primer comando — no un extra futuro.
8. **Reproducibilidad por historia auditable + snapshot exportable**, no por inmutabilidad.

## 7. Historias de usuario (épicas)

> Definición de producto en historias, para extraer features y dejar claro **qué esperar**.
> Adaptadas de [`_archivo/06`](_archivo/06-definicion-producto-v1.md) (archivada) tras cerrar el wedge (forrajeo)
> y el modelo de datos (biblioteca viva en DuckDB).

### Épica A — Sembrar con ecuaciones de búsqueda (consciente y estándar)
- **A1** · Como investigador, quiero definir mi corpus con una **ecuación de búsqueda**
  (términos, campos, años, idioma), para partir del artefacto estándar y reproducible.
- **A2** · Como investigador, quiero que la herramienta **traduzca mi ecuación a una consulta
  OpenAlex y me muestre exactamente qué se ejecutó** (y sus límites), para ser consciente de qué
  recupero.
- **A3** · Como investigador, quiero alternativamente sembrar con **papers semilla** (DOIs / IDs
  / un export BibTeX), para cuando parto de *pearls* conocidos.
- **A4** · Como investigador, quiero que mi ecuación quede **registrada y versionada** con la
  corrida, para reportarla (PRISMA / vom Brocke) y reproducirla.
- **A5** · Como investigador, quiero que mis **ecuaciones evolucionen entre iteraciones**
  (berrypicking: la idea muta y vuelvo a sembrar) y que la **biblioteca viva acumule** a través
  de esas versiones, para que el lazo del ciclo sea de primera clase y no una corrida tirada.

### Épica B — Forrajear: chaining asistido por estructura bibliométrica (sin IA)
- **B1** · Como investigador, quiero **backward chaining** (las referencias de mis semillas) y
  **forward chaining** (lo que las cita) automáticos sobre OpenAlex, para no hacer snowballing a
  mano (Wohlin).
- **B2** · Como investigador, quiero **controlar la profundidad** del chaining (1 por defecto,
  opt-in a 2) y ver un **preview de cuánto crece** el corpus antes de traer, para no hacerlo
  explotar.
- **B3** · Como investigador, quiero que los candidatos vengan **rankeados por estructura
  bibliométrica** (*information scent*: acoplamiento/co-citación, centralidad — **determinista, sin
  IA**), para revisar primero lo más relevante.
- ~~**B4** · paso opcional de IA que explique por qué un candidato es relevante~~ → **RETIRADA**
  (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)): el producto no usa IA generativa. El
  "porqué" lo da la **estructura visible** (con qué del corpus se acopla/co-cita el candidato), no un
  LLM. `explain_candidate`/`[llm]` se eliminan.

### Épica C — Ejercicio bibliotecario y biblioteca viva (curar y conservar)
- **C1** · Como investigador, quiero **dedup y normalización** de autores/instituciones apoyada
  en los IDs de OpenAlex (ORCID/ROR/DOI), para no pelear con variantes de nombres.
- **C2** · Como investigador, quiero **normalizar mis keywords con un thesaurus multilingüe**
  (en/es/pt) curado y auditable, para que conceptos equivalentes en distintos idiomas colapsen en
  la red de co-ocurrencia (p. ej. *intercambio ecológico desigual* ≡ *unequal exchange*) y no
  queden dispersos. *(Sin fallback semántico/LLM: el thesaurus es determinista — ADR 0022/0011. El
  dedup fuzzy determinista de keywords fuera del thesaurus es el Hito 7, `[dedup]`.)*
- **C3** · Como investigador, quiero aplicar **criterios de inclusión/exclusión** (año, tipo,
  idioma, mínimo de citas) y ver el **conteo en cada filtro**, para curar con trazabilidad
  (estilo flujo PRISMA).
- **C4** · Como investigador, quiero **aceptar/rechazar** candidatos y que lo aceptado quede en
  mi **biblioteca viva persistida en DuckDB**, que **crece entre corridas** con su log de
  procedencia, para cultivar la colección (berry growing). *(La sincronización con Zotero llega
  como costura opt-in en V1.1.)*

### Épica D — Proyectar a redes (el final sigue siendo las redes)
- **D1** · Como investigador, quiero proyectar el corpus a **co-citación, acoplamiento
  bibliográfico, co-autoría, co-ocurrencia de keywords e instituciones**, para analizar la
  estructura intelectual del campo.
- **D2** · Como investigador, quiero **métricas y comunidades** (densidad, centralidades,
  Louvain/propagación/voraz) sobre cada red.
- **D3** · Como investigador, quiero **asortatividad** (por un atributo categórico que yo defino
  —p. ej. región geográfica— y por grado) y la **composición de cada comunidad** por ese
  atributo, **con el disclaimer de si el atributo es un proxy** (p. ej. afiliación por-paper vs
  per-autor), para leer asimetrías estructurales (Norte–Sur, escuelas en conflicto) sin tomar el
  proxy por verdad.
- **D4** · Como investigador, quiero **exportar GraphML/CSV** para Gephi/VOSviewer y pandas.

### Épica E — Reproducibilidad y agente-native
- **E1** · Como investigador, quiero **exportar un snapshot reproducible** del estado vivo
  (ecuación, query, fecha/versión de OpenAlex, profundidad, filtros, conteos, hash), para
  auditar y reportar.
- **E2** · Como **agente/automatización**, quiero invocar cada paso por **CLI con `--json`** y
  exit codes claros, para orquestar bib2graph sin GUI.

## 8. Modelo de datos (reconciliado)

La elección **biblioteca viva desde V1** (corpus stateful en DuckDB) era **incompatible con el
snapshot inmutable** que consagraban `ARCHITECTURE.md` §6.2 y el ADR 0006, y con el `InMemoryStore`
por defecto del ADR 0003. La reconciliación quedó cerrada por los ADR 0009 y, tras el 2º giro,
precisada por el ADR [0015](decisiones/0015-corpus-tabular-backend.md):

- El **`Corpus` se respalda en un `TabularBackend` (Protocol)** y **delega las mutaciones**
  (ADR [0015](decisiones/0015-corpus-tabular-backend.md)). La persistencia por defecto **no es un
  `Store` con estado aparte**, sino el **`DuckDBBackend` del propio `Corpus`** (archivo `.duckdb`,
  mutación por SQL `UPDATE`/`MERGE` por `id`), que conserva el corpus entre corridas con su **log de
  procedencia**. El **`InMemoryBackend`** puro es el backend de los tests y del working set efímero
  (el núcleo se testea sin DuckDB). El **`DuckDBStore` es la fachada de costura** (`persist`/`load`)
  y el punto de extensión para destinos externos.
- El **`LoopState`** (ADR [0016](decisiones/0016-maquina-estados-lazo.md)) vive en ese backend
  persistente: **una investigación = un archivo `.duckdb`**, con su estado del lazo.
- El **snapshot deja de ser el modelo de datos** y es un **export sellado derivable del estado
  vivo** (foto reproducible para reportar). **Reproducir = re-leer ese snapshot, no re-correr la
  ecuación** (ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)).
- **Zotero** queda como **costura externa opt-in en V1.1**, no como la persistencia de 1.0.

Esta reconciliación ya está reflejada en `ARCHITECTURE.md` (§3.1, §4.3, §6.2), `API.md` (§1, §4) y
`ROADMAP.md` (Hitos 1.5/3). El estado de construcción (Hitos 0–6 + 1.5 terminados; v0.2 cubre el
**flujo**, con la **tanda de remediación R1–R5 pendiente** antes de los Hitos 7–11) vive en el
`ROADMAP.md`.

## 9. Criterios de "V1 hecha"

- De una **ecuación de búsqueda** a un **GraphML** de al menos una red, **sin escribir código** y
  **sin servidores**.
- El **chaining** rankea candidatos por estructura, no por lista plana, con preview de
  crecimiento.
- El corpus **persiste y crece entre corridas** en DuckDB, con log de procedencia.
- La corrida es **reportable**: se exporta un snapshot **sellado** (con la query OpenAlex visible y
  el `openalex_version` que ancla la foto) que **otro investigador reproduce releyéndolo**, sin
  volver a llamar a OpenAlex (ADR [0017](decisiones/0017-reproducibilidad-historia-snapshot.md)).
- Dedup/normalización funciona apoyada en OpenAlex **sin configuración manual de nombres**.
- Cada subcomando tiene `--json`.

## 10. Métricas de éxito

- El **primer flujo de 10 minutos** (ecuación → redes → export) corre **sin claves obligatorias
  ni infraestructura**.
- El núcleo tiene **cobertura de tests unitarios** real sobre proyección, métricas, comunidades y
  dedup (la testabilidad que v0 nunca tuvo).
- Un caso real se **reproduce** desde la ecuación, cumpliendo criterios de calidad
  **configurables** por el usuario (no umbrales hardcodeados — crítica #5). Ya hay **evidencia
  con datos reales**: el sandbox de **intercambio ecológico desigual (IED)** corrió el pipeline
  end-to-end sobre 103 papers de OpenAlex, con 3/4 redes con estructura, thesaurus multilingüe y
  asimetría Norte–Sur medible (ver
  [`exploracion/informe_ied_lectura_2.md`](../exploracion/informe_ied_lectura_2.md)). El estudio
  de semiconductores sigue como caso documentado en [`metodología.md`](Notas/metodología.md).
- Agregar una nueva `Source` o `Store` no requiere modificar el núcleo.

## 11. Próximos pasos

> ⚠️ **Corrección 2026-06-15:** el punto 1 es **planning histórico ya saldado** (los ADR 0007–0021
> están escritos). Donde dice "tensiones a v2", leer **"tensiones RETIRADAS del producto"** (ADR
> 0022); el thesaurus es **determinista sin fallback fuzzy/LLM** (ADR 0011 enmendado). El próximo
> trabajo real es la **tanda de remediación R1–R5** del [`ROADMAP.md`](ROADMAP/README.md).

1. **Nuevos ADRs** (architect), además del [0007](decisiones/0007-openalex-backbone.md) ya
   redactado: wedge = forrajeo (~~tensiones a v2~~ → **retiradas**, ADR 0022); **biblioteca viva en
   DuckDB** (supersede la premisa de 0003 y 0006); agente-native como columna; **thesaurus
   multilingüe** (T6/T10 del sandbox; formato JSON portable, **determinista sin fallback LLM**).
2. ✅ `ARCHITECTURE.md`, `API.md` y `ROADMAP.md` **reconciliados** con este PRD (§8) y con los
   ADR 0007–0011, y luego con el **2º giro** (ADR
   [0015](decisiones/0015-corpus-tabular-backend.md)–[0019](decisiones/0019-concurrencia-diferida.md)).
3. ✅ Implementación por hitos en curso (coder): **Hitos 0–6 + 1.5 terminados** (núcleo del corpus
   stateful sobre `TabularBackend`, proyectores/analizadores/export, biblioteca viva en DuckDB,
   fuentes OpenAlex/BibTeX, forrajeo + `Preprocessor` + filtros PRISMA, y el **CLI agente-native
   `b2g`** — 13 subcomandos, ADR [0021](decisiones/0021-cli-agente-native-contrato.md) +
   [0025](decisiones/0025-enricher-cocitacion-openalex.md) (`enrich`, Ciclo 8a)). Con ello
   v0.2 alcanza las capacidades del **flujo** `seed → … → export`. **El red-team de la
   [Nota 06](Notas/06-critica-as-built-v0.2.md) corrige el claim "capacidades completas":** falta la
   **tanda de remediación R1–R5** (modelo sin IA, identidad-vs-procedencia reproducible, FSM cíclico,
   scent bibliométrico, robustez) **antes** de los Hitos 7–11. Tras R1–R5 se construyó el **Hito 8 ✅**
   (`Enricher` OpenAlex: refs→DOI + co-citación end-to-end, `enrich --max-citing`); siguen pendientes
   los Hitos 7 (dedup fuzzy), 9 (`NetworkSpec` YAML), 10 (viz) y 11 (Zotero/Neo4j). Estado vivo en el
   [`ROADMAP.md`](ROADMAP/README.md).
