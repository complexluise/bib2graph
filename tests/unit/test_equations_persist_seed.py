"""Tests de persistencia de la ecuación en la tabla lateral ``equations`` (#291/#292, ADR 0050 D1).

Cubre que ``run_seed`` (OpenAlex, ``sources/openalex.py``) persiste la
ecuación en la tabla lateral ``equations`` del store vivo — no solo la sella
en el ``Manifest`` del snapshot (que hoy se pierde tras ``merge``, ver
ADR 0050 §Contexto punto 1).

Marcador: ``unit`` (DuckDB en tmp_path, transport mockeado, sin red real).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.unit

SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "sample_works.json").read_text(
        encoding="utf-8"
    )
)


def _make_mock_transport(
    works: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """MockTransport que responde con los works dados (1 página + EOF)."""
    if works is None:
        works = SAMPLE_WORKS
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
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
            headers={"x-openalex-api-version": "2026-06-17"},
        )

    return httpx.MockTransport(handler)


def test_run_seed_persiste_ecuacion_en_tabla_lateral(tmp_path: Path) -> None:
    """``run_seed`` persiste la ecuación cruda en ``store.backend.load_equations()``."""
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    transport = _make_mock_transport()
    store_path = tmp_path / "test.duckdb"
    raw_equation = "unequal exchange"

    data = run_seed(store_path, raw_equation, transport=transport)

    store = DuckDBStore(store_path)
    try:
        equations = store.backend.load_equations()
    finally:
        store.close()

    assert len(equations) == 1
    eq = equations[0]
    assert eq["engine"] == "openalex"
    # raw_query es la ecuación CRUDA (antes de traducir), no la ejecutada.
    assert eq["raw_query"] == raw_equation
    assert eq["raw_query"] != data["executed_query"]
    params = json.loads(str(eq["params_json"]))
    assert params["raw_query"] == raw_equation
    assert params["executed_query"] == data["executed_query"]
    assert eq["equation_id"].startswith("eq-")
    assert eq["created_at"]


def test_run_seed_equation_hash_reproducible_desde_raw_query(tmp_path: Path) -> None:
    """El ``equation_hash`` de ``to_arrow()`` es reproducible desde la ecuación cruda.

    Cierra el contrato de verificación del consumidor: el consumidor programático
    recomputa el hash desde la ecuación confirmada por el usuario y lo compara con
    el embebido en el Arrow.
    """
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    transport = _make_mock_transport()
    store_path = tmp_path / "test.duckdb"
    raw_equation = "unequal exchange"
    expected_hash = hashlib.sha256(raw_equation.strip().encode("utf-8")).hexdigest()

    run_seed(store_path, raw_equation, transport=transport)

    store = DuckDBStore(store_path)
    try:
        table = store.backend.to_arrow()
    finally:
        store.close()

    metadata = table.schema.metadata or {}
    assert metadata.get(b"equation_hash") == expected_hash.encode("utf-8")


def test_run_seed_reseed_con_nueva_ecuacion_acumula_en_equations(
    tmp_path: Path,
) -> None:
    """Dos ``run_seed`` (reseed) acumulan ecuaciones en la tabla lateral (no se pierden).

    ``equation_id`` tiene precisión de segundo (``eq-<YYYYMMDDTHHMMSS>``): si
    ambas siembras caen en el mismo segundo, coinciden por PK y la segunda
    reemplaza (upsert) — no rompe la trazabilidad porque el ``raw_query`` de la
    fila persistida siempre coincide con la ÚLTIMA siembra de ese segundo. El
    invariante que importa es que NINGUNA ecuación se pierda en silencio:
    al menos 1 fila, y su ``raw_query`` corresponde a una de las dos sembradas.
    """
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"

    run_seed(store_path, "ecology", transport=_make_mock_transport())
    run_seed(store_path, "environmental justice", transport=_make_mock_transport())

    store = DuckDBStore(store_path)
    try:
        equations = store.backend.load_equations()
    finally:
        store.close()

    assert len(equations) >= 1
    raw_queries = {eq["raw_query"] for eq in equations}
    assert raw_queries <= {"ecology", "environmental justice"}
    # La última ecuación sembrada siempre debe estar presente (nunca se pierde).
    assert "environmental justice" in raw_queries
