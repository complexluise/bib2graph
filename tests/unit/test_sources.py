"""Tests unitarios del Hito 4 — ``OpenAlexSource`` y ``BibtexSource``.

Todos los tests de red usan ``httpx.MockTransport`` (sin red real en CI).
Los tests de ``BibtexSource`` leen fixtures en ``tests/fixtures/``.

Casos cubiertos:
1. ``_translate`` con ecuación limpia → executed_query + report sin límites.
2. ``_translate`` con NEAR/comodín → query aproximada + línea de límite en report.
3. ``seed`` con MockTransport y fixture JSON → corpus con references_id,
   authors_affiliations per-autor, is_seed=True, curation_status=candidate.
4. ``_reconstruct_abstract`` presente → texto; ausente → None.
5. Tras ``seed``, manifest.openalex_version is not None y
   manifest.equations[0].query == executed_query.
6. ``BibtexSource.load`` sobre .bib con campos faltantes → sin KeyError;
   papers con is_seed=True, curation_status=candidate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from bib2graph.sources.openalex import OpenAlexSource, _reconstruct_abstract, _translate

# ---------------------------------------------------------------------------
# Directorio de fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_WORKS_PATH = FIXTURES_DIR / "sample_works.json"
MINIMAL_BIB_PATH = FIXTURES_DIR / "minimal.bib"
SEMILLAS_IED_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "exploracion"
    / "datos"
    / "semillas_ied.bib"
)


# ---------------------------------------------------------------------------
# Helpers de mock HTTP
# ---------------------------------------------------------------------------


def _make_handler(works: list[dict[str, Any]]) -> httpx.MockTransport:
    """Devuelve un ``MockTransport`` que responde con los works dados.

    Primera llamada: devuelve los works con ``next_cursor``.
    Segunda llamada: devuelve página vacía (fin de paginación).
    """
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
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _load_fixture_works() -> list[dict[str, Any]]:
    return json.loads(SAMPLE_WORKS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. _translate con ecuación limpia
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_translate_ecuacion_limpia() -> None:
    """Ecuación limpia → envuelta en title_and_abstract.search, report vacío."""
    query = '"unequal exchange" OR "ecological debt"'
    executed, report = _translate(query)

    assert executed == f"title_and_abstract.search:({query})"
    assert report == []


@pytest.mark.unit
def test_translate_native_flag() -> None:
    """Con native=True la query pasa cruda y el report lo indica."""
    query = "title.search:ecological+unequal+exchange"
    executed, report = _translate(query, native=True)

    assert executed == query
    assert len(report) == 1
    assert "nativa" in report[0].lower()


# ---------------------------------------------------------------------------
# 2. _translate con NEAR / comodín / tags WoS
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_translate_near_en_report() -> None:
    """``NEAR/3`` → línea en report nombrando el límite."""
    query = '"ecological exchange" NEAR/3 trade'
    executed, report = _translate(query)

    assert "NEAR" in executed  # la query sigue presente (passthrough)
    assert any("NEAR" in r for r in report)


@pytest.mark.unit
def test_translate_comodin_en_report() -> None:
    """Comodín ``*`` → línea en report nombrando el límite."""
    query = "ecolog* AND exchange*"
    _, report = _translate(query)

    assert any("comodín" in r or "*" in r for r in report)


@pytest.mark.unit
def test_translate_tag_wos_en_report() -> None:
    """Tag WoS ``TS=`` → línea en report nombrando el límite."""
    query = 'TS="unequal exchange"'
    _, report = _translate(query)

    assert any("TS=" in r or "WoS" in r or "tag" in r.lower() for r in report)


@pytest.mark.unit
def test_translate_multiples_limites() -> None:
    """Ecuación con NEAR + comodín → ambos reportados."""
    query = "ecolog* NEAR/2 trade*"
    _, report = _translate(query)

    assert len(report) >= 2


# ---------------------------------------------------------------------------
# 3. seed con MockTransport → corpus correcto
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_con_mock_transport() -> None:
    """``seed()`` con MockTransport llena el corpus con los works fixture."""
    works = _load_fixture_works()
    transport = _make_handler(works)

    source = OpenAlexSource(email="test@example.com", transport=transport)
    result = source.seed('"unequal exchange" OR "ecological debt"')

    assert len(result.corpus) == len(works)


@pytest.mark.unit
def test_seed_is_seed_true() -> None:
    """Todos los papers sembrados tienen ``is_seed=True``."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    table = result.corpus.to_arrow()
    is_seed_col = table.column("is_seed").to_pylist()
    assert all(v is True for v in is_seed_col)


@pytest.mark.unit
def test_seed_curation_status_candidate() -> None:
    """Todos los papers sembrados tienen ``curation_status='candidate'``."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    table = result.corpus.to_arrow()
    status_col = table.column("curation_status").to_pylist()
    assert all(s == "candidate" for s in status_col)


@pytest.mark.unit
def test_seed_references_id_pobladas() -> None:
    """``references_id`` se trae inline (``referenced_works``)."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    table = result.corpus.to_arrow()
    refs_col = table.column("references_id").to_pylist()
    # El primer work fixture tiene 2 referenced_works
    first_refs = refs_col[0]
    assert first_refs is not None
    assert "W1111111" in first_refs
    assert "W2222222" in first_refs


@pytest.mark.unit
def test_seed_cited_by_id_vacio() -> None:
    """``cited_by_id`` queda ``[]`` en seed (no viene inline en OpenAlex)."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    table = result.corpus.to_arrow()
    cited_col = table.column("cited_by_id").to_pylist()
    # Todos deben ser [] o None (no listas con elementos)
    for c in cited_col:
        assert not c  # [] o None → falsy


@pytest.mark.unit
def test_seed_authors_affiliations_per_autor() -> None:
    """``authors_affiliations`` se puebla per-autor desde ``authorships``."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    table = result.corpus.to_arrow()
    affil_col = table.column("authors_affiliations").to_pylist()
    # El primer work tiene 2 autores con instituciones
    first_affils = affil_col[0]
    assert first_affils is not None
    assert len(first_affils) == 2
    assert any("EC" in a for a in first_affils)


# ---------------------------------------------------------------------------
# 4. _reconstruct_abstract
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_reconstruct_abstract_presente() -> None:
    """Índice invertido presente → texto reconstruido."""
    inv = {"We": [0], "compute": [1], "footprints": [2]}
    result = _reconstruct_abstract(inv)
    assert result == "We compute footprints"


@pytest.mark.unit
def test_reconstruct_abstract_ausente() -> None:
    """Índice invertido ausente (None) → None."""
    assert _reconstruct_abstract(None) is None


@pytest.mark.unit
def test_reconstruct_abstract_dict_vacio() -> None:
    """Índice invertido vacío ({}) → None."""
    assert _reconstruct_abstract({}) is None


@pytest.mark.unit
def test_seed_abstract_none_cuando_no_hay_indice() -> None:
    """Work sin ``abstract_inverted_index`` → ``abstract`` None en corpus."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological")

    table = result.corpus.to_arrow()
    abstracts = table.column("abstract").to_pylist()
    # El segundo work fixture no tiene índice → abstract None
    assert abstracts[1] is None


# ---------------------------------------------------------------------------
# 5. Manifest.openalex_version y equations tras seed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_openalex_version_en_manifest() -> None:
    """Tras ``seed()``, ``manifest.openalex_version`` no es None (ADR 0017)."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    assert result.corpus.manifest.openalex_version is not None


@pytest.mark.unit
def test_seed_manifest_openalex_version_de_cabecera() -> None:
    """``openalex_version`` refleja la cabecera ``x-openalex-api-version``."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)
    result = source.seed("ecological exchange")

    assert result.corpus.manifest.openalex_version == "2026-05-01"


@pytest.mark.unit
def test_seed_manifest_equations_query() -> None:
    """``manifest.equations[0].query == executed_query``."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)

    query = '"unequal exchange" OR "ecological debt"'
    result = source.seed(query)

    assert len(result.corpus.manifest.equations) == 1
    assert result.corpus.manifest.equations[0].query == result.executed_query


@pytest.mark.unit
def test_seed_executed_query_wrapping() -> None:
    """La query ejecutada envuelve la ecuación en ``title_and_abstract.search``."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)

    query = '"unequal exchange" AND trade'
    result = source.seed(query)

    assert result.executed_query == f"title_and_abstract.search:({query})"


# ---------------------------------------------------------------------------
# 6. BibtexSource.load — regresión T1 (sin KeyError por campo faltante)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bibtex_load_sin_keyerror() -> None:
    """``BibtexSource.load`` sobre .bib con campos faltantes → sin KeyError."""
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    # No debe lanzar KeyError ni ninguna excepción
    corpus = source.load(str(MINIMAL_BIB_PATH))
    assert len(corpus) > 0


@pytest.mark.unit
def test_bibtex_load_is_seed_true() -> None:
    """Todos los papers cargados desde .bib tienen ``is_seed=True``."""
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    corpus = source.load(str(MINIMAL_BIB_PATH))

    table = corpus.to_arrow()
    is_seed_col = table.column("is_seed").to_pylist()
    assert all(v is True for v in is_seed_col)


@pytest.mark.unit
def test_bibtex_load_curation_status_candidate() -> None:
    """Todos los papers BibTeX tienen ``curation_status='candidate'``."""
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    corpus = source.load(str(MINIMAL_BIB_PATH))

    table = corpus.to_arrow()
    status_col = table.column("curation_status").to_pylist()
    assert all(s == "candidate" for s in status_col)


@pytest.mark.unit
def test_bibtex_load_campos_faltantes_none() -> None:
    """Entradas sin doi/abstract/journal → None (sin error)."""
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    corpus = source.load(str(MINIMAL_BIB_PATH))

    table = corpus.to_arrow()
    titles = table.column("title").to_pylist()
    dois = table.column("doi").to_pylist()

    # "Deuda ecológica del Perú" no tiene doi
    idx = next(i for i, t in enumerate(titles) if "Per" in (t or ""))
    assert dois[idx] is None


@pytest.mark.unit
def test_bibtex_load_affiliation_mapeada() -> None:
    """Campo ``affiliation`` del .bib → ``authors_affiliations``."""
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    corpus = source.load(str(MINIMAL_BIB_PATH))

    table = corpus.to_arrow()
    affil_col = table.column("authors_affiliations").to_pylist()
    # bunker1984: affiliation = US
    titles = table.column("title").to_pylist()
    idx = next(i for i, t in enumerate(titles) if "Modes" in (t or ""))
    assert affil_col[idx] is not None
    assert "US" in affil_col[idx]


@pytest.mark.unit
def test_bibtex_load_semillas_ied_sin_keyerror() -> None:
    """``BibtexSource.load`` sobre semillas_ied.bib completo → sin KeyError."""
    from bib2graph.sources.bibtex import BibtexSource

    if not SEMILLAS_IED_PATH.exists():
        pytest.skip("semillas_ied.bib no encontrado")

    source = BibtexSource()
    corpus = source.load(str(SEMILLAS_IED_PATH))
    assert len(corpus) > 0

    table = corpus.to_arrow()
    is_seed_col = table.column("is_seed").to_pylist()
    assert all(v is True for v in is_seed_col)


@pytest.mark.unit
def test_bibtex_seed_raises_not_implemented() -> None:
    """``BibtexSource.seed()`` lanza ``NotImplementedError`` claro."""
    from bib2graph.sources.bibtex import BibtexSource

    source = BibtexSource()
    with pytest.raises(NotImplementedError, match="OpenAlexSource"):
        source.seed("ecological exchange")


# ---------------------------------------------------------------------------
# Tests de precedencia de credenciales (sin red)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_api_key_desde_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """``api_key`` se resuelve desde ``OPENALEX_API_KEY`` si no hay argumento."""
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key-env")
    source = OpenAlexSource()
    assert source._api_key == "test-key-env"


@pytest.mark.unit
def test_api_key_argumento_gana_sobre_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Argumento explícito gana sobre variable de entorno."""
    monkeypatch.setenv("OPENALEX_API_KEY", "env-key")
    source = OpenAlexSource(api_key="explicit-key")
    assert source._api_key == "explicit-key"


# ---------------------------------------------------------------------------
# Fix 1 — SeedResult.corpus valida que sea un Corpus real (no basura)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_result_corpus_invalido_falla() -> None:
    """``SeedResult(corpus="basura", ...)`` debe levantar ``ValidationError``.

    Verifica que el forward-ref ``corpus: "Corpus"`` + ``model_rebuild()`` en
    ``sources/__init__`` restaura la validación runtime del campo.
    """
    from pydantic import ValidationError

    from bib2graph.sources import SeedResult

    with pytest.raises(ValidationError):
        SeedResult(corpus="no soy corpus", executed_query="x", translation_report=[])


@pytest.mark.unit
def test_seed_result_corpus_valido_funciona() -> None:
    """``SeedResult`` con un ``Corpus`` real se construye sin error."""
    import pyarrow as pa

    from bib2graph.corpus import Corpus
    from bib2graph.schemas import CORPUS_SCHEMA
    from bib2graph.sources import SeedResult

    corpus = Corpus.from_arrow(
        pa.table({col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA)
    )
    result = SeedResult(corpus=corpus, executed_query="x", translation_report=[])
    assert result.corpus is corpus


# ---------------------------------------------------------------------------
# Fix 2 — Corpus.with_manifest: API pública de sustitución de manifest
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_with_manifest_devuelve_corpus_nuevo() -> None:
    """``with_manifest`` devuelve una instancia distinta (no la misma)."""
    from datetime import UTC, datetime

    import pyarrow as pa

    from bib2graph.corpus import Corpus, Manifest
    from bib2graph.schemas import CORPUS_SCHEMA, SCHEMA_VERSION

    corpus = Corpus.from_arrow(
        pa.table({col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA)
    )
    nuevo_manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        corpus_hash="abc123",
        lib_version="1.0.0",
        created_at=datetime.now(UTC),
    )
    result = corpus.with_manifest(nuevo_manifest)

    assert result is not corpus
    assert isinstance(result, Corpus)


@pytest.mark.unit
def test_with_manifest_usa_el_manifest_dado() -> None:
    """``with_manifest`` aplica exactamente el Manifest proporcionado."""
    from datetime import UTC, datetime

    import pyarrow as pa

    from bib2graph.corpus import Corpus, EquationRef, Manifest
    from bib2graph.schemas import CORPUS_SCHEMA, SCHEMA_VERSION

    corpus = Corpus.from_arrow(
        pa.table({col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA)
    )
    eq_ref = EquationRef(equation_id="eq-001", query="ecolog*", translation_report=[])
    nuevo_manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        corpus_hash="deadbeef",
        lib_version="0.1.0",
        created_at=datetime.now(UTC),
        openalex_version="2026-05-01",
        equations=[eq_ref],
    )
    result = corpus.with_manifest(nuevo_manifest)

    assert result.manifest is nuevo_manifest
    assert result.manifest.openalex_version == "2026-05-01"
    assert len(result.manifest.equations) == 1
    assert result.manifest.equations[0].equation_id == "eq-001"


@pytest.mark.unit
def test_with_manifest_no_muta_original() -> None:
    """El corpus original no muta: su manifest queda intacto."""
    from datetime import UTC, datetime

    import pyarrow as pa

    from bib2graph.corpus import Corpus, Manifest
    from bib2graph.schemas import CORPUS_SCHEMA, SCHEMA_VERSION

    corpus = Corpus.from_arrow(
        pa.table({col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA)
    )
    manifest_original = corpus.manifest
    nuevo_manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        corpus_hash="changed",
        lib_version="0.2.0",
        created_at=datetime.now(UTC),
    )
    _ = corpus.with_manifest(nuevo_manifest)

    assert corpus.manifest is manifest_original


@pytest.mark.unit
def test_with_manifest_mismo_corpus_hash() -> None:
    """``corpus_hash`` calculado sobre el contenido es el mismo antes y después.

    El hash es sobre los datos del backend, no sobre el manifest; ``with_manifest``
    no toca el backend, por lo que el hash de contenido no cambia.
    """
    from datetime import UTC, datetime

    import pyarrow as pa

    from bib2graph.corpus import Corpus, Manifest, _compute_corpus_hash
    from bib2graph.schemas import CORPUS_SCHEMA, SCHEMA_VERSION

    corpus = Corpus.from_arrow(
        pa.table({col: [] for col in CORPUS_SCHEMA.names}, schema=CORPUS_SCHEMA)
    )
    nuevo_manifest = Manifest(
        schema_version=SCHEMA_VERSION,
        corpus_hash="irrelevante",
        lib_version="0.1.0",
        created_at=datetime.now(UTC),
    )
    result = corpus.with_manifest(nuevo_manifest)

    assert _compute_corpus_hash(corpus.table) == _compute_corpus_hash(result.table)
