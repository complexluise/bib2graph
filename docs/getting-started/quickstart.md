---
title: Quickstart
---

# Quickstart

De una ecuación de búsqueda a un GraphML, sin escribir código.

## El hilo: 5 pasos para no repetir tu related work de memoria

Cuando escribís el *related work* de memoria, repetís los papers que ya conocés y
dejás afuera —sin querer— los que no. bib2graph existe para romper ese sesgo:
convierte tu búsqueda en un corpus, redes de citación y un **orden de lectura**
con procedencia. Te lleva **hasta la lectura** y se detiene ahí; la interpretación
y la escritura quedan tuyas.

El ciclo de comandos que ves abajo es este hilo, paso a paso:

1. **Lista ingenua → barrido.** Partís de tu ecuación de búsqueda y sembrás un
   primer corpus (`seed`). Después lo expandís siguiendo las citaciones, para que
   entren los papers que tu búsqueda inicial no vio (`chain`).
2. **Puntos ciegos.** El barrido trae candidatos que *no* estaban en tu lista
   mental. Esos son, justamente, los que tendías a olvidar.
3. **Curás vos.** Aceptás o rechazás cada candidato con criterios explícitos
   (`curate`). Vos decidís qué entra; bib2graph solo te da la estructura.
4. **Lectura dirigida.** Construís las redes (`build`) y pedís el orden de lectura:
   los papers más centrales primero (`read top`). No leés al azar ni de memoria:
   leés por estructura.
5. **Escritura narrativa.** Con el corpus, las redes y el orden de lectura en la
   mano, escribís tu revisión. Ese paso es **tuyo** — bib2graph no interpreta ni
   redacta por vos.

Las [Guías](../guias/index.md) desarrollan cada paso en detalle. Lo que sigue es la
versión mínima para verlo funcionar de punta a punta.

## Antes de empezar: conseguí tu API key de OpenAlex

bib2graph siembra el corpus desde [OpenAlex](https://openalex.org). Funciona **sin
credenciales** (el *polite pool*), pero para cualquier trabajo real conviene una **API key
gratuita**: desde 2026 OpenAlex usa un modelo de créditos, y sin key el tier gratis
(~100 créditos/día) se agota rápido y empezás a ver errores `429` (rate limit) en pleno
forrajeo. La key sube el límite y evita esos cortes.

**1. Conseguí la key (gratis).** Pedila en [openalex.org/pricing](https://openalex.org/pricing)
(o desde tu cuenta de OpenAlex). Es opcional pero recomendada.

**2. Configurala como variable de entorno.** bib2graph la lee de `OPENALEX_API_KEY`:

=== "Linux / macOS"

    ```bash
    export OPENALEX_API_KEY="tu-key-aquí"
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:OPENALEX_API_KEY="tu-key-aquí"
    ```

**3. Declará tu email para el polite pool.** Independiente de la key, pasá `--email tu@correo.org`
a los comandos que pegan a OpenAlex (`seed`, `chain`, `build`): mueve tus peticiones al *polite
pool* de OpenAlex, con un límite más sano. No es un secreto (es un identificador de cortesía).

!!! tip "¿Sin key?"
    Podés hacer el Quickstart sin key para probar. Si ves un error `429 (Too Many Requests)`,
    es la señal de que necesitás configurar `OPENALEX_API_KEY` (y/o `--email`).

## Desde el CLI

<!-- termynal -->

```
$ b2g init mi-investigacion
Carpeta de investigación creada en ./mi-investigacion
$ cd mi-investigacion
$ b2g seed --equation '"unequal ecological exchange"' --email tu@correo.org --max-results 50
Sembrando desde OpenAlex...        # paso 1: lista ingenua
---> 100%
52 papers en el corpus
$ b2g chain --direction both --max-candidates 300 --email tu@correo.org
Siguiendo citaciones...            # paso 1-2: barrido + puntos ciegos
---> 100%
+180 candidatos para revisar
$ b2g curate dump                  # paso 3: curás vos (revisás el CSV offline)
Candidatos volcados a ./exports/curacion.csv
$ b2g curate apply curacion.csv
Aplicadas tus decisiones: 210 aceptados · 22 rechazados
$ b2g build                        # paso 4: redes + orden de lectura
Construyendo las redes...
---> 100%
Listas: acoplamiento · co-citación · co-autoría · instituciones · co-keywords
$ b2g read top --kind bibliographic_coupling
Orden de lectura (papers más centrales primero):
 1. ...
$ b2g export --format graphml
Exportadas a ./exports/*.graphml
```

Pasaste de una ecuación a un corpus curado, redes en GraphML y un orden de lectura,
sin escribir código. Lo que hagas con esa lectura —el **paso 5**, la escritura— es
tuyo.

Cada comando acepta `--json` para orquestarlo desde scripts o agentes. Para la
lista completa de comandos y opciones, corré `b2g --help` o mirá la
[referencia del CLI `b2g`](../reference/cli.md).

!!! tip "Una carpeta por investigación"
    `b2g init` crea una carpeta autocontenida con tu corpus, tus redes y tus
    exports adentro. Corré el resto de los comandos **dentro de esa carpeta**
    (por eso el `cd` después de `init`): así cada investigación queda separada y
    todo lo que generás se guarda junto.

## Desde Python

```python
from pathlib import Path
from bib2graph import OpenAlexSource, DuckDBStore, Networks, GraphMLExporter

# email = polite pool; api_key se toma de OPENALEX_API_KEY si no se pasa
corpus = OpenAlexSource(email="tu@correo.org").seed('"unequal ecological exchange"').corpus
store = DuckDBStore(Path("biblioteca.duckdb"))
store.persist(corpus)

for red in Networks.quick(store.load()):
    GraphMLExporter().export(red.graph, red.metrics, out_dir=Path(f"redes/{red.spec.kind}"))
```

## Siguiente paso

- Profundizá en flujos concretos en las [Guías](../guias/index.md).
- Entendé el modelo por dentro en [Arquitectura](../ARCHITECTURE.md).
