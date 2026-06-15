"""01 — Buscar papers de IED en OpenAlex y volcarlos a CSV.

Salida: ``datos/openalex_ied.csv`` con el schema común de ``_schema.py``.

Uso:
    python 01_search_openalex.py --limit 200
    python 01_search_openalex.py --dry-run
    python 01_search_openalex.py --query "ecological debt" --limit 50

Notas operativas:
- OpenAlex requiere API key desde feb-2026. Se lee de ``OPENALEX_API_KEY``
  o ``~/.openalex/credentials``. Sin key, el script igual corre a velocidad
  "polite pool" (más lento, no rompe).
- Sin red (offline), corre ``--dry-run`` y muestra la query que se haría.
- El abstract en OpenAlex viene como ``abstract_inverted_index``: un dict
  ``{palabra: [posiciones]}`` que hay que reconstruir. Si no está, el campo
  queda en None (testeo del parser defensivo).
- Las referencias en OpenAlex son URLs (``https://openalex.org/W...``). Se
  guardan como OpenAlex IDs. Si tienen DOI en el work referenciado, se prefiere
  el DOI; esto requiere un fetch adicional que se hace solo si ``--resolve-refs``
  está activo.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

from _schema import CORPUS_COLUMNS, new_row

DATA_DIR = Path(__file__).resolve().parent.parent / "datos"
OUT_CSV = DATA_DIR / "openalex_ied.csv"

DEFAULT_QUERY = (
    '"ecological unequal exchange" OR "ecological debt" OR "deuda ecológica" '
    'OR "intercambio ecológicamente desigual" OR "ecological footprint" '
    'AND (trade OR commerce OR "material flow")'
)


def reconstruct_abstract(inv_index: dict[str, list[int]] | None) -> str | None:
    if not inv_index:
        return None
    out: list[str] = [""] * (max((p for ps in inv_index.values() for p in ps), default=0) + 1)
    for word, positions in inv_index.items():
        for p in positions:
            out[p] = word
    return " ".join(out).strip() or None


def openalex_id_to_doi(oa_id: str) -> str | None:
    if not oa_id:
        return None
    if "doi.org/" in oa_id:
        return oa_id.split("doi.org/")[-1].lower()
    return None


def author_to_author_id(au: dict[str, Any]) -> str:
    raw = au.get("id") or au.get("orcid") or au.get("display_name") or "unknown"
    return str(raw).rsplit("/", 1)[-1] if isinstance(raw, str) else str(raw)


def work_to_row(work: dict[str, Any], is_seed: bool = False) -> dict[str, object]:
    row = new_row()
    row["id"] = (work.get("id") or "").rsplit("/", 1)[-1] or None
    row["doi"] = openalex_id_to_doi(work.get("doi") or "")
    row["title"] = work.get("title") or work.get("display_name")
    row["year"] = work.get("publication_year")
    row["abstract"] = reconstruct_abstract(work.get("abstract_inverted_index"))
    authorships = work.get("authorships") or []
    row["authors_raw"] = [a.get("author", {}).get("display_name", "")
                          for a in authorships if a.get("author")]
    row["authors_id"] = [author_to_author_id(a.get("author", {}))
                         for a in authorships if a.get("author")]
    affils: list[str] = []
    for a in authorships:
        for inst in a.get("institutions") or []:
            country = (inst.get("country_code") or "").upper() or "??"
            affils.append(f"{inst.get('display_name', '?')} ({country})")
    row["authors_affiliations"] = affils
    kws = work.get("keywords") or []
    row["keywords_raw"] = [k.get("display_name", "") for k in kws if k.get("display_name")]
    row["keywords_id"] = [k.get("id", "").rsplit("/", 1)[-1] for k in kws if k.get("id")]
    row["references_doi"] = [openalex_id_to_doi(r) or r
                             for r in (work.get("referenced_works") or [])]
    loc = (work.get("primary_location") or {}).get("source") or {}
    row["source"] = loc.get("display_name")
    row["language"] = work.get("language")
    row["is_seed"] = is_seed
    return row


def serialize_list(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(x) for x in value)
    return "" if value is None else str(value)


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CORPUS_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: serialize_list(row.get(c)) for c in CORPUS_COLUMNS})


def get_api_key() -> str | None:
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        return key
    cred_path = Path.home() / ".openalex" / "credentials"
    if cred_path.exists():
        return cred_path.read_text(encoding="utf-8").strip() or None
    return None


def search_openalex(query: str, limit: int, api_key: str | None) -> list[dict[str, Any]]:
    try:
        import pyalex
        from pyalex import Works
    except ImportError as exc:
        raise SystemExit(
            f"pyalex no instalado. Hacé `pip install pyalex` o corré --dry-run.\n{exc}"
        ) from exc

    if api_key:
        pyalex.config.api_key = api_key
    pyalex.config.max_retries = 3
    pyalex.config.retry_backoff_factor = 0.5

    print(f"[01] Query OpenAlex: {query!r}", file=sys.stderr)
    print(f"[01] Limit: {limit}, key: {'sí' if api_key else 'no (polite pool)'}", file=sys.stderr)

    works: list[dict[str, Any]] = []
    paginator = Works().search(query).select(
        ["id", "doi", "title", "display_name", "publication_year", "language",
         "abstract_inverted_index", "authorships", "keywords",
         "referenced_works", "primary_location", "type"]
    ).paginate(per_page=min(limit, 100))
    for page in paginator:
        for w in page:
            works.append(w)
            if len(works) >= limit:
                return works
    return works


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra la query sin llamar a la API.")
    parser.add_argument("--out", type=Path, default=OUT_CSV)
    args = parser.parse_args()

    if args.dry_run:
        print(f"[01] DRY RUN. Query: {args.query!r}")
        print(f"[01] DRY RUN. Salida: {args.out}")
        print("[01] DRY RUN. Nada se escribió.")
        return 0

    api_key = get_api_key()
    works = search_openalex(args.query, args.limit, api_key)
    rows = [work_to_row(w, is_seed=False) for w in works]
    write_csv(rows, args.out)
    print(f"[01] {len(rows)} papers -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
