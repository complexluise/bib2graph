"""foraging.forager — ``Forager``: orquesta el chaining sobre un Source.

El Forager rankeea candidatos por *information scent* (frecuencia de
enlace con el corpus existente) usando funciones puras de ``scent.py``.
Solo él toca la red (a través del ``Source`` inyectado).  El núcleo de
scent es puro.

``depth > 1`` lanza ``NotImplementedError`` claro (decisión e=A, ADR 0008).

Forward chaining requiere que el ``source`` tenga ``fetch_citing``.  Si el
source no tiene ese método, falla ruidoso (no se amplía el Protocol ``Source``).

Ver docs/API.md §5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pyarrow as pa

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus
from bib2graph.foraging.base import Direction, GrowthPreview, RankedCandidates
from bib2graph.foraging.scent import (
    compute_backward_scent,
    compute_forward_scent,
    rank_candidates,
)
from bib2graph.schemas import CORPUS_SCHEMA, ProvenanceEvent


def _make_empty_corpus() -> Corpus:
    """Corpus vacío con schema canónico."""
    return Corpus.from_arrow(
        pa.table(
            {col: [] for col in CORPUS_SCHEMA.names},
            schema=CORPUS_SCHEMA,
        )
    )


def _build_backward_candidate_row(
    ref_id: str,
    *,
    fetched_at: str,
) -> dict[str, Any]:
    """Construye una fila mínima (id-only) para un candidato backward.

    El candidato backward es un id de OpenAlex extraído de ``references_id``
    de los papers del corpus.  Solo tenemos el id; el título se rellena con
    un placeholder para pasar la validación del schema.

    Args:
        ref_id: ID de OpenAlex del candidato (p. ej. ``W12345``).
        fetched_at: Timestamp ISO del fetch.

    Returns:
        Dict con las columnas mínimas del schema canónico.
    """
    provenance_event = ProvenanceEvent(
        action="fetched",
        equation_id=None,
        chaining_hop=1,
        source="chaining:backward",
        fetched_at=fetched_at,
        decided_by=None,
        decided_at=None,
    )
    return {
        Col.OPENALEX_ID: ref_id,
        Col.DOI: None,
        Col.TITLE: f"[candidate:{ref_id}]",
        Col.YEAR: None,
        Col.ABSTRACT: None,
        Col.SOURCE: None,
        Col.LANGUAGE: None,
        Col.PUBLISHER: None,
        Col.RESEARCH_AREAS: None,
        Col.IS_SEED: False,
        Col.CURATION_STATUS: CurationStatus.CANDIDATE,
        Col.PROVENANCE: ProvenanceEvent.dump_list([provenance_event]),
        Col.AUTHORS_RAW: None,
        Col.AUTHORS_ID: None,
        Col.AUTHORS_AFFILIATIONS: None,
        Col.KEYWORDS_RAW: None,
        Col.KEYWORDS_ID: None,
        Col.INSTITUTIONS_RAW: None,
        Col.INSTITUTIONS_ID: None,
        Col.REFERENCES_ID: None,
        Col.REFERENCES_DOI: None,
        Col.CITED_BY_ID: None,
    }


class Forager:
    """Orquesta el chaining sobre un Source, rankeando candidatos por scent.

    El scent mide la frecuencia de enlace bibliométrica (ADR 0008, decisión
    a=A): backward = cuántos papers del corpus listan al candidato en sus
    referencias; forward = cuántos papers del corpus cita el candidato.

    Uso::

        forager = Forager(OpenAlexSource(email="yo@example.com"), depth=1)
        preview = forager.preview(corpus)
        ranked = forager.chain(corpus)
        corpus_expandido = corpus.merge(ranked.corpus)

    Attributes:
        source: ``Source`` inyectado (``OpenAlexSource`` u otro compatible).
        depth: Profundidad de chaining; solo 1 está implementado.
        max_candidates: Tope de candidatos en el ranking; ``None`` = sin límite.
    """

    def __init__(
        self,
        source: Any,
        *,
        depth: int = 1,
        max_candidates: int | None = None,
    ) -> None:
        """Inicializa el Forager.

        Args:
            source: ``Source`` con acceso a la API externa.  Para forward
                chaining debe tener ``fetch_citing``.
            depth: Profundidad de chaining (solo 1 implementado).
            max_candidates: Tope de candidatos en el ranking (``None`` = sin
                límite).

        Raises:
            NotImplementedError: Si ``depth > 1``.
        """
        if depth > 1:
            raise NotImplementedError(
                f"Forager: profundidad {depth} no implementada. "
                "depth > 1 es futuro (v0.3+). Usa depth=1."
            )
        self._source = source
        self._depth = depth
        self._max_candidates = max_candidates

    def preview(
        self,
        corpus: Corpus,
        *,
        direction: Direction = "both",
    ) -> GrowthPreview:
        """Estima cuántos papers nuevos agregaría un chaining.

        Opera **solo localmente, sin red**.  No realiza ninguna llamada a la
        API ni a ``fetch_citing`` en ninguna dirección.

        - **Backward**: estimación exacta desde ``references_id`` local.
        - **Forward**: no es estimable sin red (``cited_by_id`` está vacío
          tras el seed inicial).  Cuando se pide forward o both,
          ``by_direction["forward"]`` vale ``0`` y
          ``GrowthPreview.forward_requires_fetch`` es ``True``.  El conteo
          real de candidatos forward solo se conoce al llamar
          ``chain(direction="forward"/"both")``, que sí fetchea.

        NO muta el corpus de entrada.

        Args:
            corpus: Corpus actual (semillas + curados).
            direction: ``'backward'``, ``'forward'`` o ``'both'``.

        Returns:
            ``GrowthPreview`` con la estimación de crecimiento local.
            Cuando ``forward_requires_fetch`` es ``True``, ``estimated_new``
            refleja solo el crecimiento estimable localmente (backward).
        """
        rows = corpus.to_arrow().to_pylist()
        by_direction: dict[str, int] = {}
        forward_requires_fetch = False

        if direction in ("backward", "both"):
            bwd = compute_backward_scent(rows)
            if self._max_candidates is not None:
                bwd_ranked = rank_candidates(bwd, max_candidates=self._max_candidates)
                by_direction["backward"] = len(bwd_ranked)
            else:
                by_direction["backward"] = len(bwd)

        if direction in ("forward", "both"):
            # El crecimiento forward no puede estimarse localmente: cited_by_id
            # está vacío tras el seed y traerlo requeriría fetch_citing (red).
            # Marcamos el campo para que el llamador sepa que debe chain() para
            # obtener el conteo real.
            by_direction["forward"] = 0
            forward_requires_fetch = True

        estimated_new = sum(by_direction.values())
        return GrowthPreview(
            estimated_new=estimated_new,
            by_direction=by_direction,
            direction=direction,
            forward_requires_fetch=forward_requires_fetch,
        )

    def chain(
        self,
        corpus: Corpus,
        *,
        direction: Direction = "both",
    ) -> RankedCandidates:
        """Computa candidatos rankeados por *information scent*.

        Devuelve un ``RankedCandidates`` con un Corpus SOLO de candidatos
        nuevos (no mergeado con el corpus de entrada).  El humano hace
        ``seed_corpus.merge(ranked.corpus)`` para expandir.

        NO muta el corpus de entrada.

        Args:
            corpus: Corpus actual (no muta).
            direction: ``'backward'``, ``'forward'`` o ``'both'``.

        Returns:
            ``RankedCandidates`` con candidatos y ranking por scent.
        """
        rows = corpus.to_arrow().to_pylist()
        fetched_at = datetime.now(UTC).isoformat()

        combined_scent: dict[str, float] = {}
        candidate_rows: dict[str, dict[str, Any]] = {}

        if direction in ("backward", "both"):
            bwd_scent = compute_backward_scent(rows)
            for ref_id, scent_val in bwd_scent.items():
                combined_scent[ref_id] = combined_scent.get(ref_id, 0.0) + scent_val
                if ref_id not in candidate_rows:
                    candidate_rows[ref_id] = _build_backward_candidate_row(
                        ref_id, fetched_at=fetched_at
                    )

        if direction in ("forward", "both"):
            fwd_scent, fwd_rows = self._fetch_forward(rows, fetched_at=fetched_at)
            for cand_id, scent_val in fwd_scent.items():
                combined_scent[cand_id] = combined_scent.get(cand_id, 0.0) + scent_val
                if cand_id not in candidate_rows:
                    candidate_rows[cand_id] = fwd_rows[cand_id]

        # Ranking estable (desc scent, asc id)
        ranking = rank_candidates(combined_scent, max_candidates=self._max_candidates)

        # Construir el Corpus de candidatos en orden del ranking
        # (los que entran tras el corte de max_candidates no se incluyen)
        candidates_corpus = _make_empty_corpus()
        for cand_id, _ in ranking:
            row = candidate_rows[cand_id]
            candidates_corpus = candidates_corpus.add_paper(row)

        # Poblar el manifest con chaining params
        from bib2graph.corpus import ChainingParams

        new_manifest = candidates_corpus.manifest.model_copy(
            update={
                "chaining": ChainingParams(
                    depth=self._depth,
                    max_candidates=self._max_candidates,
                    direction=direction,
                )
            }
        )
        candidates_corpus = candidates_corpus.with_manifest(new_manifest)

        return RankedCandidates(
            corpus=candidates_corpus,
            ranking=ranking,
        )

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _fetch_forward(
        self,
        corpus_rows: list[dict[str, Any]],
        *,
        fetched_at: str,
    ) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
        """Trae citantes y calcula scent forward.

        Args:
            corpus_rows: Filas del corpus actual.
            fetched_at: Timestamp ISO del fetch.

        Returns:
            Tupla ``(scent_map, candidate_rows)`` donde ``candidate_rows``
            tiene la fila completa de cada candidato forward.

        Raises:
            AttributeError: Si el ``source`` no tiene ``fetch_citing``.
        """
        if not hasattr(self._source, "fetch_citing"):
            raise AttributeError(
                f"El source {type(self._source).__name__!r} no implementa "
                "'fetch_citing': el forward chaining requiere OpenAlexSource "
                "o un source con ese método."
            )

        all_citing_rows: list[dict[str, Any]] = []
        for row in corpus_rows:
            oa_id = row.get(Col.OPENALEX_ID)
            if not oa_id:
                continue
            citing = self._source.fetch_citing(str(oa_id))
            all_citing_rows.extend(citing)

        fwd_scent = compute_forward_scent(corpus_rows, all_citing_rows)

        # Indexar las filas de candidatos por id (para el corpus de candidatos)
        candidate_rows: dict[str, dict[str, Any]] = {}
        for row in all_citing_rows:
            row_id = row.get("id")
            if row_id and str(row_id) in fwd_scent:
                candidate_rows[str(row_id)] = row

        return fwd_scent, candidate_rows
