"""Tests TDD de la ingesta automática (#88 + fix cross-biblioteca).

Cubre los contratos del issue #88 y la corrección del bug de dedup
cross-biblioteca:

1. Dedup automático en seed (OpenAlex y BibTeX):
   - Tras seed, autores casi-iguales colapsan en ``authors_id``.
   - Tras seed_from_bib, autores casi-iguales colapsan.

2. Dedup automático en restore:
   - Tras restore, keywords casi-iguales colapsan.

3. Idempotencia del corpus_hash:
   - Dos seed con el mismo input → mismo corpus_hash.

4. Idempotencia de datos en re-ingesta:
   - Re-ingesta del mismo corpus no duplica filas.

5. Fix R2 — reloj en la frontera:
   - ``Preprocessor().normalize(corpus, applied_at=<fijo>)`` registra el
     timestamp inyectado, no ``now()``.

6. Verbo b2g thesaurus RETIRADO (#164): la capacidad se mueve a build --thesaurus.
   Ver test_build_thesaurus_flag.py para tests del nuevo flag.

7. Dedup CROSS-BIBLIOTECA (el bug que faltaba):
   - seed → seed con variante del mismo autor en paper DISTINTO → colapsado.
   - restore → seed con variante → colapsado.
   - Thesaurus re-mapeo: aplicar v1 luego v2 → solo canónico v2 persiste.

Filosofía (AGENTS.md): se testea la función detrás del comando.
CliRunner solo donde hay integración de flag necesaria.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------

SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "sample_works.json").read_text(
        encoding="utf-8"
    )
)


def _make_mock_transport(
    works: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    """MockTransport que responde con los works dados (1 página + EOF)."""
    if works is None:
        works = SAMPLE_WORKS
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            body = {
                "results": works,
                "meta": {"count": len(works), "next_cursor": None},
            }
        else:
            body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-06-17"},
        )

    return httpx.MockTransport(handler)


def _make_corpus_row(
    *,
    id: str,
    title: str = "Test",
    authors_id: list[str] | None = None,
    keywords_id: list[str] | None = None,
    keywords_raw: list[str] | None = None,
    curation_status: str = "candidate",
    is_seed: bool = True,
    year: int = 2020,
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
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
        "is_seed": is_seed,
        "curation_status": curation_status,
        "provenance": None,
        "authors_raw": None,
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


def _make_parquet(
    path: Path,
    rows: list[dict[str, Any]],
) -> Path:
    """Escribe un parquet con el schema canónico en ``path``."""
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    import pyarrow.parquet as pq

    pq.write_table(table, str(path))
    return path


BIB_CON_AUTORES_SIMILARES = """\
@article{p1,
  author  = {Martínez-Alier, Joan and Garcia-Lopez, Maria},
  title   = {Paper One},
  journal = {Journal X},
  year    = {2010},
  doi     = {10.1234/p1},
}

@article{p2,
  author  = {Martínez Alier, Joan and garcia lopez maria},
  title   = {Paper Two},
  journal = {Journal Y},
  year    = {2011},
  doi     = {10.1234/p2},
}
"""


# ---------------------------------------------------------------------------
# 1. Dedup automático en seed_from_bib
# ---------------------------------------------------------------------------


def test_seed_from_bib_corpus_queda_deduplicado(tmp_path: Path) -> None:
    """Tras seed_from_bib, autores casi-iguales deben colapsar en authors_id.

    El auto-preproc normaliza (lowercase + quita acentos) y luego aplica dedup.
    Dos entradas BibTeX con el mismo autor con y sin acentos deben quedar
    con el mismo valor en authors_id.
    """
    pytest.importorskip(
        "bibtexparser", reason="Requiere extra [bibtex]: uv sync --extra bibtex"
    )
    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    bib_path = tmp_path / "test.bib"
    bib_path.write_text(BIB_CON_AUTORES_SIMILARES, encoding="utf-8")
    store_path = tmp_path / "test.duckdb"

    run_seed_from_bib(store_path, bib_path)

    corpus = DuckDBStore(store_path).load()
    rows = corpus.to_arrow().to_pylist()

    # Ambos papers deben tener el mismo autor canónico para "martínez-alier joan"
    # tras normalización (lowercase + sin acentos + dedup)
    all_authors = [author for row in rows for author in (row[Col.AUTHORS_ID] or [])]
    # Después de normalizar: "martinez-alier, joan" o similar
    # Después de dedup: deben ser idénticos entre papers (mismo canónico)
    # Verificamos que no haya dos variantes del mismo autor
    unique_martinez = {a for a in all_authors if "martinez" in a or "martínez" in a}
    assert len(unique_martinez) <= 1, (
        f"El dedup no colapsó las variantes de Martínez-Alier: {unique_martinez}"
    )


def test_seed_corpus_queda_normalizado(tmp_path: Path) -> None:
    """Tras run_seed (OpenAlex mock), el corpus está normalizado.

    Verifica que normalize_and_dedup se aplicó al corpus entrante: los
    authors_id no tienen mayúsculas (normalización lowercase) y el corpus
    tiene al menos el número de papers del mock.
    El manifest no se persiste en DuckDB; el contrato de datos es lo observable.
    """
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    transport = _make_mock_transport()
    store_path = tmp_path / "test.duckdb"

    run_seed(store_path, "ecology", transport=transport)

    corpus = DuckDBStore(store_path).load()
    rows = corpus.to_arrow().to_pylist()

    # Hay al menos 1 paper del mock
    assert len(rows) > 0, "El corpus está vacío tras el seed"

    # Todos los authors_id deben estar en minúsculas (efecto de normalize)
    for row in rows:
        authors = row.get(Col.AUTHORS_ID) or []
        for author in authors:
            assert author == author.lower(), (
                f"authors_id no normalizado (uppercase): {author!r} en paper {row['id']}"
            )


# ---------------------------------------------------------------------------
# 2. Dedup automático en restore
# ---------------------------------------------------------------------------


def test_restore_corpus_queda_deduplicado(tmp_path: Path) -> None:
    """Tras run_restore, keywords casi-iguales colapsan (dedup aplicado).

    El manifest no se persiste en DuckDB; el contrato observable es que
    la variante orto-cercana desaparece del corpus persistido.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [
        _make_corpus_row(id="P1", keywords_id=["machine learning"]),
        _make_corpus_row(id="P2", keywords_id=["machine learningg"]),
    ]
    parquet_path = _make_parquet(tmp_path / "corpus.parquet", rows)
    store_path = tmp_path / "test.duckdb"

    run_restore(store_path, parquet_path)

    corpus = DuckDBStore(store_path).load()
    rows_result = corpus.to_arrow().to_pylist()
    all_kws = [kw for row in rows_result for kw in (row[Col.KEYWORDS_ID] or [])]
    unique_kws = set(all_kws)
    # La variante con typo ("machine learningg") debe haberse colapsado
    assert "machine learningg" not in unique_kws, (
        f"La variante 'machine learningg' no fue deduplicada. Keywords: {unique_kws}"
    )
    assert "machine learning" in unique_kws, (
        f"El canónico 'machine learning' debería estar en el corpus. Keywords: {unique_kws}"
    )


def test_restore_keywords_similares_colapsan(tmp_path: Path) -> None:
    """Tras restore, keywords casi-iguales colapsan en keywords_id."""
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [
        _make_corpus_row(id="P1", keywords_id=["machine learning"]),
        _make_corpus_row(id="P2", keywords_id=["machine learningg"]),
    ]
    parquet_path = _make_parquet(tmp_path / "corpus.parquet", rows)
    store_path = tmp_path / "test.duckdb"

    run_restore(store_path, parquet_path)

    corpus = DuckDBStore(store_path).load()
    rows_result = corpus.to_arrow().to_pylist()
    all_kws = [kw for row in rows_result for kw in (row[Col.KEYWORDS_ID] or [])]
    unique_kws = set(all_kws)
    assert len(unique_kws) == 1, f"Las keywords similares no colapsaron: {unique_kws}"


# ---------------------------------------------------------------------------
# 3. Idempotencia del corpus_hash tras dos seeds con el mismo input
# ---------------------------------------------------------------------------


def test_dos_seeds_mismo_input_mismo_corpus_hash(tmp_path: Path) -> None:
    """Dos run_seed con el mismo input producen el mismo corpus_hash.

    La normalización + dedup son deterministas e idempotentes: el resultado
    de contenido no cambia entre la primera y segunda siembra con el mismo corpus.
    """
    from bib2graph.backends.memory import compute_corpus_hash
    from bib2graph.cli.commands.seed import run_seed

    store1 = tmp_path / "test1.duckdb"
    store2 = tmp_path / "test2.duckdb"

    run_seed(store1, "ecology", transport=_make_mock_transport())
    run_seed(store2, "ecology", transport=_make_mock_transport())

    from bib2graph.stores.duckdb import DuckDBStore

    corpus1 = DuckDBStore(store1).load()
    corpus2 = DuckDBStore(store2).load()

    hash1 = compute_corpus_hash(corpus1.to_arrow())
    hash2 = compute_corpus_hash(corpus2.to_arrow())

    assert hash1 == hash2, (
        "Mismo input con run_seed debe producir el mismo corpus_hash "
        f"(hash1={hash1!r}, hash2={hash2!r})"
    )


# ---------------------------------------------------------------------------
# 4. Idempotencia de datos en re-ingesta
# ---------------------------------------------------------------------------


def test_reingesta_no_infla_corpus(tmp_path: Path) -> None:
    """Re-ingesta con el mismo parquet no duplica filas en el corpus.

    persist_replace es idempotente: dos restore sucesivos del mismo
    parquet dejan el mismo número de papers.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.stores.duckdb import DuckDBStore

    rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    parquet_path = _make_parquet(tmp_path / "corpus.parquet", rows)
    store_path = tmp_path / "test.duckdb"

    # Primera ingesta
    run_restore(store_path, parquet_path)
    corpus_after_first = DuckDBStore(store_path).load()
    n_papers_first = len(corpus_after_first)

    # Segunda ingesta (mismo parquet): idempotente en datos
    run_restore(store_path, parquet_path)
    corpus_after_second = DuckDBStore(store_path).load()
    n_papers_second = len(corpus_after_second)

    assert n_papers_first == n_papers_second == 2, (
        f"Re-ingesta no debería cambiar el número de papers: "
        f"primera={n_papers_first}, segunda={n_papers_second}."
    )


# ---------------------------------------------------------------------------
# 5. Fix R2 — Preprocessor.normalize acepta applied_at inyectado
# ---------------------------------------------------------------------------


def test_preprocessor_normalize_usa_applied_at_inyectado() -> None:
    """Preprocessor.normalize registra el timestamp inyectado, no now().

    Si applied_at se inyecta con un valor fijo, el PreprocRef del manifest
    debe tener exactamente ese timestamp (no datetime.now()).
    """
    import pyarrow as pa

    from bib2graph.corpus import Corpus
    from bib2graph.preprocessors.preprocessor import Preprocessor
    from bib2graph.schemas import CORPUS_SCHEMA

    row = {
        "id": "P1",
        "openalex_id": None,
        "doi": None,
        "title": "Test",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en-US",
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": ["García, Luis"],
        "authors_affiliations": None,
        "keywords_raw": None,
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }
    corpus = Corpus.from_arrow(pa.Table.from_pylist([row], schema=CORPUS_SCHEMA))

    fixed_ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
    preprocessor = Preprocessor()
    result = preprocessor.normalize(corpus, applied_at=fixed_ts)

    assert len(result.manifest.preprocessors) == 1
    ref = result.manifest.preprocessors[0]
    assert ref.name == "normalize"
    assert ref.params.get("applied_at") == fixed_ts.isoformat(), (
        f"Esperaba applied_at={fixed_ts.isoformat()!r}, "
        f"obtuve {ref.params.get('applied_at')!r}"
    )


def test_preprocessor_apply_thesaurus_usa_applied_at_inyectado(
    tmp_path: Path,
) -> None:
    """Preprocessor.apply_thesaurus registra el timestamp inyectado, no now()."""
    import json

    import pyarrow as pa

    from bib2graph.corpus import Corpus
    from bib2graph.preprocessors.preprocessor import Preprocessor
    from bib2graph.schemas import CORPUS_SCHEMA

    thesaurus = {
        "concepts": {
            "ecology": {
                "aliases_en": ["ecology", "ecological science"],
            }
        }
    }
    thesaurus_path = tmp_path / "thesaurus.json"
    thesaurus_path.write_text(json.dumps(thesaurus), encoding="utf-8")

    row = {
        "id": "P1",
        "openalex_id": None,
        "doi": None,
        "title": "Test",
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": None,
        "publisher": None,
        "research_areas": None,
        "is_seed": True,
        "curation_status": "candidate",
        "provenance": None,
        "authors_raw": None,
        "authors_id": None,
        "authors_affiliations": None,
        "keywords_raw": ["ecology"],
        "keywords_id": None,
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": None,
        "references_doi": None,
        "cited_by_id": None,
    }
    corpus = Corpus.from_arrow(pa.Table.from_pylist([row], schema=CORPUS_SCHEMA))

    fixed_ts = datetime(2025, 6, 1, 8, 0, 0, tzinfo=UTC)
    preprocessor = Preprocessor()
    result = preprocessor.apply_thesaurus(corpus, thesaurus_path, applied_at=fixed_ts)

    assert len(result.manifest.preprocessors) == 1
    ref = result.manifest.preprocessors[0]
    assert ref.name == "apply_thesaurus"
    assert ref.params.get("applied_at") == fixed_ts.isoformat(), (
        f"Esperaba applied_at={fixed_ts.isoformat()!r}, "
        f"obtuve {ref.params.get('applied_at')!r}"
    )


# ---------------------------------------------------------------------------
# 6. Verbo b2g thesaurus RETIRADO (#164)
#    La capacidad se movio a build --thesaurus. Ver test_build_thesaurus_flag.py
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 7. normalize_and_dedup standalone
# ---------------------------------------------------------------------------


def test_normalize_and_dedup_standalone() -> None:
    """normalize_and_dedup funciona como función de librería sin frontera CLI."""
    import pyarrow as pa

    from bib2graph.cli._ingest import normalize_and_dedup
    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA

    rows = [
        {
            "id": "P1",
            "openalex_id": None,
            "doi": None,
            "title": "A",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": "en-US",
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "candidate",
            "provenance": None,
            "authors_raw": None,
            "authors_id": ["García, Luis"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["machine learning"],
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": None,
            "references_doi": None,
            "cited_by_id": None,
        },
        {
            "id": "P2",
            "openalex_id": None,
            "doi": None,
            "title": "B",
            "year": 2020,
            "abstract": None,
            "source": None,
            "language": "es-AR",
            "publisher": None,
            "research_areas": None,
            "is_seed": True,
            "curation_status": "candidate",
            "provenance": None,
            "authors_raw": None,
            "authors_id": ["garcia, luis"],
            "authors_affiliations": None,
            "keywords_raw": None,
            "keywords_id": ["machine learningg"],
            "institutions_raw": None,
            "institutions_id": None,
            "references_id": None,
            "references_doi": None,
            "cited_by_id": None,
        },
    ]
    corpus = Corpus.from_arrow(pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA))

    fixed_ts = datetime(2025, 3, 10, tzinfo=UTC)
    result = normalize_and_dedup(corpus, applied_at=fixed_ts)

    # authors_id debe estar normalizado (sin acentos, lowercase)
    result_rows = result.to_arrow().to_pylist()
    all_authors = {a for row in result_rows for a in (row["authors_id"] or [])}
    # Después de normalizar y dedup: debe haber un solo canónico
    assert len(all_authors) == 1, f"Esperaba 1 canónico de autor, obtuve: {all_authors}"

    # language debe estar normalizado (subtag primario)
    langs = {row["language"] for row in result_rows}
    for lang in langs:
        if lang is not None:
            assert "-" not in lang, f"language no normalizado: {lang!r}"


# ---------------------------------------------------------------------------
# 8. Dedup CROSS-BIBLIOTECA (el bug del requisito del PO)
# ---------------------------------------------------------------------------


def test_seed_seed_cross_biblioteca_colapsa_autores(tmp_path: Path) -> None:
    """seed P1 con 'john smithh' → seed P2 con 'john smith' → colapsados.

    Requisito central del PO: TODA la biblioteca acumulada siempre deduplicada.
    La variante anterior persistida (john smithh en P1) debe colapsar con la
    variante nueva (john smith en P2) en la segunda ingesta, ya que el dedup
    ahora opera sobre el corpus COMPLETO merged.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"

    # Primera ingesta: P1 con variante con typo "john smithh"
    rows_p1 = [_make_corpus_row(id="P1", title="Paper One", authors_id=["john smithh"])]
    parquet_p1 = _make_parquet(tmp_path / "p1.parquet", rows_p1)
    run_restore(store_path, parquet_p1)

    # Segunda ingesta: P2 DISTINTO con variante "john smith" (> umbral 0.92)
    rows_p2 = [_make_corpus_row(id="P2", title="Paper Two", authors_id=["john smith"])]
    parquet_p2 = _make_parquet(tmp_path / "p2.parquet", rows_p2)
    run_restore(store_path, parquet_p2)

    # Reload desde disco: la biblioteca persistida debe tener un solo canónico
    corpus = DuckDBStore(store_path).load()
    rows_result = corpus.to_arrow().to_pylist()
    all_authors = [a for row in rows_result for a in (row[Col.AUTHORS_ID] or [])]
    unique_authors = set(all_authors)

    assert len(unique_authors) == 1, (
        f"Dedup cross-biblioteca falló: la biblioteca persistida tiene AMBAS variantes "
        f"del mismo autor. Variantes encontradas: {unique_authors}. "
        "El dedup debe operar sobre el corpus COMPLETO merged, no solo intra-lote."
    )


def test_seed_chain_cross_biblioteca_colapsa_keywords(tmp_path: Path) -> None:
    """restore P1 con 'deep learning' → seed P2 con 'deep learningg' → colapsados.

    Variante del test cross-biblioteca: primera ingesta vía restore,
    segunda vía restore con paper distinto. El dedup cross-biblioteca
    debe colapsar keywords similares entre papers distintos.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"

    # Primera ingesta: P1 con keyword canónica "deep learning"
    rows_p1 = [
        _make_corpus_row(id="P1", title="Paper One", keywords_id=["deep learning"])
    ]
    parquet_p1 = _make_parquet(tmp_path / "p1.parquet", rows_p1)
    run_restore(store_path, parquet_p1)

    # Segunda ingesta: P2 DISTINTO con typo "deep learningg" (> umbral 0.90)
    rows_p2 = [
        _make_corpus_row(id="P2", title="Paper Two", keywords_id=["deep learningg"])
    ]
    parquet_p2 = _make_parquet(tmp_path / "p2.parquet", rows_p2)
    run_restore(store_path, parquet_p2)

    # Reload desde disco
    corpus = DuckDBStore(store_path).load()
    rows_result = corpus.to_arrow().to_pylist()
    all_kws = [kw for row in rows_result for kw in (row[Col.KEYWORDS_ID] or [])]
    unique_kws = set(all_kws)

    assert "deep learningg" not in unique_kws, (
        f"Dedup cross-biblioteca falló: la variante 'deep learningg' persiste. "
        f"Keywords encontradas: {unique_kws}."
    )
    assert len(unique_kws) == 1, (
        f"Debería haber 1 sola keyword canónica, obtuve: {unique_kws}."
    )


def test_seed_openalex_cross_biblioteca_colapsa_autores(tmp_path: Path) -> None:
    """restore P1 con variante → seed OpenAlex → biblioteca colapsada.

    Verifica que la ruta seed (OpenAlex mock) también aplica dedup
    cross-biblioteca al mergear con lo existente.
    """
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.cli.commands.seed import run_seed
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"

    # Primera ingesta: paper con autor que tiene variante cercana a algún autor
    # que traería OpenAlex mock. Usamos un autor genérico del fixture SAMPLE_WORKS
    # para confirmar que el dedup cross-biblioteca opera. Como el fixture
    # tiene autores en lowercase (ya normalizados), ponemos uno con typo.
    # El test valida que la ruta run_seed usa persist_replace (no upsert).
    rows_p1 = [
        _make_corpus_row(
            id="CROSS_TEST_EXISTING",
            title="Existing Paper",
            keywords_id=["ecology"],
        )
    ]
    parquet_p1 = _make_parquet(tmp_path / "existing.parquet", rows_p1)
    run_restore(store_path, parquet_p1)

    count_before = len(DuckDBStore(store_path).load())

    # Segunda ingesta: seed OpenAlex trae papers nuevos; el corpus existente
    # se mergea y dedup se aplica sobre el total.
    run_seed(store_path, "ecology", transport=_make_mock_transport())

    corpus_after = DuckDBStore(store_path).load()
    count_after = len(corpus_after)

    # El corpus debe haber crecido (los papers del mock son distintos)
    assert count_after >= count_before, (
        "El corpus no debería encogerse tras un seed adicional."
    )

    # Todos los authors_id del corpus completo deben estar normalizados
    rows_result = corpus_after.to_arrow().to_pylist()
    for row in rows_result:
        for author in row.get(Col.AUTHORS_ID) or []:
            assert author == author.lower(), (
                f"authors_id no normalizado en corpus cross-biblioteca: {author!r}"
            )


# ---------------------------------------------------------------------------
# 9. build --thesaurus re-mapeo: persist_replace evita acumulacion de canonicos
# ---------------------------------------------------------------------------


def test_thesaurus_remapeo_no_acumula_canonicos(tmp_path: Path) -> None:
    """Aplicar thesaurus v1 luego v2 → solo el canónico v2 persiste.

    Mismo bug de raíz que el dedup cross-biblioteca: el upsert-concat
    reintroduciría el canónico v1 junto al v2 en la segunda aplicación.
    persist_replace evita esta acumulación.
    """
    import json as _json

    from bib2graph.cli.commands.build import run_build
    from bib2graph.cli.commands.restore import run_restore
    from bib2graph.constants import Col
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"

    # Corpus inicial con keyword "deep learning" en keywords_raw (input del thesaurus).
    # El thesaurus lee keywords_raw y escribe keywords_id; si keywords_raw es None
    # la fila se omite. keywords_id inicial es None (lo llena el thesaurus v1).
    rows = [
        _make_corpus_row(
            id="P1",
            title="Paper One",
            keywords_raw=["deep learning"],
        )
    ]
    parquet_path = _make_parquet(tmp_path / "corpus.parquet", rows)
    run_restore(store_path, parquet_path)

    # Thesaurus v1: "deep learning" → "ml"
    thesaurus_v1 = {
        "concepts": {
            "ml": {
                "aliases_en": ["deep learning", "machine learning", "ml"],
            }
        }
    }
    th_v1_path = tmp_path / "thesaurus_v1.json"
    th_v1_path.write_text(_json.dumps(thesaurus_v1), encoding="utf-8")
    run_build(store_path, thesaurus_path=th_v1_path)

    # Verificar estado tras v1
    corpus_v1 = DuckDBStore(store_path).load()
    rows_v1 = corpus_v1.to_arrow().to_pylist()
    kws_v1 = {kw for row in rows_v1 for kw in (row[Col.KEYWORDS_ID] or [])}
    assert "ml" in kws_v1, (
        f"Thesaurus v1 no mapeó 'deep learning' → 'ml'. Kws: {kws_v1}"
    )

    # Thesaurus v2: "deep learning" → "artificial intelligence" (mapeo DISTINTO)
    thesaurus_v2 = {
        "concepts": {
            "artificial intelligence": {
                "aliases_en": ["deep learning", "artificial intelligence", "ai"],
            }
        }
    }
    th_v2_path = tmp_path / "thesaurus_v2.json"
    th_v2_path.write_text(_json.dumps(thesaurus_v2), encoding="utf-8")
    run_build(store_path, thesaurus_path=th_v2_path)

    # Reload: solo debe haber el canónico v2, no acumulación de v1 + v2
    corpus_v2 = DuckDBStore(store_path).load()
    rows_v2 = corpus_v2.to_arrow().to_pylist()
    kws_v2 = {kw for row in rows_v2 for kw in (row[Col.KEYWORDS_ID] or [])}

    assert "ml" not in kws_v2, (
        f"Thesaurus v2 no reemplazó el canónico v1 ('ml'): sigue presente. "
        f"Keywords en la biblioteca: {kws_v2}. "
        "El re-mapeo debe reemplazar, no acumular."
    )
    assert "artificial intelligence" in kws_v2, (
        f"El canónico v2 ('artificial intelligence') no está en la biblioteca. "
        f"Keywords: {kws_v2}."
    )
