---
title: API de Python
---

# API de Python

Referencia de la **superficie pública de la librería** `bib2graph`, agrupada por
tema. Se **autogenera desde los docstrings** del código (mkdocstrings): si cambia
el código, cambia esta página.

Para usar la herramienta desde la terminal, mirá la [referencia del CLI `b2g`](cli.md).

## Corpus y persistencia

::: bib2graph.Corpus
::: bib2graph.Manifest
::: bib2graph.CorpusSnapshot
::: bib2graph.SchemaError
::: bib2graph.TabularBackend
::: bib2graph.InMemoryBackend
::: bib2graph.stores.duckdb.DuckDBStore
::: bib2graph.backends.duckdb.DuckDBBackend

## Fuentes (siembra)

::: bib2graph.Source
::: bib2graph.OpenAlexSource
::: bib2graph.BibtexSource
::: bib2graph.SeedResult

## Forrajeo y curación

::: bib2graph.Forager
::: bib2graph.RankedCandidates
::: bib2graph.GrowthPreview
::: bib2graph.Preprocessor
::: bib2graph.apply_filters
::: bib2graph.FilterCriterion

## Redes (proyección)

::: bib2graph.Networks
::: bib2graph.NetworkArtifact
::: bib2graph.BibliographicCouplingProjector
::: bib2graph.CoCitationProjector
::: bib2graph.AuthorCollaborationProjector
::: bib2graph.InstitutionCollaborationProjector
::: bib2graph.KeywordCoOccurrenceProjector

## Análisis de redes

::: bib2graph.network_metrics
::: bib2graph.centrality
::: bib2graph.detect_communities
::: bib2graph.assortativity
::: bib2graph.community_composition
::: bib2graph.cocitation_quality_report
::: bib2graph.QualityThresholds

## Exportadores

::: bib2graph.GraphMLExporter
::: bib2graph.CsvExporter
