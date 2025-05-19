"""
Enrichment module for bibliometric analysis of semiconductor supply chain.

This module provides functionality for enriching bibliographic data in the Neo4j database
by querying external APIs (Semantic Scholar, CrossRef, Scopus) for additional metadata.
"""

import os
import time
import json
from typing import Dict, List, Any, Optional, Union
import requests
from neomodel import db, config
import s2
from crossref.restful import Works
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc
from src.models import Paper, Author, Keyword, Institution

# Neo4j connection parameters
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # Change this in production

# Configure neomodel connection
config.DATABASE_URL = f"bolt://{NEO4J_USER}:{NEO4J_PASSWORD}@localhost:7687"

# API keys (replace with your own)
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
SCOPUS_API_KEY = os.environ.get("SCOPUS_API_KEY", "")

class BibliometricDataEnricher:
    """Class for enriching bibliometric data in Neo4j database using external APIs."""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize the data enricher with Neo4j connection parameters.

        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        # Configure neomodel connection
        config.DATABASE_URL = f"bolt://{user}:{password}@{uri.replace('bolt://', '')}"

        # Initialize API clients
        self.works = Works()

        # Initialize Scopus client if API key is available
        self.els_client = None
        if SCOPUS_API_KEY:
            self.els_client = ElsClient(SCOPUS_API_KEY)

    def get_papers_to_enrich(self) -> List[Paper]:
        """Get papers from Neo4j that have a DOI but might need enrichment.

        Returns:
            List of Paper nodes with DOIs
        """
        # Find papers with DOIs using neomodel
        return Paper.nodes.filter(doi__ne='')  # Get all papers with non-empty DOIs

    def enrich_from_semantic_scholar(self, paper_node: Paper) -> Dict[str, Any]:
        """Enrich paper data using Semantic Scholar API.

        Args:
            paper_node: Neo4j Paper node to enrich

        Returns:
            Dictionary with enriched data
        """
        doi = paper_node.doi
        enriched_data = {
            'citations': [],
            'references': [],
            'authors': []
        }

        try:
            # Create a session with API key if available
            session = None
            if SEMANTIC_SCHOLAR_API_KEY:
                session = requests.Session()
                session.headers = {'x-api-key': SEMANTIC_SCHOLAR_API_KEY}

            # Query Semantic Scholar API
            paper = s2.api.get_paper(
                paperId=f"DOI:{doi}",
                session=session,
                retries=2,
                wait=150,
                params=dict(include_unknown_references=True)
            )

            if paper:
                # Extract citations
                for citation in paper.citations:
                    if citation.paperId:
                        enriched_data['citations'].append({
                            'paperId': citation.paperId,
                            'title': citation.title,
                            'doi': citation.doi
                        })

                # Extract references
                for reference in paper.references:
                    if reference.paperId:
                        enriched_data['references'].append({
                            'paperId': reference.paperId,
                            'title': reference.title,
                            'doi': reference.doi
                        })

                # Extract authors with ORCID if available
                for author in paper.authors:
                    author_data = {
                        'name': author.name,
                        'authorId': author.authorId
                    }
                    if hasattr(author, 'externalIds') and author.externalIds:
                        author_data['url'] = author.externalIds.url
                    enriched_data['authors'].append(author_data)

        except Exception as e:
            print(f"Error enriching from Semantic Scholar: {e}")

        return enriched_data


    def enrich_from_scopus(self, paper_node: Paper) -> Dict[str, Any]:
        """Enrich paper data using Scopus API.

        Args:
            paper_node: Neo4j Paper node to enrich

        Returns:
            Dictionary with enriched data
        """
        doi = paper_node.doi
        enriched_data = {
            'citations': [],
            'keywords': []
        }

        # Skip if no Scopus API key or client
        if not self.els_client:
            return enriched_data

        try:
            # Query Scopus API
            doc = FullDoc(doi=doi)
            if doc.read(self.els_client):
                # Extract keywords
                if hasattr(doc, 'authkeywords'):
                    for keyword in doc.authkeywords:
                        enriched_data['keywords'].append({
                            'name': keyword
                        })

                # Extract citations if available
                if hasattr(doc, 'references'):
                    for reference in doc.references:
                        if 'doi' in reference:
                            enriched_data['citations'].append({
                                'doi': reference['doi'],
                                'title': reference.get('title', '')
                            })

        except Exception as e:
            print(f"Error enriching from Scopus: {e}")

        return enriched_data

    def update_neo4j_with_enriched_data(self, paper_node: Paper, enriched_data: Dict[str, Any]) -> None:
        """Update Neo4j database with enriched data.

        Args:
            paper_node: Neo4j Paper node to update
            enriched_data: Dictionary with enriched data
        """
        # Update citations
        for citation in enriched_data.get('citations', []):
            if 'doi' in citation and citation['doi']:
                # Check if cited paper exists
                try:
                    cited_paper = Paper.nodes.get(doi=citation['doi'])
                except Paper.DoesNotExist:
                    # Create cited paper if it doesn't exist
                    cited_paper = Paper(
                        doi=citation['doi'],
                        title=citation.get('title', ''),
                        is_seed=False
                    ).save()

                # Create CITED relationship
                paper_node.cited.connect(cited_paper)

        # Update references
        for reference in enriched_data.get('references', []):
            if 'doi' in reference and reference['doi']:
                # Check if referenced paper exists
                try:
                    ref_paper = Paper.nodes.get(doi=reference['doi'])
                except Paper.DoesNotExist:
                    # Create referenced paper if it doesn't exist
                    ref_paper = Paper(
                        doi=reference['doi'],
                        title=reference.get('title', '')
                    ).save()

                # Create REFERENCES relationship
                paper_node.references.connect(ref_paper)

        # Update authors with ORCID
        for author_data in enriched_data.get('authors', []):
            if 'name' in author_data:
                # Find author node
                try:
                    author_node = Author.nodes.get(name=author_data['name'])

                    # Update author with ORCID if available
                    if 'orcid' in author_data and author_data['orcid']:
                        author_node.orcid = author_data['orcid']
                        author_node.save()
                except Author.DoesNotExist:
                    pass

        # Update institutions
        for institution in enriched_data.get('institutions', []):
            if 'name' in institution:
                # Check if institution exists
                try:
                    institution_node = Institution.nodes.get(name=institution['name'])
                except Institution.DoesNotExist:
                    # Create institution if it doesn't exist
                    institution_node = Institution(name=institution['name']).save()

                # Find authors of the paper and create AFFILIATED_WITH relationships
                for author in paper_node.authors:
                    author.institutions.connect(institution_node)

        # Update keywords
        for keyword in enriched_data.get('keywords', []):
            if 'name' in keyword:
                # Check if keyword exists
                try:
                    keyword_node = Keyword.nodes.get(name=keyword['name'])
                except Keyword.DoesNotExist:
                    # Create keyword if it doesn't exist
                    keyword_node = Keyword(name=keyword['name']).save()

                # Create HAS_KEYWORD relationship
                paper_node.keywords.connect(keyword_node)

    def enrich_paper(self, paper_node: Paper) -> None:
        """Enrich a paper with data from all available APIs.

        Args:
            paper_node: Neo4j Paper node to enrich
        """
        # Skip if no DOI
        if not paper_node.doi:
            return

        print(f"Enriching paper: {paper_node.title} (DOI: {paper_node.doi})")

        # Enrich from Semantic Scholar
        s2_data = self.enrich_from_semantic_scholar(paper_node)

        # Enrich from CrossRef
        #crossref_data = self.enrich_from_crossref(paper_node)

        # Enrich from Scopus
        scopus_data = self.enrich_from_scopus(paper_node)

        # Combine enriched data
        enriched_data = {
            **s2_data,
            #**crossref_data,
            **scopus_data}

        # Update Neo4j with enriched data
        self.update_neo4j_with_enriched_data(paper_node, enriched_data)

        # Sleep to respect API rate limits
        time.sleep(2)

    def enrich_all_papers(self) -> None:
        """Enrich all papers in the database that have DOIs."""
        papers = self.get_papers_to_enrich()

        for paper in papers:
            self.enrich_paper(paper)

            # Sleep to respect API rate limits
            time.sleep(2)

# Example usage
if __name__ == "__main__":
    enricher = BibliometricDataEnricher()
    enricher.enrich_all_papers()
