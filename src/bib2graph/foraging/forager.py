"""foraging.forager — ``Forager``: orquesta el chaining sobre un Source.

El Forager rankea candidatos por *information scent* bibliométrico usando
funciones puras de ``scent.py`` (R4, ADR 0020/0022):

- **Backward**: score = nº de corpus-papers que listan al candidato en
  ``references_id`` (acoplamiento hacia atrás).  Los IDs backward NO se
  materializan como filas del corpus; salen en ``RankedCandidates.observed_refs``
  para que el comando CLI los persista en ``referenced_but_not_fetched`` (#54,
  opción B).  El ranking backward SIGUE en ``RankedCandidates.ranking``.
- **Forward** (fix forward-scent, Wohlin): score = citación directa al corpus.
    corpus_ids = {Pi.id | Pi.source_id : Pi ∈ corpus}
    forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|
  Robusto ante corpus con ``references_id`` ralas (estado común tras un seed
  sin enriquecimiento); el acoplamiento bibliográfico puro degeneraba a 0.
  Los candidatos forward SÍ se materializan como filas del corpus.

Solo él toca la red (a través del ``Source`` inyectado).  El núcleo de
scent es puro.  ``explain_candidate`` fue **eliminado** (R4, ADR 0022).
``_build_backward_candidate_row`` fue **eliminado** (#54): ya no se fabrica
ninguna fila-fantasma para candidatos backward.
``_build_forward_candidate_row`` fue **eliminado** (#78, opción A1): el forward
materializa metadata real vía ``fetch_citing_batch_with_works`` +
``_work_to_row`` (cero red extra: los works viajan en las mismas páginas de
atribución).

``depth > 1`` lanza ``NotImplementedError`` claro (decisión e=A, ADR 0008).

Forward chaining requiere que el ``source`` tenga ``fetch_citing_batch``.
Si el source no lo tiene, falla ruidoso.

El forward chaining opera **sobre todas las semillas** (``is_seed=True``),
independientemente de su ``curation_status``.  El chaining corre antes de la
curación (ciclo: SEEDED → FORAGED → curación); restringir a ``accepted``
bloquearía el camino feliz ``b2g seed`` + ``b2g chain`` (las semillas nacen
``candidate``).  La restricción a ``accepted`` es del Enricher (post-curación).
``max_citing_per_paper`` acota el fetch por semilla.

Ver docs/API.md §5.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pyarrow as pa

from bib2graph.constants import Col
from bib2graph.corpus import Corpus, _rows_with_ids
from bib2graph.foraging.base import Direction, GrowthPreview, RankedCandidates
from bib2graph.foraging.scent import (
    compute_backward_scent,
    rank_candidates,
)
from bib2graph.schemas import CORPUS_SCHEMA
from bib2graph.sources.openalex import _work_to_row


def _make_empty_corpus() -> Corpus:
    """Corpus vacío con schema canónico."""
    return Corpus.from_arrow(
        pa.table(
            {col: [] for col in CORPUS_SCHEMA.names},
            schema=CORPUS_SCHEMA,
        )
    )


def _extract_seed_ids(corpus_rows: list[dict[str, Any]]) -> list[str]:
    """Extrae los source_id de todas las semillas del corpus.

    El forward chaining corre antes de la curación (ciclo: SEEDED → FORAGED
    → curación); las semillas nacen con ``curation_status="candidate"`` y el
    paso de curación es posterior.  Restringir a ``accepted`` rompería el
    camino feliz ``b2g seed`` + ``b2g chain``.  La restricción a ``accepted``
    es responsabilidad del Enricher (post-curación, Hito 8b), no del Forager.

    Las no-semillas (candidatos traídos por chaining anterior, con
    ``is_seed=False``) sí se omiten: solo las semillas originales se forrajean.

    Args:
        corpus_rows: Filas del corpus como dicts.

    Returns:
        Lista de source_ids (IDs del motor de extracción) de las semillas,
        en orden de aparición (determinista).
    """
    result: list[str] = []
    for row in corpus_rows:
        if row.get(Col.IS_SEED) and row.get(Col.SOURCE_ID):
            result.append(str(row[Col.SOURCE_ID]))
    return result


def _estimate_forward_from_cited_by_detail(
    corpus_rows: list[dict[str, Any]],
) -> tuple[int, bool, int]:
    """Versión de diagnóstico que devuelve también el total sin cap.

    Args:
        corpus_rows: Filas del corpus como dicts (``to_pylist()``).

    Returns:
        Tupla ``(count_capped_placeholder, available, total_uncapped)``
        donde ``total_uncapped`` es el conteo antes de aplicar cualquier cap.
        (El cap lo aplica el llamador; aquí siempre devuelve el total completo.)
    """
    corpus_ids: set[str] = set()
    for row in corpus_rows:
        id_val = row.get(Col.ID)
        source_id_val = row.get(Col.SOURCE_ID)
        if id_val:
            corpus_ids.add(str(id_val))
        if source_id_val:
            corpus_ids.add(str(source_id_val))

    candidate_ids: set[str] = set()
    has_cited_by_data = False
    for row in corpus_rows:
        cited_by = row.get(Col.CITED_BY_ID)
        if not cited_by or not isinstance(cited_by, list):
            continue
        has_cited_by_data = True
        for cid in cited_by:
            if cid and isinstance(cid, str) and cid not in corpus_ids:
                candidate_ids.add(cid)

    if not has_cited_by_data:
        return 0, False, 0

    total = len(candidate_ids)
    return total, True, total


class Forager:
    """Orquesta el chaining sobre un Source, rankeando candidatos por scent.

    El scent mide el acoplamiento bibliométrico (ADR 0020/0022, R4):
    backward = cuántos corpus-papers listan al candidato en sus referencias;
    forward = cuántos corpus-papers cita el candidato directamente (citación
    directa al corpus, Wohlin; robusto ante ``references_id`` ralas en el corpus).

    El forward chaining opera sobre **todas las semillas** (``is_seed=True``,
    sin filtrar por ``curation_status``) y usa batcheo OR
    (``fetch_citing_batch``, ≤50 IDs/lote) para eliminar el patrón N+1.

    Uso::

        forager = Forager(OpenAlexSource(email="yo@example.com"), depth=1)
        preview = forager.preview(corpus)
        ranked = forager.chain(corpus)
        corpus_expandido = corpus.merge(ranked.corpus)

    Attributes:
        source: ``Source`` inyectado (``OpenAlexSource`` u otro compatible).
        depth: Profundidad de chaining; solo 1 está implementado.
        max_candidates: Tope de candidatos en el ranking; ``None`` = sin límite.
        max_citing_per_paper: Presupuesto de citantes por semilla en el forward
            chaining; ``None`` = sin tope.
    """

    def __init__(
        self,
        source: Any,
        *,
        depth: int = 1,
        max_candidates: int | None = None,
        max_citing_per_paper: int | None = 50,
    ) -> None:
        """Inicializa el Forager.

        Args:
            source: ``Source`` con acceso a la API externa.  Para forward
                chaining debe tener ``fetch_citing_batch``.
            depth: Profundidad de chaining (solo 1 implementado).
            max_candidates: Tope de candidatos en el ranking (``None`` = sin
                límite).
            max_citing_per_paper: Presupuesto de citantes por semilla para el
                forward chaining.  Default 50 (acota el fetch por semilla, no
                solo trunca el resultado).  Pasar ``None`` para sin tope.

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
        self._max_citing_per_paper = max_citing_per_paper

    def preview(
        self,
        corpus: Corpus,
        *,
        direction: Direction = "both",
    ) -> GrowthPreview:
        """Estima cuántos papers nuevos agregaría un chaining.

        Opera **solo localmente, sin red**.  No realiza ninguna llamada a la
        API en ninguna dirección.

        - **Backward**: estimación exacta desde ``references_id`` local.
        - **Forward** (dos casos):
          - Si el corpus tiene ``cited_by_id`` poblado (pasó por ``b2g enrich``),
            se cuentan los IDs únicos en ``cited_by_id`` que aún no están en el
            corpus — estimación local exacta sin red.
          - Si ``cited_by_id`` está vacío (corpus recién sembrado), el conteo
            forward no es estimable sin red; ``forward_requires_fetch=True``
            y ``by_direction["forward"]`` vale ``0``.

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
        forward_from_cited_by = False
        capped_by_max = False

        if direction in ("backward", "both"):
            bwd_uncapped = compute_backward_scent(rows)
            bwd_total = len(bwd_uncapped)
            if self._max_candidates is not None and bwd_total > self._max_candidates:
                by_direction["backward"] = self._max_candidates
                capped_by_max = True
            else:
                by_direction["backward"] = bwd_total

        if direction in ("forward", "both"):
            fwd_total, fwd_local, _ = _estimate_forward_from_cited_by_detail(rows)
            if fwd_local:
                # cited_by_id disponible localmente: estimación sin red.
                if (
                    self._max_candidates is not None
                    and fwd_total > self._max_candidates
                ):
                    by_direction["forward"] = self._max_candidates
                    capped_by_max = True
                else:
                    by_direction["forward"] = fwd_total
                forward_from_cited_by = True
            else:
                # cited_by_id vacío: el forward requiere fetch.
                by_direction["forward"] = 0
                forward_requires_fetch = True

        estimated_new = sum(by_direction.values())
        return GrowthPreview(
            estimated_new=estimated_new,
            by_direction=by_direction,
            direction=direction,
            forward_requires_fetch=forward_requires_fetch,
            forward_from_cited_by=forward_from_cited_by,
            capped_by_max=capped_by_max,
        )

    def chain(
        self,
        corpus: Corpus,
        *,
        direction: Direction = "both",
        since: date | None = None,
    ) -> RankedCandidates:
        """Computa candidatos rankeados por *information scent*.

        **Opción B (#54):** los candidatos backward NO se materializan como
        filas del corpus — sus IDs salen en ``RankedCandidates.observed_refs``
        para que el comando CLI los persista en ``referenced_but_not_fetched``.
        El ranking backward SIGUE presente en ``RankedCandidates.ranking``.

        Los candidatos forward SÍ se materializan como filas en
        ``RankedCandidates.corpus`` (con metadata traída por ``fetch_citing_batch``).

        Devuelve un ``RankedCandidates`` con:
        - ``corpus``: SOLO candidatos forward (no mergeado con el corpus semilla).
        - ``ranking``: candidatos backward + forward rankeados por scent.
        - ``observed_refs``: IDs backward observados (no en corpus, tabla auxiliar).

        NO muta el corpus de entrada.

        Args:
            corpus: Corpus actual (no muta).
            direction: ``'backward'``, ``'forward'`` o ``'both'``.

        Returns:
            ``RankedCandidates`` con candidatos, ranking y observed_refs.
        """
        rows = corpus.to_arrow().to_pylist()
        fetched_at = datetime.now(UTC).isoformat()

        combined_scent: dict[str, float] = {}
        # Solo los candidatos forward tienen filas materializadas
        fwd_candidate_rows: dict[str, dict[str, Any]] = {}
        # IDs backward: se observan pero NO se materializan como corpus rows
        bwd_observed: set[str] = set()

        if direction in ("backward", "both"):
            bwd_scent = compute_backward_scent(rows)
            for ref_id, scent_val in bwd_scent.items():
                combined_scent[ref_id] = combined_scent.get(ref_id, 0.0) + scent_val
                bwd_observed.add(ref_id)

        if direction in ("forward", "both"):
            fwd_scent, fwd_rows = self._fetch_forward(
                rows, fetched_at=fetched_at, since=since
            )
            for cand_id, scent_val in fwd_scent.items():
                combined_scent[cand_id] = combined_scent.get(cand_id, 0.0) + scent_val
                if cand_id not in fwd_candidate_rows:
                    fwd_candidate_rows[cand_id] = fwd_rows[cand_id]

        ranking = rank_candidates(combined_scent, max_candidates=self._max_candidates)

        # observed_refs: IDs backward presentes en el ranking (respeta el cap),
        # en orden de ranking para reproducibilidad.
        ranked_ids_set = {cand_id for cand_id, _ in ranking}
        observed_refs = [
            cand_id
            for cand_id, _ in ranking
            if cand_id in bwd_observed
            and cand_id in ranked_ids_set
            and cand_id not in fwd_candidate_rows
        ]

        # R5: bulk-load — solo filas FORWARD materializadas.
        # El orden del ranking se preserva construyendo la lista en ese orden.
        fwd_rows_ordered = [
            fwd_candidate_rows[cand_id]
            for cand_id, _ in ranking
            if cand_id in fwd_candidate_rows
        ]
        rows_with_ids = _rows_with_ids(fwd_rows_ordered)
        if rows_with_ids:
            table = pa.Table.from_pylist(rows_with_ids, schema=CORPUS_SCHEMA)
            candidates_corpus = Corpus.from_arrow(table)
        else:
            candidates_corpus = _make_empty_corpus()

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
            observed_refs=observed_refs,
        )

    # Helpers internos

    def _fetch_forward(
        self,
        corpus_rows: list[dict[str, Any]],
        *,
        fetched_at: str,
        since: date | None = None,
    ) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
        """Trae citantes via batcheo y calcula scent forward.

        Usa ``fetch_citing_batch_with_works`` del source (batcheo OR ≤50 IDs
        por request, presupuesto por semilla, retry/backoff incluidos) para
        materializar filas con metadata real (título/año/autores/etc.) en vez
        de placeholders ``[candidate:W...]`` (#78, opción A1).  CERO red extra:
        los works ya viajan en las mismas páginas que se usan para la atribución.

        Opera sobre todas las semillas (``is_seed=True``), independientemente
        del ``curation_status`` — el chaining corre antes de la curación.

        El scent forward se calcula directamente desde la re-atribución que
        devuelve ``fetch_citing_batch_with_works``: para cada citante, los
        seed IDs que cita ya están en el ``attribution`` dict.  El score es
        la intersección de esos seeds con ``corpus_ids`` (trivial: seed_ids ⊆
        corpus_ids porque son los source_id de las semillas).

        Cada fila candidata se construye con ``_work_to_row`` (el mapeador
        canónico), con ``is_seed=False``, ``chaining_hop=1`` y
        ``source_tag='chaining:forward'``.

        Args:
            corpus_rows: Filas del corpus actual.
            fetched_at: Timestamp ISO del fetch.

        Returns:
            Tupla ``(scent_map, candidate_rows)`` donde ``candidate_rows``
            tiene la fila completa (con metadata real) de cada candidato
            forward con score > 0.

        Raises:
            AttributeError: Si el ``source`` no tiene ``fetch_citing_batch``.
        """
        if not hasattr(self._source, "fetch_citing_batch"):
            raise AttributeError(
                f"El source {type(self._source).__name__!r} no implementa "
                "'fetch_citing_batch': el forward chaining requiere "
                "OpenAlexSource o un source con ese método."
            )

        # Alcance: todas las semillas (is_seed=True); el chaining precede a la curación
        seed_ids = _extract_seed_ids(corpus_rows)
        if not seed_ids:
            return {}, {}

        # Se incluye source_id porque los IDs de motor (W… de OpenAlex) aparecen
        # en references_id y deben cruzar contra source_id W… del corpus.
        corpus_ids: set[str] = set()
        for row in corpus_rows:
            id_val = row.get(Col.ID)
            src_id_val = row.get(Col.SOURCE_ID)
            if id_val:
                corpus_ids.add(str(id_val))
            if src_id_val:
                corpus_ids.add(str(src_id_val))

        # Batcheo: trae atribución Y works JSON en un solo ciclo de páginas.
        # tqdm es dependencia del núcleo; import perezoso para evitar efectos de módulo.
        use_with_works = hasattr(self._source, "fetch_citing_batch_with_works")
        citing_dict: dict[str, list[str]]
        works_map: dict[str, dict[str, Any]]

        try:
            from tqdm import tqdm as _tqdm

            with _tqdm(
                total=1,
                desc="forward chaining",
                unit="lote",
                leave=False,
            ) as pbar:
                _since_kw = {"since": since} if since is not None else {}
                if use_with_works:
                    citing_dict, works_map = self._source.fetch_citing_batch_with_works(
                        seed_ids, max_per_paper=self._max_citing_per_paper, **_since_kw
                    )
                else:
                    citing_dict = self._source.fetch_citing_batch(
                        seed_ids, max_per_paper=self._max_citing_per_paper, **_since_kw
                    )
                    works_map = {}
                pbar.update(1)
        except ImportError:
            _since_kw = {"since": since} if since is not None else {}
            if use_with_works:
                citing_dict, works_map = self._source.fetch_citing_batch_with_works(
                    seed_ids, max_per_paper=self._max_citing_per_paper, **_since_kw
                )
            else:
                citing_dict = self._source.fetch_citing_batch(
                    seed_ids, max_per_paper=self._max_citing_per_paper, **_since_kw
                )
                works_map = {}

        # Invertir: {citer_id → [seed_ids que este citante cita]}
        citer_to_seeds: dict[str, list[str]] = {}
        for seed_id, citer_ids in citing_dict.items():
            for citer_id in citer_ids:
                if citer_id not in corpus_ids:
                    citer_to_seeds.setdefault(citer_id, []).append(seed_id)

        if not citer_to_seeds:
            return {}, {}

        # Construir filas con metadata real (vía _work_to_row) cuando el source
        # proveyó los works; el score es len(seeds_citados ∩ corpus_ids).
        candidate_rows: dict[str, dict[str, Any]] = {}
        scent_map: dict[str, float] = {}
        for citer_id, seeds_cited in citer_to_seeds.items():
            score = float(sum(1 for s in seeds_cited if s in corpus_ids))
            if score > 0:
                scent_map[citer_id] = score
                work = works_map.get(citer_id)
                if work is not None:
                    row = _work_to_row(
                        work,
                        equation_id="chaining:forward",
                        fetched_at=fetched_at,
                        is_seed=False,
                        action="fetched",
                        chaining_hop=1,
                        source_tag="chaining:forward",
                    )
                else:
                    # Fallback (source sin fetch_citing_batch_with_works): fila
                    # con solo las seeds citadas en references_id para el score.
                    # No debería ocurrir con OpenAlexSource (#78 A1 requiere works).
                    from bib2graph.schemas import ProvenanceEvent

                    prov = ProvenanceEvent(
                        action="fetched",
                        equation_id=None,
                        chaining_hop=1,
                        source="chaining:forward",
                        fetched_at=fetched_at,
                        decided_by=None,
                        decided_at=None,
                    )
                    from bib2graph.constants import CurationStatus

                    row = {
                        Col.SOURCE_ID: citer_id,
                        Col.DOI: None,
                        Col.TITLE: f"[candidate:{citer_id}]",
                        Col.YEAR: None,
                        Col.ABSTRACT: None,
                        Col.SOURCE: None,
                        Col.LANGUAGE: None,
                        Col.PUBLISHER: None,
                        Col.RESEARCH_AREAS: None,
                        Col.IS_SEED: False,
                        Col.CURATION_STATUS: CurationStatus.CANDIDATE,
                        Col.PROVENANCE: ProvenanceEvent.dump_list([prov]),
                        Col.AUTHORS_RAW: None,
                        Col.AUTHORS_ID: None,
                        Col.AUTHORS_AFFILIATIONS: None,
                        Col.KEYWORDS_RAW: None,
                        Col.KEYWORDS_ID: None,
                        Col.INSTITUTIONS_RAW: None,
                        Col.INSTITUTIONS_ID: None,
                        Col.REFERENCES_ID: seeds_cited or None,
                        Col.REFERENCES_DOI: None,
                        Col.CITED_BY_ID: None,
                    }
                candidate_rows[citer_id] = row

        return scent_map, candidate_rows
