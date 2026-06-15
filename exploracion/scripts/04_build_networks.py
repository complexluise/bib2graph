"""04 — Construir las 4 redes bibliométricas y exportarlas a GraphML.

Redes (orden de la tabla de ``docs/API.md`` §5):
- **co_citacion**:   papers semilla que comparten referencias.
                    Peso = # de referencias compartidas.
                    Nodos = papers semilla; aristas = co-citación.
- **co_autoria**:    autores que co-firman papers semilla.
                    Peso = # de papers co-firmados.
                    Nodos = autores; aristas = co-firma.
- **co_word**:       keywords que co-ocurren en papers semilla.
                    Peso = # de papers que comparten esa keyword.
                    Nodos = keywords; aristas = co-ocurrencia.
- **coupling**:      papers semilla que comparten referencias.
                    **Conceptualmente** igual a co-citación pero **la unidad
                    es el par de papers que citan lo mismo, no las
                    referencias citadas**. Acá lo implementamos como
                    "papers del corpus que comparten al menos una referencia
                    resuelta por DOI". Si no hay refs, queda vacío.

Decisiones de la sandbox:
- Solo se usan **papers semilla** (``is_seed=True``) en co-citación, co-word
  y coupling. Co-autoría usa todos los autores firmantes de semillas.
- Las listas en parquet (``authors_id``, ``keywords_id``, ``references_doi``)
  son ``list[str]`` ya deserializadas (pyarrow + pyarrow.list_).
- El output es **GraphML** (interoperable con Gephi, VOSviewer, NetworkX).
- Cada red tiene atributos ``kind`` y ``seed_only`` (True/False) en metadata.
- Si la red queda vacía (ej: sin referencias), se escribe un GraphML mínimo
  con 0 nodos y 0 aristas **y se reporta** en stderr. No se rompe el pipeline.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import networkx as nx

DATA_DIR = Path(__file__).resolve().parent.parent / "datos"
REDES_DIR = DATA_DIR / "redes"


def load_corpus(path: Path) -> list[dict[str, object]]:
    import pyarrow.parquet as pq
    table = pq.read_table(path).to_pylist()
    return table


def build_co_citacion(seeds: list[dict[str, object]]) -> nx.Graph:
    """Nodos: papers semilla. Aristas: comparten >= 1 referencia (DOI)."""
    g = nx.Graph()
    for s in seeds:
        g.add_node(s["id"], label=s.get("title") or s["id"], year=s.get("year"))
    ref_index: dict[str, list[str]] = {}
    for s in seeds:
        for ref in s.get("references_doi") or []:
            if not ref:
                continue
            ref_index.setdefault(ref, []).append(s["id"])
    for _ref, papers in ref_index.items():
        for a, b in combinations(sorted(set(papers)), 2):
            if g.has_edge(a, b):
                g[a][b]["weight"] += 1
            else:
                g.add_edge(a, b, weight=1)
    return g


def build_co_autoria(seeds: list[dict[str, object]]) -> nx.Graph:
    """Nodos: autores. Aristas: co-firman >= 1 paper semilla."""
    g = nx.Graph()
    for s in seeds:
        authors = s.get("authors_id") or []
        for a in authors:
            if not a:
                continue
            g.add_node(a, label=a)
        for a, b in combinations(sorted(set(a for a in authors if a)), 2):
            if g.has_edge(a, b):
                g[a][b]["weight"] += 1
            else:
                g.add_edge(a, b, weight=1)
    return g


def build_co_word(seeds: list[dict[str, object]]) -> nx.Graph:
    """Nodos: keywords. Aristas: co-ocurren en >= 1 paper semilla."""
    g = nx.Graph()
    for s in seeds:
        kws = s.get("keywords_id") or []
        for k in kws:
            if not k:
                continue
            g.add_node(k, label=k)
        for a, b in combinations(sorted(set(k for k in kws if k)), 2):
            if g.has_edge(a, b):
                g[a][b]["weight"] += 1
            else:
                g.add_edge(a, b, weight=1)
    return g


def build_coupling(papers: list[dict[str, object]], scope: str = "seeds") -> nx.Graph:
    """Nodos: papers. Aristas: comparten >= 1 referencia por DOI.

    Acoplamento bibliográfico: dos papers están acoplados si comparten
    al menos una referencia. Distinto de co-citación: la co-citación mira
    papers que son citados **juntos por terceros** (los citadores); el
    coupling mira papers que **comparten su lista de referencias**.

    Parámetro ``scope``:
    - ``"seeds"`` (default, lo que hacía la v1): sólo papers semilla.
      Operacionalmente equivalente a co-citación cuando no hay citadores
      incorporados al corpus.
    - ``"full"``: corpus completo (semillas + citadores + referencias
      resueltas traídas por el Enricher, ``is_seed=False``). La diferencia
      con ``"seeds"`` aparece sólo si el corpus tiene citadores. Con
      datos sintéticos sin enriquecer, ambos dan lo mismo.

    Si los papers no declaran ``references_doi``, la red queda vacía.
    """
    g = nx.Graph()
    target = papers if scope == "full" else [p for p in papers if p.get("is_seed")]
    for s in target:
        g.add_node(s["id"], label=s.get("title") or s["id"],
                   year=s.get("year"), is_seed=bool(s.get("is_seed")))
    for a, b in combinations(target, 2):
        refs_a = set(a.get("references_doi") or [])
        refs_b = set(b.get("references_doi") or [])
        shared = refs_a & refs_b
        if shared:
            g.add_edge(a["id"], b["id"], weight=len(shared))
    return g


def report(g: nx.Graph, kind: str, n_seeds: int) -> None:
    n_e = g.number_of_edges()
    n_n = g.number_of_nodes()
    if n_n == 0:
        print(f"[04] {kind:<12} VACÍA (0 nodos, 0 aristas)", file=sys.stderr)
    else:
        density = nx.density(g)
        print(f"[04] {kind:<12} {n_n:>4} nodos, {n_e:>5} aristas, "
              f"densidad {density:.4f} (seeds={n_seeds})", file=sys.stderr)


def write_graphml(g: nx.Graph, path: Path, kind: str, n_seeds: int) -> None:
    g.graph["kind"] = kind
    g.graph["seed_only"] = True
    g.graph["n_seeds"] = n_seeds
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(g, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DATA_DIR / "corpus_ied.parquet")
    parser.add_argument("--out-dir", type=Path, default=REDES_DIR)
    parser.add_argument("--kinds", nargs="+",
                        default=["co_citacion", "co_autoria", "co_word", "coupling"])
    parser.add_argument("--coupling-scope", choices=["seeds", "full"], default="seeds",
                        help="Scope de la red coupling. 'seeds' (default) = solo "
                             "semillas; 'full' = corpus completo. Sólo se nota "
                             "la diferencia si hay citadores (is_seed=False) "
                             "en el corpus.")
    args = parser.parse_args()

    if not args.corpus.exists():
        print(f"[04] ERROR: no existe {args.corpus}. Corré 02/03 primero.", file=sys.stderr)
        return 2

    rows = load_corpus(args.corpus)
    seeds = [r for r in rows if r.get("is_seed")]
    n_total = len(rows)
    n_citadores = n_total - len(seeds)
    print(f"[04] Corpus: {n_total} filas totales, {len(seeds)} semillas, "
          f"{n_citadores} citadores (is_seed=False).", file=sys.stderr)

    builders = {
        "co_citacion": build_co_citacion,
        "co_autoria": build_co_autoria,
        "co_word": build_co_word,
    }
    for kind in args.kinds:
        if kind not in builders and kind != "coupling":
            print(f"[04] WARN: kind desconocido {kind!r}, lo salto.", file=sys.stderr)
            continue
        if kind == "coupling":
            g = build_coupling(rows, scope=args.coupling_scope)
            label = f"coupling[{args.coupling_scope}]"
        else:
            g = builders[kind](seeds)
            label = kind
        report(g, label, len(seeds))
        fname = f"{kind}.graphml" if kind != "coupling" else f"coupling_{args.coupling_scope}.graphml"
        out = args.out_dir / fname
        write_graphml(g, out, kind, len(seeds))
        print(f"[04] {label} -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
