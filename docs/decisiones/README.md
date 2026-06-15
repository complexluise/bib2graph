# Registro de decisiones de arquitectura (ADRs)

Cada decisión que cambia la arquitectura, los contratos o el "porqué" del proyecto se
registra como un ADR numerado e inmutable una vez aceptado. Si una decisión se revierte, se
crea un ADR nuevo que la supersede; no se reescribe la historia.

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
| [0004](0004-enriquecimiento-opcional.md) | Enriquecimiento opcional (verdad de dependencias) | Aceptada |
| [0005](0005-dependencias-extras.md) | Dependencias por extras + núcleo liviano | Aceptada |
| [0006](0006-tabla-canonica-y-networkspec.md) | Tabla canónica Arrow + NetworkSpec + snapshot | Aceptada · snapshot inmutable supersedido por [0009](0009-biblioteca-viva-duckdb.md) · Corpus-wrapper enmendado por [0015](0015-corpus-tabular-backend.md) |
| [0007](0007-openalex-backbone.md) | OpenAlex como backbone; BibTeX y enricher S2 demotados | Aceptada |
| [0008](0008-wedge-forrajeo.md) | Wedge V1 = forrajeo asistido; tensiones a v2 | Aceptada |
| [0009](0009-biblioteca-viva-duckdb.md) | Biblioteca viva stateful en DuckDB; snapshot = export | Aceptada · reencuadrada por [0015](0015-corpus-tabular-backend.md) (DuckDB = backend por defecto) |
| [0010](0010-agente-native-columna.md) | CLI agente-native como columna primaria | Aceptada |
| [0011](0011-thesaurus-multilingue.md) | Thesaurus multilingüe determinista para keywords | Aceptada |
| [0012](0012-openalex-credenciales.md) | Credenciales de OpenAlex: email + API key opcional, inyectados | Aceptada |
| [0013](0013-identidad-hash-merge-corpus.md) | Identidad estable de papers, hash de corpus order-independent y reglas de merge | Aceptada · reencuadrada por [0015](0015-corpus-tabular-backend.md) (D1/D2/D3 = contrato del backend) |
| [0014](0014-proyeccion-redes-pesos-asortatividad.md) | Semántica de proyección de redes: tipo de nodo, peso, scope y asortatividad por proxy | Aceptada |
| [0015](0015-corpus-tabular-backend.md) | `Corpus` sobre `TabularBackend`; DuckDB backend por defecto | Aceptada |
| [0016](0016-maquina-estados-lazo.md) | Máquina de estados del lazo; no-linealidad de primera clase; una investigación por archivo | Aceptada |
| [0017](0017-reproducibilidad-historia-snapshot.md) | Reproducibilidad por historia auditable + snapshot, no por recómputo | Aceptada |
| [0018](0018-source-agnostico-calidad.md) | Contrato `Source` agnóstico (mínimo universal vs enriquecimiento) + reporte de calidad declarado | Aceptada |
| [0019](0019-concurrencia-diferida.md) | Concurrencia diferida: limitación conocida, 1 archivo = 1 escritor | Aceptada |
