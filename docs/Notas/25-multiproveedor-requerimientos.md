# 25 — Soporte multi-proveedor: requerimientos para delimitar candidatos

> **Nota de exploración / encuadre.** Fecha: 2026-06-30. El PO trae una dirección que ya
> piden los usuarios: **no depender solo de OpenAlex** (Semantic Scholar, CrossRef, …) y,
> en lo posible, abrir cobertura al **Sur global** (Latinoamérica, África, Asia),
> priorizando **español / inglés** (el producto es principalmente para hispanohablantes).
>
> El pedido explícito es **lo primero, extraer requerimientos** que nos ayuden a delimitar
> qué proveedores entran y cuáles no. Esta nota hace eso y deja una primera criba de
> candidatos *a verificar*. No decide nada todavía — lo accionable está al final.

## Tesis

Depender solo de OpenAlex es un **punto único de falla** en tres dimensiones a la vez:
cobertura (qué papers existen para el motor), disponibilidad (si OpenAlex se cae o cambia
términos, el ciclo entero se cae) y **misión** (OpenAlex cubre mal mucho del Sur global y
de la producción en español). Abrir proveedores no es solo robustez técnica: es alinear la
herramienta con para quién es.

**La buena noticia (del mapeo de código):** el motor ya está preparado. Existe un
`Protocol Source` (`src/bib2graph/sources/base.py:39`) con dos métodos —`seed(query)` y
`load(path)`— y dos implementaciones (`OpenAlexSource`, `BibtexSource`). La **identidad
canónica es DOI-first** (ADR 0036: precedencia `doi > source_id > título+año`,
`corpus.py:54`). Y la arquitectura separa **Source / Enricher / Forager**. Esto define el
encuadre de los requerimientos: **no son una lista plana; son lo que un proveedor debe
cumplir según el ROL que vaya a jugar.**

## El contrato que un proveedor debe poder llenar (anclado al código)

| Pieza del motor | Qué exige del proveedor | Dónde vive |
|---|---|---|
| `Source.seed(query)` | búsqueda por ecuación → papers | `sources/base.py:39` |
| Schema canónico (mín. ADR 0018) | `title`, `year`, `authors_raw`, `keywords_raw` (el `id` se calcula) | `schemas.py:130`, `base.py:46` |
| Identidad / dedup (ADR 0036) | **DOI** (ideal) u otro id estable resoluble | `corpus.py:54` |
| Backward chaining | referencias salientes (`references_id` inline) | `forager.py:136` |
| Forward chaining | citantes en lote (`fetch_citing_batch`-equivalente) | `openalex.py:996` |
| Enricher (opcional) | resolver `DOI → metadatos / refs` por lote | `enrichers/openalex.py` |

## Los tres roles que puede jugar un proveedor

Como el motor ya separa Source / Enricher / Forager, **un proveedor no tiene que hacer
todo**. Esto agranda el universo de candidatos y simplifica los adaptadores:

1. **Sembrador / buscador** — sabe responder una ecuación de búsqueda. Alimenta la *Puerta
   A* (ecuación → corpus). Requiere endpoint de search con filtros.
2. **Forrajeador (grafo de citas)** — expone referencias y/o citantes. Es el **corazón del
   producto** (`b2g chain`). Un proveedor sin citas NO puede forrajear.
3. **Enriquecedor / resolución** — dado un DOI/ID devuelve metadatos o refs. No necesita
   search ni grafo; sirve para rellenar huecos y para la resolución `DOI → ID` de la
   Puerta B (BibTeX/RIS).

Un mismo proveedor puede cubrir varios roles (OpenAlex cubre los tres). Otros solo uno
(CrossRef es fuerte en resolución y refs salientes, débil en citantes).

## Requerimientos (criterios de criba)

Marcados **[MUST]** (sin esto no entra), **[SHOULD]** (lo queremos, negociable según rol) y
**[NICE]** (suma, no decide). Un proveedor se evalúa **contra el rol** que aspira a cubrir.

### Eje A — Acceso y licencia (gating duro)

- **A1 [MUST]** API HTTP pública y documentada. **No scraping.** (Esto descarta Google
  Scholar de entrada — ver Nota 24: la fragilidad del scraping es justo de lo que huimos.)
- **A2 [MUST]** Gratuita para uso académico. **Registro / API key está OK**; lo que no
  entra es de pago obligatorio o muro institucional.
- **A3 [MUST]** Términos que **permitan almacenar y derivar** los metadatos: la biblioteca
  viva los guarda y el grafo es un derivado. Ideal licencia abierta de los datos (CC0,
  como OpenAlex y CrossRef). Verificar caso por caso.
- **A4 [SHOULD]** Cuotas compatibles con forrajeo (polite pool o rate limit razonable; no
  límites que hagan inviable expandir una red de cientos de papers).

### Eje B — Encaje con el motor (el contrato Source)

- **B1 [MUST]** Provee los campos mínimos del schema (ADR 0018): `title`, `year`,
  `authors_raw`, `keywords_raw`.
- **B2 [MUST]** **DOI** u otro identificador estable y resoluble, para que la identidad
  canónica DOI-first deduplique cross-proveedor sin trabajo extra.
- **B3 [SHOULD, según rol]** Búsqueda por query con filtros (necesario para rol
  *sembrador*; prescindible si solo enriquece).
- **B4 [SHOULD fuerte]** **Grafo de citas**: referencias salientes (backward) y/o citantes
  (forward). Es lo que separa un proveedor *útil para el producto* de uno que solo
  engorda metadatos. Sin esto, el proveedor queda relegado a enriquecer.
- **B5 [NICE]** Lookup por **lista de IDs / batching** (para materializar y para citantes
  en lote ≤~50). Sin batching el forrajeo es lento pero posible.

### Eje C — Cobertura y misión (Sur global · idioma)

- **C1 [SHOULD]** Cobertura **real** de LatAm / África / Asia, o de un dominio/idioma que
  OpenAlex cubre mal. Aquí pesan SciELO, Redalyc, La Referencia, DOAJ.
- **C2 [SHOULD]** Indexa **español / inglés** (alineado con el público hispano).
- **C3 [MUST de valor]** **Valor marginal**: que aporte papers o citas que OpenAlex **no**
  tiene. Si solo replica a OpenAlex, no justifica la complejidad de un adaptador nuevo.
  (Criterio anti-over-engineering: cada proveedor paga su costo de mantenimiento.)

### Eje D — Operabilidad y sostenibilidad

- **D1 [SHOULD]** Gobernanza estable detrás (institución, no proyecto que muere en un año).
- **D2 [SHOULD]** Rate limits documentados, paginación (cursor), polite pool / key opcional
  inyectable sin default literal (coherente con ADR 0012).
- **D3 [MUST]** Respuesta parseable (JSON). Mapeo JSON→fila razonable.
- **D4 [NICE]** Bajo costo de adaptador: ¿hace falta traducir la ecuación de búsqueda?
  ¿cuánta lógica defensiva? (OpenAlex pidió un traductor WoS→OpenAlex no trivial.)

## Primera criba de candidatos (PRELIMINAR — a verificar)

> ⚠️ Tabla de trabajo. Las capacidades exactas de cada API (rate limits, presencia de
> citantes vs solo refs, licencia precisa) **hay que verificarlas** antes de decidir.
> Marco rol probable y banderas, no afirmo hechos cerrados.

| Proveedor | Rol probable | Citas (fwd/back) | Sur global / idioma | Bandera a verificar |
|---|---|---|---|---|
| **Semantic Scholar (S2 Academic Graph)** | sembrador + forrajeador | refs **y** citantes (fuerte) | global, fuerte en CS/inglés | key gratuita opcional; cobertura ES |
| **CrossRef** | resolución + sembrador | refs salientes (~depende del editor); **sin citantes** | global vía editores; ES si el editor deposita | forward citations las da OpenCitations, no CrossRef |
| **OpenCitations (COCI/INDEX)** | forrajeador puro | citas DOI→DOI, CC0 | global (lo que esté en COCI) | solo capa de citas; sin metadatos ni search |
| **DOAJ** | sembrador (OA) | no es grafo de citas | **fuerte OA Sur global / ES** | API de metadatos; ¿refs? |
| **SciELO** | sembrador + cobertura | citas limitadas | **núcleo Iberoamérica ES/PT** | madurez/forma de la API (ArticleMeta/OAI) |
| **Redalyc** | cobertura | limitado | **LatAm ES** | ¿API real o solo portal? |
| **La Referencia** | cobertura (agregador) | no | **LatAm, repositorios** | OAI-PMH, granularidad de metadatos |
| **CORE / BASE** | cobertura OA (agregadores) | no | global OA | calidad/dedup de metadatos |
| **Europe PMC** | sembrador + forrajeador (biomed) | refs y citas | global, biomed | dominio acotado a biomedicina |

**Lectura de la criba:** ningún proveedor único reemplaza a OpenAlex. El patrón natural es
**composición por rol**: S2 como segundo backbone con citas; CrossRef + OpenCitations como
par resolución+citas; y una **capa Sur global** (SciELO / DOAJ / La Referencia) que aporta
cobertura ES aunque sea pobre en grafo de citas. Esto encaja con la separación
Source/Enricher que ya existe.

## Verificación empírica (probe del 2026-06-30)

> Golpeamos las APIs reales con un script (`examples/multiproveedor-probe/probe_apis.py`,
> resultados en `RESULTS.md`). Esto **sustituye conjeturas por HTTP real** en varias filas
> de la criba de arriba. Una llamada por capacidad; no exhaustivo.

- **Semantic Scholar** — el **grafo de citas funciona sin key**: `references`, `citations`
  (forward) y `batch` → HTTP 200. Pero `search` dio **429 sostenido** aun con backoff
  exponencial (4 intentos, hasta 8 s). ⇒ **forrajeador hoy sin credencial; sembrador exige
  la API key gratuita**. Confirma el 2º backbone, con ese matiz operativo.
- **CrossRef** — search ✓, DOI nativo, **85 referencias depositadas**; forward es solo un
  *conteo* (`is-referenced-by-count=207`), no la lista. Confirmado: sembrador + refs +
  resolución, **sin citantes**.
- **OpenCitations** — citantes **n=208**, refs **n=72**, CC0. Completa el forward que a
  CrossRef le falta. El par CrossRef+OpenCitations cubre resolución + grafo completo.
- **DOAJ** — búsqueda en español ✓ (artículos **ES/PT**), pero **DOI solo ~1/3** de la
  primera página. Cobertura hispana real; dedup DOI-first parcial.
- **SciELO (ArticleMeta)** — el endpoint **no es búsqueda full-text** (lista PIDs por
  colección); el artículo de muestra sin DOI. Sirve por otra puerta (cosecha OAI), no para
  *seed* por ecuación vía este endpoint.

**Veredicto empírico del 2º slot Sur-global: DOAJ > SciELO** — DOAJ tiene búsqueda JSON
real que devuelve contenido ES/PT; SciELO-ArticleMeta es cosecha masiva, no seeding por
ecuación. (Re-probar SciELO por su Search API / OAI si se lo prioriza luego.)

## Verificación documental (deep-research citado, 2026-06-30)

> Un `deep-research` con verificación adversarial (24 fuentes, 22 claims confirmados)
> corroboró capacidades **con cita oficial** y corrigió dos cosas del probe. **Confianza:**
> lo de S2 pasó verificación 3-0; lo de DOAJ/SciELO/CrossRef viene de fuente primaria pero el
> corte de presupuesto lo dejó fuera del voto final → *reconfirmar antes de implementar*.
>
> **Nota de alcance:** la licencia de los *datos* de un proveedor es problema del **consumidor**
> (Atalaya / el producto), **no de bib2graph**. El motor es determinista y agnóstico a la fuente;
> solo le importa el contrato técnico (`Source`). Por eso esta nota no evalúa licencias de datos
> como criterio de inclusión del motor.

**Correcciones al probe:**
- **SciELO SÍ tiene citantes:** servicio `CitedBy` (REST, forward por DOI/título/SciELO-ID,
  `github.com/scieloorg/citedby`, BSD-2) + `ArticleMeta` para metadatos. Mi probe la
  subvaloró por golpear solo ArticleMeta-identifiers.
- **DOAJ:** API pública gratuita; key solo para editores que cargan datos → *seed/search sin
  key*. Buena cobertura OA hispana (ES/PT).
- **CrossRef:** public pool gratis sin registro (5 req/s registros · 1 req/s listas, conc. 1);
  **polite pool** con `mailto` sube límites. Sin citantes forward (confirmado: solo conteo).

## Matriz de decisión consolidada (probe empírico + deep-research)

| Proveedor | Acceso | Sembrar | Refs (back) | Citantes (fwd) | DOI | Cobertura ES / Sur | Rol recomendado |
|---|---|---|---|---|---|---|---|
| **OpenAlex** (baseline) | gratis | ✓ | ✓ | ✓ | ✓ | media | backbone (sigue) |
| **Semantic Scholar** | gratis; key gratis p/ search | ✓ (key) | ✓ | ✓ | ✓ | **sin verificar** | **2º backbone (a implementar)** |
| **CrossRef** | gratis, polite pool | ✓ | ✓ (depositadas) | ✗ (solo conteo) | ✓ nativo | vía editores | resolución + refs (roadmap) |
| **OpenCitations** | gratis | ✗ | ✓ | ✓ (DOI→DOI) | ✓ | global | forrajeador, par de CrossRef |
| **DOAJ** | gratis (sin key p/ search) | ✓ (ES/PT) | ✗ | ✗ | parcial (~1/3) | **fuerte OA hispana** | **1ª Sur-global del piloto** |
| **SciELO** | gratis (ArticleMeta+CitedBy) | parcial (no full-text search) | ? | ✓ (CitedBy) | parcial | **núcleo Iberoamérica** | Sur-global alternativa |

**Recomendación del piloto:** **S2** (2º backbone) **+ DOAJ** (1ª Sur-global: búsqueda real en
ES/PT). SciELO queda como alternativa fuerte si se prioriza grafo de citas iberoamericano
(tiene `CitedBy`) sobre facilidad de búsqueda.

## Tensiones honestas (para el PO, no se deciden acá)

1. **¿Cuántos proveedores y en qué orden?** Cada adaptador es código a mantener (C3, D4).
   Recomendación tentativa: **S2 primero** (cubre los tres roles, es el pedido más fuerte
   de usuarios y suma citas), y **una sola** fuente Sur-global de prueba — **DOAJ** según
   el probe empírico — para validar el eje misión antes de invertir en varias.
2. **Conflicto y merge cross-proveedor.** Si el mismo paper viene de OpenAlex y S2 con
   metadatos distintos, ¿quién gana? La identidad DOI-first colapsa el `id`, pero el
   *merge de campos* necesita política (precedencia por fuente, o último que escribe).
   Probable **ADR nuevo** (toca contrato de corpus / `normalize_and_dedup`, ADR 0031).
3. **Proveedor sin DOI** (mucho del Sur global). Cae al fallback `título+año`, más frágil
   para dedup. ¿Aceptamos ruido de identidad a cambio de cobertura? Decisión de producto.
4. **Selección de proveedor por comando.** ¿`b2g seed --source s2`? ¿multi-fuente en una
   corrida? ¿default configurable por workspace? Es superficie CLI nueva — encuadrar
   contra el ADR de superficie agente-native (0.10.0).
5. **Forward citations sin proveedor que las dé** (caso CrossRef): obliga a emparejar con
   OpenCitations. ¿Vale un proveedor que solo sirve emparejado?

## Accionable (sin compromiso)

1. **Verificar la criba con datos reales** — capacidades de API, licencia y cobertura ES de
   cada candidato (sobre todo S2, CrossRef+OpenCitations y la capa Sur global). Candidato a
   un `deep-research` con fuentes citadas; convertir el resultado en una matriz de decisión.
2. **Promover a Discussion** lo que cuaje de esta nota (note-first → Discussion): el debate
   de *qué proveedores y en qué orden* vive ahí, no en la nota.
3. **ADRs que esto va a disparar** (anotar, no escribir aún): (a) **merge cross-proveedor**
   (precedencia de campos sobre ADR 0031), (b) **selección de proveedor / multi-fuente** en
   la superficie CLI. Cambios a contratos públicos → ADR antes de mergear (regla del repo).
4. **Decisión del PO**: **S2 decidido como 2º backbone — a implementar.** Pendiente: alcance
   del piloto (recomendado **S2 + DOAJ**) y política para papers sin DOI (tensión 3).
5. **Reconfirmar** las capacidades de DOAJ/SciELO/CrossRef contra docs oficiales (el
   deep-research las extrajo de fuente primaria pero no pasaron el voto adversarial final).

## Síntesis

El motor **ya tiene la puerta** (`Protocol Source`, identidad DOI-first, separación
Source/Enricher/Forager): agregar proveedores es implementar un contrato conocido, no
rediseñar. Los requerimientos se ordenan **por rol** (sembrar / forrajear / enriquecer) y
por cuatro ejes (acceso, encaje, misión, operabilidad). La criba preliminar dice que **no
hay reemplazo único de OpenAlex**: el camino es **composición por rol**, con S2 como
segundo backbone y una capa Sur-global para la misión hispana. Lo que falta antes de
decidir: **verificar** las APIs candidatas y que el PO fije el alcance del piloto y la
política de identidad sin DOI.
