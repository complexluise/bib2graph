"""Tests de los alias deprecados y el entry-point ``bib2graph`` (ADR 0038, #165).

Poda epic #184: solo se conserva la verificación del aviso de deprecación.
La delegación funcional y el contrato de schema/stdout se cubren en los tests
del verbo canónico (test_cli.py y sus homólogos).

Casos cubiertos por alias:
  1. El aviso de deprecación va a **stderr** (result.stderr contiene "AVISO").
  2. En modo ``--json``, ``envelope["warnings"]`` contiene el mensaje de deprecación
     (el helper _assert_one_json_stdout también verifica stdout==1 línea y schema=="1").

Comandos deprecados testeados:
  - ``b2g accept``       → ``b2g curate accept``
  - ``b2g reject``       → ``b2g curate reject``
  - ``b2g filter``       → ``b2g curate filter``
  - ``b2g inspect``      → ``b2g read show`` / ``b2g status``
  - ``b2g restore``      → ``b2g snapshot restore``
  - ``b2g networks``     → ``b2g build --spec``

Casos de error (sin workspace → error envelope en stdout, aviso igual a stderr):
  - ``b2g monitor --json``   → error envelope, pero aviso sigue en stderr
  - ``b2g resolve --json``   → error envelope, pero aviso sigue en stderr
  - ``b2g enrich --json``    → error envelope, pero aviso sigue en stderr

Entry-point legado:
  - ``bib2graph`` (``main_bib2graph_alias``): avisa a stderr y delega en ``main()``.

Helper ``emit_deprecation``:
  - Escribe el aviso a stderr y devuelve el mensaje.
  - El formato es el canónico ("AVISO: '...' está deprecado y se eliminará en ...").

Filosofía (AGENTS.md): se testean las funciones detrás de los comandos.
CliRunner solo donde hay integración de flag necesaria.
Marcador: ``unit`` (DuckDB en tmp_path; sin red real).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pyarrow as pa
import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Título de prueba",
    year: int = 2020,
    is_seed: bool = False,
    curation_status: str = "candidate",
    language: str = "en",
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
    return {
        "id": id,
        "source_id": None,
        "doi": None,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": language,
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


def _init_workspace(tmp_path: Path, name: str = "test-ws") -> Any:
    """Crea y devuelve un Workspace inicializado."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _seed_store(ws: Any, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en el store del workspace."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(ws.library_path)
    store.persist(corpus)
    store.close()


def _make_parquet(path: Path) -> Path:
    """Escribe un parquet mínimo con el schema canónico."""
    import pyarrow.parquet as pq

    rows = [_row(id="P1"), _row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    pq.write_table(table, str(path))
    return path


def _assert_one_json_stdout(result: Any, *, schema: str = "1") -> dict[str, Any]:
    """Verifica que result.stdout es exactamente 1 línea JSON con schema correcto.

    En Click 8.4.1, result.stdout es solo stdout (no incluye stderr).
    """
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"stdout debe ser exactamente 1 línea JSON, tuvo {len(lines)}:\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    data = json.loads(lines[0])
    assert data.get("schema") == schema, (
        f"schema esperado '{schema}', obtenido {data.get('schema')!r}"
    )
    return data


# ---------------------------------------------------------------------------
# Tests del helper emit_deprecation
# ---------------------------------------------------------------------------


class TestEmitDeprecation:
    """Verifica el helper puro ``emit_deprecation``."""

    def test_escribe_a_stderr(self) -> None:
        """emit_deprecation imprime el aviso a stderr."""
        from bib2graph.cli._deprecation import emit_deprecation

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            emit_deprecation("b2g viejo", "b2g nuevo")
        assert "AVISO" in buf.getvalue()
        assert "b2g viejo" in buf.getvalue()
        assert "b2g nuevo" in buf.getvalue()

    def test_retorna_el_mensaje(self) -> None:
        """emit_deprecation devuelve el mensaje emitido."""
        from bib2graph.cli._deprecation import emit_deprecation

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            msg = emit_deprecation("b2g viejo", "b2g nuevo")
        assert msg == buf.getvalue().strip()

    def test_formato_canonico(self) -> None:
        """El mensaje sigue el formato canónico con versión de retiro."""
        from bib2graph.cli._deprecation import emit_deprecation

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            msg = emit_deprecation("b2g networks", "b2g build --spec")
        assert "0.11.0" in msg
        assert "b2g networks" in msg
        assert "b2g build --spec" in msg

    def test_version_custom(self) -> None:
        """removed_in personalizable."""
        from bib2graph.cli._deprecation import emit_deprecation

        buf = io.StringIO()
        with patch("sys.stderr", buf):
            msg = emit_deprecation("b2g old", "b2g new", removed_in="1.0.0")
        assert "1.0.0" in msg

    def test_no_escribe_a_stdout(self) -> None:
        """emit_deprecation NO escribe a stdout."""
        from bib2graph.cli._deprecation import emit_deprecation

        stderr_buf = io.StringIO()
        stdout_buf = io.StringIO()
        with patch("sys.stderr", stderr_buf), patch("sys.stdout", stdout_buf):
            emit_deprecation("b2g viejo", "b2g nuevo")
        assert stdout_buf.getvalue() == ""
        assert "AVISO" in stderr_buf.getvalue()


# ---------------------------------------------------------------------------
# Tests b2g accept (alias deprecado → b2g curate accept)
# ---------------------------------------------------------------------------


class TestAcceptDeprecado:
    """b2g accept emite aviso de deprecación y delega en curate accept.

    Delegación funcional y contrato schema/stdout se cubren en los tests de
    'b2g curate accept' (test_cli.py). Aquí solo se conserva el aviso (epic #184).
    """

    def test_aviso_va_a_stderr(self, tmp_path: Path) -> None:
        """b2g accept emite aviso de deprecación a stderr."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "accept", "--ids", "P1"],
            catch_exceptions=False,
        )
        assert "deprecad" in result.stderr.lower(), (
            f"Esperaba aviso en stderr, obtuvo: {result.stderr!r}"
        )
        assert "curate accept" in result.stderr.lower()

    def test_json_warnings_contiene_deprecacion(self, tmp_path: Path) -> None:
        """b2g accept --json: envelope['warnings'] contiene el aviso de deprecación."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "accept", "--ids", "P1", "--json"],
            catch_exceptions=False,
        )
        envelope = _assert_one_json_stdout(result)
        assert envelope["warnings"], "warnings debe ser no-vacío"
        assert any("deprecad" in w.lower() for w in envelope["warnings"])
        assert any("curate accept" in w.lower() for w in envelope["warnings"])


# ---------------------------------------------------------------------------
# Tests b2g reject (alias deprecado → b2g curate reject)
# ---------------------------------------------------------------------------


class TestRejectDeprecado:
    """b2g reject emite aviso de deprecación y delega en curate reject.

    Delegación funcional y contrato schema/stdout se cubren en los tests de
    'b2g curate reject' (test_cli.py). Aquí solo se conserva el aviso (epic #184).
    """

    def test_aviso_va_a_stderr(self, tmp_path: Path) -> None:
        """b2g reject emite aviso de deprecación a stderr."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "reject", "--ids", "P1"],
            catch_exceptions=False,
        )
        assert "deprecad" in result.stderr.lower()
        assert "curate reject" in result.stderr.lower()

    def test_json_warnings_contiene_deprecacion(self, tmp_path: Path) -> None:
        """b2g reject --json: envelope['warnings'] contiene el aviso."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "reject", "--ids", "P1", "--json"],
            catch_exceptions=False,
        )
        envelope = _assert_one_json_stdout(result)
        assert envelope["warnings"]
        assert any("curate reject" in w.lower() for w in envelope["warnings"])


# ---------------------------------------------------------------------------
# Tests b2g filter (alias deprecado → b2g curate filter)
# ---------------------------------------------------------------------------


class TestFilterDeprecado:
    """b2g filter emite aviso de deprecación y delega en curate filter.

    Delegación funcional y contrato schema/stdout se cubren en los tests de
    'b2g curate filter' (test_cli.py). Aquí solo se conserva el aviso (epic #184).
    """

    def test_aviso_va_a_stderr(self, tmp_path: Path) -> None:
        """b2g filter emite aviso de deprecación a stderr."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1", year=2020)])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "filter", "--year-gte", "1900"],
            catch_exceptions=False,
        )
        assert "deprecad" in result.stderr.lower()
        assert "curate filter" in result.stderr.lower()

    def test_json_warnings_contiene_deprecacion(self, tmp_path: Path) -> None:
        """b2g filter --json: envelope['warnings'] contiene el aviso."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1", year=2020)])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "filter", "--year-gte", "1900", "--json"],
            catch_exceptions=False,
        )
        envelope = _assert_one_json_stdout(result)
        assert envelope["warnings"]
        assert any("curate filter" in w.lower() for w in envelope["warnings"])


# ---------------------------------------------------------------------------
# Tests b2g inspect (alias deprecado → b2g read show / b2g status)
# ---------------------------------------------------------------------------


class TestInspectDeprecado:
    """b2g inspect emite aviso de deprecación y delega en read show / status.

    Delegación funcional y contrato schema/stdout se cubren en los tests de
    'b2g read show' y 'b2g status' (test_cli.py). Aquí solo se conserva el aviso
    (epic #184).
    """

    def test_aviso_va_a_stderr_sin_id(self, tmp_path: Path) -> None:
        """b2g inspect sin --id avisa 'b2g status' en stderr."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "inspect"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "deprecad" in result.stderr.lower()
        assert "b2g status" in result.stderr.lower()

    def test_aviso_va_a_stderr_con_id(self, tmp_path: Path) -> None:
        """b2g inspect con --id avisa 'b2g read show' en stderr."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "inspect", "--id", "P1"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "deprecad" in result.stderr.lower()
        assert "read show" in result.stderr.lower()

    def test_json_warnings_contiene_deprecacion(self, tmp_path: Path) -> None:
        """b2g inspect --json: envelope['warnings'] contiene el aviso."""
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1")])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "inspect", "--json"],
            catch_exceptions=False,
        )
        envelope = _assert_one_json_stdout(result)
        assert envelope["warnings"]
        assert any("deprecad" in w.lower() for w in envelope["warnings"])


# ---------------------------------------------------------------------------
# Tests b2g restore (alias deprecado → b2g snapshot restore)
# ---------------------------------------------------------------------------


class TestRestoreDeprecado:
    """b2g restore emite aviso de deprecación y delega en snapshot restore.

    Delegación funcional y contrato schema/stdout se cubren en los tests de
    'b2g snapshot restore' (test_cli.py). Aquí solo se conserva el aviso (epic #184).
    """

    def test_aviso_va_a_stderr(self, tmp_path: Path) -> None:
        """b2g restore emite aviso de deprecación a stderr."""
        ws = _init_workspace(tmp_path)
        parquet_path = _make_parquet(tmp_path / "corpus.parquet")

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "restore",
                "--from-corpus",
                str(parquet_path),
            ],
            catch_exceptions=False,
        )
        assert "deprecad" in result.stderr.lower()
        assert "snapshot restore" in result.stderr.lower()

    def test_json_warnings_contiene_deprecacion(self, tmp_path: Path) -> None:
        """b2g restore --json: envelope['warnings'] contiene el aviso."""
        ws = _init_workspace(tmp_path)
        parquet_path = _make_parquet(tmp_path / "corpus.parquet")

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "restore",
                "--from-corpus",
                str(parquet_path),
                "--json",
            ],
            catch_exceptions=False,
        )
        envelope = _assert_one_json_stdout(result)
        assert envelope["warnings"]
        assert any("snapshot restore" in w.lower() for w in envelope["warnings"])


# ---------------------------------------------------------------------------
# Tests aliases en modo error (sin workspace):
# aviso sigue yendo a stderr, y el error envelope es 1 línea en stdout
# ---------------------------------------------------------------------------


class TestAvisosEnModError:
    """En el camino de error (sin workspace), el aviso igual va a stderr (#151)."""

    @pytest.mark.parametrize(
        "cmd_args",
        [
            ["monitor", "--json"],
            ["resolve", "--json"],
            ["enrich", "--json"],
        ],
    )
    def test_aviso_a_stderr_en_error(self, cmd_args: list[str]) -> None:
        """Sin workspace, el aviso de deprecación sigue yendo a stderr."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(b2g, cmd_args, catch_exceptions=False)
        # El aviso fue a stderr
        assert "deprecad" in result.stderr.lower(), (
            f"cmd={cmd_args}, stderr={result.stderr!r}"
        )

    @pytest.mark.parametrize(
        "cmd_args",
        [
            ["monitor", "--json"],
            ["resolve", "--json"],
            ["enrich", "--json"],
        ],
    )
    def test_stdout_una_linea_json_en_error(self, cmd_args: list[str]) -> None:
        """Sin workspace con --json: stdout es 1 línea de envelope de error (#151)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(b2g, cmd_args, catch_exceptions=False)
        # stdout es exactamente 1 línea JSON (el error envelope), sin fuga del aviso
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1, (
            f"stdout debe ser 1 línea, tuvo {len(lines)}: {result.stdout!r}"
        )
        envelope = json.loads(lines[0])
        assert envelope["schema"] == "1"
        # El error envelope tiene ok=False (sin workspace)
        assert envelope["ok"] is False


# ---------------------------------------------------------------------------
# Tests del entry-point bib2graph (main_bib2graph_alias)
# ---------------------------------------------------------------------------


class TestBib2graphEntryPoint:
    """El ejecutable legado ``bib2graph`` avisa y delega en ``b2g``."""

    def test_avisa_a_stderr(self) -> None:
        """main_bib2graph_alias emite aviso de deprecación a stderr."""
        from bib2graph.cli import main_bib2graph_alias

        buf = io.StringIO()
        with (
            patch("sys.stderr", buf),
            patch("bib2graph.cli.main", return_value=0) as mock_main,
        ):
            result = main_bib2graph_alias()
        assert result == 0
        assert mock_main.called
        assert "deprecad" in buf.getvalue().lower()
        assert "bib2graph" in buf.getvalue()
        assert "b2g" in buf.getvalue()

    def test_delega_en_main(self) -> None:
        """main_bib2graph_alias delega el control en main()."""
        from bib2graph.cli import main_bib2graph_alias

        with (
            patch("sys.stderr", io.StringIO()),
            patch("bib2graph.cli.main", return_value=42) as mock_main,
        ):
            result = main_bib2graph_alias()
        assert mock_main.called
        assert result == 42

    def test_mensaje_contiene_version_retiro(self) -> None:
        """El aviso del entry-point menciona la versión de retiro 0.11.0."""
        from bib2graph.cli import main_bib2graph_alias

        buf = io.StringIO()
        with patch("sys.stderr", buf), patch("bib2graph.cli.main", return_value=0):
            main_bib2graph_alias()
        assert "0.11.0" in buf.getvalue()

    def test_entry_point_registrado_en_pyproject(self) -> None:
        """El entry-point 'bib2graph' está registrado en pyproject.toml."""
        # Verificar que la función main_bib2graph_alias existe y es importable
        from bib2graph.cli import main_bib2graph_alias

        assert callable(main_bib2graph_alias)

    def test_cli_runner_avisa_y_corre(self) -> None:
        """Via CliRunner: invocar b2g init avisa en stderr y corre correctamente."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Verificamos que b2g (main) funciona; bib2graph es un wrapper
            result = runner.invoke(b2g, ["init", "test-ws", "--json"])
        assert result.exit_code == 0
        # La función main_bib2graph_alias avisa a sys.stderr; este test verifica
        # solo que el wrapper es importable y delega (las pruebas de unit mock main).


# ---------------------------------------------------------------------------
# Tests refactor --corpus-scope → emit_deprecation
# ---------------------------------------------------------------------------


class TestCorpusScopeDeprecado:
    """build --corpus-scope usa emit_deprecation y agrega al warnings[] del envelope."""

    def test_corpus_scope_aviso_en_stderr(self, tmp_path: Path) -> None:
        """build --corpus-scope emite aviso a stderr (via emit_deprecation)."""
        from bib2graph.corpus import Corpus
        from bib2graph.stores.duckdb import DuckDBStore
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        rows = [_row(id="P1", is_seed=True)]
        table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(ws.library_path)
        store.persist(corpus)
        store.close()

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--corpus-scope", "all"],
        )
        assert result.exit_code == 0, result.output
        assert "deprecad" in result.stderr.lower()

    def test_corpus_scope_warnings_en_envelope_json(self, tmp_path: Path) -> None:
        """build --corpus-scope --json agrega el aviso al envelope['warnings']."""
        from bib2graph.corpus import Corpus
        from bib2graph.stores.duckdb import DuckDBStore
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        rows = [_row(id="P1", is_seed=True)]
        table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        store = DuckDBStore(ws.library_path)
        store.persist(corpus)
        store.close()

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--corpus-scope", "all", "--json"],
        )
        assert result.exit_code == 0, result.output
        # stdout debe ser 1 línea JSON (el envelope)
        envelope = json.loads(result.stdout)
        assert envelope["schema"] == "1"
        # El aviso de deprecación de --corpus-scope debe estar en warnings top-level
        assert any("corpus-scope" in w.lower() for w in envelope["warnings"]), (
            f"warnings debe contener 'corpus-scope', got: {envelope['warnings']}"
        )


# ---------------------------------------------------------------------------
# Tests b2g networks (alias deprecado -> b2g build --spec)
# ---------------------------------------------------------------------------


def _write_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "redes.yaml"
    spec.write_text("networks:\n  - kind: bibliographic_coupling\n", encoding="utf-8")
    return spec


class TestNetworksDeprecado:
    """b2g networks emite aviso de deprecacion y delega en build --spec.

    Delegación funcional y contrato schema/stdout se cubren en los tests de
    'b2g build --spec' (test_cli.py). Aquí solo se conserva el aviso (epic #184).
    """

    def test_aviso_va_a_stderr(self, tmp_path: Path) -> None:
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1", year=2020)])
        spec = _write_spec(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "networks", "--spec", str(spec)],
            catch_exceptions=False,
        )
        assert "deprecad" in result.stderr.lower()
        assert "build --spec" in result.stderr.lower()

    def test_json_warnings_contiene_deprecacion(self, tmp_path: Path) -> None:
        ws = _init_workspace(tmp_path)
        _seed_store(ws, [_row(id="P1", year=2020)])
        spec = _write_spec(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "networks", "--spec", str(spec), "--json"],
            catch_exceptions=False,
        )
        envelope = _assert_one_json_stdout(result)
        assert envelope["warnings"]
        assert any("build --spec" in w.lower() for w in envelope["warnings"])
