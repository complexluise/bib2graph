"""Tests TDD — issue #158: chain --since (forrajeo incremental).

Verifica:
1. parse_since: ISO date y atajos relativos (90d, 6m, 1y).
2. chain --since -> MONITORED; chain sin --since -> FORAGED.
3. --since + direction=backward -> UsageError.
4. --since + direction=both -> forzado a forward (sin error).
5. new_candidates reportado en el envelope (campo aditivo).
6. Guarda corpus vacio cuando fsm_action="monitor".
7. run_monitor suelto sigue funcionando igual (delega en run_chain).
8. stdout puro: envelope una sola linea JSON (schema="1").

Marcador: unit (DuckDB en tmp_path, red mockeada con httpx.MockTransport).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
_SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (_FIXTURES_DIR / "sample_works.json").read_text(encoding="utf-8")
)

# Citante genuinamente nuevo: cita al seed W2741809807, no esta en el corpus.
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
        "https://openalex.org/W2741809807",
    ],
    "primary_location": {"source": {"display_name": "Test Journal"}},
    "type": "article",
}


def _make_row(
    *,
    id: str,
    source_id: str | None = None,
    is_seed: bool = True,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    """Fila minima con schema canonico completo."""
    return {
        "id": id,
        "source_id": source_id,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
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
    """Puebla un store DuckDB con filas y fija el estado del lazo."""
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
    store.close()


def _make_citing_transport(
    works: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """MockTransport que devuelve los works dados como citantes en la primera llamada."""
    if works is None:
        works = [_CITING_NEW_WORK]

    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        body = (
            {
                "results": works,
                "meta": {"count": len(works), "next_cursor": None},
            }
            if calls[0] == 1
            else {"results": [], "meta": {"count": 0, "next_cursor": None}}
        )
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
# 1. parse_since: ISO date y atajos relativos
# ---------------------------------------------------------------------------


class TestParseSince:
    """parse_since convierte string -> date para el flag --since."""

    def test_iso_date(self) -> None:
        """Fecha ISO YYYY-MM-DD -> date exacta."""
        from bib2graph.cli._options import parse_since

        result = parse_since("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_relativo_dias(self) -> None:
        """90d resta 90 dias desde la fecha base inyectada."""
        from bib2graph.cli._options import parse_since

        now = date(2024, 6, 1)
        result = parse_since("90d", now=now)
        assert result == now - timedelta(days=90)

    def test_relativo_meses(self) -> None:
        """6m resta 6*30 dias desde la fecha base."""
        from bib2graph.cli._options import parse_since

        now = date(2024, 6, 1)
        result = parse_since("6m", now=now)
        assert result == now - timedelta(days=180)

    def test_relativo_anios(self) -> None:
        """1y resta 365 dias desde la fecha base."""
        from bib2graph.cli._options import parse_since

        now = date(2024, 6, 1)
        result = parse_since("1y", now=now)
        assert result == now - timedelta(days=365)

    def test_mayusculas_relativo(self) -> None:
        """El atajo relativo es case-insensitive (90D, 6M, 1Y)."""
        from bib2graph.cli._options import parse_since

        now = date(2024, 6, 1)
        assert parse_since("90D", now=now) == parse_since("90d", now=now)
        assert parse_since("6M", now=now) == parse_since("6m", now=now)
        assert parse_since("1Y", now=now) == parse_since("1y", now=now)

    def test_formato_invalido_lanza_usage_error(self) -> None:
        """Formato no reconocido lanza UsageError con mensaje accionable."""
        from bib2graph.cli._options import parse_since
        from bib2graph.service.errors import UsageError

        with pytest.raises(UsageError, match="Formato de --since"):
            parse_since("invalid-value")

    def test_formato_invalido_parcial(self) -> None:
        """Fecha incompleta tambien lanza UsageError."""
        from bib2graph.cli._options import parse_since
        from bib2graph.service.errors import UsageError

        with pytest.raises(UsageError):
            parse_since("2024-01")  # no es YYYY-MM-DD

    def test_iso_minimo_format(self) -> None:
        """Fecha ISO de principio de anio."""
        from bib2graph.cli._options import parse_since

        result = parse_since("2024-01-01")
        assert result == date(2024, 1, 1)


# ---------------------------------------------------------------------------
# 2. chain --since -> MONITORED; chain normal -> FORAGED
# ---------------------------------------------------------------------------


class TestChainSinceTransicion:
    """chain --since transiciona a MONITORED; chain normal transiciona a FORAGED."""

    def test_chain_normal_transiciona_a_foraged(self, tmp_path: Path) -> None:
        """run_chain sin since -> FORAGED."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        run_chain(
            store_path,
            direction="forward",
            transport=_make_empty_transport(),
        )

        store = DuckDBStore(store_path)
        assert store.backend.loop_state() == CycleState.FORAGED
        store.close()

    def test_chain_since_transiciona_a_monitored(self, tmp_path: Path) -> None:
        """run_chain con since -> MONITORED."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        run_chain(
            store_path,
            direction="forward",
            since=date(2024, 1, 1),
            transport=_make_empty_transport(),
        )

        store = DuckDBStore(store_path)
        assert store.backend.loop_state() == CycleState.MONITORED
        store.close()

    def test_chain_since_devuelve_loop_state_monitored(self, tmp_path: Path) -> None:
        """El resultado de run_chain con since incluye loop_state=MONITORED."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="forward",
            since=date(2024, 1, 1),
            transport=_make_empty_transport(),
        )

        assert result["loop_state"] == "MONITORED"
        assert "round" in result

    def test_chain_normal_devuelve_loop_state_foraged(self, tmp_path: Path) -> None:
        """El resultado de run_chain normal incluye loop_state=FORAGED."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="forward",
            transport=_make_empty_transport(),
        )

        assert result["loop_state"] == "FORAGED"


# ---------------------------------------------------------------------------
# 3. --since + direction=backward -> UsageError
# ---------------------------------------------------------------------------


class TestChainSinceBackwardError:
    """--since + direction=backward -> UsageError accionable."""

    def test_since_backward_lanza_usage_error(self, tmp_path: Path) -> None:
        """run_chain con since y direction=backward lanza UsageError."""
        from bib2graph.cli._errors import UsageError
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        with pytest.raises(UsageError, match="backward"):
            run_chain(
                store_path,
                direction="backward",
                since=date(2024, 1, 1),
                transport=_make_empty_transport(),
            )


# ---------------------------------------------------------------------------
# 4. --since + direction=both -> forzado a forward (sin error)
# ---------------------------------------------------------------------------


class TestChainSinceBothForzaForward:
    """--since + direction=both fuerza effective_direction=forward."""

    def test_since_both_acepta_sin_error(self, tmp_path: Path) -> None:
        """run_chain con since y direction=both no lanza error y transiciona MONITORED."""
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="both",
            since=date(2024, 1, 1),
            transport=_make_empty_transport(),
        )

        # No debe lanzar; debe ir a MONITORED
        assert result["loop_state"] == "MONITORED"
        # La direccion efectiva debe ser forward
        assert result["direction"] == "forward"

        store = DuckDBStore(store_path)
        assert store.backend.loop_state() == CycleState.MONITORED
        store.close()


# ---------------------------------------------------------------------------
# 5. new_candidates reportado en el envelope
# ---------------------------------------------------------------------------


class TestChainNewCandidates:
    """new_candidates refleja los papers genuinamente nuevos vs el corpus."""

    def test_new_candidates_se_reporta(self, tmp_path: Path) -> None:
        """run_chain incluye new_candidates en el resultado."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="forward",
            transport=_make_empty_transport(),
        )

        assert "new_candidates" in result
        assert isinstance(result["new_candidates"], int)

    def test_new_candidates_cuenta_nuevos(self, tmp_path: Path) -> None:
        """new_candidates = 1 cuando se agrega un citante genuinamente nuevo."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="forward",
            transport=_make_citing_transport([_CITING_NEW_WORK]),
        )

        assert result["new_candidates"] == 1

    def test_new_candidates_cero_sin_nuevos(self, tmp_path: Path) -> None:
        """new_candidates = 0 cuando no hay citantes nuevos."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="forward",
            transport=_make_empty_transport(),
        )

        assert result["new_candidates"] == 0

    def test_new_candidates_en_chain_since(self, tmp_path: Path) -> None:
        """new_candidates tambien esta presente cuando se usa chain --since."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        result = run_chain(
            store_path,
            direction="forward",
            since=date(2024, 1, 1),
            transport=_make_citing_transport([_CITING_NEW_WORK]),
        )

        assert "new_candidates" in result
        assert result["new_candidates"] == 1

    def test_envelope_json_incluye_new_candidates(self, tmp_path: Path) -> None:
        """El envelope JSON de chain incluye new_candidates."""
        from bib2graph.cli._envelope import build_envelope
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        data = run_chain(
            store_path,
            direction="forward",
            transport=_make_empty_transport(),
        )
        envelope = build_envelope(command="chain", ok=True, data=data, exit_code=0)

        assert envelope["schema"] == "1"
        assert "new_candidates" in envelope["data"]

        # JSON-serializable y una sola linea (sin newlines internos)
        serialized = json.dumps(envelope)
        assert "\n" not in serialized, "El envelope debe ser una sola linea JSON"


# ---------------------------------------------------------------------------
# 6. Guarda corpus vacio cuando since activo
# ---------------------------------------------------------------------------


class TestChainSinceGuardaCorpusVacio:
    """chain --since falla con DataError si no hay corpus previo."""

    def test_since_sin_estado_previo_lanza_data_error(self, tmp_path: Path) -> None:
        """run_chain con since sin estado previo -> DataError accionable."""
        from bib2graph.cli._errors import DataError
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "empty.duckdb"
        DuckDBStore(store_path)  # inicializa tablas, sin estado

        with pytest.raises(DataError, match="b2g seed"):
            run_chain(
                store_path,
                direction="forward",
                since=date(2024, 1, 1),
                transport=_make_empty_transport(),
            )

    def test_since_corpus_vacio_lanza_data_error(self, tmp_path: Path) -> None:
        """run_chain con since y corpus vacio -> DataError accionable."""
        from bib2graph.cli._errors import DataError
        from bib2graph.cli.commands.chain import run_chain
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "no_papers.duckdb"
        store = DuckDBStore(store_path)
        store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
        store.close()

        with pytest.raises(DataError, match="b2g seed"):
            run_chain(
                store_path,
                direction="forward",
                since=date(2024, 1, 1),
                transport=_make_empty_transport(),
            )


# ---------------------------------------------------------------------------
# 7. run_monitor suelto delega en run_chain y sigue funcionando
# ---------------------------------------------------------------------------


class TestMonitorDelegaEnChain:
    """run_monitor suelto sigue funcionando igual (delega en run_chain)."""

    def test_monitor_encuentra_nuevos_y_transiciona_a_monitored(
        self, tmp_path: Path
    ) -> None:
        """run_monitor mergea 1 citante nuevo y transiciona a MONITORED."""
        from bib2graph.cli.commands.monitor import run_monitor
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "monitor.duckdb"
        _seed_store(store_path)

        data = run_monitor(
            store_path, transport=_make_citing_transport([_CITING_NEW_WORK])
        )

        store = DuckDBStore(store_path)
        assert store.backend.loop_state() == CycleState.MONITORED
        store.close()

        assert data["new_candidates"] == 1
        assert data["loop_state"] == "MONITORED"
        assert data["round"] == 1
        assert data["total_papers"] == 3

    def test_monitor_sin_nuevos_transiciona_a_monitored(self, tmp_path: Path) -> None:
        """run_monitor con 0 citantes igual transiciona a MONITORED."""
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
        store.close()

    def test_monitor_sin_estado_previo_lanza_data_error(self, tmp_path: Path) -> None:
        """run_monitor sin estado previo -> DataError accionable."""
        from bib2graph.cli._errors import DataError
        from bib2graph.cli.commands.monitor import run_monitor
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "empty.duckdb"
        DuckDBStore(store_path)

        with pytest.raises(DataError, match="b2g seed"):
            run_monitor(store_path, transport=_make_empty_transport())

    def test_monitor_corpus_vacio_lanza_data_error(self, tmp_path: Path) -> None:
        """run_monitor con corpus vacio -> DataError accionable."""
        from bib2graph.cli._errors import DataError
        from bib2graph.cli.commands.monitor import run_monitor
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "no_papers.duckdb"
        store = DuckDBStore(store_path)
        store.backend.set_loop_state(CycleState.SEEDED, cycle_round=1)
        store.close()

        with pytest.raises(DataError, match="b2g seed"):
            run_monitor(store_path, transport=_make_empty_transport())

    def test_monitor_envelope_json_schema_1(self, tmp_path: Path) -> None:
        """El envelope de monitor incluye schema='1' y los campos canonicos."""
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

        serialized = json.dumps(envelope)
        parsed = json.loads(serialized)
        assert parsed["data"]["loop_state"] == "MONITORED"


# ---------------------------------------------------------------------------
# 8. since filtra la URL enviada a OpenAlex (cableado de la ventana)
# ---------------------------------------------------------------------------


class TestChainSinceFiltroURL:
    """Cuando se pasa since, el filtro from_publication_date aparece en la URL."""

    def test_since_agrega_filtro_fecha_en_url(self, tmp_path: Path) -> None:
        """La URL enviada a OpenAlex incluye from_publication_date cuando since activo."""
        urls_llamadas: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            urls_llamadas.append(str(request.url))
            return httpx.Response(
                200,
                json={"results": [], "meta": {"count": 0, "next_cursor": None}},
                headers={"x-openalex-api-version": "2026-05-01"},
            )

        transport = httpx.MockTransport(handler)

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        from bib2graph.cli.commands.chain import run_chain

        run_chain(
            store_path,
            direction="forward",
            since=date(2024, 1, 1),
            transport=transport,
        )

        # Al menos una URL debe contener el filtro de fecha
        filtros_fecha = [u for u in urls_llamadas if "from_publication_date" in u]
        assert len(filtros_fecha) >= 1, (
            f"Ninguna URL contiene from_publication_date. URLs: {urls_llamadas}"
        )
        assert "2024-01-01" in filtros_fecha[0]

    def test_sin_since_no_agrega_filtro_fecha(self, tmp_path: Path) -> None:
        """Sin --since, la URL no contiene from_publication_date."""
        urls_llamadas: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            urls_llamadas.append(str(request.url))
            return httpx.Response(
                200,
                json={"results": [], "meta": {"count": 0, "next_cursor": None}},
                headers={"x-openalex-api-version": "2026-05-01"},
            )

        transport = httpx.MockTransport(handler)

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        from bib2graph.cli.commands.chain import run_chain

        run_chain(
            store_path,
            direction="forward",
            since=None,
            transport=transport,
        )

        filtros_fecha = [u for u in urls_llamadas if "from_publication_date" in u]
        assert len(filtros_fecha) == 0, (
            f"Sin --since no debe haber filtro de fecha. URLs: {urls_llamadas}"
        )
