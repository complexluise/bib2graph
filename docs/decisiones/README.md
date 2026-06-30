# Registro de decisiones de arquitectura (ADRs)

Cada decisión que cambia la arquitectura, los contratos o el "porqué" del proyecto se
registra como un ADR numerado e inmutable una vez aceptado. Si una decisión se revierte, se
crea un ADR nuevo que la supersede; no se reescribe la historia. Los refinamientos que **no**
revierten el principio se anotan como **bloques de "Enmienda" fechados** dentro del propio ADR
(el cuerpo original queda como historia).

**Tras el red-team del AS-BUILT v0.2** ([Nota 06](../Notas/06-critica-as-built-v0.2.md)) el PO
bloqueó un nuevo modelo conceptual (2026-06-15): el **producto no usa IA generativa** (ADR 0022);
el scent es **bibliométrico determinista** (0020 enmendado); el ciclo es un **FSM cíclico de
dominio** (0016 enmendado); **identidad ≠ procedencia** (0017 enmendado); y hay una **capa base de
constants/modelos/schema** (ADR 0023). Las enmiendas viven en cada ADR; ningún ADR se borró
(historia inmutable).

Las decisiones **de implementación/proceso** que toma la **IA** de forma autónoma (no
arquitectónicas) se anotan en [`registro-ia.md`](registro-ia.md). Los ADR decididos por la IA
llevan el campo `Decidido por: IA` en su encabezado.

## Plantilla

```markdown
# NNNN — Título corto en imperativo

- **Estado:** Propuesta | Aceptada | Supersedida por NNNN | Rechazada
- **Fecha:** AAAA-MM-DD

## Contexto
Qué problema u oportunidad motiva la decisión. Hechos, no opiniones.

## Decisión
Qué se decide, en una o dos frases claras.

## Consecuencias
Qué se vuelve posible/fácil y qué se vuelve costoso/imposible. Trade-offs honestos.
```

## Índice

> Los ADR se numeran **por orden de creación**, no se reservan en general. **0027** (pivote de
> posicionamiento GUI) y **0028** (arquitectura GUI/API + capa de servicios) existen ya como
> *Aceptada* (firmados 2026-06-18), derivados de la [Nota 12](../Notas/12-arquitectura-gui-encuadre.md)
> (revisada 2026-06-18): **0027 gatea 0028** y enmienda el PRD §3/§5.2.
> **Supersedidos por [0040](0040-retiro-gui-local.md)** (2026-06-28): la GUI local se **retira de la
> librería** (fuera del foco; el core es CLI/agente-native). 0027/0028 y las Notas de diseño
> (07/08/10/12/16/17) quedan como **historia inmutable**; la capa de servicios `service/` que el 0028
> introdujo **se conserva** (la usa el CLI). (El workspace —ex prerequisito GUI— sigue vigente como
> **0029**, Aceptada/AS-BUILT.)

| ADR | Título | Estado |
|-----|--------|--------|
| [0001](0001-herramienta-reutilizable.md) | Herramienta reutilizable en vez de pipeline de un solo uso | Aceptada |
| [0002](0002-modelo-agnostico-backend.md) | Modelo de dominio agnóstico de backend; Neo4j demotado a adaptador | Aceptada |
| [0003](0003-persistencia-opcional.md) | Persistencia opcional, en memoria por defecto | Aceptada · supersedida parcial. por [0009](0009-biblioteca-viva-duckdb.md) |
| [0004](0004-enriquecimiento-opcional.md) | Enriquecimiento opcional (verdad de dependencias) | Aceptada · reencuadrada por [0007](0007-openalex-backbone.md) (Enricher deja de ser estructural; S2 demotado) |
| [0005](0005-dependencias-extras.md) | Dependencias por extras + núcleo liviano | Aceptada · el extra `[llm]` se elimina por [0022](0022-producto-sin-ia-generativa.md) · el extra `[dedup]` se elimina por [0031](0031-preprocesamiento-automatico-en-ingesta.md) (`rapidfuzz` pasa a núcleo) |
| [0006](0006-tabla-canonica-y-networkspec.md) | Tabla canónica Arrow + NetworkSpec + snapshot | Aceptada · snapshot inmutable supersedido por [0009](0009-biblioteca-viva-duckdb.md) · Corpus-wrapper enmendado por [0015](0015-corpus-tabular-backend.md) |
| [0007](0007-openalex-backbone.md) | OpenAlex como backbone; BibTeX y enricher S2 demotados | Aceptada |
| [0008](0008-wedge-forrajeo.md) | Wedge V1 = forrajeo asistido por estructura bibliométrica | Aceptada · **enmendada** (2026-06-15): la máquina de tensiones se **retira** del producto, no se difiere ([0022](0022-producto-sin-ia-generativa.md)) |
| [0009](0009-biblioteca-viva-duckdb.md) | Biblioteca viva stateful en DuckDB; snapshot = export | Aceptada · reencuadrada por [0015](0015-corpus-tabular-backend.md) (DuckDB = backend por defecto) |
| [0010](0010-agente-native-columna.md) | CLI agente-native como columna primaria | Aceptada |
| [0011](0011-thesaurus-multilingue.md) | Thesaurus multilingüe determinista para keywords | Aceptada · **enmendada** (2026-06-15): se retira el fallback semántico/LLM ([0022](0022-producto-sin-ia-generativa.md)) |
| [0012](0012-openalex-credenciales.md) | Credenciales de OpenAlex: email + API key opcional, inyectados | Aceptada |
| [0013](0013-identidad-hash-merge-corpus.md) | Identidad estable de papers, hash de corpus order-independent y reglas de merge | Aceptada · reencuadrada por [0015](0015-corpus-tabular-backend.md) (D1/D2/D3 = contrato del backend) · AS-BUILT de D3 en DuckDB actualizado por [0024](0024-orden-d3-columna-secuencia-duckdb.md) (`_seq`) |
| [0014](0014-proyeccion-redes-pesos-asortatividad.md) | Semántica de proyección de redes: tipo de nodo, peso, scope y asortatividad por proxy | Aceptada |
| [0015](0015-corpus-tabular-backend.md) | `Corpus` sobre `TabularBackend`; DuckDB backend por defecto | Aceptada |
| [0016](0016-maquina-estados-lazo.md) | Máquina de estados del lazo; no-linealidad de primera clase; una investigación por archivo | Aceptada · **enmendada** (2026-06-15): FSM **cíclico** de dominio (`cycle.py`), `reseed` de primera clase + contador de ronda, `MONITORED`, **curación transversal** |
| [0017](0017-reproducibilidad-historia-snapshot.md) | Reproducibilidad por historia auditable + snapshot, no por recómputo | Aceptada · **enmendada** (2026-06-15): **identidad (contenido) vs procedencia**; `corpus_hash` excluye timestamps; reloj en la frontera; Louvain seeded |
| [0018](0018-source-agnostico-calidad.md) | Contrato `Source` agnóstico (mínimo universal vs enriquecimiento) + reporte de calidad declarado | Aceptada |
| [0019](0019-concurrencia-diferida.md) | Concurrencia diferida: limitación conocida, 1 archivo = 1 escritor | Aceptada |
| [0020](0020-metodo-forrajeo-scent-filtros-reject.md) | Método de forrajeo: scent bibliométrico determinista, backward puro / forward red, filtros que marcan `rejected` | Aceptada · **enmendada** (2026-06-15): scent pasa de frecuencia de enlace a **proyectores** (acoplamiento/co-citación/centralidad); `explain_candidate` y `[llm]` **eliminados** |
| [0021](0021-cli-agente-native-contrato.md) | Contrato del CLI agente-native `b2g`: set de 12 subcomandos (incl. `accept`/`reject`/`monitor`), envelope JSON versionado, exit codes por tipo, `--store` global | Aceptada · **enmendada** (2026-06-15): `status` muestra curación como acción siempre-disponible; refleja `reseed`/`MONITORED`; fix UTF-8 · **cleanup pre-v0.3** (2026-06-16): 12° subcomando `monitor` (→ `MONITORED`), asimetría del pre-check `monitor`/`chain`; alias `LoopState` retirado · **enmendada por [0037](0037-superficie-cli-10-verbos-ciclo.md)** (2026-06-26): consolida la superficie 12→**10 verbos** (absorbe `monitor`/`inspect`/`networks`; `curate`/`read` noun-verb); envelope `schema="1"`/exit codes/FSM **intactos** · **enmienda `B2G_JSON`** ([#151](https://github.com/complexluise/bib2graph/issues/151), 2026-06-27): env var truthy (`1`/`true`/`yes`) activa el modo JSON en **todos** los comandos (precedencia `--json` > env; sin `--no-json`); **stdout puro enforced** en `--json`/`B2G_JSON` (envelope único en stdout, incl. error); `--json` sigue por-comando post-verbo; envelope/exit/FSM intactos |
| [0022](0022-producto-sin-ia-generativa.md) | El producto no usa IA generativa; la "inteligencia" del forrajeo es estructura bibliométrica | Aceptada |
| [0023](0023-capa-constants-modelos-schema.md) | Capa base de vocabulario + modelos: `constants`, `ProvenanceEvent`, schema única (`PaperRow` ⇄ `CORPUS_SCHEMA`) | Aceptada |
| [0024](0024-orden-d3-columna-secuencia-duckdb.md) | Orden D3 en DuckDB vía columna de secuencia interna (`_seq`) | Aceptada · AS-BUILT (2026-06-16) |
| [0025](0025-enricher-cocitacion-openalex.md) | `Enricher` opt-in sobre OpenAlex (núcleo): refs→DOI + co-citación; supersede el `[s2]` del DoD del Hito 8 | Aceptada · AS-BUILT COMPLETO (2026-06-16): 8a + 8b → Hito 8 completo |
| [0026](0026-dedup-fuzzy-determinista.md) | Dedup fuzzy determinista con `rapidfuzz` (autores + keywords, función de librería); `splink` diferido a post-V1 | Aceptada · AS-BUILT (2026-06-16): Hito 7 · **supersedida en parte por [0031](0031-preprocesamiento-automatico-en-ingesta.md)** (2026-06-18): el dedup pasa de función de librería sin subcomando a **automático en la ingesta**; el algoritmo sigue vigente |
| [0027](0027-pivote-posicionamiento-gui-local.md) | Pivote de posicionamiento: GUI local opt-in para semi-técnicos (gatea 0028) | Aceptada (firmada 2026-06-18) · **supersedida por [0040](0040-retiro-gui-local.md)** (2026-06-28): la GUI local se retira de la librería (fuera del foco) |
| [0028](0028-arquitectura-gui-api-capa-servicios.md) | Arquitectura GUI/API/frontend: capa de servicios neutral (`service/`) + CLI/API como adaptadores + empaquetado (`[gui]`, wheel con frontend) | Aceptada (firmada 2026-06-18) · **supersedida por [0040](0040-retiro-gui-local.md)** (2026-06-28): se retiran API/SPA/`[gui]`; **la capa `service/` se conserva** (la usa el CLI) |
| [0029](0029-workspace-por-investigacion.md) | Workspace por investigación: carpeta autocontenida (`workspace.json` + db + redes/snapshots/exports) + resolución ambiente | **Aceptada — AS-BUILT** (2026-06-16; remanentes #32 cerrados 2026-06-17). **Enmienda BREAKING #75 (2026-06-17):** `--store` eliminado del CLI y fin del modo degenerado — la carpeta con `workspace.json` es la única unidad canónica; `.duckdb` legacy se adopta con `b2g init .`. Enmienda 0009/0019/0021; prerequisito GUI (#34) |
| [0030](0030-ecuacion-declarativa-corpus-ejemplo.md) | Ecuación declarativa (`equation.yaml`, `seed --spec`) + `restore` de corpus curado (sin red) + corpus de ejemplo commiteado (`examples/valoraciones/`) + `seed --from-bib` (BibTeX) + filtro de año | **Aceptada — AS-BUILT** (9a + 9b + Ciclo 10, 2026-06-17): `restore`+`equation.yaml` cargable; `examples/valoraciones/` + gate R2; **`seed --from-bib` + `examples/bibtex/` + filtro de año real (#50 cerrado)**. Enmienda 0029; relacionada 0005/0006/0007/0016/0017/0018; prereq. Ciclo #33 → gate GUI (#34) |
| [0031](0031-preprocesamiento-automatico-en-ingesta.md) | Preprocesamiento automático en la ingesta (normalize + dedup sobre el corpus completo mergeado, cross-biblioteca); `rapidfuzz` al núcleo (`[dedup]` eliminado); `thesaurus` = único paso explícito (18° subcomando, transversal); `persist_replace`/`overwrite_corpus` | **Aceptada — AS-BUILT** (2026-06-18, #88). **Supersede en parte [0026](0026-dedup-fuzzy-determinista.md)** (invocación del dedup) y la enmienda `[dedup]` de [0005](0005-dependencias-extras.md). Relacionada 0011/0017/0022/0024/0016; revisión asistida de clusters → epic GUI (#34) |
| [0032](0032-capa-servicios-duena-del-flujo.md) | La capa de servicios (`service/`) es dueña del loop bibliográfico completo (ingesta/resolución/enrich/curación/tags/forrajeo/proyección); CLI/API/GUI = adaptadores finos; migración por demanda | **Propuesta** (2026-06-18). **Extiende [0028](0028-arquitectura-gui-api-capa-servicios.md)** (de reads+curate a flujo entero). Relacionada 0010/0021/0027/0033/0035. Encuadre: [Nota 18](../Notas/18-flujo-canonico-biblioteca.md) |
| [0033](0033-producto-library-centric-grafo-proyeccion.md) | Producto library-centric: la vista de Biblioteca (buscar/navegar/etiquetar/curar) es la superficie primaria; el grafo es proyección downstream; BIBFRAME fuera | **Propuesta** (2026-06-18). **Refina [0027](0027-pivote-posicionamiento-gui-local.md)** (puerta de entrada de la GUI, no revierte). Relacionada 0009/0032/0034. Encuadre: Notas [16](../Notas/16-retroalimentacion-gui-mvp.md)/[18](../Notas/18-flujo-canonico-biblioteca.md) |
| [0034](0034-etiquetado-tabla-tags-lateral.md) | Etiquetado en tabla LATERAL `paper_tags` (no toca `CORPUS_SCHEMA`, esquiva BUG-2); tags libres → taxonomía fase 2 (SKOS + OpenAlex topics, no BIBFRAME); fuera del `corpus_hash` | **Propuesta** (2026-06-18). Relacionada 0009/0023/0006/0033/0011/0031/0024/0017. **Deja abierta** la extensibilidad general del schema (BUG-2). Encuadre: Notas [16](../Notas/16-retroalimentacion-gui-mvp.md)/[17](../Notas/17-validacion-tercero-gate34.md) |
| [0035](0035-ingesta-multipuerta-resolucion-doi.md) | Ingesta de doble puerta (online + archivo) misma cadena/corpus; resolución DOI→OpenAlex ID como servicio compartido (cierra GAP-1/GAP-2); import multi-formato (RIS/EndNote/CSV); BibTeX/archivo = primera clase | **Propuesta** (2026-06-18). **Revisa "BibTeX secundaria" de [0007](0007-openalex-backbone.md)** (en la ingesta). Relacionada 0018/0030/0032/0031. Encuadre: [Nota 17](../Notas/17-validacion-tercero-gate34.md) |
| [0036](0036-identidad-source-id-agnostica-doi-ancla.md) | Identidad de fuente agnóstica: DOI como ancla universal, `source_id` genérico, motor de extracción intercambiable (tabla lateral `external_ids` 1↔N) | **Aceptada — AS-BUILT** (0.8, 2026-06-22): rename `openalex_id`→`source_id`, inversión de `_compute_id` (`doi > source_id > tt`), desacople del núcleo, infra `external_ids`, migración de `examples/valoraciones` (#118/#119). **Enmienda 0007/0013**; refuerza 0018; relacionada 0035/0034/0015. Población de `external_ids` y selector `--source` diferidos al 2º motor (#120) |
| [0037](0037-superficie-cli-10-verbos-ciclo.md) | Superficie CLI de 0.10.0: **10 verbos agents-first** que mapean el ciclo (INIT→SEED→CHAIN→CURATE→BUILD→READ→EXPORT/SNAPSHOT, STATUS transversal); `status` como mapa (`next_best_action` + **preview por-red "qué se materializa" (e)** + **maturity-stamp del one-shot (f)**, campos aditivos); `curate`/`read` noun-verb; `monitor`→`chain --since`; aliases de retrocompat | **Aceptada** (2026-06-26). **Enmienda [0021](0021-cli-agente-native-contrato.md)** (consolida 12→10; envelope `schema="1"`/exit/FSM intactos). Relacionada 0010/0016/0029/0035/0036/0032/0033; no introduce IA (0022). Origen: Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127); issues #76/#132 |
| [0038](0038-destino-verbos-huerfanos-0037.md) | Destino de los 5 verbos huérfanos que el 0037 no nombró: `gui` se mantiene fuera de los 10 (0027/0028); `enrich`→absorbido en `chain`/`build`; `restore`→`snapshot restore`; `thesaurus`→retirado; `resolve`→retirado (ruta única `seed --resolve`). Fija: ventana de deprecación cierra en **0.11.0**; `build --scope=all` default; forma de `maturity` en `docs/API.md` | **Aceptada** (2026-06-27). **Enmienda [0037](0037-superficie-cli-10-verbos-ciclo.md)** (cierra el conteo "10 verbos"); revisa el `thesaurus` de [0031](0031-preprocesamiento-automatico-en-ingesta.md); renombre de [0030](0030-ecuacion-declarativa-corpus-ejemplo.md); refuerza 0035; envelope `schema="1"`/exit/FSM intactos. Contexto: issues #149/#34 |
| [0039](0039-skill-comando-meta-distribucion.md) | Distribución de la skill de Claude Code end-user: `b2g skill add [--user\|--project] [--force]` (comando **meta**; **fuera** del set de 10, no compite con `status`); skill vendoreada en el wheel (`src/bib2graph/skill/`, fuente commiteada incluida por `packages` — **no** `force-include`) → **version-lock skill==cli**; envelope `--json` sin FSM, sin workspace. **Descarta** el extra `[skill]` (no escribe en `~/.claude/skills/`) y plugin+marketplace como primario (desacopla versionado; ruta futura) | **Aceptada** (2026-06-28). **Enmienda [0038](0038-destino-verbos-huerfanos-0037.md)** (excepción meta); relacionada 0037/0028/0010/0021/0029; no introduce IA (0022). Epic [#188](https://github.com/complexluise/bib2graph/issues/188). **Nota (2026-06-28):** el [0040](0040-retiro-gui-local.md) retira `gui`, así que `skill` queda como **única** excepción meta (conteo "10 + skill") |
| [0040](0040-retiro-gui-local.md) | Retirar la GUI local de la librería (BREAKING): se eliminan `b2g gui`, la API local FastAPI (`api/`), la SPA `frontend/`, el extra `[gui]` y el vendoreo del frontend en el wheel; el core es CLI/agente-native sobre la biblioteca viva. **La capa `service/` (incl. `reads.py`) se conserva** (la usa el CLI). Conteo: "10 verbos + `skill`" | **Aceptada** (2026-06-28). **Supersede [0027](0027-pivote-posicionamiento-gui-local.md)/[0028](0028-arquitectura-gui-api-capa-servicios.md)**; enmienda [0038](0038-destino-verbos-huerfanos-0037.md) (retira la excepción `gui`); relacionada 0010/0021/0037/0039/0005/0019/0032/0033/0034; no introduce IA (0022). Issue [#190](https://github.com/complexluise/bib2graph/issues/190); limpieza profunda de docs en [#191](https://github.com/complexluise/bib2graph/issues/191) |
| [0041](0041-documentacion-por-superficie-de-entrega.md) | Organizar la documentación por **superficie de entrega**, no por tipo de lector: los tres usuarios = **dos superficies + un mediador** (agente dentro del repo → `AGENTS.md`/código; humano-y-agente navegando → sitio Diátaxis; IA externa → `llms.txt`). **No se forkea el sitio por audiencia**; se publica `llms.txt` (derivado de `AGENTS.md` + referencia CLI) en la raíz del sitio; persona = **veneer de navegación** (3 puertas por intención, 1 cuerpo); `AGENTS.md` sube al nav. La operación-por-IA es objetivo de 1ª clase | **Aceptada** (2026-06-29). Net-new (ningún ADR gobernaba la estructura de la doc); **no cambia contratos** (envelope/exit/FSM intactos). Relacionada 0039 (skill = doc operativa mediada por IA, fuera del sitio)/0010/0021/0037/0038/0040; no introduce IA (0022) |
| [0042](0042-semantic-scholar-segundo-motor.md) | Semantic Scholar como **2º motor de extracción**: `SemanticScholarSource` implementa `Source` (núcleo intacto); **la siembra exige API key** (429 sostenido en `/paper/search` sin key) mientras forrajeo/materialización corren sin key — asimetría por rol que **dobla 0012**; la ecuación se pasa **nativa** a S2 (sin traducción WoS, `translation_report` honesto); `paperId`→`source_id`, DOI ancla la identidad cross-motor (dedup gratis), `external_ids(engine="semanticscholar")`. **Fuera del hito:** selector CLI `--source` (PR propio) | **Propuesta** (2026-06-30). **Realiza [0036](0036-identidad-source-id-agnostica-doi-ancla.md)** (2º motor diferido, #120); enmienda el linaje de [0012](0012-openalex-credenciales.md) (siembra S2 sí pide key); refuerza 0018/0007. Encuadre IA (architect), decide el PO |
