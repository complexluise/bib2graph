"""service.snapshot — Servicios de snapshot y restore (ADR 0038, #163).

Capa neutral: sin ``print``, ``sys.exit``, Click ni FastAPI.

``run_snapshot`` — exporta una foto sellada del corpus actual (parquet +
manifest.json). No transiciona el CycleState.

``run_restore`` — rehidrata un corpus desde un parquet curado, lo mergea con
el existente, aplica normalize+dedup y transiciona el estado del lazo a
``FILTERED``.

``decided_at`` se inyecta desde la frontera CLI (R2/ADR 0017): el servicio
no llama ``datetime.now()`` directamente.  El CLI (``cli/commands/snapshot.py``
y el shim ``cli/commands/restore.py``) son adaptadores delgados.

El subcomando ``snapshot create`` y ``snapshot restore`` delegan acá;
el shim ``b2g restore`` también delega acá (fuente única — ADR 0038 §163).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bib2graph.preprocessors.pipeline import normalize_and_dedup
from bib2graph.service.errors import DataError
from bib2graph.service.store import open_store as _open_store

if TYPE_CHECKING:
    from bib2graph.stores.duckdb import DuckDBStore


def _restore_equations_from_sibling_manifest(
    store: DuckDBStore, corpus_path: Path
) -> None:
    """Reconstruye la tabla lateral ``equations`` desde el manifest hermano.

    ``snapshot create`` escribe ``corpus.parquet`` y ``manifest.json`` en el
    MISMO directorio (ver ``Corpus.snapshot``): el manifest sella
    ``equations`` (lista de ``EquationRef``), pero el parquet NO las lleva
    (son laterales al ``CORPUS_SCHEMA`` — R2/ADR 0017). Este helper busca ese
    ``manifest.json`` hermano y, si existe y declara ecuaciones, las
    re-persiste vía ``backend.persist_equation`` — mismo mapeo de campos que
    ``run_seed`` (``cli/commands/seed.py``): ``engine`` (fallback
    ``"openalex"``), ``raw_query`` desde ``params["raw_query"]`` (fallback al
    ``query`` histórico si el manifest no tiene ese campo), ``params_json``
    con el dict ``params`` completo serializado, y ``created_at``.

    Idempotente (``persist_equation`` hace upsert por ``equation_id`` — PK),
    así que restaurar el mismo snapshot dos veces no duplica filas.

    Graceful: si no hay ``manifest.json`` hermano (parquet curado externo
    suelto, sin snapshot de bib2graph detrás) o el manifest no declara
    ``equations``, no hace nada — no reconstruye ecuaciones, no lanza.

    Args:
        store: Store destino ya abierto (con el corpus mergeado persistido).
        corpus_path: Ruta al parquet pasado a ``run_restore``
            (``--from-corpus``); el manifest se busca en su mismo directorio.
    """
    manifest_path = corpus_path.parent / "manifest.json"
    if not manifest_path.exists():
        return

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Manifest hermano corrupto/ilegible: graceful, no reconstruye equations.
        return

    equations = manifest_data.get("equations") or []
    for eq in equations:
        params = eq.get("params") or {}
        raw_query = params.get("raw_query", eq.get("query"))
        if raw_query is None:
            # EquationRef sin query recuperable (manifest degenerado): salteala,
            # no hay valor no-nulo aceptable para la columna NOT NULL.
            continue
        store.backend.persist_equation(
            str(eq["equation_id"]),
            engine=str(eq.get("engine") or "openalex"),
            raw_query=str(raw_query),
            params_json=json.dumps(params, ensure_ascii=False),
            created_at=eq.get("created_at"),
        )


def run_snapshot(
    store_path: str | Path,
    *,
    out_dir: str | Path,
) -> dict[str, Any]:
    """Exporta una foto sellada del corpus actual.

    Carga el corpus del store y exporta un snapshot sellado (parquet +
    manifest.json) al directorio indicado.  No transiciona el CycleState.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        out_dir: Directorio destino del snapshot.

    Returns:
        Dict con ``snapshot_dir``, ``corpus_hash``, ``total_papers``,
        ``schema_version``.

    Raises:
        StoreError: Si el store está bloqueado o no se puede abrir.
    """
    from bib2graph.service.maturity import compute_maturity

    store = _open_store(Path(store_path))
    corpus = store.load()
    snap = corpus.snapshot(Path(out_dir))
    maturity = compute_maturity(corpus, scope="all", empty_network_kinds=[])
    return {
        "snapshot_dir": str(snap.path),
        "corpus_hash": snap.manifest.corpus_hash,
        "total_papers": len(corpus),
        "schema_version": snap.manifest.schema_version,
        "maturity": maturity,
    }


def run_restore(
    store_path: str | Path,
    corpus_path: str | Path,
    *,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    """Carga un corpus curado desde un parquet y lo persiste en el store sin red.

    Lee el parquet con el schema canónico (``CORPUS_SCHEMA``), lo hidrata con
    ``Corpus.from_arrow``, hace merge con el corpus existente, aplica
    normalize + dedup y persiste.  Transiciona el ``CycleState`` a
    ``FILTERED`` (el corpus ya fue curado; ver docstring de
    ``cli/commands/restore.py`` para la justificación).

    Preserva las columnas de curación del parquet
    (``decision`` / ``curation_status`` / ``is_seed``): el merge de ``Corpus``
    respeta el ``curation_status`` más reciente (D3 del merge).

    QA 0.14.0 (hallazgo #1 continuado, ADR 0050 D1): si existe un
    ``manifest.json`` hermano del parquet (mismo directorio, producido por
    ``snapshot create``) y declara ``equations``, cada una se re-persiste en
    la tabla lateral ``equations`` del store destino vía
    ``backend.persist_equation`` — mismo mapeo de campos que usa ``run_seed``
    (``cli/commands/seed.py``) al sembrar: ``params["raw_query"]`` (fallback al
    ``query`` histórico si el manifest es más viejo y no tiene ese campo) y
    ``params`` completo serializado a ``params_json``. Sin esto, un
    ``snapshot restore`` recuperaba las filas del corpus pero
    ``backend.load_equations()`` quedaba en 0 (las ecuaciones solo viven en
    el manifest, no en el parquet — la tabla ``equations`` es lateral al
    ``CORPUS_SCHEMA``, R2/ADR 0017). Es **graceful**: si no hay manifest
    hermano (p.ej. un parquet curado externo suelto) o no declara
    ``equations``, restore no reconstruye nada — 0 ecuaciones, sin excepción.

    No instancia ``OpenAlexSource``, no hace requests.  Es el camino offline
    para rehidratar un corpus curado exportado con ``b2g snapshot create``.

    R2/ADR 0017: ``decided_at`` se inyecta desde la frontera CLI.  Si
    ``None``, el timestamp se genera internamente al pasar el control a los
    preprocesadores (el servicio no llama ``datetime.now()`` directamente).

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        corpus_path: Ruta al archivo ``.parquet`` con el corpus curado.
        decided_at: Timestamp inyectado por el llamador (R2/ADR 0017).

    Returns:
        Dict con ``papers_loaded``, ``total_papers``, ``state``, ``round``.

    Raises:
        DataError: Si el parquet no existe o no tiene el schema canónico.
        StoreError: Si el store está bloqueado.
    """
    import pyarrow.parquet as pq

    from bib2graph.corpus import Corpus
    from bib2graph.cycle import CycleState, apply_transition
    from bib2graph.schemas import CORPUS_SCHEMA

    resolved = Path(corpus_path)
    if not resolved.exists():
        raise DataError(
            f"El parquet '{resolved}' no existe. Verificá la ruta al corpus curado."
        )

    try:
        table = pq.read_table(str(resolved), schema=CORPUS_SCHEMA)  # type: ignore[no-untyped-call]
    except Exception as exc:
        raise DataError(
            f"No se pudo leer el parquet '{resolved}': {exc}. "
            "Verificá que el archivo tenga el schema canónico de bib2graph."
        ) from exc

    try:
        incoming = Corpus.from_arrow(table)
    except Exception as exc:
        raise DataError(
            f"El parquet '{resolved}' no cumple el schema canónico: {exc}."
        ) from exc

    store = _open_store(Path(store_path))
    merged_backend_close = None
    try:
        existing = store.load()

        # Transición a FILTERED: el corpus restaurado ya pasó curación.
        # apply_transition es permisiva — acepta "filter" desde cualquier estado
        # actual del store (incluyendo None para un store vacío nuevo).
        current_state = store.backend.loop_state()
        # La ronda nunca debe ser < 1: loop_round() devuelve 0 para bases legacy
        # (round=NULL, pre-R3) y para stores vacíos. max(..., 1) la normaliza en
        # ambos branches para no persistir un estado con ronda 0 incoherente.
        current_round = max(store.backend.loop_round(), 1)
        # "filter" lleva a FILTERED; la ronda no cambia (no es reseed).
        # Para un store vacío (current_state=None), arrancamos desde SEEDED ficticio.
        if current_state is None:
            new_state, new_round = apply_transition(
                CycleState.SEEDED, "filter", current_round
            )
        else:
            new_state, new_round = apply_transition(
                current_state, "filter", current_round
            )

        # Merge primero, dedup después sobre el corpus COMPLETO (fix bug cross-biblioteca).
        # El reloj se fija UNA vez por invocación (R2): pasado via decided_at.
        merged = existing.merge(incoming)
        merged_deduped = normalize_and_dedup(merged, applied_at=decided_at)
        papers_loaded = len(incoming)
        total_papers = len(merged_deduped)
        merged_backend_close = getattr(merged_deduped._backend, "close", None)
        store.persist_replace(merged_deduped)
        store.backend.set_loop_state(new_state, cycle_round=new_round)

        _restore_equations_from_sibling_manifest(store, resolved)
    finally:
        # Ver run_seed_from_bib: cierra explícitamente las conexiones DuckDB
        # para evitar segfault en Linux ante llamadas consecutivas al mismo archivo.
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    return {
        "papers_loaded": papers_loaded,
        "total_papers": total_papers,
        "state": str(new_state),
        "round": new_round,
    }
