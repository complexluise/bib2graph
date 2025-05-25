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
"""

from .consigue_los_articulos import BibliometricDataLoader
from .enriquecimiento import BibliometricDataEnricher
from .analisis_red import BibliometricNetworkAnalyzer
from .models import *

__version__ = "0.1.0"
