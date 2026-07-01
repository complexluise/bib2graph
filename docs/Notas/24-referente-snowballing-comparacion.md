# 24 — Referente: `snowballing` (JoaoFelipe) vs bib2graph

> Nota de exploración. El PO trajo https://github.com/JoaoFelipe/snowballing como
> posible "algo parecido a lo que queremos". Capturo el cotejo para no perderlo;
> lo accionable está al final.

## Qué es snowballing

Herramienta de João Felipe Pimentel (misma línea de `noWorkflow`) para acompañar
**revisiones sistemáticas con la metodología de snowballing de Wohlin (2014)**:
backward (referencias) + forward (citantes), con humano en el loop y procedencia.

- **Fuente:** scraping de **Google Scholar** (Selenium + plugin de Chrome con botones
  BibTeX/Work/Add).
- **"Base de datos":** archivos **`.py` por año** (la BD es código Python que se importa).
- **Interfaz:** **Jupyter notebooks** con widgets (pasos de snowballing, inserción de
  citas, análisis); CLI mínimo (`snowballing start|plugin|web`).
- **Modelo:** objeto `Work` con atributos configurables (perfil "default" con nombres
  propios `name`/`place1`, perfil "bibtex" con nombres estándar + `_category`/`_due`).
- **Salidas:** grafos de citación, histogramas de venue, **vista de procedencia del
  snowballing** (PROV / ProvToolBox), validación de la BD contra Scholar,
  `PDFReferencesExtractor` (refs desde PDF).
- **IA:** no usa.

## En qué se parece

El *qué* es casi idéntico: **forrajeo por citas**. Su backward/forward = nuestro
`b2g chain`. Ambos: crecen de una semilla siguiendo el grafo de citas, distinguen
sembrado de traído (`is_seed`), tienen curación humana, y cierran con procedencia +
redes de citación como salida.

## En qué difiere (y por qué confirma nuestros ADRs)

| | snowballing | bib2graph |
|---|---|---|
| Fuente | scraping Google Scholar | OpenAlex API (ADR 0007) |
| "BD" | `.py` por año | tabla Arrow + DuckDB biblioteca viva (ADR 0009) |
| Interfaz | Jupyter notebooks + plugin | CLI agente-native (Hito 6) |
| Modelo | `Work` configurable, 2 perfiles | `PaperRow` único (Pydantic) → schema Arrow |
| Determinismo | acoplado a notebook + scraping (frágil) | núcleo puro, `corpus_hash` estable |
| IA | no | no, **por diseño** (ADR 0022) |

Lectura clave: snowballing es casi un **espejo de nuestra v0** (BD-como-archivos-Python,
acoplado al notebook, scraping de Scholar). Es justo de lo que se alejó la reescritura
clean-room (`01-lecciones-v0.md`). Paga en fragilidad/no-reproducibilidad lo que nosotros
cuidamos → valida OpenAlex + núcleo puro + CLI. Encaja con la frontera motor/producto:
ellos mezclan motor + UX en el notebook; nosotros separamos.

## Qué nos puede enseñar (accionable, sin compromiso)

1. **Anclaje metodológico explícito.** Ellos dicen "snowballing de Wohlin" — método de
   SLR **citable**, con criterios de inicio/parada. Nuestro forrajeo es más rico
   (scent, redes múltiples) pero framed en lenguaje propio. Para el mensaje "antídoto al
   sesgo del related work" (#187) y el académico hispano, nombrar el linaje —
   *"snowballing de Wohlin, hecho determinista y a escala"* — baja la barrera de adopción.
   → candidato a entrar en el posicionamiento de lanzamiento.

2. **Vista de procedencia del snowballing en la GUI (#34).** Ya tenemos los datos —y más:
   `ProvenanceEvent`, `chaining_hop`, `source_tag`, `is_seed`. Ellos lo *muestran*
   ("este paper entró en la ronda 2, backward desde tal semilla"). Lectura barata para la
   GUI porque el dato ya existe.

3. **`validate` contra la fuente.** Tienen un paso de validar la BD contra Scholar. No
   tenemos un `b2g validate` que re-confronte el corpus vivo contra OpenAlex. Idea suelta.

4. **Refs desde PDF** (`PDFReferencesExtractor`). Nuestro backward depende de la cobertura
   de OpenAlex; refs-desde-PDF es un fallback que ellos tienen. Anotarlo como **límite
   conocido del backbone**, no como trabajo a hacer.

5. **Doble perfil de nombres del `Work`** — tensión "vocabulario del dominio vs del
   usuario", que resolvimos con `PaperRow` único. Confirma la elección, no la cambia.

## Síntesis

snowballing **valida la tesis** (forrajeo por citas = wedge real y publicable) y a la vez
es el **contraejemplo arquitectónico** que justifica nuestros ADRs. Lo de verdad
accionable: (1) anclaje a Wohlin para el mensaje, (2) vista de procedencia en la GUI.
El resto queda anotado como referencia/límites.
