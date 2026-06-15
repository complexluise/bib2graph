"""06 — Aplicar el thesaurus multilingüe a las keywords del corpus.

Toma el ``corpus_ied.parquet`` producido por ``03_merge_corpus.py`` y, para
cada paper, mapea cada keyword (en cualquiera de los idiomas del thesaurus)
a su **concepto canónico**. Lo hace **en la columna** ``keywords_id`` (que
es la que consume ``04_build_networks.py`` para construir la red de co-word).

Reglas:
- La búsqueda de aliases es **case-insensitive** y **normaliza acentos**
  (``deuda ecol{\'o}gica`` se trata igual a ``deuda ecologica``).
- Si una keyword matchea un alias, se reemplaza por la clave canónica.
- Si no matchea, se queda como está (no se inventan matches).
- **Idempotente**: correr dos veces no rompe nada.

El thesaurus vive en ``datos/thesaurus_ied.json`` y es **auditable a mano**
(ver su campo ``_meta.limitations``).
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "datos"


def _norm(s: str) -> str:
    """Lowercase + sin acentos + trim + colapsa espacios."""
    s = s.lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def load_thesaurus(path: Path) -> dict[str, dict[str, list[str]]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    table: dict[str, str] = {}
    for canonical, spec in data["concepts"].items():
        for lang_key, aliases in spec.items():
            if not lang_key.startswith("aliases_"):
                continue
            for alias in aliases:
                table[_norm(alias)] = canonical
    return table


def map_keyword(kw: str, table: dict[str, str]) -> str:
    n = _norm(kw)
    return table.get(n, n)


def apply_thesaurus_to_papers(
    papers: list[dict[str, object]], table: dict[str, str]
) -> tuple[list[dict[str, object]], int, int]:
    n_total = 0
    n_mapped = 0
    out: list[dict[str, object]] = []
    for paper in papers:
        kws = paper.get("keywords_raw") or []
        new_canonicals: list[str] = []
        mapped_count = 0
        for kw in kws:
            n_total += 1
            canonical = map_keyword(kw, table)
            if canonical != _norm(kw):
                mapped_count += 1
            new_canonicals.append(canonical)
        seen = set()
        deduped: list[str] = []
        for c in new_canonicals:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        new_paper = dict(paper)
        new_paper["keywords_id"] = deduped
        n_mapped += mapped_count
        out.append(new_paper)
    return out, n_total, n_mapped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-parquet", type=Path, default=DATA_DIR / "corpus_ied.parquet")
    parser.add_argument("--thesaurus", type=Path, default=DATA_DIR / "thesaurus_ied.json")
    parser.add_argument("--out-parquet", type=Path, default=DATA_DIR / "corpus_ied.parquet")
    args = parser.parse_args()

    if not args.in_parquet.exists():
        print(f"[06] ERROR: no existe {args.in_parquet}.", file=sys.stderr)
        return 2
    if not args.thesaurus.exists():
        print(f"[06] ERROR: no existe {args.thesaurus}.", file=sys.stderr)
        return 2

    import pyarrow.parquet as pq
    papers = pq.read_table(args.in_parquet).to_pylist()
    table = load_thesaurus(args.thesaurus)
    print(f"[06] Thesaurus: {len(table)} aliases cargados de {args.thesaurus.name}",
          file=sys.stderr)

    new_papers, n_total, n_mapped = apply_thesaurus_to_papers(papers, table)
    print(f"[06] Keywords: {n_mapped}/{n_total} mapeadas al canónico "
          f"({n_mapped / n_total:.0%})", file=sys.stderr)
    n_unique_canonical = len({k for p in new_papers for k in p["keywords_id"]})
    print(f"[06] Keywords canónicas únicas: {n_unique_canonical}", file=sys.stderr)

    arrays: dict[str, list[object]] = {}
    cols = list(papers[0].keys()) if papers else []
    for c in cols:
        arrays[c] = [p.get(c) for p in new_papers]
    import pyarrow as pa
    new_table = pa.table(arrays)
    args.out_parquet.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(new_table, args.out_parquet)
    print(f"[06] Corpus actualizado -> {args.out_parquet}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
