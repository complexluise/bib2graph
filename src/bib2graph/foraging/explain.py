"""foraging.explain — ``explain_candidate`` (stub gateado en ``[llm]``).

La función tiene la firma real pero hace import perezoso del extra ``[llm]``.
Si el extra no está instalado, lanza un error accionable con instrucciones de
instalación.  El forrajeo funciona sin este módulo.

Historia B4 (API.md §5): esta función es un paso OPCIONAL de IA que explica
por qué un candidato es relevante.  NO toma decisiones por el humano.

Ver docs/API.md §5 y AGENTS.md §"Importar perezoso de extras".
"""

from __future__ import annotations

from bib2graph.corpus import Corpus


def explain_candidate(corpus: Corpus, paper_id: str) -> str:
    """Explica por qué un candidato es relevante en el contexto del corpus.

    Requiere el extra ``[llm]`` (``uv sync --extra llm``).  Sin él, lanza
    un ``ImportError`` accionable.  Esta función es OPCIONAL: el forrajeo y
    el ranking funcionan sin ella.

    Args:
        corpus: Corpus de referencia (semillas + curados) para el contexto.
        paper_id: ``id`` del paper candidato a explicar.

    Returns:
        Explicación textual del candidato.

    Raises:
        ImportError: Si el extra ``[llm]`` no está instalado.
        NotImplementedError: Siempre (stub: la llamada LLM no está construida).
    """
    try:
        import importlib

        importlib.import_module("bib2graph.llm")
    except ImportError as exc:
        raise ImportError(
            "explain_candidate requiere el extra [llm]. "
            "Instalalo con: uv sync --extra llm\n"
            f"Error original: {exc}"
        ) from exc

    raise NotImplementedError(
        "explain_candidate es un stub: la integración LLM se construye en v0.2. "
        "Instalá el extra [llm] cuando esté disponible."
    )
