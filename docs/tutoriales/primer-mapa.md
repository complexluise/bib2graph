---
title: Tu primer mapa de investigación (5 min)
---

# Tu primer mapa de investigación (5 minutos)

Cómo armar una **red visual de artículos científicos** sobre un tema que te
interesa, usando un [asistente de IA](../reference/glosario.md#asistente-de-ia) para dirigir bib2graph.

!!! info "Qué necesitas"
    - **Un asistente de IA con ejecución de código**: Claude, ChatGPT, MiniMax, o similar
      (el chat, no una terminal tuya).
    - **Nada instalado en tu máquina.** El asistente instala bib2graph en su propio
      entorno de ejecución — tú no abres una terminal.
    - **5 minutos.**

---

## Paso 1 — El asistente instala bib2graph y se autodiagnostica

Abre **cualquiera** de estos (con ejecución de código activada): Claude (web o app),
ChatGPT (con Code Interpreter), MiniMax, o similar. Lo importante es que pueda
ejecutar Python y crear archivos — no hacemos vendor locking a un solo asistente.

En una conversación nueva, pégale este mensaje:

!!! example
    ```text
    Instala la librería de Python "bib2graph" (pip install bib2graph) en tu
    entorno de ejecución de código, entiende el CLI corriendo `b2g --help`, y
    confírmame que tienes salida a internet hacia la API de OpenAlex con una
    búsqueda mínima de prueba. Cuéntame si las dos cosas funcionaron.
    ```

Este mensaje hace dos cosas a la vez: instala la herramienta **dentro del entorno
del asistente** (no en tu compu) y te dice, en el momento, si ese asistente sirve para
este camino — sin que tengas que leer una tabla de compatibilidad que se desactualiza.

**Si el asistente confirma las dos cosas:** sigue al Paso 2, en la misma conversación.

**Si algo falla** (no puede instalar, o instala pero no llega a OpenAlex): ese
asistente no sirve para este camino hoy. Prueba con otro — a esta fecha, Claude.ai y
MiniMax (planes pagos) lo resuelven bien; el entorno de ejecución de código de
ChatGPT no tiene salida a internet. Esto puede cambiar con el tiempo; por eso el
diagnóstico de arriba es la forma de saberlo, no esta lista.

---

## Paso 2 — Plantea tu tema

Ya en la misma conversación (bib2graph ya está instalado), cuéntale tu tema:

!!! example
    ```text
    Quiero explorar el estado del arte sobre [TU TEMA].
    
    Usa bib2graph para:
    1. Buscar papers en OpenAlex
    2. Construir una red de referencias compartidas
    3. Mostrar qué comunidades de investigación existen
    
    Mi tema: [ejemplo: métodos de recuperación de información en contextos multilingües]
    ```

El asistente va a sugerirte una **ecuación de búsqueda** — una forma de decirle a OpenAlex
exactamente qué buscar. La revisas, ajustas si hace falta.

---

## Paso 3 — El asistente construye la red

Cuando la ecuación te cierre, pide al asistente:

!!! example
    ```text
    Bien. Ahora ejecuta estos comandos:
    
    1. b2g init mi-sota
    2. cd mi-sota
    3. b2g seed "[TU ECUACION]" --min-year 2015
    4. b2g build
    5. b2g export --format graphml
    
    Muestra la red visualizada y un resumen de las comunidades.
    ```

El asistente ejecuta esos comandos por ti — trae papers, identifica qué papers citan
las mismas referencias, agrupa esos papers en comunidades.

**Resultado:** Una imagen de la red (puntos = papers, líneas = referencias compartidas,
colores = comunidades).

---

## Paso 4 — Lee el mapa

Pide al asistente:

!!! example
    ```text
    Para cada comunidad en la red:
    - Nombre (síntesis del enfoque)
    - Keywords principales
    - Top 3 papers más centrales (autor, año)
    
    Muestra una tabla.
    ```

Ya tienes un **primer mapa mental del campo** — qué tendencias existen, quiénes
son los referentes, dónde están las divergencias.

---

## Paso 5 — Descarga tu trabajo antes de cerrar

El corpus vive en el **entorno del asistente**, no en tu compu — y ese entorno se puede
apagar si cierras la conversación o la dejas inactiva mucho tiempo. Antes de irte,
pídele al asistente:

!!! example
    ```text
    Dame para descargar el archivo .duckdb del workspace y los .graphml de exports/.
    ```

Guarda esos archivos en tu compu. Para continuar después:

- Empieza una conversación nueva, repite el Paso 1, y súbele el `.duckdb` que
  descargaste para que el asistente siga desde donde quedaste (`b2g read list`,
  `b2g read top` sobre ese mismo workspace).
- O carga directamente los `.graphml` en una conversación nueva y explora la red
  desde ahí, sin reabrir bib2graph.

---

## Listo

En 5 minutos:

✅ Tu asistente instaló bib2graph — tú no tocaste una terminal  
✅ Trajiste papers de un tema (con ayuda del asistente)  
✅ Viste cómo se relacionan (qué citan en común)  
✅ Identificaste sub-temas / enfoques  
✅ Descargaste el corpus a tu máquina  

## Qué sigue

- **Profundiza paso a paso:** las [Guías (how-to)](../guias/index.md) —
  ecuación de búsqueda, forrajeo, curación PRISMA, lectura de redes y
  redacción del reporte.
- **Referencia completa:** [Todos los comandos de bib2graph](../reference/cli.md).
- **Como librería Python:** [API Python](../reference/python-api/index.md).
