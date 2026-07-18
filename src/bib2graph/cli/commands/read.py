"""cli.commands.read — Grupo noun-verb ``b2g read`` (#156/#157, superficie CLI 0.10.0).

Primer grupo noun-verb del repo.  Agrupa lecturas read-only del corpus bajo
el verbo ``read``, con cuatro subcomandos:

  ``read list``   — lista papers con filtros opcionales (query/status/seeds/year).
  ``read stats``  — estadísticas del corpus agrupadas por status, year o is_seed.
  ``read show``   — fila completa de un paper, resolviendo por id, doi o source_id.
  ``read top``    — nodos más centrales + pares de co-citación con título (#157).

Cada subcomando delega la lógica en ``service.reads`` (capa neutral, ADR 0028):
  - ``list_papers``  → ``read list``
  - ``corpus_stats`` → ``read stats``
  - ``get_paper``    → ``read show``
  - ``get_top``      → ``read top``

Decisiones de esta implementación (#156/#157):
  - ``read`` sin subcomando → imprime ayuda y sale con exit 0
    (``invoke_without_command=True`` + check en el body; Click 8.4 usa exit 2
    con ``no_args_is_help=True`` en grupos — workaround deliberado).
  - ``--json`` y ``B2G_JSON`` funcionan en los cuatro subcomandos (ADR 0021 #151).
  - El ``command`` del envelope es la ruta completa (``"read list"``,
    ``"read stats"``, ``"read show"``, ``"read top"``), no solo ``"read"``.
  - ``--seeds`` y ``--candidates`` son mutuamente excluyentes (UsageError exit 1).
  - ``inspect`` permanece intacto; su absorción es del sub-issue #165.
  - ``read top``: red vacía → exit 0 + bloque vacío + reason/fix_command
    (honest-empty).  ``--kind`` inválido → exit 1 (UsageError de Click.Choice,
    remapeado por ``main()``).

Exit codes: 0 éxito, 1 uso (incl. ``--kind`` inválido), 2 datos (paper
inexistente; ``get_top`` con kind inválido llamado directo desde el servicio), 5 store.
"""

from __future__ import annotations

import click

from bib2graph.cli._envelope import build_envelope, emit, emit_human
from bib2graph.cli._errors import UsageError, handle_errors
from bib2graph.cli._options import json_mode, json_option
from bib2graph.cli._store import (
    resolve_workspace,
    workspace_echo,
    workspace_walkup_warning,
)
from bib2graph.constants import NetworkKind

# Grupo raíz


@click.group("read", invoke_without_command=True)
@click.pass_context
def read_grp(ctx: click.Context) -> None:
    """Lee papers del corpus (read-only).

    Subcomandos: list, stats, show, top.

    Ejemplos:
        b2g read list --query "unequal exchange"
        b2g read list --status accepted --json
        b2g read stats --group-by year
        b2g read show --id W2741809807
        b2g read show --id 10.1016/j.ecolecon.2019.01.001
        b2g read top --top 5 --json
        b2g read top --kind cocitation --json
    """
    ctx.ensure_object(dict)
    # Click 8.4: no_args_is_help=True en grupos termina con exit 2 (Missing command).
    # Usamos invoke_without_command=True + check manual para exit 0 correcto.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# read list


@read_grp.command("list")
@click.option(
    "--query",
    default=None,
    help="Texto a buscar en el título (substring, case-insensitive).",
)
@click.option(
    "--status",
    default=None,
    type=click.Choice(["candidate", "accepted", "rejected"]),
    help="Filtrar por curation_status exacto.",
)
@click.option(
    "--seeds",
    is_flag=True,
    default=False,
    help="Mostrar solo semillas (is_seed=True). Excluyente con --candidates.",
)
@click.option(
    "--candidates",
    is_flag=True,
    default=False,
    help="Mostrar solo no-semillas (is_seed=False). Excluyente con --seeds.",
)
@click.option(
    "--year",
    default=None,
    type=int,
    help="Filtrar por año exacto de publicación.",
)
@json_option
@click.pass_context
@handle_errors("read list")
def list_cmd(
    ctx: click.Context,
    query: str | None,
    status: str | None,
    seeds: bool,
    candidates: bool,
    year: int | None,
    json_output: bool,
) -> None:
    """Lista papers del corpus con filtros opcionales.

    Los filtros se combinan con AND lógico.
    Sin filtros devuelve todos los papers.

    Campos devueltos por paper: id, title, year, curation_status, is_seed.
    """
    if seeds and candidates:
        raise UsageError("--seeds y --candidates son mutuamente excluyentes.")

    is_seed: bool | None = None
    if seeds:
        is_seed = True
    elif candidates:
        is_seed = False

    from bib2graph.service.reads import list_papers

    ws = resolve_workspace(ctx.obj)
    data = list_papers(ws, query=query, status=status, is_seed=is_seed, year=year)
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="read list",
            ok=True,
            data=data,
            exit_code=0,
            warnings=workspace_walkup_warning(ws) or None,
        )
        emit(envelope)
    else:
        count = data["count"]
        emit_human(f"Papers encontrados: {count}")
        for paper in data["papers"]:
            seed_marker = " [seed]" if paper.get("is_seed") else ""
            emit_human(
                f"  {paper['id']}  {paper.get('year') or '----'}"
                f"  [{paper.get('curation_status')}]{seed_marker}"
                f"  {paper.get('title') or ''}"
            )


# read stats


@read_grp.command("stats")
@click.option(
    "--group-by",
    "group_by",
    default="status",
    type=click.Choice(["status", "year", "is_seed"]),
    show_default=True,
    help="Dimensión de agrupación.",
)
@json_option
@click.pass_context
@handle_errors("read stats")
def stats_cmd(
    ctx: click.Context,
    group_by: str,
    json_output: bool,
) -> None:
    """Estadísticas del corpus agrupadas por una dimensión.

    Dimensiones válidas: status (default), year, is_seed.
    """
    from bib2graph.service.reads import corpus_stats

    ws = resolve_workspace(ctx.obj)
    data = corpus_stats(ws, group_by=group_by)
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="read stats",
            ok=True,
            data=data,
            exit_code=0,
            warnings=workspace_walkup_warning(ws) or None,
        )
        emit(envelope)
    else:
        emit_human(f"Total papers: {data['total']}")
        emit_human(f"Agrupado por: {data['group_by']}")
        for group in data["groups"]:
            emit_human(f"  {group['key']}: {group['count']}")


# read show


@read_grp.command("show")
@click.option(
    "--id",
    "ident",
    required=True,
    help=(
        "Identificador del paper: id interno, DOI o source_id. "
        "Se prueba en ese orden (ADR 0036)."
    ),
)
@json_option
@click.pass_context
@handle_errors("read show")
def show_cmd(
    ctx: click.Context,
    ident: str,
    json_output: bool,
) -> None:
    """Muestra la fila completa de un paper.

    Resuelve --id contra id, doi y source_id (en ese orden de prioridad).
    Devuelve ~14 campos: id, source_id, doi, title, year, abstract, is_seed,
    curation_status, authors_raw, authors_id, keywords_id, references_id,
    cited_by_id, provenance.
    """
    from bib2graph.service.reads import get_paper

    ws = resolve_workspace(ctx.obj)
    data = get_paper(ws, ident)
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="read show",
            ok=True,
            data=data,
            exit_code=0,
            warnings=workspace_walkup_warning(ws) or None,
        )
        emit(envelope)
    else:
        emit_human(f"id:               {data.get('id')}")
        emit_human(f"title:            {data.get('title')}")
        emit_human(f"year:             {data.get('year')}")
        emit_human(f"doi:              {data.get('doi')}")
        emit_human(f"source_id:        {data.get('source_id')}")
        emit_human(f"curation_status:  {data.get('curation_status')}")
        emit_human(f"is_seed:          {data.get('is_seed')}")
        abstract = data.get("abstract") or ""
        emit_human(
            f"abstract:         {abstract[:120]}{'…' if len(abstract) > 120 else ''}"
        )


# read top

_NETWORK_KIND_CHOICES: list[str] = [nk.value for nk in NetworkKind]


@read_grp.command("top")
@click.option(
    "--top",
    "-n",
    "n",
    default=10,
    type=int,
    show_default=True,
    help="Número de nodos/pares a mostrar.",
)
@click.option(
    "--kind",
    default=NetworkKind.BIBLIOGRAPHIC_COUPLING.value,
    show_default=True,
    type=click.Choice(_NETWORK_KIND_CHOICES),
    help="Tipo de red para el bloque de nodos centrales.",
)
@json_option
@click.pass_context
@handle_errors("read top")
def top_cmd(
    ctx: click.Context,
    n: int,
    kind: str,
    json_output: bool,
) -> None:
    """Muestra los nodos más centrales y los pares de co-citación con título.

    Dos bloques de salida:

    \b
      central    — top N nodos de la red --kind, ordenados por degree_centrality
                   descendente.  Default: bibliographic_coupling (robusto en
                   one-shot frío, no requiere enrich previo).
      cocitation — top N pares de co-citación por peso, SIEMPRE desde la red
                   cocitation (requiere cited_by_id poblado: por un
                   'b2g chain --direction forward' previo o la pasada cited_by
                   de 'b2g build').  Si la red está vacía → bloque vacío con
                   reason/fix_command (honest-empty, exit 0).

    No requiere 'b2g build' previo: recomputa en tiempo de lectura.
    """
    from bib2graph.service.reads import get_top

    ws = resolve_workspace(ctx.obj)
    data = get_top(ws, n=n, kind=kind)
    data["workspace"] = workspace_echo(ws)

    if json_mode(json_output):
        envelope = build_envelope(
            command="read top",
            ok=True,
            data=data,
            exit_code=0,
            warnings=workspace_walkup_warning(ws) or None,
        )
        emit(envelope)
    else:
        emit_human(f"Nodos centrales ({kind}) — top {n}:")
        for node in data["central"]:
            dc = node["degree_centrality"]
            title_str = node.get("title") or node["id"]
            emit_human(f"  {node['id']}  dc={dc:.4f}  {title_str}")

        emit_human(f"\nPares de co-citación — top {n}:")
        for pair in data["cocitation"]:
            src = pair.get("source_title") or pair["source"]
            tgt = pair.get("target_title") or pair["target"]
            emit_human(f"  [{pair['weight']}]  {src}  ↔  {tgt}")

        if "reason" in data:
            emit_human(f"\nCo-citación vacía: {data['reason']}")
            if data.get("fix_command"):
                emit_human(f"Solución: {data['fix_command']}")
