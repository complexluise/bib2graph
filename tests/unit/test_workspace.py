"""Tests TDD del Hito 9 workspace — ADR 0029.

Casos cubiertos:
1. ``b2g init <name>`` crea la estructura + workspace.json válido.
2. ``b2g init .`` inicializa el cwd.
3. Error si ya hay workspace.json.
4. Resolución ambiente: (a) caminar hacia arriba encuentra workspace.json;
   (b) B2G_WORKSPACE gana sobre cwd; (c) --workspace/--store gana sobre todo;
   (d) sin nada → error accionable.
5. --store suelto (modo degenerado) sigue funcionando (retrocompat).
6. ``b2g status`` reporta el workspace resuelto.
7. ``b2g build`` escribe en ``<workspace>/networks/`` y sella corpus_hash.

Filosofía (AGENTS.md): se testean funciones núcleo, no el parser Click.
Marcador: ``unit`` (DuckDB en tmp_path, sin red real).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from bib2graph.schemas import CORPUS_SCHEMA

# ---------------------------------------------------------------------------
# Helpers compartidos
# ---------------------------------------------------------------------------


def _make_corpus_row(
    *, id: str, title: str = "Test", curation_status: str = "candidate"
) -> dict[str, Any]:
    """Fila mínima con schema completo."""
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


def _seed_store(store_path: Path, rows: list[dict[str, Any]] | None = None) -> None:
    """Puebla un store con filas mínimas."""
    from bib2graph.corpus import Corpus
    from bib2graph.stores.duckdb import DuckDBStore

    if rows is None:
        rows = [_make_corpus_row(id="P1"), _make_corpus_row(id="P2")]
    table = pa.Table.from_pylist(rows, schema=CORPUS_SCHEMA)
    corpus = Corpus.from_arrow(table)
    store = DuckDBStore(store_path)
    store.persist(corpus)


# ---------------------------------------------------------------------------
# 1. Workspace.init — scaffolding
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_workspace_init_crea_estructura(tmp_path: Path) -> None:
    """Workspace.init crea carpeta, workspace.json, library.duckdb y subdirs."""
    from bib2graph.workspace import LIBRARY_FILENAME, WORKSPACE_MANIFEST_FILE, Workspace

    ws_dir = tmp_path / "mi-investigacion"
    Workspace.init(ws_dir, "Mi investigación")

    assert ws_dir.exists()
    assert (ws_dir / WORKSPACE_MANIFEST_FILE).exists()
    assert (ws_dir / LIBRARY_FILENAME).exists()
    assert (ws_dir / "networks").exists()
    assert (ws_dir / "snapshots").exists()
    assert (ws_dir / "exports").exists()

    # workspace.json es un JSON válido con los campos del manifest
    raw = json.loads((ws_dir / WORKSPACE_MANIFEST_FILE).read_text(encoding="utf-8"))
    assert raw["name"] == "Mi investigación"
    assert "created_at" in raw
    assert "bib2graph_version" in raw
    assert raw["schema_version"] == "1"


@pytest.mark.unit
def test_workspace_init_retorna_workspace_con_paths_correctos(
    tmp_path: Path,
) -> None:
    """Workspace.init retorna Workspace con library_path y dirs correctos."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "estudio"
    ws = Workspace.init(ws_dir, "Estudio")

    assert ws.library_path == ws_dir / "library.duckdb"
    assert ws.networks_dir == ws_dir / "networks"
    assert ws.snapshots_dir == ws_dir / "snapshots"
    assert ws.exports_dir == ws_dir / "exports"
    assert ws.root == ws_dir


@pytest.mark.unit
def test_workspace_init_dot_inicializa_cwd(tmp_path: Path) -> None:
    """Workspace.init en el directorio actual (.) lo inicializa como workspace."""
    from bib2graph.cli.commands.init import run_init

    data = run_init(tmp_path, tmp_path.name)

    assert Path(data["workspace_dir"]).resolve() == tmp_path.resolve()
    assert (tmp_path / "workspace.json").exists()
    assert (tmp_path / "library.duckdb").exists()


@pytest.mark.unit
def test_workspace_init_falla_si_ya_existe(tmp_path: Path) -> None:
    """Workspace.init falla con WorkspaceExistsError si ya hay workspace.json."""
    from bib2graph.workspace import Workspace, WorkspaceExistsError

    ws_dir = tmp_path / "existente"
    Workspace.init(ws_dir, "Primera vez")

    with pytest.raises(WorkspaceExistsError, match="Ya existe"):
        Workspace.init(ws_dir, "Segunda vez")


@pytest.mark.unit
def test_run_init_error_accionable_si_ya_existe(tmp_path: Path) -> None:
    """run_init lanza UsageError (exit 1) si el workspace ya existe."""
    from bib2graph.cli._errors import UsageError
    from bib2graph.cli.commands.init import run_init

    ws_dir = tmp_path / "existente"
    run_init(ws_dir, "Primera")

    with pytest.raises(UsageError):
        run_init(ws_dir, "Segunda")


# ---------------------------------------------------------------------------
# 2. WorkspaceManifest — validación Pydantic
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_workspace_manifest_tiene_schema_version_1() -> None:
    """WorkspaceManifest tiene schema_version='1' por defecto."""
    from bib2graph.workspace import WorkspaceManifest

    m = WorkspaceManifest(name="test")
    assert m.schema_version == "1"
    assert m.name == "test"
    assert m.created_at  # no vacío
    assert m.bib2graph_version  # no vacío


# ---------------------------------------------------------------------------
# 3. Resolución ambiente — Workspace.resolve
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_workspace_flag_explícito(tmp_path: Path) -> None:
    """--workspace explícito gana sobre cualquier otra fuente."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "mi-ws"
    Workspace.init(ws_dir, "test")

    ws = Workspace.resolve(workspace=str(ws_dir))
    assert ws.root == ws_dir.resolve()
    assert ws.source == "flag"


@pytest.mark.unit
def test_resolve_store_flag_explícito_modo_degenerado(tmp_path: Path) -> None:
    """--store explícito crea un workspace degenerado (sin root, sin manifest)."""
    from bib2graph.workspace import Workspace

    store_file = tmp_path / "mi.duckdb"
    store_file.touch()

    ws = Workspace.resolve(store=str(store_file))
    assert ws.root is None
    assert ws.library_path == store_file.resolve()
    assert ws.manifest is None
    assert ws.source == "degenerate"


@pytest.mark.unit
def test_resolve_workspace_flag_gana_sobre_env(tmp_path: Path) -> None:
    """--workspace tiene precedencia sobre B2G_WORKSPACE."""
    from bib2graph.workspace import Workspace

    ws_flag = tmp_path / "flag-ws"
    ws_env = tmp_path / "env-ws"
    Workspace.init(ws_flag, "flag")
    Workspace.init(ws_env, "env")

    ws = Workspace.resolve(
        workspace=str(ws_flag),
        env={"B2G_WORKSPACE": str(ws_env)},
    )
    assert ws.root == ws_flag.resolve()
    assert ws.source == "flag"


@pytest.mark.unit
def test_resolve_env_gana_sobre_cwd(tmp_path: Path) -> None:
    """B2G_WORKSPACE tiene precedencia sobre la búsqueda desde cwd."""
    from bib2graph.workspace import Workspace

    ws_env = tmp_path / "env-ws"
    ws_cwd = tmp_path / "cwd-ws"
    Workspace.init(ws_env, "env")
    Workspace.init(ws_cwd, "cwd")

    ws = Workspace.resolve(
        env={"B2G_WORKSPACE": str(ws_env)},
        cwd=ws_cwd,
    )
    assert ws.root == ws_env.resolve()
    assert ws.source == "env"


@pytest.mark.unit
def test_resolve_caminar_hacia_arriba(tmp_path: Path) -> None:
    """Sin flags ni env, se camina hacia arriba desde cwd buscando workspace.json."""
    from bib2graph.workspace import Workspace

    ws_root = tmp_path / "proyecto"
    Workspace.init(ws_root, "proyecto")

    # Empezar desde un subdirectorio del workspace
    subdir = ws_root / "networks" / "sub"
    subdir.mkdir(parents=True, exist_ok=True)

    ws = Workspace.resolve(cwd=subdir, env={})
    assert ws.root == ws_root.resolve()
    assert ws.source == "cwd"


@pytest.mark.unit
def test_resolve_sin_workspace_lanza_error_accionable(tmp_path: Path) -> None:
    """Sin ningún workspace disponible, WorkspaceNotFoundError con sugerencia."""
    from bib2graph.workspace import Workspace, WorkspaceNotFoundError

    # tmp_path vacío sin workspace.json
    with pytest.raises(WorkspaceNotFoundError, match="b2g init"):
        Workspace.resolve(cwd=tmp_path, env={})


@pytest.mark.unit
def test_resolve_sin_workspace_mapea_a_usage_error(tmp_path: Path) -> None:
    """resolve_library_path convierte WorkspaceNotFoundError → UsageError (exit 1).

    Verificamos que la capa CLI convierte correctamente la excepción del seam.
    Usamos monkeypatching de Workspace.resolve para aislar el comportamiento.
    """
    from unittest.mock import patch

    from bib2graph.cli._errors import UsageError
    from bib2graph.cli._store import resolve_library_path
    from bib2graph.workspace import WorkspaceNotFoundError

    def _raise(*args: object, **kwargs: object) -> None:
        raise WorkspaceNotFoundError("no hay workspace")

    with patch("bib2graph.workspace.Workspace.resolve", side_effect=_raise):
        with pytest.raises(UsageError) as exc_info:
            resolve_library_path({"workspace": None, "store": None})
        assert exc_info.value.exit_code == 1


@pytest.mark.unit
def test_resolve_workspace_y_store_juntos_es_error(tmp_path: Path) -> None:
    """--workspace y --store simultáneos lanzan error accionable (son mutuamente excluyentes).

    Fija el comportamiento ante la colisión de flags: en vez de descartar
    silenciosamente uno de los dos, se rechaza explícitamente con un mensaje
    claro que guía al usuario.
    """
    from bib2graph.workspace import Workspace, WorkspaceNotFoundError

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    store_file = tmp_path / "mi.duckdb"
    store_file.touch()

    with pytest.raises(WorkspaceNotFoundError, match="mutuamente excluyentes"):
        Workspace.resolve(workspace=str(ws_dir), store=str(store_file))


@pytest.mark.unit
def test_resolve_workspace_y_store_juntos_mapea_a_usage_error(tmp_path: Path) -> None:
    """Colisión --workspace/--store → WorkspaceNotFoundError → UsageError (exit 1)."""
    from bib2graph.cli._errors import UsageError
    from bib2graph.cli._store import resolve_library_path
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "test")
    store_file = tmp_path / "mi.duckdb"
    store_file.touch()

    with pytest.raises(UsageError, match="mutuamente excluyentes"):
        resolve_library_path({"workspace": str(ws_dir), "store": str(store_file)})


# ---------------------------------------------------------------------------
# 4. Retrocompat: --store suelto (modo degenerado)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_retrocompat_store_suelto_con_run_status(tmp_path: Path) -> None:
    """--store archivo.duckdb suelto sigue funcionando (workspace degenerado)."""
    from bib2graph.cli.commands.status import run_status

    store_path = tmp_path / "mi.duckdb"
    _seed_store(store_path)

    # run_status toma directamente store_path (nivel núcleo)
    data = run_status(store_path)
    assert "loop_state" in data
    assert data["total_papers"] == 2


@pytest.mark.unit
def test_retrocompat_resolve_store_library_path(tmp_path: Path) -> None:
    """resolve_library_path con {'store': 'ruta.duckdb'} devuelve esa ruta."""
    from bib2graph.cli._store import resolve_library_path

    store_path = tmp_path / "mi.duckdb"
    store_path.touch()

    result = resolve_library_path({"workspace": None, "store": str(store_path)})
    assert result == store_path.resolve()


# ---------------------------------------------------------------------------
# 5. b2g status muestra workspace resuelto
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_status_incluye_workspace_info(tmp_path: Path) -> None:
    """status_cmd agrega campo 'workspace' con root y source al envelope."""
    from bib2graph.cli._store import resolve_workspace
    from bib2graph.cli.commands.status import run_status
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    Workspace.init(ws_dir, "proyecto")
    store_path = ws_dir / "library.duckdb"
    _seed_store(store_path)

    # Verificar que status devuelve datos base correctos
    data = run_status(store_path)
    assert "loop_state" in data
    assert data["total_papers"] == 2

    # Verificar que el workspace resuelto tiene la info correcta
    ws = resolve_workspace({"workspace": str(ws_dir), "store": None})
    assert ws.root == ws_dir.resolve()
    assert ws.source == "flag"


@pytest.mark.unit
def test_status_workspace_info_en_ctx_obj(tmp_path: Path) -> None:
    """El campo workspace se agrega cuando se usa resolve_workspace desde el CMD."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    Workspace.init(ws_dir, "proyecto")
    store_path = ws_dir / "library.duckdb"
    _seed_store(store_path)

    # Simular lo que haría status_cmd: resolver workspace + run_status
    from bib2graph.cli._store import resolve_workspace
    from bib2graph.cli.commands.status import run_status

    ws = resolve_workspace({"workspace": str(ws_dir), "store": None})
    data = run_status(ws.library_path)
    # Agregar info del workspace tal como lo haría el cmd
    data["workspace"] = {
        "root": str(ws.root),
        "source": ws.source,
    }

    assert data["workspace"]["root"] == str(ws_dir.resolve())
    assert data["workspace"]["source"] == "flag"


# ---------------------------------------------------------------------------
# 6. build escribe en <workspace>/networks/ y sella corpus_hash
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_escribe_en_workspace_networks_dir(tmp_path: Path) -> None:
    """run_build con out_dir explícito escribe artefactos en ese directorio."""
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)
    networks_dir = tmp_path / "networks"

    data = run_build(store_path, out_dir=networks_dir)

    assert Path(data["artifacts_dir"]) == networks_dir
    assert networks_dir.exists()


@pytest.mark.unit
def test_build_sella_corpus_hash(tmp_path: Path) -> None:
    """run_build escribe .corpus_hash en el directorio networks/."""
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)
    networks_dir = tmp_path / "networks"

    data = run_build(store_path, out_dir=networks_dir)

    hash_file = networks_dir / ".corpus_hash"
    assert hash_file.exists()

    stored_hash = hash_file.read_text(encoding="utf-8").strip()
    assert stored_hash == data["corpus_hash"]
    assert len(stored_hash) > 0


@pytest.mark.unit
def test_build_corpus_hash_en_envelope(tmp_path: Path) -> None:
    """run_build incluye corpus_hash en el resultado."""
    from bib2graph.cli.commands.build import run_build

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_build(store_path)

    assert "corpus_hash" in data
    assert isinstance(data["corpus_hash"], str)
    assert len(data["corpus_hash"]) > 0


@pytest.mark.unit
def test_build_corpus_hash_es_estable(tmp_path: Path) -> None:
    """El corpus_hash del build es igual al que produce compute_corpus_hash."""
    from bib2graph.backends.memory import compute_corpus_hash
    from bib2graph.cli.commands.build import run_build
    from bib2graph.stores.duckdb import DuckDBStore

    store_path = tmp_path / "test.duckdb"
    _seed_store(store_path)

    data = run_build(store_path)

    # Verificar contra el hash computado directamente
    store = DuckDBStore(store_path)
    corpus = store.load()
    expected_hash = compute_corpus_hash(corpus.to_arrow())

    assert data["corpus_hash"] == expected_hash


@pytest.mark.unit
def test_build_en_workspace_usa_networks_dir(tmp_path: Path) -> None:
    """build_cmd usa ws.networks_dir cuando el workspace es completo."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "proyecto"
    ws = Workspace.init(ws_dir, "proyecto")

    # Poblar la library
    _seed_store(ws.library_path)

    # run_build con out_dir = ws.networks_dir
    from bib2graph.cli.commands.build import run_build

    data = run_build(ws.library_path, out_dir=ws.networks_dir)

    assert Path(data["artifacts_dir"]).resolve() == ws.networks_dir.resolve()
    assert (ws.networks_dir / ".corpus_hash").exists()


# ---------------------------------------------------------------------------
# 7. Workspace.open — abrir workspace existente
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_workspace_open_lee_manifest(tmp_path: Path) -> None:
    """Workspace.open lee el manifest desde workspace.json."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    Workspace.init(ws_dir, "Mi estudio")

    ws2 = Workspace.open(ws_dir)
    assert ws2.manifest is not None
    assert ws2.manifest.name == "Mi estudio"
    assert ws2.root == ws_dir.resolve()


@pytest.mark.unit
def test_workspace_open_falla_sin_manifest(tmp_path: Path) -> None:
    """Workspace.open lanza WorkspaceNotFoundError si no hay workspace.json."""
    from bib2graph.workspace import Workspace, WorkspaceNotFoundError

    carpeta_sin_ws = tmp_path / "sin-workspace"
    carpeta_sin_ws.mkdir()

    with pytest.raises(WorkspaceNotFoundError):
        Workspace.open(carpeta_sin_ws)


# ---------------------------------------------------------------------------
# 8. Workspace.to_dict — serialización para envelope JSON
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_workspace_to_dict_completo(tmp_path: Path) -> None:
    """Workspace.to_dict incluye todas las claves esperadas."""
    from bib2graph.workspace import Workspace

    ws_dir = tmp_path / "ws"
    ws = Workspace.init(ws_dir, "test")

    d = ws.to_dict()
    assert d["root"] == str(ws_dir.resolve())
    assert "library_path" in d
    assert "networks_dir" in d
    assert "snapshots_dir" in d
    assert "exports_dir" in d
    assert d["source"] == "init"
    assert d["manifest"] is not None
    assert d["manifest"]["name"] == "test"


@pytest.mark.unit
def test_workspace_to_dict_degenerado(tmp_path: Path) -> None:
    """Workspace degenerado (store suelto) tiene root=None en to_dict."""
    from bib2graph.workspace import Workspace

    store_file = tmp_path / "mi.duckdb"
    store_file.touch()

    ws = Workspace.resolve(store=str(store_file))
    d = ws.to_dict()
    assert d["root"] is None
    assert d["manifest"] is None
    assert "library_path" in d
