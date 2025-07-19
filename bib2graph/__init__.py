"""
bib2graph - A Python package for bibliometric data processing and network analysis.

This package provides tools for:
1. Ingesting bibliographic data from various sources
2. Enriching data with additional metadata from external APIs
3. Extracting and analyzing bibliometric networks

Main components:
- BibliometricDataLoader: For loading and normalizing bibliographic data
- BibliometricDataEnricher: For enriching data with additional metadata
- BibliometricNetworkAnalyzer: For extracting and analyzing networks

Core functions:
- ingestar_datos: For ingesting data from various sources
- enriquecer_datos: For enriching data with additional metadata
- crear_relaciones_red: For creating network relationships
- analizar_red: For analyzing networks
- ejecutar_pipeline_completo: For running the complete pipeline
"""

__version__ = "0.1.1"


from bib2graph.consigue_los_articulos import BibliometricDataLoader
from bib2graph.enriquecimiento import BibliometricDataEnricher
from bib2graph.analisis_red import BibliometricNetworkAnalyzer
from bib2graph.models import *
from bib2graph.main import (
    ingestar_datos, enriquecer_datos, crear_relaciones_red, analizar_red, ejecutar_pipeline_completo
)
