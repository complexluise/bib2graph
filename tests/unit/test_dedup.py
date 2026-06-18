"""Tests TDD del Hito 7 — deduplicación fuzzy (autores + keywords).

Tests prescriptos:
- Autores: par por encima del umbral colapsa al canónico.
- Autores: par por debajo del umbral queda separado.
- Keywords: par por encima del umbral colapsa al canónico.
- Keywords: par por debajo del umbral queda separado.
- Canónico = variante más frecuente; desempate lexicográfico.
- Idempotencia: segunda pasada no cambia el Corpus.
- Determinismo: dos corridas con el mismo corpus → mismo corpus_hash.
- ``_raw`` intacto: ``authors_raw``/``keywords_raw`` no cambian.
- rapidfuzz es núcleo (#88): import siempre disponible, funciones ejecutan sin extras.
- Threshold configurable: mismo par colapsa o no según el umbral.
- PreprocRef registrado en el Manifest.
- Corpus de entrada no mutado (semántica de valor).

Marcador: ``unit`` (sin red, sin I/O).
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pytest

from bib2graph.backends.memory import compute_corpus_hash
from bib2graph.corpus import Corpus
from bib2graph.preprocessors.dedup import deduplicate_authors, deduplicate_keywords
from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _base_row(
    id: str,
    *,
    authors_raw: list[str] | None = None,
    authors_id: list[str] | None = None,
    keywords_raw: list[str] | None = None,
    keywords_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima válida para el schema canónico."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": f"Paper {id}",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": authors_raw,
        "authors_id": authors_id,
        "authors_affiliations": None,
        "keywords_raw": keywords_raw,
        "keywords_id": keywords_id,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }


def _make_corpus(*rows: dict[str, Any]) -> Corpus:
    """Construye un Corpus desde filas literales."""
    table = pa.Table.from_pylist(list(rows), schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# Tests de autores
# ---------------------------------------------------------------------------


class TestDeduplicateAuthors:
    def test_par_encima_umbral_colapsa(self) -> None:
        """Dos variantes similares por encima del umbral deben colapsar."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["john smyth"]),
        )
        result = deduplicate_authors(corpus, threshold=0.85)
        rows = result.to_arrow().to_pylist()
        # Ambas filas deben tener el mismo autor (el canónico)
        author_p1 = rows[0]["authors_id"]
        author_p2 = rows[1]["authors_id"]
        assert isinstance(author_p1, list)
        assert isinstance(author_p2, list)
        assert author_p1[0] == author_p2[0], (
            f"Esperaba el mismo canónico en P1 y P2, "
            f"obtuve: {author_p1[0]!r} vs {author_p2[0]!r}"
        )

    def test_par_debajo_umbral_permanece_separado(self) -> None:
        """Dos variantes muy distintas por debajo del umbral deben quedar separadas."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["alice johnson"]),
        )
        result = deduplicate_authors(corpus, threshold=0.92)
        rows = result.to_arrow().to_pylist()
        author_p1 = rows[0]["authors_id"]
        author_p2 = rows[1]["authors_id"]
        assert isinstance(author_p1, list)
        assert isinstance(author_p2, list)
        # Deben ser diferentes
        assert author_p1[0] != author_p2[0], (
            "Autores muy distintos no deberían colapsar"
        )
        assert "john smith" in author_p1
        assert "alice johnson" in author_p2

    def test_threshold_configurable_colapsa(self) -> None:
        """Con umbral bajo, un par moderadamente similar colapsa."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["garcia luis"]),
            _base_row("P2", authors_id=["garcia l"]),
        )
        result_bajo = deduplicate_authors(corpus, threshold=0.50)
        rows = result_bajo.to_arrow().to_pylist()
        # Con umbral bajo deben colapsar
        a1 = rows[0]["authors_id"]
        a2 = rows[1]["authors_id"]
        assert isinstance(a1, list)
        assert isinstance(a2, list)
        assert a1[0] == a2[0], "Con umbral bajo deben colapsar"

    def test_threshold_configurable_no_colapsa(self) -> None:
        """Con umbral muy alto, el mismo par NO colapsa."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["garcia luis"]),
            _base_row("P2", authors_id=["garcia l"]),
        )
        result_alto = deduplicate_authors(corpus, threshold=0.99)
        rows = result_alto.to_arrow().to_pylist()
        a1 = rows[0]["authors_id"]
        a2 = rows[1]["authors_id"]
        assert isinstance(a1, list)
        assert isinstance(a2, list)
        assert a1[0] != a2[0], "Con umbral 0.99 no deberían colapsar"

    def test_authors_raw_intacto(self) -> None:
        """``authors_raw`` no debe modificarse (fuente reversible)."""
        corpus = _make_corpus(
            _base_row(
                "P1",
                authors_raw=["García, Luis"],
                authors_id=["garcia luis"],
            ),
            _base_row(
                "P2",
                authors_raw=["García, L."],
                authors_id=["garcia l"],
            ),
        )
        result = deduplicate_authors(corpus, threshold=0.50)
        rows = result.to_arrow().to_pylist()
        assert rows[0]["authors_raw"] == ["García, Luis"]
        assert rows[1]["authors_raw"] == ["García, L."]

    def test_preproc_ref_registrado(self) -> None:
        """``deduplicate_authors`` debe registrar un ``PreprocRef`` en el Manifest."""
        corpus = _make_corpus(_base_row("P1", authors_id=["john smith"]))
        result = deduplicate_authors(corpus)
        assert len(result.manifest.preprocessors) == 1
        ref = result.manifest.preprocessors[0]
        assert ref.name == "deduplicate_authors"
        assert "library" in ref.params
        assert ref.params["library"] == "rapidfuzz"
        assert "threshold" in ref.params
        assert "n_clusters_collapsed" in ref.params
        assert "rapidfuzz_version" in ref.params

    def test_no_muta_corpus_entrada(self) -> None:
        """El Corpus de entrada no debe mutarse (semántica de valor)."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["john smyth"]),
        )
        original_rows = corpus.to_arrow().to_pylist()
        deduplicate_authors(corpus, threshold=0.85)
        after_rows = corpus.to_arrow().to_pylist()
        assert original_rows == after_rows, "El corpus original fue mutado"


# ---------------------------------------------------------------------------
# Tests de keywords
# ---------------------------------------------------------------------------


class TestDeduplicateKeywords:
    def test_par_encima_umbral_colapsa(self) -> None:
        """Dos keywords similares por encima del umbral deben colapsar."""
        corpus = _make_corpus(
            _base_row("P1", keywords_id=["machine learning"]),
            _base_row("P2", keywords_id=["machine learningg"]),
        )
        result = deduplicate_keywords(corpus, threshold=0.85)
        rows = result.to_arrow().to_pylist()
        kw_p1 = rows[0]["keywords_id"]
        kw_p2 = rows[1]["keywords_id"]
        assert isinstance(kw_p1, list)
        assert isinstance(kw_p2, list)
        assert kw_p1[0] == kw_p2[0], (
            f"Esperaba el mismo canónico, obtuve: {kw_p1[0]!r} vs {kw_p2[0]!r}"
        )

    def test_par_debajo_umbral_permanece_separado(self) -> None:
        """Dos keywords muy distintas por debajo del umbral deben quedar separadas."""
        corpus = _make_corpus(
            _base_row("P1", keywords_id=["machine learning"]),
            _base_row("P2", keywords_id=["climate change"]),
        )
        result = deduplicate_keywords(corpus, threshold=0.90)
        rows = result.to_arrow().to_pylist()
        kw_p1 = rows[0]["keywords_id"]
        kw_p2 = rows[1]["keywords_id"]
        assert isinstance(kw_p1, list)
        assert isinstance(kw_p2, list)
        assert kw_p1[0] != kw_p2[0]

    def test_keywords_raw_intacto(self) -> None:
        """``keywords_raw`` no debe modificarse."""
        corpus = _make_corpus(
            _base_row(
                "P1",
                keywords_raw=["Machine Learning"],
                keywords_id=["machine learning"],
            ),
            _base_row(
                "P2",
                keywords_raw=["Machine Learningg"],
                keywords_id=["machine learningg"],
            ),
        )
        result = deduplicate_keywords(corpus, threshold=0.85)
        rows = result.to_arrow().to_pylist()
        assert rows[0]["keywords_raw"] == ["Machine Learning"]
        assert rows[1]["keywords_raw"] == ["Machine Learningg"]

    def test_preproc_ref_registrado(self) -> None:
        """``deduplicate_keywords`` debe registrar un ``PreprocRef`` en el Manifest."""
        corpus = _make_corpus(_base_row("P1", keywords_id=["climate change"]))
        result = deduplicate_keywords(corpus)
        assert len(result.manifest.preprocessors) == 1
        ref = result.manifest.preprocessors[0]
        assert ref.name == "deduplicate_keywords"
        assert ref.params["library"] == "rapidfuzz"


# ---------------------------------------------------------------------------
# Tests del canónico (variante más frecuente, desempate lexicográfico)
# ---------------------------------------------------------------------------


class TestCanonico:
    def test_canonico_es_variante_mas_frecuente(self) -> None:
        """El canónico del cluster es la variante que aparece en más papers."""
        # "john smith" en 3 papers, "j smith" en 1 → canónico = "john smith"
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["john smith"]),
            _base_row("P3", authors_id=["john smith"]),
            _base_row("P4", authors_id=["j smith"]),
        )
        result = deduplicate_authors(corpus, threshold=0.70)
        rows = result.to_arrow().to_pylist()
        # Todos los papers deben usar "john smith" como canónico
        for row in rows:
            authors = row["authors_id"]
            assert isinstance(authors, list)
            assert authors[0] == "john smith", (
                f"Esperaba 'john smith' como canónico, obtuve {authors[0]!r}"
            )

    def test_desempate_lexicografico(self) -> None:
        """Ante empate de frecuencia, gana el string lexicográficamente menor."""
        # Ambas variantes aparecen en 1 paper: gana la lexicográficamente menor
        corpus = _make_corpus(
            _base_row("P1", authors_id=["b author"]),
            _base_row("P2", authors_id=["a author"]),
        )
        result = deduplicate_authors(corpus, threshold=0.70)
        rows = result.to_arrow().to_pylist()
        # Ambas deben colapsar a "a author" (menor lexicográficamente)
        for row in rows:
            authors = row["authors_id"]
            assert isinstance(authors, list)
            assert authors[0] == "a author", (
                f"Esperaba 'a author' (desempate lex), obtuve {authors[0]!r}"
            )


# ---------------------------------------------------------------------------
# Tests de idempotencia y determinismo
# ---------------------------------------------------------------------------


class TestIdempotenciaDeterminismo:
    def test_idempotencia_authors(self) -> None:
        """Segunda pasada de deduplicate_authors produce el mismo Corpus."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["john smyth"]),
        )
        once = deduplicate_authors(corpus, threshold=0.85)
        twice = deduplicate_authors(once, threshold=0.85)
        # El contenido debe ser idéntico (mismo hash)
        hash_once = compute_corpus_hash(once.to_arrow())
        hash_twice = compute_corpus_hash(twice.to_arrow())
        assert hash_once == hash_twice, "Segunda pasada cambió el corpus"

    def test_idempotencia_keywords(self) -> None:
        """Segunda pasada de deduplicate_keywords produce el mismo Corpus."""
        corpus = _make_corpus(
            _base_row("P1", keywords_id=["machine learning"]),
            _base_row("P2", keywords_id=["machine learningg"]),
        )
        once = deduplicate_keywords(corpus, threshold=0.85)
        twice = deduplicate_keywords(once, threshold=0.85)
        hash_once = compute_corpus_hash(once.to_arrow())
        hash_twice = compute_corpus_hash(twice.to_arrow())
        assert hash_once == hash_twice, "Segunda pasada cambió el corpus"

    def test_determinismo_authors(self) -> None:
        """Dos corridas con el mismo corpus producen el mismo corpus_hash."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["john smyth"]),
            _base_row("P3", authors_id=["jane doe"]),
        )
        result1 = deduplicate_authors(corpus, threshold=0.85)
        result2 = deduplicate_authors(corpus, threshold=0.85)
        hash1 = compute_corpus_hash(result1.to_arrow())
        hash2 = compute_corpus_hash(result2.to_arrow())
        assert hash1 == hash2, "Resultados no deterministas"

    def test_determinismo_keywords(self) -> None:
        """Dos corridas con el mismo corpus de keywords → mismo corpus_hash."""
        corpus = _make_corpus(
            _base_row("P1", keywords_id=["deep learning"]),
            _base_row("P2", keywords_id=["deep learningg"]),
        )
        result1 = deduplicate_keywords(corpus, threshold=0.85)
        result2 = deduplicate_keywords(corpus, threshold=0.85)
        hash1 = compute_corpus_hash(result1.to_arrow())
        hash2 = compute_corpus_hash(result2.to_arrow())
        assert hash1 == hash2, "Resultados no deterministas"


# ---------------------------------------------------------------------------
# Tests de disponibilidad de rapidfuzz (ahora es dependencia del núcleo, #88)
# ---------------------------------------------------------------------------


class TestRapidfuzzCore:
    def test_import_bib2graph_sin_error(self) -> None:
        """``import bib2graph`` no lanza ImportError: rapidfuzz es núcleo (#88)."""
        import importlib

        mod = importlib.import_module("bib2graph")
        assert mod is not None

    def test_import_dedup_sin_error(self) -> None:
        """``import bib2graph.preprocessors.dedup`` no lanza ImportError."""
        import importlib

        mod = importlib.import_module("bib2graph.preprocessors.dedup")
        assert mod is not None

    def test_deduplicate_authors_es_callable(self) -> None:
        """``deduplicate_authors`` está disponible sin extras adicionales."""
        from bib2graph.preprocessors import deduplicate_authors as da

        assert callable(da)

    def test_deduplicate_keywords_es_callable(self) -> None:
        """``deduplicate_keywords`` está disponible sin extras adicionales."""
        from bib2graph.preprocessors import deduplicate_keywords as dk

        assert callable(dk)

    def test_deduplicate_authors_funciona_sin_extras(self) -> None:
        """``deduplicate_authors`` ejecuta sin ImportError (rapidfuzz disponible)."""
        corpus = _make_corpus(_base_row("P1", authors_id=["john smith"]))
        # No debe lanzar ImportError ni ninguna excepción
        result = deduplicate_authors(corpus)
        assert result is not None

    def test_deduplicate_keywords_funciona_sin_extras(self) -> None:
        """``deduplicate_keywords`` ejecuta sin ImportError (rapidfuzz disponible)."""
        corpus = _make_corpus(_base_row("P1", keywords_id=["machine learning"]))
        result = deduplicate_keywords(corpus)
        assert result is not None


# ---------------------------------------------------------------------------
# Tests de transitividad y clusters
# ---------------------------------------------------------------------------


class TestTransitividad:
    def test_cluster_transitivo_autores(self) -> None:
        """Si A~B y B~C (transitivamente), los tres deben colapsar al mismo canónico."""
        # "smith john", "john smith" y "j smith" deben unirse si los umbrales lo permiten
        corpus = _make_corpus(
            _base_row("P1", authors_id=["anna a"]),
            _base_row("P2", authors_id=["anna b"]),
            _base_row("P3", authors_id=["anna c"]),
        )
        # Con umbral bajo, los tres deben colapsar (todos son variantes de "anna X")
        result = deduplicate_authors(corpus, threshold=0.50)
        rows = result.to_arrow().to_pylist()
        canonicos = {row["authors_id"][0] for row in rows if row["authors_id"]}
        assert len(canonicos) == 1, (
            f"Esperaba 1 canónico (cluster transitivo), obtuve: {canonicos}"
        )

    def test_dos_clusters_separados(self) -> None:
        """Dos grupos distintos deben dar dos canónicos distintos."""
        corpus = _make_corpus(
            _base_row("P1", authors_id=["john smith"]),
            _base_row("P2", authors_id=["john smyth"]),
            _base_row("P3", authors_id=["alice jones"]),
            _base_row("P4", authors_id=["alice jonez"]),
        )
        result = deduplicate_authors(corpus, threshold=0.85)
        rows = result.to_arrow().to_pylist()
        canonicos = {row["authors_id"][0] for row in rows if row["authors_id"]}
        assert len(canonicos) == 2, (
            f"Esperaba 2 canónicos (2 clusters), obtuve: {canonicos}"
        )

    def test_sin_variantes_corpus_sin_cambios(self) -> None:
        """Sin variantes en la columna, el corpus devuelto tiene el mismo contenido."""
        corpus = _make_corpus(
            _base_row("P1"),  # sin authors_id ni keywords_id
            _base_row("P2"),
        )
        result = deduplicate_authors(corpus)
        hash_in = compute_corpus_hash(corpus.to_arrow())
        hash_out = compute_corpus_hash(result.to_arrow())
        assert hash_in == hash_out
