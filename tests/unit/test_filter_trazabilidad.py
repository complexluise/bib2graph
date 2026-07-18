"""Tests de trazabilidad PRISMA — issue #126.

Verifica que:
1. Tras ``run_filter``, ``manifest.filters`` persiste en el store y se
   recupera en el próximo ``store.load()`` (no queda ``[]`` vacío).
2. Los pasos persisten con los conteos correctos (``count_before``,
   ``count_after``, ``criteria``).
3. Un paper rechazado por filtro tiene en su provenance el criterio
   de filtro en el campo ``source`` del evento ``rejected``.
4. El flujo limpio ``seed → filter`` (usando ``DuckDBStore``, no restore)
   funciona end-to-end con trazabilidad completa.
5. Re-aplicar ``run_filter`` (idempotencia) reemplaza los pasos anteriores
   en vez de acumularlos indefinidamente.

Marcador: ``unit`` (DuckDB en ``tmp_path``, sin red).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    *,
    id: str,
    title: str = "Título de prueba",
    year: int = 2020,
    language: str | None = "en",
    curation_status: str = "candidate",
) -> dict[str, Any]:
    """Fila mínima con todos los campos del schema canónico."""
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


def _seed_store(store_path: Path, rows: list[dict[str, Any]]) -> None:
    """Puebla un store DuckDB con las filas dadas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)
    store.close()


# ---------------------------------------------------------------------------
# 1. manifest.filters persiste tras run_filter
# ---------------------------------------------------------------------------


def test_manifest_filters_persiste_tras_run_filter(tmp_path: Path) -> None:
    """Tras run_filter, manifest.filters no queda vacío en la siguiente carga."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", year=2010, language="en"),
            _make_row(id="P2", year=2020, language="en"),
            _make_row(id="P3", year=2020, language="fr"),
        ],
    )

    # Aplicar un filtro de idioma
    filter_corpus(store_path, language=["en"])

    # Reabrir el store y verificar que manifest.filters sobrevivió
    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    assert len(corpus.manifest.filters) == 1, (
        "manifest.filters debe tener 1 paso después de run_filter con --language"
    )


def test_manifest_filters_tiene_conteos_correctos(tmp_path: Path) -> None:
    """Los conteos del FilterStep persisten con los valores calculados."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", language="en"),
            _make_row(id="P2", language="en"),
            _make_row(id="P3", language="fr"),
        ],
    )

    filter_corpus(store_path, language=["en"])

    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    step = corpus.manifest.filters[0]
    assert step.count_before == 3, "count_before debe ser 3 (todos los papers)"
    assert step.count_after == 2, "count_after debe ser 2 (P1 y P2 pasan)"
    assert "language" in step.name
    assert "en" in step.criteria


def test_manifest_filters_persiste_multiples_pasos(tmp_path: Path) -> None:
    """Varios criterios en una sola llamada → todos los pasos persisten."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", year=2010, language="en"),
            _make_row(id="P2", year=2020, language="en"),
            _make_row(id="P3", year=2020, language="fr"),
        ],
    )

    filter_corpus(store_path, year_gte=2015, language=["en"])

    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    assert len(corpus.manifest.filters) == 2, (
        "manifest.filters debe tener 2 pasos (year_gte y language)"
    )
    # El primer paso es year_gte
    assert "year" in corpus.manifest.filters[0].name
    # El segundo paso es language
    assert "language" in corpus.manifest.filters[1].name


# ---------------------------------------------------------------------------
# 2. Trazabilidad por paper: provenance.source refleja el criterio
# ---------------------------------------------------------------------------


def test_provenance_rejected_tiene_source_con_criterio(tmp_path: Path) -> None:
    """El paper rechazado tiene en provenance source = criterio del filtro."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", language="en"),
            _make_row(id="P2", language="fr"),
        ],
    )

    filter_corpus(store_path, language=["en"])

    store = DuckDBStore(store_path)
    corpus = store.load()
    # Leer la tabla antes de cerrar el store (el corpus usa el backend DuckDB)
    rows = corpus.to_arrow().to_pylist()
    store.close()

    rejected = [r for r in rows if r["curation_status"] == "rejected"]
    assert len(rejected) == 1
    rejected_paper = rejected[0]
    assert rejected_paper["id"] == "P2"

    # Verificar que la provenance tiene el criterio en source
    provenance_raw = rejected_paper.get("provenance")
    assert provenance_raw is not None, "El paper rechazado debe tener provenance"
    events = json.loads(str(provenance_raw))
    assert len(events) >= 1
    rejected_event = next(e for e in events if e["action"] == "rejected")
    assert rejected_event["source"] is not None, (
        "El evento rejected debe tener source con el criterio del filtro"
    )
    assert "language" in rejected_event["source"], (
        "El source del evento debe mencionar el campo 'language'"
    )
    assert "fr" in str(rejected_event["source"]) or "en" in str(
        rejected_event["source"]
    ), "El source debe mencionar el valor del filtro"


def test_provenance_rejected_tiene_decided_by_prisma_filter(tmp_path: Path) -> None:
    """El evento rejected por filtro tiene decided_by='prisma_filter'."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", year=2020),
            _make_row(id="P2", year=2005),
        ],
    )

    filter_corpus(store_path, year_gte=2010)

    store = DuckDBStore(store_path)
    corpus = store.load()
    # Leer la tabla antes de cerrar el store (el corpus usa el backend DuckDB)
    rows = corpus.to_arrow().to_pylist()
    store.close()

    p2 = next(r for r in rows if r["id"] == "P2")
    assert p2["curation_status"] == "rejected"

    events = json.loads(str(p2["provenance"]))
    rejected_event = next(e for e in events if e["action"] == "rejected")
    assert rejected_event["decided_by"] == "prisma_filter"


# ---------------------------------------------------------------------------
# 3. Idempotencia: re-aplicar filter reemplaza pasos anteriores
# ---------------------------------------------------------------------------


def test_reapply_filter_reemplaza_pasos_anteriores(tmp_path: Path) -> None:
    """Re-ejecutar filter_corpus reemplaza los pasos; no los duplica."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", year=2020),
            _make_row(id="P2", year=2005),
        ],
    )

    # Primera ejecución
    filter_corpus(store_path, year_gte=2010)
    # Segunda ejecución con distinto criterio (reemplaza)
    filter_corpus(store_path, year_gte=2015)

    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    # Solo debe haber 1 paso (el de la segunda ejecución), no 2
    assert len(corpus.manifest.filters) == 1, (
        "Re-ejecutar filter debe reemplazar los pasos anteriores, no acumularlos"
    )
    assert "2015" in corpus.manifest.filters[0].criteria


# ---------------------------------------------------------------------------
# 4. manifest.filters no vacío tras filter_corpus (verificado vía store.load())
#
# El verbo plano 'inspect' (que exponía manifest.filters directamente) fue
# retirado en 0.12.0 (#207); su capacidad de lectura read-only vive ahora en
# 'b2g status'/'b2g read'. Este test verifica la persistencia de manifest.filters
# directamente contra el store, sin pasar por un comando CLI de lectura.
# ---------------------------------------------------------------------------


def test_manifest_filters_no_vacio_tras_filter_via_store(tmp_path: Path) -> None:
    """manifest.filters, leído directamente del store, refleja los pasos aplicados."""
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="P1", language="en"),
            _make_row(id="P2", language="de"),
        ],
    )

    filter_corpus(store_path, language=["en"])

    store = DuckDBStore(store_path)
    corpus = store.load()
    store.close()

    filters = corpus.manifest.filters
    assert len(filters) >= 1, "manifest.filters debe reflejar los filtros aplicados"
    assert filters[0].count_before == 2
    assert filters[0].count_after == 1


# ---------------------------------------------------------------------------
# 5. Flujo limpio seed→filter con DuckDBStore (no restore)
# ---------------------------------------------------------------------------


def test_flujo_seed_filter_trazabilidad_completa(tmp_path: Path) -> None:
    """Flujo completo seed→filter con trazabilidad end-to-end.

    - manifest.filters tiene el paso correcto.
    - El paper rechazado tiene provenance con source del criterio.
    - El paper aceptado (no rechazado) no tiene evento rejected.
    """
    from bib2graph.service.curate import filter_corpus
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(
        store_path,
        [
            _make_row(id="A", year=2022, language="en"),
            _make_row(id="B", year=2022, language="es"),
            _make_row(id="C", year=2022, language="zh"),
        ],
    )

    # Filtrar: solo incluir en/es
    result = filter_corpus(store_path, language=["en", "es"])
    assert result["criteria_applied"] == 1
    assert len(result["steps"]) == 1
    assert result["steps"][0]["excluded"] == 1  # solo C excluido

    store = DuckDBStore(store_path)
    corpus = store.load()

    # manifest.filters tiene el paso
    assert len(corpus.manifest.filters) == 1
    step = corpus.manifest.filters[0]
    assert step.count_before == 3
    assert step.count_after == 2

    # Verificar provenance de C (rechazado) — leer antes de cerrar el store
    rows = {r["id"]: r for r in corpus.to_arrow().to_pylist()}
    store.close()

    assert rows["C"]["curation_status"] == "rejected"
    assert rows["A"]["curation_status"] == "candidate"
    assert rows["B"]["curation_status"] == "candidate"

    events_c = json.loads(str(rows["C"]["provenance"]))
    rejected_event = next(e for e in events_c if e["action"] == "rejected")
    assert rejected_event["source"] is not None
    assert "language" in rejected_event["source"]

    # A y B no tienen evento rejected
    assert rows["A"]["provenance"] is None
    assert rows["B"]["provenance"] is None
