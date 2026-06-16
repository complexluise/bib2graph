# 06 — Definición de producto V1 (historias de usuario)

> ⚠️ **ARCHIVADO (2026-06-15).** Contenido promovido a [`../PRD.md`](../PRD.md) §7 (historias y
> épicas, ya actualizadas: thesaurus C2, asortatividad D3, etc.). Se conserva por historia;
> **manda el PRD**. Ver [`README.md`](README.md) de este directorio.

> Primera definición de producto de la V1, en **historias de usuario**, para extraer features
> con facilidad y dejar claro **qué esperar**. Cierra las decisiones de
> [`04-direccion-ia-in-the-loop.md`](../Notas/04-direccion-ia-in-the-loop.md) y
> [`05-ciclo-investigacion-humano.md`](../Notas/05-ciclo-investigacion-humano.md) y las tensiones ya
> resueltas (OpenAlex backbone, política build/integrate, Zotero biblioteca viva, snapshot como
> registro de corrida). Fecha: 2026-06-14. **En evolución.**

## 1. La V1 en una línea

> **bib2graph V1** convierte una **ecuación de búsqueda** (el artefacto estándar y reproducible
> de la ciencia) en un **corpus curado** —vía OpenAlex + chaining asistido— y lo proyecta a
> **redes bibliométricas**. El final siguen siendo las redes; lo nuevo es cómo se llega a ellas.

## 2. Principio rector: fácil PERO consciente

Queremos que sea fácil, pero **esto es ciencia**. La **ecuación de búsqueda es un ciudadano de
primera clase**, explícita y registrada — no una caja negra como los asistentes IA que ocultan
la query (Elicit, Consensus). El investigador **debe ser consciente** de qué recupera y por qué;
esa consciencia *es* el ejercicio bibliotecario y es lo que hace el resultado reportable
(PRISMA / vom Brocke, ver [`05-...`](../Notas/05-ciclo-investigacion-humano.md)). Diferenciador real
frente al "magic black box".

## 3. Qué puedo esperar (y qué NO) en V1

**Esperá (in scope):**
- Sembrar con **ecuación de búsqueda** y/o **papers semilla**.
- **Chaining asistido** (backward/forward snowballing) sobre OpenAlex, rankeado por estructura.
- **Ejercicio bibliotecario**: dedup/normalización apoyada en IDs de OpenAlex, filtros de
  inclusión/exclusión con conteos trazables.
- **Redes**: co-citación, acoplamiento bibliográfico, co-autoría, co-ocurrencia de keywords,
  instituciones → métricas/comunidades → export GraphML/CSV.
- **Registro reproducible** de cada corrida.
- **CLI agente-native** (`--json`, exit codes).

**NO esperés (fuera de V1, explícito):**
- Máquina de **tensiones** (intención de cita supporting/contrasting) → **v2**.
- Lectura de **PDFs full-text** → futuro.
- **GUI / web** → fuera.
- WoS/Scopus/RIS como backbone → OpenAlex primero; el resto, `Source` futura.

## 4. Qué sobrevive del diseño original y qué cambia

- **Sobrevive el núcleo**: `Corpus` → proyectores → redes (`networkx`) → analizadores →
  exportadores. *El final siguen siendo las redes.*
- **Cambia el front**: las semillas dejan de ser "importar un BibTeX" y pasan a ser
  **ecuación de búsqueda + chaining sobre OpenAlex**. Muere el Enricher-S2 estructural y
  Neo4j-como-sustrato (ver [`../critica-base.md`](../critica-base.md)).

## 5. Historias de usuario

### Épica A — Sembrar con ecuaciones de búsqueda (consciente y estándar)
- **A1** · Como investigador, quiero definir mi corpus con una **ecuación de búsqueda**
  (términos, campos, años, idioma), para partir del artefacto estándar y reproducible — no de
  una caja negra.
- **A2** · Como investigador, quiero que la herramienta **traduzca mi ecuación a una consulta
  OpenAlex y me muestre exactamente qué se ejecutó** (y sus límites), para ser consciente de
  qué recupero.
- **A3** · Como investigador, quiero alternativamente sembrar con **papers semilla** (DOIs /
  IDs / un export / mi colección Zotero), para cuando parto de *pearls* conocidos.
- **A4** · Como investigador, quiero que mi ecuación quede **registrada y versionada** con la
  corrida, para reportarla (PRISMA / vom Brocke) y reproducirla.

### Épica B — Forrajear: chaining asistido (inserción de IA nº1)
- **B1** · Como investigador, quiero **backward chaining** (las referencias de mis semillas) y
  **forward chaining** (lo que las cita) automáticos sobre OpenAlex, para no hacer snowballing a
  mano (Wohlin).
- **B2** · Como investigador, quiero **controlar la profundidad** del chaining (1–2 saltos) y
  ver cuánto crece el corpus, para no hacerlo explotar.
- **B3** · Como investigador, quiero que los candidatos vengan **rankeados por estructura
  bibliométrica** (*information scent*: acoplamiento/co-citación, centralidad), para revisar
  primero lo más relevante y no una lista plana.
- **B4** · Como investigador, quiero un paso **opcional** de IA que me **explique por qué** un
  candidato es relevante / a qué conversación pertenece, para decidir más rápido — **sin que
  decida por mí**.

### Épica C — Ejercicio bibliotecario (curar)
- **C1** · Como investigador, quiero **dedup y normalización** de autores/instituciones apoyada
  en los IDs de OpenAlex (ORCID/ROR/DOI), para no pelear con variantes de nombres.
- **C2** · Como investigador, quiero aplicar **criterios de inclusión/exclusión** (año, tipo,
  idioma, mínimo de citas) y ver el **conteo en cada filtro**, para curar con trazabilidad
  (estilo flujo PRISMA).
- **C3** · Como investigador, quiero **aceptar/rechazar** candidatos y que lo aceptado se sume a
  mi **biblioteca Zotero**, para que mi colección viva crezca curada.

### Épica D — Proyectar a redes (el final sigue siendo las redes)
- **D1** · Como investigador, quiero proyectar el corpus a **co-citación, acoplamiento
  bibliográfico, co-autoría, co-ocurrencia de keywords e instituciones**, para analizar la
  estructura intelectual del campo.
- **D2** · Como investigador, quiero **métricas y comunidades** (densidad, centralidades,
  Louvain/propagación/voraz) sobre cada red.
- **D3** · Como investigador, quiero **exportar GraphML/CSV** para Gephi/VOSviewer y pandas.

### Épica E — Reproducibilidad y agente-native
- **E1** · Como investigador, quiero que cada corrida produzca un **registro reproducible**
  (ecuación, fecha/versión de OpenAlex, profundidad, filtros, conteos, hash), para auditar y
  reportar.
- **E2** · Como **agente/automatización**, quiero invocar cada paso por **CLI con `--json`** y
  exit codes claros, para orquestar bib2graph sin GUI.

## 6. Criterios de "V1 hecha"

- De una **ecuación de búsqueda** a un **GraphML** de al menos una red, **sin escribir código**
  y **sin servidores**.
- El **chaining** rankea candidatos por estructura, no por lista plana.
- La corrida queda **registrada y reproducible** (se puede reportar en un paper).
- Dedup/normalización funciona apoyada en OpenAlex **sin configuración manual de nombres**.
- Cada subcomando tiene `--json`.

## 7. Próximos pasos

- Convertir las decisiones en **ADRs** (`docs/decisiones/`): OpenAlex backbone, V1 =
  ejercicio bibliotecario, build/integrate, Zotero + snapshot.
- Reconciliar `../PRD.md` y `../ARCHITECTURE.md` con esta definición (tarea del **architect**).
- Pulir detalles abiertos: profundidad default del chaining; si la primera entrega incluye
  Zotero o es CLI pura; cómo se expresa la ecuación y su mapeo (y límites) a OpenAlex.
