"""Corte 3b (#253, ADR 0053 D2): carriles en la superficie CLI.

Cubre `--source` en curate/read/status/export/snapshot create/validate (con
`legacy_provider` correcto: un comando de lectura no migra un store v1 al carril
equivocado), `build` que sella `networks/.provider`, `status` contra el carril
sellado + `data.providers`, `export --format arrow` (metadata `provider`, error
ante red de otro carril, warning R4), `snapshot restore` por carril del parquet y
`ProviderMismatchError` -> exit 2.  Sin red; DuckDB en `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import pyarrow.feather as feather
import pyarrow.parquet as pq
import pytest
from click.testing import CliRunner
from test_lanes_253a import (
    _legacy_sibling_providers,
    _make_v1_store,
    _meta,
    _row,
    _statuses,
    _table,
)

from bib2graph.backends import ProviderMismatchError
from bib2graph.cli import b2g
from bib2graph.cli._errors import handle_errors
from bib2graph.constants import Provider
from bib2graph.corpus import Corpus
from bib2graph.stores.duckdb import DuckDBStore
from bib2graph.workspace import Workspace

pytestmark = pytest.mark.integration

OA = Provider.OPENALEX
S2 = Provider.S2


def _ws(tmp_path: Path, source: Provider = OA) -> Workspace:
    return Workspace.init(tmp_path / "w", "w", source=source)


def _put(ws: Workspace, provider: Provider, rows: list[dict[str, Any]]) -> None:
    store = DuckDBStore(ws.library_path, provider=provider)
    store.persist(Corpus.from_arrow(_table(rows)))
    store.close()


def _lane_rows(provider: str, ids: list[str]) -> list[dict[str, Any]]:
    return [
        _row(i, provider, references_id=["shared-ref", f"r-{i}"], year=2020)
        for i in ids
    ]


def _run(ws: Workspace, *args: str) -> Any:
    return CliRunner().invoke(b2g, ["--workspace", str(ws.root), *args])


def _json(result: Any) -> dict[str, Any]:
    return json.loads(result.stdout.strip().splitlines()[-1])


def _two_lane_ws(tmp_path: Path) -> Workspace:
    ws = _ws(tmp_path)
    _put(ws, OA, _lane_rows("openalex", ["a", "b", "c"]))
    _put(ws, S2, _lane_rows("s2", ["x", "y"]))
    return ws


# `--source` no migra un store v1 al carril equivocado (bloqueante del 3a)

_V1_COMMANDS: list[list[str]] = [
    ["curate", "dump", "--scope", "all"],
    ["curate", "accept", "--ids", "doi:aaa"],
    ["curate", "reject", "--ids", "doi:aaa"],
    ["curate", "filter", "--year-gte", "1900"],
    ["read", "list"],
    ["read", "stats"],
    ["read", "show", "--id", "doi:aaa"],
    ["read", "top"],
    ["status"],
    ["validate"],
    ["export", "--format", "arrow", "--no-network"],
    ["snapshot", "create"],
]


def _old_sibling_rows_providers(path: Path) -> set[str]:
    """Carril de las filas hermanas que sembró `_make_v1_store` (no las nuevas)."""
    import duckdb

    con = duckdb.connect(str(path))
    try:
        return {
            r[0]
            for r in con.execute(
                "SELECT provider FROM referenced_but_not_fetched UNION ALL "
                "SELECT provider FROM enricher_log UNION ALL "
                "SELECT provider FROM filter_log WHERE name = 'year'"
            ).fetchall()
        }
    finally:
        con.close()


@pytest.mark.parametrize("cmd", _V1_COMMANDS, ids=lambda c: " ".join(c[:2]))
def test_source_ajeno_en_store_v1_no_migra_a_otro_carril(
    tmp_path: Path, cmd: list[str]
) -> None:
    ws = _ws(tmp_path, OA)
    ws.library_path.unlink()
    _make_v1_store(ws.library_path)

    _run(ws, *cmd, "--source", "s2", "--json")  # el exit code no importa acá

    assert {p for _, p, _ in _statuses(ws.library_path)} == {"openalex"}
    # Las filas hermanas del v1 siguen siendo openalex (un `curate filter` en s2
    # puede AGREGAR su propia fila de filter_log s2, pero no re-etiqueta la vieja).
    assert "openalex" in _legacy_sibling_providers(ws.library_path)
    assert _legacy_sibling_providers(ws.library_path) <= {"openalex", "s2"}
    assert _old_sibling_rows_providers(ws.library_path) == {"openalex"}
    assert _meta(ws.library_path)["schema_version"] == "3"


# Envelope: data.provider = {name, origin}

_ENVELOPE_COMMANDS: list[list[str]] = [
    ["curate", "dump", "--scope", "all"],
    ["curate", "accept", "--ids", "x"],
    ["curate", "reject", "--ids", "x"],
    ["curate", "filter", "--year-gte", "1900"],
    ["read", "list"],
    ["read", "stats"],
    ["read", "show", "--id", "x"],
    ["read", "top"],
    ["status"],
    ["validate"],
    ["export", "--format", "arrow", "--no-network"],
    ["snapshot", "create"],
]


@pytest.mark.parametrize("cmd", _ENVELOPE_COMMANDS, ids=lambda c: " ".join(c[:2]))
def test_envelope_trae_data_provider(tmp_path: Path, cmd: list[str]) -> None:
    ws = _two_lane_ws(tmp_path)

    flag = _run(ws, *cmd, "--source", "s2", "--json")
    assert flag.exit_code == 0, flag.output
    assert _json(flag)["data"]["provider"] == {"name": "s2", "origin": "flag"}

    default = _run(ws, *cmd, "--json")
    # `read show --id x` no existe en openalex: el error no lleva data.
    if default.exit_code == 0:
        assert _json(default)["data"]["provider"] == {
            "name": "openalex",
            "origin": "workspace",
        }


def test_read_ve_solo_su_carril(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    s2 = _json(_run(ws, "read", "list", "--source", "s2", "--json"))["data"]
    assert sorted(p["id"] for p in s2["papers"]) == ["x", "y"]
    oa = _json(_run(ws, "read", "list", "--json"))["data"]
    assert sorted(p["id"] for p in oa["papers"]) == ["a", "b", "c"]


def test_curate_con_source_escribe_en_su_carril(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    result = _run(ws, "curate", "accept", "--ids", "x", "--source", "s2", "--json")
    assert result.exit_code == 0, result.output
    got = {(i, p): s for i, p, s in _statuses(ws.library_path)}
    assert got[("x", "s2")] == "accepted"
    assert got[("a", "openalex")] == "candidate"


# build: un carril, sellado


def test_build_usa_solo_su_carril(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)

    s2 = _run(ws, "build", "--source", "s2", "--json")
    assert s2.exit_code == 0, s2.output
    nets = {n["kind"]: n for n in _json(s2)["data"]["networks"]}
    assert nets["bibliographic_coupling"]["nodes"] == 2  # x, y (no a, b, c)
    assert (ws.networks_dir / ".provider").read_text(encoding="utf-8") == "s2"

    oa = _run(ws, "build", "--json")
    assert oa.exit_code == 0, oa.output
    nets = {n["kind"]: n for n in _json(oa)["data"]["networks"]}
    assert nets["bibliographic_coupling"]["nodes"] == 3
    assert (ws.networks_dir / ".provider").read_text(encoding="utf-8") == "openalex"


def test_build_sella_provider_tambien_con_scope_vacio(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    result = _run(ws, "build", "--source", "s2", "--scope", "accepted", "--json")
    assert result.exit_code == 0, result.output
    # scope=accepted deja 0 papers (todo candidato, aunque is_seed): rama vacía.
    assert (ws.networks_dir / ".provider").read_text(encoding="utf-8") == "s2"


# status: conteo por carril y staleness contra el carril sellado


def test_status_counts_por_carril(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    data = _json(_run(ws, "status", "--json"))["data"]
    assert data["providers"] == {"openalex": 3, "s2": 2}
    assert data["total_papers"] == 3  # el resto del status es del carril activo
    s2 = _json(_run(ws, "status", "--source", "s2", "--json"))["data"]
    assert s2["providers"] == {"openalex": 3, "s2": 2}
    assert s2["total_papers"] == 2


def test_status_providers_en_store_vacio(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    assert _json(_run(ws, "status", "--json"))["data"]["providers"] == {}


def test_status_stale_contra_carril_sellado(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    assert _run(ws, "build", "--json").exit_code == 0  # sella openalex

    # Cambiar OTRO carril no vuelve stale la cache de openalex, se mire con el
    # carril que se mire.
    _put(ws, S2, _lane_rows("s2", ["z"]))
    for extra in ([], ["--source", "s2"]):
        data = _json(_run(ws, "status", "--json", *extra))["data"]
        assert data["networks_cache_stale"] is False

    # Cambiar el carril sellado sí.
    _put(ws, OA, _lane_rows("openalex", ["d"]))
    for extra in ([], ["--source", "s2"]):
        result = _run(ws, "status", "--json", *extra)
        assert _json(result)["data"]["networks_cache_stale"] is True
        assert any("openalex" in w for w in _json(result)["warnings"])


def test_status_cache_sin_sello_es_del_carril_de_la_investigacion(
    tmp_path: Path,
) -> None:
    """Cache pre-#253 (sin `.provider`): se compara contra `workspace.json.source`."""
    ws = _two_lane_ws(tmp_path)
    assert _run(ws, "build", "--json").exit_code == 0
    (ws.networks_dir / ".provider").unlink()
    data = _json(_run(ws, "status", "--source", "s2", "--json"))["data"]
    assert data["networks_cache_stale"] is False


# export arrow: metadata provider, red de otro carril, warning R4


def _arrow_meta(ws: Workspace) -> dict[bytes, bytes]:
    table = feather.read_table(str(ws.exports_dir / "corpus.arrow"))
    return dict(table.schema.metadata or {})


def test_export_arrow_metadata_provider(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)

    args = ["export", "--format", "arrow", "--no-network"]
    s2 = _run(ws, *args, "--source", "s2", "--json")
    assert s2.exit_code == 0, s2.output
    assert _arrow_meta(ws)[b"provider"] == b"s2"
    assert any("OpenAlex" in w for w in _json(s2)["warnings"])  # R4
    assert _json(s2)["data"]["rows_exported"] == 2

    oa = _run(ws, *args, "--json")
    assert oa.exit_code == 0, oa.output
    assert _arrow_meta(ws)[b"provider"] == b"openalex"
    assert not any("OpenAlex" in w for w in (_json(oa).get("warnings") or []))


def test_export_arrow_red_de_otro_carril_falla(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    assert _run(ws, "build", "--json").exit_code == 0  # red de openalex

    result = _run(ws, "export", "--format", "arrow", "--source", "s2", "--json")
    assert result.exit_code == 2, result.output
    err = _json(result)["error"]
    assert err["code"] == "DATA_ERROR"
    assert "openalex" in err["message"] and "s2" in err["message"]
    assert not (ws.exports_dir / "corpus.arrow").exists()

    # Con su propio carril, o sin red, anda.
    assert _run(ws, "export", "--format", "arrow", "--json").exit_code == 0
    no_net = _run(ws, "export", "--format", "arrow", "--no-network", "--source", "s2")
    assert no_net.exit_code == 0


def test_export_arrow_red_sin_sello_se_asume_del_workspace(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    assert _run(ws, "build", "--json").exit_code == 0
    (ws.networks_dir / ".provider").unlink()
    result = _run(ws, "export", "--format", "arrow", "--source", "s2", "--json")
    assert result.exit_code == 2, result.output


def test_export_graphml_avisa_si_la_red_es_de_otro_carril(tmp_path: Path) -> None:
    ws = _two_lane_ws(tmp_path)
    assert _run(ws, "build", "--json").exit_code == 0
    result = _run(ws, "export", "--format", "graphml", "--source", "s2", "--json")
    assert result.exit_code == 0, result.output
    assert any("carril 'openalex'" in w for w in _json(result)["warnings"])


# snapshot restore: carril del parquet


def _parquet(path: Path, rows: list[dict[str, Any]]) -> Path:
    pq.write_table(_table(rows), str(path))  # type: ignore[no-untyped-call]
    return path


def test_restore_usa_carril_del_parquet(tmp_path: Path) -> None:
    ws = _ws(tmp_path, OA)  # investigación openalex, parquet s2
    parquet = _parquet(tmp_path / "c.parquet", _lane_rows("s2", ["x", "y"]))

    result = _run(ws, "snapshot", "restore", "--from-corpus", str(parquet), "--json")

    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["provider"] == {"name": "s2", "origin": "snapshot"}
    assert {p for _, p, _ in _statuses(ws.library_path)} == {"s2"}


def test_restore_registra_external_ids_con_el_carril_del_parquet(
    tmp_path: Path,
) -> None:
    ws = _ws(tmp_path, OA)
    parquet = _parquet(tmp_path / "c.parquet", [_row("x", "s2", source_id="s2paper1")])
    result = _run(ws, "snapshot", "restore", "--from-corpus", str(parquet))
    assert result.exit_code == 0, result.output
    store = DuckDBStore(ws.library_path, provider=S2)
    try:
        got = store.backend._con.execute(  # type: ignore[attr-defined]
            "SELECT engine, id FROM external_ids"
        ).fetchall()
    finally:
        store.close()
    assert got == [("s2", "s2paper1")]


def test_restore_parquet_con_dos_carriles_falla(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    parquet = _parquet(tmp_path / "c.parquet", [_row("a", "openalex"), _row("b", "s2")])
    result = _run(ws, "snapshot", "restore", "--from-corpus", str(parquet), "--json")
    assert result.exit_code == 2, result.output
    assert "más de un proveedor" in _json(result)["error"]["message"]
    assert _statuses(ws.library_path) == []


def test_restore_en_carril_coexiste_con_otro(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _put(ws, OA, _lane_rows("openalex", ["a"]))
    parquet = _parquet(tmp_path / "c.parquet", _lane_rows("s2", ["x"]))
    result = _run(ws, "snapshot", "restore", "--from-corpus", str(parquet))
    assert result.exit_code == 0, result.output
    assert {(i, p) for i, p, _ in _statuses(ws.library_path)} == {
        ("a", "openalex"),
        ("x", "s2"),
    }


# ProviderMismatchError -> DataError (exit 2)


def test_provider_mismatch_error_es_exit_2() -> None:
    @click.command("boom")
    @handle_errors("boom")
    def boom() -> None:
        raise ProviderMismatchError("carriles distintos")

    result = CliRunner().invoke(boom, [])
    assert result.exit_code == 2
    assert "carriles distintos" in result.output


def test_code_for_provider_mismatch_es_exit_2() -> None:
    """La API de servicio aplica la misma política que la CLI (ADR 0053)."""
    from bib2graph.backends.base import ProviderMismatchError
    from bib2graph.service.errors import code_for

    assert code_for(ProviderMismatchError("otro carril")) == 2
