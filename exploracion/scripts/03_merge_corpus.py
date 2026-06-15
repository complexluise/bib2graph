"""03 — Unir múltiples CSVs en un solo corpus, deduplicar y dumpear parquet.

Decisiones de la sandbox:
- **Dedupe por DOI normalizado** (lowercase, sin prefijo ``https://``). Si dos
  filas comparten DOI, se mergea: gana la que tiene más campos no vacíos, y
  se hace OR lógico sobre ``is_seed`` (si alguna fuente la marcó como semilla,
  queda como semilla).
- Si no hay DOI, se cae al ``id`` sintético (``bib:`` o ``W...`` de OpenAlex).
- La **lista** de campos se deserializa de CSV (``";"``-separado) a ``list[str]``
  antes de pasar a parquet, y se serializa al revés al leer.
- Salida:
    - ``datos/corpus_ied.csv``  — para inspección humana.
    - ``datos/corpus_ied.parquet`` — para los scripts siguientes (más rápido).
- Imprime un resumen de qué se mergeó y qué se descartó.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _schema import CORPUS_COLUMNS, new_row

DATA_DIR = Path(__file__).resolve().parent.parent / "datos"

_LIST_COLUMNS = {"authors_raw", "authors_id", "authors_affiliations",
                 "keywords_raw", "keywords_id", "references_doi"}


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d or None


def read_csv(path: Path) -> list[dict[str, object]]:
    import csv
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            row = new_row()
            for c in CORPUS_COLUMNS:
                val = raw.get(c, "")
                if c in _LIST_COLUMNS:
                    row[c] = [v.strip() for v in val.split(";") if v.strip()]
                elif c == "year":
                    row[c] = int(val) if val and val.strip().isdigit() else None
                elif c == "is_seed":
                    row[c] = val.lower() in {"true", "1", "yes", "sí", "si"}
                else:
                    row[c] = val.strip() or None
            rows.append(row)
    return rows


def fillness(row: dict[str, object]) -> int:
    return sum(1 for v in row.values() if v not in (None, "", []))


def merge_rows(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    """Gana la fila con más campos llenos; mergea listas; OR sobre is_seed."""
    winner = a if fillness(a) >= fillness(b) else b
    loser = b if winner is a else a
    out = dict(winner)
    for col in _LIST_COLUMNS:
        merged = list(winner.get(col) or []) + [x for x in (loser.get(col) or [])
                                                if x not in (winner.get(col) or [])]
        out[col] = merged
    out["is_seed"] = bool(winner.get("is_seed")) or bool(loser.get("is_seed"))
    return out


def dedupe(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, int]]:
    by_doi: dict[str, dict[str, object]] = {}
    by_id: dict[str, dict[str, object]] = {}
    no_key: list[dict[str, object]] = []
    stats = {"by_doi": 0, "by_id": 0, "no_key": 0}

    for row in rows:
        doi = normalize_doi(row.get("doi"))
        rid = row.get("id")
        if doi:
            if doi in by_doi:
                by_doi[doi] = merge_rows(by_doi[doi], row)
                stats["by_doi"] += 1
            else:
                by_doi[doi] = row
        elif rid:
            if rid in by_id:
                by_id[rid] = merge_rows(by_id[rid], row)
                stats["by_id"] += 1
            else:
                by_id[rid] = row
        else:
            no_key.append(row)
            stats["no_key"] += 1

    return list(by_doi.values()) + list(by_id.values()) + no_key, stats


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CORPUS_COLUMNS)
        writer.writeheader()
        for row in rows:
            serialized: dict[str, object] = {}
            for c in CORPUS_COLUMNS:
                v = row.get(c)
                if isinstance(v, list):
                    serialized[c] = "; ".join(str(x) for x in v)
                else:
                    serialized[c] = "" if v is None else str(v)
            writer.writerow(serialized)


def write_parquet(rows: list[dict[str, object]], path: Path) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit(f"pyarrow no instalado. `pip install pyarrow`.\n{exc}") from exc

    arrays: dict[str, list[object]] = {c: [] for c in CORPUS_COLUMNS}
    for row in rows:
        for c in CORPUS_COLUMNS:
            v = row.get(c)
            if c in _LIST_COLUMNS and v is None:
                v = []
            arrays[c].append(v)
    table = pa.table(arrays)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, required=True,
                        help="CSVs a unir (uno o más).")
    parser.add_argument("--out-csv", type=Path, default=DATA_DIR / "corpus_ied.csv")
    parser.add_argument("--out-parquet", type=Path, default=DATA_DIR / "corpus_ied.parquet")
    args = parser.parse_args()

    all_rows: list[dict[str, object]] = []
    for src in args.inputs:
        if not src.exists():
            print(f"[03] WARN: {src} no existe, lo salto.", file=sys.stderr)
            continue
        rows = read_csv(src)
        print(f"[03] {len(rows):>4} filas de {src}", file=sys.stderr)
        all_rows.extend(rows)
    print(f"[03] Total sin dedup: {len(all_rows)}", file=sys.stderr)

    merged, stats = dedupe(all_rows)
    print(f"[03] Dedup: {stats['by_doi']} merges por DOI, "
          f"{stats['by_id']} por id, {stats['no_key']} sin clave.", file=sys.stderr)
    print(f"[03] Total dedupeado: {len(merged)}", file=sys.stderr)

    n_seed = sum(1 for r in merged if r.get("is_seed"))
    n_with_doi = sum(1 for r in merged if r.get("doi"))
    n_with_kw = sum(1 for r in merged if r["keywords_raw"])
    n_with_abs = sum(1 for r in merged if r.get("abstract"))
    print(f"[03] Composición: {n_seed} semillas, {n_with_doi} con DOI, "
          f"{n_with_kw} con keywords, {n_with_abs} con abstract.", file=sys.stderr)

    write_csv(merged, args.out_csv)
    write_parquet(merged, args.out_parquet)
    print(f"[03] CSV     -> {args.out_csv}", file=sys.stderr)
    print(f"[03] Parquet -> {args.out_parquet}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
