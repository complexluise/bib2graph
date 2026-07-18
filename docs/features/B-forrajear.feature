# language: es
# Épica B — Forrajear: chaining asistido por estructura bibliométrica (sin IA)
# Historias PRD §7: B1, B2, B3, B4 (RETIRADA)
# Anclado a: src/bib2graph/cli/commands/chain.py
# Realidad post-#75: workspace por cwd; no existe --store.

Característica: Forrajear con chaining backward/forward rankeado por scent
  Como investigador
  Quiero expandir el corpus con las referencias y los citantes de mis semillas
  Para no hacer snowballing a mano (Wohlin) y revisar primero lo más relevante

  Antecedentes:
    Dado un workspace con un corpus sembrado (estado SEEDED)
    Y que trabajo dentro de esa carpeta

  # --- B1 · Backward + forward chaining automáticos ---
  Escenario: B1 — Chaining en ambas direcciones
    Cuando ejecuto "b2g chain --direction both --depth 1 --max-citing 25 --json"
    Entonces el exit code es 0
    Y "command" es "chain"
    Y "data.candidates_found" es un entero >= 0
    Y "data.direction" es "both"
    Y "data.depth" es 1
    Y tras el chain el estado del lazo transiciona a "FORAGED"
    # #269: "data.candidates_found" es el TOTAL de candidatos rankeados (backward observados +
    # forward materializados, recortado por --max-candidates), NO el nº de filas del corpus.
    # Por eso NO se sostiene "total_papers >= candidates_found": en backward puro los candidatos
    # observados pueden exceder el corpus (que no crece — opción B, #54). candidates_found es
    # independiente de total_papers.

  Escenario: B1 — chain forward puebla cited_by_id de las semillas alcanzadas (ADR 0048)
    # #270/ADR 0048: el forrajeo hacia adelante ya trae los citantes; con esto completa además
    # "cited_by_id" de las semillas (unión idempotente vía Corpus.merge), dejando listo el insumo
    # del CoCitationProjector. Así el lazo seed → chain forward → curate accept → build arma la red
    # de co-citación SIN enrich. Anclado a src/bib2graph/foraging/forager.py::_build_seed_cited_by_updates.
    Dado un corpus sembrado sin "cited_by_id" poblado
    Cuando ejecuto "b2g chain --direction forward --json"
    Entonces el exit code es 0
    Y "data.direction" es "forward"
    Y las semillas alcanzadas por citantes tienen "cited_by_id" poblado en el corpus persistido
    Y un "b2g build" posterior proyecta una red de co-citación no vacía (sin ningún paso extra de enriquecimiento)

  Escenario: B1 — Solo backward chaining (referencias de las semillas)
    Cuando ejecuto "b2g chain --direction backward --json"
    Entonces el exit code es 0
    Y "data.direction" es "backward"
    Y "data.observed_refs_count" es un entero >= 0
    Y "data.candidates_found" puede exceder "data.total_papers"
    # #54/#269: los IDs backward observados sin materializar se cuentan en observed_refs_count y en
    # status.referenced_not_fetched; también entran en candidates_found (total rankeado), que por eso
    # puede superar total_papers — el corpus no crece con backward puro.

  Escenario: B1 — Forward chaining requiere un source con fetch_citing
    Dado un source sin "fetch_citing_batch" ni "fetch_citing"
    Cuando ejecuto "b2g chain --direction forward --json"
    Entonces el exit code es 3
    Y "error.code" indica una dependencia/capacidad faltante (DependencyError)
    # Pre-check hasattr en el comando (R5): un AttributeError real no se disfraza de exit 3.

  # --- B2 · Controlar profundidad + preview de crecimiento ---
  Escenario: B2 — Profundidad 1 es el camino soportado
    Cuando ejecuto "b2g chain --depth 1 --json"
    Entonces el exit code es 0
    Y "data.depth" es 1

  @pendiente @no-implementado
  Escenario: B2 — Profundidad mayor a 1 (opt-in a depth=2)
    # PRD §5.1/§7 B2 prometen "opt-in a 2". El CLI lo rechaza hoy.
    # ROADMAP README: "B2 depth>1 futuro". Forager.chain lanza NotImplementedError,
    # que chain.py mapea a DependencyError → exit 3.
    Cuando ejecuto "b2g chain --depth 2 --json"
    Entonces el exit code es 3
    Y "error.code" indica que la profundidad 2 no está soportada aún
    # Cuando se implemente, este escenario pasa a verde con un preview de crecimiento.

  @pendiente @no-implementado
  Escenario: B2 — Preview de crecimiento antes de traer ("sumaría ~N papers")
    # PRD §4/§5.1/§7 B2 prometen un "preview de cuánto crece el corpus antes de traer".
    # AS-BUILT: existe Forager.preview (sin red) en la librería, pero NO hay un
    # subcomando/flag CLI que lo exponga (no hay `b2g chain --preview` ni `b2g preview`).
    # API.md §5 lo declara como API de librería, no de CLI.
    Cuando ejecuto un comando que reporte el crecimiento estimado sin materializar
    Entonces obtengo el conteo previsto de la expansión antes del fetch
    # Gap real: encuadre necesario (¿flag --dry-run de chain?). No escribir en verde.

  # --- B3 · Candidatos rankeados por estructura (information scent, sin IA) ---
  Escenario: B3 — Los candidatos vienen rankeados por scent
    Cuando ejecuto "b2g chain --direction both --json"
    Entonces el exit code es 0
    Y "data.ranking_preview" es una lista de objetos "{id, scent}"
    Y la lista está ordenada de mayor a menor "scent" (lo más relevante primero)
    # El scent es BIBLIOMÉTRICO (R4 hecho), determinista y sin IA: compute_backward_scent
    # (foraging/scent.py) usa collect_item_to_papers de los proyectores
    # (networks/projectors.py) — acoplamiento hacia atrás: cuántos papers del corpus
    # referencian/citan al candidato. No es la heurística de frecuencia de enlace vieja.

  # --- B4 · RETIRADA (no es un Scenario) ---
  # B4 ("paso opcional de IA que explica por qué un candidato es relevante") fue RETIRADA
  # del producto por ADR 0022 (2026-06-15): bib2graph NO usa IA generativa.
  # explain_candidate y el extra [llm] se ELIMINARON. El "porqué" de un candidato lo da la
  # estructura visible (con qué del corpus se acopla/co-cita), no un LLM.
  # No hay escenario verde ni @pendiente: es historia retirada, no trabajo diferido.
