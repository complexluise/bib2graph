"""enrichers.openalex — ``OpenAlexEnricher``: enriquecedor via OpenAlex.

Hito 8a: resuelve ``references_id`` → ``references_doi`` para cada paper
del corpus, batcheando las consultas contra la API de OpenAlex (≤100 IDs
por request) y rellenando ``references_doi`` alineado al orden de
``references_id`` (DOI o None si OpenAlex no lo tiene).

Hito 8b (futuro, NO implementado aquí): poblar ``cited_by_id`` con los IDs
de papers que citan a cada semilla.  El diseño está preparado: agregar un
método ``_enrich_cited_by(corpus)`` que consulte
``GET /works?filter=cites:{openalex_id}`` y rellene solo la columna
``cited_by_id``, sin agregar filas nuevas al corpus (decisión del PO).

La frontera núcleo/costura se mantiene: el ``OpenAlexSource`` hace la I/O
(``fetch_dois_for``); el ``OpenAlexEnricher`` orquesta la lógica.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pyarrow as pa

from bib2graph.constants import Col
from bib2graph.corpus import Corpus, EnricherRef

if TYPE_CHECKING:
    from bib2graph.sources.openalex import OpenAlexSource


class OpenAlexEnricher:
    """Enriquece el corpus resolviendo ``references_id`` → ``references_doi``.

    Recibe un ``OpenAlexSource`` ya configurado (con email, api_key y/o
    transport inyectables), de modo que los tests pueden pasar un
    ``MockTransport`` sin tocar red.

    Ejemplo::

        source = OpenAlexSource(email="yo@example.com")
        enricher = OpenAlexEnricher(source)
        corpus_enriquecido = enricher.enrich(corpus)

    Hito 8b (diseño futuro): para poblar ``cited_by_id``, agregar el método
    ``_enrich_cited_by(corpus)`` y llamarlo desde ``enrich`` tras la resolución
    de referencias.  La semántica es: solo rellena ``cited_by_id`` de los papers
    que ya están en el corpus; NO agrega filas nuevas de citantes.
    """

    def __init__(self, source: OpenAlexSource) -> None:
        """Inicializa el enricher con un source ya configurado.

        Args:
            source: ``OpenAlexSource`` con credenciales y transport inyectados.
                El enricher reutiliza su cliente httpx y retry/backoff via
                ``source.fetch_dois_for``.
        """
        self._source = source

    def enrich(self, corpus: Corpus) -> Corpus:
        """Enriquece el corpus resolviendo ``references_id`` → ``references_doi``.

        Algoritmo (Hito 8a):
        1. Recolecta todos los ``references_id`` únicos del corpus.
        2. Si no hay ninguno, devuelve el corpus sin modificaciones (0 resueltas).
        3. Resuelve los IDs a DOIs batcheando por OR (≤100 IDs/request) via
           ``source.fetch_dois_for``.
        4. Para cada paper, rellena ``references_doi`` alineado al orden de
           ``references_id``: DOI si se resolvió, None si no.
        5. Registra un ``EnricherRef`` en el Manifest (procedencia).

        Idempotente: recomputar sobre el corpus ya enriquecido da el mismo
        resultado (la columna se sobreescribe, no se acumula).

        Args:
            corpus: Corpus a enriquecer.

        Returns:
            Nuevo ``Corpus`` con ``references_doi`` rellenado y ``EnricherRef``
            registrado en el Manifest.
        """
        table = corpus.to_arrow()
        rows = table.to_pylist()

        # 1. Recolectar todos los references_id únicos
        all_ref_ids: set[str] = set()
        for row in rows:
            refs = row.get(Col.REFERENCES_ID) or []
            all_ref_ids.update(refs)

        if not all_ref_ids:
            # Sin referencias → devolver corpus con EnricherRef registrado
            return self._with_enricher_ref(corpus, resolved=0, total=0)

        # 2. Resolver IDs a DOIs
        doi_map = self._source.fetch_dois_for(list(all_ref_ids))

        # 3. Rellenar references_doi alineado a references_id
        enriched_rows: list[dict[str, Any]] = []
        for row in rows:
            row_copy = dict(row)
            refs = row_copy.get(Col.REFERENCES_ID) or []
            if refs:
                row_copy[Col.REFERENCES_DOI] = [doi_map.get(rid) for rid in refs]
            else:
                row_copy[Col.REFERENCES_DOI] = None
            enriched_rows.append(row_copy)

        # 4. Reconstruir tabla Arrow con el schema canónico
        from bib2graph.schemas import CORPUS_SCHEMA

        new_table = pa.Table.from_pylist(enriched_rows, schema=CORPUS_SCHEMA)
        new_corpus = Corpus.from_arrow(new_table)

        # Preservar el manifest original (excepto el campo enrichers)
        resolved = sum(1 for doi in doi_map.values() if doi)
        return self._with_enricher_ref(
            new_corpus.with_manifest(corpus.manifest),
            resolved=resolved,
            total=len(all_ref_ids),
        )

    def _with_enricher_ref(
        self, corpus: Corpus, *, resolved: int, total: int
    ) -> Corpus:
        """Devuelve un Corpus nuevo con el EnricherRef de esta pasada registrado.

        Idempotente: si ya existe un EnricherRef con el mismo nombre, lo
        reemplaza (no acumula duplicados al re-enriquecer).

        Args:
            corpus: Corpus al que agregar el EnricherRef.
            resolved: Cantidad de referencias resueltas en esta pasada.
            total: Total de references_id únicos del corpus.

        Returns:
            Nuevo ``Corpus`` con el Manifest actualizado.
        """
        params = {
            "resolved": str(resolved),
            "total_unique_refs": str(total),
        }
        new_ref = EnricherRef(name="openalex_references_doi", params=params)

        # Idempotencia: reemplazar si ya existe un enricher con el mismo nombre
        existing = corpus.manifest.enrichers
        updated = [e for e in existing if e.name != new_ref.name]
        updated.append(new_ref)

        new_manifest = corpus.manifest.model_copy(update={"enrichers": updated})
        return corpus.with_manifest(new_manifest)
