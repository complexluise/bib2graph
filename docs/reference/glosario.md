---
title: Glosario
---

# Glosario

Términos y conceptos clave que aparecen en bib2graph, la metodología bibliométrica y la investigación del estado del arte.

---

## A

### Acoplamiento bibliográfico

Medida de similitud entre dos papers basada en las referencias que comparten. Dos papers están acoplados si citan las mismas fuentes. Cuantas más referencias compartan, más fuerte es el acoplamiento.

**En bib2graph:** La red de **acoplamiento bibliográfico** es la proyección principal — agrupa papers en comunidades basadas en sus referencias compartidas. Es útil para identificar sub-temas y tendencias.

**Ejemplo:** Paper A cita [Ref1, Ref2, Ref3]. Paper B cita [Ref2, Ref3, Ref4]. Acoplamiento: comparten 2 referencias, acoplamiento fuerte → aparecen cerca en la red.

---

### Asistente de IA

Un chat de IA con ejecución de código (Claude, ChatGPT, MiniMax, o similar) al que le pides que instale y opere bib2graph por ti. No es parte del motor de bib2graph —que no usa IA generativa, ver [IA en el desarrollo](../ai-disclosure.md)— sino la interfaz conversacional que usa un humano no técnico para dirigir el CLI, sin escribir código ni abrir una terminal.

**En bib2graph:** el asistente ejecuta los mismos comandos `b2g` que correrías a mano; la diferencia es que los corre dentro de su propio entorno de ejecución (no en tu máquina), a tu pedido. Ver [Tutorial: Tu primer mapa de investigación](../tutoriales/primer-mapa.md).

---

## B

### Backward chaining

Ver **forrajeo**.

### Benchmark

Conjunto de datos estándar usado para evaluar y comparar algoritmos. Un benchmark típicamente incluye inputs, outputs esperados y métricas de evaluación.

**En bib2graph:** No usamos benchmarks para construir redes (nuestro ranking es determinista), pero sí los papers usan benchmarks para validar retrieval, clustering, etc.

---

## C

### Candidate

Estado de un paper en la curación PRISMA. Papers candidatos son aquellos cuya inclusión es incierta — típicamente porque no tienen acceso al texto completo, o porque su relevancia es media.

**En bib2graph:** En `b2g curate`, un paper puede ser `ACCEPTED`, `REJECTED`, o `CANDIDATE`. Los candidatos quedan en el corpus pero marcados, para revisión posterior.

**Cuándo marcar candidato:**
- Texto completo no disponible (paywall)
- Métodos vagos o especulativos
- Relevancia media pero podría aportar perspectiva

---

### Clustering

Proceso de agrupar elementos similares sin etiquetar. En bib2graph, usamos **Louvain clustering** para detectar comunidades en redes.

**En bib2graph:** Después de construir una red (acoplamiento, co-citación, etc.), ejecutamos Louvain para encontrar comunidades — grupos de papers/autores densamente conectados.

**Parámetro importante:** `resolution` (default 1.0). Resolución más alta = más comunidades, más finas. Resolución más baja = menos comunidades, más grandes.

---

### Co-autoría

Red que conecta autores que escriben papers juntos. Un edge existe si dos autores co-autorizan un paper.

**En bib2graph:** `b2g build` crea una red de co-autoría. Útil para identificar equipos, laboratorios y colaboraciones persistentes.

---

### Co-citación

Dos papers se co-citan si aparecen juntos en las referencias de otros papers. Si Paper A y Paper B se citan mutuamente, o si ambos aparecen en las referencias de muchos otros papers, su co-citación es alta.

**En bib2graph:** La red de **co-citación** proyecta papers que son frecuentemente citados juntos. Identifica papers influyentes y trabajos canónicos (clásicos del campo).

**Diferencia vs. Acoplamiento:**
- **Acoplamiento:** Basado en referencias que comparten (enfoque hacia atrás).
- **Co-citación:** Basado en quién los cita juntos (enfoque hacia atrás, pero a nivel de influencia).

---

### Corpus

Colección de papers (o documentos) que forman la base del análisis. En bib2graph, el corpus es persistente — crece con `b2g seed` y `b2g chain`, se filtra con `b2g curate`.

**En bib2graph:** El corpus vive en `.duckdb` (DuckDB, base de datos local). Cada corpus tiene un `corpus_hash` (hash de contenido) que permite reproducibilidad.

---

### Curación PRISMA

Metodología de 4 fases para decidir qué papers incluir en una síntesis de literatura. Las fases son: Identificación, Cribado, Elegibilidad, Inclusión.

**En bib2graph:** `b2g curate` implementa el flujo PRISMA. Ver [Guía: Curación PRISMA paso a paso](../guias/curacion-prisma.md).

---

## D

### DuckDB

Base de datos SQL incrustada (embedded), sin servidor. bib2graph usa DuckDB para almacenar el corpus persistentemente.

**En bib2graph:** Cada workspace tiene un archivo `.duckdb` que contiene todas las tablas del corpus (papers, referencias, decisiones de curación, etc.). DuckDB permite queries SQL rápidas sin instalar un servidor PostgreSQL.

---

## E

### Ecuación de búsqueda

Consulta booleana que especifica qué papers traer desde OpenAlex. Usa estructura `(concepto_A) AND (concepto_B) AND (concepto_C)`.

**En bib2graph:** `b2g seed "[ecuacion_aqui]"` trae papers desde OpenAlex usando tu ecuación.

**Ejemplo:**
```
(information retrieval OR IR OR search)
AND (multilingual OR cross-lingual)
AND (method OR approach OR framework)
```

Ver [Guía: Cómo armar una ecuación de búsqueda](../guias/ecuacion-busqueda.md).

---

### Embedding

Representación numérica densa (vector) de una palabra, documento o concepto. Embeddings capturan significado semántico — palabras con significado similar tienen embeddings cercanos en el espacio vectorial.

**En bib2graph:** No usamos embeddings para ranking (nuestro scent es bibliométrico puro). Pero muchos papers en el corpus usan embeddings para retrieval.

---

## F

### Forrajeo

Expansión del corpus mediante **backward chaining**: buscar papers que NO aparecieron en la búsqueda inicial, pero que son citados por los papers que sí encontraste.

**En bib2graph:** `b2g chain` ejecuta forrajeo. Aumenta sensibilidad (no pierdes papers clave) sin agregar ruido sistemático.

**Cuándo hacer forrajeo:** Tema muy específico, corpus inicial pequeño, búsqueda máxima cobertura.

Ver [Guía: ¿Expando el corpus?](../guias/forrajeo.md).

---

## G

### Grado

En una red, el número de conexiones que tiene un nodo. Un paper con grado alto está altamente acoplado (acoplamiento) o frecuentemente co-citado (co-citación).

**En bib2graph:** Papers de mayor grado son centrales en la red — son buenos candidatos para "papers seminales" de una comunidad.

---

## H

### Hub

En una red, un nodo con grado muy alto — actúa como nexo central. En co-citación, un hub es un paper que la mayoría cita (un "clásico").

---

## I

### Identificación (fase PRISMA)

Primera fase de curación PRISMA. Aquí marcas duplicados, retracciones, papers en idioma incorrecto como REJECTED sin revisar más.

Ver [Guía: Curación PRISMA paso a paso](../guias/curacion-prisma.md).

---

## L

### Louvain

Algoritmo de clustering que detecta comunidades en redes minimizando modularidad. Es probabilístico — diferentes ejecuciones pueden dar resultados levemente diferentes.

**En bib2graph:** `b2g build` usa Louvain con `resolution=1.0` (default). Puedes cambiar resolución en YAML specs: `resolution: 0.5` → comunidades más grandes; `resolution: 2.0` → comunidades más pequeñas.

---

## M

### Maturity (bloque JSON)

Campo en la salida `--json` de `b2g build`, `b2g snapshot create`, `b2g read top` que autodeclara la madurez del resultado. Indica que el reporte es un borrador sin pulir.

**Valores:** `{curated, scope, saturated, empty_networks}` — si tienes datos incompletos, bib2graph lo advierte.

---

## N

### NetworkSpec

Especificación YAML declarativa de cómo construir redes. Define qué red (acoplamiento, co-citación, etc.), qué clustering usar, y qué resolución.

**En bib2graph:** 
```yaml
networks:
  - kind: bibliographic_coupling
    clustering: louvain
    resolution: 1.0
```

`b2g build --spec networks.yaml` carga la spec y construye.

---

## O

### OpenAlex

Base de datos abierta de papers, autores, revistas, citas. API gratuita sin API key requerida (pero funcionamiento limitado sin key).

**En bib2graph:** `b2g seed` trae papers desde OpenAlex usando tu ecuación de búsqueda.

---

## P

### PRISMA

Metodología de 4 fases para síntesis sistemática de literatura: **Identificación → Cribado → Elegibilidad → Inclusión**. Cada fase tiene criterios explícitos de aceptación/rechazo.

**En bib2graph:** `b2g curate` implementa el flujo PRISMA. Requiere que documentes criterios de decisión.

Ver [Guía: Curación PRISMA paso a paso](../guias/curacion-prisma.md).

---

## R

### Reproducibilidad

Capacidad de reproducir exactamente el mismo resultado (corpus, redes, comunidades) desde los mismos inputs, sin variabilidad.

**En bib2graph:** Reproducibilidad es un principio central. Mismo corpus → mismo `corpus_hash` → mismas redes → mismas comunidades (Louvain con seed determinístico).

---

### Resolución (Louvain)

Parámetro del algoritmo Louvain que controla el tamaño de las comunidades detectadas. Resolución alta → comunidades más pequeñas y numerosas. Resolución baja → comunidades más grandes y menos numerosas.

**Default en bib2graph:** `resolution: 1.0` (balance).

---

## S

### Scent bibliométrico

Ranking determinístico sin IA que usa estructura bibliométrica (acoplamiento, co-citación, centralidad) para rankear candidatos en forrajeo.

**En bib2graph:** Cuando haces `b2g chain`, los candidatos se rankean por scent (no por LLM ni embeddings). Es reproducible y explicable.

---

### Seed

Acción de sembrar el corpus inicial desde una ecuación de búsqueda. `b2g seed "[ecuacion]"` trae papers desde OpenAlex.

**Estados del corpus:** SEEDED → CHAINED → FILTERED → BUILT → (SNAPSHOT/EXPORTED).

---

### Snapshot

Captura congelada del corpus en un momento. `b2g snapshot create` guarda el estado actual; `b2g snapshot restore` rehidrata desde un snapshot anterior.

**En bib2graph:** Útil para reproducibilidad — si necesitas volver a un corpus anterior, restaura desde snapshot.

---

## T

### TF-IDF

**Term Frequency-Inverse Document Frequency.** Métrica de ranking que pondera términos raros en el corpus (raros = más informativos) vs. frecuentes (frecuentes = menos informativos).

**En bib2graph:** No lo usamos en el core (nuestro ranking es bibliométrico). Pero muchos papers históricos en el corpus usan TF-IDF para retrieval.

---

## W

### Workspace

Carpeta de investigación que contiene un corpus, sus redes, snapshots y exports. Un workspace = una investigación.

**En bib2graph:** `b2g init ./mi-sota` crea un workspace. Dentro vive:
- `workspace.json` (metadata)
- `library.duckdb` (corpus)
- `networks/` (redes exportadas)
- `snapshots/` (snapshots)
- `exports/` (GraphML, CSV, etc.)

---

## Y

### YAML (Yet Another Markup Language)

Formato de configuración legible. bib2graph usa YAML para specs de redes y ecuaciones.

**En bib2graph:**
```yaml
networks:
  - kind: bibliographic_coupling
    clustering: louvain
    resolution: 1.0
```

---

## Z

### Zotero

Gestor de referencias de código abierto. No está integrado en bib2graph hoy, pero es un candidato para futuras integraciones (flujo: Zotero → bib2graph).

---

## Siglas comunes

| Sigla | Significado | En bib2graph |
|-------|-----------|---|
| API | Application Programming Interface | `bib2graph` es una librería Python (API) + CLI |
| CLI | Command Line Interface | `b2g` — interfaz de línea de comandos |
| CSV | Comma-Separated Values | Formato de curación: `curate.csv` |
| DOI | Digital Object Identifier | Identificador único de paper |
| FSM | Finite State Machine | El ciclo de bib2graph es un FSM (SEEDED → CHAINED → FILTERED → BUILT) |
| IR | Information Retrieval | Recuperación de información |
| JSON | JavaScript Object Notation | Formato de salida: `b2g --json` |
| PRISMA | Preferred Reporting Items for Systematic Reviews and Meta-Analyses | Metodología de curación |
| SOTA | State of The Art | Estado del arte — el objetivo de bib2graph |
| SQL | Structured Query Language | Queries en DuckDB: `b2g read list` usa SQL internamente |
| YAML | YAML Ain't Markup Language | Formato de specs: `networks.yaml`, `equation.yaml` |

---

## Cómo usar este glosario

- **Alfabéticamente:** Busca el término que no entiendes.
- **Desde las guías:** Cada guía enlaza a términos relevantes.
- **Desde el CLI:** `b2g --help` menciona términos; este glosario los define.

---

## No encontraste el término?

Si hay un término en bib2graph que no está aquí, [abre un issue](https://github.com/complexluise/bib2graph/issues) o sugiere una adición.
