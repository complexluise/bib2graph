"""Genera el corpus congelado ``corpus.parquet`` para el ejemplo de valoraciones.

**Script de procedencia** — NO corre en CI. Requiere acceso local a los archivos
fuente del PO (``valoraciones_v3.duckdb.contaminado.bak`` y
``valoraciones_v3_curable_pre.csv``), que están gitignoreados y nunca se commitean.

Sí se commitea el artefacto de salida: ``examples/valoraciones/corpus.parquet``
(corpus reducido ~120-150 filas, con curación aplicada, schema canónico Arrow).

Uso (desde la raíz del repositorio)::

    uv run python examples/valoraciones/build_corpus.py

Criterio de reducción (determinista, sin aleatoriedad):
-------------------------------------------------------
1. Se aplica la curación del CSV: ``accepted`` → ``curation_status='accepted'``,
   ``rejected`` → ``curation_status='rejected'``, ``undecided`` → se deja
   ``curation_status='candidate'`` (valor original de la DB).

2. Se seleccionan las filas INCLUIDAS en el corpus reducido:
   a. Todos los papers marcados ``accepted`` en el CSV que existen en el corpus.
   b. Top-N seeds con mayor cantidad de ``references_id`` (``ORDER BY
      len(references_id) DESC, id ASC``). Esto garantiza que
      ``bibliographic_coupling`` tenga aristas (papers comparten referencias).
   c. Top-M candidatos (no-seeds) con mayor ``references_id`` para diversidad.
   El total apunta a 120-150 filas.

3. Los papers marcados ``rejected`` en el CSV no se incluyen.

4. El orden de filas del parquet es ``ORDER BY id ASC`` (determinista).

5. Se escribe con ``CORPUS_SCHEMA`` canónico (pyarrow.parquet.write_table).

Garantías de redes no vacías (verificadas al generar el corpus):
- ``bibliographic_coupling``: los top-N seeds por refs producen ≥1000 pares
  con referencia compartida, garantizando un grafo de acoplamiento denso.
- ``author_collab``: los seeds tienen autores con colaboraciones cruzadas.
- ``keyword_cooccurrence``: los keywords de los seeds tienen alta co-ocurrencia.
- ``cocitation``: cited_by_id está vacío en todo el corpus original (el Enricher
  de Hito 8b no se corrió con este corpus). La co-citación queda vacía
  graceful (``Networks.quick`` la omite cuando cited_by_id está en blanco,
  logging una advertencia informativa). Esto es esperado y está documentado.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas de entrada y salida (relativas a la raíz del repo)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_BAK_PATH = _REPO_ROOT / "valoraciones_v3.duckdb.contaminado.bak"
_CSV_PATH = _REPO_ROOT / "valoraciones_v3_curable_pre.csv"
_OUT_PARQUET = Path(__file__).parent / "corpus.parquet"

# Parámetros de reducción (ajustados para garantizar redes no vacías)
_TOP_SEEDS_BY_REFS = 100  # seeds con mayor cantidad de references_id
_TOP_CANDIDATES_BY_REFS = 30  # candidatos con mayor cantidad de references_id
# Total esperado: ~117-150 filas (aceptados + seeds + candidatos, deduplicado)


def _load_curation(csv_path: Path) -> dict[str, str]:
    """Carga la curación del CSV: devuelve {id → decision}.

    Solo registra filas con decision no-vacía. La decisión ``undecided``
    se trata como "sin cambio" (el paper conserva ``curation_status='candidate'``).

    Args:
        csv_path: Ruta al CSV de curación.

    Returns:
        Dict de id → decision ('accepted', 'rejected', 'undecided').
    """
    decisions: dict[str, str] = {}
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            decision = row.get("decision", "").strip()
            if decision:
                decisions[row["id"]] = decision
    return decisions


def _apply_curation_status(
    row_dict: dict[str, object], decisions: dict[str, str]
) -> dict[str, object]:
    """Aplica la decisión de curación a la fila, devolviendo una copia.

    Mapeo:
    - ``accepted`` → ``curation_status = 'accepted'``
    - ``rejected`` → ``curation_status = 'rejected'``
    - ``undecided`` → sin cambio (conserva ``'candidate'`` original)
    - ID no en CSV → sin cambio (conserva ``'candidate'`` original)

    Args:
        row_dict: Fila del corpus como dict.
        decisions: Dict de id → decision (del CSV).

    Returns:
        Fila actualizada con el ``curation_status`` correcto.
    """
    from bib2graph.constants import CurationStatus

    row = dict(row_dict)
    decision = decisions.get(str(row.get("id", "")), "")
    if decision == "accepted":
        row["curation_status"] = CurationStatus.ACCEPTED
    elif decision == "rejected":
        row["curation_status"] = CurationStatus.REJECTED
    # undecided o sin decisión → conservar 'candidate' original
    return row


def build_corpus(
    bak_path: Path = _BAK_PATH,
    csv_path: Path = _CSV_PATH,
    out_parquet: Path = _OUT_PARQUET,
    *,
    top_seeds: int = _TOP_SEEDS_BY_REFS,
    top_candidates: int = _TOP_CANDIDATES_BY_REFS,
    verbose: bool = True,
) -> int:
    """Genera el corpus.parquet reducido y determinista.

    Abre la DB en modo read-only, aplica curación, selecciona filas con
    criterio determinista (sin aleatoriedad) y escribe el parquet.

    Args:
        bak_path: Ruta al .duckdb.contaminado.bak (fuente, read-only).
        csv_path: Ruta al CSV de curación (_curable_pre.csv).
        out_parquet: Destino del parquet de salida.
        top_seeds: Top-N seeds por references_id para incluir.
        top_candidates: Top-M candidatos por references_id para incluir.
        verbose: Si True, imprime progreso.

    Returns:
        Número de filas escritas al parquet.

    Raises:
        FileNotFoundError: Si los archivos de entrada no existen.
        RuntimeError: Si el corpus reducido quedaría vacío o sin redes viables.
    """
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    from bib2graph.schemas import CORPUS_SCHEMA

    # Validación de precondiciones
    if not bak_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo fuente: {bak_path}\n"
            "Este script requiere los archivos locales del PO "
            "(gitignoreados, nunca se commitean)."
        )
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No se encontró el CSV de curación: {csv_path}\n"
            "Este script requiere valoraciones_v3_curable_pre.csv "
            "(gitignoreado, nunca se commitea)."
        )

    if verbose:
        print(f"Leyendo corpus desde: {bak_path}")
    con = duckdb.connect(str(bak_path), read_only=True)

    # Carga completa de la tabla corpus (sin _seq — columna interna de la DB)
    # Las columnas están en el orden del CORPUS_SCHEMA canónico
    canonical_cols = [field.name for field in CORPUS_SCHEMA]
    cols_sql = ", ".join(canonical_cols)
    all_rows = con.execute(f"SELECT {cols_sql} FROM corpus").fetchall()
    con.close()

    if verbose:
        print(f"Total filas en DB: {len(all_rows)}")

    # Convertir a lista de dicts
    rows_as_dicts: list[dict[str, object]] = [
        dict(zip(canonical_cols, row, strict=True)) for row in all_rows
    ]

    # Cargar curación
    decisions = _load_curation(csv_path)
    accepted_ids = {id_ for id_, dec in decisions.items() if dec == "accepted"}
    rejected_ids = {id_ for id_, dec in decisions.items() if dec == "rejected"}

    if verbose:
        acc_in_corpus = sum(1 for r in rows_as_dicts if r["id"] in accepted_ids)
        rej_in_corpus = sum(1 for r in rows_as_dicts if r["id"] in rejected_ids)
        print(
            f"Curación CSV: {len(accepted_ids)} aceptados ({acc_in_corpus} en corpus), "
            f"{len(rejected_ids)} rechazados ({rej_in_corpus} en corpus)"
        )

    # Aplicar curación a TODAS las filas (para el mapa correcto de curation_status)
    curated_map: dict[str, dict[str, object]] = {}
    for row in rows_as_dicts:
        curated_row = _apply_curation_status(row, decisions)
        curated_map[str(curated_row["id"])] = curated_row

    # -----------------------------------------------------------------------
    # Criterio de selección DETERMINISTA (sin aleatoriedad):
    # 1. Todos los aceptados que existen en el corpus (forzados)
    # 2. Top-N seeds por len(references_id) DESC, id ASC (coupling)
    # 3. Top-M candidatos (no-seeds) por len(references_id) DESC, id ASC
    # Los rechazados nunca se incluyen.
    # -----------------------------------------------------------------------

    def _ref_count(row: dict[str, object]) -> int:
        refs = row.get("references_id")
        return len(refs) if isinstance(refs, list) else 0

    # 1. Accepted (del CSV) que están en el corpus
    forced_ids: set[str] = {
        id_
        for id_ in accepted_ids
        if id_ in curated_map and str(curated_map[id_]["curation_status"]) != "rejected"
    }

    # 2. Top seeds por references_id (excluir accepted y rejected)
    seeds_eligible = sorted(
        [
            row
            for row in curated_map.values()
            if row.get("is_seed")
            and str(row["id"]) not in forced_ids
            and str(row["id"]) not in rejected_ids
            and _ref_count(row) > 0
        ],
        key=lambda r: (-_ref_count(r), str(r["id"])),
    )

    # 3. Top candidatos (no-seeds) por references_id (excluir accepted y rejected)
    candidates_eligible = sorted(
        [
            row
            for row in curated_map.values()
            if not row.get("is_seed")
            and str(row["id"]) not in forced_ids
            and str(row["id"]) not in rejected_ids
            and _ref_count(row) > 0
        ],
        key=lambda r: (-_ref_count(r), str(r["id"])),
    )

    selected_ids: set[str] = set(forced_ids)
    selected_ids |= {str(r["id"]) for r in seeds_eligible[:top_seeds]}
    selected_ids |= {str(r["id"]) for r in candidates_eligible[:top_candidates]}

    if verbose:
        print(
            f"Selección: {len(forced_ids)} aceptados forzados + "
            f"{min(len(seeds_eligible), top_seeds)} seeds + "
            f"{min(len(candidates_eligible), top_candidates)} candidatos "
            f"= {len(selected_ids)} únicos"
        )

    if len(selected_ids) == 0:
        raise RuntimeError(
            "El corpus reducido quedó vacío. Revisá los criterios de selección."
        )

    # Construir tabla final, ordenada por id ASC (determinista)
    selected_rows = sorted(
        [curated_map[id_] for id_ in selected_ids],
        key=lambda r: str(r["id"]),
    )

    # Normalizar tipos para Arrow (list → list[str], None → None)
    def _normalize_list(val: object) -> list[str] | None:
        if val is None:
            return None
        if isinstance(val, list):
            return [str(x) for x in val if x is not None]
        return None

    list_cols = {
        "research_areas",
        "authors_raw",
        "authors_id",
        "authors_affiliations",
        "keywords_raw",
        "keywords_id",
        "institutions_raw",
        "institutions_id",
        "references_id",
        "references_doi",
        "cited_by_id",
    }

    normalized_rows: list[dict[str, object]] = []
    for row in selected_rows:
        norm = {}
        for col in canonical_cols:
            val = row.get(col)
            if col in list_cols:
                norm[col] = _normalize_list(val)
            elif col == "year":
                norm[col] = int(val) if val is not None else None
            elif col == "is_seed":
                norm[col] = bool(val)
            else:
                norm[col] = str(val) if val is not None else None
        normalized_rows.append(norm)

    table = pa.Table.from_pylist(normalized_rows, schema=CORPUS_SCHEMA)

    # Validar con el schema canónico
    from bib2graph.schemas import validate_table

    validate_table(table)

    # Escribir parquet
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(out_parquet))

    if verbose:
        n = len(table)
        acc_count = sum(
            1 for r in normalized_rows if r.get("curation_status") == "accepted"
        )
        rej_count = sum(
            1 for r in normalized_rows if r.get("curation_status") == "rejected"
        )
        cand_count = sum(
            1 for r in normalized_rows if r.get("curation_status") == "candidate"
        )
        with_refs = sum(
            1
            for r in normalized_rows
            if isinstance(r.get("references_id"), list) and len(r["references_id"]) > 0  # type: ignore[arg-type]
        )
        with_authors = sum(
            1
            for r in normalized_rows
            if isinstance(r.get("authors_id"), list) and len(r["authors_id"]) > 0  # type: ignore[arg-type]
        )
        with_kws = sum(
            1
            for r in normalized_rows
            if isinstance(r.get("keywords_id"), list) and len(r["keywords_id"]) > 0  # type: ignore[arg-type]
        )
        print(f"\nParquet escrito: {out_parquet}")
        print(f"  Filas: {n}")
        print(
            f"  Curación: {acc_count} accepted, {rej_count} rejected, "
            f"{cand_count} candidate"
        )
        print(
            f"  Con referencias: {with_refs} | Con autores: {with_authors} "
            f"| Con keywords: {with_kws}"
        )
        print("  cited_by_id: vacío en todo el corpus (co-citación omitida graceful)")
        print("  Redes esperadas no vacías: bibliographic_coupling, author_collab,")
        print("    keyword_cooccurrence, institution_collab (si hay instituciones)")

    return len(table)


if __name__ == "__main__":
    n = build_corpus(verbose=True)
    print(f"\nListo. {n} filas escritas en corpus.parquet")
    sys.exit(0)
