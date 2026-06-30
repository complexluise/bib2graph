"""E2E capstone: ciclo one-shot guiado por ``status --json`` (#76, epic #167).

Verifica el flujo agents-first completo (ADR 0037):

  init → seed(bib) → [status: chain, not-ready] →
  seed(bib+resolve) → [status: chain, ready] →
  chain(both) → [status: build, preview-vacío] →
  build → [status: read, ready] →
  read top

La "trampa de la Nota 20" (ADR 0037 §c): un agente que siembra desde BibTeX
sin ``--resolve`` ve ``readiness.ready=False`` con ``reason`` que menciona
``--resolve``.  El test afirma que el agente debe resolver antes de poder
encadenar de forma productiva.

Monkeypatch: ``bib2graph.sources.openalex.OpenAlexSource`` se reemplaza por
``_MockedOA`` que inyecta un ``httpx.MockTransport`` estático.  Como
``chain.py`` y ``service/resolve.py`` importan ``OpenAlexSource`` dentro
del cuerpo de sus funciones (no a nivel de módulo), el patch del atributo
de módulo se ve cuando esas funciones ejecutan — sin necesidad de inyección
directa de transport desde el CLI.

Marker: ``pytest.mark.integration`` (I/O local — DuckDB; sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.workspace import Workspace

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixture de datos
# ---------------------------------------------------------------------------

_SAMPLE_BIB = Path(__file__).resolve().parents[2] / "examples" / "bibtex" / "sample.bib"

# DOIs presentes en sample.bib con DOI → IDs sintéticos de OpenAlex
_DOI_TO_OA_ID: dict[str, str] = {
    "10.1016/j.ecolecon.2010.02.003": "W9000001",
    "10.1177/0020715209105141": "W9000002",
    "10.1177/0020715209105144": "W9000003",
    "10.1016/j.ecolecon.2020.106824": "W9000004",
    "10.1016/j.ecolecon.2015.03.012": "W9000005",
    "10.1016/j.ecolecon.2009.11.014": "W9000006",
    "10.1177/1070496503260974": "W9000007",
}

# Work citante sintético para el forward chain (cita W9000001 y W9000002)
_CITING_WORK: dict[str, Any] = {
    "id": "https://openalex.org/W8888000001",
    "doi": None,
    "title": "E2E Test Citing Paper",
    "display_name": "E2E Test Citing Paper",
    "publication_year": 2024,
    "language": "en",
    "abstract_inverted_index": None,
    "authorships": [],
    "keywords": [],
    "referenced_works": [
        "https://openalex.org/W9000001",
        "https://openalex.org/W9000002",
    ],
    "primary_location": {"source": {"display_name": "E2E Test Journal"}},
    "type": "article",
}


# ---------------------------------------------------------------------------
# Mock transport para toda la sesión E2E
# ---------------------------------------------------------------------------


def _make_e2e_transport() -> httpx.MockTransport:
    """Transport unificado que cubre todos los requests del ciclo E2E.

    Discrimina por el prefijo del parámetro ``filter``:

    - ``doi:...``          → resolución DOI→source_id (seed --resolve)
    - ``cites:...``        → forward chain (chain --direction both)
    - ``openalex_id:...``  → refs→DOI (enriquecimiento automático en chain)
    - cualquier otro       → resultado vacío (cero candidatos backward, etc.)

    El estado ``cites_calls`` limita el mock: solo devuelve
    ``_CITING_WORK`` en la primera llamada y vacío en las siguientes, para
    evitar paginación infinita (el cursor ``next_cursor=None`` ya lo previene,
    pero el contador es explícito).
    """
    cites_calls: list[int] = [0]

    def _handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        filter_val: str = params.get("filter", "")
        results: list[dict[str, Any]] = []

        if filter_val.startswith("doi:"):
            # Resolución DOI→source_id: devolver pares {id, doi} para los
            # DOIs de sample.bib presentes en el filtro.
            for doi, short_id in _DOI_TO_OA_ID.items():
                if doi in filter_val:
                    results.append(
                        {
                            "id": f"https://openalex.org/{short_id}",
                            "doi": f"https://doi.org/{doi}",
                        }
                    )

        elif filter_val.startswith("cites:"):
            # Forward chain: devolver _CITING_WORK en la primera página;
            # next_cursor=None ya corta la paginación, pero el contador
            # garantiza que un bug de paginación no cuelgue el test.
            cites_calls[0] += 1
            if cites_calls[0] == 1:
                results = [_CITING_WORK]

        elif filter_val.startswith("openalex_id:"):
            # refs→DOI: resolver IDs de referencias a sus DOIs.
            for doi, short_id in _DOI_TO_OA_ID.items():
                if short_id in filter_val:
                    results.append(
                        {
                            "id": f"https://openalex.org/{short_id}",
                            "doi": f"https://doi.org/{doi}",
                        }
                    )

        # Para cualquier otro filtro (p.ej. backward scent) devuelve vacío.
        return httpx.Response(
            200,
            json={
                "results": results,
                "meta": {
                    "count": len(results),
                    "next_cursor": None,
                },
            },
        )

    return httpx.MockTransport(_handler)


# ---------------------------------------------------------------------------
# Helpers de invocación
# ---------------------------------------------------------------------------


def _status(runner: CliRunner, ws: Workspace) -> dict[str, Any]:
    """Invoca ``b2g status --json`` y devuelve ``envelope["data"]``.

    Valida que stdout sea exactamente 1 línea JSON (vía
    ``_assert_single_json_line``) para que un mensaje espurio en stdout
    también haga fallar al test de status.
    """
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "status", "--json"],
    )
    assert result.exit_code == 0, (
        f"status --json falló (exit {result.exit_code}):\n{result.stdout}"
    )
    envelope = _assert_single_json_line(result.stdout, "status")
    assert envelope["ok"] is True, f"status devolvió ok=False: {envelope}"
    return envelope["data"]  # type: ignore[no-any-return]


def _assert_single_json_line(stdout: str, step: str) -> dict[str, Any]:
    """Afirma que stdout es exactamente 1 línea JSON parseable y la devuelve."""
    non_empty = [line for line in stdout.splitlines() if line.strip()]
    assert len(non_empty) == 1, (
        f"[{step}] stdout debe ser 1 línea JSON; got {len(non_empty)} líneas:\n{stdout!r}"
    )
    parsed: dict[str, Any] = json.loads(non_empty[0])
    return parsed


# ---------------------------------------------------------------------------
# Test capstone
# ---------------------------------------------------------------------------


def test_oneshot_readiness_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ciclo one-shot guiado por status --json — capstone E2E del epic #167.

    Afirma la "trampa de la Nota 20": sin ``--resolve``, el agente ve
    ``readiness.ready=False`` con un ``reason`` que menciona ``--resolve``.
    Tras resolver, el ciclo avanza: chain → build → read top con salida
    JSON limpia en cada paso.
    """
    # --- Monkeypatch: reemplazar OpenAlexSource con versión de mock --------
    #
    # chain.py y service/resolve.py importan OpenAlexSource DENTRO del cuerpo
    # de sus funciones, no a nivel de módulo.  Al patchear el atributo en el
    # objeto módulo, el ``from bib2graph.sources.openalex import OpenAlexSource``
    # que ejecuta en tiempo de llamada obtiene la clase mockeada.
    import bib2graph.sources.openalex as _oa_mod

    _mock_transport = _make_e2e_transport()
    _real_cls = _oa_mod.OpenAlexSource

    class _MockedOA(_real_cls):  # type: ignore[valid-type]
        """Subclase que siempre inyecta el transport de mock, ignorando el recibido."""

        def __init__(  # type: ignore[override]
            self,
            *,
            email: str | None = None,
            api_key: str | None = None,
            transport: Any = None,
            base_url: str = "https://api.openalex.org",
            max_results: int = 200,
        ) -> None:
            super().__init__(  # type: ignore[misc]
                email=email,
                api_key=api_key,
                transport=_mock_transport,
                base_url=base_url,
                max_results=max_results,
            )

    monkeypatch.setattr(_oa_mod, "OpenAlexSource", _MockedOA)

    # --- Paso 0: b2g init (primer verbo del ciclo agents-first) ------------
    #
    # Usamos CLI pura para que el capstone ejerza init→seed→…→read-top
    # completo.  TARGET es la ruta absoluta al directorio destino; --name fija
    # el nombre de la investigación; --json valida la salida.
    ws_dir = tmp_path / "research"
    runner = CliRunner()

    result = runner.invoke(
        b2g,
        ["init", str(ws_dir), "--name", "test-e2e", "--json"],
    )
    envelope = _assert_single_json_line(result.stdout, "init")
    assert result.exit_code == 0, (
        f"init falló (exit {result.exit_code}):\n{result.stdout}"
    )
    assert envelope["ok"] is True
    assert "workspace_dir" in envelope["data"], (
        f"init --json debe devolver 'workspace_dir'; got keys: {list(envelope['data'].keys())}"
    )
    assert "library_path" in envelope["data"], (
        "init --json debe devolver 'library_path'"
    )

    # Abrir el workspace creado para usar ws.root en los pasos siguientes
    ws = Workspace.open(ws_dir)

    # Status tras init: next_best_action="seed", siempre ready=True
    data = _status(runner, ws)
    assert data["next_best_action"] == "seed", (
        f"Tras init se esperaba 'seed', got {data['next_best_action']!r}"
    )
    assert data["readiness"]["ready"] is True, (
        "Antes de la primera siembra, readiness.ready debe ser True"
    )

    # --- Paso 1: seed --from-bib SIN --resolve (BibTeX, sin red) ----------
    assert _SAMPLE_BIB.exists(), f"Fixture no encontrado: {_SAMPLE_BIB}"

    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "seed", "--from-bib", str(_SAMPLE_BIB), "--json"],
    )
    envelope = _assert_single_json_line(result.stdout, "seed --from-bib")
    assert result.exit_code == 0, (
        f"seed --from-bib falló (exit {result.exit_code}):\n{result.stdout}"
    )
    assert envelope["ok"] is True
    assert envelope["data"]["papers_added"] > 0, (
        "sample.bib debe contener al menos 1 paper"
    )

    # --- Status tras seed sin resolve: Nota 20 ----------------------------
    #
    # Sin --resolve, source_id=None para todos los papers BibTeX.
    # El agente debe ver readiness.ready=False con reason mencionando --resolve.
    data = _status(runner, ws)
    assert data["next_best_action"] == "chain", (
        f"Tras seed, se esperaba next_best_action='chain', got {data['next_best_action']!r}"
    )
    readiness = data["readiness"]
    assert readiness["ready"] is False, (
        "Sin --resolve, readiness.ready debe ser False (0 seeds con source_id)"
    )
    assert readiness["reason"] is not None, (
        "readiness.reason no debe ser None cuando ready=False"
    )
    assert "--resolve" in readiness["reason"], (
        f"readiness.reason debe mencionar '--resolve'; got: {readiness['reason']!r}"
    )

    # --- Paso 2: seed --from-bib --resolve (DOI→source_id con mock) -------
    result = runner.invoke(
        b2g,
        [
            "--workspace",
            str(ws.root),
            "seed",
            "--from-bib",
            str(_SAMPLE_BIB),
            "--resolve",
            "--json",
        ],
    )
    envelope = _assert_single_json_line(result.stdout, "seed --from-bib --resolve")
    assert result.exit_code == 0, (
        f"seed --from-bib --resolve falló (exit {result.exit_code}):\n{result.stdout}"
    )
    assert envelope["ok"] is True
    resolve_sub = envelope["data"].get("resolve")
    assert resolve_sub is not None, (
        "Con resolve=True, data debe contener sub-dict 'resolve'"
    )
    assert resolve_sub["resolved"] > 0, (
        "El mock debe resolver al menos 1 DOI a source_id"
    )

    # --- Status tras seed --resolve: chain READY --------------------------
    data = _status(runner, ws)
    assert data["next_best_action"] == "chain", (
        f"Tras seed --resolve, se esperaba 'chain', got {data['next_best_action']!r}"
    )
    assert data["readiness"]["ready"] is True, (
        f"Tras --resolve, readiness.ready debe ser True; got: {data['readiness']}"
    )

    # --- Paso 3: chain --direction both (forward con mock) ----------------
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "chain", "--direction", "both", "--json"],
    )
    envelope = _assert_single_json_line(result.stdout, "chain --direction both")
    assert result.exit_code == 0, (
        f"chain falló (exit {result.exit_code}):\n{result.stdout}"
    )
    assert envelope["ok"] is True

    # Verificar que el forward-chain realmente encontró candidatos (W8888000001).
    # Si la rama ``cites:`` del mock devolviera vacío, candidates_found sería 0
    # y esta aserción fallaría antes de que el error se propague silenciosamente.
    chain_result = envelope["data"]
    assert chain_result["candidates_found"] > 0, (
        "El mock forward-chain (cites:W9000001|…) debe haber encontrado ≥1 "
        f"candidato; got candidates_found={chain_result['candidates_found']}"
    )

    # --- Status tras chain: build, preview tiene ≥1 red vacía con fix ----
    data = _status(runner, ws)
    assert data["next_best_action"] == "build", (
        f"Tras chain, se esperaba 'build', got {data['next_best_action']!r}"
    )
    build_preview = data["build_preview"]
    assert len(build_preview) == 5, (
        f"build_preview debe tener 5 entradas (una por red); got {len(build_preview)}"
    )
    empty_with_fix = [
        e
        for e in build_preview
        if e.get("would_be_empty") and e.get("fix_command") is not None
    ]
    assert len(empty_with_fix) >= 1, (
        "build_preview debe tener ≥1 red vacía con fix_command no nulo. "
        f"Preview: {json.dumps(build_preview, ensure_ascii=False)}"
    )

    # --- Paso 4: build (sin seeds aceptadas; no hay llamada a OA) ---------
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "build", "--json"],
    )
    envelope = _assert_single_json_line(result.stdout, "build")
    assert result.exit_code == 0, (
        f"build falló (exit {result.exit_code}):\n{result.stdout}"
    )
    assert envelope["ok"] is True

    build_data = envelope["data"]
    maturity = build_data.get("maturity")
    assert maturity is not None, "build --json debe incluir campo 'maturity'"
    assert maturity["curated"] is False, (
        "Sin curación previa, maturity.curated debe ser False"
    )
    assert maturity["scope"] == "all", (
        f"maturity.scope debe ser 'all'; got {maturity['scope']!r}"
    )
    assert maturity["saturated"] is False, (
        "maturity.saturated es siempre False en el ciclo one-shot"
    )
    assert isinstance(maturity["empty_networks"], list), (
        "maturity.empty_networks debe ser una lista"
    )

    # --- Status tras build: read, ready -----------------------------------
    data = _status(runner, ws)
    assert data["next_best_action"] == "read", (
        f"Tras build, se esperaba 'read', got {data['next_best_action']!r}"
    )
    assert data["readiness"]["ready"] is True, (
        f"Tras build, readiness.ready debe ser True; got: {data['readiness']}"
    )

    # --- Paso 5: read top (salida de investigación) -----------------------
    result = runner.invoke(
        b2g,
        ["--workspace", str(ws.root), "read", "top", "--json"],
    )
    envelope = _assert_single_json_line(result.stdout, "read top")
    assert result.exit_code == 0, (
        f"read top falló (exit {result.exit_code}):\n{result.stdout}"
    )
    assert envelope["ok"] is True

    read_data = envelope["data"]
    assert "central" in read_data, (
        f"read top --json debe incluir 'central'; got keys: {list(read_data.keys())}"
    )
    assert "cocitation" in read_data, (
        f"read top --json debe incluir 'cocitation'; got keys: {list(read_data.keys())}"
    )
    assert isinstance(read_data["central"], list), (
        "read_data['central'] debe ser una lista"
    )
    assert isinstance(read_data["cocitation"], list), (
        "read_data['cocitation'] debe ser una lista"
    )
