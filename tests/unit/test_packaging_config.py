"""Guard de regresión del empaquetado G5 — config ``force-include`` en pyproject.toml.

Verifica que la clave ``tool.hatch.build.targets.wheel.force-include`` existe y
mapea ``src/bib2graph/gui/static`` al destino esperado dentro del wheel.

Esto es un **guard de config**, no un build real: comprueba que nadie eliminó
accidentalmente la clave que vendorea el frontend al wheel (ADR 0028 §B.1, G5).
Sin esta clave, hatchling omite ``gui/static/`` (gitignored) y el wheel sale sin
frontend aunque ``pnpm build`` haya corrido.

Marcador: ``unit`` (puro, sin I/O de build).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PYPROJECT = Path(__file__).parent.parent.parent / "pyproject.toml"


@pytest.mark.unit
def test_force_include_clave_presente() -> None:
    """pyproject.toml declara force-include para gui/static (guard ADR 0028 §B.1)."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(_PYPROJECT, "rb") as fh:
        cfg = tomllib.load(fh)

    force = (
        cfg.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    assert force, (
        "tool.hatch.build.targets.wheel.force-include está vacío o ausente. "
        "Sin esta clave hatchling omite gui/static/ (gitignored) y el wheel "
        "sale sin frontend (ADR 0028 §B.1, G5)."
    )


@pytest.mark.unit
def test_force_include_mapea_gui_static() -> None:
    """force-include mapea 'src/bib2graph/gui/static' → 'bib2graph/gui/static'."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(_PYPROJECT, "rb") as fh:
        cfg = tomllib.load(fh)

    force = (
        cfg.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    src_key = "src/bib2graph/gui/static"
    dest_val = "bib2graph/gui/static"
    assert src_key in force, (
        f"force-include no tiene la clave '{src_key}'. "
        "Verificar pyproject.toml [tool.hatch.build.targets.wheel.force-include]."
    )
    assert force[src_key] == dest_val, (
        f"force-include['{src_key}'] = '{force[src_key]}', se esperaba '{dest_val}'. "
        "El destino dentro del wheel debe ser 'bib2graph/gui/static'."
    )
