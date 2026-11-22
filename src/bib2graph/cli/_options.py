"""cli._options — Opciones Click compartidas entre subcomandos.

Define el decorador ``json_option`` (una sola declaración del flag ``--json``),
los helpers ``_env_truthy`` / ``json_mode`` para resolver el modo JSON desde
el flag local o la variable de entorno ``B2G_JSON``, y ``parse_since`` para
convertir el flag ``--since`` de ``chain`` en un ``date`` concreto.

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
import re
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, Literal, TypeVar

import click

from bib2graph.constants import DEFAULT_PROVIDER, Provider
from bib2graph.sources.registry import PROVIDERS

F = TypeVar("F", bound=Callable[..., Any])

ProviderOrigin = Literal["flag", "workspace", "default"]


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


def source_option(func: F) -> F:
    """Decorador que agrega ``--source`` / ``source`` a un subcomando Click.

    Mismo patrón que ``json_option`` (ADR 0053 D1.2).  ``click.Choice`` se
    deriva de ``PROVIDERS`` (solo proveedores con ``Source`` implementada,
    regla de ADR 0036).  Default ``None``: la precedencia la resuelve
    ``resolve_provider`` (``--source`` > ``workspace.json.source`` > openalex).
    El parámetro inyectado en la firma del comando es ``source: str | None``.
    """
    return click.option(
        "--source",
        "source",
        type=click.Choice([p.value for p in PROVIDERS]),
        default=None,
        help=(
            "Proveedor (motor de extracción) para esta invocación. Pisa "
            "workspace.json.source; default de la investigación: openalex. "
            "En 'init', fija el proveedor por defecto de la investigación."
        ),
    )(func)


def resolve_provider(flag: str | None, ws: Any) -> tuple[Provider, ProviderOrigin]:
    """Resuelve el proveedor activo y de dónde salió (ADR 0053 D1.2).

    Precedencia: ``--source`` > ``workspace.json.source`` > ``openalex``.

    Args:
        flag: Valor de ``--source`` (``None`` si no se pasó).
        ws: ``Workspace`` resuelto (usa ``ws.provider`` y, para distinguir
            ``"workspace"`` de ``"default"``, si el manifest declara ``source``).

    Returns:
        ``(provider, origin)`` con ``origin`` en ``flag|workspace|default``.
    """
    if flag is not None:
        return Provider(flag), "flag"
    manifest = ws.manifest
    if manifest is not None and "source" in manifest.model_fields_set:
        return Provider(ws.provider), "workspace"
    return DEFAULT_PROVIDER, "default"


def provider_echo(provider: Provider, origin: ProviderOrigin) -> dict[str, str]:
    """Bloque ``data.provider`` del envelope (aditivo, ADR 0053 D1.7)."""
    return {"name": provider.value, "origin": origin}


def reject_email_for(provider: Provider, email: str | None) -> None:
    """``--email`` solo aplica a OpenAlex (polite pool); no se ignora en silencio."""
    from bib2graph.service.errors import UsageError

    if email is not None and provider is not Provider.OPENALEX:
        raise UsageError(
            f"--email es del polite pool de OpenAlex y no aplica al proveedor "
            f"'{provider.value}'. Quitá --email (las credenciales de S2 van en "
            "la variable de entorno S2_API_KEY)."
        )


def guard_provider_mix(provider: Provider, workspace_provider: Provider | None) -> None:
    """Guard transitorio R1 (ADR 0053): no mezclar proveedores en una tabla.

    Rechaza (``DataError``, exit 2) usar un proveedor distinto del de
    ``workspace.json.source`` en todo comando que ESCRIBE en el corpus
    (``seed`` en todas sus variantes, ``chain``, ``build``), haya o no corpus:
    con corpus vacío, escribir con otro proveedor dejaría un corpus de ese
    proveedor que un comando posterior sin flag (que usa el de la
    investigación) fusionaría; el upsert ``ON CONFLICT (id)`` mezclaría los
    registros de forma irreversible.  Se llama ANTES de abrir el store.

    ``workspace_provider=None`` desactiva el guard (llamadas directas sin
    workspace, p. ej. tests de las funciones núcleo).
    """
    # TODO(#253): retirar este guard cuando el corpus pase a carriles por
    # proveedor (PK compuesta (id, provider)).
    from bib2graph.service.errors import DataError

    if workspace_provider is not None and provider is not workspace_provider:
        raise DataError(
            f"--source {provider.value} difiere del proveedor de la investigación "
            f"('{workspace_provider.value}'): mezclar proveedores en una sola "
            "tabla los fusionaría de forma irreversible. Hoy, para usar otro "
            "proveedor creá la investigación con "
            f"'b2g init --source {provider.value}' (o esperá a la coexistencia "
            "por proveedor, #253)."
        )


_RELATIVE_RE = re.compile(r"^(\d+)(d|m|y)$", re.IGNORECASE)

_DAYS_PER_UNIT: dict[str, int] = {
    "d": 1,
    "m": 30,
    "y": 365,
}


def parse_since(value: str, *, now: date | None = None) -> date:
    """Parsea el valor de ``--since`` en un ``date`` concreto.

    Acepta dos formatos:
    - Fecha ISO ``YYYY-MM-DD`` (p. ej. ``"2024-01-01"``).
    - Atajo relativo ``Nd``, ``Nm``, ``Ny`` (p. ej. ``"90d"``, ``"6m"``, ``"1y"``).
      El relativo se resuelve contra ``now`` o ``datetime.now(UTC).date()``
      inyectado en la frontera (R2/ADR 0017).

    La resolución del reloj se hace en la -frontera- (el comando Click), NO
    dentro del núcleo ni del servicio.

    Args:
        value: Cadena recibida del flag CLI.
        now: Fecha base para relativos (inyectable en tests).  Cuando es
            ``None``, se usa ``date.today()`` (equivalente a ``datetime.now(UTC).date()``).

    Returns:
        Fecha resuelta como ``date``.

    Raises:
        UsageError: Si el formato no es reconocido.
    """
    from bib2graph.service.errors import UsageError

    value = value.strip()

    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    m = _RELATIVE_RE.match(value)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        base = now if now is not None else date.today()
        delta_days = n * _DAYS_PER_UNIT[unit]
        return base - timedelta(days=delta_days)

    raise UsageError(
        f"Formato de --since no reconocido: {value!r}.  "
        "Usá una fecha ISO (YYYY-MM-DD) o un atajo relativo (90d, 6m, 1y)."
    )
