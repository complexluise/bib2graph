---
title: Quickstart
---

# Quickstart

De una ecuación de búsqueda a un GraphML, sin escribir código.

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
Workspace creado en ./mi-investigacion
$ cd mi-investigacion
$ b2g seed --equation '"unequal ecological exchange"' --email tu@correo.org --max-results 50
Sembrando desde OpenAlex...
---> 100%
52 papers en el corpus
$ b2g build
Construyendo las redes...
---> 100%
Listas: acoplamiento · co-citación · co-autoría · instituciones · co-keywords
$ b2g export --format graphml
Exportadas a ./redes/*.graphml
```

En tres pasos pasaste de una ecuación a redes en GraphML, sin escribir código.

Cada comando acepta `--json` para orquestarlo desde scripts o agentes. Para la
lista completa de comandos y opciones, corré `b2g --help` o mirá la
[referencia del CLI `b2g`](../reference/cli.md).

!!! tip "Workspace por investigación"
    `b2g init` crea una carpeta autocontenida (`workspace.json` + base de datos +
    redes/snapshots/exports). Todos los comandos resuelven el workspace desde el
    directorio actual — por eso el `cd` después de `init`.

## Desde Python

```python
from pathlib import Path
from bib2graph import OpenAlexSource, DuckDBStore, Networks, GraphMLExporter

# email = polite pool; api_key se toma de OPENALEX_API_KEY si no se pasa (ADR 0012)
corpus = OpenAlexSource(email="tu@correo.org").seed('"unequal ecological exchange"').corpus
store = DuckDBStore(Path("biblioteca.duckdb"))
store.persist(corpus)

for red in Networks.quick(store.load()):
    GraphMLExporter().export(red.graph, red.metrics, out_dir=Path(f"redes/{red.spec.kind}"))
```

## Siguiente paso

- Profundizá en flujos concretos en las [Guías](../guias/index.md).
- Entendé el modelo por dentro en [Arquitectura](../ARCHITECTURE.md).
