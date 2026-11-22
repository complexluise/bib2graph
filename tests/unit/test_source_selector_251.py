"""Tests del Corte 1 (#251) del ADR 0053: selector ``--source`` + wiring.

Cubre D1: ``Provider``/``workspace.json.source``, registro de capacidades,
``resolve_provider``, ``seed``/``chain``/``build`` sobre S2 (MockTransport, sin
red), capacidad faltante antes de la red, ``Forager`` sin import de OpenAlex y
el guard transitorio R1 (mezcla de proveedores).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest
from click.testing import CliRunner

from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.cli import b2g
from bib2graph.cli._errors import DataError, DependencyError
from bib2graph.constants import Col, CurationStatus, Provider
from bib2graph.corpus import Corpus, _rows_with_ids
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent
from bib2graph.sources.registry import PROVIDERS, Capability, has, require
from bib2graph.sources.semanticscholar import _paper_to_row
from bib2graph.workspace import Workspace, WorkspaceManifestError

# Fixtures S2

S2_SEED: dict[str, Any] = {
    "paperId": "s2seedaaa111",
    "title": "Seed paper S2",
    "year": 2019,
    "abstract": "abs",
    "externalIds": {"DOI": "10.1000/seed1"},
    "authors": [{"authorId": "1", "name": "Ana Autora"}],
    "fieldsOfStudy": ["Economics"],
    "referenceCount": 0,
    "citationCount": 1,
}

S2_CITER: dict[str, Any] = {
    "paperId": "s2citerbbb222",
    "title": "Citing paper with real metadata",
    "year": 2022,
    "abstract": "citer abs",
    "externalIds": {"DOI": "10.1000/citer1"},
    "authors": [{"authorId": "2", "name": "Beto Citante"}],
    "fieldsOfStudy": ["Economics"],
    "references": [
        {"paperId": "s2seedaaa111", "externalIds": {"DOI": "10.1000/seed1"}}
    ],
}


def _s2_transport() -> httpx.MockTransport:
    """Mock S2: /paper/search devuelve S2_SEED; /citations devuelve S2_CITER."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/paper/search"):
            body = {"total": 1, "offset": 0, "data": [S2_SEED]}
            if request.url.params.get("offset", "0") != "0":
                body = {"total": 1, "offset": 1, "data": []}
            return httpx.Response(200, json=body)
        if path.endswith("/citations"):
            if request.url.params.get("offset", "0") != "0":
                return httpx.Response(200, json={"offset": 1, "data": []})
            return httpx.Response(
                200,
                json={"offset": 0, "next": None, "data": [{"citingPaper": S2_CITER}]},
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


class _ExplodingTransport(httpx.BaseTransport):
    """Transport que falla si se lo llama: prueba "falla antes de la red"."""

    def __init__(self) -> None:
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        raise AssertionError("se tocó la red")


def _openalex_row(id_: str = "P1") -> dict[str, Any]:
    row: dict[str, Any] = {name: None for name in CORPUS_SCHEMA.names}
    row.update(
        {
            "id": id_,
            "title": "OA paper",
            "year": 2020,
            "is_seed": True,
            "curation_status": "candidate",
            "cited_by_id": [],
        }
    )
    return row


def _persist_rows(store_path: Path, rows: list[dict[str, Any]]) -> None:
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    store = DuckDBStore(store_path)
    store.persist(Corpus.from_arrow(table))
    store.close()


def _corpus_hash(store_path: Path) -> str:
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    try:
        return compute_corpus_hash(store.load().to_arrow())
    finally:
        store.close()


def _load_rows(store_path: Path) -> list[dict[str, Any]]:
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    try:
        return store.load().to_arrow().to_pylist()
    finally:
        store.close()


# D1.1 / D1.2: workspace.json.source, Workspace.provider, resolve_provider


class TestWorkspaceSource:
    def test_workspace_sin_source_es_openalex(self, tmp_path: Path) -> None:
        """JSON legacy sin 'source' -> provider openalex, origin 'default'."""
        from bib2graph.cli._options import resolve_provider

        ws_dir = tmp_path / "legacy"
        Workspace.init(ws_dir, "legacy")
        manifest_path = ws_dir / "workspace.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        del raw["source"]
        manifest_path.write_text(json.dumps(raw), encoding="utf-8")

        ws = Workspace.open(ws_dir)

        assert ws.provider == Provider.OPENALEX
        assert resolve_provider(None, ws) == (Provider.OPENALEX, "default")
        # No se reescribe el archivo (compat sin migración).
        assert "source" not in json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_init_source_s2_escribe_manifest(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "s2ws"
        result = CliRunner().invoke(
            b2g, ["init", str(ws_dir), "--source", "s2", "--json"]
        )
        assert result.exit_code == 0, result.output
        raw = json.loads((ws_dir / "workspace.json").read_text(encoding="utf-8"))
        assert raw["source"] == "s2"
        assert Workspace.open(ws_dir).provider == Provider.S2
        assert raw["schema_version"] == "1"  # campo aditivo: versión intacta

    def test_init_sin_source_escribe_openalex(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        raw = json.loads((ws.root / "workspace.json").read_text(encoding="utf-8"))
        assert raw["source"] == "openalex"

    def test_workspace_source_invalido_error_accionable(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "bad"
        Workspace.init(ws_dir, "bad")
        manifest_path = ws_dir / "workspace.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw["source"] = "scopus"
        manifest_path.write_text(json.dumps(raw), encoding="utf-8")

        with pytest.raises(WorkspaceManifestError) as exc_info:
            Workspace.open(ws_dir)
        msg = str(exc_info.value)
        assert "scopus" in msg
        assert "openalex" in msg and "s2" in msg

        # En el CLI es un error de uso accionable (no un traceback).
        result = CliRunner().invoke(b2g, ["--workspace", str(ws_dir), "status"])
        assert result.exit_code == 1

    def test_init_source_invalido_lo_rechaza_click(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            b2g, ["init", str(tmp_path / "x"), "--source", "doaj"]
        )
        assert result.exit_code != 0  # doaj entra con #252

    def test_resolve_provider_precedencia(self, tmp_path: Path) -> None:
        """flag > workspace > default."""
        from bib2graph.cli._options import resolve_provider

        ws_s2 = Workspace.init(tmp_path / "a", "a", source=Provider.S2)
        ws_default = Workspace.init(tmp_path / "b", "b")
        raw_path = ws_default.root / "workspace.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        del raw["source"]
        raw_path.write_text(json.dumps(raw), encoding="utf-8")
        ws_default = Workspace.open(ws_default.root)

        assert resolve_provider("openalex", ws_s2) == (Provider.OPENALEX, "flag")
        assert resolve_provider(None, ws_s2) == (Provider.S2, "workspace")
        assert resolve_provider("s2", ws_default) == (Provider.S2, "flag")
        assert resolve_provider(None, ws_default) == (Provider.OPENALEX, "default")


# D1.4: registro de capacidades


class TestRegistry:
    def test_capacidades_declaradas(self) -> None:
        assert PROVIDERS[Provider.OPENALEX].capabilities == frozenset(Capability)
        assert PROVIDERS[Provider.S2].capabilities == frozenset(
            {
                Capability.SEED,
                Capability.BACKWARD,
                Capability.FORWARD,
                Capability.ENRICH_CITED_BY,
            }
        )

    def test_require_nombra_proveedor_y_capacidad(self) -> None:
        with pytest.raises(DependencyError) as exc_info:
            require(Provider.S2, Capability.SEED_FILTERS)
        assert exc_info.value.exit_code == 3
        assert "s2" in exc_info.value.message
        assert "seed_filters" in exc_info.value.message
        assert has(Provider.OPENALEX, Capability.RESOLVE_DOI)

    def test_make_source_instancia_la_clase_del_proveedor(self) -> None:
        from bib2graph.sources.openalex import OpenAlexSource
        from bib2graph.sources.registry import make_source
        from bib2graph.sources.semanticscholar import SemanticScholarSource

        assert isinstance(make_source(Provider.OPENALEX), OpenAlexSource)
        assert isinstance(make_source(Provider.S2), SemanticScholarSource)


# D1.5: Forager desacoplado de OpenAlex


def test_forager_no_importa_openalex() -> None:
    import bib2graph.foraging.forager as forager_mod

    assert "_work_to_row" not in vars(forager_mod)


def test_sources_exponen_work_to_row() -> None:
    from bib2graph.sources.openalex import OpenAlexSource
    from bib2graph.sources.semanticscholar import SemanticScholarSource

    assert callable(OpenAlexSource.work_to_row)
    row = SemanticScholarSource().work_to_row(
        S2_CITER,
        equation_id=None,
        fetched_at="2026-01-01T00:00:00+00:00",
        is_seed=False,
        chaining_hop=1,
        source_tag="chaining:forward",
        source_kind="chaining_forward",
    )
    assert row[Col.TITLE] == "Citing paper with real metadata"
    event = ProvenanceEvent.parse_list(row[Col.PROVENANCE])[0]
    assert event.source == "chaining:forward"
    assert event.source_kind == "chaining_forward"
    assert event.equation_id is None


def test_paper_to_row_default_source_tag_es_s2() -> None:
    row = _paper_to_row(S2_SEED, equation_id="eq", fetched_at="t")
    assert ProvenanceEvent.parse_list(row[Col.PROVENANCE])[0].source == "s2"


# seed sobre S2


class TestSeedS2:
    def test_seed_source_s2_mock(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed
        from bib2graph.stores.duckdb import DuckDBStore

        store_path = tmp_path / "lib.duckdb"
        data = run_seed(
            store_path,
            "unequal exchange",
            provider=Provider.S2,
            transport=_s2_transport(),
        )
        assert data["papers_added"] == 1
        assert data["executed_query"] == "unequal exchange"

        rows = _load_rows(store_path)
        events = ProvenanceEvent.parse_list(rows[0][Col.PROVENANCE])
        assert events[0].source == "s2"

        store = DuckDBStore(store_path)
        try:
            con = store.backend._con  # type: ignore[attr-defined]
            engines = con.execute("SELECT engine FROM equations").fetchall()
        finally:
            store.close()
        assert engines == [("s2",)]

    def test_capacidad_faltante_falla_antes_de_red(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed

        transport = _ExplodingTransport()
        store_path = tmp_path / "lib.duckdb"
        with pytest.raises(DependencyError) as exc_info:
            run_seed(
                store_path,
                "x",
                provider=Provider.S2,
                exclude=["y"],
                transport=transport,
            )
        assert exc_info.value.exit_code == 3
        assert transport.calls == 0
        assert not store_path.exists()  # ni siquiera se abrió el store

    @pytest.mark.parametrize(
        "flag", [["--exclude", "y"], ["--native"], ["--min-year", "2000"]]
    )
    def test_seed_s2_con_filtros_es_error(
        self, tmp_path: Path, flag: list[str]
    ) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        result = CliRunner().invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "seed",
                "--equation",
                "x",
                "--source",
                "s2",
                *flag,
                "--json",
            ],
        )
        assert result.exit_code == 3, result.output
        envelope = json.loads(result.stdout.strip().splitlines()[-1])
        assert envelope["ok"] is False
        assert "seed_filters" in envelope["error"]["message"]

    def test_from_bib_resolve_s2_es_error(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        bib = tmp_path / "a.bib"
        bib.write_text("@article{a, title={T}, year={2020}}", encoding="utf-8")
        result = CliRunner().invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "seed",
                "--from-bib",
                str(bib),
                "--resolve",
                "--source",
                "s2",
                "--json",
            ],
        )
        assert result.exit_code == 3, result.output
        assert "resolve_doi" in result.stdout

    def test_email_con_s2_no_se_ignora_en_silencio(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        result = CliRunner().invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "seed",
                "--equation",
                "x",
                "--source",
                "s2",
                "--email",
                "a@b.c",
                "--json",
            ],
        )
        assert result.exit_code == 1, result.output

    def test_preview_s2_query_nativa_sin_red(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        monkeypatch.chdir(tmp_path)  # sin workspace: preview es puro
        result = CliRunner().invoke(
            b2g,
            ["seed", "--equation", "a b", "--source", "s2", "--preview", "--json"],
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout.strip().splitlines()[-1])
        data = envelope["data"]
        assert data["preview"] is True
        assert data["executed_query"] == "a b"
        assert any("sin traducción" in w for w in data["translation_report"])
        assert data["provider"] == {"name": "s2", "origin": "flag"}

    def test_envelope_seed_trae_data_provider(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w", source=Provider.S2)
        bib = tmp_path / "a.bib"
        bib.write_text("@article{a, title={T}, year={2020}}", encoding="utf-8")
        result = CliRunner().invoke(
            b2g, ["--workspace", str(ws.root), "seed", "--from-bib", str(bib), "--json"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip().splitlines()[-1])["data"]
        assert data["provider"] == {"name": "s2", "origin": "workspace"}


# chain / build sobre S2


def _s2_corpus_rows(*, accepted: bool) -> list[dict[str, Any]]:
    row = _paper_to_row(
        S2_SEED, equation_id="eq", fetched_at="2026-01-01T00:00:00+00:00"
    )
    if accepted:
        row[Col.CURATION_STATUS] = CurationStatus.ACCEPTED
    return _rows_with_ids([row])


class TestChainBuildS2:
    def test_chain_forward_source_s2_usa_work_to_row(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _persist_rows(store_path, _s2_corpus_rows(accepted=False))

        data = run_chain(
            store_path,
            direction="both",
            provider=Provider.S2,
            transport=_s2_transport(),
        )

        assert data["candidates_found"] >= 1
        rows = {r[Col.SOURCE_ID]: r for r in _load_rows(store_path)}
        citer = rows["s2citerbbb222"]
        # Metadata real (no placeholder "[candidate:...]").
        assert citer[Col.TITLE] == "Citing paper with real metadata"
        assert citer[Col.YEAR] == 2022
        event = ProvenanceEvent.parse_list(citer[Col.PROVENANCE])[0]
        assert event.source_kind == "chaining_forward"
        # refs_doi no existe en S2: pasada omitida CON warning, no en silencio.
        assert any("refs_doi" in w for w in data["warnings"])

    def test_chain_budget_con_s2_no_se_ignora(self, tmp_path: Path) -> None:
        from bib2graph.cli._errors import UsageError
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        with pytest.raises(UsageError):
            run_chain(store_path, provider=Provider.S2, budget=5)

    def test_build_s2_cited_by_y_refs_doi_omitida_con_warning(
        self, tmp_path: Path
    ) -> None:
        from bib2graph.cli._enrich import enrich_corpus
        from bib2graph.cli.commands.build import run_build
        from bib2graph.sources.registry import make_source

        # (a) build: la pasada cited_by corre contra S2.
        store_path = tmp_path / "lib.duckdb"
        _persist_rows(store_path, _s2_corpus_rows(accepted=True))
        data = run_build(
            store_path,
            out_dir=tmp_path / "nets",
            provider=Provider.S2,
            transport=_s2_transport(),
        )
        assert data["enrichment"]["citing_new"] == 1
        assert data["enrichment"]["citing_targets"] == 1

        # (b) el helper compartido omite refs_doi con warning y corre cited_by.
        corpus = Corpus.from_arrow(
            pa.Table.from_pylist(_s2_corpus_rows(accepted=True), schema=CORPUS_SCHEMA)
        )
        warns: list[str] = []
        source = make_source(Provider.S2, transport=_s2_transport())
        _, metrics = enrich_corpus(
            corpus, source, pass_name="both", provider=Provider.S2, warnings=warns
        )
        assert len(warns) == 1 and "refs_doi" in warns[0]
        assert "citing_new" in metrics and "refs_resolved" not in metrics

    def test_enrich_corpus_openalex_default_sin_warnings(self) -> None:
        from bib2graph.cli._enrich import enrich_corpus
        from bib2graph.sources.registry import make_source

        corpus = Corpus.from_arrow(
            pa.Table.from_pylist([_openalex_row()], schema=CORPUS_SCHEMA)
        )
        warns: list[str] = []
        enrich_corpus(
            corpus,
            make_source(Provider.OPENALEX, transport=_ExplodingTransport()),
            pass_name="both",
            warnings=warns,
        )
        assert warns == []

    def test_build_envelope_trae_data_provider(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        result = CliRunner().invoke(
            b2g, ["--workspace", str(ws.root), "build", "--json"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip().splitlines()[-1])["data"]
        assert data["provider"] == {"name": "openalex", "origin": "workspace"}


# Guard transitorio R1


class TestGuardMezclaProveedores:
    def test_guard_mezcla_proveedores_pre_253(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed

        store_path = tmp_path / "lib.duckdb"
        _persist_rows(store_path, [_openalex_row("P1"), _openalex_row("P2")])
        before = _corpus_hash(store_path)
        transport = _ExplodingTransport()

        with pytest.raises(DataError) as exc_info:
            run_seed(
                store_path,
                "x",
                provider=Provider.S2,
                workspace_provider=Provider.OPENALEX,
                transport=transport,
            )

        assert exc_info.value.exit_code == 2
        assert "#253" in exc_info.value.message
        assert "init --source" in exc_info.value.message
        assert transport.calls == 0
        assert _corpus_hash(store_path) == before

    def test_guard_aplica_a_chain_y_build(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.build import run_build
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        _persist_rows(store_path, [_openalex_row()])
        before = _corpus_hash(store_path)
        with pytest.raises(DataError):
            run_chain(
                store_path, provider=Provider.S2, workspace_provider=Provider.OPENALEX
            )
        with pytest.raises(DataError):
            run_build(
                store_path, provider=Provider.S2, workspace_provider=Provider.OPENALEX
            )
        assert _corpus_hash(store_path) == before

    def test_guard_cli_exit_2(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")  # openalex
        _persist_rows(ws.library_path, [_openalex_row()])
        result = CliRunner().invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "seed",
                "--equation",
                "x",
                "--source",
                "s2",
                "--json",
            ],
        )
        assert result.exit_code == 2, result.output

    def test_guard_tambien_falla_con_corpus_vacio(self, tmp_path: Path) -> None:
        from bib2graph.cli.commands.seed import run_seed

        store_path = tmp_path / "lib.duckdb"
        transport = _ExplodingTransport()
        with pytest.raises(DataError) as exc_info:
            run_seed(
                store_path,
                "x",
                provider=Provider.S2,
                workspace_provider=Provider.OPENALEX,
                transport=transport,
            )
        assert exc_info.value.exit_code == 2
        assert transport.calls == 0
        assert not store_path.exists()  # sin escribir

    def test_secuencia_init_seed_s2_falla_en_el_seed(self, tmp_path: Path) -> None:
        """B1: init (openalex) -> seed --source s2 -> falla; no queda corpus s2."""
        ws_dir = tmp_path / "w"
        runner = CliRunner()
        assert runner.invoke(b2g, ["init", str(ws_dir), "--json"]).exit_code == 0

        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws_dir),
                "seed",
                "--equation",
                "x",
                "--source",
                "s2",
                "--json",
            ],
        )
        assert result.exit_code == 2, result.output
        assert _load_rows(ws_dir / "library.duckdb") == []

    @pytest.mark.parametrize("resolve", [False, True])
    def test_from_bib_source_distinto_es_exit_2(
        self, tmp_path: Path, resolve: bool
    ) -> None:
        ws = Workspace.init(tmp_path / "w", "w")  # openalex
        bib = tmp_path / "a.bib"
        bib.write_text("@article{a, title={T}, year={2020}}", encoding="utf-8")
        args = ["--workspace", str(ws.root), "seed", "--from-bib", str(bib)]
        if resolve:
            args.append("--resolve")
        # --resolve con s2 falla antes por capacidad (exit 3); sin --resolve, el
        # guard (exit 2).  Con --source igual al del workspace no cambia nada.
        result = CliRunner().invoke(b2g, [*args, "--source", "s2", "--json"])
        assert result.exit_code == (3 if resolve else 2), result.output
        assert _load_rows(ws.library_path) == []

    def test_source_igual_al_workspace_no_cambia_nada(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "w", "w")
        bib = tmp_path / "a.bib"
        bib.write_text("@article{a, title={T}, year={2020}}", encoding="utf-8")
        result = CliRunner().invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "seed",
                "--from-bib",
                str(bib),
                "--source",
                "openalex",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_chain_preview_valida_igual_que_modo_normal(self, tmp_path: Path) -> None:
        from bib2graph.cli._errors import UsageError
        from bib2graph.cli.commands.chain import run_chain

        store_path = tmp_path / "lib.duckdb"
        with pytest.raises(UsageError):
            run_chain(store_path, provider=Provider.S2, budget=5, preview=True)


def test_chain_since_con_s2_emite_warning_de_aproximacion(tmp_path: Path) -> None:
    from datetime import date

    from bib2graph.cli.commands.chain import run_chain
    from bib2graph.cli.commands.seed import run_seed

    store_path = tmp_path / "lib.duckdb"
    run_seed(store_path, "x", provider=Provider.S2, transport=_s2_transport())
    data = run_chain(
        store_path,
        direction="forward",
        since=date(2021, 6, 1),
        provider=Provider.S2,
        transport=_s2_transport(),
    )
    assert any("--since" in w and "año" in w for w in data["warnings"])


def test_chain_cli_warnings_un_solo_canal(tmp_path: Path) -> None:
    ws = Workspace.init(tmp_path / "w", "w")
    _persist_rows(ws.library_path, [_openalex_row()])
    result = CliRunner().invoke(
        b2g,
        ["--workspace", str(ws.root), "chain", "--preview", "--json"],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.stdout.strip().splitlines()[-1])
    assert "warnings" not in envelope["data"]


def test_chain_modo_humano_muestra_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Modo humano (sin --json/--preview): los warnings no se pierden en silencio."""
    import bib2graph.cli.commands.chain as chain_mod

    def _fake_run_chain(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "candidates_found": 0,
            "total_papers": 1,
            "ranking_preview": [],
            "warnings": ["Pasada de enriquecimiento 'refs_doi' omitida"],
        }

    monkeypatch.setattr(chain_mod, "run_chain", _fake_run_chain)
    ws = Workspace.init(tmp_path / "w", "w")
    result = CliRunner().invoke(b2g, ["--workspace", str(ws.root), "chain"])
    assert result.exit_code == 0, result.output
    assert "Aviso: Pasada de enriquecimiento 'refs_doi' omitida" in result.output
