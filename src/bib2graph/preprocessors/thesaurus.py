"""preprocessors.thesaurus — thesaurus multilingüe determinista (funciones puras).

Lee ``keywords_raw`` y sobrescribe ``keywords_id`` con los conceptos
canónicos (decisión d=A, ADR 0011).

Formato del thesaurus JSON::

    {
        "concepts": {
            "unequal_exchange": {
                "aliases_en": ["unequal exchange", ...],
                "aliases_es": ["intercambio desigual", ...],
                "aliases_pt": ["troca desigual", ...]
            },
            ...
        }
    }

Reglas:
- Búsqueda case-insensitive + normalización de acentos (NFD).
- Idempotente: el canónico mapea a sí mismo (si ``unequal_exchange`` aparece
  como keyword_raw, se mapea al mismo canónico).
- Si una keyword no matchea, se deja como está (no se inventan matches).
- Multilingüe: en/es/pt (el thesaurus declara ``aliases_{en|es|pt}``).
- Acepta ``dict`` (ya cargado) o ``Path`` (lo lee y parsea).

Ver docs/API.md §6, ADR 0011, decisión d=A.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path


def _norm(s: str) -> str:
    """Lowercase + quitar acentos + trim + colapso de espacios.

    Mismo algoritmo que en ``exploracion/scripts/06_apply_thesaurus.py``
    para garantizar compatibilidad con los thesauri existentes.

    Args:
        s: Cadena a normalizar.

    Returns:
        Cadena normalizada.
    """
    s = s.lower().strip()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


def load_thesaurus(thesaurus: dict[str, object] | Path) -> dict[str, str]:
    """Carga el thesaurus y construye el lookup ``alias_norm → canonical``.

    Si ``thesaurus`` es un ``dict``, se usa directamente.  Si es un ``Path``,
    lo lee y parsea como JSON.

    El lookup es idempotente: el propio canónico (normalizado) apunta a sí
    mismo como alias implícito.

    Args:
        thesaurus: Datos del thesaurus (dict) o ruta al JSON (Path).

    Returns:
        Dict ``{alias_normalizado: canonical}`` listo para mapear.

    Raises:
        FileNotFoundError: Si ``thesaurus`` es un ``Path`` que no existe.
        KeyError: Si el JSON no tiene la clave ``'concepts'``.
    """
    if isinstance(thesaurus, Path):
        data: dict[str, object] = json.loads(thesaurus.read_text(encoding="utf-8"))
    else:
        data = dict(thesaurus)

    lookup: dict[str, str] = {}
    concepts: dict[str, object] = data["concepts"]  # type: ignore[assignment]
    for canonical, spec in concepts.items():
        # El propio canónico también mapea a sí mismo (idempotencia)
        lookup[_norm(canonical)] = canonical
        spec_dict: dict[str, list[str]] = spec  # type: ignore[assignment]
        for lang_key, aliases in spec_dict.items():
            if not lang_key.startswith("aliases_"):
                continue
            for alias in aliases:
                lookup[_norm(alias)] = canonical

    return lookup


def apply_thesaurus_to_rows(
    rows: list[dict[str, object]],
    lookup: dict[str, str],
) -> list[dict[str, object]]:
    """Aplica el lookup del thesaurus a las filas del corpus.

    Lee ``keywords_raw`` y sobrescribe ``keywords_id`` con los canónicos.
    Las keywords que no matchean se mantienen tal cual (normalización mínima).
    Deduplicación: si dos keywords distintas mapean al mismo canónico, se
    cuenta solo una vez (preservando el orden de aparición).

    Args:
        rows: Lista de filas del corpus como dicts.
        lookup: Lookup ``{alias_norm → canonical}`` de ``load_thesaurus``.

    Returns:
        Nueva lista de filas con ``keywords_id`` actualizado.
    """
    result: list[dict[str, object]] = []
    for row in rows:
        kws_raw = row.get("keywords_raw")
        if not isinstance(kws_raw, list) or not kws_raw:
            # Sin keywords_raw: dejar keywords_id intacto
            result.append(dict(row))
            continue

        new_ids: list[str] = []
        seen: set[str] = set()
        for kw in kws_raw:
            if not isinstance(kw, str):
                continue
            canonical = lookup.get(_norm(kw), _norm(kw))
            if canonical not in seen:
                seen.add(canonical)
                new_ids.append(canonical)

        new_row = dict(row)
        from bib2graph.constants import Col

        new_row[Col.KEYWORDS_ID] = new_ids if new_ids else None
        result.append(new_row)

    return result
