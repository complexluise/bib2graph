# PRD — bib2graph

> Documento de Requisitos de Producto de la **V1** de `bib2graph`. Reescribe el PRD anterior
> (que describía una librería BibTeX→redes con Semantic Scholar como enricher estructural y
> Neo4j como preocupación central) tras el **giro** documentado en `Notas/04`–`07` y la
> demolición de [`critica-base.md`](critica-base.md). Fecha: 2026-06-14.
>
> Documentos hermanos: la dirección "IA in the loop" en
> [`Notas/04-direccion-ia-in-the-loop.md`](Notas/04-direccion-ia-in-the-loop.md), el ciclo de
> investigación humano en [`Notas/05-ciclo-investigacion-humano.md`](Notas/05-ciclo-investigacion-humano.md),
> el método bibliométrico en [`metodología.md`](metodología.md), y las decisiones en
> [`decisiones/`](decisiones/) — en particular [ADR 0007](decisiones/0007-openalex-backbone.md)
> (OpenAlex backbone).
>
> ✅ **Reconciliación hecha:** `ARCHITECTURE.md`, `API.md` y `ROADMAP.md` ya están alineados con
> este PRD y los ADR 0007–0011 (OpenAlex backbone, biblioteca viva en DuckDB, forrajeo,
> agente-native, thesaurus). El `ROADMAP.md` ata cada hito a las historias del §7 con criterios
> de aceptación. Los ADR 0001–0006 son **registro histórico** (inmutables): los puntos superados
> quedan marcados como tales por los ADR 0007–0011, no se reescriben.

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
**sustrato que hace posible el lazo** — se acepta/rechaza, crece y se cultiva en el tiempo.

*El final siguen siendo las redes; lo nuevo es **cómo se llega a ellas** (forrajeo asistido) y
que **la colección vive** (berry growing).*

## 2. Problema que resuelve

La exploración bibliográfica humana es **iterativa, no lineal** (Kuhlthau, Ellis, Bates,
Pirolli, Wohlin — ver [`Notas/05`](Notas/05-ciclo-investigacion-humano.md) y
[`metodología.md`](metodología.md)): se siembra, se hace *chaining*, la query y la idea
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
es **re-instrumentar el ciclo humano clásico** insertando IA solo en los puntos donde la
estructura bibliométrica funciona como *information scent*, **sin desplazar el juicio humano**.
Mapeo del ciclo de 9 pasos (05 §3–4) sobre la V1:

| Paso del ciclo | En la V1 |
|---|---|
| **0** · Idea / pregunta difusa | **Humano** — no se automatiza |
| **1–3** · Semillas → chaining/forrajeo → browsing/diferenciar | **Núcleo de V1** (inserción de IA nº1: bibliometría = *information scent*) |
| **4** · La query y la idea **mutan** | **Humano**; la herramienta lo soporta (re-sembrar, ecuaciones que evolucionan) |
| **5** · Organizar en evidencia | **Parcial** — las redes/métricas son la organización estructural; la matriz concepto×paper (Webster & Watson) no está en V1 |
| **6** · Sensemaking / tensiones | **v2** (máquina de tensiones, inserción de IA nº2) |
| **7** · Curar la biblioteca | **V1** — biblioteca viva en DuckDB (berry growing); el *juicio* de qué curar es humano |
| **8** · Monitoreo / alertas de lo nuevo | **Futuro** (encaja sobre la biblioteca viva) |

La **no-linealidad** (el lazo 2→3→4→1) es propiedad de primera clase, no un detalle: la
biblioteca viva existe precisamente para que la idea pueda mutar y volver a sembrarse sin perder
lo acumulado.

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
  vivo. Reproducibilidad por **historia auditable**, no por inmutabilidad.
- **Agente-native como columna** (no adorno): doble salida (`--json`), exit codes claros,
  errores accionables, sin estado entre invocaciones.
- **Sin infraestructura pesada.** DuckDB embebido, sin servidores; OpenAlex sin clave
  obligatoria (pool cortés con email en config).

## 5. Alcance

### 5.1 Dentro de alcance (V1)

- **Sembrado** por **ecuación de búsqueda** (términos, campos, años, idioma, tipo) y/o por
  **papers semilla** (DOIs / IDs / un export BibTeX).
- **Traducción** de la ecuación a query OpenAlex con **query ejecutada visible + reporte de
  traducción**, ambas **registradas** con la corrida.
- **Chaining asistido** backward/forward sobre OpenAlex; **profundidad 1 por defecto**, opt-in a
  2, con **preview de crecimiento** ("esta expansión sumaría ~N papers") y **tope** configurable.
- **Ranking por estructura** (acoplamiento/co-citación, centralidad) de los candidatos.
- **Paso opcional de IA** que **explica por qué** un candidato es relevante / a qué conversación
  pertenece — **sin decidir por el humano**.
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

- **Máquina de tensiones** (intención de cita: apoya / refuta / escuelas en conflicto) → **v2**.
  Es el candidato a *moat* ([`Notas/04`](Notas/04-direccion-ia-in-the-loop.md) §5), **deferido a
  propósito** para que la V1 sea un wedge entregable (inserción de IA nº1: forrajeo).
- **Costura Zotero** (biblioteca viva externa) → **V1.1**, extra opt-in `[zotero]`. El **corazón
  de la persistencia en V1.0 es DuckDB nativo**, no Zotero.
- **Monitoreo / alertas de literatura nueva** (paso 8 del ciclo, estilo Litmaps) → futuro;
  encaja sobre la biblioteca viva, pero no en V1.
- **Matriz concepto×paper** (Webster & Watson, paso 5) → futuro; en V1 la organización es vía
  redes/métricas.
- **Fallback fuzzy/semántico del thesaurus** (embeddings o LLM barato para keywords que no
  matchean el thesaurus curado) → futuro (v0.2). En V1 el thesaurus es **curado y determinista**
  (decisión abierta exhaustivo-vs-cobertura+fuzzy, ver ADR pendiente en §11).
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

## 6. Principios de producto

1. **Fácil PERO consciente.** La ecuación es ciudadana de primera clase, explícita y registrada.
2. **IA in the loop, NOT human in the loop.** La IA entra en **1–2 puntos** (forrajeo en V1;
   tensiones en v2); el **juicio humano** (formular la idea, dejarla mutar, decidir qué curar)
   no se automatiza.
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

### Épica B — Forrajear: chaining asistido (inserción de IA nº1)
- **B1** · Como investigador, quiero **backward chaining** (las referencias de mis semillas) y
  **forward chaining** (lo que las cita) automáticos sobre OpenAlex, para no hacer snowballing a
  mano (Wohlin).
- **B2** · Como investigador, quiero **controlar la profundidad** del chaining (1 por defecto,
  opt-in a 2) y ver un **preview de cuánto crece** el corpus antes de traer, para no hacerlo
  explotar.
- **B3** · Como investigador, quiero que los candidatos vengan **rankeados por estructura
  bibliométrica** (*information scent*: acoplamiento/co-citación, centralidad), para revisar
  primero lo más relevante.
- **B4** · Como investigador, quiero un paso **opcional** de IA que me **explique por qué** un
  candidato es relevante, para decidir más rápido — **sin que decida por mí**.

### Épica C — Ejercicio bibliotecario y biblioteca viva (curar y conservar)
- **C1** · Como investigador, quiero **dedup y normalización** de autores/instituciones apoyada
  en los IDs de OpenAlex (ORCID/ROR/DOI), para no pelear con variantes de nombres.
- **C2** · Como investigador, quiero **normalizar mis keywords con un thesaurus multilingüe**
  (en/es/pt) curado y auditable, para que conceptos equivalentes en distintos idiomas colapsen en
  la red de co-ocurrencia (p. ej. *intercambio ecológico desigual* ≡ *unequal exchange*) y no
  queden dispersos. *(Fallback fuzzy/semántico → v0.2.)*
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

## 8. Modelo de datos (reconciliación pendiente)

La elección **biblioteca viva desde V1** (corpus stateful en DuckDB) es **incompatible con el
snapshot inmutable** que hoy consagran `ARCHITECTURE.md` §6.2 y el ADR 0006, y con el
`InMemoryStore` por defecto del ADR 0003. Reconciliación adoptada por este PRD:

- El **núcleo de V1.0 tiene un `Store` con estado** (DuckDB embebido): el corpus persiste entre
  corridas, con **log de procedencia** de cada decisión.
- El **snapshot deja de ser el modelo de datos** y pasa a ser un **export derivable del estado
  vivo** (foto sellada para reportar).
- **Zotero** queda como **costura externa opt-in en V1.1**, no como la persistencia de 1.0.

Llevar esto a `ARCHITECTURE.md`, `ROADMAP.md` (Hito 1: `seal`→inmutable) y a nuevos ADRs es
tarea del **architect** (ver §11).

## 9. Criterios de "V1 hecha"

- De una **ecuación de búsqueda** a un **GraphML** de al menos una red, **sin escribir código** y
  **sin servidores**.
- El **chaining** rankea candidatos por estructura, no por lista plana, con preview de
  crecimiento.
- El corpus **persiste y crece entre corridas** en DuckDB, con log de procedencia.
- La corrida es **reportable**: se exporta un snapshot reproducible con la query OpenAlex visible.
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
  de semiconductores sigue como caso documentado en [`metodología.md`](metodología.md).
- Agregar una nueva `Source` o `Store` no requiere modificar el núcleo.

## 11. Próximos pasos

1. **Nuevos ADRs** (architect), además del [0007](decisiones/0007-openalex-backbone.md) ya
   redactado: wedge = forrajeo (tensiones a v2); **biblioteca viva en DuckDB** (supersede la
   premisa de 0003 y 0006); agente-native como columna; **thesaurus multilingüe** (T6/T10 del
   sandbox: exhaustivo vs cobertura+fuzzy, formato JSON portable).
2. ✅ `ARCHITECTURE.md`, `API.md` y `ROADMAP.md` **reconciliados** con este PRD (§8) y con los
   ADR 0007–0011.
3. Recién entonces, implementación por hitos (coder), empezando por el núcleo del corpus
   stateful y el sembrado por ecuación → OpenAlex.
