"""Tests del decorador compartido ``json_option`` y helper ``json_mode``.

Cubre (DoD sub-issue #151):
  1. Helpers ``_env_truthy`` y ``json_mode`` — lógica pura.
  2. Flag ``--json`` (post-verbo): stdout exactamente una línea JSON válida,
     ``schema == "1"``.
  3. Env var ``B2G_JSON=1`` sin flag: activa el mismo comportamiento.
  4. Precedencia: flag gana; ``B2G_JSON`` activa sin flag.
  5. Camino de ERROR con ``--json``: stdout = una línea envelope ``ok=False``.
  6. Anti-regresión: en modo JSON, stdout NUNCA más de una línea.
  7. Borde SIN envelope: error de parseo Click → stderr, stdout vacío.

Estrategia: la mayoría de comandos se llaman sin workspace activo (no hay
``workspace.json`` en el cwd del runner aislado) → ``UsageError`` →
``handle_errors`` emite el envelope de error → exactamente una línea en stdout.
Para ``init`` se prueba el camino exitoso porque crea su propio workspace.

Nota: Click 8.4+ provee ``result.stdout`` y ``result.stderr`` como streams
separados; ``result.stdout`` mezcla ambos.  Todos los asserts sobre stdout
usan ``result.stdout``.

Marcador: ``unit`` (sin red ni DuckDB persistente; el runner usa filesystem
aislado temporal).
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g
from bib2graph.cli._options import _env_truthy, json_mode

# ---------------------------------------------------------------------------
# 1. Helpers puros — _env_truthy y json_mode
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnvTruthy:
    """Verifica valores truthy/falsy reconocidos por ``_env_truthy``."""

    def test_valor_1_es_truthy(self) -> None:
        with patch.dict(os.environ, {"_B2G_TEST_VAR": "1"}):
            assert _env_truthy("_B2G_TEST_VAR") is True

    def test_valor_true_es_truthy(self) -> None:
        with patch.dict(os.environ, {"_B2G_TEST_VAR": "true"}):
            assert _env_truthy("_B2G_TEST_VAR") is True

    def test_valor_yes_es_truthy(self) -> None:
        with patch.dict(os.environ, {"_B2G_TEST_VAR": "yes"}):
            assert _env_truthy("_B2G_TEST_VAR") is True

    def test_mayusculas_son_truthy(self) -> None:
        with patch.dict(os.environ, {"_B2G_TEST_VAR": "TRUE"}):
            assert _env_truthy("_B2G_TEST_VAR") is True

    def test_valor_0_es_falsy(self) -> None:
        with patch.dict(os.environ, {"_B2G_TEST_VAR": "0"}):
            assert _env_truthy("_B2G_TEST_VAR") is False

    def test_variable_ausente_es_falsy(self) -> None:
        # Asegura que la variable no existe en el entorno
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("_B2G_TEST_VAR", None)
            assert _env_truthy("_B2G_TEST_VAR") is False

    def test_valor_vacio_es_falsy(self) -> None:
        with patch.dict(os.environ, {"_B2G_TEST_VAR": ""}):
            assert _env_truthy("_B2G_TEST_VAR") is False


@pytest.mark.unit
class TestJsonMode:
    """Verifica la lógica de precedencia de ``json_mode``."""

    def test_flag_local_activa_json(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("B2G_JSON", None)
            assert json_mode(True) is True

    def test_env_var_activa_json_sin_flag(self) -> None:
        with patch.dict(os.environ, {"B2G_JSON": "1"}):
            assert json_mode(False) is True

    def test_ninguno_retorna_false(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("B2G_JSON", None)
            assert json_mode(False) is False

    def test_flag_y_env_var_retornan_true(self) -> None:
        """Con ambos activos, el resultado sigue siendo True."""
        with patch.dict(os.environ, {"B2G_JSON": "1"}):
            assert json_mode(True) is True

    def test_env_var_false_sin_flag_retorna_false(self) -> None:
        with patch.dict(os.environ, {"B2G_JSON": "0"}):
            assert json_mode(False) is False

    def test_env_var_true_string_activa_json(self) -> None:
        with patch.dict(os.environ, {"B2G_JSON": "true"}):
            assert json_mode(False) is True

    def test_env_var_yes_activa_json(self) -> None:
        with patch.dict(os.environ, {"B2G_JSON": "yes"}):
            assert json_mode(False) is True


# ---------------------------------------------------------------------------
# 2. Helpers de test para CliRunner
# ---------------------------------------------------------------------------


def _assert_one_json_line(stdout: str, *, schema: str = "1") -> dict:
    """Aserta que stdout es exactamente una línea JSON con ``schema`` correcto.

    Returns:
        El dict parseado para asserts adicionales.
    """
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"Se esperaba exactamente 1 línea en stdout, se obtuvieron {len(lines)}:\n"
        f"{stdout!r}"
    )
    data = json.loads(lines[0])
    assert data.get("schema") == schema, (
        f"schema esperado '{schema}', obtenido {data.get('schema')!r}"
    )
    return data


# ---------------------------------------------------------------------------
# 3. Parametrizado sobre comandos que emiten envelope
#    (camino de error: sin workspace → UsageError → error envelope)
# ---------------------------------------------------------------------------

# Comandos y sus argumentos mínimos para pasar la validación de Click.
# Todos fallarán en el interior (no hay workspace) → handle_errors →
# envelope de error (ok=False) → una línea en stdout.
_CMDS_NO_WORKSPACE: list[list[str]] = [
    ["status", "--json"],
    ["validate", "--json"],
    ["inspect", "--json"],
    ["build", "--json"],
    ["export", "--json"],
    ["snapshot", "--json"],
    ["chain", "--json"],
    ["filter", "--json"],
    ["enrich", "--json"],
    ["monitor", "--json"],
    ["resolve", "--json"],
    ["accept", "--ids", "DUMMY_ID", "--json"],
    ["reject", "--ids", "DUMMY_ID", "--json"],
    ["curate", "--dump", "--json"],
    ["restore", "--from-corpus", "nonexistent.parquet", "--json"],
    ["seed", "--equation", "test query", "--json"],
    ["thesaurus", "--from", "nonexistent.json", "--json"],
]


@pytest.mark.unit
@pytest.mark.parametrize("cmd_args", _CMDS_NO_WORKSPACE)
def test_json_flag_stdout_una_linea_envelope(cmd_args: list[str]) -> None:
    """Con ``--json``, stdout es exactamente una línea de envelope JSON válido."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, cmd_args, catch_exceptions=False)
    stdout = result.stdout
    _assert_one_json_line(stdout)


@pytest.mark.unit
@pytest.mark.parametrize("cmd_args", _CMDS_NO_WORKSPACE)
def test_b2g_json_env_var_stdout_una_linea_envelope(cmd_args: list[str]) -> None:
    """Con ``B2G_JSON=1`` sin flag ``--json``, stdout es una línea de envelope."""
    # args sin --json (quitarlo si está presente)
    args_sin_json = [a for a in cmd_args if a != "--json"]
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g, args_sin_json, env={"B2G_JSON": "1"}, catch_exceptions=False
        )
    stdout = result.stdout
    _assert_one_json_line(stdout)


# ---------------------------------------------------------------------------
# 4. Comando init — camino exitoso
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_init_json_happy_path_stdout_una_linea() -> None:
    """``b2g init <dir> --json`` exitoso: stdout = una línea envelope ok=True."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["init", "mi-ws", "--json"], catch_exceptions=False)
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "init"
    assert data["exit_code"] == 0


@pytest.mark.unit
def test_init_b2g_json_env_var_happy_path() -> None:
    """``b2g init <dir>`` con ``B2G_JSON=1``: stdout = una línea envelope ok=True."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g, ["init", "mi-ws"], env={"B2G_JSON": "1"}, catch_exceptions=False
        )
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# 5. Camino de ERROR — error envelope en stdout (ok=False)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_error_envelope_stdout_ok_false_sin_workspace() -> None:
    """Comando sin workspace → UsageError → envelope ok=False en stdout."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["status", "--json"], catch_exceptions=False)
    data = _assert_one_json_line(result.stdout)
    assert data["ok"] is False
    assert "error" in data
    assert data["error"] is not None


@pytest.mark.unit
def test_error_modo_humano_stderr_no_stdout() -> None:
    """Modo humano: error va a stderr, NO a stdout."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["status"], catch_exceptions=False)
    # stdout debe estar vacío (el mensaje de error fue a stderr)
    assert result.stdout.strip() == "", (
        f"stdout debería estar vacío en modo humano-error, obtuvo: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# 6. Precedencia
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_precedencia_flag_sin_env_var() -> None:
    """``--json`` explícito activa JSON aunque ``B2G_JSON`` no esté seteada."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # B2G_JSON ausente del env inyectado
        result = runner.invoke(
            b2g,
            ["status", "--json"],
            env={"B2G_JSON": "0"},  # explícitamente falsy
            catch_exceptions=False,
        )
    # El flag --json gana sobre B2G_JSON=0
    _assert_one_json_line(result.stdout)


@pytest.mark.unit
def test_precedencia_env_var_sin_flag() -> None:
    """``B2G_JSON=1`` activa JSON sin pasar ``--json``."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g, ["status"], env={"B2G_JSON": "1"}, catch_exceptions=False
        )
    _assert_one_json_line(result.stdout)


@pytest.mark.unit
def test_sin_flag_ni_env_var_modo_humano() -> None:
    """Sin ``--json`` ni ``B2G_JSON``: stderr tiene el error (modo humano)."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            b2g, ["status"], env={"B2G_JSON": "0"}, catch_exceptions=False
        )
    # stdout vacío en modo humano-error
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# 7. Anti-regresión: stdout NUNCA más de una línea en modo JSON
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("cmd_args", _CMDS_NO_WORKSPACE)
def test_anti_regresion_stdout_max_una_linea_con_json(cmd_args: list[str]) -> None:
    """Guard: stdout NUNCA supera una línea no-vacía en modo JSON."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, cmd_args, catch_exceptions=False)
    lineas = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lineas) <= 1, (
        f"stdout tiene {len(lineas)} líneas en modo JSON ({cmd_args[0]}):\n"
        f"{result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# 8. Borde SIN envelope: errores de parseo de Click
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_opcion_desconocida_no_emite_envelope() -> None:
    """Opción desconocida → Click stderr, stdout vacío, exit 2 (sin envelope)."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["status", "--opcion-inexistente"])
    # stdout debe estar vacío (no hay envelope para errores de parseo de Click)
    assert result.stdout.strip() == "", (
        f"stdout debería estar vacío ante opción desconocida, obtuvo: {result.stdout!r}"
    )
    # Click retorna exit code 2 para errores de uso
    assert result.exit_code == 2


@pytest.mark.unit
def test_b2g_json_env_var_valores_truthy_alternativos() -> None:
    """``B2G_JSON=true`` y ``B2G_JSON=yes`` también activan el modo JSON."""
    for val in ("true", "yes", "TRUE", "True", "YES"):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                b2g, ["status"], env={"B2G_JSON": val}, catch_exceptions=False
            )
        (
            _assert_one_json_line(result.stdout),
            f"B2G_JSON={val!r} debería activar JSON mode",
        )
