#!/usr/bin/env python
"""Guardarraíl de PreToolUse para bib2graph.

Lee el JSON del hook por stdin. Si el comando viola una regla dura del flujo,
imprime el porqué en stderr y sale con código 2 (Claude Code bloquea la acción).
Si todo está bien, sale 0 y la acción procede.

Reglas (las no-negociables del proyecto):
  - npm           -> usar pnpm (preferencia firme del PO)
  - pip install   -> usar uv
  - push a main/dev (push directo a rama protegida)
  - commit estando parado en main/dev (ramear primero)
  - editar CHANGELOG.md / version de pyproject a mano (lo hace release-please)
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys

with contextlib.suppress(Exception):
    sys.stderr.reconfigure(encoding="utf-8")  # mensajes con acentos sin mojibake


def block(reason: str) -> None:
    print(f"[guardarraíl bib2graph] {reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # sin payload válido, no bloqueamos nada

    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    cmd = ti.get("command") or ""
    low = cmd.lower()

    # --- Reglas sobre comandos de shell (Bash / PowerShell) ---
    if tool in ("Bash", "PowerShell"):
        if re.search(r"(^|\s|&|;|\|)npm(\s|$)", low):
            block("Usá pnpm, no npm (preferencia firme del PO).")

        if re.search(r"pip\s+install", low):
            block("Usá uv (uv add / uv sync), no pip install.")

        if re.search(r"git\s+push", low) and re.search(r"\b(main|dev)\b", low):
            block("Push directo a main/dev prohibido. Rameá (feat/...) y abrí PR.")

        if re.match(r"\s*git\s+commit", low):
            try:
                branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
                ).strip()
            except Exception:
                branch = ""
            if branch in ("main", "dev"):
                block(
                    f"Estás en '{branch}' (rama protegida). Rameá (feat/...) antes "
                    "de commitear; el trabajo va por PR."
                )

    # --- Reglas sobre edición de archivos gestionados por el bot ---
    if tool in ("Edit", "Write"):
        path = (ti.get("file_path") or "").replace("\\", "/").lower()
        if path.endswith("changelog.md"):
            block("CHANGELOG.md lo gestiona release-please. No lo edites a mano.")

    sys.exit(0)


if __name__ == "__main__":
    main()
