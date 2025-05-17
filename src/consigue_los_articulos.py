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
from src.models import Paper, Author, Keyword, Institution, Funder

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
            # Assuming data is a pandas DataFrame
            for _, row in data.iterrows():
                paper = {
                    'doi': row.get('DOI', ''),
                    'title': row.get('Title', ''),
                    'authors': [author.strip() for author in row.get('Authors', '').split(';')],
                    'year': row.get('Publication Year', ''),
                    'source': row.get('Source Title', ''),
                    'keywords': [],  # CSV might not have keywords
                    'references': [],  # CSV might not have references
                    'institutions': [],  # Extract from affiliations if available
                    'funders': []  # Extract from acknowledgments if available
                }
                normalized_data.append(paper)

        elif source_type == 'bibtex':
            # Assuming data is a bibtexparser result
            for entry in data.entries:
                paper = {
                    'doi': entry.get('doi', ''),
                    'title': entry.get('title', ''),
                    'authors': [author.strip() for author in entry.get('author', '').split(' and ')],
                    'year': entry.get('year', ''),
                    'source': entry.get('journal', ''),
                    'keywords': [kw.strip() for kw in entry.get('keywords', '').split(',')],
                    'abstract': entry.get('abstract', ''),
                    'references': [],  # BibTeX might not have references
                    'institutions': [],  # Extract from affiliations if available
                    'funders': []  # Extract from acknowledgments if available
                }
                normalized_data.append(paper)

        elif source_type == 'json':
            # Assuming a specific JSON format, adjust as needed
            if isinstance(data, list):
                for item in data:
                    paper = {
                        'doi': item.get('doi', ''),
                        'title': item.get('title', ''),
                        'authors': item.get('authors', []),
                        'year': item.get('year', ''),
                        'source': item.get('source', ''),
                        'keywords': item.get('keywords', []),
                        'references': item.get('references', []),
                        'institutions': item.get('institutions', []),
                        'funders': item.get('funders', [])
                    }
                    normalized_data.append(paper)
            else:
                # Single paper in JSON
                paper = {
                    'doi': data.get('doi', ''),
                    'title': data.get('title', ''),
                    'authors': data.get('authors', []),
                    'year': data.get('year', ''),
                    'source': data.get('source', ''),
                    'keywords': data.get('keywords', []),
                    'references': data.get('references', []),
                    'institutions': data.get('institutions', []),
                    'funders': data.get('funders', [])
                }
                normalized_data.append(paper)

        return normalized_data

    def create_graph_nodes(self, papers: List[Dict[str, Any]]) -> None:
        """Create nodes and relationships in Neo4j from normalized paper data.

        Args:
            papers: List of normalized paper dictionaries
        """
        for paper_data in papers:
            # Create Paper node
            paper_node = Paper(
                doi=paper_data['doi'],
                title=paper_data['title'],
                year=paper_data['year'],
                source=paper_data['source']
            ).save()

            # Create Author nodes and relationships
            for author_name in paper_data['authors']:
                # Get or create author
                try:
                    author_node = Author.nodes.get(name=author_name)
                except Author.DoesNotExist:
                    author_node = Author(name=author_name).save()

                # Create AUTHORED relationship
                author_node.papers.connect(paper_node)

            # Create Keyword nodes and relationships
            for keyword in paper_data['keywords']:
                if keyword:  # Skip empty keywords
                    # Get or create keyword
                    try:
                        keyword_node = Keyword.nodes.get(name=keyword)
                    except Keyword.DoesNotExist:
                        keyword_node = Keyword(name=keyword).save()

                    # Create HAS_KEYWORD relationship
                    paper_node.keywords.connect(keyword_node)

            # Create Institution nodes and relationships
            for institution in paper_data['institutions']:
                if institution:  # Skip empty institutions
                    # Get or create institution
                    try:
                        institution_node = Institution.nodes.get(name=institution)
                    except Institution.DoesNotExist:
                        institution_node = Institution(name=institution).save()

                    # Find authors affiliated with this institution
                    for author_name in paper_data['authors']:
                        try:
                            author_node = Author.nodes.get(name=author_name)
                            # Create AFFILIATED_WITH relationship
                            author_node.institutions.connect(institution_node)
                        except Author.DoesNotExist:
                            pass

            # Create Funder nodes and relationships
            for funder in paper_data['funders']:
                if funder:  # Skip empty funders
                    # Get or create funder
                    try:
                        funder_node = Funder.nodes.get(name=funder)
                    except Funder.DoesNotExist:
                        funder_node = Funder(name=funder).save()

                    # Create FUNDED_BY relationship
                    paper_node.funders.connect(funder_node)

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
