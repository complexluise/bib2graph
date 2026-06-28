"""Tests del Hito G3 — API local FastAPI (ADR 0028).

Cobertura priorizada (docs/ROADMAP/05-gui.md §Hito G3):

1. ``b2g gui`` exit 3 sin extra (monkeypatch ImportError fastapi/uvicorn).
2. Mapeo código-HTTP: un caso por código 0-5.
3. Token: sin token → 401; con token → 200.
4. Happy-path forma del envelope (``schema=="1"``, ``ok``, ``data``) por endpoint.
5. Write: POST curate → 200 y get_paper refleja el cambio; id inexistente → 422;
   decision inválida → 422.

No se testea concurrencia del lock ni uvicorn/browser (plumbing).
Marcador: ``unit`` (DuckDB en tmp_path, TestClient en memoria, sin red real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers compartidos (mismo patrón que test_service_reads.py)
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str,
    title: str = "Test title",
    year: int = 2020,
    is_seed: bool = True,
    curation_status: str = "candidate",
    references_id: list[str] | None = None,
    cited_by_id: list[str] | None = None,
) -> dict[str, Any]:
    """Fila mínima con schema completo para tests."""
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
        "authors_raw": ["Autor A"],
        "authors_id": ["oa:author1"],
        "authors_affiliations": None,
        "keywords_raw": ["keyword1"],
        "keywords_id": ["kw1"],
        "institutions_raw": None,
        "institutions_id": None,
        "references_id": references_id,
        "references_doi": None,
        "cited_by_id": cited_by_id,
    }


def _init_workspace(tmp_path: Path, name: str = "test-ws") -> Any:
    """Crea y devuelve un Workspace inicializado en tmp_path."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / name
    return Workspace.init(ws_dir, name)


def _seed_store(ws: Any, rows: list[dict[str, Any]]) -> None:
    """Persiste filas en el store del workspace."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(ws.library_path)
    store.persist(corpus)


def _make_test_client(ws: Any, token: str) -> Any:
    """Construye un TestClient con la app configurada."""
    from fastapi.testclient import TestClient

    from bib2graph.api.app import create_app

    app = create_app(ws, token=token, cors_origins=["http://localhost:3000"])
    return TestClient(app, raise_server_exceptions=False)


# Token de prueba fijo para los tests
_TEST_TOKEN = "token-de-prueba-para-tests-12345"
_AUTH_HEADER = {"Authorization": f"Bearer {_TEST_TOKEN}"}


# ---------------------------------------------------------------------------
# 1. b2g gui — exit 3 sin extra (monkeypatch ImportError)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_b2g_gui_exit_3_sin_extra(tmp_path: Path) -> None:
    """``b2g gui`` lanza DependencyError (exit 3) si fastapi/uvicorn no están instalados."""
    from bib2graph.cli._errors import DependencyError
    from bib2graph.cli.commands.gui import run_gui

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    ctx_obj: dict[str, object] = {"workspace": str(ws.root)}

    with (
        patch("bib2graph.cli.commands.gui.resolve_workspace", return_value=ws),
        patch.dict(
            "sys.modules",
            {"fastapi": None, "uvicorn": None},  # type: ignore[dict-item]
        ),
        pytest.raises(DependencyError, match="gui"),
    ):
        run_gui(workspace_ctx=ctx_obj)


# ---------------------------------------------------------------------------
# 2. Mapeo código-HTTP - un caso por código 0-5
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_http_status_for_mapeo_completo() -> None:
    """``http_status_for`` devuelve el status correcto para cada código 0-5."""
    from bib2graph.api.envelopes import http_status_for

    assert http_status_for(0) == 200
    assert http_status_for(1) == 400
    assert http_status_for(2) == 422
    assert http_status_for(3) == 501
    assert http_status_for(4) == 502
    assert http_status_for(5) == 409
    # No mapeado → 500
    assert http_status_for(99) == 500


@pytest.mark.unit
def test_make_error_response_b2gerror_codigo_y_status(tmp_path: Path) -> None:
    """``make_error_response`` construye el envelope correcto con el status esperado."""
    from bib2graph.api.envelopes import make_error_response
    from bib2graph.service.errors import DataError, StoreError, UsageError

    # UsageError → code 1 → HTTP 400
    resp = make_error_response("test_cmd", UsageError("uso incorrecto"))
    assert resp.status_code == 400
    body = resp.body
    import json

    data = json.loads(body)
    assert data["ok"] is False
    assert data["exit_code"] == 1
    assert data["error"]["code"] == "USAGE_ERROR"

    # StoreError → code 5 → HTTP 409
    resp5 = make_error_response("test_cmd", StoreError("bloqueado"))
    assert resp5.status_code == 409
    data5 = json.loads(resp5.body)
    assert data5["exit_code"] == 5

    # DataError → code 2 → HTTP 422
    resp2 = make_error_response("test_cmd", DataError("no existe"))
    assert resp2.status_code == 422
    data2 = json.loads(resp2.body)
    assert data2["exit_code"] == 2


@pytest.mark.unit
def test_make_error_response_excepcion_inesperada_es_500() -> None:
    """Una excepción NO de contrato (bug interno) → HTTP 500, no 409.

    Regresión: el fallback enmascaraba errores internos como 409 (store
    bloqueado), mintiéndole a la SPA. Un bug inesperado debe ser 500.
    """
    import json

    from bib2graph.api.envelopes import make_error_response

    resp = make_error_response("test_cmd", ValueError("boom inesperado"))
    assert resp.status_code == 500
    data = json.loads(resp.body)
    assert data["ok"] is False
    assert data["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# 3. Token — sin token → 401; con token → 200
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_api_sin_token_rechaza_401(tmp_path: Path) -> None:
    """GET /api/workspace sin token → 401."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/workspace")
    assert resp.status_code == 401


@pytest.mark.unit
def test_api_token_invalido_rechaza_401(tmp_path: Path) -> None:
    """GET /api/workspace con token incorrecto → 401."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get(
        "/api/workspace", headers={"Authorization": "Bearer token-incorrecto"}
    )
    assert resp.status_code == 401


@pytest.mark.unit
def test_api_con_token_valido_acepta_200(tmp_path: Path) -> None:
    """GET /api/workspace con token correcto → 200."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/workspace", headers=_AUTH_HEADER)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Happy-path — forma del envelope por endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_workspace_forma_envelope(tmp_path: Path) -> None:
    """GET /api/workspace devuelve envelope canónico con clave 'name'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1"), _row(id="P2")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/workspace", headers=_AUTH_HEADER)

    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "1"
    assert body["ok"] is True
    assert body["error"] is None
    assert "name" in body["data"]
    assert body["data"]["total_papers"] == 2


@pytest.mark.unit
def test_list_rounds_forma_envelope(tmp_path: Path) -> None:
    """GET /api/rounds devuelve envelope con clave 'rounds' (lista)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/rounds", headers=_AUTH_HEADER)

    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "1"
    assert body["ok"] is True
    assert isinstance(body["data"]["rounds"], list)
    # Debe incluir la entrada "live"
    live_entries = [r for r in body["data"]["rounds"] if r["id"] == "live"]
    assert len(live_entries) == 1


@pytest.mark.unit
def test_get_paper_forma_envelope(tmp_path: Path) -> None:
    """GET /api/paper/{id} devuelve envelope con los campos del paper."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(
                id="P1",
                title="Paper de prueba",
                year=2023,
                curation_status="candidate",
            )
        ],
    )

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/paper/P1", headers=_AUTH_HEADER)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["id"] == "P1"
    assert body["data"]["title"] == "Paper de prueba"


@pytest.mark.unit
def test_get_paper_inexistente_422(tmp_path: Path) -> None:
    """GET /api/paper/{id} con id inexistente → 422 (DataError)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/paper/no-existe", headers=_AUTH_HEADER)

    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["exit_code"] == 2


@pytest.mark.unit
def test_get_network_kind_invalido_422(tmp_path: Path) -> None:
    """GET /api/network/{kind} con kind inválido → 422 (DataError)."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/network/red_inventada", headers=_AUTH_HEADER)

    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["exit_code"] == 2


@pytest.mark.unit
def test_get_scent_forma_envelope(tmp_path: Path) -> None:
    """GET /api/paper/{id}/scent devuelve envelope con claves de scent."""
    ws = _init_workspace(tmp_path)
    _seed_store(
        ws,
        [
            _row(id="P1", references_id=["R1", "R2"]),
            _row(id="P2", references_id=["R1", "R3"]),
        ],
    )

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.get("/api/paper/P1/scent", headers=_AUTH_HEADER)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert "paper_id" in data
    assert "score" in data
    assert "coupling" in data


# ---------------------------------------------------------------------------
# 5. Write — POST curate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_post_curate_accepted_200(tmp_path: Path) -> None:
    """POST /api/paper/{id}/curate {decision:'accepted'} → 200."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", curation_status="candidate")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.post(
        "/api/paper/P1/curate",
        json={"decision": "accepted"},
        headers=_AUTH_HEADER,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["accepted_count"] == 1


@pytest.mark.unit
def test_post_curate_y_get_paper_refleja_cambio(tmp_path: Path) -> None:
    """POST curate accepted + GET paper → curation_status == 'accepted'."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1", curation_status="candidate")])

    client = _make_test_client(ws, _TEST_TOKEN)
    client.post(
        "/api/paper/P1/curate",
        json={"decision": "accepted"},
        headers=_AUTH_HEADER,
    )

    resp = client.get("/api/paper/P1", headers=_AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["data"]["curation_status"] == "accepted"


@pytest.mark.unit
def test_post_curate_id_inexistente_422(tmp_path: Path) -> None:
    """POST curate con id inexistente → 422."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.post(
        "/api/paper/id-que-no-existe/curate",
        json={"decision": "accepted"},
        headers=_AUTH_HEADER,
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["exit_code"] == 2


@pytest.mark.unit
def test_post_curate_decision_invalida_422(tmp_path: Path) -> None:
    """POST curate con decision inválida → 422."""
    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = _make_test_client(ws, _TEST_TOKEN)
    resp = client.post(
        "/api/paper/P1/curate",
        json={"decision": "decision_invalida"},
        headers=_AUTH_HEADER,
    )

    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["exit_code"] == 2


# Neutralidad del núcleo (service no importa fastapi): consolidada en
# test_service.py::test_service_modulo_neutral_de_transporte (epic #184).


# ---------------------------------------------------------------------------
# 6. Wiring del frontend (build_gui_app) — REGRESIÓN GET / 422
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_gui_app_sirve_index_con_token(tmp_path: Path) -> None:
    """REGRESIÓN: GET / sirve index.html con el token inyectado (no 422).

    Bug real (caught en runtime, no por el verifier que reconstruía la app):
    ``serve_index(_request: Request)`` bajo ``from __future__ import annotations``
    hacía que FastAPI tratara ``_request`` como query param requerido → 422.
    Este test ejercita el wiring REAL ``build_gui_app``, no una app reconstruida.
    """
    from fastapi.testclient import TestClient

    from bib2graph.cli.commands.gui import build_gui_app

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        '<meta name="b2g-token" content="__B2G_TOKEN__">', encoding="utf-8"
    )

    client = TestClient(build_gui_app(ws, "TESTTOK", static_dir))

    resp = client.get("/")
    assert resp.status_code == 200
    assert "TESTTOK" in resp.text
    assert "__B2G_TOKEN__" not in resp.text  # placeholder reemplazado
    # El wiring del static NO rompe la auth de los routers /api/*
    assert client.get("/api/workspace").status_code == 401


@pytest.mark.unit
def test_build_gui_app_sin_static_solo_api(tmp_path: Path) -> None:
    """Sin frontend buildeado (static_dir=None): GET / → 404; la API sigue montada."""
    from fastapi.testclient import TestClient

    from bib2graph.cli.commands.gui import build_gui_app

    ws = _init_workspace(tmp_path)
    _seed_store(ws, [_row(id="P1")])

    client = TestClient(build_gui_app(ws, "TESTTOK", None))

    assert client.get("/").status_code == 404
    assert client.get("/api/workspace").status_code == 401
