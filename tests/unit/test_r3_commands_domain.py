"""Tests R3 — gap arquitectónico: fuente única de verdad en cycle.py.

Verifica que el estado persistido por chain/filter/build es el dictado por
``apply_transition``, no un literal en el comando.  Si alguien cambia las
reglas en ``cycle.py``, los comandos lo siguen y estos tests lo detectan.

Filosofía del repo: solo lo que tiene lógica o riesgo de regresión.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import pyarrow as pa
import pytest

from bib2graph.cycle import CycleState, apply_transition
from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *, id: str, title: str = "Test", curation_status: str = "candidate"
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "openalex_id": None,
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
    state: CycleState | None = None,
    cycle_round: int = 1,
) -> None:
    """Puebla un store con filas mínimas y opcionalmente fija el estado del lazo."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [_make_row(id="P1"), _make_row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    if state is not None:
        store.backend.set_loop_state(state, cycle_round=cycle_round)


def _make_noop_transport() -> Any:
    """MockTransport que devuelve respuesta vacía (sin candidatos)."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"results": [], "meta": {"count": 0, "next_cursor": None}},
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_empty_forage_result() -> Any:
    """Resultado de foraging vacío compatible con run_chain (Forager.chain mock)."""
    from bib2graph.corpus import Corpus

    empty = Corpus.from_arrow(
        pa.table(
            {f.name: pa.array([], type=f.type) for f in CORPUS_SCHEMA},
            schema=CORPUS_SCHEMA,
        )
    )

    class _FakeResult:
        corpus = empty
        ranking: ClassVar[list[Any]] = []

    return _FakeResult()


# ---------------------------------------------------------------------------
# Contrato domain-tied: estado persistido == apply_transition(prev, action)
#
# Parametrizado sobre las 3 acciones: chain / filter / build.
# En cada caso se parte de un estado previo representativo y se verifica que
# el estado almacenado en el backend coincide con apply_transition, no con un
# literal hardcodeado.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "action, prev_state, prev_round",
    [
        # chain desde SEEDED (camino habitual)
        ("chain", CycleState.SEEDED, 1),
        # filter desde FORAGED (camino habitual)
        ("filter", CycleState.FORAGED, 1),
        # build desde FILTERED (camino habitual)
        ("build", CycleState.FILTERED, 1),
        # Saltos permisivos: chain/filter/build desde cualquier estado
        ("chain", CycleState.BUILT, 2),
        ("filter", CycleState.SEEDED, 1),
        ("build", CycleState.SEEDED, 1),
        # Acciones desde None (sin estado previo): permisivas también
        ("chain", None, 0),
        ("filter", None, 0),
        ("build", None, 0),
    ],
)
def test_estado_persistido_es_dictado_por_cycle(
    tmp_path: Path,
    action: str,
    prev_state: CycleState | None,
    prev_round: int,
) -> None:
    """El estado guardado tras chain/filter/build == apply_transition(prev, action, round).

    Garantiza que el destino de la transición lo dicta cycle.py (fuente única
    de verdad), no un literal en el comando (ADR 0016 enmendado §1).
    Si alguien cambia _CHAIN_TRANSITIONS en cycle.py, este test lo detecta.
    """
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / f"test_{action}_{prev_state}_{prev_round}.duckdb"
    _seed_store(store_path, state=prev_state, cycle_round=prev_round)

    # Derivar el estado esperado desde el dominio ANTES de ejecutar el comando
    expected_state, expected_round = apply_transition(prev_state, action, prev_round)

    # Ejecutar el comando correspondiente (se parchean operaciones externas costosas)
    if action == "chain":
        from bib2graph.cli.commands.chain import run_chain

        with patch(
            "bib2graph.foraging.forager.Forager.chain",
            return_value=_make_empty_forage_result(),
        ):
            run_chain(store_path, transport=_make_noop_transport())
    elif action == "filter":
        from bib2graph.cli.commands.filter import run_filter

        run_filter(store_path, year_gte=2000)
    elif action == "build":
        from bib2graph.cli.commands.build import run_build

        with patch(
            "bib2graph.networks.facade.Networks.quick",
            return_value=[],
        ):
            run_build(store_path)

    # Verificar que el backend tiene el estado dictado por cycle.py
    store = DuckDBStore(store_path)
    assert store.backend.loop_state() == expected_state, (
        f"action={action!r} desde state={prev_state!r}: "
        f"esperado {expected_state!r}, obtenido {store.backend.loop_state()!r}. "
        "El comando debe usar apply_transition, no un literal."
    )
    assert store.backend.loop_round() == expected_round, (
        f"action={action!r} desde round={prev_round}: "
        f"round esperado {expected_round!r}, obtenido {store.backend.loop_round()!r}."
    )
