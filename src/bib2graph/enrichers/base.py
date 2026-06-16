"""enrichers.base — Protocolo ``Enricher``.

Define el contrato que deben cumplir todos los enriquecedores del núcleo
y los extras.  El ``Enricher`` es un ``Protocol`` comprobable en runtime
(``@runtime_checkable``) para que el tipo-check y ``isinstance`` funcionen
sin herencia explícita.

Contrato:
  - ``enrich(corpus)`` devuelve un ``Corpus`` *nuevo* (semántica de valor).
  - **Idempotente**: ``enrich(enrich(c))`` produce el mismo resultado que
    ``enrich(c)`` —sin duplicar datos ni alterar papers no enriquecidos.
  - **No pierde papers**: el corpus resultado siempre tiene al menos los
    mismos papers que el corpus de entrada.
  - **Config inyectada**: las credenciales y dependencias se pasan al
    constructor, nunca como globales ni default secretos.
  - El método no transiciona el ``CycleState`` del store; eso lo hace el
    comando CLI ``b2g enrich`` si corresponde.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bib2graph.corpus import Corpus


@runtime_checkable
class Enricher(Protocol):
    """Protocolo de enriquecedor de Corpus.

    Cualquier clase con el método ``enrich(corpus: Corpus) -> Corpus``
    cumple el protocolo, sin necesidad de herencia explícita.

    Args:
        corpus: Corpus a enriquecer.

    Returns:
        Corpus nuevo con los campos adicionales rellenados.
    """

    def enrich(self, corpus: Corpus) -> Corpus:
        """Enriquece el corpus y devuelve uno nuevo.

        Semántica de valor: la instancia original no muta nunca.
        El resultado es idempotente: enriquecer dos veces da el mismo corpus.

        Args:
            corpus: Corpus a enriquecer.

        Returns:
            Nuevo ``Corpus`` con los campos enriquecidos.
        """
        ...
