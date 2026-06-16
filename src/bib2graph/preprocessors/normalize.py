"""preprocessors.normalize — normalización mínima/conservadora (función pura).

Operaciones (decisión b=A):
- ``authors_id``: lowercase + trim + colapso de espacios + quitar acentos
  (NFD + filtro de Mn).  Sin unificación fuzzy de autores (eso es Hito 7
  ``[dedup]``).
- ``language``: normaliza a ISO 639-1 si el valor es un código largo trivial
  (p. ej. ``en-US`` → ``en``, ``es_419`` → ``es``).  Sin tablas de mapeo
  exhaustivas.

Idempotente: aplicar normalize dos veces produce el mismo resultado que
aplicarla una vez.

Ver docs/API.md §6, ADR 0011, decisión b=A.
"""

from __future__ import annotations

import unicodedata


def _norm_str(s: str) -> str:
    """Lowercase + quitar acentos + trim + colapso de espacios.

    Args:
        s: Cadena a normalizar.

    Returns:
        Cadena normalizada.
    """
    s = s.strip().lower()
    # Quitar diacríticos (NFD + filtro de Mn)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    # Colapsar espacios internos múltiples
    return " ".join(s.split())


def normalize_authors_id(authors_id: list[str] | None) -> list[str] | None:
    """Normaliza la lista de ids de autor.

    Aplica ``_norm_str`` a cada elemento.  Si la lista es ``None`` o vacía,
    devuelve ``None``.

    Args:
        authors_id: Lista de ids de autor crudos (ORCID o nombre).

    Returns:
        Lista normalizada, o ``None`` si la entrada es ``None``/vacía.
    """
    if not authors_id:
        return None
    return [_norm_str(a) for a in authors_id]


def normalize_language(language: str | None) -> str | None:
    """Normaliza el código de idioma a ISO 639-1 cuando es trivial.

    Trunca al subtag primario (``en-US`` → ``en``, ``es_419`` → ``es``).
    Si el valor es ``None`` o vacío, devuelve ``None``.

    Args:
        language: Código de idioma crudo.

    Returns:
        Código ISO 639-1 (2 letras), o ``None``.
    """
    if not language:
        return None
    # Normalizar separadores y tomar el primer subtag
    lang = language.strip().replace("_", "-").split("-")[0].lower()
    return lang if lang else None


def normalize_row(row: dict[str, object]) -> dict[str, object]:
    """Aplica normalización a una fila del corpus.

    Opera sobre ``authors_id`` y ``language`` (decisión b=A).
    El resto de las columnas pasan sin cambios.

    Args:
        row: Fila como dict (resultado de ``to_pylist()``).

    Returns:
        Nueva fila con los campos normalizados.
    """
    from bib2graph.constants import Col

    new_row = dict(row)
    authors_id = row.get(Col.AUTHORS_ID)
    if isinstance(authors_id, list):
        new_row[Col.AUTHORS_ID] = normalize_authors_id(authors_id)
    language = row.get(Col.LANGUAGE)
    if isinstance(language, str):
        new_row[Col.LANGUAGE] = normalize_language(language)
    return new_row
