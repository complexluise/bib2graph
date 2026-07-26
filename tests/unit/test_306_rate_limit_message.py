"""Tests TDD — issue #306: el 429 de OpenAlex se reporta como error de conexión.

Contexto (QA, sesión capstone): ``b2g chain --direction forward`` sobre
un corpus grande topó el rate-limit de OpenAlex.  El mensaje reportado fue
"Error de red (HTTPStatusError)... Verificá tu conexión a internet y
reintentá." — un misdiagnóstico peligroso: (1) un 429 NO es un problema de
conexión, es rate-limit/cuota account-wide (recuperación de horas); (2) el
consejo "reintentá" induce a un agente a reintentar en loop y quemar más
cuota.

Cubre, extremo a extremo:
1. ``OpenAlexSource.fetch_citing_batch``/``fetch_citing_batch_with_works``
   (el path de ``chain --direction forward``, exactamente el escenario del
   issue) traducen un 429 agotado a ``NetworkError(subcode="RATE_LIMITED")``
   en vez de dejar escapar el ``httpx.HTTPStatusError`` crudo.
2. ``run_chain`` (núcleo del comando ``chain``, sin Click) propaga esa
   ``NetworkError`` con el subcode intacto.
3. El decorador ``@handle_errors`` la captura y el envelope ``--json`` de
   error expone ``error.subcode == "RATE_LIMITED"``; el mensaje humano NO
   dice "conexión" ni aconseja "reintentá" a secas.

Subcode elegido: ``RATE_LIMITED`` (no ``openalex_rate_limit``) — reutiliza
el subcode ya establecido por el ADR 0045 (#258, ``NetworkError.subcode`` /
``subcode_for_status``), evitando duplicar convención.

Marcador: ``unit`` (sin red real, ``httpx.MockTransport``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.service.errors import NetworkError
from bib2graph.sources.openalex import OpenAlexSource

pytestmark = pytest.mark.unit


def _make_row(*, id: str, source_id: str | None = None) -> dict[str, Any]:
    """Fila mínima con schema canónico completo (semilla aceptada)."""
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
        "is_seed": True,
        "curation_status": "accepted",
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


def _seed_store(store_path: Path) -> None:
    """Puebla un store DuckDB con una semilla aceptada, lista para chain forward."""
    from bib2graph.corpus import Corpus
    from bib2graph.cycle import apply_transition
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_row(id="P1", source_id="W2741809807")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    new_state, new_round = apply_transition(None, "seed", 0)
    store.backend.set_loop_state(new_state, cycle_round=new_round)
    store.close()


def _make_always_429_transport(
    *, retry_after: str | None = None
) -> httpx.MockTransport:
    """MockTransport que siempre responde 429 (rate-limit agotado)."""

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": retry_after} if retry_after else {}
        return httpx.Response(429, text="Rate limit exceeded", headers=headers)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# 1. Source: el batch citing path (chain forward) traduce 429 → NetworkError
# ---------------------------------------------------------------------------


class TestSourceBatchCitingTraduceRateLimit:
    """El path real de ``chain --direction forward`` (batch citing) ya no
    deja escapar el httpx.HTTPStatusError crudo ante un 429 agotado."""

    def test_fetch_citing_batch_no_deja_escapar_httpstatuserror_crudo(self) -> None:
        """fetch_citing_batch con 429 agotado NUNCA propaga httpx.HTTPStatusError
        pelado — siempre se traduce a NetworkError (accionable)."""
        transport = _make_always_429_transport()
        source = OpenAlexSource(transport=transport)

        with (
            patch("bib2graph.sources.openalex.time.sleep"),
            pytest.raises(NetworkError),
        ):
            source.fetch_citing_batch(["W2741809807"])

    def test_fetch_citing_batch_subcode_rate_limited(self) -> None:
        """El subcode elegido para un 429 es RATE_LIMITED (convención ADR 0045)."""
        transport = _make_always_429_transport()
        source = OpenAlexSource(transport=transport)

        with (
            patch("bib2graph.sources.openalex.time.sleep"),
            pytest.raises(NetworkError) as exc_info,
        ):
            source.fetch_citing_batch(["W2741809807"])

        assert exc_info.value.subcode == "RATE_LIMITED"
        assert exc_info.value.exit_code == 4
        assert exc_info.value.code == "NETWORK_ERROR"


# ---------------------------------------------------------------------------
# 2. run_chain (núcleo del comando, sin Click) propaga NetworkError intacta
# ---------------------------------------------------------------------------


class TestRunChainForwardPropagaRateLimit:
    """run_chain(direction='forward') ante 429 agotado de OpenAlex."""

    def test_run_chain_forward_429_propaga_network_error_con_subcode(
        self, tmp_path: Path
    ) -> None:
        """run_chain --direction forward con 429 agotado -> NetworkError con
        subcode='RATE_LIMITED' (no un httpx.HTTPStatusError crudo)."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        with (
            patch("bib2graph.sources.openalex.time.sleep"),
            pytest.raises(NetworkError) as exc_info,
        ):
            run_chain(
                store_path,
                direction="forward",
                transport=_make_always_429_transport(),
            )

        assert exc_info.value.subcode == "RATE_LIMITED"

    def test_run_chain_forward_429_mensaje_nombra_rate_limit_no_conexion(
        self, tmp_path: Path
    ) -> None:
        """El mensaje de la NetworkError propagada por run_chain nombra
        rate-limit/cuota; NO dice 'conexión' ni aconseja 'reintentá' a secas."""
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        with (
            patch("bib2graph.sources.openalex.time.sleep"),
            pytest.raises(NetworkError) as exc_info,
        ):
            run_chain(
                store_path,
                direction="forward",
                transport=_make_always_429_transport(),
            )

        msg_lower = str(exc_info.value).lower()
        assert "conexión" not in msg_lower
        assert "conexion" not in msg_lower
        assert "rate-limit" in msg_lower or "cuota" in msg_lower


# ---------------------------------------------------------------------------
# 3. @handle_errors + envelope --json: error.subcode y mensaje humano
# ---------------------------------------------------------------------------


class TestHandleErrorsEnvelopeRateLimit306:
    """El envelope --json y el mensaje humano tratan el 429 distinto de un
    error de red genérico (#306 DoD)."""

    def test_envelope_json_error_subcode_rate_limited(self, tmp_path: Path) -> None:
        """El envelope de error --json de 'chain' expone
        error.subcode == 'RATE_LIMITED' para un agente que ramifica sin parsear
        texto."""
        from bib2graph.cli._errors import handle_errors
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        @handle_errors("chain")
        def fn(json_output: bool = False) -> None:
            with patch("bib2graph.sources.openalex.time.sleep"):
                run_chain(
                    store_path,
                    direction="forward",
                    transport=_make_always_429_transport(),
                )

        with (
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            fn(json_output=True)

        assert exc_info.value.code == 4
        printed = mock_print.call_args_list[0].args[0]
        envelope = json.loads(printed)
        assert envelope["ok"] is False
        assert envelope["exit_code"] == 4
        assert envelope["error"]["code"] == "NETWORK_ERROR"
        assert envelope["error"]["subcode"] == "RATE_LIMITED"
        # El mensaje del envelope tampoco debe decir "conexión" ni "reintentá".
        msg_lower = envelope["error"]["message"].lower()
        assert "conexión" not in msg_lower
        assert "conexion" not in msg_lower

    def test_mensaje_humano_stderr_no_dice_conexion_ni_reintenta(
        self, tmp_path: Path
    ) -> None:
        """En modo humano (sin --json), el mensaje impreso tampoco dice
        'conexión' ni aconseja 'reintentá' a secas ante un 429."""
        from bib2graph.cli._errors import handle_errors
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        @handle_errors("chain")
        def fn(json_output: bool = False) -> None:
            with patch("bib2graph.sources.openalex.time.sleep"):
                run_chain(
                    store_path,
                    direction="forward",
                    transport=_make_always_429_transport(),
                )

        with patch("builtins.print") as mock_print, pytest.raises(SystemExit):
            fn(json_output=False)

        # En modo humano, handle_errors imprime "Error: {message}" por stderr
        # (kwargs file=sys.stderr en el print real; el mock captura igual).
        printed_text = " ".join(
            str(call.args[0]) for call in mock_print.call_args_list if call.args
        )
        printed_lower = printed_text.lower()
        assert "conexión" not in printed_lower
        assert "conexion" not in printed_lower
        assert "rate-limit" in printed_lower or "cuota" in printed_lower

    def test_mensaje_sugiere_esperar_reset_o_reducir_alcance(
        self, tmp_path: Path
    ) -> None:
        """El mensaje sugiere esperar el reset de cuota o reducir el alcance
        del forrajeo (--top/--ids, #309) — no un 'reintentá' desnudo."""
        from bib2graph.cli._errors import handle_errors
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path)

        @handle_errors("chain")
        def fn(json_output: bool = False) -> None:
            with patch("bib2graph.sources.openalex.time.sleep"):
                run_chain(
                    store_path,
                    direction="forward",
                    transport=_make_always_429_transport(),
                )

        with (
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit),
        ):
            fn(json_output=True)

        printed = mock_print.call_args_list[0].args[0]
        envelope = json.loads(printed)
        msg = envelope["error"]["message"]
        assert "--top" in msg or "--ids" in msg
