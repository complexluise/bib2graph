"""foraging.forager — ``Forager``: orquesta el chaining sobre un Source.

El Forager rankea candidatos por *information scent* bibliométrico usando
funciones puras de ``scent.py`` (R4, ADR 0020/0022):

- **Backward**: score = nº de corpus-papers que listan al candidato en
  ``references_id`` (acoplamiento hacia atrás).  Los IDs backward NO se
  materializan como filas del corpus; salen en ``RankedCandidates.observed_refs``
  para que el comando CLI los persista en ``referenced_but_not_fetched`` (#54,
  opción B).  El ranking backward SIGUE en ``RankedCandidates.ranking``.
- **Forward** (fix forward-scent, Wohlin): score = citación directa al corpus.
    corpus_ids = {Pi.id | Pi.openalex_id : Pi ∈ corpus}
    forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|
  Robusto ante corpus con ``references_id`` ralas (estado común tras un seed
  sin enriquecimiento); el acoplamiento bibliográfico puro degeneraba a 0.
  Los candidatos forward SÍ se materializan como filas del corpus.

Solo él toca la red (a través del ``Source`` inyectado).  El núcleo de
scent es puro.  ``explain_candidate`` fue **eliminado** (R4, ADR 0022).
``_build_backward_candidate_row`` fue **eliminado** (#54): ya no se fabrica
ninguna fila-fantasma para candidatos backward.

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

from datetime import UTC, datetime
from typing import Any

import pyarrow as pa

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus, _rows_with_ids
from bib2graph.foraging.base import Direction, GrowthPreview, RankedCandidates
from bib2graph.foraging.scent import (
    compute_backward_scent,
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


def _extract_seed_ids(corpus_rows: list[dict[str, Any]]) -> list[str]:
    """Extrae los openalex_id de todas las semillas del corpus.

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
        Lista de IDs cortos de OpenAlex de las semillas, en orden de aparición
        (determinista).
    """
    result: list[str] = []
    for row in corpus_rows:
        if row.get(Col.IS_SEED) and row.get(Col.OPENALEX_ID):
            result.append(str(row[Col.OPENALEX_ID]))
    return result


def _build_forward_candidate_row(
    citer_id: str,
    *,
    seed_ids_cited: list[str],
    fetched_at: str,
) -> dict[str, Any]:
    """Construye una fila mínima para un candidato forward.

    A diferencia del candidato backward (que tiene solo el id), el candidato
    forward incorpora en ``references_id`` los IDs de las semillas que él cita
    (atribuidos por ``fetch_citing_batch``).  Esto permite calcular el score
    por intersección con ``corpus_ids`` sin re-fetchear los datos de red.

    Args:
        citer_id: ID corto de OpenAlex del citante (p. ej. ``W99999``).
        seed_ids_cited: IDs de las semillas del corpus que este citante cita,
            según la re-atribución de ``fetch_citing_batch``.
        fetched_at: Timestamp ISO del fetch.

    Returns:
        Dict con las columnas mínimas del schema canónico.
    """
    provenance_event = ProvenanceEvent(
        action="fetched",
        equation_id=None,
        chaining_hop=1,
        source="chaining:forward",
        fetched_at=fetched_at,
        decided_by=None,
        decided_at=None,
    )
    return {
        Col.OPENALEX_ID: citer_id,
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
        Col.PROVENANCE: ProvenanceEvent.dump_list([provenance_event]),
        Col.AUTHORS_RAW: None,
        Col.AUTHORS_ID: None,
        Col.AUTHORS_AFFILIATIONS: None,
        Col.KEYWORDS_RAW: None,
        Col.KEYWORDS_ID: None,
        Col.INSTITUTIONS_RAW: None,
        Col.INSTITUTIONS_ID: None,
        # references_id incluye los seeds citados para que compute_forward_scent
        # pueda calcular el score por intersección con corpus_ids.
        Col.REFERENCES_ID: seed_ids_cited or None,
        Col.REFERENCES_DOI: None,
        Col.CITED_BY_ID: None,
    }


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
        - **Forward**: el conteo de citantes no es estimable sin red
          (``cited_by_id`` está vacío tras el seed inicial).  Sin embargo,
          se reporta el número de semillas (``is_seed=True``) que se forejarían
          como estimación del costo de red (~1 request por lote de 50 semillas).
          Cuando se pide forward o
          both, ``by_direction["forward"]`` vale ``0`` y
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
            # está vacío tras el seed y traerlo requeriría fetch a la red.
            # Marcamos el campo para que el llamador sepa que debe chain() para
            # obtener el conteo real.  El número de semillas (is_seed=True)
            # es la única estimación disponible sin red.
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
            fwd_scent, fwd_rows = self._fetch_forward(rows, fetched_at=fetched_at)
            for cand_id, scent_val in fwd_scent.items():
                combined_scent[cand_id] = combined_scent.get(cand_id, 0.0) + scent_val
                if cand_id not in fwd_candidate_rows:
                    fwd_candidate_rows[cand_id] = fwd_rows[cand_id]

        # Ranking estable (desc scent, asc id) — incluye backward + forward
        ranking = rank_candidates(combined_scent, max_candidates=self._max_candidates)

        # observed_refs: IDs backward presentes en el ranking (respeta el cap),
        # en orden de ranking para reproducibilidad.
        ranked_ids_set = {cand_id for cand_id, _ in ranking}
        observed_refs = [
            cand_id
            for cand_id, _ in ranking
            if cand_id in bwd_observed
            and cand_id in ranked_ids_set
            # excluir IDs que también aparecen como forward (ya en corpus)
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
            observed_refs=observed_refs,
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
        """Trae citantes via batcheo y calcula scent forward.

        Usa ``fetch_citing_batch`` del source (batcheo OR ≤50 IDs por request,
        presupuesto por semilla, retry/backoff incluidos) en lugar del loop N+1.
        Opera sobre todas las semillas (``is_seed=True``), independientemente
        del ``curation_status`` — el chaining corre antes de la curación.

        El scent forward se computa desde la re-atribución que ya realiza
        ``fetch_citing_batch``: para cada citante, los seed IDs que él cita
        están en el dict resultado; con eso se construye una fila mínima con
        ``references_id=seed_ids_citados`` y el score se calcula por
        intersección con ``corpus_ids``.

        Args:
            corpus_rows: Filas del corpus actual.
            fetched_at: Timestamp ISO del fetch.

        Returns:
            Tupla ``(scent_map, candidate_rows)`` donde ``candidate_rows``
            tiene la fila mínima de cada candidato forward (con
            ``references_id`` = seeds citadas, para el scent).

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

        # corpus_ids: ids y openalex_ids de todos los papers del corpus
        # (para compute_forward_scent y para excluir candidatos ya presentes)
        corpus_ids: set[str] = set()
        for row in corpus_rows:
            id_val = row.get(Col.ID)
            oa_id_val = row.get(Col.OPENALEX_ID)
            if id_val:
                corpus_ids.add(str(id_val))
            if oa_id_val:
                corpus_ids.add(str(oa_id_val))

        # Batcheo: fetch_citing_batch hace ≤50 IDs por request, presupuesto
        # por semilla y retry/backoff.  Devuelve {seed_id: [citer_id]}.
        # tqdm es dependencia del núcleo; el import perezoso evita efectos de módulo.
        try:
            from tqdm import tqdm as _tqdm

            # Barra de progreso: una iteración por llamada batch (no por semilla)
            with _tqdm(
                total=1,
                desc="forward chaining",
                unit="lote",
                leave=False,
            ) as pbar:
                citing_dict = self._source.fetch_citing_batch(
                    seed_ids, max_per_paper=self._max_citing_per_paper
                )
                pbar.update(1)
        except ImportError:
            # tqdm no disponible: continuar sin barra de progreso
            citing_dict = self._source.fetch_citing_batch(
                seed_ids, max_per_paper=self._max_citing_per_paper
            )

        # Invertir: {citer_id → [seed_ids que este citante cita]}
        # para construir las filas mínimas y calcular el scent.
        citer_to_seeds: dict[str, list[str]] = {}
        for seed_id, citer_ids in citing_dict.items():
            for citer_id in citer_ids:
                if citer_id not in corpus_ids:  # excluir ya presentes
                    citer_to_seeds.setdefault(citer_id, []).append(seed_id)

        if not citer_to_seeds:
            return {}, {}

        # Construir filas mínimas de candidatos (con references_id = seeds citadas)
        # y calcular scent forward directamente desde la re-atribución.
        # score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|
        # Como seed_ids ⊆ corpus_ids (openalex_id de las semillas), la
        # intersección es trivial: score = len(seed_ids_citados por Y).
        candidate_rows: dict[str, dict[str, Any]] = {}
        scent_map: dict[str, float] = {}
        for citer_id, seeds_cited in citer_to_seeds.items():
            score = float(sum(1 for s in seeds_cited if s in corpus_ids))
            if score > 0:
                scent_map[citer_id] = score
                candidate_rows[citer_id] = _build_forward_candidate_row(
                    citer_id,
                    seed_ids_cited=seeds_cited,
                    fetched_at=fetched_at,
                )

        return scent_map, candidate_rows
