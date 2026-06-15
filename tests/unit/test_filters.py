"""Tests TDD del Hito 5 — filtros PRISMA.

Tests prescriptos:
- Secuencia año → idioma → min_citas: conteos PRISMA correctos en cada FilterStep.
- Los rejected NO se borran (siguen en la tabla con curation_status=rejected).
- apply_filters sella Manifest.filters con todos los pasos.
- apply_filter individual: conteos before/after correctos.

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pytest

from bib2graph.corpus import Corpus
from bib2graph.filters.prisma import FilterCriterion, apply_filter, apply_filters
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_row(
    id: str,
    *,
    year: int | None = 2020,
    language: str | None = "en",
    cited_by_id: list[str] | None = None,
    research_areas: list[str] | None = None,
    curation_status: str = "candidate",
) -> dict[str, Any]:
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": f"Paper {id}",
        "year": year,
        "abstract": None,
        "source": None,
        "language": language,
        "publisher": None,
        "research_areas": research_areas,
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
        "cited_by_id": cited_by_id,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Tests de apply_filter
# ---------------------------------------------------------------------------


class TestApplyFilterAnio:
    def test_filtra_por_year_gte(self) -> None:
        """Filtra papers anteriores al año mínimo."""
        corpus = _make_corpus(
            _base_row("P1", year=2015),
            _base_row("P2", year=2020),
            _base_row("P3", year=2022),
        )
        criterion = FilterCriterion(field="year", op="gte", value=2018)
        new_corpus, step = apply_filter(corpus, criterion)

        assert step.count_before == 3
        assert step.count_after == 2  # P2 y P3

        rows = new_corpus.to_arrow().to_pylist()
        statuses = {r["id"]: r["curation_status"] for r in rows}
        assert statuses["P1"] == "rejected"
        assert statuses["P2"] == "candidate"
        assert statuses["P3"] == "candidate"

    def test_filtra_por_year_lte(self) -> None:
        corpus = _make_corpus(
            _base_row("P1", year=2015),
            _base_row("P2", year=2020),
            _base_row("P3", year=2022),
        )
        criterion = FilterCriterion(field="year", op="lte", value=2019)
        new_corpus, step = apply_filter(corpus, criterion)

        assert step.count_after == 1  # solo P1
        rows = new_corpus.to_arrow().to_pylist()
        statuses = {r["id"]: r["curation_status"] for r in rows}
        assert statuses["P1"] == "candidate"
        assert statuses["P2"] == "rejected"
        assert statuses["P3"] == "rejected"

    def test_sin_año_es_rechazado(self) -> None:
        corpus = _make_corpus(_base_row("P1", year=None))
        criterion = FilterCriterion(field="year", op="gte", value=2010)
        _, step = apply_filter(corpus, criterion)

        assert step.count_after == 0

    def test_rejected_previos_no_se_cuentan(self) -> None:
        """Los ya-rejected no participan en count_before ni en count_after."""
        corpus = _make_corpus(
            _base_row("P1", year=2020, curation_status="rejected"),
            _base_row("P2", year=2020),
        )
        criterion = FilterCriterion(field="year", op="gte", value=2010)
        _, step = apply_filter(corpus, criterion)

        # count_before solo cuenta los no-rejected = 1 (P2)
        assert step.count_before == 1
        assert step.count_after == 1


class TestApplyFilterIdioma:
    def test_filtra_por_language_eq(self) -> None:
        corpus = _make_corpus(
            _base_row("P1", language="en"),
            _base_row("P2", language="es"),
            _base_row("P3", language="pt"),
        )
        criterion = FilterCriterion(field="language", op="eq", value="en")
        _, step = apply_filter(corpus, criterion)

        assert step.count_before == 3
        assert step.count_after == 1

    def test_filtra_por_language_in(self) -> None:
        corpus = _make_corpus(
            _base_row("P1", language="en"),
            _base_row("P2", language="es"),
            _base_row("P3", language="fr"),
        )
        criterion = FilterCriterion(field="language", op="in", value=["en", "es"])
        _, step = apply_filter(corpus, criterion)

        assert step.count_after == 2

    def test_filtra_por_language_not_in(self) -> None:
        corpus = _make_corpus(
            _base_row("P1", language="en"),
            _base_row("P2", language="zh"),
        )
        criterion = FilterCriterion(field="language", op="not_in", value=["zh"])
        _, step = apply_filter(corpus, criterion)

        assert step.count_after == 1


class TestApplyFilterMinCitations:
    def test_filtra_por_min_citations(self) -> None:
        corpus = _make_corpus(
            _base_row("P1", cited_by_id=["C1", "C2", "C3"]),  # 3 citas
            _base_row("P2", cited_by_id=["C4"]),  # 1 cita
            _base_row("P3", cited_by_id=None),  # 0 citas
        )
        criterion = FilterCriterion(field="min_citations", op="gte", value=2)
        _, step = apply_filter(corpus, criterion)

        assert step.count_before == 3
        assert step.count_after == 1  # solo P1


# ---------------------------------------------------------------------------
# Tests de apply_filters (secuencia PRISMA)
# ---------------------------------------------------------------------------


class TestApplyFiltersSecuencia:
    def test_secuencia_year_idioma_min_citas(self) -> None:
        """Secuencia año → idioma → min_citas con conteos PRISMA correctos."""
        # 5 papers: distintas combinaciones de año / idioma / citas
        corpus = _make_corpus(
            _base_row("P1", year=2015, language="en", cited_by_id=["C1", "C2"]),
            _base_row("P2", year=2020, language="en", cited_by_id=["C3", "C4", "C5"]),
            _base_row("P3", year=2021, language="es", cited_by_id=["C6"]),
            _base_row("P4", year=2022, language="en", cited_by_id=[]),
            _base_row("P5", year=2023, language="fr", cited_by_id=["C7", "C8"]),
        )

        criteria = [
            FilterCriterion(field="year", op="gte", value=2018),  # excluye P1
            FilterCriterion(
                field="language", op="in", value=["en", "es"]
            ),  # excluye P5
            FilterCriterion(field="min_citations", op="gte", value=2),  # excluye P3, P4
        ]

        _final_corpus, steps = apply_filters(corpus, criteria)

        # Paso 1: 5 → 4 (excluye P1)
        assert steps[0].count_before == 5
        assert steps[0].count_after == 4

        # Paso 2: 4 → 3 (excluye P5)
        assert steps[1].count_before == 4
        assert steps[1].count_after == 3

        # Paso 3: 3 → 1 (excluye P3 con 1 cita, P4 con 0 citas)
        assert steps[2].count_before == 3
        assert steps[2].count_after == 1

    def test_rejected_no_se_borran(self) -> None:
        """Los papers rechazados siguen en la tabla como filas rejected."""
        corpus = _make_corpus(
            _base_row("P1", year=2010),
            _base_row("P2", year=2020),
        )
        criteria = [FilterCriterion(field="year", op="gte", value=2015)]
        final_corpus, _ = apply_filters(corpus, criteria)

        rows = final_corpus.to_arrow().to_pylist()
        all_ids = {r["id"] for r in rows}
        # P1 debe seguir en la tabla (como rejected)
        assert "P1" in all_ids
        assert "P2" in all_ids
        # P1 debe estar rejected
        p1_row = next(r for r in rows if r["id"] == "P1")
        assert p1_row["curation_status"] == "rejected"

    def test_sella_manifest_filters(self) -> None:
        """apply_filters sella Manifest.filters con los pasos."""
        corpus = _make_corpus(
            _base_row("P1", year=2010),
            _base_row("P2", year=2020),
        )
        criteria = [
            FilterCriterion(field="year", op="gte", value=2015),
            FilterCriterion(field="language", op="eq", value="en"),
        ]
        final_corpus, _steps = apply_filters(corpus, criteria)

        # El manifest debe tener los pasos sellados
        assert len(final_corpus.manifest.filters) == 2
        assert final_corpus.manifest.filters[0].count_before == 2
        assert final_corpus.manifest.filters[1].count_before == 1

    def test_lista_vacia_de_criterios(self) -> None:
        """Sin criterios, el corpus queda igual y los steps están vacíos."""
        corpus = _make_corpus(_base_row("P1"))
        final_corpus, steps = apply_filters(corpus, [])

        assert steps == []
        assert len(final_corpus) == 1

    def test_apply_filter_no_muta_corpus(self) -> None:
        """apply_filter no muta el corpus de entrada."""
        corpus = _make_corpus(
            _base_row("P1", year=2010),
            _base_row("P2", year=2020),
        )
        original_statuses = {
            r["id"]: r["curation_status"] for r in corpus.to_arrow().to_pylist()
        }

        criterion = FilterCriterion(field="year", op="gte", value=2015)
        apply_filter(corpus, criterion)

        current_statuses = {
            r["id"]: r["curation_status"] for r in corpus.to_arrow().to_pylist()
        }
        assert original_statuses == current_statuses
