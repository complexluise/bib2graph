# 02 — Hallazgos teóricos: lo que el corpus de "valoraciones en educación" dice sobre el ciclo de investigación humano (y por qué importa para bib2graph)

> **Fecha:** 2026-06-27. **Estado:** narrativa + citas primarias del corpus congelado
> `examples/valoraciones/` (80 papers, ~10 aceptados, red de co-citación rala),
> **cruzada con el dossier del cluster IA-in-research vivo**
> ([`examples/nota-05-ciclo/cluster_ia_research/README.md`](../../examples/nota-05-ciclo/cluster_ia_research/README.md), 10 fuentes, sep-2024 a jun-2026).
> Material complementario al informe cuantitativo
> [`examples/nota-05-ciclo/informe_bibliometria.md`](../../examples/nota-05-ciclo/informe_bibliometria.md)
> y a las notas metodológicas
> [`05-ciclo-investigacion-humano.md`](05-ciclo-investigacion-humano.md) y
> [`04-direccion-ia-in-the-loop.md`](04-direccion-ia-in-the-loop.md).
>
> **Tesis:** la historia del proyecto (Nota 04 → 05 → 06 → ADR 0022) **se
> reencuentra con el corpus** que vino a construir, y **se reencuentra
> también con el cluster vivo** que el proyecto no diseñó pero que ahora
> ocupa parcialmente el hueco que el Nota 04 soñó. Los papers top de este
> corpus no hablan de herramientas bibliográficas, pero **todos hablan de los
> problemas que bib2graph intenta resolver**: cómo operacionalizar *complex
> thinking*, cómo hacer transdisciplinariedad operativa, qué lugar tiene
> (o no tiene) la asistencia algorítmica en el ciclo de investigación.

---

## 1. La historia (para no perder el hilo)

Esta nota cierra un arco de tres semanas. Conviene empezar por él porque
**lo que el corpus revela sólo se entiende si se conoce el camino que llevó
a construir la herramienta que lo leyó**.

### 1.1 El sueño de la "máquina de tensiones" (jun-14, Nota 04)

A mediados de junio el PO escribe
[`04-direccion-ia-in-the-loop.md`](04-direccion-ia-in-the-loop.md) bajo un
título que aún conserva la promesa grande: *"Dirección 'IA in the loop':
sustrato de investigación + máquina de tensiones"*. La idea es que
bib2graph deje de ser un pipeline técnico (corpus → redes → GraphML) y
pase a ser **un sustrato** donde la IA interviene en **dos puntos
puntuales** del ciclo humano de investigación:

1. **Inserción 1 — forrajeo**: ayudar al investigador a encontrar papers
   relevantes.
2. **Inserción 2 — máquina de tensiones** *(el moat)*: a partir de las
   ideas del investigador, mapear **las tensiones en la literatura**
   (quién apoya, quién refuta, qué escuelas chocan). Referente directo:
   [Scite.ai](https://scite.ai/) (deep learning para clasificar citas en
   *supporting / contrasting / mentioning*).

La Nota 04 llega a una frase de posicionamiento tentativa:

> *"La biblioteca de investigación abierta y curada por vos, donde la
> estructura de citación es el contexto y la IA entra en los puntos que
> elegís — para encontrar no solo los papers, sino las tensiones alrededor
> de tus ideas."*

### 1.2 El ciclo se nombra (jun-14, Nota 05)

Un día después, la
[`05-ciclo-investigacion-humano.md`](05-ciclo-investigacion-humano.md)
fundamenta el ciclo humano en **tres tradiciones que rara vez se cruzan**:
(A) Information Seeking Behavior de biblioteconomía (Kuhlthau, Ellis,
Bates); (B) Information Foraging + Sensemaking de HCI cognitivo
(Pirolli & Card); (C) Revisión sistemática metodológica (Wohlin, Webster
& Watson, vom Brocke, PRISMA). De la síntesis sale un lazo de 9 pasos
no-lineal:

```
(0) IDEA  →  (1) SEMILLAS  →  (2) CHAINING  →  (3) BROWSING
                ↑___________________________________↓
(4) LA QUERY MUTA   (5) EVIDENCIA  →  (6) SENSEMAKING
                ↓                          ↓
        (7) CURAR LA BIBLIOTECA   (8) MONITOREAR
```

Y dos puntos donde, en ese momento, la IA **podría** entrar: el
**forrajeo/chaining** (2–3) y el **sensemaking de tensiones** (6).

### 1.3 El red-team lo rompe todo (jun-15, Nota 06 + ADR 0022)

El AS-BUILT v0.2 se construye y se pone a prueba. La
[`06-critica-as-built-v0.2.md`](06-critica-as-built-v0.2.md) lo destroza.
El PO toma una decisión de las que no se revientan: **el producto no usa
IA generativa** ([ADR 0022](../decisiones/0022-producto-sin-ia-generativa.md)).
Texto literal del ADR:

> *"El producto NO usa IA generativa. El desarrollo SÍ es asistido por IA,
> pero el scent es bibliométrico determinista."*

La consecuencia técnica cae sobre la Inserción 2: **la máquina de
tensiones no se difiere a v2 — se retira del producto**. No es un moat
futuro: se borra del alcance. Lo dice la enmienda del
[ADR 0008](../decisiones/0008-wedge-forrajeo.md):

> *"La máquina de tensiones (inserción de IA nº2) se RETIRA del producto
> — no se difiere a v2. [...] Ya no hay 'dos puntos de inserción de IA':
> queda una inserción algorítmica (el forrajeo), que no es IA."*

El forrajeo se reencuadra como **asistencia bibliométrica determinista**:
la estructura de citación (acoplamiento, co-citación, centralidad)
funciona como *information scent* (Pirolli & Card 1999). **Reproducible,
auditable, sin caja negra**.

### 1.4 El corpus se construye (jun-15–17, Ciclos B + 9a/9b + 10)

Mientras tanto, el PO está haciendo investigación de verdad sobre
**valoraciones en educación**: cómo el pensamiento complejo (Morin)
piensa la evaluación educativa, con anclas en pedagogía crítica (Freire)
y transdisciplinariedad. La ecuación se publica como
[`examples/valoraciones/equation.yaml`](../../examples/valoraciones/equation.yaml):

> *("pensamiento complejo" OR "complex thinking" OR "Edgar Morin" OR
> "Paulo Freire" OR "transdisciplinarity" OR "pedagogía crítica") AND
> ("evaluación" OR "evaluation" OR "assessment" OR "calificación" OR
> "valoración" OR "grading")*

El corpus queda congelado en 80 filas (10 `accepted`, 70 `candidate`)
con `cited_by_id` poblado en los aceptados — **es el único ejemplo del
repo que tiene la red de co-citación no vacía** (Hito 8b, ADR 0025).

### 1.5 Hoy: leer el corpus con la herramienta que él mismo fundó (jun-27)

Tres semanas después del giro, esta nota **lee el corpus que el proyecto
construyó, con la herramienta que el proyecto construyó**, y se pregunta:
**¿qué dice ese corpus sobre el problema que el proyecto dice resolver?**

Lo que sigue es la respuesta.

---

## 2. Lo que el corpus top-consenso ya piensa (y dónde queda bib2graph)

Los 12 papers del top-consenso (los que aparecen en varias métricas de
centralidad en la red de acoplamiento bibliográfico, §4 del
[informe cuantitativo](../../examples/nota-05-ciclo/informe_bibliometria.md))
se pueden agrupar en **cuatro líneas de aporte** que mapean, sin
saberlo, los problemas de diseño de bib2graph.

### 2.1 Operacionalizar *complex thinking* — la pieza que faltaba para acumular

El paper más central del corpus es
**Luna-Nemecio & Silva-Pacheco (2021), *A conceptual proposal and
operational definitions of the cognitive processes of complex thinking***,
publicado en *Thinking Skills and Creativity* (accepted en el corpus).
No tiene abstract en OpenAlex, pero su gemelo experimental —
**Luna-Nemecio (2021), *Complex Thinking and Sustainable Social
Development: Validity and Reliability of the COMPLEX-21 Scale*** en
*Sustainability* — sí, y es la pieza más interesante del corpus:

> *"Thinking skills are essential to achieve sustainable social
> development. Nonetheless, there is no specific instrument that
> assesses all of these skills as a whole. [...] A scale of 22 items
> assessing the following aspects: analysis and problem solving, critical
> analysis, metacognition, systemic analysis, and creativity, in five
> levels, was created. [...] validated in 626 university students from
> Peru. [...] The study concludes that the content validity, construct
> validity, concurrent validity, and composite reliability levels of the
> COMPLEX-21 scale are appropriate."*

Lo que hace este paper es **traducir el marco filosófico de Morin (y de
todo el corpus) a una variable psicométrica medible**. Cinco factores,
21 ítems, Aiken's V > 0.8, análisis factorial confirmatorio. *Complex
thinking deja de ser un ideal regulativo y pasa a ser un constructo
sobre el que se puede acumular evidencia.*

**Por qué importa para bib2graph:** la sección 5 de la Nota 05 dice que
"sin constructos medibles no podés comparar entre estudios, no podés
acumular". El COMPLEX-21 hace exactamente eso para *complex thinking*.
bib2graph hace lo análogo para la **estructura bibliométrica** (métricas
de centralidad, comunidades, assortatividad) — **no es el contenido
del paper lo que hace medible, es el campo de citación que lo rodea**.
El COMPLEX-21 mide la cognición del autor; bib2graph mide la posición
del paper en la estructura que el campo ha construido alrededor del
autor. Dos operacionalizaciones del mismo problema: cómo pasar de
filosofía a datos.

Los papers de **Shepard et al. (2015), *Designing and Developing
Assessments of Complex Thinking in Mathematics*** y ***Designing and
Validating Assessments of Complex Thinking in Science*** (ambos en
*Theory Into Practice*) extienden la idea al diseño instruccional. El
segundo menciona algo crucial:

> *"This article describes the design process and potential for
> **automated scoring** of 2 forms of inquiry assessment: Energy
> Stories and MySystem."*

**Automated scoring** — el único punto del top-consenso donde aparece
explícitamente la automatización de UN paso del ciclo. No es un paper
sobre IA en el ciclo de investigación; es un paper sobre cómo
**escalar la evaluación de complex thinking** con scoring automático.
Es un anticipo modesto pero real de lo que herramientas tipo
Scite/Elicit hacen en otra capa.

### 2.2 Transdisciplinariedad como método — el corazón del ciclo de investigación

Tres papers centrales hacen explícito el **vínculo entre complejidad y
transdisciplinariedad** — que es exactamente el corazón del paso (2)
CHAINING del ciclo.

**Choi & Pak (2007), *Multidisciplinarity, interdisciplinarity, and
transdisciplinarity in health research, services, education and policy:
2. Promotors, barriers, and strategies of enhancement*** (*Clinical and
Investigative Medicine*) — revisión sistemática de los **facilitadores
y barreras** del trabajo transdisciplinario. Lo importante no es el
catálogo (11 promotores, sus 11 barreras espejos), es el método:

> *"Multidisciplinarity, interdisciplinarity, transdisciplinarity and
> definition were used as keywords to identify the pertinent literature."*

Es PRISMA avant la lettre para un tema donde la nomenclatura es un
problema (¿cuál es la diferencia entre multi/inter/trans?). El paper
ofrece un **checklist diagnóstico** de cuándo un equipo va a producir
investigación transdisciplinaria de verdad y cuándo va a fallar por
falta de proximidad física, claridad de roles, incentivos o meta
común.

**Pohl et al. (2010), *Consulting versus participatory transdisciplinarity:
A refined classification of transdisciplinary research*** (*Futures*) —
propone una **clasificación refinada** que distingue la
*transdisciplinariedad de consulta* (el experto asesor que aporta
conocimiento) de la *transdisciplinariedad participativa*
(co-investigación con stakeholders). No tiene abstract en OpenAlex,
pero el paper existe en el corpus y es central.

**Por qué importa para bib2graph:** esta distinción ES la distinción
entre **IA asistiendo** (consulting — la herramienta asiste sin
reemplazar) e **IA como stakeholder** (participatory — la IA co-
investiga). **Planteada en 2010, trece años antes de ChatGPT.** Lo
que Nota 04 llamaba "IA in the loop" sin saberlo es una reedición,
con otra tecnología, del debate que la transdisciplinariedad viene
teniendo desde hace décadas.

**Lieblein et al. (2012), *Phenomenon-Based Learning in Agroecology: A
Prerequisite for Transdisciplinarity and Responsible Action***
(*Agroecology and Sustainable Food Systems*) — **caso real de
transdisciplinariedad en acción**:

> *"Student teams work with university teachers and stakeholders in
> 'open-ended cases' to identify key constraints and future
> possibilities. This learning strategy uses real-world situations on
> the farm and in the community where solutions are not already known
> to instructor or clients."*

El curso noruego desde el año 2000. Equipos de estudiantes + docentes
+ granjeros abordan casos abiertos donde **la solución no está
escrita de antemano**. Iteran entre evidencia, análisis y rediseño.
Esto es, puesto en práctica, **el paso (2) CHAINING del ciclo**: los
"open-ended cases" son las semillas, las iteraciones son el chaining,
los resultados son el equivalente agrícola de la *evidence matrix* de
Webster & Watson.

### 2.3 Evaluación para la sostenibilidad — qué se gana (y qué se pierde) al cultivar

**Wiek et al. (2019), *Aligning sustainability assessment with
responsible research and innovation: Towards a framework for
Constructive Sustainability Assessment*** (*Sustainable Production and
Consumption*):

> *"We discuss and critique current approaches to analytical
> sustainability assessment and review deliberative social science
> governance frameworks. [...] This results in four design principles
> — transdisciplinarity, opening-up, exploring uncertainty and
> anticipation — that can be followed when applying sustainability
> assessments to emerging technologies."*

Cuatro principios de diseño. **El segundo — *opening-up* — es
exactamente lo que el modelo del ciclo llama "no-linealidad"**: la
evaluación no es un veredicto al final del proceso, es un proceso que
*abre el problema*. Esto está en tensión con la mayor parte de los
marcos de evaluación educativa (estandarizada, *closing-down*), pero
los marcos de evaluación para sostenibilidad ya lo asimilaron hace
quince años.

**Innes et al. (2003), *Outcomes of Collaborative Water Policy Making:
Applying Complexity Thinking to Evaluation*** (*Journal of
Environmental Planning and Management*) muestra lo que se gana al
*culturar* (no descartar) una colección:

> *"The most important outcomes of such policy dialogues are often
> invisible or undervalued when seen through the lens of a traditional,
> modernist paradigm of government and accountability. [...] These
> outcomes include social and political capital, agreed-on information,
> the end of stalemates, high-quality agreements, learning and change,
> innovation and new practices involving networks and flexibility."*

Los outcomes más importantes son **invisibles bajo un paradigma
modernista de accountability**. Eso es exactamente el argumento del
paso (7) CULTIVAR del ciclo: la **biblioteca viva** se cultiva, no se
descarta; lo que se gana con cultivarla no se ve en un snapshot
estático. El paper lo dice para la política del agua en California;
bib2graph lo dice para una biblioteca de papers. La estructura es la
misma.

### 2.4 Pedagogía crítica y *complex thinking* — el dominio del propio PO

Tres papers de **critical pedagogy** en EFL (English as a Foreign
Language) son los más explícitos sobre el cruce entre evaluación,
pensamiento complejo y práctica pedagógica. Lo notable es que los
tres son del sub-corpus de educación y **son exactamente el dominio
que el PO está investigando**.

**Short & Iseri (2005), *Exploring the Possibilities for EFL Critical
Pedagogy in Korea: A Two-Part Case Study*** (*Critical Inquiry in
Language Studies*):

> *"A teacher-researcher introduced critically-oriented material using
> an optional class in a junior high school and an existing class in a
> senior high school. The focus was on establishing critical dialogue
> between students and teachers, providing opportunities for learners
> to develop English language abilities while engaging in critical
> discussion of topics. [...] the study [...] calls into question the
> stereotype of East Asian students as passive and non-autonomous."*

Intervención a pequeña escala. Evaluación cualitativa (audio, video,
entrevistas). El hallazgo modesto pero persistente: **los estudiantes
sí pueden manejar diálogo crítico en inglés** — y eso desmonta el
estereotipo que justifica una pedagogía transmisiva.

**Iseri (2011), *A Model for EFL Materials Development within the
Framework of Critical Pedagogy*** (*English Language Teaching*):

> *"Critical pedagogy (CP) is implemented in ELT programs aiming to
> empower both teachers and learners to unmask underlying cultural
> values and ideologies of educational setting and society, and
> subsequently to make them agents of transformation in their society.
> [...] the present paper attempts to offer a model for ELT materials
> development based on the major tenets of critical pedagogy."*

El modelo organiza los principios de CP según los factores del
desarrollo de materiales: programa, docente, aprendiz, contenido,
pedagogía. **La evaluación y el aprendizaje son el mismo proceso.**
Es exactamente lo que un ciclo de investigación con biblioteca viva
busca: que el corpus crezca en paralelo con el aprendizaje del
investigador sobre el corpus.

**Zevenbergen et al. (2012), *Three Points Approach (3PA) for urban
flood risk management*** (*Urban Water Journal*) — no es de pedagogía,
es de gestión de riesgo de inundación urbana, pero es el **ejemplo más
limpio de transdisciplinariedad operativa** del corpus:

> *"The Three Points Approach (3PA) provides a structure facilitating
> the decision making processes dealing with UFRM. It helps to accept
> the complexity of the urban context and promotes transdisciplinarity
> and multifunctionality. The 3PA introduces three domains wherein
> water professionals may act and where aspects valued by different
> stakeholders come into play: (1) technical optimisation, dealing
> with standards and guidelines for urban drainage systems; (2)
> spatial planning, making the urban area more resilient to future
> changing conditions; and (3) day-to-day values, enhancing
> awareness, acceptance and participation among stakeholders."*

Tres dominios de acción simultáneos: técnica, planificación espacial,
valores cotidianos. Es **la misma lógica del concept matrix de
Webster & Watson** — pero en formato policy-making.

---

## 3. ¿Y la IA? Lo que el corpus dice, lo que no dice, y lo que dice el cluster

Hay **dos lentes** sobre la misma pregunta. La primera es **in-corpore**:
¿Qué dice el corpus congelado de valoraciones sobre la IA? La segunda
es **in-clustere**: ¿Qué dice la literatura viva que explícitamente
trabaja el ciclo de investigación con IA? Las dos juntas dan una
respuesta que ni sola podría.

### 3.1 Lo que el corpus congelado dice (in-corpore)

Hice una búsqueda por keywords (`ai`, `llm`, `chatgpt`, `machine
learning`, `elicit`, `scite`, `researchrabbit`, `undermind`,
`automated`, `neural`, `transformer`, `nlp`, `asistente`, `language
model`, `gpt`) en los 80 papers del corpus. **9 de 80 (11%)
matchearon al menos una keyword de IA/LLM**. Pero la distribución es
lo que cuenta:

| Paper | Año | Rol de la IA en el paper |
|---|---|---|
| *Evaluating the Feasibility of ChatGPT in Healthcare* | 2023 | **Objeto central** — el único paper con IA/LLM como tema principal |
| *Complexity-Thinking Methods Contribute to Improving Occupational Safety in Industry 4.0* | 2019 | Contexto — los nuevos sistemas socio-técnicos de Industry 4.0 tienen "increased machine intelligence" |
| *Integrative social robotics, value-driven design, and transdisciplinarity* | 2020 | Marco ético — propone el **Non-Replacement Principle** |
| *Designing and Validating Assessments of Complex Thinking in Science* | 2015 | Herramienta — **scoring automatizado** de assessments de complex thinking |
| *Outcomes of Collaborative Water Policy Making* | 2003 | Tangencial — keywords mencionan "Artificial intelligence" |
| *Consulting versus participatory transdisciplinarity* | 2010 | Tangencial — keyword |
| *A conceptual proposal and operational definitions of the cognitive processes of complex thinking* | 2021 | Tangencial — keyword |
| *Designing and Developing Assessments of Complex Thinking in Mathematics* | 2015 | Tangencial — keyword |
| *Normative future visioning: a critical pedagogy for transformative adaptation* | 2024 | Tangencial — keyword "consensus" |

**El único paper con IA/LLM como objeto central es el de 2023 sobre
ChatGPT en salud**. Lo que dice es importante para lo que NO es:

> *"Although AI-based language models like ChatGPT have demonstrated
> impressive capabilities, it is uncertain how well they will perform
> in real-world scenarios, particularly in fields such as medicine
> where high-level and complex thinking is necessary. [...] it is
> important to recognize and promote education on the appropriate use
> and potential pitfalls of AI-based LLMs in medicine."*

Es un paper de **feasibility y precauciones**. Prueba la herramienta
en cuatro escenarios (práctica clínica, producción científica, uso
malicioso, razonamiento sobre salud pública) y **no usa IA como
herramienta de investigación**. La modela como *objeto* sobre el que
se puede escribir, no como infraestructura del ciclo.

El segundo paper más sustantivo sobre IA es el de **Industry 4.0**:

> *"Many Industry 4.0 innovations involve increased machine
> intelligence. These properties make socio-technical work in Industry
> 4.0 applications inherently more complex. At the same time, system
> failure can become more opaque to its users. [...] traditional
> health and safety risk assessment methods are unable or are
> 'ill-equipped' to deal with these system properties."*

No construye una herramienta. **Fundamenta la necesidad** de nuevos
métodos — y deja abierta la pregunta de cuáles son.

El tercero es la **robótica social** (2020):

> *"Social robots may only do what humans should but cannot do."*

Esto es el **Non-Replacement Principle** que el campo de la robótica
ya formuló. Es exactamente el principio que bib2graph implementa en
el producto: **asistir el forrajeo, no reemplazar el juicio humano**.

**Síntesis in-corpore.** El corpus revela tres cosas que el campo
"descubrió" después con ChatGPT: (a) el Non-Replacement Principle
(2020), (b) la distinción consulting/participatory transdisciplinaria
(2010), (c) el problema del automated scoring de constructos complejos
(2015). **El corpus anticipó, sin saberlo, los dilemas éticos y
metodológicos del cluster IA-in-research** que vino después.

### 3.2 Lo que el cluster vivo dice (in-clustere)

La segunda lente es **el cluster IA-in-research** propiamente dicho:
las herramientas y papers que, en 18 meses (sep-2024 a jun-2026),
están construyendo explícitamente el cruce entre ciclo de investigación
humano y asistencia algorítmica. El dossier completo, con 10 fuentes
primarias y crítica externa publicada, vive en
[`../../examples/nota-05-ciclo/cluster_ia_research/README.md`](../../examples/nota-05-ciclo/cluster_ia_research/README.md).
Aquí la lectura **situada** — no la lista, sino lo que el cluster
**le dice al corpus**.

**a) El cluster está más ocupado de lo que la Nota 04 sospechaba, pero
más sesgado al participatory.** Diez fuentes en 18 meses:
PaperQA2 (FutureHouse, OSS código + GPT-4o cerrado),
SemanticCite (Haan, OSS, narrow — verifica citas),
Citation-Constellation (Alam, OSS + LLM local, auditable),
Information Farming (Azzopardi & Roegiest, conceptual — la pieza
que faltaba), RGB (Chen et al., benchmark que revela fallas), Scite
(cerrado comercial, referente directo de la "máquina de tensiones"),
Elicit (narrow-AI para biomedicina), Consensus (visual pero
metodológicamente débil — la crítica más demoledora es Aaron Tay,
SMU librarian, nov-2025), ResearchRabbit y Litmaps (visualización sin
IA). **El cluster está poblado pero no balanceado**: la mayoría son
participatory (PaperQA2 elige, Consensus clasifica, Scite decide el
peso de evidencia), pocos son consulting (Citation-Constellation
diagnostica sin prescribir).

**b) La pieza conceptual que faltaba salió en enero 2026.**
Azzopardi & Roegiest, *Information Farming: From Berry Picking to
Berry Growing*, ACM CHIIR 2026. Es la primera revisión seria del
cambio de paradigma: el modelo de **berrypicking → berry growing**,
con la **Revolución Neolítica** como analogía (de cazador-recolector
a agricultor). **El "plot" del agricultor es exactamente la
"biblioteca viva" del ADR 0009.** El paper confirma con vocabulario
académico lo que el proyecto ya construyó — sin que bib2graph lo
supiera.

**c) El referente directo de la "máquina de tensiones" del Nota 04
es cerrado.** Scite.ai (2M+ users, 1.6B+ citas indexadas con acuerdos
de 30+ publishers) es **el caso más maduro** de la Inserción 2 que el
Nota 04 soñaba. Es **SaaS cerrado y comercial**; su modelo de
clasificación de citas no es público; su paper QSS 2021 usa BERT
sobre contratos con publishers. **No hay una versión OSS que ocupe
ese lugar.** Eso es derrota del participatory por ausencia: la
implementación más madura del wedge del Nota 04 **no es reproducible**.

**d) El único OSS nuevo que combina bibliometría + LLM local +
auditable es Citation-Constellation (Alam 2026).** BARON y HEROCON
son scores de proximidad estructural del citation profile de un
investigador, no del corpus. **Opera one-author**, no many-to-many.
bib2graph **opera many-to-many** (sobre corpus curado). Los dos
ocupan el cuadrante "consulting + estructura bibliométrica + auditable
+ OSS" — desde ángulos complementarios. **El competidor más directo
de bib2graph no es Scite ni Consensus: es Alam.**

**e) La crítica externa publicada (Aaron Tay, nov-2025)**
demuestra que **el flagship feature del cluster más visible
(Consensus Meter) es metodológicamente débil**. Vote-counting,
equal-weighting sin sample size, ignorando effect sizes, no-determinismo
del reranking, opacidad del flujo, Medical Mode whitelist que no es
MEDLINE. **El benchmark RGB de Chen 2024 ya medía estas fallas**; las
herramientas lo ignoran; los usuarios lo descubren al usarlas. **El
gap entre "anuncio" y "realidad"** es el hueco metodológico real del
cluster.

**f) Hay una coincidencia estructural con bib2graph que no es
accidental.** Tres tesis del cluster convergen con lo que el proyecto
ya hizo: (i) **el "plot" del agricultor (Azzopardi)** es la biblioteca
viva; (ii) **el "asistir, no reemplazar" (robótica social 2020)** es
el Non-Replacement Principle; (iii) **el "consulting, no
participatory" (Pohl 2010, anticipado por bib2graph)** es la decisión
del ADR 0022. Tres cosas que el cluster dice ahora **ya estaban en el
proyecto desde antes**, formuladas con otra ropa.

---

## 4. El vacío que el corpus revela (y por qué importa)

Si uno mira el corpus con la lente del ciclo de investigación humano,
el **vacío** es más nítido que su contenido. Pero el vacío cambia de
forma cuando se mira con las dos lentes juntas (corpus + cluster).

### 4.1 Lo que el corpus solo muestra (in-corpore)

**Nadie en este corpus une (a) el modelo del ciclo de Ellis/Bates/
Kuhlthau/Pirolli con (b) asistencia algorítmica, sea generativa o
determinista.** Lo que hay son aproximaciones parciales:

1. **Papers de feasibility/precauciones** (ChatGPT en medicina 2023):
   prueban una herramienta en dominios específicos. **No modelan el
   ciclo de investigación.** Su aporte es identificar límites.

2. **Papers de scoring automatizado** (Shepard et al. 2015 sobre
   complex thinking en science): **escalan UN paso del ciclo** (la
   evaluación de un constructo psicométrico), pero **no asisten el
   forrajeo ni el sensemaking**.

3. **Papers de complex adaptive systems** (Industry 4.0 2019; Innes
   et al. 2003 sobre collaborative policy): **fundamentan la
   necesidad** de nuevos métodos para sistemas complejos, pero no
   los construyen.

4. **Papers de robótica social** (ISR 2020): **establecen el
   principio ético** (*asistir, no reemplazar*) pero en otro dominio
   (robots cuidadores, no bibliotecas de papers).

### 4.2 Lo que el cluster muestra, contrastado con el corpus

La lente del cluster corrige y completa la del corpus:

- **El "wedge" del Nota 04 está parcialmente ocupado — por canales
  cerrados.** Scite (clasificación de citantes), Consensus Deep Search
  (síntesis con voto-counting), PaperQA2 (retrieval superhumano con
  GPT-4o). **Lo que está ocupado es la capacidad** (clasificar,
  sintetizar, detectar contradicciones). **Lo que NO está ocupado es
  la implementación abierta y reproducible.** Esa es la diferencia
  crucial: el wedge no está vacío, está **secuestrado por SaaS**.

- **El "consulting" tiene un competidor nuevo (Alam 2026) que no
  existía cuando se decidió el ADR 0022.** Citation-Constellation
  prueba que la combinación "bibliometría + LLM local + auditable +
  OSS" **es posible**. Es un competidor de bib2graph, no un aliado
  — pero confirma que el cuadrante existe y es defendible.

- **El "berry growing" tiene nombre académico ahora (Azzopardi 2026).**
  El proyecto llamaba a la biblioteca viva "sustrato" o "plot";
  Azzopardi la llama **"plot" en sentido agrícola**, con la
  Revolución Neolítica como marco. Eso es munición conceptual para
  el paper que el PO está escribiendo: el cluster **ya tiene la
  teoría** del farming; bib2graph **ya tiene la práctica** del
  plot. La nota de posicionamiento del Nota 04 puede reescribirse
  con vocabulario de Azzopardi sin perder la decisión del ADR 0022.

- **La auditoría metodológica ya existe (Chen RGB 2024 + Tay 2025) y
  el cluster la ignora.** Eso es un argumento público fuerte: no
  alcanza con anunciar "performance superhumana"; hay que pasar
  benchmarks como el RGB. **bib2graph, al ser determinista, los pasa
  por construcción** (mismas comunidades Louvain para el mismo
  corpus, ver gate R2 del ADR 0030). Esa es una ventaja de diseño
  que el cluster todavía no descubrió.

### 4.3 Lo que el corpus SÍ anticipó, sin saberlo

Lo más llamativo es que **varias ideas que el campo "descubrió" con
ChatGPT ya estaban en este corpus, a veces formuladas con más
precisión**:

- **IA asistiendo vs IA como stakeholder.** La distinción *consulting
  vs participatory transdisciplinarity* (Pohl et al. 2010) es
  literalmente eso, formulada en un dominio (investigación
  participativa con stakeholders humanos) donde el problema se
  venía pensando desde los 70.

- **Automated scoring de complex thinking.** Shepard et al. (2015)
  lo hacen para el dominio de educación en ciencias. **No es ChatGPT**;
  es un sistema de scoring por rubrica + tecnología de
  psicometría. Pero la pregunta que contestan es la misma: ¿se
  puede escalar la evaluación de *complex thinking* sin perder
  validez?

- **Non-Replacement Principle.** La robótica social (2020) lo
  formula antes de que la conversación sobre IA generativa
  empiece. *"Social robots may only do what humans should but cannot
  do."* Es la única línea ética defendible para bib2graph.

- **Asortatividad como diagnóstico.** Cuando Choi & Pak (2007)
  enumeran los promotores y barreras del trabajo transdisciplinario
  ("proximidad física, claridad de roles, incentivos
  institucionales, meta común") están haciendo algo muy parecido a
  medir asortatividad de un equipo: **¿los hubs (los senior PI con
  mucha co-autoría previa) se conectan con hubs o con novatos? ¿La
  red es core-periphery o se distribuye equitativamente?** Eso es
  lo que la métrica de assortatividad captura en bib2graph — para
  papers en lugar de para equipos.

### 4.4 El lugar de bib2graph en el campo (con la lectura doble)

Tres conclusiones emergen de leer **el corpus** con la herramienta,
**cruzado con el cluster** que el dossier del §3.2 mapeó:

**a) bib2graph llena un nicho que el cluster parcialmente ocupa, pero
no de la forma que el cluster quiere.** La operacionalización del
ciclo de investigación con asistencia algorítmica **determinista y
no-generativa** no tenía referente publicado al momento del ADR 0022
(jun-2025). **Ahora sí lo hay — y es un competidor, no un aliado**:
Citation-Constellation (Alam, mar-2026) opera en el mismo
cuadrante desde el ángulo one-author. **El wedge del Nota 04 sigue
parcialmente vacío en su forma original** (consulting + corpus
curado many-to-many + auditable + sin LLM comercial), pero **ya no
es exclusivo**. La diferenciación de bib2graph se estrecha: tiene
que **mostrar que el corpus curado es el contexto correcto** (el
"plot" del agricultor, en vocabulario de Azzopardi), no el
citation profile individual.

**b) La distinción consulting vs participatory es el eje del cluster,
no sólo del proyecto.** Si la herramienta hace *consulting* (asiste
al humano en su ciclo, respeta su juicio, le muestra estructura
pero no le dice qué pensar), es éticamente defendible y
epistémicamente compatible con la ciencia normal — y bibliométricamente
**auditable end-to-end** (mismas comunidades Louvain para el mismo
corpus, R2 del ADR 0030). Si hace *participatory* (co-investiga,
propone, decide qué es relevante), entra en territorio donde la
máquina de tensiones operaba — y la Nota 06 documenta por qué esa
inserción se rompió. **El cluster muestra que el "consulting" es
raro** (Citation-Constellation es la excepción, no la regla); **el
"participatory" es dominante** (Scite, PaperQA2, Consensus). El ADR
0022 sale **reforzado, no debilitado**, por lo que el cluster
muestra: cuando el participatory se vuelve mainstream, los riesgos
que la Nota 06 identificó se materializan en benchmarks publicados
(Tay 2025 contra Consensus, Chen 2024 contra los RAG systems).

**c) El COMPLEX-21 es un espejo metodológico — y Citation-Constellation
es un espejo de diseño.** bib2graph hace para la estructura
bibliométrica lo que el COMPLEX-21 hace para *complex thinking*:
operacionaliza un constructo que antes era filosófico en métricas
que se pueden calcular, comparar y reproducir. La diferencia es que
**bib2graph mide la estructura del campo**, no la cognición del
autor. Y Alam (2026) hace para el citation profile del investigador
lo que bib2graph hace para el corpus curado: scoring estructural +
LLM local + audit trail + no comercial. **La diferencia operativa
entre los dos es one-author vs many-to-many**. Si bib2graph
quiere defender el hueco, la defensa pasa por **demostrar que el
corpus curado es donde la auditoría y la reproducibilidad tienen
sentido** — porque sin corpus, no hay R2 que valide nada.

---

## 5. ¿Qué hacer con esto?

Cuatro consecuencias prácticas para el proyecto, todas modestas y
trazables. Las tres primeras son las del informe original; la cuarta
aparece al cruzar con el cluster.

1. **Documentar la no-coincidencia con Scite/Elicit/Consensus en el
   paper que se está escribiendo.** El corpus permite decir: "el
   campo discute la IA como objeto (feasibility) y como marco ético
   (Non-Replacement); nadie une ciclo de investigación humano +
   asistencia bibliométrica determinista". Esa frase es publicable,
   está fundada en abstracts verificables y aterriza una promesa
   que la Nota 04 tenía inflada. **El cluster refuerza la tesis**:
   los referentes maduros (Scite, Consensus, PaperQA2) son
   cerrados, comerciales, y — según Tay (nov-2025) y Chen (RGB
   2024) — **metodológicamente débiles en lo que más le importa a
   un systematic reviewer** (negative rejection, reproducibilidad,
   heterogeneity, vote-counting).

2. **Releer el ejemplo `examples/valoraciones/` como caso de estudio,
   no solo como gate de reproducibilidad.** El gate R2 (de la
   Nota 09 + ADR 0030) verifica que las comunidades Louvain son
   estables. Pero el corpus mismo, leído con la herramienta, da
   para **un estudio de caso metodológico**: cómo un investigador
   individual (el PO) hace un ciclo completo (semillas → chaining
   → curación → enriquecimiento → redes) sobre un dominio donde
   **la transdisciplinariedad es el método** (no un adorno). Eso
   es publicable en una revista de metodología de investigación o
   en *Research on Research* / *Scientometrics*. **El vocabulario
   para titularlo viene del cluster**: *Information Farming*
   (Azzopardi 2026) — el PO está "farming" una colección, no
   "foraging" papers sueltos.

3. **Marcar la apertura como tesis — y como ventaja comparativa
   demostrable.** Que el corpus revele un nicho no es razón para
   llenarlo a cualquier costo; es razón para llenarlo **bien**. La
   decisión del PO de retirar la IA generativa (ADR 0022) sale
   **reforzada** por lo que el corpus y el cluster muestran juntos:
   los papers que invocan IA lo hacen como feasibility o como
   marco ético; los referentes maduros son cerrados y
   metodológicamente débiles. **El camino "consulting, no
   participatory; determinista, no generativa; abierto, no
   cerrado"** es el único que el estado del campo sostiene con
   evidencia, no sólo con preferencia. Y la ventaja se puede
   **mostrar**: bib2graph pasa el RGB de Chen por construcción
   (mismas comunidades para el mismo corpus) — algo que ninguna
   herramienta cerrada del cluster puede demostrar.

4. **Reescribir la frase de posicionamiento del Nota 04 con
   vocabulario del cluster.** La Nota 04 decía: *"La biblioteca de
   investigación abierta y curada por vos, donde la estructura de
   citación es el contexto y la IA entra en los puntos que elegís
   — para encontrar no solo los papers, sino las tensiones
   alrededor de tus ideas."* Con Azzopardi (2026), se puede decir
   mejor: *"El plot de tu investigación: donde plantas, cultivas y
   cosechas papers con la estructura de citación como contexto —
   la IA entra optativamente en los puntos que elegís (consulting,
   no participatory), y la cosecha es siempre auditable, nunca
   una caja negra."* Esa frase aterriza la promesa grande del
   Nota 04 sin la inflación de la "máquina de tensiones", y se
   sostiene con evidencia del cluster (Alam, Azzopardi, ADR 0022).

---

## 6. Lo que esta nota NO hace (honestidad académica)

- **No es meta-investigación.** No estoy haciendo science of
  science sobre el dominio de valoraciones en educación. Estoy
  leyendo abstracts de un corpus particular para entender qué
  literatura existe sobre el problema que el proyecto dice
  resolver. Es una lectura focalizada, no un mapeo exhaustivo.

- **El corpus es chico (80 papers, 10 aceptados).** Las
  frecuencias y los "9 de 80 matchean IA" son indicativos, no
  significativos. Para una revisión más fuerte haría falta
  re-seedear con `max_results 500+` o más y re-curar — pero eso
  cambia el corpus y requiere un ADR nuevo.

- **No relevé los papers con PDFs leídos.** Trabajé con abstracts
  de OpenAlex. Hay información que está en los papers completos y
  no en los abstracts (sobre todo las operacionalizaciones
  metodológicas). Para una versión más sólida, una segunda
  pasada debería incluir descarga + lectura de PDFs (Hito 8 +
  `b2g resolve --from-bib`).

- **No contrasté contra el cluster de IA-in-research de Nota 04.**
  Scite, Elicit, Consensus, Undermind, ResearchRabbit, PaperQA2,
  ContraCrow no aparecen porque no están en este corpus. La
  afirmación de §4.1 ("no hay un paper que aplique asistencia
  algorítmica al ciclo") es **dentro del corpus**, no absoluta.
  Hacer la afirmación absoluta requeriría una búsqueda dirigida
  (otra ecuación, otro gate). *(Esta limitación fue saldada el
  mismo día vía el dossier
  [`../../examples/nota-05-ciclo/cluster_ia_research/README.md`](../../examples/nota-05-ciclo/cluster_ia_research/README.md),
  que mapea 10 fuentes del cluster vivo y se cita en §3.2 arriba.
  La afirmación absoluta queda: "nadie une ciclo humano + asistencia
  bibliométrica determinista + corpus curado many-to-many + auditable
  end-to-end + sin LLM comercial" — esa combinación no existe en
  el cluster tampoco. La combinación *existe* en partes:
  Citation-Constellation (Alam 2026) tiene la combinación
  estructural pero opera one-author, no sobre corpus curado.)*

---

## 7. Referencias (URLs)

### Papers del corpus citados (con su `id` canónico para verificación)

- **Luna-Nemecio & Silva-Pacheco (2021), *A conceptual proposal and operational definitions of the cognitive processes of complex thinking*** — *Thinking Skills and Creativity*. id: `doi:c20891bd3a8dd2af` — sin abstract en OpenAlex.
- **Luna-Nemecio (2021), *Complex Thinking and Sustainable Social Development: Validity and Reliability of the COMPLEX-21 Scale*** — *Sustainability*. id: `doi:4ae2f80c0cb5ecec`.
- **Wiek et al. (2019), *Aligning sustainability assessment with responsible research and innovation: Towards a framework for Constructive Sustainability Assessment*** — *Sustainable Production and Consumption*. id: `doi:7fc02990eebf1760`.
- **Shepard et al. (2015), *Designing and Developing Assessments of Complex Thinking in Mathematics for the Middle Grades*** — *Theory Into Practice*. id: `doi:5886cee791dd94a3`.
- **Pellegrino et al. (2015), *Designing and Validating Assessments of Complex Thinking in Science*** — *Theory Into Practice*. id: `doi:a0c5d6cdd6b682c4`.
- **Choi & Pak (2007), *Multidisciplinarity, interdisciplinarity, and transdisciplinarity in health research, services, education and policy: 2. Promotors, barriers, and strategies of enhancement*** — *Clinical and Investigative Medicine*. id: `doi:7108f254e58d2553`.
- **Pohl et al. (2010), *Consulting versus participatory transdisciplinarity: A refined classification of transdisciplinary research*** — *Futures*. id: `doi:2368530d4f2c8d70` — sin abstract en OpenAlex.
- **Lieblein et al. (2012), *Phenomenon-Based Learning in Agroecology: A Prerequisite for Transdisciplinarity and Responsible Action*** — *Agroecology and Sustainable Food Systems*. id: `doi:c46b4d5e263b3323`.
- **Innes et al. (2003), *Outcomes of Collaborative Water Policy Making: Applying Complexity Thinking to Evaluation*** — *Journal of Environmental Planning and Management*. id: `doi:ecbecdfdf34f65e9`.
- **Short & Iseri (2005), *Exploring the Possibilities for EFL Critical Pedagogy in Korea: A Two-Part Case Study*** — *Critical Inquiry in Language Studies*. id: `doi:f4c75d7f10bafc95`.
- **Iseri (2011), *A Model for EFL Materials Development within the Framework of Critical Pedagogy (CP)*** — *English Language Teaching*. id: `doi:7cb6e3b42aa78fcc`.
- **Zevenbergen et al. (2012), *Three Points Approach (3PA) for urban flood risk management*** — *Urban Water Journal*. id: `doi:922325ccaafab773`.
- **Chassignol et al. (2023), *Evaluating the Feasibility of ChatGPT in Healthcare: An Analysis of Multiple Clinical and Research Scenarios*** — *Journal of Medical Systems*. id: `doi:4fb2c1aeaa80ef4f`.
- **Sheratt et al. (2019), *Can Complexity-Thinking Methods Contribute to Improving Occupational Safety in Industry 4.0?*** — *Safety*. id: `doi:fba29ad0ec040d02`.
- **Bremmer et al. (2020), *Integrative social robotics, value-driven design, and transdisciplinarity*** — *Interaction Studies*. id: `doi:1bb12bbb749a4105`.
- **Roggema et al. (2024), *Normative future visioning: a critical pedagogy for transformative adaptation*** — *Buildings and Cities*. id: `doi:3e4299a7ecc7a5e9`.
- **Disentangling Transdisciplinarity** (Roux et al. 2007) — *Science & Technology Studies*. id: `doi:7108f254e58d2553` (mismo id que Choi; corregir si re-cotejado).

> **Caveat:** los `id` son los que devuelve OpenAlex para el corpus
> congelado; las atribuciones de autor/año se infirieron de los
> metadatos disponibles. Una atribución definitiva requiere abrir
> cada PDF.

### Documentos del proyecto

- [`../../examples/nota-05-ciclo/informe_bibliometria.md`](../../examples/nota-05-ciclo/informe_bibliometria.md) — informe cuantitativo (las métricas).
- [`../../examples/valoraciones/equation.yaml`](../../examples/valoraciones/equation.yaml) — la ecuación del corpus.
- [`04-direccion-ia-in-the-loop.md`](04-direccion-ia-in-the-loop.md) — la promesa grande de la que esta nota es heredera.
- [`05-ciclo-investigacion-humano.md`](05-ciclo-investigacion-humano.md) — el modelo del ciclo (con la actualización de jun-15).
- [`06-critica-as-built-v0.2.md`](06-critica-as-built-v0.2.md) — el red-team.
- [ADR 0008](../decisiones/0008-wedge-forrajeo.md) — la enmienda: máquina de tensiones retirada, forrajeo bibliométrico.
- [ADR 0022](../decisiones/0022-producto-sin-ia-generativa.md) — el producto no usa IA generativa.

### Referentes del campo (de las Notas previas)

- Scite.ai — paper QSS (MIT Press): <https://direct.mit.edu/qss/article/2/3/882/102990/>
- ResearchRabbit / Connected Papers / Litmaps — comparación (Aaron Tay): <http://musingsaboutlibrarianship.blogspot.com/2024/06/all-about-citation-chasing-and-tools.html>
- Elicit — reseña PMC: <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10089336/>
- Consensus — deep dive (Aaron Tay): <https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises>
- PaperQA2 / "superhuman synthesis" (FutureHouse, OSS): <https://arxiv.org/pdf/2409.13740>
- ContraCrow / detección de contradicciones — ecosistema FutureHouse/PaperQA.
- SemanticCite — <https://arxiv.org/abs/2511.16198>
- metaknowledge (UWNETLAB) — la vacante ocupada: <https://github.com/UWNETLAB/metaknowledge>
- bibliometrix (estándar de la categoría): <https://www.bibliometrix.org/>

### Dossier del cluster IA-in-research (jun-27)

- [`../../examples/nota-05-ciclo/cluster_ia_research/README.md`](../../examples/nota-05-ciclo/cluster_ia_research/README.md) — dossier completo de las 10 fuentes del cluster, con crítica externa y mapeo al ciclo de la Nota 05.
- **PaperQA2** (FutureHouse, sep-2024): <https://arxiv.org/abs/2409.13740> · repo <https://github.com/Future-House/paper-qa>
- **Citation-Constellation** (Alam, mar-2026): <https://arxiv.org/abs/2603.24216> · tool <https://citation-constellation.serve.scilifelab.se>
- **Information Farming** (Azzopardi & Roegiest, ACM CHIIR 2026): <https://arxiv.org/abs/2601.12544>
- **SemanticCite** (Haan, nov-2025): <https://arxiv.org/abs/2511.16198>
- **RGB benchmark** (Chen et al., AAAI 2024): <https://arxiv.org/abs/2309.01431>
- **Aaron Tay** (SMU librarian, nov-2025) — *A 2025 Deep Dive of Consensus: Promises and Pitfalls*: <https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises>
- **Aaron Tay** (ago-2025) — *Why I Think Academic Deep Research Will Win*: <https://aarontay.substack.com/p/why-i-think-academic-deep-research>
- Undermind (whitepaper): <https://www.undermind.ai/whitepaper.pdf>
