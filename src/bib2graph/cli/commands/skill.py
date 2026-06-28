"""cli.commands.skill — Grupo noun-verb ``b2g skill`` (Epic #188).

Gestión de la skill vendida de bib2graph para Claude.

  ``skill add`` — instala la skill en ~/.claude/skills/bib2graph/ (scope
                 ``--user``, default) o en <cwd>/.claude/skills/bib2graph/
                 (scope ``--project``).

La skill reside en ``src/bib2graph/skill/`` y se localiza vía
``importlib.resources.files("bib2graph") / "skill"`` con fallback a la ruta
relativa a ``__file__`` (árbol de desarrollo).

Flags de ``skill add``:
  --user / --project   Scope de instalación (mutuamente excluyentes vía
                       ``flag_value``; default ``--user``).
  --force              Pisar el destino si ya existe.

Comportamiento (idempotente — contrato en ADR 0039 / API.md):
  - Destino no existe → instala.
  - Destino existe e **idéntico** a la versión vendida → **no-op**, exit 0, lo
    reporta (``already_present=True``). Re-correr el comando es seguro.
  - Destino existe y **difiere** (edición del usuario u otra versión), sin
    ``--force`` → ``UsageError`` (exit 1) que sugiere ``--force``.
  - Con ``--force`` → pisa (``shutil.rmtree`` + ``shutil.copytree``).
  - **NO requiere workspace** (es comando meta global; no llama a
    ``resolve_workspace``).
  - Emite envelope ``--json`` ``schema="1"`` con ``install_path``, ``scope``,
    ``installed`` y ``already_present``.
  - Sin transición de FSM (operación transversal al lazo, como ``gui``).
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import UsageError, handle_errors
from bib2graph.cli._options import json_mode, json_option

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _locate_skill_source() -> Path:
    """Localiza el directorio de la skill vendida en el paquete instalado.

    Intenta primero con ``importlib.resources.files`` (funciona en editable
    install y en wheel instalado).  Si no existe o falla, usa un fallback
    relativo a ``__file__`` (árbol de desarrollo).

    Returns:
        Path al directorio ``skill/`` que contiene ``SKILL.md`` y
        ``reference/``.

    Raises:
        RuntimeError: Si no se puede localizar el directorio en ninguna de
            las dos rutas intentadas.
    """
    import importlib.resources as _res

    # Primario: importlib.resources — funciona tanto en editable install
    # (apunta a src/bib2graph/) como en wheel instalado.
    try:
        skill_dir = Path(str(_res.files("bib2graph"))) / "skill"
        if skill_dir.exists() and (skill_dir / "SKILL.md").exists():
            return skill_dir
    except Exception:
        pass

    # Fallback: árbol de fuentes relativo a este archivo.
    # Ruta: cli/commands/skill.py → cli/ → bib2graph/ → skill/
    fallback = Path(__file__).parent.parent.parent / "skill"
    if fallback.exists() and (fallback / "SKILL.md").exists():
        return fallback

    raise RuntimeError(
        "No se puede localizar el directorio de la skill vendida. "
        "Verificá que el paquete bib2graph esté instalado correctamente "
        "(src/bib2graph/skill/ debe contener SKILL.md)."
    )


def _trees_identical(a: Path, b: Path) -> bool:
    """True si ``a`` y ``b`` tienen los mismos archivos con idéntico contenido.

    Comparación **por contenido** (``shallow=False``), recursiva. Si difiere
    cualquier archivo, falta o sobra alguno, devuelve ``False``. Es la base de
    la idempotencia: ``skill add`` es no-op solo si lo instalado coincide
    exactamente con la versión vendida.
    """
    cmp = filecmp.dircmp(str(a), str(b))
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(
        str(a), str(b), cmp.common_files, shallow=False
    )
    if mismatch or errors:
        return False
    return all(_trees_identical(a / sub, b / sub) for sub in cmp.common_dirs)


def run_skill_add(
    *,
    scope: str,
    force: bool,
    cwd: Path | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Instala la skill de bib2graph en el directorio de Claude.

    Args:
        scope: ``"user"`` (instala en ``~/.claude/skills/bib2graph/``) o
               ``"project"`` (instala en ``<cwd>/.claude/skills/bib2graph/``).
        force: Si ``True``, pisa el destino si ya existe.
        cwd: Directorio de trabajo para el scope ``"project"`` (inyectable
             en tests; default: ``Path.cwd()``).
        home: Directorio home para el scope ``"user"`` (inyectable en tests;
              default: ``Path.home()``).

    Returns:
        Dict con ``"install_path"`` (ruta absoluta), ``"scope"``, ``"installed"``
        (``True`` si copió/pisó, ``False`` si fue no-op) y ``"already_present"``
        (``True`` si la versión vendida ya estaba instalada).

    Raises:
        UsageError: Si el destino existe, **difiere** de la versión vendida y
            ``force=False``.
        RuntimeError: Si no se puede localizar el directorio de la skill.
    """
    effective_home = home if home is not None else Path.home()
    effective_cwd = cwd if cwd is not None else Path.cwd()

    if scope == "user":
        dest = effective_home / ".claude" / "skills" / "bib2graph"
    else:
        dest = effective_cwd / ".claude" / "skills" / "bib2graph"

    source = _locate_skill_source()

    # Idempotencia: si ya está exactamente la versión vendida → no-op.
    if dest.exists() and _trees_identical(source, dest):
        return {
            "install_path": str(dest),
            "scope": scope,
            "installed": False,
            "already_present": True,
        }

    # Existe pero difiere (edición del usuario u otra versión): exige --force.
    if dest.exists() and not force:
        raise UsageError(
            f"El destino ya existe y difiere de la versión vendida: {dest}. "
            "Usá --force para pisar la instalación existente."
        )

    if dest.exists():
        shutil.rmtree(dest)

    shutil.copytree(source, dest)

    return {
        "install_path": str(dest),
        "scope": scope,
        "installed": True,
        "already_present": False,
    }


# ---------------------------------------------------------------------------
# Grupo raíz
# ---------------------------------------------------------------------------


@click.group("skill", invoke_without_command=True)
@click.pass_context
def skill_grp(ctx: click.Context) -> None:
    """Gestión de la skill de bib2graph para Claude.

    Subcomandos: add.

    Ejemplos:
        b2g skill add
        b2g skill add --project
        b2g skill add --force
    """
    ctx.ensure_object(dict)
    # Click 8.4: no_args_is_help=True en grupos termina con exit 2.
    # Usamos invoke_without_command=True + check manual para exit 0 correcto.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# skill add
# ---------------------------------------------------------------------------


@skill_grp.command("add")
@click.option(
    "--user",
    "scope",
    flag_value="user",
    default=True,
    help="Instala la skill en ~/.claude/skills/bib2graph/ (default).",
)
@click.option(
    "--project",
    "scope",
    flag_value="project",
    help="Instala la skill en <cwd>/.claude/skills/bib2graph/.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Pisar el destino si ya existe.",
)
@json_option
@click.pass_context
@handle_errors("skill add")
def add_cmd(
    ctx: click.Context,
    scope: str,
    force: bool,
    json_output: bool,
) -> None:
    """Instala la skill de bib2graph en el directorio de Claude.

    Por defecto instala en ~/.claude/skills/bib2graph/ (scope --user).
    Con --project instala en <cwd>/.claude/skills/bib2graph/.

    Es idempotente: si la versión vendida ya está instalada, no hace nada y lo
    reporta. Si el destino existe pero difiere, use --force para pisarlo.
    """
    data = run_skill_add(scope=scope, force=force)

    if json_mode(json_output):
        envelope = build_envelope(
            command="skill add",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    elif data["already_present"]:
        emit_human(
            f"Skill ya instalada (versión vendida) en: {data['install_path']} "
            "— nada que hacer."
        )
    else:
        emit_human(f"Skill instalada en: {data['install_path']}")
