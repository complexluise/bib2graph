"""Tests TDD para la resolución de identificadores en curate (#287 fricción #1).

`read show` acepta id interno, DOI o source_id, pero `curate accept/reject`
solo aceptaba el id interno — para un agente, dos identificadores visibles para
la misma entidad sin señal de cuál espera cada comando cuesta una llamada
perdida por ocurrencia. Estos tests fijan que `curate` acepta las tres formas
(prioridad id > doi > source_id, ADR 0036), y que el error lista los idents que
no resolvieron por ninguna vía.

Marcador: ``unit`` (DuckDB en tmp_path, sin red).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.service._identity import (
    resolve_ident_to_id,
    resolve_ident_to_row,
    resolve_idents,
)

pytestmark = pytest.mark.unit


def _row(
    *,
    id: str,
    doi: str | None = None,
    source_id: str | None = None,
    title: str = "Título de prueba",
    year: int = 2020,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
    return {
        "id": id,
        "source_id": source_id,
        "doi": doi,
        "title": title,
        "year": year,
        "abstract": None,
        "source": None,
        "language": "en",
        "publisher": None,
        "research_areas": None,
        "is_seed": False,
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


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


def _status_by_id(store_path: Path) -> dict[str, str]:
    from bib2graph.stores.duckdb import DuckDBStore

    store = DuckDBStore(store_path)
    corpus = store.load()
    by_id = {r["id"]: r["curation_status"] for r in corpus.to_arrow().to_pylist()}
    store.close()
    return by_id


# ---------------------------------------------------------------------------
# Resolver puro
# ---------------------------------------------------------------------------


def test_resolver_por_id_doi_y_source_id() -> None:
    """resolve_ident_to_id resuelve las tres formas al mismo id interno."""
    rows = [_row(id="doi:abc123", doi="10.1234/x", source_id="W111")]

    assert resolve_ident_to_id(rows, "doi:abc123") == "doi:abc123"
    assert resolve_ident_to_id(rows, "10.1234/x") == "doi:abc123"
    assert resolve_ident_to_id(rows, "W111") == "doi:abc123"
    assert resolve_ident_to_id(rows, "no-existe") is None


def test_resolver_prioridad_id_gana_sobre_source_id() -> None:
    """Si un ident matchea un id y otro paper lo tiene como source_id, gana el id."""
    rows = [
        _row(id="W999", source_id="W111"),  # su id ES 'W999'
        _row(id="doi:zzz", source_id="W999"),  # tiene 'W999' como source_id
    ]
    # 'W999' debe resolver a la fila cuyo id es 'W999' (prioridad id > source_id)
    row = resolve_ident_to_row(rows, "W999")
    assert row is not None
    assert row["id"] == "W999"


def test_resolve_idents_dedup_preserva_orden_y_lista_no_resueltos() -> None:
    """Dos idents del mismo paper (DOI y source_id) colapsan a un id; lista faltantes."""
    rows = [
        _row(id="doi:aaa", doi="10.1/a", source_id="W1"),
        _row(id="doi:bbb", doi="10.1/b", source_id="W2"),
    ]
    resolved, unresolved = resolve_idents(rows, ["10.1/a", "W1", "doi:bbb", "fantasma"])
    # '10.1/a' y 'W1' apuntan al mismo paper → un solo id, en orden de entrada
    assert resolved == ["doi:aaa", "doi:bbb"]
    assert unresolved == ["fantasma"]


# ---------------------------------------------------------------------------
# Servicio: accept/reject aceptan las tres formas (#287 fricción #1)
# ---------------------------------------------------------------------------


def test_reject_por_source_id_resuelve_al_id_interno(tmp_path: Path) -> None:
    """Reproducción del #287: rechazar por el source_id visible en read show."""
    from bib2graph.service.curate import reject_papers

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [_row(id="doi:a77f0e6c3be4d992", doi="10.2196/1", source_id="W2160088281")],
    )

    result = reject_papers(
        store_path, ["W2160088281"], by="review", decided_at=datetime.now(UTC)
    )

    assert result["rejected_count"] == 1
    assert result["ids"] == ["doi:a77f0e6c3be4d992"]  # resuelto al id interno
    assert _status_by_id(store_path)["doi:a77f0e6c3be4d992"] == "rejected"


def test_accept_por_doi_crudo_resuelve_al_id_interno(tmp_path: Path) -> None:
    """Aceptar por el DOI crudo también funciona."""
    from bib2graph.service.curate import accept_papers

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path, [_row(id="doi:xyz", doi="10.1234/openscience", source_id="W5")]
    )

    result = accept_papers(
        store_path, ["10.1234/openscience"], decided_at=datetime.now(UTC)
    )

    assert result["accepted_count"] == 1
    assert result["ids"] == ["doi:xyz"]
    assert _status_by_id(store_path)["doi:xyz"] == "accepted"


def test_accept_ids_mixtos_dedup_a_un_paper(tmp_path: Path) -> None:
    """Pasar DOI y source_id del MISMO paper cuenta un solo paper aceptado."""
    from bib2graph.service.curate import accept_papers

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_row(id="doi:uno", doi="10.1/uno", source_id="W7")])

    result = accept_papers(
        store_path, ["10.1/uno", "W7", "doi:uno"], decided_at=datetime.now(UTC)
    )

    assert result["accepted_count"] == 1  # colapsan al mismo id
    assert result["ids"] == ["doi:uno"]


def test_reject_ids_no_resueltos_error_lista_y_menciona_formas(tmp_path: Path) -> None:
    """Un ident inexistente → DataError que lo lista y menciona las 3 formas."""
    from bib2graph.service.curate import reject_papers
    from bib2graph.service.errors import DataError

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path, [_row(id="doi:real", doi="10.1/real", source_id="W1")])

    with pytest.raises(DataError) as exc_info:
        reject_papers(store_path, ["fantasma"], decided_at=datetime.now(UTC))

    msg = str(exc_info.value.message)
    assert "fantasma" in msg
    assert "source_id" in msg  # el mensaje explica que acepta las 3 formas
