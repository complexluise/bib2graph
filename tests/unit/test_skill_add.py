"""Tests del comando ``b2g skill add`` (Epic #188).

Casos cubiertos:

Registro en el CLI:
  1. ``skill`` aparece en ``b2g --help``.
  2. ``skill add`` aparece en ``b2g skill --help``.

Instalación por scope:
  3. ``skill add --user`` escribe SKILL.md + reference/ciclo.md bajo
     ``<home>/.claude/skills/bib2graph/``.
  4. ``skill add --project`` escribe SKILL.md bajo
     ``<cwd>/.claude/skills/bib2graph/``.

Comportamiento de --force:
  5. Sin ``--force`` sobre destino existente → exit ≠ 0 + mensaje accionable.
  6. Con ``--force`` sobre destino existente → pisa y sale con exit 0.

Default scope:
  7. Sin flag de scope → comportamiento idéntico a ``--user``.

Envelope JSON:
  8. ``skill add --json`` emite envelope ``schema="1"`` válido en stdout
     (parseable, una sola línea).

Sin workspace:
  9. Corre OK en un directorio sin ``workspace.json``.

Version-lock (load-bearing):
  10. ``importlib.resources.files("bib2graph") / "skill" / "SKILL.md"``
      existe y es legible — garantiza que skill == paquete.

Anti-drift (load-bearing — sostiene la promesa central):
  11. Parsea el SKILL.md vendido, extrae todos los comandos invocados con
      prefijo ``b2g ``, y verifica que cada top-level y cada subcomando
      mencionado existen en el grupo ``b2g``.  Si SKILL.md menciona un
      verbo que el CLI no expone, este test falla.

Filosofía (AGENTS.md): se testea la FUNCIÓN detrás del comando cuando es
posible; CliRunner solo donde hay integración necesaria.
Marcador: ``unit`` (sin red ni DuckDB; operaciones de filesystem en tmp_path).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.cli.commands.skill import run_skill_add

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures compartidas
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """CliRunner (Click 8.2+ separa stdout/stderr por defecto)."""
    return CliRunner()


# ---------------------------------------------------------------------------
# 1. Registro: skill en b2g --help
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_aparece_en_b2g_help(runner: CliRunner) -> None:
    """``skill`` aparece listado en ``b2g --help``."""
    result = runner.invoke(b2g, ["--help"])
    assert result.exit_code == 0, f"b2g --help falló: {result.output!r}"
    assert "skill" in result.output, (
        "El grupo 'skill' no aparece en b2g --help. "
        "Verificá que skill_grp esté registrado en cli/__init__.py."
    )


# ---------------------------------------------------------------------------
# 2. Registro: skill add en b2g skill --help
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_aparece_en_skill_help(runner: CliRunner) -> None:
    """``skill add`` aparece listado en ``b2g skill --help``."""
    result = runner.invoke(b2g, ["skill", "--help"])
    assert result.exit_code == 0, f"b2g skill --help falló: {result.output!r}"
    assert "add" in result.output, "El subcomando 'add' no aparece en b2g skill --help."


# ---------------------------------------------------------------------------
# 3. Instalación --user
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_user_copia_archivos(tmp_path: Path) -> None:
    """``skill add --user`` copia SKILL.md + reference/ciclo.md bajo <home>/.claude/."""
    data = run_skill_add(scope="user", force=False, home=tmp_path)

    assert data["scope"] == "user"
    install_path = Path(data["install_path"])
    assert install_path == tmp_path / ".claude" / "skills" / "bib2graph"

    skill_md = install_path / "SKILL.md"
    ciclo_md = install_path / "reference" / "ciclo.md"

    assert skill_md.exists(), f"SKILL.md no fue copiado a {skill_md}"
    assert skill_md.stat().st_size > 0, "SKILL.md está vacío"
    assert ciclo_md.exists(), f"reference/ciclo.md no fue copiado a {ciclo_md}"


@pytest.mark.unit
def test_skill_add_user_via_cli(tmp_path: Path, runner: CliRunner) -> None:
    """``b2g skill add --user`` escribe SKILL.md bajo <tmp>/.claude/... (CliRunner)."""
    with patch.object(Path, "home", return_value=tmp_path):
        result = runner.invoke(b2g, ["skill", "add", "--user"], catch_exceptions=False)

    assert result.exit_code == 0, (
        f"Falló con exit {result.exit_code}: {result.output!r}"
    )
    skill_md = tmp_path / ".claude" / "skills" / "bib2graph" / "SKILL.md"
    assert skill_md.exists(), f"SKILL.md no fue instalado en {skill_md}"


# ---------------------------------------------------------------------------
# 4. Instalación --project
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_project_copia_archivos(tmp_path: Path) -> None:
    """``skill add --project`` copia SKILL.md bajo <cwd>/.claude/skills/bib2graph/."""
    data = run_skill_add(scope="project", force=False, cwd=tmp_path)

    assert data["scope"] == "project"
    install_path = Path(data["install_path"])
    assert install_path == tmp_path / ".claude" / "skills" / "bib2graph"

    skill_md = install_path / "SKILL.md"
    assert skill_md.exists(), f"SKILL.md no fue copiado a {skill_md}"


@pytest.mark.unit
def test_skill_add_project_via_cli(tmp_path: Path, runner: CliRunner) -> None:
    """``b2g skill add --project`` escribe SKILL.md bajo <cwd>/.claude/... (CliRunner)."""
    with patch.object(Path, "cwd", return_value=tmp_path):
        result = runner.invoke(
            b2g, ["skill", "add", "--project"], catch_exceptions=False
        )

    assert result.exit_code == 0, (
        f"Falló con exit {result.exit_code}: {result.output!r}"
    )
    skill_md = tmp_path / ".claude" / "skills" / "bib2graph" / "SKILL.md"
    assert skill_md.exists(), f"SKILL.md no fue instalado en {skill_md}"


# ---------------------------------------------------------------------------
# 5. Sin --force sobre destino existente → error accionable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_idempotente_noop(tmp_path: Path) -> None:
    """Re-correr con la versión vendida ya instalada → no-op (idempotente).

    Contrato ADR 0039 / API.md: sin --force, si ya está la versión vendida,
    no hace nada y lo reporta (no falla).
    """
    d1 = run_skill_add(scope="user", force=False, home=tmp_path)
    assert d1["installed"] is True
    assert d1["already_present"] is False

    d2 = run_skill_add(scope="user", force=False, home=tmp_path)
    assert d2["installed"] is False, "Re-correr idéntico debe ser no-op."
    assert d2["already_present"] is True
    assert d2["install_path"] == d1["install_path"]


@pytest.mark.unit
def test_skill_add_sin_force_destino_difiere_falla(tmp_path: Path) -> None:
    """Sin --force, si el destino existe y DIFIERE de la vendida → UsageError."""
    from bib2graph.cli._errors import UsageError

    # Primera instalación
    run_skill_add(scope="user", force=False, home=tmp_path)

    # Ensuciar la instalación para que difiera de la versión vendida
    installed = tmp_path / ".claude" / "skills" / "bib2graph" / "SKILL.md"
    installed.write_text(
        installed.read_text(encoding="utf-8") + "\n<!-- EDITADO -->\n",
        encoding="utf-8",
    )

    # Segunda instalación sin --force sobre destino divergente → debe fallar
    with pytest.raises(UsageError) as exc_info:
        run_skill_add(scope="user", force=False, home=tmp_path)

    assert "--force" in str(exc_info.value), (
        "El mensaje de error debe sugerir --force. "
        f"Mensaje obtenido: {exc_info.value!r}"
    )


@pytest.mark.unit
def test_skill_add_sin_force_via_cli_exit_no_cero(
    tmp_path: Path, runner: CliRunner
) -> None:
    """``b2g skill add`` sin --force sobre destino divergente → exit ≠ 0."""
    # Primera instalación OK
    with patch.object(Path, "home", return_value=tmp_path):
        r1 = runner.invoke(b2g, ["skill", "add", "--user"])
    assert r1.exit_code == 0

    # Ensuciar la instalación para que difiera
    installed = tmp_path / ".claude" / "skills" / "bib2graph" / "SKILL.md"
    installed.write_text(
        installed.read_text(encoding="utf-8") + "\n<!-- EDIT -->\n",
        encoding="utf-8",
    )

    # Segunda invocación sin --force → error
    with patch.object(Path, "home", return_value=tmp_path):
        r2 = runner.invoke(b2g, ["skill", "add", "--user"])
    assert r2.exit_code != 0, (
        "Se esperaba exit ≠ 0 cuando el destino difiere y no se pasa --force."
    )
    assert "--force" in r2.output or "--force" in (r2.stderr or ""), (
        "El mensaje de error no sugiere --force."
    )


# ---------------------------------------------------------------------------
# 6. Con --force sobre destino existente → pisa OK
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_force_pisa_destino(tmp_path: Path) -> None:
    """Con --force, pisa un destino divergente y restaura la versión vendida."""
    # Primera instalación
    run_skill_add(scope="user", force=False, home=tmp_path)
    install_path = tmp_path / ".claude" / "skills" / "bib2graph"
    skill_md = install_path / "SKILL.md"
    vendored = skill_md.read_text(encoding="utf-8")

    # Ensuciar la instalación
    skill_md.write_text(vendored + "\n<!-- JUNK -->\n", encoding="utf-8")

    # --force pisa → restaura exactamente la versión vendida
    data = run_skill_add(scope="user", force=True, home=tmp_path)
    assert data["installed"] is True
    assert Path(data["install_path"]).exists()
    assert skill_md.read_text(encoding="utf-8") == vendored, (
        "--force debe restaurar la versión vendida (sin restos de la edición)."
    )


@pytest.mark.unit
def test_skill_add_force_via_cli(tmp_path: Path, runner: CliRunner) -> None:
    """``b2g skill add --force`` pisa el destino y sale con exit 0 (CliRunner)."""
    # Primera instalación
    with patch.object(Path, "home", return_value=tmp_path):
        r1 = runner.invoke(b2g, ["skill", "add", "--user"])
    assert r1.exit_code == 0

    # Segunda con --force → debe salir 0
    with patch.object(Path, "home", return_value=tmp_path):
        r2 = runner.invoke(b2g, ["skill", "add", "--user", "--force"])
    assert r2.exit_code == 0, (
        f"--force debería pisar OK, pero falló con exit {r2.exit_code}: {r2.output!r}"
    )


# ---------------------------------------------------------------------------
# 7. Default scope → --user
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_default_scope_es_user(tmp_path: Path) -> None:
    """Sin flag de scope, run_skill_add usa scope='user' por defecto."""
    # Verificamos llamando la función directamente con scope="user"
    data_user = run_skill_add(scope="user", force=False, home=tmp_path)

    # Y llamando vía CLI sin flag de scope (usando patch de home)
    home2 = tmp_path / "home2"
    home2.mkdir()
    with patch.object(Path, "home", return_value=home2):
        runner = CliRunner()
        result = runner.invoke(b2g, ["skill", "add"], catch_exceptions=False)

    assert result.exit_code == 0
    # Debe instalar en home2/.claude/skills/bib2graph/ (scope user por defecto)
    expected = home2 / ".claude" / "skills" / "bib2graph" / "SKILL.md"
    assert expected.exists(), (
        f"El default scope no fue 'user': SKILL.md no encontrado en {expected}. "
        "Verificá que --user tenga default=True en el comando add."
    )
    # El path de data_user tampoco debe coincidir con project
    assert ".claude/skills" in data_user["install_path"].replace("\\", "/")


# ---------------------------------------------------------------------------
# 8. Envelope --json
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_json_envelope_valido(tmp_path: Path, runner: CliRunner) -> None:
    """``skill add --json`` emite envelope schema='1' válido en stdout (1 sola línea)."""
    with patch.object(Path, "home", return_value=tmp_path):
        result = runner.invoke(
            b2g, ["skill", "add", "--user", "--json"], catch_exceptions=False
        )

    assert result.exit_code == 0, f"Falló: {result.output!r}"

    # stdout debe tener exactamente una línea no vacía
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"Se esperaba 1 línea en stdout, se obtuvieron {len(lines)}:\n{result.stdout!r}"
    )

    envelope: dict[str, Any] = json.loads(lines[0])
    assert envelope.get("schema") == "1", (
        f"schema incorrecto: {envelope.get('schema')!r}"
    )
    assert envelope.get("ok") is True, f"ok debería ser True: {envelope!r}"
    assert envelope.get("command") == "skill add", (
        f"command incorrecto: {envelope.get('command')!r}"
    )
    assert envelope.get("exit_code") == 0

    data = envelope.get("data", {})
    assert "install_path" in data, f"data no contiene 'install_path': {data!r}"
    assert "scope" in data, f"data no contiene 'scope': {data!r}"
    assert data["scope"] == "user"


# ---------------------------------------------------------------------------
# 9. Sin workspace → OK
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_add_sin_workspace(tmp_path: Path, runner: CliRunner) -> None:
    """``skill add`` corre OK en un directorio sin workspace.json."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    # tmp_path no tiene workspace.json — debe funcionar igual
    with (
        patch.object(Path, "home", return_value=home_dir),
        runner.isolated_filesystem(temp_dir=tmp_path),
    ):
        result = runner.invoke(b2g, ["skill", "add", "--user"], catch_exceptions=False)

    assert result.exit_code == 0, (
        f"skill add falló sin workspace (exit {result.exit_code}): {result.output!r}"
    )


# ---------------------------------------------------------------------------
# 10. Version-lock (load-bearing)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_md_accesible_via_importlib_resources() -> None:
    """importlib.resources.files('bib2graph') / 'skill' / 'SKILL.md' existe y es legible.

    Garantía de que la skill vendida está incluida en el paquete instalado.
    Si este test falla, la instalación via 'b2g skill add' entregará un
    directorio vacío o fallará.
    """
    import importlib.resources as _res

    skill_path = _res.files("bib2graph") / "skill" / "SKILL.md"
    # Convertir a Path para poder usar .exists() y .read_text()
    skill_file = Path(str(skill_path))
    assert skill_file.exists(), (
        f"SKILL.md no encontrado en {skill_file}. "
        "Verificá que src/bib2graph/skill/ esté incluido en el paquete "
        "(pyproject.toml [tool.hatch.build.targets.wheel.force-include])."
    )
    content = skill_file.read_text(encoding="utf-8")
    assert len(content) > 100, (
        f"SKILL.md parece estar vacío o truncado (len={len(content)})."
    )
    assert "bib2graph" in content, "SKILL.md no contiene la palabra 'bib2graph'."


@pytest.mark.unit
def test_skill_reference_ciclo_accesible() -> None:
    """reference/ciclo.md también es accesible vía importlib.resources."""
    import importlib.resources as _res

    ciclo_path = _res.files("bib2graph") / "skill" / "reference" / "ciclo.md"
    ciclo_file = Path(str(ciclo_path))
    assert ciclo_file.exists(), (
        f"reference/ciclo.md no encontrado en {ciclo_file}. "
        "Verificá que src/bib2graph/skill/reference/ esté incluido en el paquete."
    )


# ---------------------------------------------------------------------------
# 11. Anti-drift (load-bearing — sostiene la promesa central)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_skill_md_anti_drift_comandos_en_cli() -> None:
    """Todos los verbos b2g mencionados en SKILL.md están registrados en el CLI.

    Parsea el SKILL.md vendido, extrae todos los patrones ``b2g <cmd> [<subcmd>]``
    (ignorando flags ``--foo`` y placeholders ``<...>``), y verifica que:
    - Cada ``<cmd>`` de primer nivel está en ``b2g.commands``.
    - Cada ``<subcmd>`` (cuando existe y es un token-palabra) está en el grupo
      correspondiente.

    Si SKILL.md menciona un verbo que el CLI no expone, este test FALLA.
    Esto impide que el skill describa comandos inexistentes (drift).
    """
    import importlib.resources as _res

    # 1. Leer SKILL.md
    skill_path = Path(str(_res.files("bib2graph") / "skill" / "SKILL.md"))
    text = skill_path.read_text(encoding="utf-8")

    # 2. Extraer patrones: b2g <word> [<word>]
    #    \w+ captura solo chars de palabra (a-z, A-Z, 0-9, _) — filtra
    #    automáticamente flags (--foo) y placeholders (<...>).
    #    [ \t] (no \s) para NO cruzar saltos de línea: con \s, "b2g build\nb2g
    #    read" capturaría (build, b2g) — el subcomando debe estar en la misma línea.
    pattern = re.compile(r"b2g[ \t]+(\w+)(?:[ \t]+(\w+))?")
    raw_matches = pattern.findall(text)

    assert raw_matches, (
        "No se encontraron patrones 'b2g <cmd>' en SKILL.md. "
        "¿El SKILL.md fue vaciado o la regex rota?"
    )

    # 3. Construir el conjunto único de (cmd, subcmd) a verificar
    to_check: set[tuple[str, str]] = set()
    for cmd, subcmd in raw_matches:
        # cmd nunca puede ser vacío dado el regex; subcmd puede ser ''
        to_check.add((cmd, subcmd))

    # 4. Verificar contra b2g.commands
    b2g_cmds: dict[str, Any] = b2g.commands  # type: ignore[attr-defined]

    for cmd, subcmd in sorted(to_check):
        assert cmd in b2g_cmds, (
            f"Comando top-level '{cmd}' mencionado en SKILL.md no está "
            f"registrado en el grupo b2g. "
            f"Comandos registrados: {sorted(b2g_cmds.keys())}. "
            "Actualizá SKILL.md o registrá el comando."
        )
        if subcmd:
            group_obj = b2g_cmds[cmd]
            # Obtener subcomandos si el objeto es un grupo Click
            sub_cmds: dict[str, Any] = getattr(group_obj, "commands", {})
            assert subcmd in sub_cmds, (
                f"Subcomando '{cmd} {subcmd}' mencionado en SKILL.md no está "
                f"registrado. Subcomandos de '{cmd}': {sorted(sub_cmds.keys())}. "
                "Actualizá SKILL.md o registrá el subcomando."
            )
