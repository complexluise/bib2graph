"""cli.commands.thesaurus — Subcomando ``b2g thesaurus``.

Aplica un thesaurus multilingüe curado al corpus, sobrescribiendo
``keywords_id`` con los conceptos canónicos definidos por el usuario.

Transversal al FSM: NO transiciona el ``CycleState`` (mismo criterio que
``b2g enrich`` / ``b2g curate`` / ``b2g networks``).  El thesaurus es un
paso explícito y voluntario del investigador; la deduplicación automática
(``normalize + dedup``) ocurre en la ingesta.

Formato del thesaurus JSON (ADR 0011):
    {
        "concepts": {
            "<canonical>": {
                "aliases_en": ["...", "..."],
                "aliases_es": ["...", "..."],
                "aliases_pt": ["...", "..."]
            }
        }
    }

Envelope ``--json`` (schema="1"): ``keywords_mapped``, ``keywords_total``,
``aliases_loaded``, ``applied_at``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import DataError, handle_errors
from bib2graph.cli._store import open_store, resolve_library_path

# ---------------------------------------------------------------------------
# Función núcleo (testeable, sin Click)
# ---------------------------------------------------------------------------


def run_thesaurus(
    store_path: str | Path,
    thesaurus_path: str | Path,
) -> dict[str, Any]:
    """Aplica el thesaurus al corpus y persiste sin transicionar el CycleState.

    Lee el corpus del store, aplica ``Preprocessor.apply_thesaurus`` (que
    sobrescribe ``keywords_id`` desde los aliases del thesaurus) y persiste
    el corpus actualizado.  El ``CycleState`` no cambia.

    Args:
        store_path: Ruta al archivo ``.duckdb``.
        thesaurus_path: Ruta al JSON del thesaurus (formato ADR 0011).

    Returns:
        Dict con ``keywords_mapped``, ``keywords_total``, ``aliases_loaded``,
        ``applied_at``.

    Raises:
        DataError: Si el thesaurus no existe o tiene formato inválido.
        StoreError: Si el store está bloqueado.
    """
    from bib2graph.preprocessors.preprocessor import Preprocessor
    from bib2graph.preprocessors.thesaurus import load_thesaurus

    resolved = Path(thesaurus_path)
    if not resolved.exists():
        raise DataError(
            f"El thesaurus '{resolved}' no existe. "
            "Verificá la ruta al archivo JSON del thesaurus."
        )

    try:
        lookup = load_thesaurus(resolved)
    except Exception as exc:
        raise DataError(
            f"No se pudo cargar el thesaurus '{resolved}': {exc}. "
            "Verificá que el archivo tenga el formato correcto "
            '({"concepts": {"canonical": {"aliases_en": [...]}}})'
        ) from exc

    applied_at = datetime.now(UTC)
    preprocessor = Preprocessor()

    merged_backend_close = None
    store = open_store(store_path)
    try:
        corpus = store.load()

        result = preprocessor.apply_thesaurus(
            corpus,
            resolved,
            applied_at=applied_at,
        )

        # Contar keywords mapeadas por el thesaurus
        rows = result.to_arrow().to_pylist()
        total_kw = sum(len(r["keywords_id"]) for r in rows if r.get("keywords_id"))
        # Contar cuántas son canónicas del thesaurus (keys del lookup invertido)
        canonical_set = set(lookup.values())
        mapped_kw = sum(
            1
            for r in rows
            if r.get("keywords_id")
            for kw in r["keywords_id"]
            if kw in canonical_set
        )

        merged_backend_close = getattr(result._backend, "close", None)
        # persist_replace: el thesaurus reemplaza los keywords_id del corpus
        # completo; el upsert-concat reintroduría los canónicos viejos junto a
        # los nuevos si el mapeo cambió (mismo bug que el dedup cross-biblioteca).
        store.persist_replace(result)
        # NO transicionar el CycleState (transversal al lazo)
    finally:
        if merged_backend_close is not None:
            merged_backend_close()
        store.close()

    return {
        "keywords_mapped": mapped_kw,
        "keywords_total": total_kw,
        "aliases_loaded": len(lookup),
        "applied_at": applied_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Comando Click (no se testea directamente)
# ---------------------------------------------------------------------------


@click.command("thesaurus")
@click.option(
    "--from",
    "thesaurus_path",
    required=True,
    type=click.Path(),
    help=(
        "Ruta al archivo JSON del thesaurus multilingüe (formato ADR 0011). "
        "Sobrescribe keywords_id con los conceptos canónicos del mapa."
    ),
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Salida JSON estructurada.",
)
@click.pass_context
@handle_errors("thesaurus")
def thesaurus_cmd(
    ctx: click.Context,
    thesaurus_path: str,
    json_output: bool,
) -> None:
    """Aplica el thesaurus multilingüe al corpus (transversal al lazo).

    Sobrescribe ``keywords_id`` con los conceptos canónicos del mapa curado.
    NO transiciona el CycleState: puede aplicarse en cualquier momento del
    ciclo bibliométrico (igual que enrich, curate y networks).

    \\b
    El thesaurus debe ser un JSON con la estructura:
      {\"concepts\": {\"canonical\": {\"aliases_en\": [...], \"aliases_es\": [...]}}}

    \\b
    Ejemplos:
      b2g thesaurus --from thesaurus.json
      b2g thesaurus --from thesaurus.json --json
    """
    store_path = resolve_library_path(ctx.obj)
    data = run_thesaurus(store_path, thesaurus_path)

    if json_output:
        envelope = build_envelope(
            command="thesaurus",
            ok=True,
            data=data,
            exit_code=0,
        )
        emit(envelope)
    else:
        emit_human(
            f"Thesaurus aplicado: {data['keywords_mapped']} keywords mapeadas "
            f"(de {data['keywords_total']} totales, "
            f"{data['aliases_loaded']} aliases cargados)."
        )
