# Destrucción del concepto base — para rediseñar mejor

> Red team adversarial del diseño **actual** de `bib2graph` (el de
> [`PRD.md`](../PRD.md) / [`ARCHITECTURE.md`](../ARCHITECTURE.md)). El objetivo no es defender lo
> escrito: es **romperlo a propósito** para que el rediseño nazca de una crítica honesta y no
> de la inercia. Si un argumento aguanta, queda como restricción del nuevo diseño; si se cae,
> mejor que se caiga ahora. Documento hermano: [`referentes.md`](referentes.md).
> Fecha: 2026-06-14.

## Tesis central

El diseño actual está **justificado hacia adentro** (expiar los pecados de v0: Neo4j
acoplado, claves hardcodeadas, sin tests) y **no hacia afuera** (ganarle a un referente real
en algo que a un usuario le importe). Una reescritura cuyo principal argumento es "no
repetiremos *nuestros* errores" produce, en el mejor caso, un cadáver bien arquitecturado
—como [`metaknowledge`](referentes.md), que está muerto desde hace ~4 años pese a ser
técnicamente sólido. La higiene no es propuesta de valor.

## Los golpes

### 1. El pecado original: BibTeX como entrada *fabrica* el problema más caro
Toda la arquitectura pivotea sobre "BibTeX no trae referencias → necesitamos el `Enricher` de
Semantic Scholar → API keys, rate limits, rama opcional, reintentos". **Ese problema es
autoinfligido.** WoS/Scopus exportan las referencias citadas incluidas (campo CR);
**OpenAlex** las da gratis, sin key (key gratis desde feb-2026), con cobertura de referencias
comparable a WoS/Scopus. Elegiste el peor formato de entrada y luego construiste media
arquitectura para tapar el agujero que ese formato abre. → **Rediseño: la fuente primaria es
OpenAlex; BibTeX pasa a `Source` secundaria. El `Enricher` deja de ser estructural.**

### 2. Co-citación es la peor colina, y es justo la más cara
La metodología consagra co-citación como red insignia. Pero co-citación mide estructura
*histórica*, sesgada a documentos viejos muy citados, lenta para frentes nuevos. Y es la
única de las cuatro redes que **necesita el enricher**. La alternativa —**bibliographic
coupling**— mira hacia adelante, usa las refs de los propios documentos semilla (que OpenAlex
ya trae) y **no necesita enricher**; ni siquiera está en la lista de cuatro redes. Tenés la
red más cara y más cuestionada como flagship, y la más barata y defendible ausente.
→ **Rediseño: coupling y citación directa como ciudadanos de primera; co-citación, una más.**

### 3. ¿Para quién? El usuario declarado no es el usuario que se quiere enseñar
El PRD apunta a "Python 3.12+, cómodo con CLI, no usuario final". Pero el objetivo declarado
ahora es **"fácil de usar para enseñárselo a otros"**. Esos dos no son el mismo usuario. El
que enseñás no quiere construir un `Corpus` a mano ni elegir entre `ParquetStore` y
`DuckDBStore`; quiere "de esta búsqueda a este mapa". La comunidad real de co-citación usa
GUIs (biblioshiny, VOSviewer). → **Rediseño: definir el "primer flujo de 10 minutos" como
contrato de diseño, no como tutorial posterior. La superficie por defecto debe ser diminuta.**

### 4. Exportás GraphML = admitís que el insight lo generan otros
La salida es "GraphML para Gephi/Cytoscape" y la visualización está fuera de alcance.
`bib2graph` es **el medio aburrido** de un pipeline cuyos dos extremos (datos: OpenAlex; viz:
VOSviewer/Gephi) son de terceros maduros y mejores. → **Rediseño: o se aporta algo en el
último kilómetro (aunque sea un layout/clustering opinado y reproducible), o se asume
explícitamente el rol de "backend" y se hace que ese rol sea excelente y agente-native — no
ambas cosas a medias.**

### 5. El "validador" se filtra dentro del producto "genérico"
"El estudio de semiconductores es el validador, no el producto" — pero el informe de calidad
hardcodea los umbrales de *ese* estudio (≥200 docs, ≥90% DOI, 5 países, ≥10 autores) como si
fueran universales. O la herramienta es genérica (y esos números son arbitrarios) o es el
estudio. → **Rediseño: los umbrales son configuración del usuario, no del núcleo. La
metodología de semiconductores es un *ejemplo*, no un default del producto.**

### 6. El agente-native está tratado como adorno futuro, no como columna
ARQUITECTURA §6.3 tiene las intuiciones correctas (`--json`, exit codes, sin estado) pero las
posterga a "v0.3+, si la demanda lo justifica". Si el flujo con agentes es un objetivo
declarado, **es una columna del diseño, no un extra**. Hoy existen principios maduros de CLI
agente-native (doble salida, errores accionables, eficiencia de tokens, auto-documentación;
ver [`referentes.md`](referentes.md) §4) que deberían moldear la API desde el primer comando.
→ **Rediseño: la CLI agente-native es superficie primaria, diseñada con esos principios desde
el hito 1.**

### 7. La elegancia interna ocupa el lugar de la propuesta de valor
El ADR 0006 (tabla Arrow vs 4 dicts, wrapper Pydantic, NetworkSpec, snapshot inmutable) es
buena ingeniería **con cero consecuencia visible para el usuario**, y ocupa protagonismo
documental. La reproducibilidad local (schema_version, corpus_hash, DVC) resuelve una parte
chica de un problema cuyo grueso vive en la **capa de datos** (WoS/Scopus mutan y son pagas;
OpenAlex ya publica snapshots versionados). → **Rediseño: invertir el presupuesto de diseño
hacia lo que el usuario toca (el primer flujo, la CLI, las redes correctas) y dejar la
representación interna como detalle de implementación, no como north star.**

### 8. Sostenibilidad: un rewrite solitario contra el patrón de muerte del nicho
`tethne` muerto, `metaknowledge` muerto, y este tipo de OSS académico muere cuando su autor
se va. Enfrente: bibliometrix (instituto + libro + comunidad), VOSviewer (CWTS Leiden). Y en
2026 ya entraron pyBiblioNet y Biblium al mismo nicho. → **Rediseño: el plan de
sostenibilidad (alcance chico mantenible, datos abiertos sin dependencias frágiles, valor que
no requiere un equipo) es parte del diseño, no un detalle posterior.**

## Qué sobrevive (no todo es escombro)

- **Núcleo puro y testeable** sobre datos en memoria: correcto, se conserva.
- **Costuras tipadas** (`Source`/`Enricher`/`Store`): el patrón es bueno; cambia *cuál* es la
  implementación de referencia (OpenAlex, no BibTeX+S2).
- **Reproducibilidad + scriptabilidad**: genuinamente lo que las GUIs hacen mal — pero solo
  vale si la **fuente** también es reproducible (otra vez: OpenAlex, no WoS/BibTeX).
- **Intuición agente-native**: correcta; hay que ascenderla de "futuro" a "columna".

## El rediseño en una frase

De *"librería que convierte BibTeX en redes, con co-citación como flagship y Neo4j exorcizado,
todo para no repetir v0"* a *"herramienta agente-native y enseñable que va de una consulta
OpenAlex a redes bibliométricas reproducibles (coupling/citación directa de primera), con una
superficie diminuta por defecto"*. Validar este giro con el Product Owner antes de tocar
[`PRD.md`](../PRD.md) y [`ARCHITECTURE.md`](../ARCHITECTURE.md); registrar la decisión "BibTeX vs
OpenAlex como entrada de referencia" y "agente-native como columna" como ADRs nuevos.

## Referencias

Ver [`referentes.md`](referentes.md) §6 (mantenimiento de metaknowledge, OpenAlex, principios
de CLIs agente-native, entrantes 2026).
