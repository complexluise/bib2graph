"""preprocessors.preprocessor — ``Preprocessor``: orquesta normalize + thesaurus.

Determinista e idempotente (ADR 0011).  Registra un ``PreprocRef`` en el
Manifest por cada operación aplicada.

Fix R2 (#88): ``normalize`` y ``apply_thesaurus`` aceptan ``applied_at``
inyectado desde la frontera (mismo patrón que ``decided_at`` en curación).
Si se omite, usan ``datetime.now(UTC)`` como fallback para uso como librería.
El reloj se llama UNA sola vez en la frontera (``_ingest.normalize_and_dedup``),
no dentro del núcleo — garantía de corpus_hash estable ante llamadas rápidas.

Ver docs/API.md §6.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa

from bib2graph.corpus import Corpus, PreprocRef
from bib2graph.preprocessors.normalize import normalize_row
from bib2graph.preprocessors.thesaurus import apply_thesaurus_to_rows, load_thesaurus
from bib2graph.schemas import CORPUS_SCHEMA


class Preprocessor:
    """Determinístico e idempotente.  Normaliza y aplica thesaurus al Corpus.

    Las funciones puras (``normalize_row``, ``apply_thesaurus_to_rows``)
    viven en sus módulos; este orquestador reconstruye el Corpus Arrow y
    actualiza el Manifest.

    Ver docs/API.md §6, ADR 0011.
    """

    def normalize(
        self,
        corpus: Corpus,
        applied_at: datetime | None = None,
    ) -> Corpus:
        """Canonicaliza ``authors_id`` y ``language`` (normalización mínima).

        Operaciones (decisión b=A):
        - ``authors_id``: lowercase + quitar acentos + colapso de espacios.
        - ``language``: trunca al subtag ISO 639-1 primario.

        Idempotente: aplicar dos veces == aplicar una.
        Registra un ``PreprocRef(name='normalize')`` en el Manifest con el
        timestamp ``applied_at`` (R2: reloj en la frontera).

        Args:
            corpus: Corpus a normalizar (no muta).
            applied_at: Timestamp de la operación.  Si ``None``, usa
                ``datetime.now(UTC)`` (para uso como librería independiente).
                La frontera CLI inyecta un único timestamp por invocación.

        Returns:
            Nuevo Corpus normalizado.
        """
        ts = applied_at if applied_at is not None else datetime.now(UTC)
        rows = corpus.to_arrow().to_pylist()
        normalized = [normalize_row(row) for row in rows]
        new_table = pa.Table.from_pylist(normalized, schema=CORPUS_SCHEMA)
        new_corpus = Corpus.from_arrow(new_table)

        preproc_ref = PreprocRef(
            name="normalize",
            params={"applied_at": ts.isoformat()},
        )
        new_manifest = corpus.manifest.model_copy(
            update={"preprocessors": [*corpus.manifest.preprocessors, preproc_ref]}
        )
        return new_corpus.with_manifest(new_manifest)

    def apply_thesaurus(
        self,
        corpus: Corpus,
        thesaurus: dict[str, object] | Path,
        applied_at: datetime | None = None,
    ) -> Corpus:
        """Normaliza keywords con el thesaurus multilingüe curado.

        Lee ``keywords_raw`` y sobrescribe ``keywords_id`` con los conceptos
        canónicos del thesaurus.  Determinista e idempotente (ADR 0011).
        Registra un ``PreprocRef(name='apply_thesaurus')`` en el Manifest con
        el timestamp ``applied_at`` (R2: reloj en la frontera).

        Args:
            corpus: Corpus a procesar (no muta).
            thesaurus: Dict con formato ``{concepts: {canonical: {aliases_*:
                [...]}}}`` o ``Path`` a un JSON con esa estructura.
            applied_at: Timestamp de la operación.  Si ``None``, usa
                ``datetime.now(UTC)`` (para uso como librería independiente).
                La frontera CLI inyecta un único timestamp por invocación.

        Returns:
            Nuevo Corpus con ``keywords_id`` poblado.
        """
        ts = applied_at if applied_at is not None else datetime.now(UTC)
        lookup = load_thesaurus(thesaurus)
        rows = corpus.to_arrow().to_pylist()
        processed = apply_thesaurus_to_rows(rows, lookup)
        new_table = pa.Table.from_pylist(processed, schema=CORPUS_SCHEMA)
        new_corpus = Corpus.from_arrow(new_table)

        # Params del registro: fuente del thesaurus y nº de aliases
        params: dict[str, str] = {
            "n_aliases": str(len(lookup)),
            "applied_at": ts.isoformat(),
        }
        if isinstance(thesaurus, Path):
            params["source"] = str(thesaurus)

        preproc_ref = PreprocRef(name="apply_thesaurus", params=params)
        new_manifest = corpus.manifest.model_copy(
            update={"preprocessors": [*corpus.manifest.preprocessors, preproc_ref]}
        )
        return new_corpus.with_manifest(new_manifest)
