"""Genera el corpus.parquet de la e2e de 0.15.0.

Crea 8 papers sinteticos con `references_id` materializados (no son papers
reales, pero los ids simulan OpenAlex `W...` para que el acoplamiento
bibliografico pueda construir aristas). El grafo de referencias esta
disenado para tener 2 comunidades claras:

  Comunidad A: papers 1, 2, 3, 4 (todos citan a paper 5)
  Comunidad B: papers 5, 6, 7, 8 (todos citan a paper 1)

Asi el acoplamiento tiene aristas reales, el clustering Leiden detecta
2 comunidades, y `intra_community_pagerank` da valores no triviales.

Offline y determinista (R2 gate).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DST = Path(__file__).parent / "corpus.parquet"

# 8 papers sinteticos. source_id formato OpenAlex W + digitos.
papers = [
    # id, source_id, doi, title, year, references_id
    (
        "src:p1",
        "W1000000001",
        "10.1234/synth.001",
        "Synthetic paper on critical pedagogy and complexity (A1)",
        2003,
        ["W1000000005"],
    ),
    (
        "src:p2",
        "W1000000002",
        "10.1234/synth.002",
        "Synthetic paper on critical pedagogy and complexity (A2)",
        2005,
        ["W1000000005"],
    ),
    (
        "src:p3",
        "W1000000003",
        "10.1234/synth.003",
        "Synthetic paper on critical pedagogy and complexity (A3)",
        2007,
        ["W1000000005"],
    ),
    (
        "src:p4",
        "W1000000004",
        "10.1234/synth.004",
        "Synthetic paper on critical pedagogy and complexity (A4)",
        2009,
        ["W1000000005"],
    ),
    (
        "src:p5",
        "W1000000005",
        "10.1234/synth.005",
        "Foundational paper on transdisciplinarity (B1)",
        1998,
        ["W1000000001"],
    ),
    (
        "src:p6",
        "W1000000006",
        "10.1234/synth.006",
        "Synthetic paper on transdisciplinarity (B2)",
        2001,
        ["W1000000001"],
    ),
    (
        "src:p7",
        "W1000000007",
        "10.1234/synth.007",
        "Synthetic paper on transdisciplinarity (B3)",
        2004,
        ["W1000000001"],
    ),
    (
        "src:p8",
        "W1000000008",
        "10.1234/synth.008",
        "Synthetic paper on transdisciplinarity (B4)",
        2010,
        ["W1000000001"],
    ),
]

ids = pa.array([p[0] for p in papers], type=pa.string())
source_ids = pa.array([p[1] for p in papers], type=pa.string())
dois = pa.array([p[2] for p in papers], type=pa.string())
titles = pa.array([p[3] for p in papers], type=pa.string())
years = pa.array([p[4] for p in papers], type=pa.int32())
references_ids = pa.array([p[5] for p in papers], type=pa.list_(pa.string()))

# Schema canonico del corpus (ver docs/API.md §1.1).
schema = pa.schema(
    [
        ("id", pa.string()),
        ("source_id", pa.string()),
        ("doi", pa.string()),
        ("title", pa.string()),
        ("year", pa.int32()),
        ("abstract", pa.string()),
        ("source", pa.string()),
        ("language", pa.string()),
        ("publisher", pa.string()),
        ("research_areas", pa.list_(pa.string())),
        ("is_seed", pa.bool_()),
        ("curation_status", pa.string()),
        ("provenance", pa.string()),
        ("authors_raw", pa.list_(pa.string())),
        ("authors_id", pa.list_(pa.string())),
        ("authors_affiliations", pa.list_(pa.string())),
        ("keywords_raw", pa.list_(pa.string())),
        ("keywords_id", pa.list_(pa.string())),
        ("institutions_raw", pa.list_(pa.string())),
        ("institutions_id", pa.list_(pa.string())),
        ("references_id", pa.list_(pa.string())),
        ("references_doi", pa.list_(pa.string())),
        ("cited_by_id", pa.list_(pa.string())),
    ]
)

# Llena las columnas que no son de la e2e con valores neutros / listas vacias.
n = len(papers)
table = pa.table(
    {
        "id": ids,
        "source_id": source_ids,
        "doi": dois,
        "title": titles,
        "year": years,
        "abstract": pa.array([None] * n, type=pa.string()),
        "source": pa.array([None] * n, type=pa.string()),
        "language": pa.array(["en"] * n, type=pa.string()),
        "publisher": pa.array([None] * n, type=pa.string()),
        "research_areas": pa.array([None] * n, type=pa.list_(pa.string())),
        "is_seed": pa.array([True] * n, type=pa.bool_()),
        "curation_status": pa.array(["candidate"] * n, type=pa.string()),
        # provenance: usa el formato D2 (con source_kind) — simula un corpus post-D2.
        "provenance": pa.array(
            [
                '[{"action":"fetched","equation_id":"eq-e2e-0_15_0","chaining_hop":null,'
                '"source":"openalex","fetched_at":"2026-10-11T00:00:00+00:00",'
                '"decided_by":null,"decided_at":null,"source_kind":"seed_equation"}]'
            ]
            * n,
            type=pa.string(),
        ),
        "authors_raw": pa.array(
            [
                ["Author A"],
                ["Author B"],
                ["Author C"],
                ["Author D"],
                ["Author E"],
                ["Author F"],
                ["Author G"],
                ["Author H"],
            ],
            type=pa.list_(pa.string()),
        ),
        "authors_id": pa.array(
            [
                ["a0001"],
                ["a0002"],
                ["a0003"],
                ["a0004"],
                ["a0005"],
                ["a0006"],
                ["a0007"],
                ["a0008"],
            ],
            type=pa.list_(pa.string()),
        ),
        "authors_affiliations": pa.array([None] * n, type=pa.list_(pa.string())),
        "keywords_raw": pa.array(
            [
                ["complexity"],
                ["complexity"],
                ["complexity"],
                ["complexity"],
                ["transdisciplinarity"],
                ["transdisciplinarity"],
                ["transdisciplinarity"],
                ["transdisciplinarity"],
            ],
            type=pa.list_(pa.string()),
        ),
        "keywords_id": pa.array(
            [
                ["complexity"],
                ["complexity"],
                ["complexity"],
                ["complexity"],
                ["transdisciplinarity"],
                ["transdisciplinarity"],
                ["transdisciplinarity"],
                ["transdisciplinarity"],
            ],
            type=pa.list_(pa.string()),
        ),
        "institutions_raw": pa.array([None] * n, type=pa.list_(pa.string())),
        "institutions_id": pa.array([None] * n, type=pa.list_(pa.string())),
        "references_id": references_ids,
        "references_doi": pa.array([None] * n, type=pa.list_(pa.string())),
        "cited_by_id": pa.array([None] * n, type=pa.list_(pa.string())),
    },
    schema=schema,
)

DST.parent.mkdir(parents=True, exist_ok=True)
pq.write_table(table, DST)
print(
    f"OK: {DST} ({table.num_rows} papers, references_id materializado, 2 comunidades intencionales)"
)
