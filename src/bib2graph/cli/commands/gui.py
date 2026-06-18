"""cli.commands.gui — 19º subcomando ``b2g gui`` (Hito G3, ADR 0028).

Levanta uvicorn sobre la API local FastAPI, sirve los assets pre-build del
frontend (si existen en ``src/bib2graph/gui/static/index.html``), e imprime la
URL con el token efímero.

Wiring del token (G4, B-G4-3): al servir ``index.html``, reemplaza el
placeholder ``__B2G_TOKEN__`` con el token real.  Los demás assets (JS, CSS,
etc.) se sirven con ``StaticFiles`` sin modificación.

El import de ``fastapi`` y ``uvicorn`` es **perezoso**: se hace dentro de
``run_gui`` para que el núcleo no los importe al arrancar el CLI sin el extra
``[gui]``.  Si faltan, lanza ``DependencyError`` (exit 3) con un mensaje
accionable.

Flags:
  --host  TEXT     Host de bind (default: 127.0.0.1).
  --port  INTEGER  Puerto (default: 8765).
  --no-browser     No abrir el browser automáticamente.
"""

from __future__ import annotations

from typing import Any

import click

from bib2graph.cli._errors import handle_errors
from bib2graph.cli._store import resolve_workspace

# Placeholder que el frontend espera en index.html y en window.__B2G_TOKEN__
_TOKEN_PLACEHOLDER = "__B2G_TOKEN__"


def _make_index_response(static_dir: object, token: str) -> object:
    """Construye una respuesta HTMLResponse con el token inyectado en index.html.

    Lee el ``index.html`` del directorio estático, reemplaza todas las
    ocurrencias del placeholder ``__B2G_TOKEN__`` con el token efímero y
    devuelve una ``HTMLResponse`` lista para ser usada como respuesta de
    un endpoint de FastAPI.

    Args:
        static_dir: ``pathlib.Path`` del directorio de assets.
        token: Token efímero generado en el arranque.

    Returns:
        ``HTMLResponse`` con el HTML modificado.
    """
    from pathlib import Path

    from fastapi.responses import HTMLResponse

    index_path = Path(str(static_dir)) / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = html.replace(_TOKEN_PLACEHOLDER, token)
    return HTMLResponse(content=html)


def run_gui(
    *,
    workspace_ctx: dict[str, object],
    host: str = "127.0.0.1",
    port: int = 8765,
    no_browser: bool = False,
) -> None:
    """Levanta la API local FastAPI con uvicorn.

    Verifica que ``fastapi`` y ``uvicorn`` estén instalados **antes** de
    importar ``bib2graph.api`` (import perezoso).  Si faltan → ``DependencyError``
    (exit 3) con sugerencia accionable.

    Cuando el frontend está buildeado (``gui/static/index.html`` existe),
    inyecta el token en el HTML servido reemplazando el placeholder
    ``__B2G_TOKEN__`` (G4, B-G4-3).

    Args:
        workspace_ctx: Dict ``ctx.obj`` del grupo Click (para ``resolve_workspace``).
        host: Host de bind (default: ``"127.0.0.1"``).
        port: Puerto (default: ``8765``).
        no_browser: Si ``True``, no abre el browser.

    Raises:
        DependencyError: Si ``fastapi`` o ``uvicorn`` no están instalados.
        UsageError: Si no se puede resolver el workspace.
    """
    # Import perezoso: verificar dependencias ANTES de importar bib2graph.api
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as exc:
        from bib2graph.cli._errors import DependencyError

        raise DependencyError(
            f"Dependencia GUI faltante: {exc}. "
            "Instalá el extra con: uv sync --extra gui"
        ) from exc

    from bib2graph.api.security import generate_token

    ws = resolve_workspace(workspace_ctx)
    token = generate_token()

    # Import de la API solo después de verificar que fastapi/uvicorn están disponibles
    import importlib.resources as _res
    from pathlib import Path

    from bib2graph.api import create_app

    static_dir: Path | None = None
    try:
        # Busca el static generado por G4/G5 en el paquete instalado
        pkg_root = Path(__file__).parent.parent.parent / "bib2graph" / "gui" / "static"
        if not pkg_root.exists():
            # Intentar vía importlib.resources (wheel instalado)
            pkg_root = Path(str(_res.files("bib2graph"))) / "gui" / "static"
        if pkg_root.exists() and (pkg_root / "index.html").exists():
            static_dir = pkg_root
    except Exception:
        static_dir = None

    app = create_app(ws, token=token, cors_origins=None)

    if static_dir is not None:
        from fastapi import Request
        from fastapi.staticfiles import StaticFiles

        # Ruta raíz: sirve index.html con el token inyectado (B-G4-3)
        @app.get("/", include_in_schema=False)  # type: ignore[untyped-decorator]
        async def serve_index(_request: Request) -> Any:
            """Sirve index.html con el token Bearer inyectado."""
            return _make_index_response(static_dir, token)

        # Assets estáticos (JS, CSS, imágenes, fuentes)
        app.mount(
            "/",
            StaticFiles(directory=str(static_dir), html=False),
            name="static",
        )
        click.echo(f"Frontend servido desde: {static_dir}")
    else:
        click.echo(
            "Advertencia: frontend no construido aún (G4). "
            "Solo la API está disponible.",
            err=True,
        )

    url = f"http://{host}:{port}"
    click.echo(f"b2g GUI — API en {url}")
    click.echo(f"Token: {token}")
    click.echo("Usá este token como Bearer en el header Authorization.")

    if not no_browser:
        import webbrowser

        webbrowser.open(url)

    import uvicorn as _uvicorn

    _uvicorn.run(app, host=host, port=port)


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------


@click.command("gui")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host de bind para la API.",
)
@click.option(
    "--port",
    default=8765,
    show_default=True,
    type=int,
    help="Puerto para la API.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="No abrir el browser automáticamente.",
)
@click.pass_context
@handle_errors("gui")
def gui_cmd(
    ctx: click.Context,
    host: str,
    port: int,
    no_browser: bool,
) -> None:
    """Levanta la API local GUI (FastAPI + uvicorn).

    Requiere el extra [gui]: uv sync --extra gui.
    Imprime la URL y el token efímero al arrancar.
    """
    run_gui(
        workspace_ctx=ctx.obj,
        host=host,
        port=port,
        no_browser=no_browser,
    )
