"""Tests de ``b2g monitor`` — paso 8 del ciclo (Ellis), transición a MONITORED.

Casos cubiertos:
1. monitor encuentra N citantes nuevos, los mergea y transiciona a MONITORED.
2. Envelope ``--json`` con schema="1" incluye new_candidates, loop_state, round.
3. Error accionable si el store no tiene estado previo (sin seed previo).
4. Error accionable si el store está vacío (corpus sin papers).

Filosofía del repo: se testea ``run_monitor`` (sin Click), con MockTransport.
Marcador: ``unit`` (DuckDB en tmp_path, red mockeada).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixtures de datos
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
_SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (_FIXTURES_DIR / "sample_works.json").read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    source_id: str | None = None,
    title: str = "Test",
    curation_status: str = "candidate",
) -> dict[str, Any]:
    """Fila mínima con schema completo.

    El default de ``curation_status`` es ``'candidate'`` porque así nacen
    las semillas al sembrarse (``b2g seed``).  El forward chaining del Forager
    opera sobre ``is_seed=True`` independientemente del ``curation_status``;
    la restricción a ``accepted`` es del Enricher (post-curación).
    """
    return {
        "id": id,
        "source_id": source_id,
        "doi": None,
        "title": title,
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _seed_store(
    store_path: Path,
    rows: list[dict[str, Any]] | None = None,
    *,
    state_action: str = "seed",
) -> None:
    """Puebla un store con filas y fija el estado del lazo."""
    from bib2graph.corpus import Corpus
    from bib2graph.cycle import apply_transition
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [
            _make_row(id="P1", source_id="W2741809807"),
            _make_row(id="P2", source_id="W9999999999"),
        ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    new_state, new_round = apply_transition(None, state_action, 0)
    store.backend.set_loop_state(new_state, cycle_round=new_round)


def _make_citing_transport(
    works: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """MockTransport que responde con los works dados como citantes.

    Simula el endpoint ``/works?filter=cites:{id}`` devolviendo works
    en la primera llamada y vacío en las subsiguientes (por papel del corpus).
    """
    if works is None:
        works = [_SAMPLE_WORKS[0]]

    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        # Primera llamada por papel: devuelve citantes; el resto: vacío
        if calls[0] == 1:
            body = {
                "results": works,
                "meta": {"count": len(works), "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_empty_transport() -> httpx.MockTransport:
    """MockTransport que siempre devuelve sin resultados."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [], "meta": {"count": 0, "next_cursor": None}},
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Fixture de citante genuino para el test de forward chaining
# ---------------------------------------------------------------------------

# Work mínimo que cita al seed P1 (openalex_id W2741809807).
# El campo ``referenced_works`` contiene la URL canónica del seed para que
# ``compute_forward_scent`` calcule forward_score > 0.
# Su propio id (W8888888888) no existe en el corpus → es un candidato nuevo.
_CITING_NEW_WORK: dict[str, Any] = {
    "id": "https://openalex.org/W8888888888",
    "doi": None,
    "title": "New paper citing the corpus seed",
    "display_name": "New paper citing the corpus seed",
    "publication_year": 2025,
    "language": "en",
    "abstract_inverted_index": None,
    "authorships": [],
    "keywords": [],
    "referenced_works": [
        "https://openalex.org/W2741809807",  # cita al seed P1
    ],
    "primary_location": {"source": {"display_name": "Test Journal"}},
    "type": "article",
}


# ---------------------------------------------------------------------------
# 1. monitor encuentra citantes nuevos, mergea y transiciona a MONITORED
# ---------------------------------------------------------------------------


def test_monitor_encuentra_nuevos_y_transiciona_a_monitored(tmp_path: Path) -> None:
    """run_monitor mergea 1 citante nuevo y transiciona el estado a MONITORED.

    ``_CITING_NEW_WORK`` tiene id ``W8888888888``, distinto de los seeds P1
    (``W2741809807``) y P2 (``W9999999999``), y referencia al seed P1 en
    ``referenced_works`` → ``compute_forward_scent`` produce forward_score > 0.
    Los asserts son estrictos para verificar que la ruta de merge de candidatos
    nuevos se ejercita realmente (new_candidates = 1, total_papers = 3).
    """
    from bib2graph.cli.commands.monitor import run_monitor
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "monitor.duckdb"
    _seed_store(store_path)

    # MockTransport: devuelve 1 citante genuinamente nuevo en la primera llamada.
    # W8888888888 no está en el corpus y referencia al seed W2741809807.
    transport = _make_citing_transport([_CITING_NEW_WORK])

    data = run_monitor(store_path, transport=transport)

    # El estado debe ser MONITORED
    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == CycleState.MONITORED

    # Exactamente 1 candidato nuevo (el citante no estaba en el corpus)
    assert data["new_candidates"] == 1

    # loop_state en la respuesta
    assert data["loop_state"] == "MONITORED"
    assert data["round"] == 1
    # 2 seeds originales + 1 citante nuevo = 3 en total
    assert data["total_papers"] == 3


def test_monitor_sin_nuevos_transiciona_de_todas_formas(tmp_path: Path) -> None:
    """run_monitor con 0 citantes nuevos igual transiciona a MONITORED."""
    from bib2graph.cli.commands.monitor import run_monitor
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "monitor_empty.duckdb"
    _seed_store(store_path)

    data = run_monitor(store_path, transport=_make_empty_transport())

    assert data["new_candidates"] == 0
    assert data["loop_state"] == "MONITORED"

    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == CycleState.MONITORED


def test_monitor_desde_built_transiciona_a_monitored(tmp_path: Path) -> None:
    """run_monitor desde BUILT transiciona a MONITORED (camino principal del ciclo)."""
    from bib2graph.cli.commands.monitor import run_monitor
    from bib2graph.corpus import Corpus
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "from_built.duckdb"
    rows = [_make_row(id="P1", source_id="W2741809807")]

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    # Simular que estamos en BUILT
    store.backend.set_loop_state(CycleState.BUILT, cycle_round=1)

    data = run_monitor(store_path, transport=_make_empty_transport())

    assert data["loop_state"] == "MONITORED"
    assert data["round"] == 1

    store2 = DuckDBStore(store_path)
    assert store2.backend.loop_state() == CycleState.MONITORED


# ---------------------------------------------------------------------------
# 2. Envelope --json con schema="1"
# ---------------------------------------------------------------------------


def test_monitor_envelope_json_schema_1(tmp_path: Path) -> None:
    """El envelope de monitor incluye schema='1' y los campos canónicos."""
    from bib2graph.cli._envelope import build_envelope
    from bib2graph.cli.commands.monitor import run_monitor

    store_path = tmp_path / "env.duckdb"
    _seed_store(store_path)

    data = run_monitor(store_path, transport=_make_empty_transport())
    envelope = build_envelope(
        command="monitor",
        ok=True,
        data=data,
        exit_code=0,
    )

    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "monitor"
    assert envelope["exit_code"] == 0
    assert "new_candidates" in envelope["data"]
    assert "total_papers" in envelope["data"]
    assert "loop_state" in envelope["data"]
    assert "round" in envelope["data"]

    # JSON-serializable
    serialized = json.dumps(envelope)
    parsed = json.loads(serialized)
    assert parsed["data"]["loop_state"] == "MONITORED"


# ---------------------------------------------------------------------------
# 3. Error accionable si no hay estado previo
# ---------------------------------------------------------------------------


def test_monitor_error_sin_estado_previo(tmp_path: Path) -> None:
    """run_monitor falla con DataError accionable si no hay corpus ni estado previo."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.monitor import run_monitor
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "empty.duckdb"
    DuckDBStore(store_path)  # solo inicializa las tablas, sin estado

    with pytest.raises(DataError, match="b2g seed"):
        run_monitor(store_path, transport=_make_empty_transport())


# ---------------------------------------------------------------------------
# 4. Error accionable si el corpus está vacío (estado previo pero sin papers)
# ---------------------------------------------------------------------------


def test_monitor_error_corpus_vacio(tmp_path: Path) -> None:
    """run_monitor falla con DataError si hay estado pero el corpus está vacío."""
    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.monitor import run_monitor
    from bib2graph.cycle import CycleState
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "no_papers.duckdb"
    store = DuckDBStore(store_path)
    # Forzar un estado sin papers en el corpus
    store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)

    with pytest.raises(DataError, match="b2g seed"):
        run_monitor(store_path, transport=_make_empty_transport())
