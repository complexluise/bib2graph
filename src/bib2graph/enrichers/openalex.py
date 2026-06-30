"""enrichers.openalex — ``OpenAlexEnricher``: enriquecedor via OpenAlex.

Hito 8a: resuelve ``references_id`` → ``references_doi`` para cada paper
del corpus, batcheando las consultas contra la API de OpenAlex (≤100 IDs
por request) y rellenando ``references_doi`` alineado al orden de
``references_id`` (DOI o None si OpenAlex no lo tiene).

Hito 8b: puebla ``cited_by_id`` con los IDs de los citantes de cada semilla
aceptada.  Usa batching por OR (``cites:W1|W2|...``, ≤50 IDs/lote) via
``source.fetch_citing_batch``.  Re-atribución: como el filtro OR no indica
qué seed citó cada citante, se cruza ``references_id`` del citante con el
set de IDs objetivo para asignar el citante solo a los seeds que realmente
cita.  Idempotente: unión de sets en ``cited_by_id``, sin duplicar.
Solo rellena ``cited_by_id``; los citantes NO entran como filas nuevas
(decisión A del PO).

La frontera núcleo/costura se mantiene: el ``OpenAlexSource`` hace la I/O;
el ``OpenAlexEnricher`` orquesta la lógica.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pyarrow as pa

from bib2graph.constants import Col, CurationStatus
from bib2graph.corpus import Corpus, EnricherRef

if TYPE_CHECKING:
    from bib2graph.sources.openalex import OpenAlexSource


class OpenAlexEnricher:
    """Enriquece el corpus en dos pasadas.

    **Pasada 1 (Hito 8a):** resuelve ``references_id`` → ``references_doi``.

    **Pasada 2 (Hito 8b):** puebla ``cited_by_id`` de las semillas aceptadas
    consultando sus citantes en OpenAlex con batching por OR y re-atribuye
    cada citante solo a los seeds que realmente cita.

    Recibe un ``OpenAlexSource`` ya configurado (con email, api_key y/o
    transport inyectables), de modo que los tests pueden pasar un
    ``MockTransport`` sin tocar red.

    Ejemplo::

        source = OpenAlexSource(email="yo@example.com")
        enricher = OpenAlexEnricher(source, max_citing_per_paper=50)
        corpus_enriquecido = enricher.enrich(corpus)

    El ``max_citing_per_paper`` limita cuántos citantes se registran en
    ``cited_by_id`` por paper (default ``None`` = sin tope).
    """

    def __init__(
        self,
        source: OpenAlexSource,
        *,
        max_citing_per_paper: int | None = None,
    ) -> None:
        """Inicializa el enricher con un source ya configurado.

        Args:
            source: ``OpenAlexSource`` con credenciales y transport inyectados.
                El enricher reutiliza su cliente httpx y retry/backoff via
                ``source.fetch_dois_for`` y ``source.fetch_citing_batch``.
            max_citing_per_paper: Tope de citantes a registrar en
                ``cited_by_id`` por paper objetivo.  ``None`` = sin tope.
        """
        self._source = source
        self._max_citing_per_paper = max_citing_per_paper

    def enrich(self, corpus: Corpus) -> Corpus:
        """Enriquece el corpus en dos pasadas (refs→DOI y cited_by_id).

        Algoritmo:
        1. **Pasada 1 (refs→DOI):** recolecta ``references_id`` únicos, los
           resuelve a DOIs batcheando por OR (≤100 IDs/request) y rellena
           ``references_doi`` alineado al orden de ``references_id``.
        2. **Pasada 2 (cited_by_id):** identifica semillas aceptadas
           (``is_seed=True AND curation_status=accepted``); batchea sus IDs
           en lotes ≤50 con ``fetch_citing_batch``; re-atribuye cada citante
           a los seeds que realmente cita cruzando ``references_id`` del
           citante con el set de IDs objetivo; respeta ``max_citing_per_paper``.
        3. Registra dos ``EnricherRef`` en el Manifest (uno por pasada).

        **Idempotente:** re-enriquecer produce el mismo resultado (``cited_by_id``
        es una unión de sets; los DOIs se sobreescriben).

        **No pierde papers:** el corpus resultado tiene exactamente los mismos
        papers que el corpus de entrada; los citantes NO se agregan como filas.

        Args:
            corpus: Corpus a enriquecer.

        Returns:
            Nuevo ``Corpus`` con ``references_doi`` y ``cited_by_id`` rellenados
            y dos ``EnricherRef`` registrados en el Manifest.
        """
        # Pasada 1: references_id → references_doi
        corpus = self.enrich_references_doi(corpus)

        # Pasada 2: cited_by_id para semillas aceptadas
        corpus = self.enrich_cited_by(corpus)

        return corpus

    # ------------------------------------------------------------------
    # Pasada 1: references_id → references_doi (pública para absorción en chain)
    # ------------------------------------------------------------------

    def enrich_references_doi(self, corpus: Corpus) -> Corpus:
        """Rellena ``references_doi`` alineado a ``references_id``.

        Pasada 1 del enriquecimiento (Hito 8a). Expuesta como método público
        para que ``chain`` pueda ejecutarla de forma aislada (sin la pasada
        de co-citación), usando el mismo helper ``enrich_corpus`` que ``enrich``
        standalone y ``build``.

        Args:
            corpus: Corpus de entrada.

        Returns:
            Corpus con ``references_doi`` rellenado y ``EnricherRef`` registrado.
        """
        return self._enrich_references_doi(corpus)

    def _enrich_references_doi(self, corpus: Corpus) -> Corpus:
        """Implementación interna de la pasada refs→DOI.

        Ver ``enrich_references_doi`` para la documentación pública.

        Args:
            corpus: Corpus de entrada.

        Returns:
            Corpus con ``references_doi`` rellenado y ``EnricherRef`` registrado.
        """
        table = corpus.to_arrow()
        rows = table.to_pylist()

        # Recolectar todos los references_id únicos
        all_ref_ids: set[str] = set()
        for row in rows:
            refs = row.get(Col.REFERENCES_ID) or []
            all_ref_ids.update(refs)

        if not all_ref_ids:
            return self._with_refs_doi_ref(corpus, resolved=0, total=0)

        # Resolver IDs a DOIs
        doi_map = self._source.fetch_dois_for(list(all_ref_ids))

        # Rellenar references_doi alineado a references_id
        enriched_rows: list[dict[str, Any]] = []
        for row in rows:
            row_copy = dict(row)
            refs = row_copy.get(Col.REFERENCES_ID) or []
            if refs:
                row_copy[Col.REFERENCES_DOI] = [doi_map.get(rid) for rid in refs]
            else:
                row_copy[Col.REFERENCES_DOI] = None
            enriched_rows.append(row_copy)

        from bib2graph.schemas import CORPUS_SCHEMA

        new_table = pa.Table.from_pylist(enriched_rows, schema=CORPUS_SCHEMA)
        new_corpus = Corpus.from_arrow(new_table).with_manifest(corpus.manifest)

        resolved = sum(1 for doi in doi_map.values() if doi)
        return self._with_refs_doi_ref(
            new_corpus, resolved=resolved, total=len(all_ref_ids)
        )

    # ------------------------------------------------------------------
    # Pasada 2: cited_by_id para semillas aceptadas (Hito 8b, pública para build)
    # ------------------------------------------------------------------

    def enrich_cited_by(self, corpus: Corpus) -> Corpus:
        """Puebla ``cited_by_id`` de las semillas aceptadas.

        Pasada 2 del enriquecimiento (Hito 8b). Expuesta como método público
        para que ``build`` pueda ejecutarla de forma aislada (sin la pasada
        de refs→DOI), usando el mismo helper ``enrich_corpus`` que ``enrich``
        standalone y ``chain``.

        Args:
            corpus: Corpus de entrada.

        Returns:
            Corpus con ``cited_by_id`` rellenado y ``EnricherRef`` registrado.
        """
        return self._enrich_cited_by(corpus)

    def _enrich_cited_by(self, corpus: Corpus) -> Corpus:
        """Implementación interna de la pasada cited_by.

        Ver ``enrich_cited_by`` para la documentación pública.

        Algoritmo:
        1. Filtra las semillas con ``curation_status=accepted`` y ``source_id``
           no nulo (solo esas tienen IDs válidos para consultar en OpenAlex).
           Bug #111: normaliza URL→corto vía ``_oa_id_short`` para que el lookup
           no falle en silencio si el id viene en forma URL.
        2. Si no hay ninguna, devuelve el corpus sin modificar y registra el
           ``EnricherRef`` con 0 citantes.
        3. Batchea los IDs objetivo en lotes ≤50 con
           ``source.fetch_citing_batch``, que pagina con cursor, atribuye
           por semilla y acota por ``max_per_paper`` (presupuesto por semilla).
           Devuelve ``{seed_id: [citer_id]}``, ya atribuido y acotado.
        4. Une los citantes devueltos con los existentes en ``cited_by_id``
           (idempotencia) y re-aplica el tope.
        5. Respeta ``max_citing_per_paper``: el Source ya acotó y atribuyó por
           semilla con presupuesto per-seed (orden determinista, alfabético).
        6. Idempotencia: ``cited_by_id`` es una unión de sets (existente +
           nuevos); re-enriquecer no duplica.

        Args:
            corpus: Corpus (ya con pasada 1 aplicada).

        Returns:
            Corpus con ``cited_by_id`` rellenado y ``EnricherRef`` registrado.
        """
        table = corpus.to_arrow()
        rows = table.to_pylist()

        # 1. Identificar semillas aceptadas con source_id (motor OpenAlex).
        # Bug #111: normalizar URL→corto para que el lookup no falle en silencio
        # si el id viene como URL completa (https://openalex.org/W...).
        from bib2graph.sources.openalex import _oa_id_short

        target_ids: list[str] = []
        for row in rows:
            if (
                row.get(Col.IS_SEED)
                and row.get(Col.CURATION_STATUS) == CurationStatus.ACCEPTED
                and row.get(Col.SOURCE_ID)
            ):
                raw_src = str(row[Col.SOURCE_ID])
                # Normalizar: si viene como URL de OpenAlex, extraer el segmento final
                normalized = _oa_id_short(raw_src) or raw_src
                target_ids.append(normalized)

        if not target_ids:
            return self._with_cited_by_ref(corpus, resolved=0, total=0)

        target_set: set[str] = set(target_ids)

        # 2. Batching: fetch_citing_batch loteó en ≤50, paginó con presupuesto
        # por semilla y devuelve ya atribuido y acotado: {seed_id: [citer_id]}
        citing_dict = self._source.fetch_citing_batch(
            target_ids, max_per_paper=self._max_citing_per_paper
        )

        # 3. Reconstruir filas con cited_by_id actualizado (unión con existentes).
        # total_new cuenta citantes efectivamente agregados post-tope.
        enriched_rows: list[dict[str, Any]] = []
        total_new = 0
        for row in rows:
            row_copy = dict(row)
            src_id_raw = row_copy.get(Col.SOURCE_ID)
            oa_id = _oa_id_short(str(src_id_raw)) if src_id_raw else None
            if oa_id and oa_id in target_set:
                existing: list[str] = list(row_copy.get(Col.CITED_BY_ID) or [])
                existing_set = set(existing)
                # Citantes devueltos por el source (ya acotados por max_per_paper)
                source_citers: list[str] = citing_dict.get(str(oa_id)) or []
                # Unión determinista; re-aplicar tope para idempotencia robusta
                merged = sorted(existing_set | set(source_citers))
                if self._max_citing_per_paper is not None:
                    merged = merged[: self._max_citing_per_paper]
                row_copy[Col.CITED_BY_ID] = merged
                # Contar solo los citantes efectivamente agregados (post-tope)
                total_new += len(set(merged) - existing_set)
            enriched_rows.append(row_copy)

        from bib2graph.schemas import CORPUS_SCHEMA

        new_table = pa.Table.from_pylist(enriched_rows, schema=CORPUS_SCHEMA)
        new_corpus = Corpus.from_arrow(new_table).with_manifest(corpus.manifest)

        return self._with_cited_by_ref(
            new_corpus,
            resolved=total_new,
            total=len(target_ids),
        )

    # ------------------------------------------------------------------
    # Helper: registrar EnricherRef en el Manifest (idempotente por nombre)
    # ------------------------------------------------------------------

    def _with_refs_doi_ref(
        self, corpus: Corpus, *, resolved: int, total: int
    ) -> Corpus:
        """Registra el ``EnricherRef`` de la pasada refs→DOI (Hito 8a).

        Usa la clave ``total_unique_refs`` (nombre histórico) para compatibilidad
        con el código cliente que lee ``params["total_unique_refs"]``.

        Idempotente: reemplaza por nombre si ya existe.

        Args:
            corpus: Corpus al que agregar el EnricherRef.
            resolved: Cantidad de referencias resueltas en esta pasada.
            total: Total de references_id únicos del corpus.

        Returns:
            Nuevo ``Corpus`` con el Manifest actualizado.
        """
        name = "openalex_references_doi"
        params = {
            "resolved": str(resolved),
            "total_unique_refs": str(total),
        }
        new_ref = EnricherRef(name=name, params=params)
        existing = corpus.manifest.enrichers
        updated = [e for e in existing if e.name != name]
        updated.append(new_ref)
        new_manifest = corpus.manifest.model_copy(update={"enrichers": updated})
        return corpus.with_manifest(new_manifest)

    def _with_cited_by_ref(
        self, corpus: Corpus, *, resolved: int, total: int
    ) -> Corpus:
        """Registra el ``EnricherRef`` de la pasada cited_by (Hito 8b).

        Usa la clave ``total`` para el total de seeds objetivo y ``resolved``
        para el total de nuevos citantes añadidos.

        Idempotente: reemplaza por nombre si ya existe.

        Args:
            corpus: Corpus al que agregar el EnricherRef.
            resolved: Nuevos citantes añadidos a ``cited_by_id`` en esta pasada.
            total: Total de seeds aceptadas procesadas.

        Returns:
            Nuevo ``Corpus`` con el Manifest actualizado.
        """
        name = "openalex_cited_by"
        params = {
            "resolved": str(resolved),
            "total": str(total),
        }
        new_ref = EnricherRef(name=name, params=params)
        existing = corpus.manifest.enrichers
        updated = [e for e in existing if e.name != name]
        updated.append(new_ref)
        new_manifest = corpus.manifest.model_copy(update={"enrichers": updated})
        return corpus.with_manifest(new_manifest)

    # ------------------------------------------------------------------
    # Alias de compatibilidad: _with_enricher_ref (Hito 8a)
    # ------------------------------------------------------------------

    def _with_enricher_ref(
        self, corpus: Corpus, *, resolved: int, total: int
    ) -> Corpus:
        """Alias de ``_with_refs_doi_ref`` para compatibilidad con código externo."""
        return self._with_refs_doi_ref(corpus, resolved=resolved, total=total)
