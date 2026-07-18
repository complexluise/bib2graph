"""cli.commands.skill — Grupo noun-verb ``b2g skill`` (Epic #188, ADR 0046/#193).

Gestión de la skill vendida de bib2graph para agentes de código.

  ``skill add``       — instala la skill en el directorio de skills del
                        ``--provider`` elegido (default ``claude-code``),
                        scope ``--user`` (default) o ``--project``.
  ``skill providers`` — lista los providers soportados (introspección agente).

La skill reside en ``src/bib2graph/skill/`` y se localiza vía
``importlib.resources.files("bib2graph") / "skill"`` con fallback a la ruta
relativa a ``__file__`` (árbol de desarrollo).

Distribución agnóstica del proveedor (ADR 0046, enmienda al ADR 0039):
  El provider se modela como un **dato** (``_Provider``), no como ramas
  ``if provider == ...``. Cada provider fija dónde vive la skill en scope
  ``--project``/``--user`` y una ``transform`` sobre el contenido (en la 1ª
  iteración, siempre identidad — ``copytree`` tal cual). Agregar un provider
  de copia-identidad es agregar una fila a ``_PROVIDERS``, no una rama nueva.

Flags de ``skill add``:
  --provider            Cliente destino (``claude-code`` default, ``opencode``).
  --user / --project     Scope de instalación (mutuamente excluyentes vía
                        ``flag_value``; default ``--user``).
  --force               Pisar el destino si ya existe.

Comportamiento (idempotente — contrato en ADR 0039/0046 / API.md):
  - Destino no existe → instala.
  - Destino existe e **idéntico** a la versión vendida → **no-op**, exit 0, lo
    reporta (``already_present=True``). Re-correr el comando es seguro.
  - Destino existe y **difiere** (edición del usuario u otra versión), sin
    ``--force`` → ``UsageError`` (exit 1) que sugiere ``--force``.
  - Con ``--force`` → pisa (``shutil.rmtree`` + ``shutil.copytree``).
  - **NO requiere workspace** (es comando meta global; no llama a
    ``resolve_workspace``).
  - Emite envelope ``--json`` ``schema="1"`` con ``install_path``, ``scope``,
    ``provider``, ``installed`` y ``already_present``.
  - Sin transición de FSM (operación transversal al lazo, como ``gui``).
  - **Version-lock (ADR 0039 M2, preservado por 0046):** el ``--provider``
    cambia SOLO el destino (y, en fase 2, la forma); la skill siempre viaja
    en el wheel instalado, nunca se descarga de otra fuente.
"""

from __future__ import annotations

import filecmp
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import UsageError, handle_errors
from bib2graph.cli._options import json_mode, json_option

# Provider-como-dato (ADR 0046)


@dataclass(frozen=True)
class _Provider:
    """Un cliente de agentes soportado por ``skill add``.

    ``project_root``/``user_root`` son rutas RELATIVAS (al cwd y al home,
    respectivamente); se resuelven en ``run_skill_add``. ``transform`` es
    ``None`` en la 1ª iteración (ADR 0046): copia-identidad vía
    ``copytree``. Un provider con transformación real (fase 2, p. ej.
    ``agents-md``) fijaría acá una función de transformación de contenido.
    """

    name: str
    project_root: Path
    user_root_parts: tuple[str, ...]  # partes relativas a Path.home()
    description: str


_PROVIDERS: dict[str, _Provider] = {
    "claude-code": _Provider(
        name="claude-code",
        project_root=Path(".claude") / "skills" / "bib2graph",
        user_root_parts=(".claude", "skills", "bib2graph"),
        description="Claude Code (Anthropic) — .claude/skills/bib2graph/ (default).",
    ),
    "opencode": _Provider(
        name="opencode",
        project_root=Path(".opencode") / "skills" / "bib2graph",
        user_root_parts=(".config", "opencode", "skills", "bib2graph"),
        description=(
            "OpenCode — .opencode/skills/bib2graph/. Comodidad: OpenCode ya lee "
            ".claude/skills/ de todos modos (mismo SKILL.md, sin transformación)."
        ),
    ),
}

DEFAULT_PROVIDER: str = "claude-code"


def _resolve_dest(provider: _Provider, scope: str, *, cwd: Path, home: Path) -> Path:
    """Resuelve el directorio destino para ``(provider, scope)`` (ADR 0046).

    Args:
        provider: Dato del provider elegido.
        scope: ``"user"`` o ``"project"``.
        cwd: Directorio de trabajo (para scope ``"project"``).
        home: Directorio home (para scope ``"user"``).

    Returns:
        Ruta absoluta al directorio destino de instalación.
    """
    if scope == "user":
        return home.joinpath(*provider.user_root_parts)
    return cwd / provider.project_root


# Helpers internos


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


# Resumen "a grandes rasgos" de cómo opera bib2graph, para que un agente de
# CUALQUIER proveedor (no solo Claude Code) sepa qué es esto y vaya al SKILL.md.
_HOW_IT_WORKS = (
    "bib2graph entrevista al investigador y corre el ciclo de forrajeo "
    "seed→chain→build→read (one-shot o profundizando), priorizando candidatos "
    "por estructura de citación (determinista, sin IA). El SKILL.md trae la "
    "entrevista y cómo operar cada paso."
)


def _build_result(
    dest: Path,
    scope: str,
    provider: str,
    *,
    installed: bool,
    already_present: bool,
) -> dict[str, Any]:
    """Arma el dict de resultado de ``skill add``.

    Incluye las rutas que un agente necesita para **leer** la skill —``skill_md``
    y ``reference_dir``— y el resumen ``how_to``, de modo que un agente agnóstico
    al proveedor pueda auto-onboardearse desde la salida ``--json`` sin depender
    del mecanismo de descubrimiento de Claude Code.
    """
    return {
        "install_path": str(dest),
        "scope": scope,
        "provider": provider,
        "installed": installed,
        "already_present": already_present,
        "skill_md": str(dest / "SKILL.md"),
        "reference_dir": str(dest / "reference"),
        "how_to": _HOW_IT_WORKS,
    }


def run_skill_add(
    *,
    scope: str,
    force: bool,
    provider: str = DEFAULT_PROVIDER,
    cwd: Path | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Instala la skill de bib2graph en el directorio de skills del provider.

    Args:
        scope: ``"user"`` (instala en la raíz global del provider) o
               ``"project"`` (instala en ``<cwd>/<project_root del provider>``).
        force: Si ``True``, pisa el destino si ya existe.
        provider: Cliente destino (``"claude-code"`` default, ``"opencode"``).
            Ver ``_PROVIDERS`` (ADR 0046) — el provider es un dato, no una
            rama de control; agregar uno nuevo de copia-identidad es agregar
            una fila a la tabla.
        cwd: Directorio de trabajo para el scope ``"project"`` (inyectable
             en tests; default: ``Path.cwd()``).
        home: Directorio home para el scope ``"user"`` (inyectable en tests;
              default: ``Path.home()``).

    Returns:
        Dict con ``install_path``, ``scope``, ``provider``, ``installed``
        (``True`` si copió/pisó, ``False`` si fue no-op), ``already_present``
        (``True`` si la versión vendida ya estaba), y —para que un agente
        sepa dónde leerla— ``skill_md`` (ruta al SKILL.md), ``reference_dir``
        y ``how_to`` (resumen).

    Raises:
        UsageError: Si ``provider`` no está soportado, o si el destino
            existe, **difiere** de la versión vendida y ``force=False``.
        RuntimeError: Si no se puede localizar el directorio de la skill.
    """
    if provider not in _PROVIDERS:
        raise UsageError(
            f"Provider '{provider}' no soportado. "
            f"Providers disponibles: {sorted(_PROVIDERS)}. "
            "Corré `b2g skill providers` para ver la lista completa."
        )

    effective_home = home if home is not None else Path.home()
    effective_cwd = cwd if cwd is not None else Path.cwd()

    provider_data = _PROVIDERS[provider]
    dest = _resolve_dest(provider_data, scope, cwd=effective_cwd, home=effective_home)

    source = _locate_skill_source()

    # Idempotencia: si ya está exactamente la versión vendida → no-op.
    if dest.exists() and _trees_identical(source, dest):
        return _build_result(
            dest, scope, provider, installed=False, already_present=True
        )

    # Existe pero difiere (edición del usuario u otra versión): exige --force.
    if dest.exists() and not force:
        raise UsageError(
            f"El destino ya existe y difiere de la versión vendida: {dest}. "
            "Usá --force para pisar la instalación existente."
        )

    if dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    return _build_result(dest, scope, provider, installed=True, already_present=False)


def run_skill_providers() -> dict[str, Any]:
    """Enumera los providers soportados por ``skill add`` (ADR 0046, #193).

    Comando meta introspectable: un agente puede descubrir qué clientes
    puede targetear sin leer el código ni la documentación.

    Returns:
        Dict con ``providers``: lista de dicts ``{name, default, description,
        project_root, user_root}`` (rutas relativas, tal como se resuelven
        contra cwd/home) y ``default_provider``.
    """
    providers = []
    for name, data in _PROVIDERS.items():
        providers.append(
            {
                "name": name,
                "default": name == DEFAULT_PROVIDER,
                "description": data.description,
                "project_root": str(data.project_root).replace("\\", "/"),
                "user_root": "~/" + "/".join(data.user_root_parts),
            }
        )
    return {
        "providers": providers,
        "default_provider": DEFAULT_PROVIDER,
    }


# Grupo raíz


@click.group("skill", invoke_without_command=True)
@click.pass_context
def skill_grp(ctx: click.Context) -> None:
    """Gestión de la skill de bib2graph para agentes de código.

    Subcomandos: add, providers.

    Ejemplos:
        b2g skill add
        b2g skill add --project
        b2g skill add --provider opencode
        b2g skill add --force
        b2g skill providers
    """
    ctx.ensure_object(dict)
    # Click 8.4: no_args_is_help=True en grupos termina con exit 2.
    # Usamos invoke_without_command=True + check manual para exit 0 correcto.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# skill add


@skill_grp.command("add")
@click.option(
    "--provider",
    "provider",
    type=click.Choice(sorted(_PROVIDERS)),
    default=DEFAULT_PROVIDER,
    show_default=True,
    help="Cliente destino de la instalación (ADR 0046).",
)
@click.option(
    "--user",
    "scope",
    flag_value="user",
    default=True,
    help="Instala la skill en la raíz global del provider (default).",
)
@click.option(
    "--project",
    "scope",
    flag_value="project",
    help="Instala la skill en <cwd>/<ruta de proyecto del provider>.",
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
    provider: str,
    scope: str,
    force: bool,
    json_output: bool,
) -> None:
    """Instala la skill de bib2graph en el directorio de skills del provider.

    Por defecto usa el provider ``claude-code`` e instala en
    ~/.claude/skills/bib2graph/ (scope --user). Con --project instala en
    <cwd>/.claude/skills/bib2graph/. Con --provider opencode instala en la
    ruta nativa de OpenCode (.opencode/skills/bib2graph/).

    Es idempotente: si la versión vendida ya está instalada, no hace nada y lo
    reporta. Si el destino existe pero difiere, use --force para pisarlo.
    """
    data = run_skill_add(scope=scope, force=force, provider=provider)

    if json_mode(json_output):
        envelope = build_envelope(
            command="skill add",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        estado = (
            "Skill ya instalada (versión vendida)"
            if data["already_present"]
            else "Skill instalada"
        )
        # Salida explícita y agnóstica al proveedor: dónde quedó el artículo,
        # cómo opera bib2graph a grandes rasgos, y la instrucción de leerlo
        # (cualquier agente, no solo Claude Code, puede auto-onboardearse así).
        emit_human(
            f"{estado} ({data['provider']}) en: {data['install_path']}\n"
            "\n"
            "Cómo opera bib2graph (a grandes rasgos):\n"
            f"  {data['how_to']}\n"
            "\n"
            "Agente (cualquier proveedor): leé este archivo para operar bib2graph →\n"
            f"  {data['skill_md']}\n"
            f"  (marco teórico en {data['reference_dir']}/ciclo.md)"
        )


# skill providers


@skill_grp.command("providers")
@json_option
@handle_errors("skill providers")
def providers_cmd(json_output: bool) -> None:
    """Lista los providers soportados por ``skill add`` (ADR 0046, #193).

    Comando meta e introspectable: no requiere workspace ni transiciona FSM.
    """
    data = run_skill_providers()

    if json_mode(json_output):
        envelope = build_envelope(
            command="skill providers",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Providers soportados ({len(data['providers'])}):")
        for p in data["providers"]:
            marca = " (default)" if p["default"] else ""
            emit_human(f"  {p['name']}{marca}")
            emit_human(f"    project: {p['project_root']}")
            emit_human(f"    user:    {p['user_root']}")
            emit_human(f"    {p['description']}")
