"""
Data ingestion module for bibliometric analysis of semiconductor supply chain.

This module provides functionality for ingesting bibliographic data from various sources
(BibTeX, CSV, JSON) and loading it into a Neo4j database for further analysis.
"""

import os
import json
import pandas as pd
import bibtexparser
from neomodel import db, config
from typing import Dict, List, Any, Optional, Union
from src.models import Paper, Author, Keyword, Institution, Publisher, ResearchArea

# Neo4j connection parameters
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # Change this in production

# Configure neomodel connection
config.DATABASE_URL = f"bolt://{NEO4J_USER}:{NEO4J_PASSWORD}@localhost:7687"

class BibliometricDataLoader:
    """Class for loading bibliometric data into Neo4j database."""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize the data loader with Neo4j connection parameters.

        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        # Configure neomodel connection
        config.DATABASE_URL = f"bolt://{user}:{password}@{uri.replace('bolt://', '')}"

    def load_csv(self, filepath: str) -> pd.DataFrame:
        """Load bibliographic data from a CSV file.

        Args:
            filepath: Path to the CSV file

        Returns:
            DataFrame containing the bibliographic data
        """
        return pd.read_csv(filepath)

    def load_bibtex(self, filepath: str) -> Dict[str, Any]:
        """Load bibliographic data from a BibTeX file.

        Args:
            filepath: Path to the BibTeX file

        Returns:
            Dictionary containing the bibliographic data
        """
        with open(filepath, 'r', encoding='utf-8') as bibtex_file:
            parser = bibtexparser.bparser.BibTexParser(common_strings=True)
            return bibtexparser.load(bibtex_file, parser=parser)

    def load_json(self, filepath: str) -> Dict[str, Any]:
        """Load bibliographic data from a JSON file.

        Args:
            filepath: Path to the JSON file

        Returns:
            Dictionary containing the bibliographic data
        """
        with open(filepath, 'r', encoding='utf-8') as json_file:
            return json.load(json_file)

    def normalize_metadata(self, data: Union[pd.DataFrame, Dict[str, Any]], source_type: str) -> List[Dict[str, Any]]:
        """Normalize metadata from different sources into a common format.

        Args:
            data: Bibliographic data from a source
            source_type: Type of source ('csv', 'bibtex', 'json')

        Returns:
            List of dictionaries with normalized metadata
        """
        normalized_data = []

        if source_type == 'csv':
            raise NotImplementedError('CSV normalization not yet implemented. Use BibTeX')

        elif source_type == 'bibtex':
            # Parsear todos los campos relevantes de cada entry
            for entry in data.entries:
                paper = {
                    'doi': entry.get('doi', ''),
                    'title': entry.get('title', ''),
                    'authors': [author.strip() for author in entry.get('author', '').split(' and ')],
                    'year': entry.get('year', ''),
                    'month': entry.get('month', ''),
                    'source': entry.get('journal', entry.get('booktitle', '')),
                    'volume': entry.get('volume', ''),
                    'issue': entry.get('number', ''),
                    'pages': entry.get('pages', ''),
                    'publisher': entry.get('publisher', ''),
                    'address': entry.get('address', ''),
                    'keywords': [kw.strip() for kw in entry.get('keywords', '').split(';') if kw.strip()],  # TODO Validar
                    'research_areas' : [research_areas.strip() for research_areas in entry['research-areas'].split(";")],
                    'abstract': entry.get('abstract', ''),
                    'issn': entry.get('issn', ''),
                    'isbn': entry.get('isbn', ''),
                    'url': entry.get('url', ''),
                    'language': entry.get('language', ''),
                    'type': entry.get('ENTRYTYPE', ''),
                    'institutions': [affi for affi in entry.get('affiliation', '').split(";")],
                }
                # Elimina entradas vacías de listas y cadenas
                for k in ['institutions']:
                    paper[k] = [v for v in paper[k] if v]
                normalized_data.append(paper)

        elif source_type == 'json':
            raise NotImplementedError('JSON normalization not yet implemented. Use BibTeX')

        return normalized_data

    def create_graph_nodes(self, papers: List[Dict[str, Any]]) -> None:
        """Create nodes and relationships in Neo4j from normalized paper data.

        Args:
            papers: List of normalized paper dictionaries
        """

        for paper_data in papers:
            paper_node = Paper(
                doi=paper_data['doi'],
                title=paper_data['title'],
                year=paper_data['year'],
                source=paper_data['source'],
                volume=paper_data.get('volume', ''),
                issue=paper_data.get('issue', ''),
                pages=paper_data.get('pages', ''),
                address=paper_data.get('address', ''),
                month=paper_data.get('month', ''),
                note=paper_data.get('note', ''),
                issn=paper_data.get('issn', ''),
                isbn=paper_data.get('isbn', ''),
                url=paper_data.get('url', ''),
                language=paper_data.get('language', ''),
                type=paper_data.get('type', ''),
                abstract=paper_data.get('abstract', ''),
                is_seed=True
            ).save()

            publisher_name = paper_data.get('publisher', '')
            if publisher_name:
                try:
                    publisher_node = Publisher.nodes.get(name=publisher_name)
                except Publisher.DoesNotExist:
                    publisher_node = Publisher(name=publisher_name).save()
                paper_node.publisher.connect(publisher_node)
                if paper_node.address and not publisher_node.address:
                    publisher_node.address = paper_node.address
                    publisher_node.save()

            # Crear Author nodes y relación AUTHORED
            for author_name in paper_data['authors']:
                try:
                    author_node = Author.nodes.get(name=author_name)
                except Author.DoesNotExist:
                    author_node = Author(name=author_name).save()
                author_node.papers.connect(paper_node)

            # Keywords
            for keyword in paper_data['keywords']:
                if keyword:
                    try:
                        keyword_node = Keyword.nodes.get(name=keyword)
                    except Keyword.DoesNotExist:
                        keyword_node = Keyword(name=keyword).save()
                paper_node.keywords.connect(keyword_node)

            # Research Areas
            for research_area in paper_data['research_areas']:
                if research_area:
                    try:
                        research_area_node = ResearchArea.nodes.get(name=research_area)
                    except ResearchArea.DoesNotExist:
                        research_area_node = ResearchArea(name=research_area).save()
                paper_node.research_areas.connect(research_area_node)

            # Institutions
            for institution in paper_data['institutions']:
                if institution:
                    try:
                        institution_node = Institution.nodes.get(name=institution)
                    except Institution.DoesNotExist:
                        institution_node = Institution(name=institution).save()
                paper_node.institutions.connect(institution_node)


    def process_file(self, filepath: str, file_type: str) -> None:
        """Process a file and load its data into Neo4j.

        Args:
            filepath: Path to the file
            file_type: Type of file ('csv', 'bibtex', 'json')
        """
        # Load data based on file type
        if file_type == 'csv':
            data = self.load_csv(filepath)
        elif file_type == 'bibtex':
            data = self.load_bibtex(filepath)
        elif file_type == 'json':
            data = self.load_json(filepath)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Normalize metadata
        normalized_data = self.normalize_metadata(data, file_type)

        # Create graph nodes and relationships
        self.create_graph_nodes(normalized_data)

    def process_directory(self, directory: str) -> None:
        """Process all supported files in a directory.

        Args:
            directory: Path to the directory
        """
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)

            if filename.endswith('.csv'):
                self.process_file(filepath, 'csv')
            elif filename.endswith('.bib'):
                self.process_file(filepath, 'bibtex')
            elif filename.endswith('.json'):
                self.process_file(filepath, 'json')

# Example usage
if __name__ == "__main__":
    loader = BibliometricDataLoader()

    # Process a single CSV file
    csv_file = "data/Citación semiconductores comercio internacional.txt"
    if os.path.exists(csv_file):
        loader.process_file(csv_file, 'csv')

    # Process all files in a directory
    # loader.process_directory("data")