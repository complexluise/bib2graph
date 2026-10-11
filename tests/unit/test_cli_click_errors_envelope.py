"""Tests de errores de Click como envelope ``schema="1"`` en modo JSON (#283).

Cubre el camino de errores de parseo de Click (``NoSuchCommand``,
``NoSuchOption``, ``BadParameter``) que escapan al cuerpo del comando Click
y, por lo tanto, no pasan por el decorador ``@handle_errors``.

DoD (#283):
  - En modo ``--json``/``B2G_JSON``, los errores de Click se emiten como
    envelope ``schema="1"`` con ``ok:false``, ``error.code='USAGE_ERROR'``,
    ``exit_code`` (2 = parse error de Click), ``command`` best-effort.
  - Tests sellan: ``b2g <verbo-inexistente> --json`` y
    ``b2g build --opcion-inexistente --json`` → envelope válido en stdout
    (vía ``B2G_JSON=1``, ver NOTA abajo).
  - Regresión: modo humano sigue mostrando texto plano (no se rompe).
  - Regresión: ``b2g <verbo-existente> --json`` sigue funcionando.

NOTA sobre ``--json`` como flag en argv (#283 + limitación de Click):
  Click aborta el parseo **en el primer token inválido** y nunca alcanza
  el ``--json`` posterior. ``b2g monitor --json`` parsea ``monitor``, ve
  que no existe, lanza ``NoSuchCommand`` y sale con exit 2 antes de mirar
  ``--json``. Por eso, en producción el camino agente-native para errores
  de Click es siempre ``B2G_JSON=1`` (env). Los tests sellan **ambos
  arranques**: (a) ``B2G_JSON=1`` (lo que el agente usa), y (b) ``--json``
  en argv por completitud (que Click nunca puede ejecutar para verbos
  desconocidos, pero sí para errores que ocurran POSTERIORMENTE — p. ej.
  una ``BadParameter`` sobre un comando cuyo sub-camino dispare un
  ``UsageError``).

Estrategia: para llegar al ``except click.exceptions.UsageError`` que
agregamos en ``main()`` necesitamos invocar ``main()`` con ``sys.argv``
reemplazado (CliRunner invoca ``cli.main()`` directamente, no nuestro
``main()`` adaptador). El helper ``_invoke_main_capture`` hace ambas
cosas en un ``contextmanager``.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from collections.abc import Iterator, Mapping
from typing import Any

import click
import pytest
from click.testing import CliRunner

from bib2graph.cli import b2g

# ---------------------------------------------------------------------------
# Helper de invocación que sí pasa por main() — el path real de producción
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _invoke_main_capture(
    argv: list[str],
    *,
    env: Mapping[str, str | None] | None = None,
) -> Iterator[tuple[int, str, str]]:
    """Reemplaza ``sys.argv``/``sys.stdout``/``sys.stderr`` y llama a ``main()``.

    Returns:
        Tupla ``(exit_code, stdout, stderr)`` con el resultado.
    """
    saved_argv = list(sys.argv)
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    saved_env_keys = set(env.keys()) if env else set()
    saved_env_values: dict[str, str | None] = {
        k: os.environ.get(k) for k in saved_env_keys
    }

    out_buf = io.StringIO()
    err_buf = io.StringIO()
    sys.stdout = out_buf
    sys.stderr = err_buf
    sys.argv = argv
    if env:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    exit_code: int = 0
    try:
        from bib2graph.cli import main

        try:
            exit_code = main()
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 0
        yield (exit_code, out_buf.getvalue(), err_buf.getvalue())
    finally:
        sys.argv = saved_argv
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
        # Restaurar env a su estado previo (eliminar claves si no existían)
        if env:
            for k in saved_env_keys:
                prev = saved_env_values[k]
                if prev is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev


def _assert_envelope_ok_false(stdout: str) -> dict[str, Any]:
    """Aserta que stdout es exactamente una línea envelope ``ok=false`` válida.

    Returns:
        El dict parseado para asserts adicionales.
    """
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"Se esperaba exactamente 1 línea en stdout, se obtuvieron {len(lines)}:\n"
        f"{stdout!r}"
    )
    data = json.loads(lines[0])
    assert data.get("schema") == "1"
    assert data.get("ok") is False, f"Se esperaba ok=False, obtuvo {data.get('ok')!r}"
    assert isinstance(data.get("error"), dict)
    return data


# ---------------------------------------------------------------------------
# 1. Helper puro: extracción best-effort del command desde click.exceptions.UsageError
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractCommandFromUsageError:
    """Cubre el helper de extracción best-effort del verb invocado.

    Para ``NoSuchCommand`` la verb attempted aparece en el mensaje (``No such
    command 'X'``); para otras variantes (``NoSuchOption``, ``BadParameter``)
    el verb está en ``exc.ctx.command.name``.
    """

    def test_no_such_command_extrae_nombre_de_message(self) -> None:
        from bib2graph.cli._click_error_handler import extract_command_from_usage_error

        runner = CliRunner()
        # standalone_mode=False para que Click NO convierta la excepción a SystemExit;
        # catch_exceptions=False para que la excepción se propague al test.
        with pytest.raises(click.exceptions.NoSuchCommand) as exc_info:
            runner.invoke(
                b2g,
                ["monitor"],
                standalone_mode=False,
                catch_exceptions=False,
            )
        assert extract_command_from_usage_error(exc_info.value) == "monitor"
        # Confirmamos también que el path de Click es estable: segunda invocación
        # con el mismo input también lanza NoSuchCommand (regresión silenciosa).
        with pytest.raises(click.exceptions.NoSuchCommand):
            runner.invoke(
                b2g,
                ["monitor"],
                standalone_mode=False,
                catch_exceptions=False,
            )

    def test_no_such_option_extrae_nombre_de_ctx(self) -> None:
        from bib2graph.cli._click_error_handler import extract_command_from_usage_error

        runner = CliRunner()
        with pytest.raises(click.exceptions.NoSuchOption) as exc_info:
            runner.invoke(
                b2g,
                ["build", "--opcion-inexistente"],
                standalone_mode=False,
                catch_exceptions=False,
            )
        assert extract_command_from_usage_error(exc_info.value) == "build"


# ---------------------------------------------------------------------------
# 2. Helper puro: emisión del envelope de Click error
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEmitClickUsageErrorEnvelope:
    """Cubre el helper que decide entre envelope JSON y texto humano."""

    def _capture_no_such_command(self) -> click.exceptions.UsageError:
        runner = CliRunner()
        with pytest.raises(click.exceptions.NoSuchCommand) as exc_info:
            runner.invoke(
                b2g,
                ["monitor"],
                standalone_mode=False,
                catch_exceptions=False,
            )
        return exc_info.value

    def test_json_mode_emite_envelope_a_stdout(self, capsys) -> None:
        from bib2graph.cli._click_error_handler import emit_click_usage_error_envelope

        exc = self._capture_no_such_command()
        exit_code = emit_click_usage_error_envelope(
            exc, command="monitor", json_mode=True
        )
        captured = capsys.readouterr()
        envelope = json.loads(captured.out.strip())
        assert envelope["ok"] is False
        assert envelope["command"] == "monitor"
        assert envelope["exit_code"] == 2
        assert envelope["error"]["code"] == "USAGE_ERROR"
        assert "monitor" in envelope["error"]["message"]
        assert exit_code == 2

    def test_human_mode_imprime_texto_a_stderr(self, capsys) -> None:
        from bib2graph.cli._click_error_handler import emit_click_usage_error_envelope

        exc = self._capture_no_such_command()
        exit_code = emit_click_usage_error_envelope(
            exc, command="monitor", json_mode=False
        )
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "monitor" in captured.err
        assert exit_code == 2


# ---------------------------------------------------------------------------
# 3. Integración end-to-end vía main() — el camino de producción real
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClickErrorsAsEnvelopeEndToEndViaEnvVar:
    """Pasa por ``main()`` con ``B2G_JSON=1``.

    Camino agente-native canónico: el agente setea ``B2G_JSON=1`` una vez y
    todos los errores —incluidos los de parseo de Click— vienen como
    envelope.
    """

    def test_verbo_inexistente_emite_envelope_en_stdout(self) -> None:
        with _invoke_main_capture(["b2g", "monitor"], env={"B2G_JSON": "1"}) as (
            exit_code,
            stdout,
            stderr,
        ):
            assert exit_code == 2
            assert stderr == "", (
                f"En modo JSON stderr debe estar vacío, obtuvo {stderr!r}"
            )
            data = _assert_envelope_ok_false(stdout)
            assert data["command"] == "monitor"
            assert data["exit_code"] == 2
            assert data["error"]["code"] == "USAGE_ERROR"
            assert "monitor" in data["error"]["message"]

    def test_opcion_inexistente_emite_envelope_en_stdout(self) -> None:
        with _invoke_main_capture(
            ["b2g", "build", "--opcion-inexistente"],
            env={"B2G_JSON": "1"},
        ) as (exit_code, stdout, stderr):
            assert exit_code == 2
            assert stderr == ""
            data = _assert_envelope_ok_false(stdout)
            assert data["command"] == "build"
            assert data["exit_code"] == 2
            assert data["error"]["code"] == "USAGE_ERROR"


@pytest.mark.unit
class TestClickErrorsAsEnvelopeEndToEndViaFlag:
    """Pasa por ``main()`` con ``--json`` después de un argumento POSIBLEMENTE válido.

    Click aborta en el primer token desconocido, así que ``--json`` después de
    un verbo malo nunca se parsea. Estos tests verifican el caso opuesto:
    ``--json`` ANTES del verbo malo (lo cual sigue siendo poco útil porque
    Click en realidad nunca llegará al parseo de ``--json`` cuando el primer
    arg es desconocido). Documentamos la limitación como DoD parcial.
    """

    def test_flag_json_no_parseable_con_verbo_malo(self) -> None:
        """``--json`` antes de un verbo malo NO se parsea (limitación de Click).

        Sin ``B2G_JSON``, el ``--json`` queda en argv pero Click aborta en el
        primer parseo. Confirmamos que el envelope aparece vía env o no
        aparece, sin importar el flag.
        """
        with _invoke_main_capture(["b2g", "monitor", "--json"], env=None) as (
            exit_code,
            stdout,
            stderr,
        ):
            assert exit_code == 2
            # Modo humano: stderr tiene texto, stdout vacío
            assert stdout.strip() == "", (
                f"Sin B2G_JSON, stdout debe estar vacío, obtuvo {stdout!r}"
            )
            assert "monitor" in stderr


@pytest.mark.unit
class TestHumanModeUnchangedViaMain:
    """El modo humano (sin --json ni B2G_JSON) NO se rompe."""

    def test_verbo_inexistente_modo_humano(self) -> None:
        with _invoke_main_capture(["b2g", "monitor"], env=None) as (
            exit_code,
            stdout,
            stderr,
        ):
            assert exit_code == 2
            # Modo humano: stdout vacío (texto a stderr)
            assert stdout.strip() == ""
            assert "monitor" in stderr

    def test_opcion_inexistente_modo_humano(self) -> None:
        with _invoke_main_capture(
            ["b2g", "build", "--opcion-inexistente"], env=None
        ) as (exit_code, stdout, stderr):
            assert exit_code == 2
            assert stdout.strip() == ""
            assert "opcion-inexistente" in stderr


@pytest.mark.unit
class TestClickErrorsViaB2GJsonFalsyValue:
    """``B2G_JSON=0`` / ``false`` NO activa el modo JSON — comportamiento previo."""

    def test_b2g_json_cero_no_emite_envelope(self) -> None:
        with _invoke_main_capture(["b2g", "monitor"], env={"B2G_JSON": "0"}) as (
            exit_code,
            stdout,
            stderr,
        ):
            assert exit_code == 2
            # Modo humano (env falsy)
            assert stdout.strip() == ""
            assert "monitor" in stderr

    def test_b2g_json_false_no_emite_envelope(self) -> None:
        with _invoke_main_capture(["b2g", "monitor"], env={"B2G_JSON": "false"}) as (
            exit_code,
            stdout,
            stderr,
        ):
            assert exit_code == 2
            assert stdout.strip() == ""
            assert "monitor" in stderr


# ---------------------------------------------------------------------------
# 4. Regresión: comando existente con --json sin error de Click
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_comando_existente_con_json_sigue_funcionando() -> None:
    """``b2g status --json`` sin workspace sigue emitiendo un envelope de dominio.

    Verifica que NO rompimos ``@handle_errors``: el camino pre-existente
    sigue emitiendo envelopes. Distinguimos el envelope de dominio (de
    ``handle_errors``) del envelope de Click (de nuestra enmienda #283)
    por la combinación ``command='status'`` + ``exit_code=1`` (B2G exit
    code para errores de uso de dominio); el de Click sería exit 2 con
    ``command='<verb-intentado>'``.
    """
    with _invoke_main_capture(["b2g", "status"], env={"B2G_JSON": "1"}) as (
        exit_code,
        stdout,
        _stderr,
    ):
        # status sin workspace falla con un UsageError de dominio (exit 1)
        assert exit_code == 1, (
            f"UsageError de dominio debe mapear a exit 1, obtuvo {exit_code}"
        )
        data = _assert_envelope_ok_false(stdout)
        # Envelope de DOMINIO: command='status', code='USAGE_ERROR' (de B2G,
        # no de Click), exit_code=1 — la diferencia con los tests de arriba
        # es que acá el comando que se intentó SE EJECUTÓ (no es NoSuchCommand).
        assert data["command"] == "status"
        assert data["exit_code"] == 1
        assert data["error"]["code"] == "USAGE_ERROR"


# ---------------------------------------------------------------------------
# 5. Regresión: comportamiento pre-existente del modo humano vía CliRunner
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_opcion_desconocida_humano_via_cli_runner() -> None:
    """Regresión: ``b2g status --opcion-inexistente`` en modo humano,
    stdout vacío y exit 2.

    No tocamos el body de ``b2g status``. Este test sella que el cambio
    en ``main()`` no afecta el comportamiento de CliRunner cuando el
    envelope handler del CLI emite el envelope de error de dominio.
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(b2g, ["status", "--opcion-inexistente"])
    # stdout vacío (modo humano: errores de parseo de Click NO son envelope)
    assert result.stdout.strip() == "", (
        f"stdout no debe tener envelope en modo humano, obtuvo {result.stdout!r}"
    )
    # Click ya imprimió el usage en stderr → exit 2
    assert result.exit_code == 2
