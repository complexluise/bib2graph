---
title: CLI b2g
---

# CLI `b2g`

Referencia completa del CLI agente-native `b2g`: el grupo principal y todos sus
subcomandos, con sus opciones y textos de ayuda. Se **autogenera desde el grupo
Click** (mkdocs-click): es la misma información que `b2g --help`, siempre en
sincronía con el código.

!!! info "Salida JSON"
    Cada subcomando acepta `--json` (envelope versionado) y respeta los exit
    codes 0–5. Los detalles del contrato (envelope, exit codes, FSM) están en
    [Contratos detallados](../API.md).

::: mkdocs-click
    :module: bib2graph.cli
    :command: b2g
    :prog_name: b2g
    :depth: 1
    :style: table
