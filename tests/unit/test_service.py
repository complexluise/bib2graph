"""Tests unitarios del Hito G1 — capa de servicios neutral ``bib2graph.service``.

Casos cubiertos (docs/ROADMAP/05-gui.md §Hito G1):
1. ``service.build_envelope`` produce el envelope canónico ``schema="1"``
   (ok y error).
2. Cada subclase de ``B2GError`` mapea al exit code esperado (0-5) vía
   ``.exit_code`` y ``code_for``.
3. ``code_for`` mapea excepciones estándar (OSError→5, ImportError→3,
   httpx.HTTPError→4).
4. La capa ``service/`` no importa Click, FastAPI, ``sys.exit`` ni ``print``
   (contrato de neutralidad de transporte, ADR 0028).

Filosofía (AGENTS.md): se testea el contrato y la lógica real; no se testean
los re-exports triviales de cli/ (eso lo cubre test_cli.py).
Marcador: ``unit`` (puro, sin I/O).
"""

from __future__ import annotations

import httpx
import pytest

# ---------------------------------------------------------------------------
# 1. build_envelope — envelope canónico schema="1"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_envelope_ok_tiene_claves_canonicas() -> None:
    """build_envelope(ok=True) produce el envelope canónico con schema='1'."""
    from bib2graph.service import build_envelope

    envelope = build_envelope(
        command="seed",
        ok=True,
        data={"papers_added": 5},
        exit_code=0,
    )

    assert envelope["schema"] == "1"
    assert envelope["ok"] is True
    assert envelope["command"] == "seed"
    assert envelope["exit_code"] == 0
    assert envelope["data"] == {"papers_added": 5}
    assert isinstance(envelope["warnings"], list)
    assert envelope["error"] is None


@pytest.mark.unit
def test_build_envelope_error_tiene_claves_canonicas() -> None:
    """build_envelope(ok=False, error=...) popula la clave error correctamente."""
    from bib2graph.service import build_envelope

    envelope = build_envelope(
        command="build",
        ok=False,
        data={},
        exit_code=3,
        error={"code": "DEPENDENCY_ERROR", "message": "Falta python-louvain."},
    )

    assert envelope["schema"] == "1"
    assert envelope["ok"] is False
    assert envelope["exit_code"] == 3
    assert envelope["error"] is not None
    assert envelope["error"]["code"] == "DEPENDENCY_ERROR"
    assert envelope["error"]["message"] == "Falta python-louvain."
    assert envelope["data"] == {}


# ---------------------------------------------------------------------------
# 2. Jerarquia B2GError - exit codes 1-5 via .exit_code y code_for
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "cls_name, expected_exit_code, expected_code",
    [
        ("UsageError", 1, "USAGE_ERROR"),
        ("DataError", 2, "DATA_ERROR"),
        ("DependencyError", 3, "DEPENDENCY_ERROR"),
        ("NetworkError", 4, "NETWORK_ERROR"),
        ("StoreError", 5, "STORE_ERROR"),
    ],
)
def test_b2gerror_subclase_exit_code(
    cls_name: str, expected_exit_code: int, expected_code: str
) -> None:
    """Cada subclase de B2GError tiene el exit_code y code esperados."""
    import bib2graph.service as svc

    cls = getattr(svc, cls_name)
    exc = cls("mensaje de prueba")

    assert exc.exit_code == expected_exit_code
    assert exc.code == expected_code
    assert exc.message == "mensaje de prueba"


@pytest.mark.unit
@pytest.mark.parametrize(
    "cls_name, expected_exit_code",
    [
        ("UsageError", 1),
        ("DataError", 2),
        ("DependencyError", 3),
        ("NetworkError", 4),
        ("StoreError", 5),
    ],
)
def test_code_for_b2gerror_subclases(cls_name: str, expected_exit_code: int) -> None:
    """code_for devuelve el exit code correcto para cada subclase de B2GError."""
    import bib2graph.service as svc

    cls = getattr(svc, cls_name)
    exc = cls("mensaje de prueba")

    assert svc.code_for(exc) == expected_exit_code


# ---------------------------------------------------------------------------
# 3. code_for — mapeo de excepciones estándar
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_code_for_oserror_devuelve_5() -> None:
    """code_for(OSError(...)) → 5."""
    from bib2graph.service import code_for

    assert code_for(OSError("disco lleno")) == 5


@pytest.mark.unit
def test_code_for_importerror_devuelve_3() -> None:
    """code_for(ImportError(...)) → 3."""
    from bib2graph.service import code_for

    assert code_for(ImportError("No module named 'community'")) == 3


@pytest.mark.unit
def test_code_for_httpx_connect_error_devuelve_4() -> None:
    """code_for(httpx.ConnectError) → 4."""
    from bib2graph.service import code_for

    exc = httpx.ConnectError("Sin conexión")
    assert code_for(exc) == 4


@pytest.mark.unit
def test_code_for_excepcion_no_mapeada_lanza_typeerror() -> None:
    """code_for de excepción no mapeada lanza TypeError (no silencia)."""
    from bib2graph.service import code_for

    with pytest.raises(TypeError, match="No hay mapeo de exit code"):
        code_for(ValueError("excepción genérica"))


# ---------------------------------------------------------------------------
# 4. Neutralidad de transporte — service/ no importa Click ni hace sys.exit
# ---------------------------------------------------------------------------


def _service_module_names() -> list[str]:
    """Todos los módulos del paquete service/ (auto-descubrimiento: cubre módulos
    futuros sin tocar el test). Fuente única del contrato de neutralidad ADR 0028.
    Consolida las copias que vivían en test_service_reads, test_api, test_cli_read
    y test_cli_read_top (epic #184)."""
    import importlib
    import pkgutil

    pkg = importlib.import_module("bib2graph.service")
    names = ["bib2graph.service"]
    names += [
        f"bib2graph.service.{info.name}" for info in pkgutil.iter_modules(pkg.__path__)
    ]
    return sorted(names)


@pytest.mark.unit
@pytest.mark.parametrize("module_name", _service_module_names())
def test_service_modulo_neutral_de_transporte(module_name: str) -> None:
    """Cada módulo de service/ es agnóstico de transporte (ADR 0028): no importa
    click/fastapi ni hace sys.exit/print. Detección por AST real (no substrings),
    sobre TODO el paquete service/ (no solo envelope/errors)."""
    import ast
    import importlib
    import pathlib

    mod = importlib.import_module(module_name)
    source_file = mod.__file__
    assert source_file is not None
    tree = ast.parse(pathlib.Path(source_file).read_text(encoding="utf-8"))

    forbidden = {"click", "fastapi"}
    for node in ast.walk(tree):
        # Imports de transporte (AST real: tolera comentarios y substrings engañosos)
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden, (
                    f"{module_name} importa '{alias.name}' - viola neutralidad de transporte"
                )
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden, (
                f"{module_name} importa de '{node.module}' - viola neutralidad de transporte"
            )
        # Llamadas reales (no docstrings) a sys.exit(...) o print(...)
        elif isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
                and node.func.attr == "exit"
            ):
                raise AssertionError(
                    f"{module_name} llama a sys.exit - viola neutralidad de transporte"
                )
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                raise AssertionError(
                    f"{module_name} llama a print() - viola neutralidad de transporte"
                )
