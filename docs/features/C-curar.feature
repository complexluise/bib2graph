# language: es
# Épica C — Ejercicio bibliotecario y biblioteca viva (curar y conservar)
# Historias PRD §7: C1 (no-CLI), C2 (no-CLI), C3, C4
# Anclado a: src/bib2graph/cli/commands/filter.py, curate.py, accept.py, reject.py
# Realidad post-#75: workspace por cwd; no existe --store.

Característica: Curar el corpus con filtros PRISMA y biblioteca viva
  Como investigador
  Quiero aplicar criterios de inclusión/exclusión con conteo y aceptar/rechazar candidatos
  Para curar con trazabilidad y cultivar una colección que crece entre corridas

  Antecedentes:
    Dado un workspace con un corpus forrajeado (estado FORAGED)
    Y que trabajo dentro de esa carpeta

  # --- C1 · Dedup y normalización de autores/instituciones ---
  @pendiente @no-implementado
  Escenario: C1 — Dedup/normalización de autores e instituciones por CLI
    # PRD §7 C1 pide dedup/normalización apoyada en IDs OpenAlex (ORCID/ROR/DOI).
    # AS-BUILT: normalize_authors_id / deduplicate_keywords / Preprocessor existen como
    # API de librería (src/bib2graph/preprocessors/), pero NINGÚN subcomando b2g los expone
    # (no hay `b2g normalize` ni `b2g preprocess`). Instituciones: DIFERIDAS (ROADMAP C1).
    # Por eso no hay receta CLI verde para esta historia hoy.
    Cuando ejecuto un comando que normalice/deduplique autores e instituciones
    Entonces las variantes de nombre colapsan apoyadas en ORCID/ROR
    # Gap real: el preprocesamiento vive en la librería; falta encuadre de su superficie CLI.

  # --- C2 · Normalizar keywords con thesaurus multilingüe ---
  @pendiente @no-implementado
  Escenario: C2 — Aplicar el thesaurus multilingüe (en/es/pt) por CLI
    # PRD §7 C2 pide normalizar keywords con un thesaurus curado y auditable, para que
    # conceptos equivalentes en distintos idiomas colapsen (p. ej. "intercambio ecológico
    # desigual" ≡ "unequal exchange").
    # AS-BUILT: apply_thesaurus vive en src/bib2graph/preprocessors/thesaurus.py (determinista,
    # SIN fallback LLM — ADR 0022/0011), pero NO hay subcomando b2g que lo exponga.
    # API.md §5/§6 lo declara como API de librería.
    Cuando ejecuto un comando que aplique el thesaurus al corpus
    Entonces "keywords_id" se reescribe con los conceptos canónicos del thesaurus
    # Gap real: falta superficie CLI del Preprocessor.

  # --- C3 · Filtros de inclusión/exclusión con conteo por paso (PRISMA) ---
  Escenario: C3 — Filtrar por año e idioma con conteo en cada paso
    Cuando ejecuto "b2g filter --year-gte 2010 --language en --language es --json"
    Entonces el exit code es 0
    Y "command" es "filter"
    Y "data.criteria_applied" es 2
    Y "data.steps" es una lista, una entrada por criterio
    Y cada entrada tiene "count_before", "count_after" y "excluded"
    Y "excluded" es igual a "count_before" menos "count_after"
    Y tras el filtro el estado del lazo transiciona a "FILTERED"
    # Los filtros MARCAN rejected (no borran): el corpus conserva la trazabilidad PRISMA.

  Escenario: C3 — Filtrar sin ningún criterio es un error de datos
    Cuando ejecuto "b2g filter --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)
    # "Debés especificar al menos un criterio: --year-gte/--year-lte/--language/--type/--min-citations."

  Escenario: C3 — Filtro por mínimo de citas
    Cuando ejecuto "b2g filter --min-citations 5 --json"
    Entonces el exit code es 0
    Y "data.steps" incluye un paso de mínimo de citas (len(cited_by_id) >= 5)

  # --- C4 · Aceptar/rechazar + biblioteca viva persistida que crece ---
  Escenario: C4 — Aceptar candidatos por ID
    Dado un candidato con id "oa:abc123def456" en el corpus
    Cuando ejecuto "b2g accept --ids oa:abc123def456 --json"
    Entonces el exit code es 0
    Y "command" es "accept"
    Y "data.accepted_count" es 1
    Y "accept" NO transiciona el estado del lazo (curación transversal)

  Escenario: C4 — Aceptar un ID inexistente
    Cuando ejecuto "b2g accept --ids oa:no-existe --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)
    # "IDs no encontrados en el corpus: [...]. Verificá con b2g inspect."

  Escenario: C4 — Rechazar candidatos por ID
    Cuando ejecuto "b2g reject --ids oa:abc123def456 --json"
    Entonces el exit code es 0
    Y "command" es "reject"
    # reject tampoco transiciona el lazo (curación transversal).

  # --- C4 (escala) · Curación en lote vía CSV ---
  Escenario: C4 — Volcar candidatos a CSV para revisión offline
    Cuando ejecuto "b2g curate dump --json"
    Entonces el exit code es 0
    Y se escribe "exports/curacion.csv" con las 16 columnas estables
    Y "data.papers_exported" es un entero >= 0
    # Default scope=candidates: status==candidate AND is_seed==False (EXCLUYE semillas, #72).
    # Solo "decision" y "note" son editables por el humano.

  Escenario: C4 — Volcar semillas o todo el corpus con --scope
    Cuando ejecuto "b2g curate dump --scope all --json"
    Entonces el exit code es 0
    Y "data.papers_exported" cubre todo el corpus (candidates + seeds + accepted + rejected)

  Escenario: C4 — Reimportar las decisiones del CSV en lote (idempotente)
    Dado un "exports/curacion.csv" con la columna "decision" editada
    Cuando ejecuto "b2g curate apply exports/curacion.csv --json"
    Entonces el exit code es 0
    Y "data.accepted_count" cuenta papers efectivamente marcados como accepted
    Y "data.rejected_count" cuenta papers efectivamente marcados como rejected
    Y "data.skipped_count" cuenta las filas "undecided" (no-op)
    Y "data.not_found_count" cuenta IDs del CSV ausentes del corpus (huérfanos, sin abortar)
    # Idempotente: reimportar el mismo CSV deja el mismo corpus_hash (note se ignora al importar).

  Escenario: C4 — apply con una decision inválida falla accionable
    Dado un CSV con un valor de "decision" fuera de {accepted, rejected, undecided}
    Cuando ejecuto "b2g curate apply exports/curacion.csv --json"
    Entonces el exit code es 2
    Y "error.code" indica un error de datos (DataError)

  Escenario: C4 — La biblioteca viva crece y persiste entre corridas
    Dado que acepté papers en una ronda anterior
    Cuando vuelvo a sembrar y curar en el mismo workspace
    Entonces los papers aceptados previos siguen en el corpus
    Y "b2g status --json" muestra los conteos por "curation_status" acumulados
    # La biblioteca viva es DuckDB nativo; la sincronización con Zotero está DESCARTADA (PO 2026-06-17).
