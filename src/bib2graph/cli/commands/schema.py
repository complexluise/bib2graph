"""cli.commands.schema — Comando meta ``b2g schema`` (ADR 0045, #260).

Grieta 3c del ADR 0045: la salida del CLI está versionada (``schema="1"``,
``service/envelope.py:26``) pero, hasta este comando, no había introspección
del contrato **por el mismo canal** de invocación — un agente en frío debía
ir a ``docs/API.md`` en prosa para conocer la forma del envelope y los exit
codes (el *hop* débil señalado en el ADR).

``b2g schema`` emite, por el envelope estándar (``--json``), una descripción
legible por máquina y estática del contrato:

  - ``envelope_schema``: JSON-schema (borrador simplificado, sin dependencia
    de ``jsonschema``) de la forma ``{schema, ok, command, exit_code, data,
    warnings, error}`` que produce ``build_envelope`` (ADR 0021/0028).
  - ``exit_codes``: los 6 exit codes (0-5) con su significado (ADR 0021).
  - ``contract_version``: ``ENVELOPE_SCHEMA_VERSION`` (hoy ``"1"``).

Sigue el **patrón de comando meta de ``skill``** (ADR 0039): NO transiciona
la FSM, NO resuelve workspace, vive fuera de los 10 verbos del ciclo. El
conteo de la superficie pasa a "10 verbos + skill + schema" (ADR 0045).

``schema`` es puramente estático/determinista: no lee el store, no hace red,
no depende del workspace activo — coherente con 0022 (sin IA generativa).
"""

from __future__ import annotations

from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._options import json_mode, json_option
from bib2graph.service.envelope import ENVELOPE_SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Descripción estática del contrato (ADR 0021/0028/0045)
# ---------------------------------------------------------------------------

#: JSON-schema simplificado de la forma del envelope (``build_envelope``,
#: ``service/envelope.py``). No depende de la librería ``jsonschema``: es un
#: dict literal en el vocabulario JSON Schema Draft-07 (propiedades top-level
#: y sus tipos), suficiente para que un agente valide la forma sin ambigüedad.
_ENVELOPE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "bib2graph envelope",
    "type": "object",
    "required": ["schema", "ok", "command", "exit_code", "data", "warnings", "error"],
    "properties": {
        "schema": {
            "type": "string",
            "description": "Versión del contrato del envelope (ENVELOPE_SCHEMA_VERSION).",
            "const": ENVELOPE_SCHEMA_VERSION,
        },
        "ok": {
            "type": "boolean",
            "description": "True si la operación terminó con éxito.",
        },
        "command": {
            "type": "string",
            "description": "Nombre del subcomando u operación invocada.",
        },
        "exit_code": {
            "type": "integer",
            "minimum": 0,
            "maximum": 5,
            "description": "Código de resultado del proceso (0-5, ADR 0021).",
        },
        "data": {
            "type": "object",
            "description": (
                "Datos de resultado (dict vacío {} cuando ok=false). "
                "La forma interna es específica de cada comando; ver "
                "docs/API.md por comando."
            ),
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista de advertencias accionables (puede estar vacía).",
        },
        "error": {
            "type": ["object", "null"],
            "description": (
                "null si ok=true. Si ok=false: {code, message, subcode?}. "
                "'subcode' es OPCIONAL y aditivo (ADR 0045 #258): solo se "
                "puebla cuando code='NETWORK_ERROR' (exit 4), con "
                "'RATE_LIMITED' (HTTP 429, transitorio) o 'UPSTREAM_TIMEOUT' "
                "(HTTP 504/timeout, no reintentable sin cambiar la petición)."
            ),
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Código estable del error (p. ej. NETWORK_ERROR).",
                },
                "message": {
                    "type": "string",
                    "description": "Mensaje accionable legible por humanos y agentes.",
                },
                "subcode": {
                    "type": ["string", "null"],
                    "enum": ["RATE_LIMITED", "UPSTREAM_TIMEOUT", None],
                    "description": (
                        "Aditivo y opcional (ADR 0045 #258); solo presente "
                        "para code='NETWORK_ERROR'."
                    ),
                },
            },
            "required": ["code", "message"],
        },
    },
}

#: Los 6 exit codes del contrato (ADR 0021), con su significado y la
#: excepción/condición típica que los produce.
_EXIT_CODES: list[dict[str, Any]] = [
    {
        "code": 0,
        "name": "OK",
        "meaning": "Éxito.",
    },
    {
        "code": 1,
        "name": "USAGE_ERROR",
        "meaning": "Error de uso: opción faltante o inválida.",
    },
    {
        "code": 2,
        "name": "DATA_ERROR",
        "meaning": "Error de datos: schema inválido, ids inexistentes, filtro inválido.",
    },
    {
        "code": 3,
        "name": "DEPENDENCY_ERROR",
        "meaning": "Dependencia o capacidad faltante (ImportError; extra no instalado).",
    },
    {
        "code": 4,
        "name": "NETWORK_ERROR",
        "meaning": (
            "Error de red (httpx.HTTPError / timeout). Puede traer "
            "error.subcode='RATE_LIMITED' (HTTP 429) o "
            "'UPSTREAM_TIMEOUT' (HTTP 504/timeout) — ADR 0045 #258."
        ),
    },
    {
        "code": 5,
        "name": "STORE_ERROR",
        "meaning": "Store/snapshot bloqueado o corrupto (StoreLockedError / OSError).",
    },
]

#: Resumen de la superficie del CLI, para que un agente en frío sepa dónde
#: parado sin salir del canal de invocación (ADR 0045 §Consecuencias:
#: "10 verbos del ciclo + skill + schema").
_SURFACE_SUMMARY = (
    "10 verbos del ciclo (init, seed, chain, build, export, status, validate, "
    "read, curate, snapshot) + 2 comandos meta fuera del ciclo (skill, schema). "
    "'schema' no transiciona la FSM ni resuelve workspace."
)


def build_schema_data() -> dict[str, Any]:
    """Arma el ``data`` del envelope de ``b2g schema`` (función pura, sin I/O).

    Returns:
        Dict con ``contract_version``, ``envelope_schema``, ``exit_codes`` y
        ``surface_summary``.
    """
    return {
        "contract_version": ENVELOPE_SCHEMA_VERSION,
        "envelope_schema": _ENVELOPE_JSON_SCHEMA,
        "exit_codes": _EXIT_CODES,
        "surface_summary": _SURFACE_SUMMARY,
    }


# Comando Click


@click.command("schema")
@json_option
def schema_cmd(json_output: bool) -> None:
    """Describe el contrato del envelope: JSON-schema, exit codes y versión.

    Comando META (como ``skill``): no transiciona la FSM, no resuelve
    workspace. Determinista y estático — mismo resultado en cualquier
    invocación, sin dependencia del workspace activo ni de la red.
    """
    data = build_schema_data()

    if json_mode(json_output):
        envelope = build_envelope(
            command="schema",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(f"Versión del contrato (schema): {data['contract_version']}")
        emit_human("Exit codes:")
        for entry in data["exit_codes"]:
            emit_human(f"  {entry['code']}  {entry['name']:<18} {entry['meaning']}")
        emit_human(f"\n{data['surface_summary']}")
        emit_human(
            "\nPara el JSON-schema completo del envelope, usá 'b2g schema --json'."
        )
