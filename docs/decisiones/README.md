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

| ADR | Título | Estado |
|-----|--------|--------|
| [0001](0001-herramienta-reutilizable.md) | Herramienta reutilizable en vez de pipeline de un solo uso | Aceptada |
| [0002](0002-modelo-agnostico-backend.md) | Modelo de dominio agnóstico de backend; Neo4j demotado a adaptador | Aceptada |
| [0003](0003-persistencia-opcional.md) | Persistencia opcional, en memoria por defecto | Aceptada · supersedida parcial. por [0009](0009-biblioteca-viva-duckdb.md) |
| [0004](0004-enriquecimiento-opcional.md) | Enriquecimiento opcional (verdad de dependencias) | Aceptada · reencuadrada por [0007](0007-openalex-backbone.md) (Enricher deja de ser estructural; S2 demotado) |
| [0005](0005-dependencias-extras.md) | Dependencias por extras + núcleo liviano | Aceptada · el extra `[llm]` se elimina por [0022](0022-producto-sin-ia-generativa.md) |
| [0006](0006-tabla-canonica-y-networkspec.md) | Tabla canónica Arrow + NetworkSpec + snapshot | Aceptada · snapshot inmutable supersedido por [0009](0009-biblioteca-viva-duckdb.md) · Corpus-wrapper enmendado por [0015](0015-corpus-tabular-backend.md) |
| [0007](0007-openalex-backbone.md) | OpenAlex como backbone; BibTeX y enricher S2 demotados | Aceptada |
| [0008](0008-wedge-forrajeo.md) | Wedge V1 = forrajeo asistido por estructura bibliométrica | Aceptada · **enmendada** (2026-06-15): la máquina de tensiones se **retira** del producto, no se difiere ([0022](0022-producto-sin-ia-generativa.md)) |
| [0009](0009-biblioteca-viva-duckdb.md) | Biblioteca viva stateful en DuckDB; snapshot = export | Aceptada · reencuadrada por [0015](0015-corpus-tabular-backend.md) (DuckDB = backend por defecto) |
| [0010](0010-agente-native-columna.md) | CLI agente-native como columna primaria | Aceptada |
| [0011](0011-thesaurus-multilingue.md) | Thesaurus multilingüe determinista para keywords | Aceptada · **enmendada** (2026-06-15): se retira el fallback semántico/LLM ([0022](0022-producto-sin-ia-generativa.md)) |
| [0012](0012-openalex-credenciales.md) | Credenciales de OpenAlex: email + API key opcional, inyectados | Aceptada |
| [0013](0013-identidad-hash-merge-corpus.md) | Identidad estable de papers, hash de corpus order-independent y reglas de merge | Aceptada · reencuadrada por [0015](0015-corpus-tabular-backend.md) (D1/D2/D3 = contrato del backend) |
| [0014](0014-proyeccion-redes-pesos-asortatividad.md) | Semántica de proyección de redes: tipo de nodo, peso, scope y asortatividad por proxy | Aceptada |
| [0015](0015-corpus-tabular-backend.md) | `Corpus` sobre `TabularBackend`; DuckDB backend por defecto | Aceptada |
| [0016](0016-maquina-estados-lazo.md) | Máquina de estados del lazo; no-linealidad de primera clase; una investigación por archivo | Aceptada · **enmendada** (2026-06-15): FSM **cíclico** de dominio (`cycle.py`), `reseed` de primera clase + contador de ronda, `MONITORED`, **curación transversal** |
| [0017](0017-reproducibilidad-historia-snapshot.md) | Reproducibilidad por historia auditable + snapshot, no por recómputo | Aceptada · **enmendada** (2026-06-15): **identidad (contenido) vs procedencia**; `corpus_hash` excluye timestamps; reloj en la frontera; Louvain seeded |
| [0018](0018-source-agnostico-calidad.md) | Contrato `Source` agnóstico (mínimo universal vs enriquecimiento) + reporte de calidad declarado | Aceptada |
| [0019](0019-concurrencia-diferida.md) | Concurrencia diferida: limitación conocida, 1 archivo = 1 escritor | Aceptada |
| [0020](0020-metodo-forrajeo-scent-filtros-reject.md) | Método de forrajeo: scent bibliométrico determinista, backward puro / forward red, filtros que marcan `rejected` | Aceptada · **enmendada** (2026-06-15): scent pasa de frecuencia de enlace a **proyectores** (acoplamiento/co-citación/centralidad); `explain_candidate` y `[llm]` **eliminados** |
| [0021](0021-cli-agente-native-contrato.md) | Contrato del CLI agente-native `b2g`: set de 11 subcomandos (incl. `accept`/`reject`), envelope JSON versionado, exit codes por tipo, `--store` global | Aceptada · **enmendada** (2026-06-15): `status` muestra curación como acción siempre-disponible; refleja `reseed`/`MONITORED`; fix UTF-8 |
| [0022](0022-producto-sin-ia-generativa.md) | El producto no usa IA generativa; la "inteligencia" del forrajeo es estructura bibliométrica | Aceptada |
| [0023](0023-capa-constants-modelos-schema.md) | Capa base de vocabulario + modelos: `constants`, `ProvenanceEvent`, schema única (`PaperRow` ⇄ `CORPUS_SCHEMA`) | Aceptada |
