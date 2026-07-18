"""Tests unitarios para la resolución DOI→source_id (ADR 0035).

Cubre:
1. ``fetch_dois_to_openalex_ids``: mock devuelve works → dict correcto;
   DOI inexistente → ausente; normalización de DOI (URL → bare).
2. ``service.resolve.resolve_dois``: corpus con doi+source_id=NULL →
   tras resolver, source_id poblado (W…); papers sin DOI intactos;
   idempotente (re-ejecutar no cambia nada).
3. CLI ``seed --from-bib <bib> --resolve --email …``: envelope JSON correcto
   (ruta única de resolución DOI→OpenAlex desde 0.12.0, #207 — el verbo
   suelto ``b2g resolve`` fue retirado).
4. CLI ``seed --from-bib <bib> --resolve --email …``: carga + resuelve en
   un paso, envelope incluye sub-dict ``resolve``.
5. Integración acotada: from-bib → resolve → corpus tiene source_id poblado
   (demuestra que se cierra el GAP-1 sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pytest

from bib2graph.constants import Col
from bib2graph.corpus import Corpus
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.sources.openalex import OpenAlexSource

# ---------------------------------------------------------------------------
# Helpers de mock HTTP
# ---------------------------------------------------------------------------


def _make_doi_resolve_handler(
    works: list[dict[str, Any]],
) -> httpx.MockTransport:
    """MockTransport que devuelve works al filtrar por DOI.

    Responde siempre con la lista completa de works (sin paginación).
    """

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "results": works,
            "meta": {"count": len(works), "next_cursor": None},
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_empty_handler() -> httpx.MockTransport:
    """MockTransport que devuelve siempre una página vacía."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {"results": [], "meta": {"count": 0, "next_cursor": None}}
        return httpx.Response(
            200,
            json=body,
            headers={"x-openalex-api-version": "2026-05-01"},
        )

    return httpx.MockTransport(handler)


def _make_corpus_with_dois(
    dois: list[str | None],
    source_ids: list[str | None],
) -> Corpus:
    """Construye un Corpus mínimo con las columnas doi y source_id dadas."""
    rows = []
    for i, (doi, sid) in enumerate(zip(dois, source_ids, strict=True)):
        row: dict[str, Any] = {
            Col.ID: f"tt:{i:04d}abcdef012345",
            Col.SOURCE_ID: sid,
            Col.DOI: doi,
            Col.TITLE: f"Paper {i}",
            Col.YEAR: 2020 + i,
            Col.ABSTRACT: None,
            Col.SOURCE: None,
            Col.LANGUAGE: None,
            Col.PUBLISHER: None,
            Col.RESEARCH_AREAS: [],
            Col.IS_SEED: True,
            Col.CURATION_STATUS: "candidate",
            Col.PROVENANCE: None,
            Col.AUTHORS_RAW: [],
            Col.AUTHORS_ID: [],
            Col.AUTHORS_AFFILIATIONS: [],
            Col.KEYWORDS_RAW: [],
            Col.KEYWORDS_ID: [],
            Col.INSTITUTIONS_RAW: [],
            Col.INSTITUTIONS_ID: [],
            Col.REFERENCES_ID: [],
            Col.REFERENCES_DOI: [],
            Col.CITED_BY_ID: [],
        }
        rows.append(row)
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    return Corpus.from_arrow(table)


# ---------------------------------------------------------------------------
# 1. fetch_dois_to_openalex_ids
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fetch_dois_to_openalex_ids_devuelve_dict_correcto() -> None:
    """DOIs presentes en OpenAlex → dict {doi_normalizado: source_id_corto}."""
    works = [
        {"id": "https://openalex.org/W111", "doi": "https://doi.org/10.1234/abc"},
        {"id": "https://openalex.org/W222", "doi": "https://doi.org/10.5678/def"},
    ]
    transport = _make_doi_resolve_handler(works)
    source = OpenAlexSource(transport=transport)

    result = source.fetch_dois_to_openalex_ids(["10.1234/abc", "10.5678/def"])

    assert result["10.1234/abc"] == "W111"
    assert result["10.5678/def"] == "W222"


@pytest.mark.unit
def test_fetch_dois_to_openalex_ids_doi_inexistente_ausente() -> None:
    """DOI no encontrado en OpenAlex simplemente no aparece en el dict."""
    # Solo devuelve un work
    works = [
        {"id": "https://openalex.org/W111", "doi": "https://doi.org/10.1234/abc"},
    ]
    transport = _make_doi_resolve_handler(works)
    source = OpenAlexSource(transport=transport)

    result = source.fetch_dois_to_openalex_ids(["10.1234/abc", "10.9999/inexistente"])

    assert "10.1234/abc" in result
    assert "10.9999/inexistente" not in result


@pytest.mark.unit
def test_fetch_dois_to_openalex_ids_normaliza_doi_con_prefijo_url() -> None:
    """DOI con prefijo URL se normaliza correctamente antes de buscar."""
    works = [
        {"id": "https://openalex.org/W333", "doi": "https://doi.org/10.9999/xyz"},
    ]
    transport = _make_doi_resolve_handler(works)
    source = OpenAlexSource(transport=transport)

    # Pasamos el DOI con prefijo URL completo
    result = source.fetch_dois_to_openalex_ids(["https://doi.org/10.9999/xyz"])

    # La clave en el resultado debe estar normalizada (sin prefijo, minúsculas)
    assert "10.9999/xyz" in result
    assert result["10.9999/xyz"] == "W333"


@pytest.mark.unit
def test_fetch_dois_to_openalex_ids_lista_vacia_devuelve_dict_vacio() -> None:
    """Lista vacía de DOIs → dict vacío sin hacer ninguna request."""
    source = OpenAlexSource()  # sin transport; no debería hacer request

    result = source.fetch_dois_to_openalex_ids([])

    assert result == {}


@pytest.mark.unit
def test_fetch_dois_to_openalex_ids_normaliza_mayusculas() -> None:
    """DOI en mayúsculas se normaliza a minúsculas."""
    works = [
        {"id": "https://openalex.org/W444", "doi": "https://doi.org/10.ABC/TEST"},
    ]
    transport = _make_doi_resolve_handler(works)
    source = OpenAlexSource(transport=transport)

    result = source.fetch_dois_to_openalex_ids(["10.ABC/TEST"])

    # La clave resultante debería estar normalizada a minúsculas
    assert "10.abc/test" in result


# ---------------------------------------------------------------------------
# 2. service.resolve.resolve_dois — con store temporal
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_dois_puebla_source_id(tmp_path: Path) -> None:
    """Papers con doi+source_id=NULL → tras resolve, source_id populado."""
    from bib2graph.service.resolve import resolve_dois
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "test.duckdb"

    # Crear corpus con doi pero sin source_id
    corpus = _make_corpus_with_dois(
        dois=["10.1234/abc"],
        source_ids=[None],
    )
    store = DuckDBStore(db_path)
    store.persist_replace(corpus)
    store.close()

    # Mock: OpenAlex devuelve el source_id para el DOI
    works = [
        {"id": "https://openalex.org/W999", "doi": "https://doi.org/10.1234/abc"},
    ]
    transport = _make_doi_resolve_handler(works)

    result = resolve_dois(db_path, transport=transport)

    assert result["resolved"] == 1
    assert result["total_with_doi"] == 1
    assert result["already_resolved"] == 0
    assert result["total_papers"] == 1

    # Verificar que el corpus tiene el source_id actualizado
    store2 = DuckDBStore(db_path)
    loaded = store2.load()
    rows = loaded.to_arrow().to_pylist()
    store2.close()
    assert rows[0][Col.SOURCE_ID] == "W999"


@pytest.mark.unit
def test_resolve_dois_papers_sin_doi_no_se_tocan(tmp_path: Path) -> None:
    """Papers sin DOI quedan intactos (source_id=NULL permanece NULL)."""
    from bib2graph.service.resolve import resolve_dois
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "test.duckdb"

    corpus = _make_corpus_with_dois(
        dois=[None, "10.1234/abc"],
        source_ids=[None, None],
    )
    store = DuckDBStore(db_path)
    store.persist_replace(corpus)
    store.close()

    works = [
        {"id": "https://openalex.org/W111", "doi": "https://doi.org/10.1234/abc"},
    ]
    transport = _make_doi_resolve_handler(works)

    result = resolve_dois(db_path, transport=transport)

    assert result["resolved"] == 1
    assert result["total_with_doi"] == 1
    assert result["total_papers"] == 2

    store2 = DuckDBStore(db_path)
    loaded = store2.load()
    rows = loaded.to_arrow().to_pylist()
    store2.close()
    # El paper sin DOI sigue sin source_id
    sin_doi = next(r for r in rows if r[Col.DOI] is None)
    assert sin_doi[Col.SOURCE_ID] is None
    # El paper con DOI tiene source_id ahora
    con_doi = next(r for r in rows if r[Col.DOI] is not None)
    assert con_doi[Col.SOURCE_ID] == "W111"


@pytest.mark.unit
def test_resolve_dois_idempotente(tmp_path: Path) -> None:
    """Re-ejecutar resolve no duplica ni altera los source_id ya poblados."""
    from bib2graph.service.resolve import resolve_dois
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "test.duckdb"

    # Corpus: un paper con doi, sin source_id
    corpus = _make_corpus_with_dois(
        dois=["10.1234/abc"],
        source_ids=[None],
    )
    store = DuckDBStore(db_path)
    store.persist_replace(corpus)
    store.close()

    works = [
        {"id": "https://openalex.org/W555", "doi": "https://doi.org/10.1234/abc"},
    ]

    # Primera corrida
    result1 = resolve_dois(db_path, transport=_make_doi_resolve_handler(works))
    assert result1["resolved"] == 1

    # Segunda corrida: el paper ya tiene source_id → no se resuelve de nuevo
    result2 = resolve_dois(db_path, transport=_make_doi_resolve_handler(works))
    assert result2["resolved"] == 0
    assert result2["already_resolved"] == 1

    # El source_id sigue siendo el mismo
    store2 = DuckDBStore(db_path)
    loaded = store2.load()
    rows = loaded.to_arrow().to_pylist()
    store2.close()
    assert rows[0][Col.SOURCE_ID] == "W555"


@pytest.mark.unit
def test_resolve_dois_corpus_sin_papers_con_doi(tmp_path: Path) -> None:
    """Corpus sin ningún DOI → resolve devuelve 0 sin llamar a OpenAlex."""
    from bib2graph.service.resolve import resolve_dois
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "test.duckdb"

    corpus = _make_corpus_with_dois(dois=[None, None], source_ids=[None, None])
    store = DuckDBStore(db_path)
    store.persist_replace(corpus)
    store.close()

    # No pasamos transport: si hace request, fallará
    result = resolve_dois(db_path)

    assert result["resolved"] == 0
    assert result["total_with_doi"] == 0
    assert result["total_papers"] == 2


# ---------------------------------------------------------------------------
# 3. run_seed_from_bib(resolve=True) — ruta única de resolución (seed --resolve)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_seed_from_bib_resolve_envelope_shape(tmp_path: Path) -> None:
    """run_seed_from_bib(resolve=True) devuelve el sub-dict 'resolve' con forma estable.

    El CLI ``b2g seed --from-bib --resolve`` no acepta inyección de transport;
    se ejerce la función núcleo directamente (misma ruta de código que el CLI,
    sin la capa Click) con MockTransport — patrón usado en el resto del módulo.
    """
    from bib2graph.cli.commands.seed import run_seed_from_bib

    bib_content = """@article{test2024,
  title = {Test Article},
  author = {Smith, John},
  year = {2024},
  doi = {10.1234/abc},
  journal = {Test Journal}
}
"""
    bib_path = tmp_path / "test.bib"
    bib_path.write_text(bib_content, encoding="utf-8")

    works = [
        {"id": "https://openalex.org/W999", "doi": "https://doi.org/10.1234/abc"},
    ]
    transport = _make_doi_resolve_handler(works)

    db_path = tmp_path / "test.duckdb"
    data = run_seed_from_bib(db_path, bib_path, resolve=True, transport=transport)

    assert "resolve" in data
    r = data["resolve"]
    assert "resolved" in r
    assert "total_with_doi" in r
    assert "total_papers" in r
    assert r["resolved"] == 1


# ---------------------------------------------------------------------------
# 4. CLI seed --from-bib --resolve
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_seed_from_bib_resolve_envelope(tmp_path: Path) -> None:
    """seed --from-bib --resolve --json emite envelope con sub-dict resolve.

    Usa DuckDB real + httpx.MockTransport: no mockea resolve_dois ni
    _resolve_dois_on_store.  Verifica que el encadenado seed→resolve en el
    mismo proceso NO crashea (era el bug #110) y que el envelope JSON tiene
    el sub-dict ``resolve`` con source_id poblado.
    """
    from click.testing import CliRunner

    from bib2graph.cli import b2g

    # Crear workspace mínimo
    ws_path = tmp_path
    (ws_path / "workspace.json").write_text(
        json.dumps(
            {
                "name": "test",
                "version": "1",
                "created_at": "2026-01-01T00:00:00",
                "bib2graph_version": "test",
            }
        )
    )

    # Crear un .bib mínimo con un DOI conocido
    bib_content = """@article{test2024,
  title = {Test Article},
  author = {Smith, John},
  year = {2024},
  doi = {10.1234/test},
  journal = {Test Journal}
}
"""
    bib_path = tmp_path / "test.bib"
    bib_path.write_text(bib_content, encoding="utf-8")

    # MockTransport que responde con un work para el DOI del paper cargado
    works_mock = [
        {"id": "https://openalex.org/W7777", "doi": "https://doi.org/10.1234/test"},
    ]
    transport = _make_doi_resolve_handler(works_mock)

    # El CLI no acepta inyección de transport directamente; invocamos la
    # función núcleo run_seed_from_bib que sí lo acepta, exactamente como lo
    # haría el CLI (misma ruta de código, sin la capa Click).
    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = ws_path / "library.duckdb"
    seed_data = run_seed_from_bib(
        db_path,
        bib_path,
        resolve=True,
        email="test@example.com",
        transport=transport,
    )

    # El comando no crasheó → assert básico de integridad
    assert seed_data["papers_added"] == 1
    assert seed_data["total_papers"] >= 1
    assert "resolve" in seed_data
    r = seed_data["resolve"]
    assert r["resolved"] == 1
    assert r["total_with_doi"] == 1

    # Verificar en DuckDB real que source_id quedó poblado
    store_check = DuckDBStore(db_path)
    loaded = store_check.load()
    rows = loaded.to_arrow().to_pylist()
    store_check.close()
    con_doi = next(row for row in rows if row.get(Col.DOI))
    assert con_doi[Col.SOURCE_ID] == "W7777"

    # Test CLI envelope para verificar la salida estructurada de 'seed --resolve'
    # (ruta única de resolución DOI→OpenAlex desde 0.12.0, #207: el CLI no
    # inyecta transport, así que ejercemos un .bib con DOI ya sin nada pendiente
    # de resolver — no dispara red — para verificar solo la forma del envelope).
    runner = CliRunner()
    bib_sin_doi = tmp_path / "sin_doi.bib"
    bib_sin_doi.write_text(
        """@article{nodoi2024,
  title = {Sin DOI},
  author = {Doe, Jane},
  year = {2024},
  journal = {Test Journal}
}
""",
        encoding="utf-8",
    )
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws_path),
            "seed",
            "--from-bib",
            str(bib_sin_doi),
            "--resolve",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "seed"
    assert "resolve" in data["data"]
    assert "resolved" in data["data"]["resolve"]


# ---------------------------------------------------------------------------
# 5. Integración real: from-bib → resolve → source_id poblado (DuckDB real)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_integracion_from_bib_resolve_cierra_gap1(tmp_path: Path) -> None:
    """seed --from-bib --resolve con DuckDB real y red mockeada: no crashea.

    Demuestra el cierre del GAP-1 (ADR 0035) Y la corrección del bug #110:
    el encadenado seed→resolve en el mismo proceso dejaba de usar el store
    abierto y lo reabría, corrompiendo las UDFs de DuckDB → segfault.

    Este test FALLABA con el código previo al fix (exit 139 segfault) y PASA
    tras el fix (operación sobre el store ya abierto vía _resolve_dois_on_store).

    Usa:
    - DuckDB real (tmp_path / library.duckdb).
    - examples/bibtex/sample.bib (el .bib del proyecto).
    - httpx.MockTransport para simular la respuesta de OpenAlex sin red real.

    Aserta:
    1. run_seed_from_bib(..., resolve=True, transport=mock) NO crashea.
    2. papers_added > 0 (el .bib cargó papers).
    3. resolve.resolved > 0 (al menos un DOI del .bib fue resuelto por el mock).
    4. source_id queda poblado (W...) en el store para los papers resueltos.
    """
    import os

    from bib2graph.cli.commands.seed import run_seed_from_bib
    from bib2graph.stores.duckdb import DuckDBStore

    db_path = tmp_path / "library.duckdb"

    # Usar examples/bibtex/sample.bib del repo
    repo_root = Path(os.path.dirname(__file__)).parent.parent
    sample_bib = repo_root / "examples" / "bibtex" / "sample.bib"
    assert sample_bib.exists(), f"sample.bib no encontrado en {sample_bib}"

    # DOIs del sample.bib con DOI (de los que tiene doi definido):
    #   10.1016/j.ecolecon.2010.02.003 (martinez-alier2010)
    #   10.1177/0020715209105141        (hornborg2009)
    #   10.1177/0020715209105144        (shandra2009)
    #   10.1016/j.ecolecon.2020.106824  (dorninger2021)
    #   10.1016/j.ecolecon.2015.03.012  (no_authors_entry)
    #   10.1016/j.ecolecon.2009.11.014  (no_year_entry)
    #   10.1177/1070496503260974        (giljum2004)
    # El mock resolverá los primeros dos.
    works_mock = [
        {
            "id": "https://openalex.org/W1001",
            "doi": "https://doi.org/10.1016/j.ecolecon.2010.02.003",
        },
        {
            "id": "https://openalex.org/W1002",
            "doi": "https://doi.org/10.1177/0020715209105141",
        },
    ]
    transport = _make_doi_resolve_handler(works_mock)

    # Llamada encadenada en el mismo proceso: antes del fix → segfault
    seed_data = run_seed_from_bib(
        db_path,
        sample_bib,
        resolve=True,
        email="test@example.com",
        transport=transport,
    )

    # 1. No crasheó (si llegamos acá, el segfault fue corregido)
    assert seed_data["papers_added"] > 0, "El .bib cargó 0 papers"
    assert seed_data["total_papers"] >= seed_data["papers_added"]

    # 2. La resolución corrió y reportó el resultado
    assert "resolve" in seed_data, "El sub-dict 'resolve' no está en el resultado"
    r = seed_data["resolve"]
    assert r["resolved"] == 2, f"Se esperaban 2 papers resueltos, got {r['resolved']}"
    assert r["total_with_doi"] >= 2

    # 3. source_id poblado en el store (DuckDB real)
    store_check = DuckDBStore(db_path)
    loaded = store_check.load()
    rows = loaded.to_arrow().to_pylist()
    store_check.close()

    resolved_rows = [row for row in rows if row.get(Col.SOURCE_ID) is not None]
    assert len(resolved_rows) == 2, (
        f"Se esperaban 2 filas con source_id, got {len(resolved_rows)}"
    )
    source_ids_found = {row[Col.SOURCE_ID] for row in resolved_rows}
    assert "W1001" in source_ids_found
    assert "W1002" in source_ids_found
