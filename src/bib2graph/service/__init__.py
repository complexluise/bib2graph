"""service — Capa de servicios neutral de bib2graph (ADR 0028).

Agnóstica de transporte: sin ``print``, ``sys.exit``, Click ni FastAPI.
CLI y API son adaptadores delgados de esta capa.

Contrato público re-exportado:
  - ``build_envelope``, ``ENVELOPE_SCHEMA_VERSION`` — envelope JSON versionado.
  - ``B2GError``, ``UsageError``, ``DataError``, ``DependencyError``,
    ``NetworkError``, ``StoreError`` — jerarquía de errores tipados.
  - ``code_for`` — helper de mapeo error→exit code (sin I/O).
  - ``get_workspace``, ``list_rounds``, ``get_paper``, ``get_scent``,
    ``get_network``, ``compare_rounds`` — lecturas del Hito G2 (ADR 0028).
  - ``accept_papers``, ``reject_papers``, ``curate_paper`` — escrituras del
    Hito G3 (ADR 0028).
"""

from __future__ import annotations

from bib2graph.service.curate import accept_papers, curate_paper, reject_papers
from bib2graph.service.envelope import ENVELOPE_SCHEMA_VERSION, build_envelope
from bib2graph.service.errors import (
    B2GError,
    DataError,
    DependencyError,
    NetworkError,
    StoreError,
    UsageError,
    code_for,
)
from bib2graph.service.reads import (
    compare_rounds,
    get_network,
    get_paper,
    get_scent,
    get_workspace,
    list_rounds,
)

__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "B2GError",
    "DataError",
    "DependencyError",
    "NetworkError",
    "StoreError",
    "UsageError",
    "accept_papers",
    "build_envelope",
    "code_for",
    "compare_rounds",
    "curate_paper",
    "get_network",
    "get_paper",
    "get_scent",
    "get_workspace",
    "list_rounds",
    "reject_papers",
]
