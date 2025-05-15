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
from py2neo import Graph, Node, Relationship, NodeMatcher
import s2
from crossrefapi import Works
from elsapy.elsclient import ElsClient
from elsapy.elsdoc import FullDoc

# Neo4j connection parameters
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # Change this in production

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
        self.graph = Graph(uri, auth=(user, password))
        self.node_matcher = NodeMatcher(self.graph)
        
        # Initialize API clients
        self.works = Works()
        
        # Initialize Scopus client if API key is available
        self.els_client = None
        if SCOPUS_API_KEY:
            self.els_client = ElsClient(SCOPUS_API_KEY)
    
    def get_papers_to_enrich(self) -> List[Node]:
        """Get papers from Neo4j that have a DOI but might need enrichment.
        
        Returns:
            List of Paper nodes with DOIs
        """
        # Find papers with DOIs
        cypher_query = """
        MATCH (p:Paper)
        WHERE p.doi IS NOT NULL AND p.doi <> ''
        RETURN p
        """
        return list(self.graph.run(cypher_query).data())
    
    def enrich_from_semantic_scholar(self, paper_node: Node) -> Dict[str, Any]:
        """Enrich paper data using Semantic Scholar API.
        
        Args:
            paper_node: Neo4j Paper node to enrich
            
        Returns:
            Dictionary with enriched data
        """
        doi = paper_node['doi']
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
                            'doi': citation.externalIds.get('DOI', '')
                        })
                
                # Extract references
                for reference in paper.references:
                    if reference.paperId:
                        enriched_data['references'].append({
                            'paperId': reference.paperId,
                            'title': reference.title,
                            'doi': reference.externalIds.get('DOI', '')
                        })
                
                # Extract authors with ORCID if available
                for author in paper.authors:
                    author_data = {
                        'name': author.name,
                        'authorId': author.authorId
                    }
                    if hasattr(author, 'externalIds') and author.externalIds:
                        author_data['orcid'] = author.externalIds.get('ORCID', '')
                    enriched_data['authors'].append(author_data)
        
        except Exception as e:
            print(f"Error enriching from Semantic Scholar: {e}")
        
        return enriched_data
    
    def enrich_from_crossref(self, paper_node: Node) -> Dict[str, Any]:
        """Enrich paper data using CrossRef API.
        
        Args:
            paper_node: Neo4j Paper node to enrich
            
        Returns:
            Dictionary with enriched data
        """
        doi = paper_node['doi']
        enriched_data = {
            'funders': [],
            'institutions': []
        }
        
        try:
            # Query CrossRef API
            work = self.works.doi(doi)
            
            if work:
                # Extract funders
                if 'funder' in work:
                    for funder in work['funder']:
                        if 'name' in funder:
                            enriched_data['funders'].append({
                                'name': funder['name'],
                                'doi': funder.get('DOI', '')
                            })
                
                # Extract institutions from affiliations
                if 'author' in work:
                    for author in work['author']:
                        if 'affiliation' in author:
                            for affiliation in author['affiliation']:
                                if 'name' in affiliation:
                                    enriched_data['institutions'].append({
                                        'name': affiliation['name']
                                    })
        
        except Exception as e:
            print(f"Error enriching from CrossRef: {e}")
        
        return enriched_data
    
    def enrich_from_scopus(self, paper_node: Node) -> Dict[str, Any]:
        """Enrich paper data using Scopus API.
        
        Args:
            paper_node: Neo4j Paper node to enrich
            
        Returns:
            Dictionary with enriched data
        """
        doi = paper_node['doi']
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
    
    def update_neo4j_with_enriched_data(self, paper_node: Node, enriched_data: Dict[str, Any]) -> None:
        """Update Neo4j database with enriched data.
        
        Args:
            paper_node: Neo4j Paper node to update
            enriched_data: Dictionary with enriched data
        """
        # Start a transaction
        tx = self.graph.begin()
        
        # Update citations
        for citation in enriched_data.get('citations', []):
            if 'doi' in citation and citation['doi']:
                # Check if cited paper exists
                cited_paper = self.node_matcher.match("Paper", doi=citation['doi']).first()
                
                # Create cited paper if it doesn't exist
                if not cited_paper:
                    cited_paper = Node("Paper", 
                                      doi=citation['doi'],
                                      title=citation.get('title', ''))
                    tx.create(cited_paper)
                
                # Create CITED relationship
                cited_rel = Relationship(paper_node, "CITED", cited_paper)
                tx.merge(cited_rel)
        
        # Update references
        for reference in enriched_data.get('references', []):
            if 'doi' in reference and reference['doi']:
                # Check if referenced paper exists
                ref_paper = self.node_matcher.match("Paper", doi=reference['doi']).first()
                
                # Create referenced paper if it doesn't exist
                if not ref_paper:
                    ref_paper = Node("Paper", 
                                    doi=reference['doi'],
                                    title=reference.get('title', ''))
                    tx.create(ref_paper)
                
                # Create REFERENCES relationship
                ref_rel = Relationship(paper_node, "REFERENCES", ref_paper)
                tx.merge(ref_rel)
        
        # Update authors with ORCID
        for author_data in enriched_data.get('authors', []):
            if 'name' in author_data:
                # Find author node
                author_node = self.node_matcher.match("Author", name=author_data['name']).first()
                
                # Update author with ORCID if available
                if author_node and 'orcid' in author_data and author_data['orcid']:
                    author_node['orcid'] = author_data['orcid']
                    tx.push(author_node)
        
        # Update funders
        for funder in enriched_data.get('funders', []):
            if 'name' in funder:
                # Check if funder exists
                funder_node = self.node_matcher.match("Funder", name=funder['name']).first()
                
                # Create funder if it doesn't exist
                if not funder_node:
                    funder_node = Node("Funder", name=funder['name'])
                    if 'doi' in funder and funder['doi']:
                        funder_node['doi'] = funder['doi']
                    tx.create(funder_node)
                
                # Create FUNDED_BY relationship
                funded_by_rel = Relationship(paper_node, "FUNDED_BY", funder_node)
                tx.merge(funded_by_rel)
        
        # Update institutions
        for institution in enriched_data.get('institutions', []):
            if 'name' in institution:
                # Check if institution exists
                institution_node = self.node_matcher.match("Institution", name=institution['name']).first()
                
                # Create institution if it doesn't exist
                if not institution_node:
                    institution_node = Node("Institution", name=institution['name'])
                    tx.create(institution_node)
                
                # Find authors of the paper
                cypher_query = """
                MATCH (a:Author)-[:AUTHORED]->(p:Paper {doi: $doi})
                RETURN a
                """
                authors = list(self.graph.run(cypher_query, doi=paper_node['doi']).data())
                
                # Create AFFILIATED_WITH relationships
                for author_data in authors:
                    author_node = author_data['a']
                    affiliated_rel = Relationship(author_node, "AFFILIATED_WITH", institution_node)
                    tx.merge(affiliated_rel)
        
        # Update keywords
        for keyword in enriched_data.get('keywords', []):
            if 'name' in keyword:
                # Check if keyword exists
                keyword_node = self.node_matcher.match("Keyword", name=keyword['name']).first()
                
                # Create keyword if it doesn't exist
                if not keyword_node:
                    keyword_node = Node("Keyword", name=keyword['name'])
                    tx.create(keyword_node)
                
                # Create HAS_KEYWORD relationship
                has_keyword_rel = Relationship(paper_node, "HAS_KEYWORD", keyword_node)
                tx.merge(has_keyword_rel)
        
        # Commit the transaction
        tx.commit()
    
    def enrich_paper(self, paper_node: Node) -> None:
        """Enrich a paper with data from all available APIs.
        
        Args:
            paper_node: Neo4j Paper node to enrich
        """
        # Get paper data
        paper = paper_node['p'] if isinstance(paper_node, dict) else paper_node
        
        # Skip if no DOI
        if not paper.get('doi'):
            return
        
        print(f"Enriching paper: {paper.get('title')} (DOI: {paper.get('doi')})")
        
        # Enrich from Semantic Scholar
        s2_data = self.enrich_from_semantic_scholar(paper)
        
        # Enrich from CrossRef
        crossref_data = self.enrich_from_crossref(paper)
        
        # Enrich from Scopus
        scopus_data = self.enrich_from_scopus(paper)
        
        # Combine enriched data
        enriched_data = {**s2_data, **crossref_data, **scopus_data}
        
        # Update Neo4j with enriched data
        self.update_neo4j_with_enriched_data(paper, enriched_data)
        
        # Sleep to respect API rate limits
        time.sleep(1)
    
    def enrich_all_papers(self) -> None:
        """Enrich all papers in the database that have DOIs."""
        papers = self.get_papers_to_enrich()
        
        for paper_data in papers:
            self.enrich_paper(paper_data)
            
            # Sleep to respect API rate limits
            time.sleep(2)

# Example usage
if __name__ == "__main__":
    enricher = BibliometricDataEnricher()
    enricher.enrich_all_papers()