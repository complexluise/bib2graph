"""cli._options — Opciones Click compartidas entre subcomandos.

Define el decorador ``json_option`` (una sola declaración del flag ``--json``)
y los helpers ``_env_truthy`` / ``json_mode`` para resolver el modo JSON desde
el flag local o la variable de entorno ``B2G_JSON``.

Precedencia para activar el modo JSON:
  1. ``--json`` explícito en el comando (flag local ``json_output=True``).
  2. Variable de entorno ``B2G_JSON`` truthy (``"1"``, ``"true"``, ``"yes"``,
     case-insensitive).

Caso de uso agente-native: un agente setea ``B2G_JSON=1`` una vez y no pasa
``--json`` nunca más; todos los comandos emiten el envelope sin flag explícito.

No hay ``--no-json``: el modo humano es el default cuando ni el flag ni la env
var están presentes.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypeVar

import click

F = TypeVar("F", bound=Callable[..., Any])


def _env_truthy(name: str) -> bool:
    """Devuelve True si la variable de entorno ``name`` está seteada y es truthy.

    Considera truthy: ``"1"``, ``"true"``, ``"yes"`` (case-insensitive).
    Todo lo demás (ausente, ``"0"``, ``"false"``, ``"no"``, vacío) → False.

    Args:
        name: Nombre de la variable de entorno.

    Returns:
        True si la variable tiene un valor truthy.
    """
    val = os.environ.get(name, "").strip().lower()
    return val in ("1", "true", "yes")


def json_mode(local_flag: bool) -> bool:
    """Resuelve si el modo JSON está activo (flag local O env var ``B2G_JSON``).

    Precedencia:
      1. ``--json`` explícito (``local_flag=True``) → modo JSON.
      2. ``B2G_JSON`` truthy en el entorno → modo JSON.
      3. Ninguno → modo humano.

    Usalo en cada subcomando en lugar de ``if json_output:`` →
    ``if json_mode(json_output):``.

    Args:
        local_flag: Valor del flag ``--json`` recibido por el comando Click.

    Returns:
        True si el modo JSON está activo (por flag o por entorno).
    """
    return bool(local_flag) or _env_truthy("B2G_JSON")


def json_option(func: F) -> F:
    """Decorador que agrega ``--json`` / ``json_output`` a un subcomando Click.

    Declaración única del flag; aplicado con ``@json_option`` en cada
    subcomando en lugar de repetir el bloque ``@click.option("--json", ...)``.
    El parámetro inyectado en la firma del comando es ``json_output: bool``.

    Para activar el modo JSON sin pasar el flag, setear ``B2G_JSON=1``
    (o ``"true"`` / ``"yes"``) en el entorno; ver ``json_mode``.

    Args:
        func: Función Click a decorar.

    Returns:
        La función decorada con la opción ``--json``.
    """
    return click.option(
        "--json",
        "json_output",
        is_flag=True,
        default=False,
        help="Salida JSON estructurada (también activado por B2G_JSON=1).",
    )(func)
