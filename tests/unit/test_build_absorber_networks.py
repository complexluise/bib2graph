"""Tests TDD — ``b2g build`` absorbe capacidad de ``b2g networks`` (#159).

Cubre las decisiones y contratos del sub-issue #159 (ADR 0038):

1. [Retirado #207] La paridad ``build --spec`` ≡ ``networks --spec`` ya no
   aplica: el verbo suelto ``networks`` fue eliminado en 0.12.0.
2. **D1**: ``build --spec`` transiciona FSM a BUILT y sella ``.corpus_hash``.
3. **Scopes**: ``--scope all|accepted|seeds`` filtran el corpus y sellan el hash
   del corpus filtrado.
4. **Parámetro interno**: ``run_build(corpus_scope=...)`` sigue vivo (usado por
   ``--scope`` vía ``_map_scope``); el flag CLI deprecado ``--corpus-scope`` fue
   retirado en 0.12.0 (#207, ADR 0038 P1) sin alias — solo queda ``--scope``.
5. **min-weight**: aristas con peso < N se filtran; red vacía → warning específico.
6. **No-divergencia** (ADR 0037 §(e)): corpus sin ``keywords_id`` → ``build``
   exit 0, warning ``reason``/``fix_command`` coincide con ``predict_build_preview``.
7. **--json**: warning solo en envelope, stdout exactamente una línea JSON,
   ``data.empty_networks`` presente cuando aplica, ``schema="1"``.

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.constants import NetworkKind
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    is_seed: bool = True,
    curation_status: str = "candidate",
    references_id: list[str] | None = None,
    authors_id: list[str] | None = None,
    institutions_id: list[str] | None = None,
    keywords_id: list[str] | None = None,
    keywords_raw: list[str] | None = None,
    cited_by_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema canónico completo."""
    return {
        "id": id,
        "source_id": None,
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
        "authors_id": authors_id,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": institutions_id,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    """Construye un Corpus en memoria desde filas dict."""
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Persiste un conjunto de filas en un DuckDB temporal."""
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _rows_con_referencias() -> list[dict[str, Any]]:
    """3 papers con referencias compartidas → produce aristas de coupling."""
    return [
        _row(
            f"P{i}",
            references_id=[f"REF_{i}", "REF_SHARED"],
            authors_id=[f"AUTH_{i}", "AUTH_0"],
            keywords_id=[f"KW_{i}", "KW_SHARED"],
            institutions_id=[f"INST_{i}"],
        )
        for i in range(3)
    ]


def _write_spec(path: Path, kinds: list[str]) -> None:
    """Escribe un YAML de specs para los kinds dados."""
    lines = ["networks:"]
    for k in kinds:
        lines.append(f"  - kind: {k}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. [Retirado #207] La paridad build --spec ≡ networks --spec ya no aplica:
#    'b2g networks' fue eliminado en 0.12.0 (ADR 0038 P1); 'build --spec'
#    (D1, abajo) es la única implementación. Su cobertura de artefactos
#    (nodos/aristas por kind) vive en TestJsonOutput y en test_networkspec_yaml.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2. D1: build --spec transiciona FSM a BUILT y sella corpus_hash
# ---------------------------------------------------------------------------


class TestD1BuildSpecTransiciona:
    """D1 (ADR 0038): build --spec DEBE transicionar a BUILT y sellar hash."""

    def test_build_spec_transiciona_a_built(self, tmp_path: Path) -> None:
        """build --spec cambia el CycleState a BUILT."""
        from bib2graph.cli.commands.build import run_build
        from bib2graph.cycle import CycleState
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        spec_file = tmp_path / "redes.yaml"
        _write_spec(spec_file, ["bibliographic_coupling"])

        # Estado antes: None (store recién creado)
        store_before = DuckDBStore(store_path)
        state_before = store_before.backend.loop_state()
        store_before.close()
        assert state_before is None

        run_build(store_path, out_dir=tmp_path / "nets", spec_path=spec_file)

        # Estado después: BUILT
        store_after = DuckDBStore(store_path)
        state_after = store_after.backend.loop_state()
        store_after.close()
        assert state_after == CycleState.BUILT

    def test_build_spec_sella_corpus_hash(self, tmp_path: Path) -> None:
        """build --spec escribe .corpus_hash en el directorio de redes."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        spec_file = tmp_path / "redes.yaml"
        _write_spec(spec_file, ["bibliographic_coupling"])

        out_dir = tmp_path / "nets"
        data = run_build(store_path, out_dir=out_dir, spec_path=spec_file)

        hash_file = out_dir / ".corpus_hash"
        assert hash_file.exists(), ".corpus_hash no fue creado"
        assert hash_file.read_text(encoding="utf-8") == data["corpus_hash"]
        assert len(data["corpus_hash"]) > 0

    # [Retirado #207] test_networks_no_transiciona_fsm probaba que el verbo
    # suelto 'networks' (transversal, sin transición) contrastaba con D1;
    # 'networks' fue eliminado en 0.12.0 y build --spec es ahora la única
    # ruta — transiciona siempre, sin excepción a contrastar.


# ---------------------------------------------------------------------------
# 3. Scopes --scope all|accepted|seeds
# ---------------------------------------------------------------------------


class TestScopes:
    """Los 3 scopes filtran el corpus y sellan el hash del filtrado."""

    def _setup_corpus(self, store_path: Path) -> None:
        """P1=seed, P2=accepted no-seed, P3=candidate no-seed."""
        _seed_store(
            store_path,
            [
                _row(
                    "P1",
                    is_seed=True,
                    curation_status="candidate",
                    references_id=["R1", "R2"],
                    keywords_id=["k1", "k2"],
                ),
                _row(
                    "P2",
                    is_seed=False,
                    curation_status="accepted",
                    references_id=["R1", "R3"],
                    keywords_id=["k1", "k3"],
                ),
                _row(
                    "P3",
                    is_seed=False,
                    curation_status="candidate",
                    references_id=["R2", "R3"],
                    keywords_id=["k2", "k3"],
                ),
            ],
        )

    def test_scope_all_usa_corpus_completo(self, tmp_path: Path) -> None:
        """--scope all (default) construye sobre los 3 papers."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        self._setup_corpus(store_path)

        data = run_build(store_path, out_dir=tmp_path / "nets", corpus_scope="all")

        assert data["corpus_scope"] == "all"
        assert data["scope"] == "all"
        # Hay 3 papers con keywords_id → kw_cooccurrence debería tener nodos
        kw_net = next(
            (n for n in data["networks"] if n["kind"] == "keyword_cooccurrence"), None
        )
        assert kw_net is not None
        assert kw_net["nodes"] == 3, "scope=all debe incluir los 3 papers"

    def test_scope_accepted_filtra_seeds_y_aceptados(self, tmp_path: Path) -> None:
        """--scope accepted excluye candidatos no-seed (P3)."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        self._setup_corpus(store_path)

        data = run_build(store_path, out_dir=tmp_path / "nets", corpus_scope="accepted")

        assert data["corpus_scope"] == "accepted"
        # Keyword net: nodos son keywords (k1,k2,k3 únicos en P1+P2+P3).
        # Con scope=accepted solo P1(k1,k2) y P2(k1,k3) → se excluye P3(k2,k3).
        # La diferencia observable es en ARISTAS: P3 aporta la arista (k2,k3);
        # sin P3, quedan solo 2 aristas: (k1,k2) de P1 y (k1,k3) de P2.
        kw_net = next(
            (n for n in data["networks"] if n["kind"] == "keyword_cooccurrence"), None
        )
        assert kw_net is not None
        assert kw_net["edges"] == 2, (
            "scope=accepted excluye P3 (candidate): debe tener 2 aristas, no 3"
        )

    def test_scope_seeds_filtra_solo_semillas(self, tmp_path: Path) -> None:
        """--scope seeds deja solo P1 (is_seed=True)."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        self._setup_corpus(store_path)

        data = run_build(
            store_path, out_dir=tmp_path / "nets", corpus_scope="seeds_only"
        )

        assert data["corpus_scope"] == "seeds_only"
        # Keyword net: solo P1 → 2 nodos de keywords (k1, k2 en combinaciones)
        kw_net = next(
            (n for n in data["networks"] if n["kind"] == "keyword_cooccurrence"), None
        )
        assert kw_net is not None
        # P1 tiene kw_id=[k1, k2] → 2 nodos de keyword con 1 arista
        assert kw_net["nodes"] == 2

    def test_scope_sella_hash_del_corpus_filtrado(self, tmp_path: Path) -> None:
        """El .corpus_hash sellado es el hash del subset filtrado, no del completo."""
        from bib2graph.backends.memory import compute_corpus_hash
        from bib2graph.cli.commands.build import run_build
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        self._setup_corpus(store_path)

        out_dir = tmp_path / "nets"
        data = run_build(store_path, out_dir=out_dir, corpus_scope="accepted")

        # Calcular el hash esperado del subset accepted
        store = DuckDBStore(store_path)
        corpus_full = store.load()
        subset = corpus_full.scoped("accepted")
        store.close()

        expected_hash = compute_corpus_hash(subset.to_arrow())
        assert data["corpus_hash"] == expected_hash

        hash_file = out_dir / ".corpus_hash"
        assert hash_file.read_text(encoding="utf-8") == expected_hash

    def test_map_scope_seeds_a_seeds_only(self) -> None:
        """_map_scope mapea 'seeds' → 'seeds_only'; otros valores pasan sin cambio."""
        from bib2graph.cli.commands.build import _map_scope

        assert _map_scope("seeds") == "seeds_only"
        assert _map_scope("all") == "all"
        assert _map_scope("accepted") == "accepted"


# ---------------------------------------------------------------------------
# 4. run_build(corpus_scope=...) — parámetro interno (el flag CLI
#    '--corpus-scope' fue retirado en 0.12.0, #207, ADR 0038 P1; solo queda
#    '--scope'). El parámetro interno 'corpus_scope' de la función núcleo
#    sigue vivo (usado por '--scope' vía _map_scope) y se testea directo.
# ---------------------------------------------------------------------------


class TestScopeInternoSeedsOnly:
    """run_build(corpus_scope='seeds_only') filtra correctamente (vocab interno)."""

    def test_corpus_scope_seeds_only_funciona(self, tmp_path: Path) -> None:
        """run_build(corpus_scope='seeds_only') filtra a solo semillas."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        # 2 seeds + 1 non-seed
        _seed_store(
            store_path,
            [
                _row("S1", is_seed=True, keywords_id=["k1", "k2"]),
                _row("S2", is_seed=True, keywords_id=["k1", "k3"]),
                _row("C1", is_seed=False, keywords_id=["k2", "k4"]),
            ],
        )

        data = run_build(
            store_path, out_dir=tmp_path / "nets", corpus_scope="seeds_only"
        )

        assert data["corpus_scope"] == "seeds_only"
        kw_net = next(
            (n for n in data["networks"] if n["kind"] == "keyword_cooccurrence"), None
        )
        # Solo seeds (S1, S2) → keyword nodes de k1, k2, k3 (3 nodos, no k4)
        assert kw_net is not None
        assert kw_net["nodes"] <= 3, "Solo keywords de seeds deben aparecer"


# ---------------------------------------------------------------------------
# 5. --min-weight: filtrado de aristas + warning específico
# ---------------------------------------------------------------------------


class TestMinWeight:
    """--min-weight N filtra aristas; red vacía → warning específico de min_weight."""

    def test_min_weight_1_default_sin_filtro(self, tmp_path: Path) -> None:
        """min_weight=1 (default) no filtra nada."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        data_mw1 = run_build(store_path, out_dir=tmp_path / "nets1", min_weight=1)
        data_default = run_build(store_path, out_dir=tmp_path / "nets2")

        # Con min_weight=1 debe ser idéntico al default
        assert data_mw1["networks_built"] == data_default["networks_built"]

    def test_min_weight_alto_produce_redes_vacias(self, tmp_path: Path) -> None:
        """min_weight=999 filtra todas las aristas → redes vacías con warning."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        # Corpus con referencias compartidas (peso 1 por par)
        _seed_store(store_path, _rows_con_referencias())

        data = run_build(store_path, out_dir=tmp_path / "nets", min_weight=999)

        # Debe haber redes vacías
        assert any(
            en.get("reason") and "999" in str(en["reason"])
            for en in data["empty_networks"]
        ), (
            f"Esperaba warning de min_weight=999, empty_networks={data['empty_networks']}"
        )

    def test_min_weight_warning_reason_contiene_umbral(self, tmp_path: Path) -> None:
        """El reason del warning de min_weight menciona el umbral N."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        data = run_build(store_path, out_dir=tmp_path / "nets", min_weight=50)

        min_weight_warnings = [
            en for en in data["empty_networks"] if "50" in str(en.get("reason", ""))
        ]
        # Debe haber al menos 1 red vacía con el umbral mencionado
        assert len(min_weight_warnings) >= 1, (
            f"Esperaba warning de min_weight=50, "
            f"empty_networks={data['empty_networks']}"
        )

    def test_min_weight_quick_extiende_networkspec(self, tmp_path: Path) -> None:
        """Networks.quick con min_weight pasa el valor a NetworkSpec."""
        from bib2graph.networks.facade import Networks

        corpus = _make_corpus(*_rows_con_referencias())
        # min_weight=999 → todas las aristas filtradas
        artifacts_999 = Networks.quick(corpus, min_weight=999)
        # Verificar que el spec tiene min_weight=999
        for art in artifacts_999:
            assert art.spec.min_weight == 999

    def test_min_weight_fix_command_baja_umbral(self, tmp_path: Path) -> None:
        """El fix_command sugiere un umbral menor (min_weight - 1)."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        data = run_build(store_path, out_dir=tmp_path / "nets", min_weight=10)

        for en in data["empty_networks"]:
            if "10" in str(en.get("reason", "")):
                assert en["fix_command"] is not None
                assert "9" in str(en["fix_command"]), (
                    f"fix_command debe sugerir min-weight=9, got: {en['fix_command']}"
                )
                break


# ---------------------------------------------------------------------------
# 6. No-divergencia: build-time ≡ status-time (ADR 0037 §(e))
# ---------------------------------------------------------------------------


class TestNoDivergencia:
    """La razón/fix de redes vacías en build-time coincide con predict_build_preview.

    NOTA sobre alcance de la no-divergencia (opcional, ADR 0037 §(e)):
    La paridad build-vs-status es *por-corpus*. Cuando se usa ``--scope != all``,
    ``run_build`` computa ``predict_build_preview`` sobre el corpus YA FILTRADO.
    Esto es correcto: si status se llama sobre el corpus completo y build se llama
    sobre un subset (accepted/seeds), los conteos en los ``reason`` pueden diferir
    legítimamente. La invariante garantizada es que para el MISMO corpus, build y
    status reportan el mismo reason/fix_command — no que coincidan cross-scope.
    """

    def test_keyword_warning_coincide_con_preview(self, tmp_path: Path) -> None:
        """Corpus sin keywords_id → warning reason/fix_command == predict_build_preview."""
        from bib2graph.cli.commands.build import run_build
        from bib2graph.networks.facade import predict_build_preview
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        # BibTeX sin --resolve: keywords_raw poblado, keywords_id vacío
        rows = [
            _row(f"P{i}", keywords_raw=["ecology", "diversity"]) for i in range(1, 5)
        ]
        _seed_store(store_path, rows)

        data = run_build(store_path, out_dir=tmp_path / "nets")

        # Obtener preview (como lo haría status)
        store2 = DuckDBStore(store_path)
        corpus2 = store2.load()
        preview = predict_build_preview(corpus2)
        store2.close()

        kw_preview = next(
            e for e in preview if e["kind"] == str(NetworkKind.KEYWORD_COOCCURRENCE)
        )

        # Encontrar la entrada de empty_networks para keyword_cooccurrence
        kw_empty = next(
            (
                e
                for e in data["empty_networks"]
                if e["kind"] == str(NetworkKind.KEYWORD_COOCCURRENCE)
            ),
            None,
        )

        assert kw_empty is not None, (
            "keyword_cooccurrence debe estar en empty_networks "
            f"(corpus sin keywords_id); empty_networks={data['empty_networks']}"
        )
        assert kw_empty["reason"] == kw_preview["reason"], (
            f"build-time reason != status-time reason: "
            f"'{kw_empty['reason']}' != '{kw_preview['reason']}'"
        )
        assert kw_empty["fix_command"] == kw_preview["fix_command"], (
            f"build-time fix_command != status-time fix_command: "
            f"'{kw_empty['fix_command']}' != '{kw_preview['fix_command']}'"
        )

    def test_build_exit_0_con_redes_vacias(self, tmp_path: Path) -> None:
        """build con redes vacías termina con exit 0 (no error), warnings en data."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        # Sin ningún _id: todas las redes vacías
        rows = [_row(f"P{i}") for i in range(1, 4)]
        _seed_store(store_path, rows)

        # No debe lanzar excepción
        data = run_build(store_path, out_dir=tmp_path / "nets")

        # networks_built > 0 (quick sí construye redes, aunque vacías)
        assert data["networks_built"] >= 1
        # Pero hay empty_networks
        assert len(data["empty_networks"]) > 0


# ---------------------------------------------------------------------------
# 7. --json: stdout puro, envelope, data.empty_networks
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """--json: stdout una línea JSON, warnings en envelope, data.empty_networks."""

    # stdout de 1 línea JSON (camino de éxito) lo cubre
    # test_json_warnings_en_envelope_no_en_stdout (asserta len==1 + colocación de
    # warnings); el camino de error lo cubre el guard de test_cli_json_option
    # (build en _CMDS_NO_WORKSPACE). Epic #184, sub-tarea 2.

    def test_json_schema_1(self, tmp_path: Path) -> None:
        """--json: envelope tiene schema='1'."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_store(ws.library_path, _rows_con_referencias())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--json"],
        )

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert envelope["command"] == "build"

    def test_json_empty_networks_en_data(self, tmp_path: Path) -> None:
        """Cuando hay redes vacías, data.empty_networks está en el envelope JSON."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        # Sin _id: redes vacías
        rows = [_row(f"P{i}") for i in range(1, 4)]
        _seed_store(ws.library_path, rows)

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--json"],
        )

        assert result.exit_code == 0
        envelope = json.loads(result.output)

        # empty_networks debe estar en data
        assert "empty_networks" in envelope["data"], (
            "data.empty_networks debe estar presente cuando hay redes vacías"
        )
        assert len(envelope["data"]["empty_networks"]) > 0

        # Cada entrada de empty_networks tiene kind, reason, fix_command
        for en in envelope["data"]["empty_networks"]:
            assert "kind" in en
            assert "reason" in en
            assert "fix_command" in en

    def test_json_warnings_en_envelope_no_en_stdout(self, tmp_path: Path) -> None:
        """Warnings van solo en envelope.warnings, NUNCA como línea extra en stdout."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        rows = [_row(f"P{i}") for i in range(1, 4)]
        _seed_store(ws.library_path, rows)

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--json"],
        )

        assert result.exit_code == 0

        # stdout puro (result.stdout) debe ser 1 línea JSON.
        # Warnings van en envelope.warnings (no prints sueltos a stdout en JSON mode).
        stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert len(stdout_lines) == 1

        envelope = json.loads(stdout_lines[0])
        # Los warnings están en el envelope, no sueltos en stdout
        assert isinstance(envelope.get("warnings"), list)

    def test_json_data_tiene_scope_y_corpus_scope(self, tmp_path: Path) -> None:
        """data incluye 'scope' (nuevo) y 'corpus_scope' (backward compat)."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_store(ws.library_path, _rows_con_referencias())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--json"],
        )

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert "scope" in envelope["data"], "data debe tener clave 'scope'"
        assert "corpus_scope" in envelope["data"], (
            "data debe tener clave 'corpus_scope' (compat)"
        )

    def test_build_spec_json_envelope_correcto(self, tmp_path: Path) -> None:
        """build --spec --json emite envelope con schema='1' y claves de build."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_store(ws.library_path, _rows_con_referencias())

        spec_file = tmp_path / "redes.yaml"
        _write_spec(spec_file, ["bibliographic_coupling"])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws_dir),
                "build",
                "--spec",
                str(spec_file),
                "--json",
            ],
        )

        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)

        assert envelope["schema"] == "1"
        assert envelope["ok"] is True
        assert envelope["command"] == "build"
        assert envelope["exit_code"] == 0
        assert "networks_built" in envelope["data"]
        assert "corpus_hash" in envelope["data"]
        assert envelope["data"]["networks_built"] == 1

    def test_scope_seeds_cli_json(self, tmp_path: Path) -> None:
        """--scope seeds via CLI en modo --json produce scope correcto en data."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        rows = [
            _row("S1", is_seed=True, keywords_id=["k1", "k2"]),
            _row("C1", is_seed=False, keywords_id=["k3", "k4"]),
        ]
        _seed_store(ws.library_path, rows)

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--scope", "seeds", "--json"],
        )

        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        # corpus_scope = vocab interno (backward compat)
        assert envelope["data"]["corpus_scope"] == "seeds_only"
        # scope = token CLI tal como lo tipió el usuario (FIX 2 — gancho #160)
        assert envelope["data"]["scope"] == "seeds"


# ---------------------------------------------------------------------------
# 8. FIX 1: --min-weight + --spec footgun; FIX 2: data["scope"] = token CLI
# ---------------------------------------------------------------------------


class TestFix1MinWeightSpec:
    """FIX 1: --min-weight se ignora silenciosamente en modo --spec → avisar + diagnosticar bien."""

    def test_spec_mas_min_weight_avisa_a_stderr(self, tmp_path: Path) -> None:
        """--spec + --min-weight N>1 emite aviso a stderr; stdout sigue siendo JSON puro."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_store(ws.library_path, _rows_con_referencias())

        spec_file = tmp_path / "redes.yaml"
        _write_spec(spec_file, ["bibliographic_coupling"])

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws_dir),
                "build",
                "--spec",
                str(spec_file),
                "--min-weight",
                "5",
                "--json",
            ],
        )

        assert result.exit_code == 0, f"Error: {result.output}"

        # stderr debe contener el aviso de que --min-weight se ignora con --spec
        assert "ignora" in result.stderr.lower(), (
            f"Esperaba aviso 'ignora' en stderr; stderr={result.stderr!r}"
        )
        assert "spec" in result.stderr.lower()

        # stdout debe ser exactamente 1 línea JSON válida (sin contaminar)
        stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert len(stdout_lines) == 1, (
            f"stdout debe ser 1 línea JSON, tiene {len(stdout_lines)}: {result.stdout!r}"
        )
        json.loads(stdout_lines[0])

    def test_spec_red_vacia_por_min_weight_del_yaml_reason_honesto(
        self, tmp_path: Path
    ) -> None:
        """Red vacía en modo spec por min_weight del YAML → reason del spec, no del CLI.

        El reason debe mencionar el min_weight del propio spec, NO sugerir
        `--min-weight` de la CLI (que en modo spec no hace nada).
        """
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        # Corpus con referencias compartidas → preview dice "no vacía"
        _seed_store(store_path, _rows_con_referencias())

        # Spec con min_weight muy alto para forzar red vacía
        spec_lines = [
            "networks:",
            "  - kind: bibliographic_coupling",
            "    min_weight: 999",
        ]
        spec_file = tmp_path / "alto_umbral.yaml"
        spec_file.write_text("\n".join(spec_lines) + "\n", encoding="utf-8")

        data = run_build(store_path, out_dir=tmp_path / "nets", spec_path=spec_file)

        bc_empty = next(
            (
                en
                for en in data["empty_networks"]
                if en["kind"] == str(NetworkKind.BIBLIOGRAPHIC_COUPLING)
            ),
            None,
        )

        assert bc_empty is not None, (
            f"bibliographic_coupling debe estar en empty_networks; "
            f"empty_networks={data['empty_networks']}"
        )

        # El reason debe mencionar el min_weight del spec (999), no el --min-weight CLI
        assert "999" in str(bc_empty["reason"]), (
            f"reason debe mencionar 999 (min_weight del spec); reason={bc_empty['reason']!r}"
        )
        assert "spec" in str(bc_empty["reason"]).lower(), (
            f"reason debe mencionar 'spec'; reason={bc_empty['reason']!r}"
        )

        # fix_command DEBE ser None: --min-weight de la CLI no aplica en modo spec
        assert bc_empty["fix_command"] is None, (
            f"fix_command debe ser None en modo spec (CLI --min-weight no aplica); "
            f"fix_command={bc_empty['fix_command']!r}"
        )

        # Verificación negativa: el reason NO debe sugerir `--min-weight` del CLI
        assert "--min-weight" not in str(bc_empty["reason"]), (
            f"reason no debe mencionar '--min-weight' del CLI en modo spec; "
            f"reason={bc_empty['reason']!r}"
        )

    def test_spec_red_vacia_fix_command_no_es_min_weight_cli(
        self, tmp_path: Path
    ) -> None:
        """En modo spec, el fix_command de una red vacía NUNCA es 'b2g build --min-weight N'."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        spec_lines = [
            "networks:",
            "  - kind: bibliographic_coupling",
            "    min_weight: 999",
        ]
        spec_file = tmp_path / "alto.yaml"
        spec_file.write_text("\n".join(spec_lines) + "\n", encoding="utf-8")

        # Incluso si el usuario pasó --min-weight (ignorado en spec mode),
        # el fix_command no debe sugerir bajarlo
        data = run_build(
            store_path,
            out_dir=tmp_path / "nets",
            spec_path=spec_file,
            min_weight=5,  # ignorado en spec mode, pero presente en la firma
        )

        for en in data["empty_networks"]:
            fix = en.get("fix_command")
            if fix is not None:
                assert "b2g build --min-weight" not in str(fix), (
                    f"fix_command en modo spec no debe sugerir --min-weight CLI: {fix!r}"
                )


class TestFix2ScopeCliToken:
    """FIX 2: data['scope'] expone el token CLI, no el vocab interno."""

    def test_scope_seeds_cli_token_en_data(self, tmp_path: Path) -> None:
        """--scope seeds → data['scope']='seeds' (token CLI), corpus_scope='seeds_only' (interno)."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_store(
            ws.library_path,
            [
                _row("S1", is_seed=True, references_id=["R1", "R2"]),
                _row("C1", is_seed=False, references_id=["R1", "R3"]),
            ],
        )

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--scope", "seeds", "--json"],
        )

        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.stdout)

        # scope = token CLI
        assert envelope["data"]["scope"] == "seeds", (
            f"data['scope'] debe ser 'seeds' (token CLI), no 'seeds_only'; "
            f"got {envelope['data']['scope']!r}"
        )
        # corpus_scope = vocab interno (backward compat)
        assert envelope["data"]["corpus_scope"] == "seeds_only"

    def test_scope_accepted_cli_token_en_data(self, tmp_path: Path) -> None:
        """--scope accepted → data['scope']='accepted' (idéntico en ambos vocabs)."""
        from click.testing import CliRunner

        from bib2graph.cli import b2g
        from bib2graph.workspace import Workspace

        ws_dir = tmp_path / "ws"
        ws = Workspace.init(ws_dir, "test")
        _seed_store(ws.library_path, _rows_con_referencias())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws_dir), "build", "--scope", "accepted", "--json"],
        )

        assert result.exit_code == 0
        envelope = json.loads(result.stdout)
        assert envelope["data"]["scope"] == "accepted"
        assert envelope["data"]["corpus_scope"] == "accepted"

    def test_scope_directo_run_build_sin_cli_token_backward_compat(
        self, tmp_path: Path
    ) -> None:
        """run_build() directamente sin scope_cli_token → data['scope'] = corpus_scope (compat)."""
        from bib2graph.cli.commands.build import run_build

        store_path = tmp_path / "lib.duckdb"
        _seed_store(store_path, _rows_con_referencias())

        # Llamada directa sin scope_cli_token (tests pre-0.10.0)
        data = run_build(
            store_path, out_dir=tmp_path / "nets", corpus_scope="seeds_only"
        )

        # Backward compat: sin token CLI, scope == corpus_scope
        assert data["corpus_scope"] == "seeds_only"
        assert data["scope"] == "seeds_only"

    # [Retirado #207] test_scope_alias_deprecado_preserva_vocab_interno testeaba
    # el flag CLI '--corpus-scope' (deprecado desde 0037/0038); fue retirado en
    # 0.12.0 sin alias. El caso "sin token CLI" queda cubierto arriba.
