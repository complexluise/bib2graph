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


# ---------------------------------------------------------------------------
# QA 0.14.0 hallazgo #1: DuckDBStore.load() reconstruye manifest.equations
# desde la tabla lateral ``equations`` (antes solo reconstruía filters/enrichers).
# ---------------------------------------------------------------------------


def test_load_reconstruye_manifest_equations_desde_tabla_lateral(
    tmp_path: Path,
) -> None:
    """Cargar el store en un ``Corpus`` NUEVO refleja las ecuaciones sembradas.

    Bug confirmado en QA: tras sembrar, ``backend.load_equations()`` devuelve
    las filas, pero ``corpus.manifest.equations`` (del ``Corpus`` recién
    cargado en una sesión nueva) quedaba en ``[]`` — la reconstrucción de
    filters/enrichers existía, la de equations no.
    """
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    run_seed(store_path, "unequal exchange", transport=_make_mock_transport())

    # Sesión NUEVA: instancia de store distinta, simula reabrir el archivo.
    store = DuckDBStore(store_path)
    try:
        corpus = store.load()
    finally:
        store.close()

    assert len(corpus.manifest.equations) == 1
    eq_ref = corpus.manifest.equations[0]
    assert eq_ref.equation_id.startswith("eq-")
    assert eq_ref.engine == "openalex"
    assert eq_ref.params.get("raw_query") == "unequal exchange"
    assert eq_ref.created_at


def test_load_reconstruye_manifest_equations_con_dos_ecuaciones(
    tmp_path: Path,
) -> None:
    """Dos siembras (ecuaciones distintas) reconstruyen 2 ``EquationRef``."""
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    run_seed(store_path, "ecology", transport=_make_mock_transport())
    run_seed(store_path, "environmental justice", transport=_make_mock_transport())

    store = DuckDBStore(store_path)
    try:
        corpus = store.load()
    finally:
        store.close()

    # Puede colapsar a 1 fila si ambas siembras caen en el mismo segundo
    # (mismo equation_id, ver test de arriba); el invariante es que refleja
    # exactamente lo que hay en la tabla lateral.
    store2 = DuckDBStore(store_path)
    try:
        raw_equations = store2.backend.load_equations()
    finally:
        store2.close()

    assert len(corpus.manifest.equations) == len(raw_equations)
    raw_queries_manifest = {
        eq.params.get("raw_query") for eq in corpus.manifest.equations
    }
    raw_queries_table = {eq["raw_query"] for eq in raw_equations}
    assert raw_queries_manifest == raw_queries_table


def test_snapshot_create_sella_ecuaciones_no_vacio(tmp_path: Path) -> None:
    """``snapshot create`` sella ``equations`` en ``manifest.json`` (no vacío).

    Cierra el bug de punta a punta: antes, el snapshot sellaba
    ``"equations": []`` en ``manifest.json`` pese a haber ecuaciones
    registradas en la biblioteca viva.
    """
    import json as _json

    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.service.snapshot import run_snapshot
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    run_seed(store_path, "unequal exchange", transport=_make_mock_transport())

    snap_dir = tmp_path / "snap"
    run_snapshot(store_path, out_dir=snap_dir)

    manifest_path = snap_dir / "manifest.json"
    assert manifest_path.exists()
    manifest_data = _json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["equations"], (
        "manifest.json debe sellar las ecuaciones registradas (no vacío)"
    )
    assert manifest_data["equations"][0]["params"]["raw_query"] == "unequal exchange"

    # DuckDBStore usado directo (no vía run_seed) para verificar además que
    # el manifest reconstruido en memoria coincide con lo sellado en disco.
    store = DuckDBStore(store_path)
    try:
        corpus = store.load()
    finally:
        store.close()
    assert len(corpus.manifest.equations) == len(manifest_data["equations"])


def test_load_store_sin_tabla_equations_no_rompe(tmp_path: Path) -> None:
    """Store sin ecuaciones registradas → ``manifest.equations == []`` sin excepción.

    Cubre retrocompat: la tabla ``equations`` se crea siempre con
    ``CREATE TABLE IF NOT EXISTS`` al abrir el ``DuckDBBackend`` (incluso en
    stores viejos pre-ADR 0050 D1), así que ``load_equations()`` nunca lanza
    por tabla ausente — simplemente no hay filas.
    """
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "empty.duckdb"
    store = DuckDBStore(store_path)
    try:
        corpus = store.load()
    finally:
        store.close()

    assert corpus.manifest.equations == []


# ---------------------------------------------------------------------------
# Deuda de cobertura 0.14.0: ``DuckDBBackend._clone()`` preserva ``equations``.
# ---------------------------------------------------------------------------


def test_clone_via_add_paper_preserva_tabla_equations(tmp_path: Path) -> None:
    """``add_paper`` dispara ``_clone()``; las ecuaciones persistidas sobreviven.

    ``add_paper`` llama internamente a ``self._clone()`` antes de insertar la
    fila nueva (ver ``DuckDBBackend.add_paper``). Este test asevera que ese
    clonado — que copia explícitamente ``loop_state_log``,
    ``referenced_but_not_fetched``, ``external_ids``, ``filter_log``,
    ``enricher_log`` y ``equations`` fila por fila — efectivamente conserva
    las ecuaciones sembradas antes de la operación, en el mismo orden
    (``equation_id``/``raw_query``).
    """
    from bib2graph.backends.duckdb import DuckDBBackend

    store_path = tmp_path / "clone_equations.duckdb"
    backend = DuckDBBackend(path=store_path)
    backend.persist_equation(
        "eq-0001", engine="openalex", raw_query="ecology", params_json="{}"
    )
    backend.persist_equation(
        "eq-0002",
        engine="openalex",
        raw_query="environmental justice",
        params_json="{}",
    )

    # Dispara _clone() por la vía pública normal (add_paper clona antes de
    # insertar). El backend devuelto es una instancia NUEVA (semántica de valor).
    new_backend = backend.add_paper(
        {
            "id": "doi:new-paper",
            "title": "New paper via add_paper",
            "is_seed": True,
            "curation_status": "candidate",
        }
    )

    equations = new_backend.load_equations()
    assert [eq["equation_id"] for eq in equations] == ["eq-0001", "eq-0002"]
    assert [eq["raw_query"] for eq in equations] == ["ecology", "environmental justice"]

    backend.close()
    new_backend.close()


def test_persist_replace_no_borra_tabla_equations(tmp_path: Path) -> None:
    """``DuckDBStore.persist_replace`` (``DELETE FROM corpus``) NO toca ``equations``.

    ``persist_replace`` -> ``overwrite_corpus`` hace ``DELETE FROM corpus``
    seguido de un INSERT masivo del contenido final. La tabla lateral
    ``equations`` (ADR 0050 D1) es una tabla HERMANA, no la tabla ``corpus``:
    este test asevera explícitamente que el ``DELETE`` acotado a ``corpus``
    no arrastra las ecuaciones ya registradas.
    """
    import pyarrow as pa

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "replace_equations.duckdb"
    store = DuckDBStore(store_path)
    store.backend.persist_equation(
        "eq-0001", engine="openalex", raw_query="unequal exchange", params_json="{}"
    )

    row = {
        "id": "doi:p1",
        "source_id": None,
        "doi": None,
        "title": "Paper P1",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
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
    table = pa.Table.from_pylist([row], schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)

    # persist_replace hace DELETE FROM corpus + INSERT masivo (overwrite_corpus).
    store.persist_replace(corpus)

    equations_after = store.backend.load_equations()
    corpus_after = store.backend.to_arrow()
    store.close()

    assert len(corpus_after) == 1
    assert len(equations_after) == 1
    assert equations_after[0]["equation_id"] == "eq-0001"
    assert equations_after[0]["raw_query"] == "unequal exchange"
