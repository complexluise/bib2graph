---
title: Tu primer mapa de investigación en Claude (5 min)
---

# Tu primer mapa de investigación en Claude

Cómo armar, sin instalar nada, una **red visual de artículos científicos** sobre
un tema que te interesa. Pura conversación — Claude hace el trabajo técnico por vos.

!!! info "Qué necesitás"
    - **Claude (web o app)** — con ejecución de código activada (la herramienta de
      análisis/Code Execution).
    - **5 minutos**.
    - Nada más. Sin instalación, sin código, sin API keys.

---

## Paso 1 — Decile a Claude qué tema te interesa

Abrí una conversación y escribí algo así:

!!! example
    ```text
    Quiero explorar el estado del arte sobre [TU TEMA].
    
    Usá bib2graph para traerme artículos desde OpenAlex, 
    armar una red de referencias compartidas y mostrarme 
    qué comunidades de investigación existen.
    
    Mi tema: [ejemplo: "métodos de recuperación de información en contextos multilingües"]
    ```

Claude va a sugerirte una **ecuación de búsqueda** — básicamente, cómo pedirle
a Google Scholar que busque exactamente lo que querés. La revisás, ajustás si
hace falta, y listo.

---

## Paso 2 — Claude trae los papers y construye la red

Cuando la ecuación te cierre, decile:

!!! example
    ```text
    Dale, vamos. Traé hasta 150 papers desde 2015, construí 
    la red y mostrá las comunidades.
    ```

Claude hace todo por debajo — trae papers, identifica qué papers citan las
mismas referencias, agrupa esos papers en comunidades (como si fueran "escuelas"
o "enfoques" dentro del tema).

**Resultado:** Una imagen donde ves la red (puntos = papers, líneas = referencias
compartidas, colores = comunidades).

---

## Paso 3 — Leé el mapa

Pedile a Claude:

!!! example
    ```text
    Nombrá cada comunidad y listá los 3 papers más importantes 
    de cada una (autor, año, qué hacen).
    ```

Listo. **Ya tenés un primer mapa mental del campo** — qué tendencias existen,
quiénes son los referentes, dónde están las divergencias.

---

## Paso 4 — Descargá tu trabajo

Nada persiste cuando cerrás la conversación. Pedile a Claude:

!!! example
    ```text
    Descargá todo: la red en formato GraphML, una lista de 
    papers en CSV, una imagen de la red.
    ```

Guardá esos archivos. Si querés seguir investigando después en otra conversación
(o en tu máquina), tenés la semilla guardada.

---

## Listo

En 5 minutos:

✅ Trajiste papers de un tema  
✅ Viste cómo se relacionan (qué citan en común)  
✅ Identificaste sub-temas / enfoques  
✅ Guardaste los archivos  

## Qué sigue

- **Más detalles:** [Tutorial completo — De la pregunta al reporte de SOTA](sota-completo.md) — cómo refinar la búsqueda, curar papers y redactar un análisis serio.
- **Tu máquina:** Si lo vas a hacer seguido, conviene instalar bib2graph localmente. Mira el [Quickstart](../getting-started/quickstart.md).
- **Referencia:** [Todos los comandos de bib2graph](../reference/cli.md).
