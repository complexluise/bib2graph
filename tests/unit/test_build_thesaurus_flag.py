"""Tests para el flag build --thesaurus (#164).

El verbo `b2g thesaurus` fue retirado. La capacidad se movio al flag
`b2g build --thesaurus <archivo>` (ADR 0038).

Secciones:
1. build --thesaurus aplica consolidacion de keywords_id (unitario).
2. Sin --thesaurus el build funciona igual que antes.
3. El verbo b2g thesaurus ya no existe en el CLI.
4. El envelope JSON contiene stats del thesaurus cuando se pasa --thesaurus.
5. Thesaurus inexistente emite DataError.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers locales (mismo contrato que test_ingest._make_corpus_row / _make_parquet)
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Test",
    keywords_raw: list[str] | None = None,
    keywords_id: list[str] | None = None,
    year: int = 2020,
) -> dict[str, Any]:
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _write_parquet(tmp_path: pathlib.Path, rows: list[dict[str, Any]]) -> pathlib.Path:
    import pyarrow.parquet as pq

    p = tmp_path / "corpus.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA), str(p))
    return p


def _make_minimal_thesaurus(canonical: str, aliases: list[str]) -> dict[str, Any]:
    return {"concepts": {canonical: {"aliases_en": aliases}}}


def _setup_store(tmp_path: pathlib.Path) -> pathlib.Path:
    """Crea un store con corpus basico (deep learning + machine learning)."""
    from bib2graph.cli.commands.restore import run_restore

    store_path = tmp_path / "lib.duckdb"
    rows = [
        _row(id="P1", title="Paper on deep learning", keywords_raw=["deep learning"]),
        _row(id="P2", title="Paper on ml", keywords_raw=["machine learning"]),
    ]
    run_restore(store_path, _write_parquet(tmp_path, rows))
    return store_path


# ---------------------------------------------------------------------------
# 1. build --thesaurus aplica consolidacion
# ---------------------------------------------------------------------------


def test_build_thesaurus_consolida_keywords_id(tmp_path: pathlib.Path) -> None:
    """build --thesaurus unifica aliases bajo el termino canonico en keywords_id."""
    from bib2graph.cli.commands.build import run_build
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    th = _make_minimal_thesaurus("ml", ["deep learning", "machine learning", "ml"])
    th_path = tmp_path / "th.json"
    th_path.write_text(json.dumps(th), encoding="utf-8")

    store_path = _setup_store(tmp_path)
    run_build(store_path, thesaurus_path=th_path)

    corpus = DuckDBStore(store_path).load()
    rows = corpus.to_arrow().to_pylist()
    all_kw_ids = [kw for row in rows for kw in (row.get(Col.KEYWORDS_ID) or [])]

    assert "ml" in all_kw_ids, (
        f"El canonical 'ml' debe estar en keywords_id. Got: {all_kw_ids}"
    )
    assert "deep learning" not in all_kw_ids, (
        "El alias 'deep learning' no debe estar en keywords_id (solo el canonical)."
    )
    assert "machine learning" not in all_kw_ids, (
        "El alias 'machine learning' no debe estar en keywords_id (solo el canonical)."
    )


def test_build_thesaurus_retorna_stats(tmp_path: pathlib.Path) -> None:
    """run_build con thesaurus_path retorna stats en data thesaurus."""
    from bib2graph.cli.commands.build import run_build

    th = _make_minimal_thesaurus("ml", ["deep learning", "machine learning"])
    th_path = tmp_path / "th.json"
    th_path.write_text(json.dumps(th), encoding="utf-8")

    store_path = _setup_store(tmp_path)
    data = run_build(store_path, thesaurus_path=th_path)

    th_stats = data.get("thesaurus")
    assert th_stats is not None, "run_build debe retornar stats en data['thesaurus']"
    assert "keywords_mapped" in th_stats
    assert "keywords_total" in th_stats
    assert "aliases_loaded" in th_stats
    assert "applied_at" in th_stats
    assert (
        th_stats["aliases_loaded"] == 3
    )  # 2 aliases + canonical self-map (ADR 0011 idempotence)


# ---------------------------------------------------------------------------
# 2. Sin --thesaurus el build funciona como antes
# ---------------------------------------------------------------------------


def test_build_sin_thesaurus_funciona_normal(tmp_path: pathlib.Path) -> None:
    """Sin --thesaurus, run_build no aplica thesaurus y retorna data thesaurus = None."""
    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.restore import run_restore

    store_path = tmp_path / "lib.duckdb"
    rows = [_row(id="P1", title="Paper A", keywords_raw=["ecology"])]
    run_restore(store_path, _write_parquet(tmp_path, rows))

    data = run_build(store_path)

    assert data.get("thesaurus") is None, (
        "Sin thesaurus_path, data['thesaurus'] debe ser None"
    )
    assert "networks_built" in data


# ---------------------------------------------------------------------------
# 3. El verbo b2g thesaurus ya no existe
# ---------------------------------------------------------------------------


def test_b2g_thesaurus_verb_no_existe() -> None:
    """El subcomando thesaurus fue eliminado del CLI (#164)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    runner = CliRunner()
    result = runner.invoke(b2g, ["thesaurus", "--from", "nada.json"])

    assert result.exit_code != 0, "El verbo 'thesaurus' no debe existir"
    output = result.output or ""
    assert "No such command" in output or "Error" in output


# ---------------------------------------------------------------------------
# 4. Envelope JSON con thesaurus stats
# ---------------------------------------------------------------------------


def test_build_thesaurus_json_envelope(tmp_path: pathlib.Path) -> None:
    """build --thesaurus --json produce envelope schema=1 con thesaurus stats."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test_th")
    rows = [_row(id="P1", title="Paper A", keywords_raw=["neural net"])]
    run_restore(ws.library_path, _write_parquet(tmp_path, rows))

    th = _make_minimal_thesaurus("ml", ["neural net", "deep learning"])
    th_path = tmp_path / "th.json"
    th_path.write_text(json.dumps(th), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "build",
            "--thesaurus",
            str(th_path),
            "--json",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"exit != 0: {result.output}"
    envelope = json.loads(result.output)
    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "build"
    data = envelope["data"]
    assert data.get("thesaurus") is not None
    assert "keywords_mapped" in data["thesaurus"]
    assert "aliases_loaded" in data["thesaurus"]


# ---------------------------------------------------------------------------
# 5. Thesaurus inexistente emite DataError
# ---------------------------------------------------------------------------


def test_build_thesaurus_inexistente_error(tmp_path: pathlib.Path) -> None:
    """build --thesaurus con ruta inexistente emite DataError (exit code 2)."""
    from click.testing import CliRunner

    from bib2graph.cli import b2g
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test_err")
    rows = [_row(id="P1", title="Paper A")]
    run_restore(ws.library_path, _write_parquet(tmp_path, rows))

    runner = CliRunner()
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_dir),
            "build",
            "--thesaurus",
            str(tmp_path / "no_existe.json"),
            "--json",
        ],
    )

    assert result.exit_code != 0, "Debe fallar con thesaurus inexistente"


@pytest.mark.unit
def test_build_thesaurus_json_malformado_dataerror(tmp_path: pathlib.Path) -> None:
    """build --thesaurus con JSON malformado (existente) -> DataError limpio (#164).

    Regresion: el curador edita el JSON a mano y lo rompe; debe dar un DataError
    accionable (exit 2), no un traceback no controlado.
    """
    import pytest as _pytest

    from bib2graph.cli._errors import DataError
    from bib2graph.cli.commands.build import run_build

    th_path = tmp_path / "th_malformado.json"
    th_path.write_text("{ esto no es json valido ", encoding="utf-8")

    store_path = _setup_store(tmp_path)
    with _pytest.raises(DataError):
        run_build(store_path, thesaurus_path=th_path)
