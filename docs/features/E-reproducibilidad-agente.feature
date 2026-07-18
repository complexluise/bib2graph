# language: es
# Épica E — Reproducibilidad y agente-native
# Historias PRD §7: E1, E2
# Anclado a: src/bib2graph/cli/commands/snapshot.py, restore.py, status.py
#            src/bib2graph/cli/__init__.py (envelope, exit codes, --workspace global)
# Realidad post-#75: el estado vive en el library.duckdb del workspace; --store ELIMINADA.

Característica: Snapshot reproducible y orquestación agente-native por CLI
  Como investigador y como agente/automatización
  Quiero exportar una foto reproducible y orquestar cada paso por CLI con --json
  Para auditar/reportar la corrida y operar bib2graph sin GUI

  Antecedentes:
    Dado un workspace con un corpus curado
    Y que trabajo dentro de esa carpeta

  # --- E1 · Snapshot reproducible del estado vivo ---
  Escenario: E1 — Exportar un snapshot sellado
    Cuando ejecuto "b2g snapshot create --json"
    Entonces el exit code es 0
    Y "command" es "snapshot create"
    Y se escribe un parquet + "manifest.json" bajo "snapshots/"
    Y "data.corpus_hash" no está vacío
    Y "data.total_papers" es el número de papers del corpus
    Y "snapshot create" NO transiciona el estado del lazo

  Escenario: E1 — Reproducir = re-leer el snapshot, no re-correr la ecuación
    Dado un parquet "corpus.parquet" producido por "b2g snapshot create"
    Y un workspace nuevo distinto
    Cuando ejecuto "b2g snapshot restore --from-corpus corpus.parquet --json"
    Entonces el exit code es 0
    Y "command" es "snapshot restore"
    Y "data.papers_loaded" es el número de papers del parquet
    Y "data.state" es "FILTERED"
    Y la restauración NO hace ninguna llamada a OpenAlex (sin red)
    # snapshot restore preserva la curación (curation_status/is_seed); reproducir NO re-corre la
    # ecuación (ADR 0017). OpenAlex cambia en el tiempo: re-correr es re-investigar, no reproducir.

  Escenario: E1 — El corpus_hash es estable entre corridas (identidad por contenido)
    Dado dos corridas que aceptan los mismos IDs en el mismo corpus
    Cuando comparo "data.corpus_hash" de sus snapshots
    Entonces ambos hashes coinciden
    # R2 (ADR 0017 enmendado): el hash excluye provenance/timestamps e incluye curation_status.

  Escenario: E1 — Restaurar un parquet con schema no canónico falla accionable
    Cuando ejecuto "b2g snapshot restore --from-corpus ajeno.parquet --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)

  # --- E2 · CLI con --json y exit codes para agentes ---
  Escenario: E2 — Cada subcomando emite el envelope versionado
    Cuando ejecuto cualquier subcomando con "--json"
    Entonces la salida es un único objeto JSON
    Y tiene los campos "schema", "ok", "command", "exit_code", "data", "warnings", "error"
    Y "schema" es "1"
    Y en éxito "ok" es true y "error" es null

  Escenario: E2 — Mapeo de exit codes por tipo de error
    # ADR 0021 §D — el decorador @handle_errors mapea por tipo:
    #   0 éxito · 1 uso · 2 datos (DataError) · 3 dependencia (DependencyError/ImportError/
    #   NotImplementedError) · 4 red (httpx.HTTPError) · 5 store bloqueado/corrupto
    #   (StoreLockedError/OSError).
    Cuando un comando falla con un DataError conocido
    Entonces el exit code es 2
    Y "ok" es false
    Y "data" es un objeto vacío
    Y "error.code" y "error.message" describen el fallo de forma accionable

  Escenario: E2 — El error de USO sale SIN envelope JSON
    Cuando ejecuto "b2g seed --store x.duckdb --json"
    Entonces el exit code es 1
    Y NO se emite envelope JSON (Click aborta el parseo antes del comando)
    # --store fue ELIMINADA (#75): produce "No such option: --store" en stderr.

  Escenario: E2 — Sin workspace resoluble, error accionable
    Dado un directorio que no es un workspace y sin B2G_WORKSPACE
    Cuando ejecuto "b2g status" fuera de cualquier workspace
    Entonces el exit code es 1
    Y el mensaje sugiere "b2g init" o "--workspace"

  Escenario: E2 — status expone el mapa del lazo para el agente
    Cuando ejecuto "b2g status --json"
    Entonces el exit code es 0
    Y "data.loop_state" refleja el estado del FSM (SEEDED/FORAGED/FILTERED/BUILT/MONITORED o null)
    Y "data.transitions_available" lista las transiciones del estado actual
    Y "data.curation_available" lista "accept" y "reject" (curación transversal siempre disponible)
    Y "data.round" es el contador de ronda
    Y "data.counts_by_status" tiene los conteos por "curation_status"
    Y "data.workspace" tiene "root" y "source" (de dónde se resolvió el workspace)
    Y "data.networks_cache_stale" indica si la cache de redes quedó obsoleta

  Escenario: E2 — Sin estado entre invocaciones (stateful vía archivo)
    Dado que ejecuté un seed en una invocación previa
    Cuando ejecuto "b2g status --json" en una invocación nueva
    Entonces el estado persiste (vive en el library.duckdb del workspace, no en el proceso)
