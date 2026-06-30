---
title: Tu primera red bibliométrica con bib2graph en Claude
---

# Tu primera red bibliométrica con bib2graph en Claude

Este tutorial lleva, partiendo de cero, a construir un **primer mapa de
citaciones** sobre un tema elegido — sin instalar nada y sin escribir código.
El truco: no se utiliza bib2graph directamente, sino que **se le pide a Claude que lo use
por la persona** en su entorno de ejecución de código.

Al terminar se tendrá un corpus de papers, una red de acoplamiento bibliográfico
con sus comunidades, y se entenderá el **lazo** de trabajo. Es para *aprender
haciendo*; si ya se sabe qué se quiere y se busca la receta de un reporte completo, véase la guía [Cómo elaborar un reporte de estado del arte](../guias/reporte-estado-del-arte.md).

!!! info "Qué se necesita"
    - Una sesión de **Claude (web o app) con ejecución de código activada**
      (la herramienta de *Code Execution / análisis*, que permite a Claude
      correr Python y crear archivos).
    - 15 minutos.
    - *Opcional pero recomendado:* una **API key de OpenAlex** (gratuita) si se van a
      traer más de ~100 papers. Sin ella funciona, pero más lento y con límites.

!!! warning "Alpha"
    bib2graph está en `0.x`: la interfaz puede cambiar. Úsalo para explorar y
    validar, no como dependencia estable todavía.

---

## El modelo mental en una frase

En Claude web, **cada conversación es una mesa de trabajo nueva**. Claude instala
bib2graph, siembra el corpus, construye las redes y devuelve las figuras y los
archivos — todo dentro de esa charla. Se dirige con lenguaje natural; bib2graph
hace el trabajo determinista por debajo.

```
usuario (en lenguaje natural)
        │  "armame una red de acoplamiento sobre X"
        ▼
   Claude  ── instala y ejecuta bib2graph ──►  OpenAlex
        │                                          │
        │  ◄──── corpus + redes + figuras ─────────┘
        ▼
   archivos que se descargan (el "guardado")
```

## Paso 1 — Planteale el tema a Claude

Se abre una conversación y se describe qué se quiere explorar. No hace falta que se sepa la
ecuación de búsqueda: Claude ayuda a armarla.

!!! example "Prompt de arranque"
    ```text
    Quiero explorar el estado del arte sobre [TU TEMA].
    Usá la librería bib2graph (instalala con pip) para armar una red de
    acoplamiento bibliográfico desde OpenAlex.
    Antes de sembrar, proponeme una ecuación de búsqueda y discutámosla.
    ```

Se reemplaza `[TU TEMA]` por algo concreto, por ejemplo *"métodos de generación de
electricidad más eficientes que la turbina de vapor"*.

## Paso 2 — Afiná la ecuación de búsqueda

Claude propone una **ecuación de tres conceptos** (tema ∧ enfoque ∧
términos específicos) con sinónimos. Se la lee y se ajusta: se agrega un término que importe, se saca uno que ensucie. Este ida y vuelta es parte del método — la
pregunta y la búsqueda **mutan** mientras se piensa.

!!! tip "Una buena ecuación es angosta a propósito"
    Si se pide algo demasiado genérico ("energía"), el corpus se ahoga. Mejor un
    eje claro y unos pocos términos específicos que delimiten el campo.

## Paso 3 — Sembrá y construí la red

Cuando la ecuación cierre, se le pide a Claude que ejecute el lazo.

!!! example "Prompt"
    ```text
    Perfecto. Sembrá hasta 200 papers desde 2015, construí la red de
    acoplamiento bibliográfico y detectá comunidades con Louvain.
    Mostrame la red coloreada por comunidad y cuántos papers cayó en cada una.
    ```

Por debajo, Claude corre el equivalente a este lazo de bib2graph:

```python
from bib2graph import OpenAlexSource, Networks
from bib2graph.networks.spec import NetworkSpec
from bib2graph.constants import NetworkKind

src = OpenAlexSource(email="usuario@ejemplo.org", max_results=200)
corpus = src.seed(tu_ecuacion, min_year=2015).corpus

spec = NetworkSpec(kind=NetworkKind.BIBLIOGRAPHIC_COUPLING,
                   clustering="louvain")
art = Networks.build(corpus, spec)   # art.graph, art.communities, art.metrics
```

Se recibe una **imagen de la red** (cada punto un paper; cada línea,
referencias compartidas; cada color, una comunidad) y un resumen: número de
nodos, aristas y el tamaño de cada comunidad.

!!! note "Qué es el acoplamiento bibliográfico"
    Dos papers se *acoplan* si citan las mismas referencias. Cuantas más
    comparten, más cerca quedan. Las comunidades que aparecen suelen ser
    **sub-temas o escuelas** del campo. Es la red "barata": no requiere un
    segundo nivel de descargas.

## Paso 4 — Leé el mapa

Se le pide a Claude que ponga nombre a las comunidades a partir de sus keywords
dominantes, y que muestre los papers más centrales (los de mayor grado) de
cada una.

!!! example "Prompt"
    ```text
    Nombrá cada comunidad según sus keywords y listame los 3 papers más
    centrales de cada una, con título y año.
    ```

Eso da, en una pantalla, el **plano del campo**: qué grandes familias existen
y cuáles son sus trabajos de referencia. Ya se tiene el primer mapa.

## Paso 5 — Guardá tu trabajo

!!! warning "El entorno es efímero"
    Cuando se cierre la conversación, la mesa de trabajo se borra. La promesa de
    bib2graph de *"biblioteca que persiste y crece entre sesiones"* **no se
    cumple sola en Claude web**: se tienen que llevar los archivos.

Se piden los exports en formatos abiertos y se descargan:

!!! example "Prompt"
    ```text
    Exportá el corpus a Parquet, la red a GraphML y un CSV con
    paper → comunidad → grado. Pasámelos para descargar.
    ```

El `GraphML` se abre después en [Gephi](https://gephi.org) o Cytoscape para
explorar la red a mano. El `Parquet` es la **semilla guardada**: en una próxima
conversación se la sube a Claude y se sigue desde ahí.

## Qué se aprendió

- A dirigir bib2graph **conversacionalmente** desde Claude, sin escribir código.
- El lazo mínimo: **pregunta → ecuación → siembra → red de acoplamiento →
  comunidades → lectura**.
- Que en Claude web **el archivo exportado es la memoria**: sin descarga, no hay
  persistencia.

## Siguientes pasos

- [Cómo elaborar un reporte de estado del arte](../guias/reporte-estado-del-arte.md)
  — la receta completa hasta un informe con tensiones y conclusiones.
- [Quickstart](../getting-started/quickstart.md) — el mismo lazo, pero desde el CLI
  `b2g` en la propia máquina.
- [Referencia del CLI `b2g`](../reference/cli.md) — todos los comandos.

!!! tip "¿Se va a usar seguido?"
    Para un uso repetido y con biblioteca persistente de verdad, conviene correr
    bib2graph en la máquina (o con **Claude Code** y la skill incluida, `b2g skill
    add`), donde el corpus en DuckDB sí vive entre sesiones. Claude web es ideal
    para explorar; el CLI local, para sostener una investigación en el tiempo.
