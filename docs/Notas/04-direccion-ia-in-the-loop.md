# 04 — Dirección "IA in the loop": sustrato de investigación + máquina de tensiones

> **Nota en evolución.** Captura un giro de categoría del proyecto, todavía sin decidir: de
> "librería que convierte corpus en redes" a "sustrato de investigación que el humano cura y
> sobre el que la IA interviene en puntos puntuales". Incluye una revisión de referentes del
> **nuevo cluster** (asistentes de investigación con IA), que es distinto del cluster
> bibliométrico de [`../referentes.md`](../referentes.md). No es diseño congelado: es material
> para pensar. Fecha: 2026-06-14.
>
> ⚠️ **ESTADO HISTÓRICO — superado en parte por ADR
> [0022](../decisiones/0022-producto-sin-ia-generativa.md) (2026-06-15).** Esta nota es la **base de
> la "máquina de tensiones"** (la *Inserción 2* de IA). Tras el red-team del AS-BUILT
> ([Nota 06](06-critica-as-built-v0.2.md)) el PO **bloqueó que el producto NO usa IA generativa**: la
> **máquina de tensiones / sensemaking asistido por IA se ABANDONA** (no se difiere a v2: se retira
> del producto), y la *Inserción 1* (forrajeo) se reencuadra como **asistencia bibliométrica
> determinista, sin IA**. El sensemaking de tensiones lo hace el **humano leyendo las redes**. Se
> conserva el contenido como **historia del proceso** (de dónde vino el giro), **no como diseño
> vigente**. El "AI-in-the-loop" que queda es **solo el del desarrollo** (ver
> [`../../AI_DISCLOSURE.md`](../../AI_DISCLOSURE.md)). El diseño vigente está en
> [`../ARCHITECTURE.md`](../ARCHITECTURE.md) y los ADR 0022/0023.

## 1. El giro, en una frase

bib2graph deja de ser un *pipeline* (corpus → redes → GraphML) y pasa a ser un **sustrato**:
una **biblioteca viva y curada** de literatura, organizada por las *ideas/tensiones* sobre las
que se quiere escribir, donde la **estructura bibliométrica es el contexto** que hace que la
intervención de IA sea buena, y donde la IA entra en **pasos puntuales de un ciclo de
investigación que es humano de punta a punta**.

## 2. La inversión central: "IA in the loop, NOT human in the loop"

- *Human-in-the-loop* (convencional): la IA maneja, el humano supervisa/aprueba.
- **Lo que queremos**: el **loop es del humano** y siempre estuvo ahí (leer, anotar, conectar,
  escribir); la **IA es un invitado** que se inserta en 1–2 pasos puntuales.

Consecuencia de diseño dura: **no se construye un agente autónomo que investiga.** Se
construye algo que respeta el ciclo humano existente y mete IA quirúrgicamente. La pregunta de
diseño nº1 no es "qué puede hacer el agente" sino:

> **¿Cuál es el ciclo de investigación humano, y cuáles son los 1–2 puntos exactos donde la IA
> interviene?** Si no se pueden nombrar, "IA in the loop" es un eslogan.

## 3. Las tres piezas del valor

1. **Biblioteca viva y curada** — no un export de una corrida, sino una colección que se va
   puliendo, organizada por temas/tensiones para los que se quiere desarrollar papers. El
   "manejo de archivos/PDFs" es el **artefacto central**, no plomería.
2. **Máquina de citación / de tensiones** — a partir de *mis ideas*, no solo traer papers
   relevantes (eso ya lo hace cualquier RAG) sino mapear **las tensiones**: quién apoya, quién
   refuta, qué escuelas chocan. Es lo difícil y lo valioso.
3. **Bibliometría como ingeniería de contexto** — hay muchos tipos de bibliometría porque cada
   uno revela una estructura distinta (co-citación, coupling, citación directa, co-word, main
   path…). Esa estructura es **mejor contexto para la IA** que la similitud plana de
   embeddings. Ahí conecta todo: el grafo no es el producto, es el **sustrato de retrieval**.

## 4. Esto cambia contra quién competimos

El proyecto se movió de "tools bibliométricos" (metaknowledge/bibliometrix) hacia
**asistentes de investigación con IA**. Revisión del nuevo cluster, por capas:

### 4.1 Capa de descubrimiento por grafo (SaaS, cerrados o free)
| Tool | Qué hace | Acceso / dato |
|---|---|---|
| **ResearchRabbit** | viz interactiva de redes de citación/coautoría desde una *colección* semilla; notas | Gratis, sin API pública; datos MAG/S2 |
| **Connected Papers** | mapa "one-shot" desde **un** paper semilla; grafo de *similitud* (no citación) | Freemium, sin API abierta |
| **Litmaps** | mapa citación×fecha, **monitor** semanal de papers nuevos | Freemium; datos Crossref/S2/**OpenAlex** |
| **Inciteful / Citation Gecko** | citation chasing | Free |
| **Citation-Constellation** (arXiv 2026) | descomposición de redes de citación, **open-source, no-code, auditable** | OSS — referente abierto |

### 4.2 Capa de tensiones / intención de cita (lo difícil)
| Tool | Qué hace | Acceso |
|---|---|---|
| **Scite.ai** | "Smart Citations": clasifica cada cita en **supporting / contrasting / mentioning** con la frase en contexto (deep learning) | **SaaS cerrado**, API paga. *El referente directo de la máquina de tensiones.* |
| **ContraCrow** (FutureHouse) | extrae claims de un paper y **detecta contradicciones** en la literatura vía LLM | **Open-source** |
| **SemanticCite / CiteVerifier** (arXiv 2025-26) | verificación de citas full-text, clasificación Supported/Partially/Unsupported/Uncertain | Investigación / OSS |

### 4.3 Capa de asistente/agente sobre papers
| Tool | Qué hace | Acceso |
|---|---|---|
| **Elicit** | extrae y sintetiza datos de ≤500 papers en una matriz; usa GPT+Claude | SaaS, freemium |
| **Consensus** | búsqueda en lenguaje natural → respuesta con citas (claims) | SaaS |
| **Undermind** | agente de *deep search* iterativo (semántico+keyword+citación) | SaaS |
| **PaperQA2 / Aviary** (FutureHouse) | **RAG agéntico open-source** sobre literatura; "superhuman synthesis" | **Open-source** — el referente abierto más cercano a la visión |

**Backbone de datos** de casi todos: Semantic Scholar (200M+) y/o OpenAlex.

## 5. Dónde está el valor (honesto)

- **Encontrar papers relevantes** está resuelto (RAG, S2, OpenAlex, ResearchRabbit). No es el
  hueco.
- **Las tensiones** (apoyo/refutación/escuelas en conflicto alrededor de una idea) es lo que
  **no** está resuelto bien y es genuinamente valioso. Scite lo hace cerrado y caro;
  ContraCrow/SemanticCite lo abordan en investigación. **Esa es la candidata a moat.**
- **El diferenciador frente a TODOS los SaaS (Scite, Elicit, ResearchRabbit, Undermind):**
  son **cajas negras cerradas**. La propuesta es un **sustrato abierto, que el investigador
  posee y cura**, donde la **estructura bibliométrica es de primera clase** y la **IA entra
  donde el humano decide**. Frente a los abiertos (PaperQA2, Citation-Constellation): ellos no
  tratan la **biblioteca curada longeva + las N bibliometrías como contexto** como columna.

Frase de posicionamiento candidata (a validar):
> *"La biblioteca de investigación abierta y curada por vos, donde la estructura de citación
> es el contexto y la IA entra en los puntos que elegís — para encontrar no solo los papers,
> sino las tensiones alrededor de tus ideas."*

## 6. Tensiones de diseño que este giro abre (sin resolver)

1. **Scope vs. supervivencia.** La visión explota el alcance (biblioteca + PDFs + tensiones +
   RAG + N bibliometrías). El antídoto: **el wedge más chico que entregue "las tensiones
   alrededor de mi idea"** y nada más, primero.
2. **Biblioteca viva vs. snapshot inmutable.** La visión quiere un corpus *que se cura en el
   tiempo* (stateful, longevo); el diseño actual ([`../ARCHITECTURE.md`](../ARCHITECTURE.md)
   §6.2) quiere *snapshots inmutables por corrida, sin estado*. **Incompatibles** — reconciliar
   a nivel modelo de datos.
3. **Construir vs. integrar la capa de tensiones.** ¿Se implementa detección de intención de
   cita (caro, frontera de investigación) o se integra (Scite API paga / ContraCrow OSS)? Define
   cuánto del moat es propio.
4. **OpenAlex vs. Semantic Scholar como backbone** (S2 tiene mejor señal de citas/contextos;
   OpenAlex es más abierto). Hereda el debate de [`../critica-base.md`](critica-base.md) §1.

## 7. Próximo paso recomendado

**Nombrar el ciclo de investigación humano y el punto de inserción de IA** antes de elegir
wedge o tocar [`../PRD.md`](../PRD.md). Sin el loop nombrado, todo lo demás flota.

## 8. Referencias

- Scite — [scite.ai](https://scite.ai/) ·
  [paper QSS (MIT Press)](https://direct.mit.edu/qss/article/2/3/882/102990/)
- ResearchRabbit / Connected Papers / Litmaps —
  [comparación (Aaron Tay)](http://musingsaboutlibrarianship.blogspot.com/2024/06/all-about-citation-chasing-and-tools.html) ·
  [HKUST LibGuide](https://libguides.hkust.edu.hk/citation-chaining/citation-mapping-tools-comparison)
- Citation-Constellation (OSS) — [arXiv 2603.24216](https://arxiv.org/pdf/2603.24216)
- Elicit — [reseña PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10089336/) ·
  Consensus — [deep dive (Aaron Tay)](https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises)
- PaperQA2 / "superhuman synthesis" (FutureHouse, OSS) — [arXiv 2409.13740](https://arxiv.org/pdf/2409.13740)
- ContraCrow / detección de contradicciones — (ecosistema FutureHouse/PaperQA)
- SemanticCite — [arXiv 2511.16198](https://arxiv.org/abs/2511.16198) ·
  citation integrity NLP — [Bioinformatics 2024](https://academic.oup.com/bioinformatics/article/40/7/btae420/7699794)
