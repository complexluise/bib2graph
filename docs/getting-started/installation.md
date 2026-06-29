---
title: Instalación
---

# Instalación

bib2graph necesita **Python ≥ 3.11**.

## Con uv (recomendado)

Recomendamos [**uv**](https://docs.astral.sh/uv/) para gestionar el entorno:

```bash
uv add bib2graph
```

## Con pip

```bash
pip install bib2graph
```

## Extras opcionales

Algunas capacidades viven en extras opt-in para mantener el núcleo liviano:

| Extra | Habilita | Instalar |
|-------|----------|----------|
| `bibtex` | Sembrar el corpus desde archivos `.bib` | `uv add "bib2graph[bibtex]"` |
| `gui` | Interfaz local (FastAPI + SPA), aún en construcción | `uv add "bib2graph[gui]"` |

## Verificá la instalación

```bash
b2g --help
```

Deberías ver el grupo de comandos del CLI `b2g`. Si es así, seguí con el
[Quickstart](quickstart.md).
