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


# El contrato de campos de BibtexSource.load (is_seed=True, curation_status="candidate",
# campos faltantes → None, sin KeyError) vive en test_bibtex_source_contrato.py
# (test_campos_title_autores_anio_keywords_persisten) y se ejercita end-to-end en
# test_seed_from_bib.py (run_seed_from_bib usa BibtexSource.load). Epic #184, sub-tarea 7.


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


# ---------------------------------------------------------------------------
# #14 — max_results: el source respeta el tope al paginar
# ---------------------------------------------------------------------------


def _make_handler_paged(
    works: list[dict[str, Any]], *, page_size: int = 2
) -> httpx.MockTransport:
    """MockTransport que devuelve ``works`` en páginas de ``page_size``.

    Permite verificar que ``max_results`` corta la paginación antes de agotar
    todos los works disponibles cuando el tope es menor que el total.
    """
    pages: list[list[dict[str, Any]]] = []
    for i in range(0, len(works), page_size):
        pages.append(works[i : i + page_size])
    # Añadir página vacía al final para señalar fin de paginación
    pages.append([])
    call_count: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        idx = call_count[0]
        call_count[0] += 1
        page = pages[idx] if idx < len(pages) else []
        has_next = idx < len(pages) - 2  # hay más páginas no vacías
        body = {
            "results": page,
            "meta": {
                "count": len(works),
                "next_cursor": "cursor_next" if has_next else None,
            },
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


@pytest.mark.unit
def test_max_results_propagado_al_source() -> None:
    """``OpenAlexSource(max_results=N)`` almacena el valor en ``_max_results``."""
    source = OpenAlexSource(max_results=30)
    assert source._max_results == 30


@pytest.mark.unit
def test_max_results_default_es_200() -> None:
    """Sin ``max_results`` explícito, el default es 200."""
    source = OpenAlexSource()
    assert source._max_results == 200


@pytest.mark.unit
def test_seed_max_results_corta_resultados() -> None:
    """``seed()`` con ``max_results=1`` devuelve a lo sumo 1 paper."""
    works = _load_fixture_works()
    # Fixture tiene al menos 2 works; con max_results=1 solo llega 1
    assert len(works) >= 2

    transport = _make_handler_paged(works, page_size=2)
    source = OpenAlexSource(max_results=1, transport=transport)
    result = source.seed("ecological exchange")

    assert len(result.corpus) == 1


@pytest.mark.unit
def test_seed_max_results_trae_todos_si_hay_menos() -> None:
    """Si el total de works < max_results, se traen todos."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(max_results=9999, transport=transport)
    result = source.seed("ecological exchange")

    assert len(result.corpus) == len(works)


# ---------------------------------------------------------------------------
# #30 — negaciones / exclusiones en _translate y seed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_translate_sin_exclusiones_comportamiento_actual() -> None:
    """Sin ``exclude``, el comportamiento es idéntico al actual (sin AND NOT)."""
    query = '"unequal exchange" OR trade'
    executed, _report = _translate(query)

    assert executed == f"title_and_abstract.search:({query})"
    # Sin exclusiones no aparece AND NOT
    assert "AND NOT" not in executed


@pytest.mark.unit
def test_translate_con_una_exclusion() -> None:
    """Un término excluido → cláusula ``AND NOT "…"`` dentro de title_and_abstract.search."""
    query = "sistémico AND complejidad"
    executed, _report = _translate(query, exclude=["machine learning"])

    # El campo NO se repite: exactamente un "title_and_abstract.search:" en el filtro
    assert executed.count("title_and_abstract.search:") == 1
    # La cláusula NOT va dentro del paréntesis, sin prefijo de campo
    assert 'AND NOT "machine learning"' in executed
    assert "AND NOT title_and_abstract.search:" not in executed
    # La query base sigue envuelta correctamente
    assert executed.startswith(f"title_and_abstract.search:({query})")


@pytest.mark.unit
def test_translate_con_multiples_exclusiones() -> None:
    """Múltiples exclusiones → una cláusula AND NOT por cada término, todas dentro del paréntesis."""
    query = "sujeto AND sistema"
    terms = ["machine learning", "algorithm", "lupus"]
    executed, _report = _translate(query, exclude=terms)

    # El campo NO se repite: exactamente un "title_and_abstract.search:" en el filtro
    assert executed.count("title_and_abstract.search:") == 1
    assert "AND NOT title_and_abstract.search:" not in executed
    for term in terms:
        assert f'AND NOT "{term}"' in executed


@pytest.mark.unit
def test_translate_exclusiones_en_translation_report() -> None:
    """Las exclusiones aparecen listadas en el ``translation_report``."""
    _, report = _translate(
        "ecological exchange", exclude=["machine learning", "algorithm"]
    )

    assert len(report) >= 1
    # El report debe mencionar explícitamente las exclusiones
    combined = " ".join(report)
    assert "machine learning" in combined
    assert "algorithm" in combined


@pytest.mark.unit
def test_translate_exclusion_lista_vacia_sin_efecto() -> None:
    """``exclude=[]`` equivale a sin exclusiones."""
    query = "ecological exchange"
    executed_sin, report_sin = _translate(query)
    executed_con, report_con = _translate(query, exclude=[])

    assert executed_sin == executed_con
    assert report_sin == report_con


@pytest.mark.unit
def test_translate_exclusion_none_sin_efecto() -> None:
    """``exclude=None`` equivale a sin exclusiones."""
    query = "ecological exchange"
    executed_sin, _ = _translate(query)
    executed_con, _ = _translate(query, exclude=None)

    assert executed_sin == executed_con


# La forma de la query con exclusiones (campo no repetido, AND NOT dentro del
# paréntesis, exclusiones en el report) está cubierta por los tests PUROS de
# _translate (test_translate_con_una_exclusion / _con_multiples_exclusiones /
# _exclusiones_en_translation_report), que corren en el gate; el comportamiento
# REAL contra la API (count>0) lo cubre el test @network
# tests/integration/test_openalex_exclude_integration.py. Estos tests seed+mock
# solo re-verificaban que seed() expone la salida de _translate. Epic #184, sub-tarea 6.


@pytest.mark.unit
def test_seed_sin_exclude_comportamiento_intacto() -> None:
    """Sin ``exclude``, la query sigue siendo solo el wrapping PASSTHROUGH."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)

    query = '"unequal exchange" AND trade'
    result = source.seed(query)

    assert result.executed_query == f"title_and_abstract.search:({query})"
    assert "AND NOT" not in result.executed_query


@pytest.mark.unit
def test_translate_native_ignora_exclude() -> None:
    """Con ``native=True`` las exclusiones se ignoran: la query pasa cruda sin AND NOT."""
    query = "title.search:ecologia"
    executed, report = _translate(query, native=True, exclude=["machine learning"])

    assert executed == query
    assert "AND NOT" not in executed
    # El report indica modo nativo pero no menciona exclusiones
    assert any("nativa" in r.lower() for r in report)


@pytest.mark.unit
def test_seed_native_ignora_exclude() -> None:
    """``seed(native=True, exclude=[...])`` no añade AND NOT a la query ejecutada."""
    works = _load_fixture_works()
    transport = _make_handler(works)
    source = OpenAlexSource(transport=transport)

    query = "title.search:ecologia"
    result = source.seed(query, native=True, exclude=["machine learning", "algorithm"])

    assert result.executed_query == query
    assert "AND NOT" not in result.executed_query


@pytest.mark.unit
def test_translate_exclude_strip_comillas_internas() -> None:
    """Comillas embebidas en un término se eliminan para no romper la frase OpenAlex."""
    executed, _report = _translate("ecologia", exclude=['"machine learning"'])

    # El campo NO se repite: exactamente un "title_and_abstract.search:"
    assert executed.count("title_and_abstract.search:") == 1
    assert "AND NOT title_and_abstract.search:" not in executed
    # Las comillas del término se eliminaron; la frase externa queda bien formada
    assert 'AND NOT "machine learning"' in executed
    # No debe haber comilla suelta que cierre la frase antes de tiempo
    after_not = executed.split('AND NOT "')[1]
    assert after_not.startswith("machine learning")
    # La cláusula cierra con exactamente una comilla de cierre
    assert after_not.count('"') == 1  # solo la comilla de cierre


# ---------------------------------------------------------------------------
# #210 — 429 → NetworkError accionable (polite pool / email)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_seed_429_levanta_network_error_accionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un 429 persistente en seed() lanza NetworkError con mensaje accionable.

    Sin email declarado → pool anónimo → 429. Tras agotar los reintentos
    (#287 fricción #3), el error debe mencionar email y polite pool como
    remedio primario (no un HTTPStatusError pelado).
    Referencia: ADR 0012.
    """
    import bib2graph.sources.openalex as openalex_mod
    from bib2graph.service.errors import NetworkError

    monkeypatch.setattr(openalex_mod.time, "sleep", lambda _s: None)  # sin delays

    calls = 0

    def handler_429(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, text="Too Many Requests")

    transport = httpx.MockTransport(handler_429)
    source = OpenAlexSource(transport=transport)

    with pytest.raises(NetworkError) as exc_info:
        source.seed("ecological exchange")

    # Reintentó antes de rendirse (no falló a la primera).
    assert calls >= 2

    msg = str(exc_info.value)
    assert "429" in msg
    assert "email" in msg.lower()
    assert "polite" in msg.lower()
    assert "OPENALEX_API_KEY" in msg
    assert "ADR 0012" in msg
    assert "api_key" in msg  # la api_key se nombra como opcional en el mensaje


@pytest.mark.unit
def test_seed_429_transitorio_se_recupera_con_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#287 fricción #3: un 429 transitorio en seed() se reintenta y tiene éxito.

    El primer request devuelve 429; el segundo, 200. El agente NO tiene que
    detectar el 429, dormir y reintentar a mano: seed() lo hace solo.
    """
    import bib2graph.sources.openalex as openalex_mod

    monkeypatch.setattr(openalex_mod.time, "sleep", lambda _s: None)  # sin delays

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="Too Many Requests")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "doi": "https://doi.org/10.1/x",
                        "title": "Recovered paper",
                        "publication_year": 2021,
                    }
                ],
                "meta": {"next_cursor": None},
            },
            headers={"x-openalex-api-version": "test"},
        )

    transport = httpx.MockTransport(handler)
    source = OpenAlexSource(transport=transport)

    result = source.seed("ecological exchange")

    assert calls == 2  # 429 → reintento → 200
    assert len(result.corpus) == 1


@pytest.mark.unit
def test_translate_exclude_con_anio_forma_completa() -> None:
    """Con exclude + year, los NOT van dentro de search y el año va fuera con coma.

    Forma esperada:
        title_and_abstract.search:(query) AND NOT "t1" AND NOT "t2",
        from_publication_date:2020-01-01,to_publication_date:2024-12-31

    Los NOT están dentro de la expresión de search (un solo campo);
    los predicados de año se añaden fuera con coma (sintaxis idiomática OpenAlex).
    """
    query = "complejidad AND sistemas"
    executed, _report = _translate(
        query,
        exclude=["machine learning", "deep learning"],
        min_year=2020,
        max_year=2024,
    )

    # Exactamente un campo de búsqueda (no se repite)
    assert executed.count("title_and_abstract.search:") == 1
    assert "AND NOT title_and_abstract.search:" not in executed

    # Los NOT van dentro de la expresión (sin prefijo de campo)
    assert 'AND NOT "machine learning"' in executed
    assert 'AND NOT "deep learning"' in executed

    # El año va fuera de la expresión de search, separado por coma
    assert ",from_publication_date:2020-01-01" in executed
    assert ",to_publication_date:2024-12-31" in executed

    # La expresión de search precede a los predicados de año
    search_idx = executed.index("title_and_abstract.search:")
    from_idx = executed.index(",from_publication_date:")
    to_idx = executed.index(",to_publication_date:")
    assert search_idx < from_idx
    assert search_idx < to_idx
