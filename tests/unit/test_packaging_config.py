"""Guard de regresión del empaquetado — config del wheel en pyproject.toml.

Cubre dos invariantes:

1. ``force-include`` mapea ``src/bib2graph/gui/static`` → ``bib2graph/gui/static``
   (frontend GUI, gitignored; ADR 0028 §B.1, G5). Sin esa clave hatchling omite
   el frontend y el wheel sale sin GUI.
2. La skill vendida (``src/bib2graph/skill/``, Epic #188) es **fuente commiteada**
   bajo el paquete → la incluye ``packages = ["src/bib2graph"]``. NO debe estar en
   ``force-include``: duplicarla rompe el build ("A second file is being added to
   the wheel archive at the same path"). ``b2g skill add`` la lee vía
   ``importlib.resources.files('bib2graph') / 'skill'``.

Esto es un **guard de config**, no un build real.

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


@pytest.mark.unit
def test_skill_es_fuente_commiteada_no_force_include() -> None:
    """La skill se incluye por ``packages``, NO por ``force-include`` (Epic #188).

    La skill vive bajo ``src/bib2graph/skill/`` (fuente commiteada), así que
    ``packages = ["src/bib2graph"]`` ya la vendea en el wheel. Si alguien la
    agrega a ``force-include``, hatchling la duplica y el build falla con
    "A second file is being added to the wheel archive at the same path".
    Este guard fija que NO esté en force-include y que el SKILL.md exista.
    """
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
    assert "src/bib2graph/skill" not in force, (
        "src/bib2graph/skill NO debe estar en force-include: ya entra por "
        "packages=['src/bib2graph'] y duplicarla rompe el build (doble inclusión)."
    )

    # La skill debe existir como fuente commiteada para que packages la incluya.
    skill_md = _PYPROJECT.parent / "src" / "bib2graph" / "skill" / "SKILL.md"
    assert skill_md.exists(), (
        f"No existe {skill_md}. La skill vendida debe vivir bajo "
        "src/bib2graph/skill/ para que el wheel la incluya vía packages."
    )
