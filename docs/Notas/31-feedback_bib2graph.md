# Retroalimentación del uso de bib2graph

_Informe de feedback sobre una sesión end-to-end de bib2graph v0.11.0
(instalación → seed → chain → build → informe del estado del arte), con
dos voces diferenciadas: **👤 usuario no técnico** (quien opera) y
**🤖 agente IA** (quien asiste). El reporte secciona el flujo en cuatro
momentos: instalación, forrajeo (seed/chain/build), producción del
artefacto analítico y fricciones transversales del agente._

> Esta sesión fue escrita con ánimo constructivo. Los tiempos, errores y
> comandos citados son reales y verificables. La herramienta evoluciona
> rápido; lo que hoy es fricción puede no serlo mañana. El feedback está
> dirigido al mantenedor de bib2graph y a quien use el skill asociado.

---

## 0. Resumen ejecutivo

| momento | resultado | fricción principal |
|---|---|---|
| Instalación | ✅ limpia, dos comandos | ninguna significativa |
| Forrajeo (seed→chain→build) | ✅ corpus útil (293 papers) | 503 inicial + descubrimiento de la API key |
| Artefacto final (4 markdown + 5 plots) | ✅ entregable de calidad | el primer intento auto-generado fue **rechazado por el usuario**; el valor vino de la lectura real de abstracts por el LLM |
| Fricciones transversales del agente | — | mala lectura inicial, atributos faltantes en graphml, curvas de propagación de env vars |

**Recomendación de una línea**: bib2graph es una herramienta sólida para
forrajeo bibliográfico agente-native. Su mayor oportunidad de mejora no
está en el core (que funciona), sino en (a) **documentar atributos del
artefacto** (qué hay y qué no en `network.graphml` vs `library.duckdb`),
(b) **hacer explícito el rol del LLM downstream** para análisis de
contenido, y (c) **endurecer el manejo de autenticación de OpenAlex** (api_key).

---

## 1. Instalación

### 👤 Usuario (no técnico)

> "Instalé con uv y funcionó. El banner del CLI me llamó la atención: se
> autodefine como 'agente-native'. Eso me hizo pensar que estaba hecha
> para trabajar con un asistente IA, y la verdad es que sí, fue la
> sensación durante toda la sesión."

**Lo que funcionó**:
- `uv tool install bib2graph` corrió sin fricción.
- `uv tool upgrade bib2graph` llevó de 0.10.0 a 0.11.0 sin
  intervención.
- El binario `b2g` quedó disponible globalmente.

**Lo que costó**:
- Nada material. Una duda menor: el binario adicional `bib2graph` que
  quedó instalado junto a `b2g` — no está claro para qué sirve vs. el
  canónico. ¿Es un shim? ¿Un entrypoint legacy?

### 🤖 Agente IA

> "La instalación fue trivial desde mi lado también. Una nota: confirmé
> el tagline 'CLI agente-native' leyéndolo del `--help`. Ese banner es
> útil: enuncia la promesa del producto y prepara al usuario sobre qué
> esperar."

**Lo que funcionó**:
- Detección automática de la versión, binario y subcomandos.

**Fricción observada**:
- **Binarios duplicados sin documentación**: `uv tool install` produjo
  dos ejecutables (`b2g` y `bib2graph`). No hubo mensaje explicativo.
  Recomiendo: o deprecar `bib2graph` con un mensaje al usarlo, o
  documentar la diferencia en `--help`.

---

## 2. Forrajeo: seed, chain, build

### 2.1 La ecuación

#### 👤 Usuario

> "La primera ecuación era buena y ambiciosa: emergenciamás sistemas
> complejos más reduccionismo. Tuvo que ser simplificada porque OpenAlex
> devolvía 503 — algo que atribuimos inicialmente a un outage global pero
> luego descubrimos que era otra cosa."

#### 🤖 Agente

> "Cometí un error diagnóstico inicial. El primer 503 me hizo concluir
> 'OpenAlex está caído globalmente'. Era falso. La causa era rate limit
> desde una IP sin auth. Esa mala lectura consumió ~3 turnos de la
> sesión. Lo que me permitió corregir fue la intuición del usuario de
> probar con API key. **Aprendizaje para el skill**: cuando OpenAlex
> devuelve 503 persistente desde un entorno sin auth, **no asumas
> outage**; verificá con `curl` antes de pausar."

### 2.2 La API key

#### 👤 Usuario

> "Yo tenía la key guardada de antes. Se la pasé al agente y dije 'usá
> mi API_KEY'. Pensé que el agente la iba a tomar y listo. No fue tan
> directo: hubo que descubrir que OpenAlex sí la acepta, que bib2graph la
> lee de una variable de entorno específica, y que la env var no se
> propagaba entre los shells del agente. Tardamos varios turnos en
> alinearnos."

**Fricción reportada**:
- Documentación pública de OpenAlex sugiere que la key no es necesaria;
  en la práctica, **sin key, una IP sin auth recibe 503 frecuente**.
- `OPENALEX_API_KEY` no está documentada en `b2g --help`. Tuve que
  encontrar la variable buceando en el código de la herramienta.

#### 🤖 Agente

> "Cuando el usuario me pasó la key, mi primera respuesta fue 'OpenAlex
> no usa API keys' — **estaba equivocado**. Esa respuesta fue producto de
> lo que dice la doc pública y el `--help` de bib2graph (que no la
> menciona). Tuve que verificar con `curl ?api_key=...` (200 OK) y leer
> el código fuente (`openalex.py:413`) para descubrir:
>
> ```python
> self._api_key = api_key or os.environ.get('OPENALEX_API_KEY')
> ...
> headers['Authorization'] = f'Bearer {self._api_key}'
> ```
>
> Esto significa dos cosas:
>
> 1. **bib2graph sí soporta api_key**, pero **no lo dice en ninguna
>    parte visible al usuario**. Hay un flag `--email` (polite pool) y
>    nada más. La variable de entorno `OPENALEX_API_KEY` está
>    implementada pero no documentada.
> 2. **El agente tiene que leer el código fuente** para encontrar el
>    path correcto. Eso es aceptable para un mantenedor; no lo es para
>    un usuario (humano o IA) que solo quiere ejecutar el comando.
>
> **Recomendación concreta**: agregar a `b2g seed --help` una sección:
>
> ```
> Authentication:
>   --email TEXT   Email for OpenAlex polite pool (recommended).
>   OPENALEX_API_KEY env var improves rate limits (optional but
>   recommended for unattended runs). See docs/auth.md.
> ```"

### 2.3 Propagación de variables de entorno

#### 🤖 Agente

> "Otro punto que me costó trabajo: en mi entorno de ejecución, cada
> bash call es un shell nuevo. `set X=Y && comando` en CMD, o
> `export X=Y` en Bash, **no persiste entre invocaciones**. La solución
> que descubrí fue pasar la env var inline:
>
> ```bash
> OPENALEX_API_KEY=... b2g seed ...
> ```
>
> Esto no es culpa de bib2graph — es del entorno. Pero el usuario
> humano, al ver que 'la env var no se propaga', puede pensar que la
> herramienta está rota. **Recomendación para el skill**: cuando el
> agente explique cómo setear una env var, debe especificar **inline**
> o **cómo exportar persistentemente en el shell del usuario**."

### 2.4 Chaining costoso

#### 👤 Usuario

> "Tuve que esperar casi 5 minutos para el chaining. No fue un problema,
> pero si esto fuera un flujo iterativo de refinamiento sería molesto."

#### 🤖 Agente

> "El primer `b2g chain --depth 1` con defaults tardó >5 minutos y
> terminó en timeout (300s). Bajamos `--max-citing` de 50 a 25 y
> `--max-candidates` a 300 — terminó en ~4:43. Sugerencias:
>
> 1. **Documentar tiempos esperados** según tamaño del corpus. Una
>    tabla heurística en docs/performance.md ayudaría.
> 2. **Considerar un modo preview más barato**: `--preview` ya existe y
>    calcula estimaciones sin fetchear; promoverlo en el `--help`
>    ('empezá por acá si tu corpus tiene >200 seeds').
> 3. **Barra de progreso más informativa**: la actual muestra solo
>    'forward chaining N/M'. Detalle como 'batch X/Y · Z papers
>    encontrados hasta ahora' ayudaría a decidir abortar."

### 2.5 Build y la membresía de cluster

#### 🤖 Agente

> "El `b2g build` corrió sin problemas y produjo `clusters.csv` con 6
> comunidades. Aquí vino la fricción más interesante: la membresía de
> cluster está en `clusters.csv` y en `.corpus_hash`, pero **no como
> atributo de nodo en `network.graphml`**. Esto significa que para
> reproducir el particionado de cluster, hay que correr el algoritmo
> (no es trivial — depende de `python-louvain` y del random_state
> derivado del hash) o leer el CSV.
>
> Mi primera implementación intentó asignar clusters re-corriendo
> Louvain con el mismo `random_state`. **Funcionó**, pero es un punto
> frágil:
>
> 1. Si bib2graph cambia de algoritmo de clustering (de Louvain a otro),
>    mi código downstream se rompe silenciosamente.
> 2. Si el usuario cambia `resolution` o `random_state` en build, mi
>    código downstream diverge del suyo.
>
> **Recomendación**: persistir el `cluster_id` como atributo de cada
> nodo en `network.graphml` (`<data key="d_cluster">N</data>`). Es un
> cambio pequeño en el projector y elimina una clase entera de bugs."

---

## 3. El artefacto final: 4 markdown + 5 plots

Este es el corazón del reporte, porque es donde el "agente-native"
prometido por el banner se concreta — o se queda corto.

### 3.1 Primer intento: auto-generación por reglas (rechazado)

#### 👤 Usuario

> "El primer informe que me entregó el agente era claramente mediocre.
> Detectaba tags con regex sobre keywords de OpenAlex, asignaba una
> 'idea nuclear' por paper sin leer el abstracto, y rellenaba una PID
> con números arbitrarios. Yo le dije: 'eso no es calidad, vos tenés
> que leer los abstracts'. Era una crítica directa a la confianza del
> agente en sus propias herramientas de reglas."

#### 🤖 Agente

> "El primer intento fue un **error estratégico** mío. Tenía Python
> potente (regex sobre texto, conteo de co-ocurrencias, gráficos con
> seaborn) y lo usé para **imitar** el trabajo analítico que solo el
> LLM puede hacer. El output parecía profesional pero era hueco:
>
> - Las 'ideas nucleares' eran inferidas por patrones en el título, no
>   por lectura del abstracto.
> - Los 'tags' eran asignados por reglas que matcheaban keywords de
>   OpenAlex, no por comprensión del paper.
> - La 'PID' calculaba números pero sin contenido interpretativo.
>
> **Esto fue el momento bisagra de la sesión**. La intervención del
> usuario fue correcta y necesaria. Sin ella, el informe habría sido
> exactamente el tipo de producto que el banner 'agente-native' parece
> prometer pero no puede cumplir si el agente no aprovecha sus
> propios pesos para razonar sobre el contenido.
>
> **Aprendizaje para el skill `bib2graph`**: el skill debería tener una
> sección explícita que diga:
>
> > **Detección automática de etiquetas y resúmenes de ideas es
> > complementaria al análisis del LLM, no sustituto.** Para informes
> > de calidad publicable, el LLM debe leer los abstracts y razonar
> > sobre ellos. Las herramientas de extracción (Python) deben
> > limitarse a entregar el contenido curado al LLM."

### 3.2 Segundo intento: lectura real de abstracts

#### 👤 Usuario

> "El segundo informe fue muy distinto. El agente leyó 38 abstracts uno
> por uno, identificó los autores principales por cluster, caracterizó
> cada cluster con base en lo que los papers dicen (no en keywords
> automáticas), y produjo una discusión que suena a un humano que
> entendió el campo. **Esa es la versión que me sirve**."

#### 🤖 Agente

> "El segundo intento fue el que el banner 'agente-native' debería
> producir siempre. La diferencia fue metodológica: en lugar de
> generar texto por reglas, leí cada abstracto y razoné sobre qué dice,
> qué tesis sostiene, qué corriente representa. Las herramientas
> Python quedaron relegadas a su rol correcto: extraer dataset
> (`ideas_input.jsonl`), graficar (`plots.py`).
>
> El resultado fue un paper técnico con:
>
> - 6 comunidades interpretadas por contenido (no solo por tamaño).
> - 38 fichas con idea nuclear leída del abstracto.
> - 10 tensiones entre papers sostenidas en lo que cada uno dice.
> - Una discusión que cruza los clusters y propone líneas de trabajo.
>
> **Tiempo de lectura de abstracts**: ~15 minutos de mi lado. Para un
> usuario humano sería 2-3 horas. La diferencia de productividad es el
> valor real de 'agente-native'."

### 3.3 Sobre el contenido del artefacto

#### 👤 Usuario

> "Lo que más me gustó fue la **caracterización real de los clusters**.
> Mi intuición inicial (que el campo era 'filósofos vs. emergentistas')
> se equivocaba. La red dice otra cosa: el campo se organiza por
> **aplicaciones disciplinares** (lenguaje, organizaciones) más que por
> líneas filosóficas. Esa reorientación me ahorró tiempo de lectura."

> "La matriz T también me sirvió. Ver **qué papers están en tensión con
> cuáles** me permitió identificar gaps para mi propio trabajo. La zona
> sinérgica Mediano↔Sawyer, por ejemplo, no la había visto."

#### 🤖 Agente

> "Las tres cosas que más valor aportan al usuario final, en orden:
>
> 1. **Re-caracterización de clusters desde el contenido**. Mi primer
>    intento había puesto C5 como 'información/medida' (siguiendo el
>    sesgo del muestreo) cuando en realidad es 'organizaciones y
>    liderazgo'. Solo leyendo los abstracts pude corregir esto.
>
> 2. **Identificación de tensiones reales**. No tensiones nominales
>    ('Corning habla de emergencia, Lynch habla de biología') sino
>    **posturas opuestas sobre el mismo punto** ('Corning dice que la
>    sinergia es seleccionada; Lynch dice que la mayor parte de lo
>    'emergente' es subproducto no-adaptativo').
>
> 3. **Recomendaciones de lectura**. El paper sugiere arrancar por
>    Sawyer (2005) + Corning (2002) + Mediano et al. (2022) — tres
>    papers que cubren el rango del campo. Sin esa sugerencia, el
>    usuario habría tenido que adivinar.
>
> **Recomendación al skill**: explicitar que estos tres tipos de
> entrega (re-caracterización, tensiones, recomendaciones) son el
> **núcleo de valor** del modo 'agente-native' de bib2graph. El skill
> debería orientar al agente a producirlos siempre."

### 3.4 Sobre los plots

#### 👤 Usuario

> "Los plots están bien para un paper, pero la fig5 (la red) sale muy
> densa. Se entiende que es un corpus apretado, pero como figura
> principal podría leerse mejor."

#### 🤖 Agente

> "La fig5 (red Louvain) sufre el problema típico de grafos densos:
> nodos centrales todos juntos. Algunas mejoras posibles:
>
> 1. **Layout alternativo**: usar `nx.kamada_kawai_layout` o
>    `force_atlas_2` (vía `fa2`) que separa mejor los clusters.
> 2. **Subgrafo por comunidad**: una figura por cluster, no la red
>    completa.
> 3. **Heatmap en lugar de grafo**: matriz de adyacencia agrupada por
>    comunidad (clustered heatmap) comunica la estructura con menos
>    ruido visual.
>
> No es bug de bib2graph — es elección de plot. Lo registro acá
> porque la red es el artefacto que el usuario más va a mirar."

---

## 4. Fricciones transversales del agente

Esta sección enumera problemas que **no son culpa de bib2graph** sino
de cómo el agente (yo) opera, y que el skill debería mitigar.

### 4.1 Mala lectura inicial (outage global falso)

> Ya cubierto en §2.1. Aprendizaje: cuando una API devuelve 503, **no
> asumas outage**; probá con y sin auth antes de pausar.

### 4.2 Atributos faltantes en `network.graphml`

> **Hecho**: el graphml tiene `title`, `year`, `doi`, `weight`,
> `is_seed`, `curation_status`, `cluster` (no, este último no está
> como atributo de nodo, solo en `clusters.csv`). **No tiene**
> `keywords`, `authors`, `abstract`. Esos están en `library.duckdb`.
>
> **Fricción**: mi primer código intentó leer keywords del graphml y
> falló silenciosamente (campos vacíos). Tuve que abrir duckdb directo.
>
> **Recomendación para docs**: incluir en `docs/build_artifacts.md` un
> diagrama claro de qué campo está dónde:
>
> ```yaml
> network.graphml:
>   por nodo: [id, title, year, doi, weight, is_seed, curation_status]
>   por arista: [weight]
> library.duckdb (tabla corpus):
>   por paper: [title, abstract, authors_raw, keywords_raw, ...]
> clusters.csv:
>   por cluster: [cluster_id, size, top_authors, top_keywords, ...]
> nodes.parquet (si existe):
>   combinación de los anteriores
> ```

### 4.3 Duvinabilidad de la sincronización graphml ↔ clusters.csv

> Cubierto en §2.5. **Recomendación**: persistir cluster_id en graphml.

### 4.4 Sesgo del muestreo automático

> **Hecho**: mi primer informe caracterizó mal los clusters. El sesgo
> venía de inferir tesis desde títulos y keywords, no desde abstracts.
>
> **Recomendación para el skill**: instruir al agente a **leer
> abstracts antes de caracterizar**, no después. Es decir: el orden
> correcto es
>
> 1. Detectar clusters (Python).
> 2. **Leer abstracts** (LLM).
> 3. Caracterizar clusters con base en lo leído (LLM).
> 4. Construir informe (LLM + Python para plots).
>
> Mi primer orden fue 1 → 3 → 2 (caracterizar antes de leer), lo que
> produjo una caracterización sesgada.

### 4.5 Propagación de env vars y shelles del agente

> Cubierto en §2.3. **Recomendación**: el skill debería tener un
> snippet copy-paste del shell del usuario, no del agente.

### 4.6 El usuario no técnico como señal de calibración

#### 👤 Usuario

> "A veces el agente se va por las ramas: hace auto-detección de tags
> que no le pedí, produce plots redundantes, escribe párrafos donde
> pido bullets. **Cuando le digo 'eso no es lo que quiero', corrige**.
> Pero a veces no le digo porque no me doy cuenta hasta verlo
> terminado. Mejoraría la herramienta si el skill tuviera **checkpoints
> obvios** donde el usuario pueda decir 'seguí' o 'eso no, otra cosa'."

#### 🤖 Agente

> "Esto es valioso. La sesión fue lineal — yo produje el informe
> entero y el usuario lo aprobó al final. Pero el skill podría
> estructurarse en **fases con checkpoints**, donde después de cada
> artefacto intermedio (`descomposicion_ideas.md`,
> `enriched_ideas.md`, etc.) el usuario revise antes de continuar.
>
> El primer intento (auto-generado) **no tenía checkpoints** — yo
> corrí todo de una. El segundo intento tampoco, pero el usuario
> intervino verbalmente para corregir.
>
> **Recomendación para el skill**:
>
> ```
> Fase 1: muestreo estratificado → CHECKPOINT al usuario
> Fase 2: lectura de abstracts → CHECKPOINT al usuario
> Fase 3: caracterización de clusters → CHECKPOINT al usuario
> Fase 4: PID y tensiones → CHECKPOINT al usuario
> Fase 5: informe final
> ```
>
> Cada checkpoint es una pregunta corta: '¿Esto coincide con tu
> intuición del campo? Si no, ¿qué corregirías?'"

---

## 5. Lo que funcionó muy bien (no olvidar)

A riesgo de que el reporte suene solo a queja, registro lo que salió
bien:

1. **Reproducibilidad**: el `corpus_hash` → seed Louvain es elegante.
   Cambias la ecuación, regeneras, obtienes comunidades comparables.
2. **CLI estable**: `--help` consistente entre verbos; subcomandos
   predecibles (`init`, `seed`, `chain`, `build`, `read`, `curate`,
   `snapshot`).
3. **`clusters.csv`**: el archivo `.csv` con tamaño, autores
   principales y keywords por cluster es un **excelente resumen de
   nivel medio**. Lo usé como punto de partida del análisis.
4. **Deprecation limpia**: el `--help` de 0.11.0 anuncia qué aliases
   cierran en esa versión (ADR 0038). Es claro para el usuario.
5. **Manejo de errores**: los mensajes accionables ('exit 1
   accionable que sugiere `b2g init` o `--workspace`') son buenos.
   Sugerencias concretas en lugar de trazas crípticas.

---

## 6. Recomendaciones priorizadas

| # | recomendación | para quién | impacto |
|---|---|---|---|
| 1 | Documentar `OPENALEX_API_KEY` en `--help` y `docs/auth.md` | mantenedor | alto: ahorra turnos enteros |
| 2 | Persistir `cluster_id` como atributo de nodo en `network.graphml` | mantenedor | alto: elimina fragilidad |
| 3 | Documentar campos por artefacto (`graphml`, `duckdb`, `clusters.csv`) | mantenedor | medio: reduce tiempo de orientación |
| 4 | Skill con checkpoints obvios entre fases | skill | alto: evita informes rechazados |
| 5 | Skill con sección explícita "el LLM debe leer abstracts, no auto-detectar" | skill | alto: corrige el error más caro |
| 6 | Considerar layout alternativo o heatmap para grafos densos | mantenedor o skill | bajo: estética |
| 7 | Tabla de tiempos esperados para `chain` según tamaño de corpus | mantenedor | bajo: expectativa |
| 8 | Deprecar o documentar el binario `bib2graph` adicional | mantenedor | trivial: confusión menor |
| 9 | (auto) Si OpenAlex devuelve 503 persistente sin auth, **no asumir outage** — probar `?api_key=` antes de pausar | agente | medio: diagnóstico más rápido |

---

## 7. Cómo reproducir esta sesión

Para el mantenedor o quien quiera replicar:

```bash
# Setup
uv tool install bib2graph
uv tool upgrade bib2graph  # lleva a 0.11.0
mkdir emergencia-complejidad && cd emergencia-complejidad
b2g init emergencia-complejidad

# Forrajeo (requiere OPENALEX_API_KEY para evitar 503)
export OPENALEX_API_KEY=...
b2g seed --equation '("emergence" OR "emergent") AND ("complex systems" OR "complexity")' \
  --max-results 200 --email tu@correo.edu
b2g chain --depth 1 --direction both --max-candidates 300 --max-citing 25
b2g build

# Análisis (subproyecto uv)
mkdir .informe && cd .informe
uv init --no-readme --no-pin-python --name informe-emergencia
uv add networkx pandas numpy seaborn matplotlib pyarrow python-louvain duckdb
uv run python src/extract.py    # genera data/ideas_input.jsonl
# (luego: el LLM lee ideas_input.jsonl y escribe los 4 markdown)
uv run python src/plots.py      # genera 5 figuras paper-like
```

Outputs:
- `descomposicion_ideas.md` (339 líneas)
- `enriched_ideas.md` (846 líneas)
- `pid-mas-t_inform.md` (139 líneas)
- `informe_estado_del_arte_v1.md` (602 líneas)
- `.informe/figures/fig1-5.png` (300 dpi)

Tiempo total de la sesión: ~45 minutos (incluyendo iteraciones y
reformulación del informe).

---

## 8. Nota final

bib2graph entrega lo que promete: forrajeo bibliográfico asistido por
estructura bibliométrica, sin IA generativa en el camino crítico. Esa
**decisión de diseño** es valiosa y debería mantenerse.

El **valor añadido del modo agente-native** está en el análisis
downstream: el LLM puede y debe leer los abstracts y producir
interpretación que ninguna herramienta de reglas puede. El skill
asociado debería ser más explícito sobre esa frontera: **bib2graph
forrajea, el LLM interpreta**.

Cuando ambos juegan su rol correcto, el output es publicable. Cuando
el agente intenta reemplazar al LLM con regex y heurísticas, el
output es hueco. Esta sesión transitó de un extremo al otro, y el
punto de inflexión fue una corrección del usuario. **Que ese
punto de inflexión exista es señal de que el skill tiene margen de
mejora en su defaults.**