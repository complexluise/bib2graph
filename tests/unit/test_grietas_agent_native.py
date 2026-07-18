"""Tests TDD del ADR 0045 — las tres grietas agent-native del release 0.12.0.

Sella el comportamiento aditivo de los issues #258/#259/#260 sobre el
envelope ``schema="1"`` existente:

1. (3a, #258) ``error.subcode`` — un 429 de OpenAlex mapea a
   ``NetworkError(subcode="RATE_LIMITED")``; un 504 (agotados los reintentos)
   mapea a ``subcode="UPSTREAM_TIMEOUT"``. El envelope de error los expone
   como ``error.subcode``; ``code``/``exit_code`` no cambian.
2. (3b, #259) ``data.workspace`` — comandos que resuelven workspace ecoan
   ``{"root", "source"}``; cuando ``source == "cwd"`` (walk-up implícito) se
   emite el warning accionable ``WORKSPACE_WALKUP_WARNING``.
3. (3c, #260) ``b2g schema`` — comando meta que emite el JSON-schema del
   envelope, los 6 exit codes y ``ENVELOPE_SCHEMA_VERSION`` por el mismo
   canal ``--json``.

Las tres son estrictamente aditivas: no tocan ``schema="1"``, los exit codes
0-5 ni la FSM (ver ADR 0045 y sus invariantes).

Marcador: ``unit`` (sin red real, ``httpx.MockTransport``/mocks para 429/504).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.sources.openalex import OpenAlexSource

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers de fixture de store (mismo patrón que test_workspace.py)
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *, id: str, title: str = "Test", curation_status: str = "candidate"
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "source_id": None,
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


def _seed_store(store_path: Path, rows: list[dict[str, Any]] | None = None) -> None:
    """Puebla un store con filas mínimas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


# ===========================================================================
# 1. (3a, #258) error.subcode — RATE_LIMITED / UPSTREAM_TIMEOUT
# ===========================================================================


class TestSubcodeNetworkError:
    """NetworkError transporta .subcode; el mapeo status→subcode es puro."""

    def test_network_error_subcode_default_none(self) -> None:
        """Sin subcode explícito, NetworkError.subcode es None (retrocompat)."""
        from bib2graph.service.errors import NetworkError

        exc = NetworkError("mensaje")
        assert exc.subcode is None
        assert exc.exit_code == 4
        assert exc.code == "NETWORK_ERROR"

    def test_network_error_subcode_explicito(self) -> None:
        """NetworkError acepta subcode explícito sin alterar exit_code/code."""
        from bib2graph.service.errors import NetworkError

        exc = NetworkError("mensaje", subcode="RATE_LIMITED")
        assert exc.subcode == "RATE_LIMITED"
        assert exc.exit_code == 4
        assert exc.code == "NETWORK_ERROR"

    @pytest.mark.parametrize(
        "status_code, expected_subcode",
        [
            (429, "RATE_LIMITED"),
            (504, "UPSTREAM_TIMEOUT"),
            (500, None),
            (404, None),
            (200, None),
        ],
    )
    def test_subcode_for_status(
        self, status_code: int, expected_subcode: str | None
    ) -> None:
        """subcode_for_status mapea 429/504 tipados; el resto → None."""
        from bib2graph.service.errors import subcode_for_status

        assert subcode_for_status(status_code) == expected_subcode


class TestOpenAlexSubcodePropagation:
    """El source de OpenAlex puebla NetworkError.subcode ante 429/504 reales."""

    def test_seed_429_agotado_propaga_rate_limited(self) -> None:
        """OpenAlexSource.seed con 429 → NetworkError(subcode='RATE_LIMITED')."""
        from bib2graph.service.errors import NetworkError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="Too Many Requests")

        transport = httpx.MockTransport(handler)
        source = OpenAlexSource(transport=transport)

        with pytest.raises(NetworkError) as exc_info:
            source.seed("unequal exchange")

        assert exc_info.value.subcode == "RATE_LIMITED"
        assert exc_info.value.exit_code == 4
        assert exc_info.value.code == "NETWORK_ERROR"

    def test_seed_504_propaga_upstream_timeout(self) -> None:
        """OpenAlexSource.seed con 504 → NetworkError(subcode='UPSTREAM_TIMEOUT')."""
        from bib2graph.service.errors import NetworkError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(504, text="Gateway Timeout")

        transport = httpx.MockTransport(handler)
        source = OpenAlexSource(transport=transport)

        with pytest.raises(NetworkError) as exc_info:
            source.seed("unequal exchange")

        assert exc_info.value.subcode == "UPSTREAM_TIMEOUT"
        assert exc_info.value.exit_code == 4

    def test_fetch_citing_429_agotado_propaga_rate_limited(self) -> None:
        """fetch_citing (retry path) con 429 agotado → subcode='RATE_LIMITED'."""
        from bib2graph.service.errors import NetworkError

        def handler_siempre_429(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="Rate limit exceeded")

        transport = httpx.MockTransport(handler_siempre_429)
        source = OpenAlexSource(transport=transport)

        with (
            patch("bib2graph.sources.openalex.time.sleep"),
            pytest.raises(NetworkError) as exc_info,
        ):
            source.fetch_citing("W99999")

        assert exc_info.value.subcode == "RATE_LIMITED"

    def test_fetch_citing_504_agotado_propaga_upstream_timeout(self) -> None:
        """fetch_citing (retry path) con 504 agotado → subcode='UPSTREAM_TIMEOUT'."""
        from bib2graph.service.errors import NetworkError

        def handler_siempre_504(request: httpx.Request) -> httpx.Response:
            return httpx.Response(504, text="Gateway Timeout")

        transport = httpx.MockTransport(handler_siempre_504)
        source = OpenAlexSource(transport=transport)

        with (
            patch("bib2graph.sources.openalex.time.sleep"),
            pytest.raises(NetworkError) as exc_info,
        ):
            source.fetch_citing("W99999")

        assert exc_info.value.subcode == "UPSTREAM_TIMEOUT"


class TestEnvelopeErrorSubcode:
    """build_envelope/_emit_error_envelope exponen error.subcode aditivamente."""

    def test_build_envelope_con_subcode(self) -> None:
        """build_envelope(error={..., "subcode": ...}) lo preserva en el dict."""
        from bib2graph.service.envelope import build_envelope

        envelope = build_envelope(
            command="seed",
            ok=False,
            data={},
            exit_code=4,
            error={
                "code": "NETWORK_ERROR",
                "message": "429",
                "subcode": "RATE_LIMITED",
            },
        )

        assert envelope["schema"] == "1"
        assert envelope["error"]["code"] == "NETWORK_ERROR"
        assert envelope["error"]["subcode"] == "RATE_LIMITED"

    def test_build_envelope_sin_subcode_no_rompe(self) -> None:
        """build_envelope sin 'subcode' en error sigue funcionando (aditivo)."""
        from bib2graph.service.envelope import build_envelope

        envelope = build_envelope(
            command="build",
            ok=False,
            data={},
            exit_code=3,
            error={"code": "DEPENDENCY_ERROR", "message": "falta algo"},
        )

        assert envelope["error"] == {
            "code": "DEPENDENCY_ERROR",
            "message": "falta algo",
        }
        assert "subcode" not in envelope["error"]

    def test_handle_errors_networkerror_subcode_en_envelope_json(self) -> None:
        """@handle_errors propaga NetworkError.subcode a error.subcode (--json)."""
        import json

        from bib2graph.cli._errors import handle_errors
        from bib2graph.service.errors import NetworkError

        @handle_errors("seed")
        def fn_rate_limited(json_output: bool = False) -> None:
            raise NetworkError("429 Too Many Requests", subcode="RATE_LIMITED")

        with (
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            fn_rate_limited(json_output=True)

        assert exc_info.value.code == 4
        # El primer arg posicional de print() es la línea JSON del envelope.
        printed = mock_print.call_args_list[0].args[0]
        envelope = json.loads(printed)
        assert envelope["exit_code"] == 4
        assert envelope["error"]["code"] == "NETWORK_ERROR"
        assert envelope["error"]["subcode"] == "RATE_LIMITED"

    def test_handle_errors_networkerror_sin_subcode_omite_clave(self) -> None:
        """NetworkError sin subcode → error.subcode ausente (no 'null' ensuciando)."""
        import json

        from bib2graph.cli._errors import handle_errors
        from bib2graph.service.errors import NetworkError

        @handle_errors("seed")
        def fn_sin_subcode(json_output: bool = False) -> None:
            raise NetworkError("timeout genérico sin status tipado")

        with patch("builtins.print") as mock_print, pytest.raises(SystemExit):
            fn_sin_subcode(json_output=True)

        printed = mock_print.call_args_list[0].args[0]
        envelope = json.loads(printed)
        assert envelope["error"]["code"] == "NETWORK_ERROR"
        assert "subcode" not in envelope["error"]

    def test_handle_errors_httpstatuserror_429_deriva_subcode(self) -> None:
        """Un httpx.HTTPStatusError 429 crudo (no traducido a NetworkError)
        también deriva subcode='RATE_LIMITED' en el envelope."""
        import json

        from bib2graph.cli._errors import handle_errors

        @handle_errors("chain")
        def fn_http_429(json_output: bool = False) -> None:
            response = MagicMock()
            response.status_code = 429
            raise httpx.HTTPStatusError("429", request=MagicMock(), response=response)

        with (
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            fn_http_429(json_output=True)

        assert exc_info.value.code == 4
        printed = mock_print.call_args_list[0].args[0]
        envelope = json.loads(printed)
        assert envelope["error"]["code"] == "NETWORK_ERROR"
        assert envelope["error"]["subcode"] == "RATE_LIMITED"

    def test_handle_errors_httpstatuserror_504_deriva_subcode(self) -> None:
        """Un httpx.HTTPStatusError 504 crudo deriva subcode='UPSTREAM_TIMEOUT'."""
        import json

        from bib2graph.cli._errors import handle_errors

        @handle_errors("chain")
        def fn_http_504(json_output: bool = False) -> None:
            response = MagicMock()
            response.status_code = 504
            raise httpx.HTTPStatusError("504", request=MagicMock(), response=response)

        with patch("builtins.print") as mock_print, pytest.raises(SystemExit):
            fn_http_504(json_output=True)

        printed = mock_print.call_args_list[0].args[0]
        envelope = json.loads(printed)
        assert envelope["error"]["subcode"] == "UPSTREAM_TIMEOUT"

    def test_handle_errors_exit_code_y_code_no_cambian(self) -> None:
        """Invariante ADR 0045: exit_code sigue 4 y code sigue NETWORK_ERROR."""
        import json

        from bib2graph.cli._errors import handle_errors
        from bib2graph.service.errors import NetworkError

        @handle_errors("seed")
        def fn(json_output: bool = False) -> None:
            raise NetworkError("429", subcode="RATE_LIMITED")

        with (
            patch("builtins.print") as mock_print,
            pytest.raises(SystemExit) as exc_info,
        ):
            fn(json_output=True)

        assert exc_info.value.code == 4
        envelope = json.loads(mock_print.call_args_list[0].args[0])
        assert envelope["exit_code"] == 4
        assert envelope["error"]["code"] == "NETWORK_ERROR"
        assert envelope["ok"] is False


# ===========================================================================
# 2. (3b, #259) data.workspace + warning en walk-up
# ===========================================================================


class TestWorkspaceEchoHelpers:
    """workspace_echo/workspace_walkup_warning (cli._store) — helper puro."""

    def test_workspace_echo_forma(self, tmp_path: Path) -> None:
        from bib2graph.cli._store import workspace_echo
        from bib2graph.workspace import Workspace

        ws = Workspace.init(tmp_path / "proyecto", "proyecto")
        echo = workspace_echo(ws)

        assert echo == {"root": str(ws.root), "source": "init"}

    def test_workspace_walkup_warning_ausente_si_no_es_cwd(
        self, tmp_path: Path
    ) -> None:
        from bib2graph.cli._store import resolve_workspace, workspace_walkup_warning

        ws_dir = tmp_path / "proyecto"
        from bib2graph.workspace import Workspace

        Workspace.init(ws_dir, "proyecto")

        ws = resolve_workspace({"workspace": str(ws_dir)})
        assert ws.source == "flag"
        assert workspace_walkup_warning(ws) == []

    def test_workspace_walkup_warning_presente_si_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bib2graph.cli._store import (
            WORKSPACE_WALKUP_WARNING,
            resolve_workspace,
            workspace_walkup_warning,
        )
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "proyecto"
        Workspace.init(ws_dir, "proyecto")
        monkeypatch.chdir(ws_dir)
        monkeypatch.delenv("B2G_WORKSPACE", raising=False)

        ws = resolve_workspace({"workspace": None})
        assert ws.source == "cwd"
        assert workspace_walkup_warning(ws) == [WORKSPACE_WALKUP_WARNING]


class TestStatusCommandWorkspaceEcho:
    """status ya implementaba data.workspace (ADR 0029); sigue intacto."""

    def test_status_cmd_json_incluye_workspace(self, tmp_path: Path) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        ws_dir = tmp_path / "proyecto"
        from bib2graph.workspace import Workspace

        Workspace.init(ws_dir, "proyecto")
        _seed_store(ws_dir / "library.duckdb")

        runner = CliRunner()
        result = runner.invoke(b2g, ["--workspace", str(ws_dir), "status", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert "workspace" in envelope["data"]
        assert envelope["data"]["workspace"]["source"] == "flag"


class TestCicloCommandsWorkspaceEcho:
    """Comandos del ciclo que resuelven workspace ecoan data.workspace (ADR 0045 #259).

    Cubre representativamente comandos que antes usaban ``resolve_library_path``
    (validate, curate accept) y comandos que ya usaban ``resolve_workspace``
    pero no ecoaban (export, build, read list).
    """

    def _init_ws_with_store(self, tmp_path: Path) -> Path:
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "proyecto"
        Workspace.init(ws_dir, "proyecto")
        _seed_store(ws_dir / "library.duckdb")
        return ws_dir

    def test_validate_incluye_workspace(self, tmp_path: Path) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        ws_dir = self._init_ws_with_store(tmp_path)
        runner = CliRunner()
        result = runner.invoke(b2g, ["--workspace", str(ws_dir), "validate", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["workspace"]["source"] == "flag"
        assert envelope["data"]["workspace"]["root"] == str(ws_dir.resolve())

    def test_read_list_incluye_workspace(self, tmp_path: Path) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        ws_dir = self._init_ws_with_store(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            b2g, ["--workspace", str(ws_dir), "read", "list", "--json"]
        )

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["workspace"] == {
            "root": str(ws_dir.resolve()),
            "source": "flag",
        }

    def test_curate_accept_incluye_workspace(self, tmp_path: Path) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        ws_dir = self._init_ws_with_store(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws_dir),
                "curate",
                "accept",
                "--ids",
                "P1",
                "--json",
            ],
        )

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["workspace"]["source"] == "flag"

    def test_export_incluye_workspace(self, tmp_path: Path) -> None:
        """export (ya usaba resolve_workspace) ahora también ecoa (antes no lo hacía)."""
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        ws_dir = self._init_ws_with_store(tmp_path)
        # export exige artefactos de build previos; falla con DataError (exit 2)
        # si no hay build, pero igual debe llegar al envelope de error (no aplica
        # data.workspace en error). Para el caso ok, corremos build antes.
        runner = CliRunner()
        build_result = runner.invoke(b2g, ["--workspace", str(ws_dir), "build"])
        assert build_result.exit_code == 0

        result = runner.invoke(b2g, ["--workspace", str(ws_dir), "export", "--json"])
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["workspace"]["source"] == "flag"

    def test_walkup_source_cwd_emite_warning_en_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Un comando invocado sin --workspace/B2G_WORKSPACE, resuelto por cwd,
        emite el warning accionable de walk-up (ADR 0045 #259)."""
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.cli._store import WORKSPACE_WALKUP_WARNING

        ws_dir = self._init_ws_with_store(tmp_path)
        monkeypatch.chdir(ws_dir)
        monkeypatch.delenv("B2G_WORKSPACE", raising=False)

        runner = CliRunner()
        result = runner.invoke(b2g, ["status", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["workspace"]["source"] == "cwd"
        assert WORKSPACE_WALKUP_WARNING in envelope["warnings"]

    def test_walkup_source_flag_no_emite_warning(self, tmp_path: Path) -> None:
        """Con --workspace explícito (source='flag'), NO se emite el warning."""
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.cli._store import WORKSPACE_WALKUP_WARNING

        ws_dir = self._init_ws_with_store(tmp_path)
        runner = CliRunner()
        result = runner.invoke(b2g, ["--workspace", str(ws_dir), "status", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["data"]["workspace"]["source"] == "flag"
        assert WORKSPACE_WALKUP_WARNING not in envelope["warnings"]


class TestMetaCommandsSinWorkspace:
    """skill/schema NO ecoan data.workspace (comandos meta, ADR 0045)."""

    def test_skill_add_no_tiene_workspace_en_data(self, tmp_path: Path) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["skill", "add", "--project", "--json"],
            env={"HOME": str(tmp_path)},
        )
        # No importa el resultado exacto (puede fallar por I/O de skill vendida
        # en el entorno de test); solo verificamos que si hay data, no tiene
        # la clave workspace.
        if result.output.strip():
            try:
                envelope = json.loads(result.output)
            except json.JSONDecodeError:
                return
            assert "workspace" not in envelope.get("data", {})

    def test_schema_no_tiene_workspace_en_data(self) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert "workspace" not in envelope["data"]


# ===========================================================================
# 3. (3c, #260) b2g schema — comando meta de introspección del contrato
# ===========================================================================


class TestSchemaCommand:
    """b2g schema emite envelope_schema, exit_codes y contract_version."""

    def test_schema_json_ok_exit_0(self) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert envelope["command"] == "schema"
        assert envelope["exit_code"] == 0
        assert envelope["error"] is None

    def test_schema_contract_version_coincide_con_envelope_schema_version(self) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.service.envelope import ENVELOPE_SCHEMA_VERSION

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema", "--json"])
        envelope = json.loads(result.output)

        assert envelope["data"]["contract_version"] == ENVELOPE_SCHEMA_VERSION

    def test_schema_incluye_json_schema_del_envelope(self) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema", "--json"])
        envelope = json.loads(result.output)

        env_schema = envelope["data"]["envelope_schema"]
        assert env_schema["type"] == "object"
        for key in (
            "schema",
            "ok",
            "command",
            "exit_code",
            "data",
            "warnings",
            "error",
        ):
            assert key in env_schema["properties"]
            assert key in env_schema["required"]

    def test_schema_incluye_seis_exit_codes(self) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema", "--json"])
        envelope = json.loads(result.output)

        exit_codes = envelope["data"]["exit_codes"]
        assert len(exit_codes) == 6
        codes = {entry["code"] for entry in exit_codes}
        assert codes == {0, 1, 2, 3, 4, 5}

    def test_schema_exit_codes_tienen_nombre_y_significado(self) -> None:
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema", "--json"])
        envelope = json.loads(result.output)

        by_code = {e["code"]: e for e in envelope["data"]["exit_codes"]}
        assert by_code[1]["name"] == "USAGE_ERROR"
        assert by_code[2]["name"] == "DATA_ERROR"
        assert by_code[3]["name"] == "DEPENDENCY_ERROR"
        assert by_code[4]["name"] == "NETWORK_ERROR"
        assert by_code[5]["name"] == "STORE_ERROR"
        for entry in envelope["data"]["exit_codes"]:
            assert entry["meaning"]

    def test_schema_no_transiciona_fsm_ni_requiere_store(self, tmp_path: Path) -> None:
        """b2g schema funciona sin workspace/store — comando meta puro."""
        import json

        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        # Corre en un directorio SIN workspace.json y sin --workspace.
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(b2g, ["schema", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["ok"] is True

    def test_schema_modo_humano_no_json(self) -> None:
        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["schema"])

        assert result.exit_code == 0
        assert "Exit codes" in result.output
        assert "NETWORK_ERROR" in result.output

    def test_schema_registrado_fuera_de_verbos_ciclo(self) -> None:
        """b2g --help lista 'schema' como comando disponible (meta, junto a skill)."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g

        runner = CliRunner()
        result = runner.invoke(b2g, ["--help"])

        assert result.exit_code == 0
        assert "schema" in result.output
        assert "skill" in result.output

    def test_build_schema_data_es_funcion_pura(self) -> None:
        """build_schema_data no requiere I/O ni argumentos — determinista."""
        from bib2graph.cli.commands.schema import build_schema_data

        d1 = build_schema_data()
        d2 = build_schema_data()
        assert d1 == d2
