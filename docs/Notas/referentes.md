# Referentes y oportunidades — mapa del campo

> Investigación de referentes para situar a `bib2graph` en el ecosistema real de
> herramientas bibliométricas. No se diseña en vacío: el objetivo es **encontrar el hueco**
> que justifique construir algo nuevo en vez de usar lo que ya existe.
> Fecha: 2026-06-14. Documento hermano: [`critica-base.md`](critica-base.md) (destrucción del
> concepto actual). Datos de mantenimiento verificados en PyPI/GitHub (ver §6).

## 1. Las tres preguntas que guían el mapa

El producto que se quiere construir tiene tres restricciones que **filtran** a los referentes:

1. **Fácil de usar y de enseñar.** El criterio de éxito no es "tiene más features", es "puedo
   sentar a alguien y que en una tarde haga su primer análisis". Esto descarta a buena parte
   del Tier-Python (notebooks crudos) y favorece flujos guiados.
2. **Pensada para flujo de trabajo con agentes** (CLI idiomática para LLM/agentes). Casi
   ningún referente bibliométrico nace agente-native; los que existen son CLIs genéricas que
   *resultan* agente-amigables, no diseñadas para eso (ver §4).
3. **Sostenible sobre datos abiertos.** El referente más parecido al objetivo
   (`metaknowledge`) está **abandonado** (§2). Construir sobre fuentes pagas (WoS/Scopus)
   ata el proyecto a un sesgo de acceso; OpenAlex cambia esa ecuación (§3).

## 2. Tier 2 — la competencia directa (Python → redes)

Estas son las herramientas con las que `bib2graph` se solapa **funcionalmente**: Python, leen
registros bibliográficos, construyen redes (co-citación / co-autoría / co-word).

| Herramienta | Estado mantenimiento | Fuentes | Redes / salida | Hueco / debilidad |
|---|---|---|---|---|
| **metaknowledge** (UWNETLAB) | ⚠️ **Abandonado**: última release 3.4.1 **nov-2020**, último commit **feb-2022** (~4 años) | WoS, Scopus, PubMed, Proquest, NSF | co-citación/co-autoría/co-word → networkx, export Gephi | El más parecido al objetivo, **pero muerto**. networkx-céntrico, sin GUI, sin OpenAlex, sin diseño para agentes. **Esta es la vacante a ocupar.** |
| **litstudy** (NLeSC) | ✅ Activo | Scopus, S2, CrossRef, arXiv (OpenAlex parcial) | redes + topic modeling, en Jupyter | Pensado para *literature reviews* en notebook, no para producir redes reproducibles vía CLI. No agente-native. |
| **pyBibX** (Valdecy) | ✅ Activo (2023+) | Scopus, WoS, PubMed | EDA + redes citación/colaboración/similitud + NLP/LLM (BERTopic, ChatGPT) | All-in-one con IA, pero **pesado** y orientado a output visual/EDA; curva de entrada alta, no "fácil de enseñar". |
| **pySciSci** (SciSciCollective) | ✅ Activo | MAG/OpenAlex, WoS, Dimensions | métricas science-of-science sobre pandas en RAM | Orientado a *science of science* a gran escala, no a estudios de campo guiados. |
| **ScientoPy** (jpruiz84) | ✅ Activo | WoS, Scopus | tendencias/temporal, preproc multi-core | Foco en análisis temporal/tendencias, no en redes. |
| **pyBiblioNet** (arXiv ene-2026) | 🆕 Muy reciente | — | análisis bibliométrico **basado en redes** en Python | **Señal de alarma**: alguien acaba de publicar justo "redes bibliométricas en Python". El nicho se está llenando. |
| **Biblium** (2026) | 🆕 Reciente | multi-DB | análisis comparativo bibliométrico | Otro entrante 2026. |
| **tethne** (ASU) | ❌ Muerto | WoS, etc. | networkx | Precedente de cómo muere este tipo de OSS de nicho. |

**Lectura:** el espacio "redes bibliométricas en Python" tiene **un cadáver bien posicionado
(metaknowledge)** y **dos entrantes 2026** (pyBiblioNet, Biblium). El hueco no es "otra
librería de redes" — eso ya está saturándose. El hueco es **el ángulo de uso**: facilidad de
enseñanza + agente-native + datos abiertos, que ninguno cubre junto.

## 3. Tier 1 — los que dominan (GUI, no-programadores) y la capa de datos

- **bibliometrix / biblioshiny** (R): el estándar. WoS/Scopus/Dimensions/Lens/PubMed/OpenAlex,
  todo el análisis + GUI Shiny sin código. Paper citable, libro, comunidad. **No se le gana
  por features ni por comunidad.**
- **VOSviewer** (Java, CWTS Leiden): estándar de *visualización* (clustering, density maps
  publicables). Lee exports y consulta Crossref/OpenAlex/S2/Lens por API. Es el "último
  kilómetro" al que cualquier herramienta termina exportando GraphML.
- **CiteSpace / SciMAT / CitNetExplorer / Sci2 / Gephi / Pajek**: análisis temporal, evolución
  temática, viz general.

**Capa de datos — el cambio de régimen:**

- **OpenAlex** (OurResearch, desde 2022): ~250M works, CC0, **gratis**, con referencias y citas
  incluidas. Cobertura de referencias **comparable a WoS/Scopus** en datasets recientes
  (Scientometrics 2025). Desde **13-feb-2026** requiere API key, pero la key es **gratis**.
- **pyalex** / **openalexR**: wrappers finos de la API.
- Consecuencia: la razón de existir del `Enricher` de Semantic Scholar (traer referencias que
  el BibTeX no tiene) **se evapora** si la fuente primaria es OpenAlex. Ver
  [`critica-base.md`](critica-base.md) §1.

## 4. El ángulo agente-native (lo que casi nadie hace)

Ningún referente bibliométrico está diseñado para agentes. Pero ya hay principios establecidos
para CLIs agente-native (Linearis, Memori, discusiones HN 2025-2026):

- **Doble salida**: humano por defecto, `--json` estructurado y versionado para máquina.
- **Eficiencia de tokens**: flags `--raw`/`--compact` (menos contexto consumido por llamada).
- **Errores como señales de ruta, no de stop**: el error dice qué pasó, por qué y **qué hacer
  en cambio** (exit codes claros y accionables).
- **Auto-documentación**: un comando que vuelca el esquema completo de uso al contexto del
  agente.
- **Sin estado entre invocaciones**: cada llamada independiente y reproducible.

`bib2graph` ya tiene intuiciones de esto (ARQUITECTURA §6.3: `--json`, exit codes, sin
estado). El diferencial real sería **tratar esto como requisito de primera clase desde el
día uno**, no como "trabajo futuro v0.3+". Es, junto con OpenAlex + facilidad de enseñanza,
el eje donde no hay competencia ocupando el lugar.

## 5. Síntesis — dónde está el hueco

Cruzando las tres preguntas de §1 contra el mapa:

- **Contra metaknowledge**: ocupar su vacante (redes networkx en Python) **pero vivo, sobre
  datos abiertos y enseñable**.
- **Contra bibliometrix/VOSviewer**: no competir en features ni en GUI; competir en
  **reproducibilidad scriptable + integración con agentes** (lo que las GUIs hacen mal).
- **Contra litstudy/pyBibX**: no ser otro notebook todo-en-uno; ser una **herramienta con
  una superficie chica, fácil de enseñar**, que un agente pueda orquestar.

Frase de posicionamiento candidata (a validar):
> *"El backend reproducible y agente-native para bibliometría sobre datos abiertos
> (OpenAlex), tan simple que se enseña en una tarde."*

Eso **no lo ocupa nadie limpio hoy**. Lo que sí hay que aceptar: implica mover el centro de
gravedad de BibTeX→S2→co-citación hacia OpenAlex→coupling/citación-directa, y de
"librería+CLI" hacia "CLI agente-native como frontera primaria". Ese rediseño se argumenta en
[`critica-base.md`](critica-base.md).

## 6. Referencias

- metaknowledge — [GitHub](https://github.com/UWNETLAB/metaknowledge) ·
  [releases](https://github.com/UWNETLAB/metaknowledge/releases) (3.4.1, nov-2020) ·
  [PyPI](https://pypi.org/project/metaknowledge/) · [docs](https://metaknowledge.readthedocs.io/)
- litstudy — [GitHub](https://github.com/NLeSC/litstudy) · [docs](https://nlesc.github.io/litstudy/)
- pyBibX — [GitHub](https://github.com/Valdecy/pybibx) · [arXiv 2304.14516](https://arxiv.org/abs/2304.14516)
- pySciSci — [GitHub](https://github.com/SciSciCollective/pyscisci)
- ScientoPy — [GitHub](https://github.com/jpruiz84/ScientoPy)
- pyBiblioNet — [arXiv 2601.16990](https://arxiv.org/pdf/2601.16990) (ene-2026)
- Biblium — [Research Square](https://www.researchsquare.com/article/rs-8633785/v1)
- bibliometrix — [sitio](https://www.bibliometrix.org/) · [GitHub](https://github.com/massimoaria/bibliometrix)
- OpenAlex — [Wikipedia](https://en.wikipedia.org/wiki/OpenAlex) ·
  [cobertura de referencias vs WoS/Scopus (Scientometrics 2025)](https://link.springer.com/article/10.1007/s11192-025-05293-3)
- pyalex — [GitHub](https://github.com/J535D165/pyalex) · openalexR — [docs](https://docs.ropensci.org/openalexR/)
- CLIs agente-native — [Principles for agent-native CLIs (HN)](https://news.ycombinator.com/item?id=48052333) ·
  [Designing CLI Tools for AI Agents (Memori)](https://archit15singh.github.io/posts/2026-02-28-designing-cli-tools-for-ai-agents/) ·
  [Rethinking CLI interfaces for AI](https://www.notcheckmark.com/2025/07/rethinking-cli-interfaces-for-ai/)
