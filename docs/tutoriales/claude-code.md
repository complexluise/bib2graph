---
title: Tu primer mapa de investigación (5 min)
---

# Tu primer mapa de investigación (5 minutos)

Cómo armar una **red visual de artículos científicos** sobre un tema que te
interesa, usando un agente de IA para dirigir bib2graph.

!!! info "Qué necesitas"
    - **Un agente de IA** con ejecución de código: Claude, ChatGPT, MiniMax, o similar.
    - **bib2graph instalado** en tu máquina (1 minuto: `pip install bib2graph`).
    - **5 minutos**.

!!! warning "Paso previo: instala bib2graph"
    Abre tu terminal y ejecuta:
    ```bash
    pip install bib2graph
    ```
    
    Verifica que funciona:
    ```bash
    b2g --help
    ```
    
    Si ves la ayuda de comandos, listo. Si no, ve a [Instalación](../getting-started/installation.md).

---

## Paso 1 — Elige un agente

Abre **cualquiera** de estos (con ejecución de código activada):

- **Claude** (web o app)
- **ChatGPT** (Plus, con Code Interpreter)
- **MiniMax** o similar

Lo importante: que pueda ejecutar Python y crear archivos. Nosotros no hacemos vendor locking
a un solo agente — bib2graph funciona igual en todos.

---

## Paso 2 — Plantea el tema al agente

En una conversación nueva, escribe algo así:

!!! example
    ```text
    Tengo bib2graph instalado en mi máquina.
    
    Quiero explorar el estado del arte sobre [TU TEMA].
    
    Usa bib2graph para:
    1. Buscar papers en OpenAlex
    2. Construir una red de referencias compartidas
    3. Mostrar qué comunidades de investigación existen
    
    Mi tema: [ejemplo: métodos de recuperación de información en contextos multilingües]
    ```

El agente va a sugerirte una **ecuación de búsqueda** — una forma de decirle a OpenAlex
exactamente qué buscar. La revisas, ajustas si hace falta.

---

## Paso 3 — El agente construye la red

Cuando la ecuación te cierre, pide al agente:

!!! example
    ```text
    Bien. Ahora ejecuta estos comandos en mi máquina:
    
    1. b2g init mi-sota
    2. cd mi-sota
    3. b2g seed "[TU ECUACION]" --min-year 2015
    4. b2g build
    5. b2g export --format graphml
    
    Muestra la red visualizada y un resumen de las comunidades.
    ```

El agente ejecuta esos comandos por ti — trae papers, identifica qué papers citan
las mismas referencias, agrupa esos papers en comunidades.

**Resultado:** Una imagen de la red (puntos = papers, líneas = referencias compartidas,
colores = comunidades).

---

## Paso 4 — Lee el mapa

Pide al agente:

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

## Paso 5 — Guarda tu trabajo

Tu corpus está en el archivo `.duckdb` dentro de la carpeta `mi-sota/`. Los archivos
`.graphml` están en `exports/`.

Para continuar después:

```bash
cd mi-sota
b2g read list  # Ver papers en el corpus
b2g read top   # Ver papers más centrales
```

Si quieres explorar más tarde desde el agente, carga los archivos GraphML o Parquet en
la conversación y sigue desde ahí.

---

## Listo

En 5 minutos:

✅ Instalaste bib2graph  
✅ Trajiste papers de un tema (con ayuda del agente)  
✅ Viste cómo se relacionan (qué citan en común)  
✅ Identificaste sub-temas / enfoques  
✅ El corpus está guardado en tu máquina  

## Qué sigue

- **Más detalles:** [Tutorial completo — De la pregunta al reporte de SOTA](sota-completo.md)
  — cómo refinar, curar y redactar un análisis riguroso.
- **Referencia completa:** [Todos los comandos de bib2graph](../reference/cli.md).
- **Como librería Python:** [API Python](../reference/python-api.md).
