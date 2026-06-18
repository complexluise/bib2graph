# language: es
# Épica A — Sembrar con ecuaciones de búsqueda (consciente y estándar)
# Historias PRD §7: A1, A2, A3, A4, A5
# Anclado a: src/bib2graph/cli/commands/seed.py, status.py, snapshot.py
# Realidad post-#75: el estado vive en el library.duckdb del workspace; no existe --store.

Característica: Sembrar el corpus desde la ecuación de búsqueda
  Como investigador
  Quiero partir del artefacto estándar (la ecuación) o de papers semilla
  Para definir mi corpus de forma consciente y reproducible

  Antecedentes:
    Dado un workspace recién creado con "b2g init mi-investigacion"
    Y que trabajo dentro de esa carpeta (el workspace se resuelve por cwd)

  # --- A1 · Definir el corpus con una ecuación de búsqueda ---
  Escenario: A1 — Sembrar desde una ecuación cruda
    Cuando ejecuto "b2g seed --equation 'unequal exchange' --max-results 50 --json"
    Entonces el exit code es 0
    Y el envelope tiene "schema" igual a "1"
    Y "command" es "seed"
    Y "data.papers_added" es un entero >= 0
    Y "data.total_papers" es un entero >= "data.papers_added"
    Y "data.reseeded" es false
    Y "data.round" es 1

  # --- A1 (variante) · Sembrar parametrizado por YAML versionable ---
  Escenario: A1 — Sembrar desde un YAML declarativo (equation.yaml)
    Dado un archivo "equation.yaml" con la clave raíz "equation:" (modelo EquationSpec)
    Cuando ejecuto "b2g seed --spec equation.yaml --json"
    Entonces el exit code es 0
    Y "data.executed_query" está presente (mismo resultado que --equation + flags)
    Y "data.round" es 1

  Escenario: A1 — Modos de seed mutuamente excluyentes
    Cuando ejecuto "b2g seed --equation 'x' --from-bib semillas.bib"
    Entonces el exit code es 1
    # Error de USO: Click aborta antes del comando; sale SIN envelope JSON (mensaje en stderr).

  Escenario: A1 — Sin ningún modo de seed
    Cuando ejecuto "b2g seed --json"
    Entonces el exit code es 1
    # UsageError: "Debés especificar un modo: --equation / --spec / --from-bib."

  # --- A2 · Query ejecutada visible + reporte de traducción ---
  Escenario: A2 — La query ejecutada y el reporte de traducción quedan visibles
    Cuando ejecuto "b2g seed --equation 'unequal exchange' --exclude 'gas exchange' --json"
    Entonces el exit code es 0
    Y "data.executed_query" contiene la query OpenAlex efectivamente ejecutada
    Y la exclusión queda registrada en "data.translation_report"
    Y "warnings" refleja "data.translation_report" (ejercicio consciente, no silencioso)
    # La negación va DENTRO de title_and_abstract.search:((query) AND NOT "gas exchange").

  Escenario: A2 — El filtro de año se reporta en la traducción
    Cuando ejecuto "b2g seed --equation 'unequal exchange' --min-year 2010 --max-year 2020 --json"
    Entonces el exit code es 0
    Y "data.executed_query" incluye "from_publication_date:2010-01-01"
    Y "data.executed_query" incluye "to_publication_date:2020-12-31"
    # Ciclo 10 (#50): --min-year/--max-year filtran de verdad contra OpenAlex.

  # --- A3 · Sembrar desde papers semilla (BibTeX, sin red) ---
  Escenario: A3 — Sembrar desde un archivo BibTeX local sin red
    Dado un archivo "semillas.bib" válido y el extra [bibtex] instalado
    Cuando ejecuto "b2g seed --from-bib semillas.bib --json"
    Entonces el exit code es 0
    Y "data.papers_added" es un entero >= 0
    Y el envelope NO incluye "data.executed_query" (no aplica a BibTeX)
    Y el envelope NO incluye "data.translation_report"

  Escenario: A3 — --from-bib rechaza flags de OpenAlex
    Cuando ejecuto "b2g seed --from-bib semillas.bib --max-results 10"
    Entonces el exit code es 1
    # UsageError: los flags de OpenAlex son exclusivos de --equation/--spec.

  Escenario: A3 — Falta el extra [bibtex]
    Dado que bibtexparser NO está instalado
    Cuando ejecuto "b2g seed --from-bib semillas.bib --json"
    Entonces el exit code es 3
    Y "error.code" indica una dependencia faltante (DependencyError)
    # Sugiere: uv sync --extra bibtex.

  Escenario: A3 — Archivo .bib inexistente o malformado
    Cuando ejecuto "b2g seed --from-bib no-existe.bib --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)

  # --- A4 · Ecuación registrada y versionada con la corrida ---
  Escenario: A4 — La ecuación queda registrada para reportar y reproducir
    Dado que sembré con "b2g seed --equation 'unequal exchange' --json"
    Cuando ejecuto "b2g snapshot --json"
    Entonces el exit code es 0
    Y se escribe un parquet + "manifest.json" bajo "snapshots/"
    Y "data.corpus_hash" no está vacío
    # El Manifest sella equations/query/filtros; la procedencia vive en la columna provenance.

  # --- A5 · Ecuaciones que mutan entre iteraciones (berrypicking) + acumular ---
  Escenario: A5 — Re-sembrar con otra ecuación acumula sobre lo curado
    Dado que sembré y curé una primera ronda en el mismo workspace
    Cuando ejecuto "b2g seed --equation 'ecological debt' --json"
    Entonces el exit code es 0
    Y "data.reseeded" es true
    Y "data.round" es 2
    Y "data.total_papers" incluye lo acumulado de la ronda anterior
    # reseed: loop-back a SEEDED, ronda++, sin perder la biblioteca viva (ADR 0016).

  Escenario: A5 — El estado del lazo refleja la ronda
    Dado que re-sembré (segunda ronda)
    Cuando ejecuto "b2g status --json"
    Entonces el exit code es 0
    Y "data.loop_state" es "SEEDED"
    Y "data.round" es 2
    Y "data.workspace.root" apunta a la carpeta del workspace resuelto
