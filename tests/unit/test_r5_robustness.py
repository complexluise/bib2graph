"""Tests TDD del Hito R5 — Robustez / escala.

Casos cubiertos (docs/ROADMAP.md §Hito R5):

1. UTF-8: envelope con acento se decodifica bien al forzar UTF-8 en stdout.
2. @handle_errors: un caso por exit code incluyendo el 4 (con assert) y el 5
   (sin rama muerta — el OSError directo produce exit 5).
3. .bib roto → warning accionable (no no-op silencioso).
4. Filtro con campo-op desconocido → ValueError (no no-op silencioso).
5. Retry de fetch_citing ante 429 sobre cliente mock.
6. Bulk-load: test de no-regresión (N papers → 1 construcción, no N clones).
7. Auto-creación del store en solo-lectura → StoreError accionable.
8. _lib_version fallback → 'unknown' (no '0.0.0').
9. cocitation_quality_report ya no acepta `g` como segundo argumento positivo.
10. except Exception en detect_communities eliminado → error real se propaga.
11. NetworkSpec.kind acepta NetworkKind (fuente única).

Marcador: ``unit`` (sin red real, sin DuckDB de producción).
"""

from __future__ import annotations

import io
import json
import sys
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from bib2graph.sources.openalex import OpenAlexSource

# ---------------------------------------------------------------------------
# Fixtures de datos
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
_SAMPLE_WORKS: list[dict[str, Any]] = json.loads(
    (_FIXTURES_DIR / "sample_works.json").read_text(encoding="utf-8")
)

# ---------------------------------------------------------------------------
# Helpers internos compartidos
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *, id: str, title: str = "Test", curation_status: str = "candidate"
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
    return {
        "id": id,
        "openalex_id": None,
        "doi": None,
        "title": title,
        "year": 2020,
        "abstract": None,
        "source": None,
        "language": "en",
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


# ===========================================================================
# 1. UTF-8 en la frontera CLI
# ===========================================================================


@pytest.mark.unit
def test_force_utf8_reconfigura_stdout() -> None:
    """_force_utf8 intenta reconfigure(encoding='utf-8') en stdout/stderr.

    En un entorno normal (pytest), stdout ya es UTF-8 o TextIOWrapper con
    reconfigure disponible.  El test verifica que la función no lanza y que
    el encoding resultante es 'utf-8'.
    """
    from bib2graph.cli import _force_utf8

    _force_utf8()
    # Tras llamar, stdout debe ser UTF-8 (en pytest ya lo es, pero la función
    # no debe romper en ningún entorno).
    encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    assert encoding.lower().replace("-", "") in ("utf8", "utf-8")


@pytest.mark.unit
def test_envelope_con_acento_decodifica_bien() -> None:
    """El envelope JSON con acentos se puede decodificar desde bytes UTF-8.

    Simula la situación de Windows: el envelope se escribe a un stream UTF-8
    y se lee como bytes.  Con ensure_ascii=False y encoding=UTF-8 los acentos
    sobreviven el round-trip.

    R5 (Nota 06, RAÍZ 3): sin forzar UTF-8, en cp1252 el 'ó' de 'ecuación'
    se corrompe.
    """
    from bib2graph.cli._envelope import build_envelope

    envelope = build_envelope(
        command="seed",
        ok=True,
        data={"executed_query": "ecuación"},
        exit_code=0,
    )

    # Simular escritura a bytes UTF-8 (como haría el stream forzado)
    encoded = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    decoded = json.loads(encoded.decode("utf-8"))

    assert decoded["data"]["executed_query"] == "ecuación"


@pytest.mark.unit
def test_force_utf8_no_falla_en_stream_sin_reconfigure() -> None:
    """_force_utf8 no lanza si el stream no tiene reconfigure (guarda)."""
    from bib2graph.cli import _force_utf8

    # Crear un stream sin método reconfigure
    fake_stream = io.BytesIO()
    assert not hasattr(fake_stream, "reconfigure")

    with (
        patch.object(sys, "stdout", fake_stream),
        patch.object(sys, "stderr", fake_stream),
    ):
        # No debe lanzar, solo pasar silenciosamente
        _force_utf8()


# ===========================================================================
# 2. @handle_errors: exit codes 4 y 5 (footgun OSError muerto cerrado)
# ===========================================================================


@pytest.mark.unit
def test_handle_errors_exit_4_httpx_status_error() -> None:
    """httpx.HTTPStatusError (subclase de HTTPError) → exit 4.

    R5: exit_code 4 ahora tiene assert (antes sin assert en la suite).
    """
    from bib2graph.cli._errors import handle_errors

    @handle_errors("test_cmd")
    def fn_que_lanza_http_error() -> None:
        response = MagicMock()
        response.status_code = 503
        raise httpx.HTTPStatusError("503", request=MagicMock(), response=response)

    with pytest.raises(SystemExit) as exc_info:
        fn_que_lanza_http_error()

    assert exc_info.value.code == 4


@pytest.mark.unit
def test_handle_errors_exit_5_oserror_directo() -> None:
    """OSError directo (no StoreLockedError) → exit 5.

    R5: verifica que la rama muerta fue eliminada — solo hay un camino para
    OSError y produce exit 5 sin bifurcación innecesaria.
    """
    from bib2graph.cli._errors import handle_errors

    @handle_errors("test_cmd")
    def fn_que_lanza_oserror() -> None:
        raise OSError("Disco lleno")

    with pytest.raises(SystemExit) as exc_info:
        fn_que_lanza_oserror()

    assert exc_info.value.code == 5


@pytest.mark.unit
def test_handle_errors_exit_5_store_locked() -> None:
    """StoreLockedError (subclase OSError) → exit 5 (caso real)."""
    from bib2graph.backends.duckdb import StoreLockedError
    from bib2graph.cli._errors import handle_errors

    @handle_errors("test_cmd")
    def fn_que_lanza_store_locked() -> None:
        raise StoreLockedError("Archivo bloqueado")

    with pytest.raises(SystemExit) as exc_info:
        fn_que_lanza_store_locked()

    assert exc_info.value.code == 5


@pytest.mark.unit
def test_handle_errors_attribute_error_no_disfrazado() -> None:
    """AttributeError genuino NO se captura como exit 3 (R5).

    Un bug real en el código (AttributeError inesperado) debe propagarse
    limpio, no disfrazarse de 'Capacidad no disponible'.
    """
    from bib2graph.cli._errors import handle_errors

    @handle_errors("test_cmd")
    def fn_con_bug_real() -> None:
        # Simula un AttributeError inesperado (bug en el código, no dependencia)
        obj: Any = None
        obj.metodo_que_no_existe()  # type: ignore[union-attr]

    # R5: AttributeError ya NO se captura → se propaga como AttributeError real
    with pytest.raises(AttributeError):
        fn_con_bug_real()


# ===========================================================================
# 3. .bib roto → warning accionable
# ===========================================================================


@pytest.mark.unit
def test_bibtex_load_archivo_vacio_emite_warning(tmp_path: Path) -> None:
    """.bib vacío → UserWarning accionable (no no-op silencioso).

    R5 (Nota 06, catálogo de secundarios): antes un .bib roto se tragaba
    sin advertencia.
    """
    from bib2graph.sources.bibtex import BibtexSource

    bib_vacio = tmp_path / "vacio.bib"
    bib_vacio.write_text("", encoding="utf-8")

    source = BibtexSource()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        corpus = source.load(str(bib_vacio))

    assert len(corpus) == 0
    # Debe haber un warning sobre el archivo vacío
    mensajes = [str(warning.message) for warning in w]
    assert any("vacio.bib" in m or "vacío" in m or "válidas" in m for m in mensajes), (
        f"Se esperaba warning sobre archivo vacío, mensajes obtenidos: {mensajes}"
    )


@pytest.mark.unit
def test_bibtex_load_entradas_sin_titulo_emite_warning(tmp_path: Path) -> None:
    """.bib con entradas sin título → warning con conteo omitidos.

    R5: el silencio anterior ocultaba que se saltaron entradas.
    """
    from bib2graph.sources.bibtex import BibtexSource

    bib_sin_titulo = tmp_path / "sin_titulo.bib"
    # Entrada sin campo 'title' (la clave de la entrada está, pero no el título)
    bib_sin_titulo.write_text(
        "@article{ref1, author = {Autor, Juan}, year = {2020}}\n",
        encoding="utf-8",
    )

    source = BibtexSource()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        corpus = source.load(str(bib_sin_titulo))

    assert len(corpus) == 0
    mensajes = [str(warning.message) for warning in w]
    assert any("omitieron" in m or "título" in m or "title" in m for m in mensajes), (
        f"Se esperaba warning sobre entradas omitidas, mensajes: {mensajes}"
    )


# ===========================================================================
# 4. Filtros PRISMA con campo-op desconocido → ValueError (no no-op)
# ===========================================================================


@pytest.mark.unit
def test_filter_campo_desconocido_lanza_value_error() -> None:
    """_passes con campo desconocido lanza ValueError (no no-op silencioso).

    R5 (Nota 06, catálogo de secundarios): prisma.py:115 devolvía True
    silenciosamente para campos desconocidos.
    """
    # Usamos la clase directamente en vez del Corpus para probar _passes
    # sin estado.  FilterCriterion no permite 'campo_raro' como Literal, así
    # que la instanciamos vía model_construct para evadir la validación Pydantic.
    from bib2graph.filters.prisma import FilterCriterion, _passes

    # Construir con model_construct para evadir la validación Pydantic
    criterion = FilterCriterion.model_construct(
        field="campo_raro",  # type: ignore[arg-type]
        op="gte",
        value=5,
    )

    row: dict[str, Any] = {"year": 2020}

    with pytest.raises(ValueError, match="campo_raro"):
        _passes(row, criterion)


@pytest.mark.unit
def test_filter_operador_invalido_para_campo_year_lanza_value_error() -> None:
    """_passes con operador inválido para 'year' lanza ValueError.

    R5: antes el default era ``return True`` (pasar el filtro silenciosamente).
    """
    from bib2graph.filters.prisma import FilterCriterion, _passes

    # 'eq' no es un operador válido para 'year' (solo gte/lte)
    criterion = FilterCriterion.model_construct(
        field="year",
        op="eq",  # type: ignore[arg-type]
        value=2020,
    )

    row: dict[str, Any] = {"year": 2020}

    with pytest.raises(ValueError, match="year"):
        _passes(row, criterion)


# ===========================================================================
# 5. Retry de fetch_citing ante 429 sobre cliente mock
# ===========================================================================


@pytest.mark.unit
def test_fetch_citing_retry_ante_429_luego_200() -> None:
    """fetch_citing reintenta ante 429 y devuelve el paper (no lo pierde).

    R5 (Nota 06, RAÍZ 3): sin retry, el forward chaining pierde papers ante
    rate-limit de OpenAlex.  Este test verifica que:
    - Un 429 seguido de 200 → el paper llega al resultado.
    - time.sleep se llama con el backoff esperado.
    """
    calls: list[int] = [0]

    def handler_429_luego_200(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        if calls[0] == 1:
            # Primera llamada: 429 Too Many Requests
            return httpx.Response(429, text="Rate limit exceeded")
        # Segunda llamada: 200 con un work
        body = {
            "results": [_SAMPLE_WORKS[0]],
            "meta": {"count": 1, "next_cursor": None},
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler_429_luego_200)
    source = OpenAlexSource(transport=transport)

    with patch("bib2graph.sources.openalex.time.sleep") as mock_sleep:
        rows = source.fetch_citing("W12345")

    # No pierde el paper
    assert len(rows) >= 1
    # Se durmió al menos una vez (backoff)
    assert mock_sleep.called
    assert calls[0] == 2  # primer intento (429) + segundo intento (200)


@pytest.mark.unit
def test_fetch_citing_retry_agotado_lanza_error() -> None:
    """fetch_citing lanza NetworkError si se agotan los reintentos con 429.

    R5 / #210: con 3 intentos de 429 consecutivos, la excepción se convierte
    a NetworkError accionable (no HTTPStatusError pelado).
    """
    from bib2graph.service.errors import NetworkError

    calls: list[int] = [0]

    def handler_siempre_429(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(429, text="Rate limit exceeded")

    transport = httpx.MockTransport(handler_siempre_429)
    source = OpenAlexSource(transport=transport)

    with (
        patch("bib2graph.sources.openalex.time.sleep"),
        pytest.raises(NetworkError) as exc_info,
    ):
        source.fetch_citing("W12345")

    msg = str(exc_info.value)
    assert "429" in msg
    assert "polite" in msg.lower()
    # Se intentó _RETRY_MAX_ATTEMPTS veces (cada intento = al menos 1 HTTP)
    assert calls[0] >= 1


@pytest.mark.unit
def test_fetch_citing_no_retry_ante_404() -> None:
    """fetch_citing NO reintenta ante 404 (no es un status retryable).

    R5: solo 429/5xx entran en el retry; 404 se propaga inmediatamente.
    """
    calls: list[int] = [0]

    def handler_404(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(404, text="Not found")

    transport = httpx.MockTransport(handler_404)
    source = OpenAlexSource(transport=transport)

    with (
        patch("bib2graph.sources.openalex.time.sleep") as mock_sleep,
        pytest.raises(httpx.HTTPStatusError),
    ):
        source.fetch_citing("W12345")

    # No reintentó — solo 1 llamada
    assert calls[0] == 1
    assert not mock_sleep.called


@pytest.mark.unit
def test_fetch_citing_429_levanta_network_error_accionable() -> None:
    """fetch_citing con 429 agotado lanza NetworkError con mensaje completo.

    #210: el path de chaining (_fetch_all_with_retry) convierte 429
    agotado en NetworkError con mensaje que menciona email, polite-pool,
    ADR 0012 y api_key como opcional. Sin red real (MockTransport).
    """
    from bib2graph.service.errors import NetworkError

    def handler_siempre_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    transport = httpx.MockTransport(handler_siempre_429)
    source = OpenAlexSource(transport=transport)

    with (
        patch("bib2graph.sources.openalex.time.sleep"),
        pytest.raises(NetworkError) as exc_info,
    ):
        source.fetch_citing("W99999")

    msg = str(exc_info.value)
    assert "email" in msg.lower()
    assert "polite" in msg.lower()
    assert "ADR 0012" in msg
    assert "api_key" in msg  # la api_key se nombra como opcional en el mensaje


# ===========================================================================
# 6. Bulk-load: test de no-regresión
# ===========================================================================


@pytest.mark.unit
def test_bulk_load_bibtex_no_llama_add_paper(tmp_path: Path) -> None:
    """BibtexSource.load usa bulk from_arrow, no add_paper iterativo.

    R5: verifica que N papers generan 1 construcción de Corpus (from_arrow),
    no N clones vía add_paper.
    """
    from bib2graph.sources.bibtex import BibtexSource

    bib_path = tmp_path / "multi.bib"
    bib_path.write_text(
        """
@article{ref1,
  author = {Autor Uno},
  title = {Paper Uno},
  year = {2020},
  journal = {Journal A}
}
@article{ref2,
  author = {Autor Dos},
  title = {Paper Dos},
  year = {2021},
  journal = {Journal B}
}
@article{ref3,
  author = {Autor Tres},
  title = {Paper Tres},
  year = {2022},
  journal = {Journal C}
}
""",
        encoding="utf-8",
    )

    source = BibtexSource()

    with patch("bib2graph.corpus.Corpus.add_paper") as mock_add:
        corpus = source.load(str(bib_path))

    # add_paper NO se llama (bulk-load usa from_arrow directamente)
    assert not mock_add.called, (
        f"Se esperaba bulk-load sin add_paper, pero add_paper se llamó "
        f"{mock_add.call_count} veces"
    )
    assert len(corpus) == 3


@pytest.mark.unit
def test_bulk_load_openalex_seed_no_llama_add_paper() -> None:
    """OpenAlexSource.seed usa bulk from_arrow, no add_paper iterativo.

    R5: verifica que N works generan 1 construcción, no N clones.
    """
    calls: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        body = {
            "results": _SAMPLE_WORKS[:3],
            "meta": {"count": 3, "next_cursor": None},
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    source = OpenAlexSource(transport=transport)

    with patch("bib2graph.corpus.Corpus.add_paper") as mock_add:
        result = source.seed("test query")

    assert not mock_add.called, (
        f"Se esperaba bulk-load sin add_paper, pero se llamó {mock_add.call_count} veces"
    )
    assert len(result.corpus) == 3


# ===========================================================================
# 7. Auto-creación del store en solo-lectura → StoreError accionable
# ===========================================================================


@pytest.mark.unit
def test_status_store_inexistente_lanza_store_error(tmp_path: Path) -> None:
    """run_status con store inexistente → StoreError accionable (no auto-crea).

    R5 (Nota 06, catálogo de secundarios): antes status/validate creaban el
    store silenciosamente ante un typo en --store.
    """
    from bib2graph.cli._errors import StoreError
    from bib2graph.cli.commands.status import run_status

    ruta_inexistente = tmp_path / "no_existe.duckdb"
    assert not ruta_inexistente.exists()

    with pytest.raises(StoreError) as exc_info:
        run_status(ruta_inexistente)

    assert "no existe" in str(exc_info.value).lower() or "no_existe" in str(
        exc_info.value
    )
    # Verificar que NO se creó el archivo
    assert not ruta_inexistente.exists()


@pytest.mark.unit
def test_validate_store_inexistente_lanza_store_error(tmp_path: Path) -> None:
    """run_validate con store inexistente → StoreError accionable (no auto-crea).

    R5: mismo footgun que status.
    """
    from bib2graph.cli._errors import StoreError
    from bib2graph.cli.commands.validate import run_validate

    ruta_inexistente = tmp_path / "phantom.duckdb"
    assert not ruta_inexistente.exists()

    with pytest.raises(StoreError):
        run_validate(ruta_inexistente)

    assert not ruta_inexistente.exists()


# ===========================================================================
# 8. _lib_version fallback → 'unknown' (no '0.0.0')
# ===========================================================================


@pytest.mark.unit
def test_lib_version_fallback_es_unknown() -> None:
    """_lib_version retorna 'unknown' cuando falla importlib.metadata.

    R5 (Nota 06, catálogo de secundarios): antes retornaba '0.0.0' (versión
    inventada que engaña sobre la reproducibilidad del Manifest).
    """
    import importlib.metadata as _meta

    import bib2graph.corpus as corpus_module

    # Patchear importlib.metadata.version (que ahora se accede como _meta.version)
    with patch.object(_meta, "version", side_effect=Exception("no instalado")):
        result = corpus_module._lib_version()

    assert result == "unknown", f"Se esperaba 'unknown', obtuvo '{result}'"
    assert result != "0.0.0"


# ===========================================================================
# 9. cocitation_quality_report sin parámetro g
# ===========================================================================


@pytest.mark.unit
def test_cocitation_quality_report_sin_param_g() -> None:
    """cocitation_quality_report ya no acepta 'g' como segundo arg posicional.

    R5: el parámetro muerto 'g' fue eliminado (Nota 06, catálogo secundarios).
    """
    import inspect

    from bib2graph.networks.analyzer import cocitation_quality_report

    sig = inspect.signature(cocitation_quality_report)
    param_names = list(sig.parameters.keys())

    assert "g" not in param_names, (
        f"El param muerto 'g' sigue en la firma: {param_names}"
    )
    assert "corpus" in param_names
    assert "thresholds" in param_names


# ===========================================================================
# 10. except Exception en detect_communities eliminado
# ===========================================================================


@pytest.mark.unit
def test_detect_communities_error_real_se_propaga() -> None:
    """Errores reales en detect_communities se propagan (no quedan enmascarados).

    R5 (Nota 06, catálogo de secundarios): el ``except Exception`` de
    ``facade.py`` tragaba errores no-ImportError y los convertía en
    ``communities=None`` silenciosamente.

    Ahora un grafo con método inválido lanza ValueError que se propaga.
    """
    import networkx as nx

    from bib2graph.networks.analyzer import detect_communities

    g = nx.Graph()
    g.add_edge("A", "B")

    with pytest.raises(ValueError, match=r"no reconocido|not recognized"):
        detect_communities(g, method="metodo_inexistente")


@pytest.mark.unit
def test_build_artifact_propaga_error_de_comunidades() -> None:
    """_build_artifact propaga errores de detect_communities (no los traga).

    R5: el ``except Exception`` de facade.py fue eliminado.  Un RuntimeError
    en detect_communities se propaga, no queda silenciado como
    ``communities=None``.

    Estrategia: patchear el método ``number_of_nodes`` del grafo proyectado
    para retornar 1 (haciendo que la rama de clustering se ejecute) y
    luego patchear ``detect_communities`` para lanzar RuntimeError.
    """
    import networkx as nx
    import pyarrow as pa

    from bib2graph.corpus import Corpus
    from bib2graph.networks.facade import _build_artifact
    from bib2graph.networks.spec import NetworkSpec
    from bib2graph.schemas import CORPUS_SCHEMA

    rows = [
        _make_corpus_row(id="P1", title="Paper 1"),
        _make_corpus_row(id="P2", title="Paper 2"),
    ]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)

    spec = NetworkSpec(
        kind="bibliographic_coupling",
        clustering="louvain",
    )

    # Construir un grafo no vacío para que la rama de clustering se ejecute.
    # Patcheamos el proyector para devolver un grafo con nodos.
    fake_graph = nx.Graph()
    fake_graph.add_edge("A", "B")

    # R5: RuntimeError en detect_communities se propaga (no queda en silence).
    with (
        patch(
            "bib2graph.networks.facade._projector_for_kind",
            return_value=MagicMock(project=MagicMock(return_value=fake_graph)),
        ),
        patch(
            "bib2graph.networks.facade.detect_communities",
            side_effect=RuntimeError("Error inesperado en clustering"),
        ),
        pytest.raises(RuntimeError, match="inesperado"),
    ):
        _build_artifact(corpus, spec)


# ===========================================================================
# 11. NetworkSpec.kind acepta NetworkKind (fuente única)
# ===========================================================================


@pytest.mark.unit
def test_network_spec_acepta_network_kind() -> None:
    """NetworkSpec.kind acepta NetworkKind directamente (fuente única, R5).

    R5: NetworkSpec.kind ahora es de tipo NetworkKind, no un Literal duplicado.
    """
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.spec import NetworkSpec

    spec = NetworkSpec(kind=NetworkKind.BIBLIOGRAPHIC_COUPLING)
    assert spec.kind == NetworkKind.BIBLIOGRAPHIC_COUPLING
    assert spec.kind == "bibliographic_coupling"  # StrEnum → comparación con str


@pytest.mark.unit
def test_network_spec_acepta_string_de_kind() -> None:
    """NetworkSpec.kind acepta el string correspondiente al NetworkKind (Pydantic coerce)."""
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.spec import NetworkSpec

    # Pydantic con StrEnum coerce automáticamente el string al enum
    spec = NetworkSpec(kind="author_collab")  # type: ignore[arg-type]
    assert spec.kind == NetworkKind.AUTHOR_COLLAB


@pytest.mark.unit
def test_quick_kinds_son_instancias_de_network_kind() -> None:
    """_QUICK_KINDS contiene valores de NetworkKind (fuente única verificada)."""
    from bib2graph.constants import NetworkKind
    from bib2graph.networks.facade import _QUICK_KINDS

    for kind in _QUICK_KINDS:
        assert isinstance(kind, NetworkKind), (
            f"_QUICK_KINDS contiene '{kind}' que no es NetworkKind"
        )

    # La co-citación no debe estar en quick (requiere 2º nivel de fetch)
    assert NetworkKind.COCITATION not in _QUICK_KINDS
