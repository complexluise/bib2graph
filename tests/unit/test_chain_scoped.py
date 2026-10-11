"""Tests TDD — issue #309: forrajeo acotado (scoping, preview de fanout, budget).

`chain` forrajea sobre TODAS las semillas por default; el costo es
multiplicativo e invisible y puede agotar la cuota de OpenAlex (429
account-wide).  Este módulo cubre los guardarraíles ADITIVOS:

- ``--ids``/``--top``/``--scope``: acotan la unidad escopada del forrajeo
  (mutuamente excluyentes).  Sin ninguno: comportamiento actual (todas las
  semillas), sin cambios.
- ``--preview``: dry-run que estima el fanout SIN red, reflejando el scoping.
- ``--budget``: tope de llamadas HTTP; al alcanzarlo, para y reporta parcial,
  SIN reintentar.  Ante un 429 mockeado, tampoco reintenta si el budget ya
  se agotó.

Marcador: ``unit`` (DuckDB en tmp_path + httpx.MockTransport, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    source_id: str | None = None,
    is_seed: bool = True,
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    """Fila mínima con schema canónico completo."""
    return {
        "id": id,
        "source_id": source_id,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _seed_store_with_rows(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un store DuckDB con las filas dadas."""
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _citing_work(
    citer_id: str,
    *,
    cites_ids: list[str],
    title: str = "Citing Paper",
    year: int = 2022,
) -> dict[str, Any]:
    """Work JSON de OpenAlex que cita ``cites_ids`` (IDs cortos, sin prefijo)."""
    return {
        "id": f"https://openalex.org/{citer_id}",
        "doi": None,
        "title": title,
        "display_name": title,
        "publication_year": year,
        "language": "en",
        "abstract_inverted_index": None,
        "authorships": [],
        "keywords": [],
        "referenced_works": [f"https://openalex.org/{cid}" for cid in cites_ids],
        "primary_location": None,
        "type": "article",
    }


def _make_recording_transport(
    citing_by_seed: dict[str, list[dict[str, Any]]],
    *,
    calls: list[str],
) -> httpx.MockTransport:
    """Transport que responde a ``cites:`` según la semilla en el filtro y registra llamadas.

    ``citing_by_seed``: ``{seed_short_id: [work_json, ...]}``.  El handler
    determina qué semillas participan del filtro OR (``cites:W1|W2``) y
    devuelve la unión de los works asociados — así un test puede verificar
    que SOLO se consultó por las semillas esperadas (scoping, #309).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        filter_val: str = params.get("filter", "")
        calls.append(filter_val)
        if "cites:" not in filter_val:
            return httpx.Response(
                200,
                json={"results": [], "meta": {"count": 0, "next_cursor": None}},
                headers={"x-openalex-api-version": "2026-05-01"},
            )
        # Extraer los seed ids del filtro cites:W1|W2,...
        cites_segment = filter_val.split("cites:")[1].split(",")[0]
        seed_ids_in_filter = cites_segment.split("|")
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sid in seed_ids_in_filter:
            for work in citing_by_seed.get(sid, []):
                wid = work["id"]
                if wid not in seen:
                    seen.add(wid)
                    results.append(work)
        return httpx.Response(
            200,
            json={
                "results": results,
                "meta": {"count": len(results), "next_cursor": None},
            },
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# --preview: no hace red, reporta origin_count
# ---------------------------------------------------------------------------


class TestChainPreviewNoRed:
    def test_preview_no_llama_al_transport(self, tmp_path: Path) -> None:
        """--preview no debe hacer ninguna llamada HTTP (dry-run puro)."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", source_id="W1", references_id=["REF_A", "REF_B"])],
        )

        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            raise AssertionError("preview no debe hacer llamadas HTTP")

        transport = httpx.MockTransport(handler)

        result = run_chain(
            store_path,
            direction="backward",
            preview=True,
            transport=transport,
        )

        assert calls == [], f"preview hizo llamadas HTTP: {calls}"
        assert result["preview"] is True
        assert result["estimated_candidates"] == 2

    def test_preview_reporta_origin_count_todas_las_semillas_sin_scoping(
        self, tmp_path: Path
    ) -> None:
        """Sin --ids/--top/--scope, origin_count = nº de semillas (comportamiento actual)."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", source_id="W1", references_id=["REF_A"]),
                _row("P2", source_id="W2", references_id=["REF_B"]),
            ],
        )

        result = run_chain(store_path, direction="backward", preview=True)

        assert result["origin_count"] == 2

    def test_preview_con_ids_acota_origin_count_y_estimacion(
        self, tmp_path: Path
    ) -> None:
        """--preview --ids acota tanto origin_count como el fanout estimado."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", source_id="W1", references_id=["REF_A", "REF_B"]),
                _row("P2", source_id="W2", references_id=["REF_C"]),
            ],
        )

        result = run_chain(
            store_path,
            direction="backward",
            preview=True,
            ids=("P1",),
        )

        assert result["origin_count"] == 1
        # Solo cuenta REF_A/REF_B (de P1), no REF_C (de P2)
        assert result["estimated_candidates"] == 2
        assert result["by_direction"]["backward"] == 2

    def test_preview_con_scope_seeds_acota_origin_count(self, tmp_path: Path) -> None:
        """--preview --scope acota origin_count al subconjunto resuelto."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", source_id="W1", references_id=["REF_A"], is_seed=True),
                _row(
                    "P2",
                    source_id="W2",
                    references_id=["REF_B"],
                    is_seed=False,
                    curation_status="candidate",
                ),
            ],
        )

        result = run_chain(
            store_path,
            direction="backward",
            preview=True,
            scope="seeds",
        )

        # scope=seeds sólo incluye P1 (is_seed=True)
        assert result["origin_count"] == 1
        assert result["estimated_candidates"] == 1

    def test_preview_ids_y_top_juntos_es_usage_error(self, tmp_path: Path) -> None:
        """Combinar --ids y --top es un UsageError claro (mutuamente excluyentes)."""
        from bib2graph.cli._errors import UsageError
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(store_path, [_row("P1", source_id="W1")])

        with pytest.raises(UsageError):
            run_chain(
                store_path,
                direction="backward",
                preview=True,
                ids=("P1",),
                top=1,
            )

    def test_preview_ids_inexistente_es_usage_error(self, tmp_path: Path) -> None:
        """--ids con un id que no está en el corpus falla con UsageError."""
        from bib2graph.cli._errors import UsageError
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(store_path, [_row("P1", source_id="W1")])

        with pytest.raises(UsageError):
            run_chain(
                store_path,
                direction="backward",
                preview=True,
                ids=("NO_EXISTE",),
            )


# ---------------------------------------------------------------------------
# --ids / --top / --scope: forward chaining SOLO consulta el subconjunto
# ---------------------------------------------------------------------------


class TestChainForwardScopedFetch:
    """Verifica con mock que sólo se forrajea desde el subconjunto pedido."""

    def test_ids_acota_las_llamadas_a_esa_semilla(self, tmp_path: Path) -> None:
        """--ids P1 sólo debe consultar citantes de P1, no de P2."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", source_id="W1", curation_status="accepted"),
                _row("P2", source_id="W2", curation_status="accepted"),
            ],
        )

        calls: list[str] = []
        citing_by_seed = {
            "W1": [_citing_work("W9001", cites_ids=["W1"])],
            "W2": [_citing_work("W9002", cites_ids=["W2"])],
        }
        transport = _make_recording_transport(citing_by_seed, calls=calls)

        result = run_chain(
            store_path,
            direction="forward",
            ids=("P1",),
            transport=transport,
        )

        cites_calls = [c for c in calls if "cites:" in c]
        assert cites_calls, "debería haber al menos una llamada cites:"
        for c in cites_calls:
            assert "W2" not in c, f"--ids=P1 no debe consultar W2: {c}"
            assert "W1" in c

        # Solo el candidato de W1 se materializa
        result_ids = {item["id"] for item in result["ranking_preview"]}
        assert "W9002" not in result_ids

    def test_scope_seeds_solo_forrajea_semillas(self, tmp_path: Path) -> None:
        """--scope seeds excluye no-semillas del forward chaining."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", source_id="W1", is_seed=True, curation_status="accepted"),
            ],
        )

        calls: list[str] = []
        citing_by_seed = {"W1": [_citing_work("W9001", cites_ids=["W1"])]}
        transport = _make_recording_transport(citing_by_seed, calls=calls)

        run_chain(
            store_path,
            direction="forward",
            scope="seeds",
            transport=transport,
        )

        cites_calls = [c for c in calls if "cites:" in c]
        assert cites_calls
        assert "W1" in cites_calls[0]

    def test_top_1_acota_a_la_semilla_con_mas_referencias(self, tmp_path: Path) -> None:
        """--top 1 elige la semilla con más references_id (criterio documentado)."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row(
                    "P1",
                    source_id="W1",
                    curation_status="accepted",
                    references_id=["REF_A", "REF_B", "REF_C"],
                ),
                _row(
                    "P2",
                    source_id="W2",
                    curation_status="accepted",
                    references_id=["REF_D"],
                ),
            ],
        )

        calls: list[str] = []
        citing_by_seed = {
            "W1": [_citing_work("W9001", cites_ids=["W1"])],
            "W2": [_citing_work("W9002", cites_ids=["W2"])],
        }
        transport = _make_recording_transport(citing_by_seed, calls=calls)

        run_chain(
            store_path,
            direction="forward",
            top=1,
            transport=transport,
        )

        cites_calls = [c for c in calls if "cites:" in c]
        assert cites_calls
        # P1 tiene más referencias (3 vs 1) → debe ser la elegida
        assert "W1" in cites_calls[0]
        assert "W2" not in cites_calls[0]

    def test_top_0_es_usage_error(self, tmp_path: Path) -> None:
        from bib2graph.cli._errors import UsageError
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(store_path, [_row("P1", source_id="W1")])

        with pytest.raises(UsageError):
            run_chain(store_path, direction="backward", top=0)


# ---------------------------------------------------------------------------
# --budget: para al topar, reporta parcial, no reintenta ante 429
# ---------------------------------------------------------------------------


class TestChainBudget:
    def test_budget_topa_llamadas_y_reporta_parcial(self, tmp_path: Path) -> None:
        """--budget 1 detiene el forward chaining tras 1 llamada HTTP."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [
                _row("P1", source_id="W1", curation_status="accepted"),
                _row("P2", source_id="W2", curation_status="accepted"),
            ],
        )

        calls: list[str] = []
        citing_by_seed = {
            "W1": [_citing_work("W9001", cites_ids=["W1"])],
            "W2": [_citing_work("W9002", cites_ids=["W2"])],
        }
        transport = _make_recording_transport(citing_by_seed, calls=calls)

        result = run_chain(
            store_path,
            direction="forward",
            budget=1,
            transport=transport,
        )

        cites_calls = [c for c in calls if "cites:" in c]
        assert len(cites_calls) <= 1, (
            f"--budget=1 no debe hacer más de 1 llamada cites:; got {cites_calls}"
        )
        assert result["budget_used"] <= 1
        assert result["budget_stopped"] is True

    def test_sin_budget_no_marca_budget_stopped(self, tmp_path: Path) -> None:
        """Sin --budget (comportamiento actual), budget_stopped queda False."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", source_id="W1", curation_status="accepted")],
        )

        calls: list[str] = []
        citing_by_seed = {"W1": [_citing_work("W9001", cites_ids=["W1"])]}
        transport = _make_recording_transport(citing_by_seed, calls=calls)

        result = run_chain(store_path, direction="forward", transport=transport)

        assert result["budget_stopped"] is False
        assert result["budget_used"] == 0

    def test_budget_agotado_ante_429_no_reintenta_y_reporta_parcial(
        self, tmp_path: Path
    ) -> None:
        """Con budget=1 y un 429 en la única llamada permitida, NO reintenta.

        El comando NO debe fallar con excepción: para limpio y reporta
        estado parcial (``budget_stopped=True``) — exactamente el DoD de
        #309 ("ante un 429, no reintentar en loop: parar limpio y reportar").
        Se verifica con ``time.sleep`` mockeado que NUNCA se llamó (no hubo
        backoff) y que el mock recibió como máximo 1 request.
        """
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", source_id="W1", curation_status="accepted")],
        )

        calls: list[str] = []

        def handler_429(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(429, text="Rate limit exceeded")

        transport = httpx.MockTransport(handler_429)

        with patch("bib2graph.sources.openalex.time.sleep") as mock_sleep:
            result = run_chain(
                store_path,
                direction="forward",
                budget=1,
                transport=transport,
            )

        assert len(calls) == 1, (
            f"budget=1 debe hacer como máximo 1 llamada; got {calls}"
        )
        assert not mock_sleep.called, (
            "Con budget agotado en la primera llamada, NO debe reintentar "
            "(ni dormir el backoff)."
        )
        assert result["budget_stopped"] is True
        assert result["budget_used"] == 1
        # No crashea: el comando devuelve un resultado parcial pero consistente.
        assert result["total_papers"] == 1  # solo P1, ningún candidato materializado

    def test_budget_grande_no_para_forrajeo_normal(self, tmp_path: Path) -> None:
        """Un --budget holgado no interfiere con un forward chaining normal."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store_with_rows(
            store_path,
            [_row("P1", source_id="W1", curation_status="accepted")],
        )

        citing_by_seed = {"W1": [_citing_work("W9001", cites_ids=["W1"])]}
        transport = _make_recording_transport(citing_by_seed, calls=[])

        result = run_chain(
            store_path,
            direction="forward",
            budget=1000,
            transport=transport,
        )

        assert result["budget_stopped"] is False
        assert result["candidates_found"] >= 1


# ---------------------------------------------------------------------------
# Forager puro: CallBudget y origin_ids (sin pasar por el CLI)
# ---------------------------------------------------------------------------


class TestForagerCallBudgetUnit:
    def test_call_budget_exhausted_property(self) -> None:
        from bib2graph.foraging.base import CallBudget

        budget = CallBudget(2)
        assert budget.exhausted is False
        budget.record_call()
        assert budget.exhausted is False
        budget.record_call()
        assert budget.exhausted is True

    def test_call_budget_none_nunca_agotado(self) -> None:
        from bib2graph.foraging.base import CallBudget

        budget = CallBudget(None)
        for _ in range(100):
            budget.record_call()
        assert budget.exhausted is False

    def test_forager_origin_ids_acota_backward_preview(self) -> None:
        """Forager(origin_ids=...) acota el preview backward al subconjunto."""
        from unittest.mock import MagicMock

        from bib2graph.foraging.forager import Forager

        rows = [
            _row("P1", source_id="W1", references_id=["REF_A", "REF_B"]),
            _row("P2", source_id="W2", references_id=["REF_C"]),
        ]
        table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)

        forager = Forager(MagicMock(), depth=1, origin_ids={"P1"})
        preview = forager.preview(corpus, direction="backward")

        assert preview.by_direction["backward"] == 2  # solo REF_A, REF_B (de P1)


# ---------------------------------------------------------------------------
# Smoke test del wiring Click (barato, sin workspace — --help no lo requiere)
# ---------------------------------------------------------------------------


def test_chain_cmd_help_lista_los_flags_nuevos() -> None:
    """--ids/--top/--scope/--budget están registrados en el comando Click.

    Smoke test mínimo del wiring (no plumbing fino): confirma que Click no
    tiene errores de definición (tipos, duplicados) al construir el comando.
    """
    from click.testing import CliRunner

    from bib2graph.cli.commands.chain import chain_cmd

    runner = CliRunner()
    result = runner.invoke(chain_cmd, ["--help"])

    assert result.exit_code == 0, result.output
    for flag in ("--ids", "--top", "--scope", "--budget"):
        assert flag in result.output, f"{flag} no aparece en --help"
