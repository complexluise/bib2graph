# 0007 — OpenAlex como backbone de datos; BibTeX y enricher S2 demotados

- **Estado:** Aceptada
- **Fecha:** 2026-06-14
- **Relacionada con:** [0004](0004-enriquecimiento-opcional.md) (cambia su premisa central),
  [0001](0001-herramienta-reutilizable.md)

## Contexto

El diseño previo (ver [`../PRD.md`](../PRD.md) anterior y
[`../critica-base.md`](../Notas/critica-base.md) §1) pivoteaba sobre **BibTeX como entrada de
referencia**. Pero el BibTeX **no trae las listas de referencias citadas**, y eso fabricaba el
problema más caro de toda la arquitectura: un `Enricher` de Semantic Scholar **estructural**
para poder construir la red de co-citación (API keys, rate limits, rama opcional, reintentos
sin perder papers). Era un problema **autoinfligido** por la elección del formato de entrada.

Los hechos que cambian la ecuación:

- **OpenAlex** entrega referencias citadas **y** citantes **gratis, sin clave obligatoria**
  (key gratuita desde feb-2026), con cobertura de referencias comparable a WoS/Scopus.
- Trae **IDs canónicos** (DOI / ORCID / ROR) que habilitan dedup/normalización sin pelear con
  variantes de nombres.
- Al traer refs y citantes, habilita el **chaining asistido** (backward/forward snowballing) y
  el **ranking por estructura bibliométrica** (*information scent*) **sin enricher**.
- Soporta **boolean + búsqueda por campo + filtros facetados**, lo que permite traducir una
  ecuación de búsqueda a una query ejecutable y registrable.

## Decisión

**OpenAlex es la fuente primaria y el backbone de datos de la V1.** La **ecuación de búsqueda**
se traduce a una query OpenAlex, mostrando la query exacta ejecutada y un **reporte de
traducción** (qué mapeó limpio, qué se aproximó, qué se descartó).

- **BibTeX pasa a `Source` secundaria** (sembrar desde un export o desde *pearls* conocidos),
  ya no es la entrada de referencia.
- **El `Enricher` de Semantic Scholar deja de ser estructural**: las referencias y citantes ya
  vienen de OpenAlex, así que **co-citación y acoplamiento ya no dependen de él**. S2 queda como
  costura futura opcional para señal adicional, no como camino para construir redes.

## Consecuencias

- **Las cinco redes** (co-citación, acoplamiento bibliográfico, co-autoría, co-ocurrencia de
  keywords, instituciones) se construyen **sin keys ni enricher estructural**.
- Se habilitan la **épica de forrajeo/chaining asistido** y el ranking por estructura como
  *information scent* — el corazón del valor de la V1.
- **Mejor reproducibilidad de la fuente**: OpenAlex publica snapshots versionados; cada corrida
  registra fecha/versión de OpenAlex además de la ecuación y la query.
- **Cambia la premisa central de [ADR 0004](0004-enriquecimiento-opcional.md)**: ese ADR
  justificaba el enricher por la carencia de referencias del BibTeX. Con OpenAlex esa carencia
  desaparece; el enricher deja de ser el camino para co-citación. El **principio** de 0004
  (enriquecimiento opt-in, nunca obligatorio, keys inyectadas) sigue vigente; su **motivación**
  queda superada por este ADR.
- **Límites que hay que explicitarle al investigador** (principio "consciente", por eso el
  reporte de traducción): stemming + stop-words ON por defecto, sin proximidad `NEAR/n`,
  comodines que se comportan distinto a WoS, tags de campo (`TS=`/`AB=`/`AU=`) que no mapean
  1:1, y cobertura distinta a WoS/Scopus (la misma ecuación da resultados distintos — es
  advertencia de reproducibilidad, no bug).
- **Costo**: se asume dependencia de la API y la cobertura de OpenAlex. Se mitiga con un **pool
  cortés** (email/API key en config para rate limit sano) y por tratarse de **datos abiertos**
  versionados, no de un proveedor cerrado y pago.
