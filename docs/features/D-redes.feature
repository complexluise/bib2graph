# language: es
# Épica D — Proyectar a redes (el final sigue siendo las redes)
# Historias PRD §7: D1, D2, D3 (no-CLI), D4
# Anclado a: src/bib2graph/cli/commands/build.py, networks.py, export.py, enrich.py
#            src/bib2graph/networks/facade.py, analyzer.py, spec.py
# Realidad post-#75: workspace por cwd; no existe --store.

Característica: Proyectar el corpus a redes bibliométricas y exportarlas
  Como investigador
  Quiero proyectar el corpus a redes con métricas y comunidades, y exportarlas
  Para analizar la estructura intelectual del campo en Gephi/VOSviewer/pandas

  Antecedentes:
    Dado un workspace con un corpus curado (estado FILTERED o posterior)
    Y que trabajo dentro de esa carpeta

  # --- D1 · Cinco proyecciones ---
  Escenario: D1 — Construir las redes principales con build
    Cuando ejecuto "b2g build --json"
    Entonces el exit code es 0
    Y "command" es "build"
    Y "data.networks_built" es 4 o 5
    Y "data.networks" incluye los kinds "bibliographic_coupling", "author_collab", "institution_collab" y "keyword_cooccurrence"
    Y cada red escribe "networks/<kind>/network.graphml" y "networks/<kind>/metrics.json"
    Y tras el build el estado del lazo transiciona a "BUILT"
    Y "networks/.corpus_hash" queda sellado con el hash del corpus filtrado

  Escenario: D1 — La co-citación aparece solo tras enriquecer (cited_by_id)
    Dado un corpus sin "cited_by_id" poblado
    Cuando ejecuto "b2g enrich --max-citing 25 --json"
    Y luego ejecuto "b2g build --json"
    Entonces "data.networks_built" es 5
    Y "data.networks" incluye el kind "cocitation"
    # Networks.quick agrega cocitación solo si algún paper tiene cited_by_id (Hito 8b).
    # enrich NO transiciona el lazo (ortogonal al FSM).

  Escenario: D1 — Filtrar el corpus por curación antes de proyectar
    Cuando ejecuto "b2g build --corpus-scope accepted --json"
    Entonces el exit code es 0
    Y "data.corpus_scope" es "accepted"
    # accepted = semillas (is_seed=True) + papers aceptados. NO confundir con NetworkSpec.scope.

  Escenario: D1 — Scope que deja 0 papers no es error
    Cuando ejecuto "b2g build --corpus-scope seeds_only --json" sobre un corpus sin semillas
    Entonces el exit code es 0
    Y "data.networks_built" es 0
    Y "warnings" sugiere correr "b2g curate" o usar "--corpus-scope=all"

  # --- D2 · Métricas y comunidades ---
  Escenario: D2 — Cada red emite métricas y comunidades
    Dado que ejecuté "b2g build --json"
    Cuando leo "networks/<kind>/metrics.json"
    Entonces incluye "density", "nodes" y "edges"
    Y las redes de paper (bibliographic_coupling, cocitation) con comunidades escriben "networks/<kind>/clusters.csv"
    Y en el envelope la entrada de esa red suma "clusters_csv"
    # Comunidades por Louvain (sembrado por corpus_hash → reproducible, R2).
    # author_collab/institution_collab/keyword_cooccurrence NO emiten clusters.csv por diseño.

  # --- D3 · Asortatividad + composición de comunidades + disclaimer de proxy ---
  @pendiente @no-implementado
  Escenario: D3 — Asortatividad por atributo y composición de comunidades, con disclaimer de proxy
    # PRD §7 D3 pide asortatividad (por atributo categórico configurable y por grado) y la
    # composición de cada comunidad por ese atributo, con el disclaimer si el atributo es proxy.
    # AS-BUILT: assortativity() y community_composition() EXISTEN como funciones puras en
    # networks/analyzer.py (con 'proxy_disclaimer') y se re-exportan en networks/__init__.py,
    # PERO no hay camino CLI: facade._build_artifact fija siempre assortativity=None y NO
    # consume NetworkSpec.assortativity_attribute; ni build, ni networks, ni export las invocan.
    # Es API de librería (Python), no de CLI.
    Cuando ejecuto un comando que calcule asortatividad/composición con el disclaimer de proxy
    Entonces obtengo el coeficiente por atributo y por grado, y la composición por comunidad
    Y, si el atributo es un proxy, un "proxy_disclaimer" lo advierte
    # Gap real: cablear assortativity_attribute en el camino del artefacto y exponerlo en el CLI.

  # --- D4 · Export GraphML/CSV ---
  Escenario: D4 — Exportar las redes a GraphML
    Dado que ejecuté "b2g build --json"
    Cuando ejecuto "b2g export --format graphml --json"
    Entonces el exit code es 0
    Y "command" es "export"
    Y "data.format" es "graphml"
    Y los archivos se escriben bajo "exports/<kind>/network.graphml"
    Y "export" NO transiciona el estado del lazo

  Escenario: D4 — Exportar las redes a CSV (nodos y aristas)
    Dado que ejecuté "b2g build --json"
    Cuando ejecuto "b2g export --format csv --json"
    Entonces el exit code es 0
    Y "data.format" es "csv"
    Y por cada red se escriben "nodos.csv" y "aristas.csv"

  Escenario: D4 — Exportar sin haber construido falla accionable
    Dado un workspace sin artefactos en "networks/"
    Cuando ejecuto "b2g export --format graphml --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)
    # "No hay artefactos de build. Ejecutá primero b2g build."

  # --- D (capa declarativa) · Redes ad-hoc desde YAML ---
  Escenario: D1 — Construir redes declarativas desde un YAML (networks --spec)
    Dado un archivo "redes.yaml" con la clave raíz "networks:" (lista de NetworkSpec)
    Cuando ejecuto "b2g networks --spec redes.yaml --json"
    Entonces el exit code es 0
    Y "command" es "networks"
    Y "data.networks" tiene una entrada por red definida en el YAML
    Y "networks --spec" NO transiciona el lazo ni sella "networks/.corpus_hash"

  Escenario: D1 — YAML de redes malformado o spec inválida
    Dado un "redes.yaml" con un campo desconocido (extra="forbid")
    Cuando ejecuto "b2g networks --spec redes.yaml --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)
