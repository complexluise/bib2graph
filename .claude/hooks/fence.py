#!/usr/bin/env python
"""Fence por agente: niega Edit/Write fuera del territorio del agente.

Uso (en el frontmatter del agente; invocar vía uv para garantizar el intérprete):
    command: "uv run --no-sync --quiet python .claude/hooks/fence.py docs"        # niega docs/
    command: "uv run --no-sync --quiet python .claude/hooks/fence.py src tests"   # niega src/ y tests/

Lee el JSON del hook por stdin. Si el agente intenta Edit/Write sobre un archivo
cuyo primer segmento de ruta (relativo al repo) está en la lista de denegados,
imprime el porqué en stderr y sale 2 (Claude Code bloquea). Si no, sale 0.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys

with contextlib.suppress(Exception):
    sys.stderr.reconfigure(encoding="utf-8")


def main() -> None:
    denied = sys.argv[1:]
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name", "") not in ("Edit", "Write", "NotebookEdit"):
        sys.exit(0)

    ti = data.get("tool_input", {}) or {}
    path = ti.get("file_path") or ""
    if not path:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    try:
        rel = os.path.relpath(os.path.abspath(path), cwd).replace("\\", "/")
    except Exception:
        rel = path.replace("\\", "/")
    first = rel.split("/")[0]

    if first in denied:
        print(
            f"[fence] Este agente no es dueño de '{first}/' y no puede editarlo. "
            f"Eso es artefacto de otro rol; recomendá el cambio en tu reporte.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
