"""Tests TDD — ``b2g export --format arrow|bibtex`` (ADR 0050 D4, issue #293).

Cubre:
1. ``--format arrow``: escribe un Feather (Arrow IPC) que se relee con
   ``pyarrow.feather.read_table``; columnas del schema presentes; metadata
   de schema preservada cuando ``to_arrow()`` la trae (genérico — no asume
   ``equation_hash`` presente, eso es de la otra pieza del contrato).
2. ``--format bibtex``: el ``.bib`` parsea con ``bibtexparser``; citekeys =
   ``id`` interno; entry-type ``@article`` por default; entradas con
   metadata incompleta se emiten igual (no se filtran).
3. ``--scope``: aplicado en arrow/bibtex (distinto Nº de filas); ignorado
   (con warning) en graphml/csv.
4. Envelope ``--json`` consistente: ``{format, out_dir, files_written,
   workspace}``.

Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from click.testing import CliRunner

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos (mismo patrón que test_maturity.py)
# ---------------------------------------------------------------------------


def _row(
    id: str,
    *,
    title: str = "Paper",
    is_seed: bool = True,
    curation_status: str = "candidate",
    doi: str | None = None,
    year: int | None = 2020,
    source: str | None = None,
    authors_raw: list[str] | None = None,
    references_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema canónico completo."""
    return {
        "id": id,
        "source_id": None,
        "doi": doi,
        "title": title,
        "year": year,
        "abstract": None,
        "source": source,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": authors_raw,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": None,
    }


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en un DuckDB temporal."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _init_workspace(tmp_path: Path, name: str = "ws") -> Any:
    """Crea y devuelve un Workspace inicializado en tmp_path."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _mixed_rows() -> list[dict[str, Any]]:
    """3 papers: 2 semillas (1 aceptada, 1 candidata) + 1 no-semilla aceptado."""
    return [
        _row(
            "doi:p1",
            title="Seed accepted",
            is_seed=True,
            curation_status="accepted",
            doi="10.1/p1",
            year=2019,
            source="Journal A",
            authors_raw=["Smith, John"],
        ),
        _row(
            "doi:p2",
            title="Seed candidate",
            is_seed=True,
            curation_status="candidate",
        ),
        _row(
            "doi:p3",
            title="Chained accepted",
            is_seed=False,
            curation_status="accepted",
        ),
    ]


# ---------------------------------------------------------------------------
# 1. --format arrow
# ---------------------------------------------------------------------------


class TestExportFormatArrow:
    def test_arrow_escribe_feather_legible(self, tmp_path: Path) -> None:
        """--format arrow escribe un Feather releíble con las columnas del schema."""
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "arrow", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["ok"] is True
        data = envelope["data"]
        assert data["format"] == "arrow"

        files_written = data["files_written"]
        assert len(files_written) == 1
        arrow_path = Path(files_written[0])
        assert arrow_path.exists()
        assert arrow_path.suffix == ".arrow"

        import pyarrow.feather as feather

        reread = feather.read_table(str(arrow_path))
        assert set(reread.schema.names) == set(CORPUS_SCHEMA.names)
        assert reread.num_rows == 3

    def test_arrow_preserva_metadata_de_schema_si_presente(
        self, tmp_path: Path
    ) -> None:
        """Si to_arrow() trae metadata de schema, el Feather la preserva.

        Genérico: NO asume equation_hash presente (eso lo testea la pieza
        de #291/#292); solo verifica que CUALQUIER metadata puesta en el
        schema por to_arrow() sobrevive la serialización/deserialización.
        """
        from bib2graph.corpus import Corpus
        from bib2graph.exporters.arrow import ArrowExporter

        rows = _mixed_rows()
        table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
        corpus = Corpus.from_arrow(table)
        live_table = corpus.to_arrow()

        # Si la tabla que produce to_arrow() ya trae metadata, debe sobrevivir.
        # Si no trae ninguna (según el estado actual de to_arrow(), pieza en
        # paralelo), el test igual es válido: metadata None -> None.
        out_path = tmp_path / "corpus.arrow"
        ArrowExporter().export(live_table, out_path)

        import pyarrow.feather as feather

        reread = feather.read_table(str(out_path))
        assert reread.schema.metadata == live_table.schema.metadata

    def test_arrow_respeta_scope(self, tmp_path: Path) -> None:
        """--scope seeds exporta solo las 2 filas is_seed=True."""
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "export",
                "--format",
                "arrow",
                "--scope",
                "seeds",
                "--json",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        data = envelope["data"]
        assert data["rows_exported"] == 2

        import pyarrow.feather as feather

        arrow_path = Path(data["files_written"][0])
        reread = feather.read_table(str(arrow_path))
        assert reread.num_rows == 2

    def test_arrow_scope_accepted_distinto_de_seeds(self, tmp_path: Path) -> None:
        """--scope accepted (seeds + aceptados) difiere en Nº de filas de seeds."""
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())
        runner = CliRunner()

        result_accepted = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "export",
                "--format",
                "arrow",
                "--scope",
                "accepted",
                "--out-dir",
                str(ws.root / "exports_accepted"),
                "--json",
            ],
            catch_exceptions=False,
        )
        assert result_accepted.exit_code == 0
        data_accepted = json.loads(result_accepted.output)["data"]
        # accepted = is_seed OR curation_status==accepted: p1 (seed+accepted),
        # p2 (seed), p3 (accepted, no seed) => las 3 filas.
        assert data_accepted["rows_exported"] == 3

        result_all = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "export",
                "--format",
                "arrow",
                "--scope",
                "all",
                "--out-dir",
                str(ws.root / "exports_all"),
                "--json",
            ],
            catch_exceptions=False,
        )
        data_all = json.loads(result_all.output)["data"]
        assert data_all["rows_exported"] == 3

    def test_arrow_out_dir_default_es_exports_dir_del_workspace(
        self, tmp_path: Path
    ) -> None:
        """Sin --out-dir, corpus.arrow va a <workspace>/exports/."""
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "arrow", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)["data"]
        assert Path(data["out_dir"]) == ws.exports_dir
        assert (ws.exports_dir / "corpus.arrow").exists()


# ---------------------------------------------------------------------------
# 2. --format bibtex
# ---------------------------------------------------------------------------


class TestExportFormatBibtex:
    def test_bibtex_parsea_y_citekeys_son_ids_internos(self, tmp_path: Path) -> None:
        """El .bib generado parsea con bibtexparser; citekeys = id interno."""
        pytest.importorskip("bibtexparser")
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "bibtex", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        data = json.loads(result.output)["data"]
        assert data["format"] == "bibtex"
        bib_path = Path(data["files_written"][0])
        assert bib_path.exists()
        assert bib_path.suffix == ".bib"

        import bibtexparser

        parsed = bibtexparser.loads(bib_path.read_text(encoding="utf-8"))
        assert len(parsed.entries) == 3
        ids = {e["ID"] for e in parsed.entries}
        assert ids == {"doi:p1", "doi:p2", "doi:p3"}

    def test_bibtex_entry_type_article_por_default(self, tmp_path: Path) -> None:
        """Sin señal para inferir otro tipo, el ENTRYTYPE es 'article'."""
        pytest.importorskip("bibtexparser")
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "bibtex", "--json"],
            catch_exceptions=False,
        )
        data = json.loads(result.output)["data"]
        bib_path = Path(data["files_written"][0])

        import bibtexparser

        parsed = bibtexparser.loads(bib_path.read_text(encoding="utf-8"))
        for entry in parsed.entries:
            assert entry["ENTRYTYPE"] == "article"

    def test_bibtex_campos_minimos_presentes_para_fila_completa(
        self, tmp_path: Path
    ) -> None:
        """La fila con metadata completa trae title/author/year/doi/journal/url."""
        pytest.importorskip("bibtexparser")
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "bibtex", "--json"],
            catch_exceptions=False,
        )
        data = json.loads(result.output)["data"]
        bib_path = Path(data["files_written"][0])

        import bibtexparser

        parsed = bibtexparser.loads(bib_path.read_text(encoding="utf-8"))
        entry_p1 = next(e for e in parsed.entries if e["ID"] == "doi:p1")
        assert entry_p1["title"] == "Seed accepted"
        assert entry_p1["author"] == "Smith, John"
        assert entry_p1["year"] == "2019"
        assert entry_p1["doi"] == "10.1/p1"
        assert entry_p1["journal"] == "Journal A"
        assert "doi.org" in entry_p1["url"]

    def test_bibtex_entradas_incompletas_no_se_filtran(self, tmp_path: Path) -> None:
        """Entradas con metadata incompleta se emiten con los campos que haya."""
        pytest.importorskip("bibtexparser")
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "bibtex", "--json"],
            catch_exceptions=False,
        )
        data = json.loads(result.output)["data"]
        bib_path = Path(data["files_written"][0])

        import bibtexparser

        parsed = bibtexparser.loads(bib_path.read_text(encoding="utf-8"))
        # p2 no tiene doi/author/journal — debe seguir presente con lo que hay.
        entry_p2 = next(e for e in parsed.entries if e["ID"] == "doi:p2")
        assert entry_p2["title"] == "Seed candidate"
        assert "doi" not in entry_p2
        assert "author" not in entry_p2

    def test_bibtex_respeta_scope(self, tmp_path: Path) -> None:
        """--scope seeds exporta solo 2 entradas al .bib."""
        pytest.importorskip("bibtexparser")
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "export",
                "--format",
                "bibtex",
                "--scope",
                "seeds",
                "--json",
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)["data"]
        assert data["rows_exported"] == 2

        import bibtexparser

        bib_path = Path(data["files_written"][0])
        parsed = bibtexparser.loads(bib_path.read_text(encoding="utf-8"))
        assert len(parsed.entries) == 2


# ---------------------------------------------------------------------------
# 3. --scope ignorado (con warning) para graphml/csv
# ---------------------------------------------------------------------------


class TestScopeIgnoradoParaFormatosDeRed:
    def test_scope_con_graphml_emite_warning_y_no_falla(self, tmp_path: Path) -> None:
        """--scope con --format graphml no rompe; emite warning accionable."""
        from bib2graph.cli import b2g
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(
            ws.library_path,
            [
                _row("doi:p1", references_id=["R1", "R2"]),
                _row("doi:p2", references_id=["R1", "R3"]),
            ],
        )
        run_build(ws.library_path, out_dir=ws.networks_dir)

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            [
                "--workspace",
                str(ws.root),
                "export",
                "--format",
                "graphml",
                "--scope",
                "seeds",
                "--json",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Error: {result.output}"
        envelope = json.loads(result.output)
        assert envelope["ok"] is True
        warnings_list = envelope.get("warnings") or []
        assert any("--scope" in w and "graphml" in w for w in warnings_list)

    def test_sin_scope_no_hay_warning_para_graphml(self, tmp_path: Path) -> None:
        """Sin --scope explícito, no se emite el warning de scope-ignorado."""
        from bib2graph.cli import b2g
        from bib2graph.cli.commands.build import run_build

        ws = _init_workspace(tmp_path)
        _seed_store(
            ws.library_path,
            [
                _row("doi:p1", references_id=["R1", "R2"]),
                _row("doi:p2", references_id=["R1", "R3"]),
            ],
        )
        run_build(ws.library_path, out_dir=ws.networks_dir)

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "graphml", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        warnings_list = envelope.get("warnings") or []
        assert not any("--scope" in w for w in warnings_list)


# ---------------------------------------------------------------------------
# 4. Envelope --json consistente
# ---------------------------------------------------------------------------


class TestEnvelopeJson:
    def test_envelope_arrow_tiene_claves_esperadas(self, tmp_path: Path) -> None:
        """Envelope --json expone format/out_dir/files_written/workspace."""
        from bib2graph.cli import b2g

        ws = _init_workspace(tmp_path)
        _seed_store(ws.library_path, _mixed_rows())

        runner = CliRunner()
        result = runner.invoke(
            b2g,
            ["--workspace", str(ws.root), "export", "--format", "arrow", "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["schema"] == "1"
        data = envelope["data"]
        assert "format" in data
        assert "out_dir" in data
        assert "files_written" in data
        assert "workspace" in data
