"""
Network analysis module for bibliometric analysis of semiconductor supply chain.

This module provides functionality for extracting co-citation networks from the Neo4j database
and exporting them for analysis in external tools.
"""

import os
import networkx as nx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from neomodel import db, config
from typing import Dict, Any, Tuple, Set

# Neo4j connection parameters
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # Change this in production

# Configure neomodel connection
config.DATABASE_URL = f"bolt://{NEO4J_USER}:{NEO4J_PASSWORD}@localhost:7687"

class BibliometricNetworkAnalyzer:
    """Class for analyzing bibliometric networks from Neo4j database."""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize the network analyzer with Neo4j connection parameters.

        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        # Configure neomodel connection
        config.DATABASE_URL = f"bolt://{user}:{password}@{uri.replace('bolt://', '')}"

    def create_co_citation_relationships(self) -> int:
        """Create CO_CITED_WITH relationships in Neo4j based on shared references.

        Returns:
            Number of CO_CITED_WITH relationships created
        """
        cypher_query = """
        MATCH (p1:Paper {is_seed: True})-[:REFERENCES]->(ref:Paper)<-[:REFERENCES]-(p2:Paper {is_seed: True})
        WHERE p1 <> p2
        WITH p1, p2, COUNT(ref) AS shared_refs
        WHERE shared_refs > 0
        MERGE (p1)-[r:CO_CITED_WITH]-(p2)
        ON CREATE SET r.weight = shared_refs
        RETURN COUNT(r) AS relationship_count
        """

        results, meta = db.cypher_query(cypher_query)
        return results[0][0] if results else 0

    def create_author_collaboration_relationships(self) -> int:
        """Create COLLABORATED_WITH relationships in Neo4j between authors who co-authored papers.

        Returns:
            Number of COLLABORATED_WITH relationships created
        """
        cypher_query = """
        MATCH (a1:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)
        WHERE a1 <> a2
        WITH a1, a2, COUNT(p) AS collaboration_count
        WHERE collaboration_count > 0
        MERGE (a1)-[r:COLLABORATED_WITH]-(a2)
        ON CREATE SET r.weight = collaboration_count
        RETURN COUNT(r) AS relationship_count
        """

        results, meta = db.cypher_query(cypher_query)
        return results[0][0] if results else 0

    def create_institution_collaboration_relationships(self) -> int:
        """Create COLLABORATED_WITH relationships in Neo4j between institutions whose authors co-authored papers.

        Returns:
            Number of COLLABORATED_WITH relationships created
        """
        cypher_query = """
        MATCH (i1:Institution)<-[:AFFILIATED_WITH]-(a1:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)-[:AFFILIATED_WITH]->(i2:Institution)
        WHERE i1 <> i2
        WITH i1, i2, COUNT(DISTINCT p) AS collaboration_count
        WHERE collaboration_count > 0
        MERGE (i1)-[r:COLLABORATED_WITH]-(i2)
        ON CREATE SET r.weight = collaboration_count
        RETURN COUNT(r) AS relationship_count
        """

        results, meta = db.cypher_query(cypher_query)
        return results[0][0] if results else 0

    def create_keyword_co_occurrence_relationships(self) -> int:
        """Create CO_OCCURS_WITH relationships in Neo4j between keywords that appear in the same papers.

        Returns:
            Number of CO_OCCURS_WITH relationships created
        """
        cypher_query = """
        MATCH (k1:Keyword)<-[:HAS_KEYWORD]-(p:Paper)-[:HAS_KEYWORD]->(k2:Keyword)
        WHERE k1 <> k2
        WITH k1, k2, COUNT(p) AS cooccurrence_count
        WHERE cooccurrence_count > 0
        MERGE (k1)-[r:CO_OCCURS_WITH]-(k2)
        ON CREATE SET r.weight = cooccurrence_count
        RETURN COUNT(r) AS relationship_count
        """

        results, meta = db.cypher_query(cypher_query)
        return results[0][0] if results else 0

    def generate_quality_report(self, dois_set: Set[str]) -> Dict[str, Any]:
        """Generate a quality report for the co-citation network.

        Args:
            dois_set: Set of DOIs involved in the co-citation network

        Returns:
            Dictionary containing quality metrics
        """
        report = {}

        # 1. Document volume check
        report["document_count"] = len(dois_set)
        report["meets_volume_threshold"] = report["document_count"] >= 200

        # 2. DOI and references percentage
        if dois_set:
            doi_ref_query = """
            MATCH (p:Paper)
            WHERE p.doi IN $dois
            RETURN COUNT(p) AS total,
                   SUM(
                       CASE 
                           WHEN p.doi IS NOT NULL AND EXISTS { (p)-[:REFERENCES]->() }
                           THEN 1 
                           ELSE 0 
                       END
                   ) AS with_doi_and_refs
            """
            results, _ = db.cypher_query(doi_ref_query, {"dois": list(dois_set)})
            total = results[0][0] if results and results[0][0] is not None else 0
            with_doi_and_refs = results[0][1] if results and results[0][1] is not None else 0

            if total > 0:
                report["doi_ref_percentage"] = (with_doi_and_refs / total) * 100
            else:
                report["doi_ref_percentage"] = 0

            report["meets_doi_ref_threshold"] = report["doi_ref_percentage"] >= 90
        else:
            report["doi_ref_percentage"] = 0
            report["meets_doi_ref_threshold"] = False

        # 3. Temporal coverage
        if dois_set:
            year_query = """
            MATCH (p:Paper)
            WHERE p.doi IN $dois AND p.year IS NOT NULL
            RETURN MIN(toInteger(p.year)) AS min_year, 
                   MAX(toInteger(p.year)) AS max_year,
                   COUNT(DISTINCT p.year) AS unique_years
            """
            results, _ = db.cypher_query(year_query, {"dois": list(dois_set)})

            if results and results[0][0] is not None:
                report["min_year"] = results[0][0]
                report["max_year"] = results[0][1]
                report["unique_years"] = results[0][2]
                report["temporal_coverage"] = f"{report['min_year']}–{report['max_year']}"
                # Check if coverage includes 2000-2024
                report["meets_temporal_threshold"] = (
                    report["min_year"] <= 2000 and report["max_year"] >= 2024
                )
            else:
                report["temporal_coverage"] = "No data"
                report["meets_temporal_threshold"] = False
        else:
            report["temporal_coverage"] = "No data"
            report["meets_temporal_threshold"] = False

        # 4. Geographic diversity
        if dois_set:
            country_query = """
            MATCH (p:Paper)-[:AUTHORED]->(a:Author)-[:AFFILIATED_WITH]->(i:Institution)
            WHERE p.doi IN $dois
            RETURN COUNT(DISTINCT i.address) AS country_count
            """
            results, _ = db.cypher_query(country_query, {"dois": list(dois_set)})

            report["country_count"] = results[0][0] if results and results[0][0] is not None else 0
            report["meets_geographic_threshold"] = report["country_count"] >= 5
        else:
            report["country_count"] = 0
            report["meets_geographic_threshold"] = False

        # 5. Key author participation
        if dois_set:
            author_query = """
            MATCH (p:Paper)-[:AUTHORED]->(a:Author)
            WHERE p.doi IN $dois
            WITH a, COUNT(p) AS paper_count
            WHERE paper_count > 1
            RETURN COUNT(a) AS recurring_authors
            """
            results, _ = db.cypher_query(author_query, {"dois": list(dois_set)})

            report["recurring_authors"] = results[0][0] if results and results[0][0] is not None else 0
            report["meets_author_threshold"] = report["recurring_authors"] >= 10

            # Get top authors for the report
            top_authors_query = """
            MATCH (p:Paper)-[:AUTHORED]->(a:Author)
            WHERE p.doi IN $dois
            WITH a, COUNT(p) AS paper_count
            ORDER BY paper_count DESC
            LIMIT 10
            RETURN a.name AS author_name, paper_count
            """
            results, meta = db.cypher_query(top_authors_query, {"dois": list(dois_set)})
            columns = [col for col in meta]

            top_authors = []
            for row in results:
                record = dict(zip(columns, row))
                top_authors.append({
                    "name": record["author_name"],
                    "paper_count": record["paper_count"]
                })

            report["top_authors"] = top_authors
        else:
            report["recurring_authors"] = 0
            report["meets_author_threshold"] = False
            report["top_authors"] = []

        # 6. Source duplication level
        if dois_set:
            source_query = """
            MATCH (p:Paper)
            WHERE p.doi IN $dois
            RETURN COUNT(p) AS total,
                   COUNT(DISTINCT p.source) AS unique_sources
            """
            results, _ = db.cypher_query(source_query, {"dois": list(dois_set)})

            total = results[0][0] if results and results[0][0] is not None else 0
            unique_sources = results[0][1] if results and results[0][1] is not None else 0

            if total > 0:
                report["source_duplication_percentage"] = ((total - unique_sources) / total) * 100
            else:
                report["source_duplication_percentage"] = 0
        else:
            report["source_duplication_percentage"] = 0

        # 7. Missing data quality
        if dois_set:
            missing_data_query = """
            MATCH (p:Paper)
            WHERE p.doi IN $dois
            RETURN 
                COUNT(p) AS total,
                SUM(CASE WHEN p.title IS NULL THEN 1 ELSE 0 END) AS missing_title,
                SUM(CASE WHEN p.year IS NULL THEN 1 ELSE 0 END) AS missing_year,
                SUM(CASE WHEN p.abstract IS NULL THEN 1 ELSE 0 END) AS missing_abstract,
                SUM(CASE WHEN NOT EXISTS((p)-[:AUTHORED]->()) THEN 1 ELSE 0 END) AS missing_authors,
                SUM(CASE WHEN NOT EXISTS((p)-[:HAS_KEYWORD]->()) THEN 1 ELSE 0 END) AS missing_keywords
            """
            results, meta = db.cypher_query(missing_data_query, {"dois": list(dois_set)})
            columns = [col for col in meta]

            if results:
                record = dict(zip(columns, results[0]))
                total = record["total"] if record["total"] is not None else 0

                missing_data = {}
                for field in ["title", "year", "abstract", "authors", "keywords"]:
                    field_key = f"missing_{field}"
                    if total > 0 and record[field_key] is not None:
                        missing_data[field] = (record[field_key] / total) * 100
                    else:
                        missing_data[field] = 0

                report["missing_data_percentages"] = missing_data
            else:
                report["missing_data_percentages"] = {
                    "title": 0, "year": 0, "abstract": 0, "authors": 0, "keywords": 0
                }
        else:
            report["missing_data_percentages"] = {
                "title": 0, "year": 0, "abstract": 0, "authors": 0, "keywords": 0
            }

        # Overall quality assessment
        criteria_met = [
            report["meets_volume_threshold"],
            report["meets_doi_ref_threshold"],
            report["meets_temporal_threshold"],
            report["meets_geographic_threshold"],
            report["meets_author_threshold"]
        ]

        report["criteria_met_count"] = sum(1 for c in criteria_met if c)
        report["criteria_total_count"] = len(criteria_met)
        report["quality_score"] = (report["criteria_met_count"] / report["criteria_total_count"]) * 100 if report["criteria_total_count"] > 0 else 0

        return report

    def extract_co_citation_network(self, min_weight: int = 1) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Extrae la red de cocitación a partir de Neo4j, sólo con papers con relaciones.

        Args:
            min_weight: Minimum weight for co-citation relationships

        Returns:
            Tuple containing:
                - NetworkX graph representing the co-citation network
                - Dictionary containing quality report metrics
        """
        G = nx.Graph()

        # 1. Primero recuperamos solo las relaciones relevantes (edges)
        cocitation_query = """
        MATCH (p1:Paper)-[r:CO_CITED_WITH]-(p2:Paper)
        WHERE r.weight >= $min_weight
        RETURN p1.doi AS source, p2.doi AS target, r.weight AS weight
        """
        cocit_results, cocit_meta = db.cypher_query(cocitation_query, {"min_weight": min_weight})
        columns = [col for col in cocit_meta]
        # Guardar el set de DOIs involucrados en cocitación
        dois_set = set()
        edges = []
        for row in cocit_results:
            record = dict(zip(columns, row))
            if record['source'] and record['target'] and record['weight'] is not None:
                # Aseguramos que no haya None en weight
                edges.append((record['source'], record['target'], record['weight']))
                dois_set.add(record['source'])
                dois_set.add(record['target'])

        if dois_set:
            paper_query = """
            MATCH (p:Paper)
            WHERE p.doi IN $dois
            RETURN p.doi AS doi, p.title AS title, p.year AS year
            """
            paper_results, paper_meta = db.cypher_query(paper_query, {"dois": list(dois_set)})
            col_paper = [col for col in paper_meta]
            for row in paper_results:
                record = dict(zip(col_paper, row))
                # Limpiar/asegurar que fields no sean None (GraphML NO soporta None)
                doi = record['doi']
                title = record['title'] if record['title'] is not None else ""
                year = record['year'] if record['year'] is not None else -1
                G.add_node(doi, title=title, year=year)

        for source, target, weight in edges:
            G.add_edge(source, target, weight=weight)

        # Generate quality report
        quality_report = self.generate_quality_report(dois_set)

        return G, quality_report

    def extract_author_collaboration_network(self) -> nx.Graph:
        """Extract author collaboration network from Neo4j.

        Returns:
            NetworkX graph representing the author collaboration network
        """
        # Create an empty undirected graph
        G = nx.Graph()

        # Cypher query to get authors
        author_query = """
        MATCH (a:Author)
        RETURN a.name AS name, a.orcid AS orcid
        """

        # Cypher query to get collaboration relationships
        collaboration_query = """
        MATCH (a1:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)
        WHERE a1 <> a2
        WITH a1, a2, COUNT(p) AS collaboration_count
        RETURN a1.name AS source, a2.name AS target, collaboration_count AS weight
        """

        # Add nodes (authors)
        results, meta = db.cypher_query(author_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            G.add_node(
                record['name'],
                orcid=record['orcid']
            )

        # Add edges (collaboration relationships)
        results, meta = db.cypher_query(collaboration_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            G.add_edge(
                record['source'],
                record['target'],
                weight=record['weight']
            )

        return G

    def extract_institution_collaboration_network(self) -> nx.Graph:
        """Extract institution collaboration network from Neo4j.

        Returns:
            NetworkX graph representing the institution collaboration network
        """
        # Create an empty undirected graph
        G = nx.Graph()

        # Cypher query to get institutions
        institution_query = """
        MATCH (i:Institution)
        RETURN i.name AS name
        """

        # Cypher query to get collaboration relationships
        collaboration_query = """
        MATCH (i1:Institution)<-[:AFFILIATED_WITH]-(a1:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)-[:AFFILIATED_WITH]->(i2:Institution)
        WHERE i1 <> i2
        WITH i1, i2, COUNT(DISTINCT p) AS collaboration_count
        RETURN i1.name AS source, i2.name AS target, collaboration_count AS weight
        """

        # Add nodes (institutions)
        results, meta = db.cypher_query(institution_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            G.add_node(record['name'])

        # Add edges (collaboration relationships)
        results, meta = db.cypher_query(collaboration_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            G.add_edge(
                record['source'],
                record['target'],
                weight=record['weight']
            )

        return G

    def extract_keyword_co_occurrence_network(self) -> nx.Graph:
        """Extract keyword co-occurrence network from Neo4j.

        Returns:
            NetworkX graph representing the keyword co-occurrence network
        """
        # Create an empty undirected graph
        G = nx.Graph()

        # Cypher query to get keywords
        keyword_query = """
        MATCH (k:Keyword)
        RETURN k.name AS name
        """

        # Cypher query to get co-occurrence relationships
        cooccurrence_query = """
        MATCH (k1:Keyword)<-[:HAS_KEYWORD]-(p:Paper)-[:HAS_KEYWORD]->(k2:Keyword)
        WHERE k1 <> k2
        WITH k1, k2, COUNT(p) AS cooccurrence_count
        RETURN k1.name AS source, k2.name AS target, cooccurrence_count AS weight
        """

        # Add nodes (keywords)
        results, meta = db.cypher_query(keyword_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            G.add_node(record['name'])

        # Add edges (co-occurrence relationships)
        results, meta = db.cypher_query(cooccurrence_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            G.add_edge(
                record['source'],
                record['target'],
                weight=record['weight']
            )

        return G

    def export_graph_to_graphml(self, G: nx.Graph, filepath: str) -> None:
        """Export a NetworkX graph to GraphML format.

        Args:
            G: NetworkX graph to export
            filepath: Path to save the GraphML file
        """
        nx.write_graphml(G, filepath)

    def export_graph_to_csv(self, G: nx.Graph, nodes_filepath: str, edges_filepath: str) -> None:
        """Export a NetworkX graph to CSV format (nodes and edges files).

        Args:
            G: NetworkX graph to export
            nodes_filepath: Path to save the nodes CSV file
            edges_filepath: Path to save the edges CSV file
        """
        # Export nodes
        with open(nodes_filepath, 'w', encoding='utf-8') as f:
            # Write header
            f.write('id,')
            # Get all possible attributes from nodes
            attrs = set()
            for _, attr in G.nodes(data=True):
                attrs.update(attr.keys())
            f.write(','.join(attrs))
            f.write('\n')

            # Write node data
            for node, attr in G.nodes(data=True):
                f.write(f'"{node}",')
                f.write(','.join([f'"{attr.get(a, "")}"' for a in attrs]))
                f.write('\n')

        # Export edges
        with open(edges_filepath, 'w', encoding='utf-8') as f:
            # Write header
            f.write('source,target,')
            # Get all possible attributes from edges
            attrs = set()
            for _, _, attr in G.edges(data=True):
                attrs.update(attr.keys())
            f.write(','.join(attrs))
            f.write('\n')

            # Write edge data
            for source, target, attr in G.edges(data=True):
                f.write(f'"{source}","{target}",')
                f.write(','.join([f'"{attr.get(a, "")}"' for a in attrs]))
                f.write('\n')

    def calculate_network_metrics(self, G: nx.Graph) -> Dict[str, Any]:
        """Calculate various network metrics for a graph.

        Args:
            G: NetworkX graph to analyze

        Returns:
            Dictionary of network metrics
        """
        metrics = {}

        # Basic metrics
        metrics['node_count'] = G.number_of_nodes()
        metrics['edge_count'] = G.number_of_edges()
        metrics['density'] = nx.density(G)

        # Connected components
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            metrics['connected_components'] = len(components)
            metrics['largest_component_size'] = len(max(components, key=len))
        else:
            metrics['connected_components'] = 1
            metrics['largest_component_size'] = G.number_of_nodes()

        # Centrality measures (for the largest component to avoid errors)
        largest_cc = max(nx.connected_components(G), key=len)
        largest_subgraph = G.subgraph(largest_cc).copy()

        # Degree centrality
        degree_centrality = nx.degree_centrality(largest_subgraph)
        metrics['max_degree_centrality'] = max(degree_centrality.values()) if degree_centrality else 0
        metrics['avg_degree_centrality'] = sum(degree_centrality.values()) / len(degree_centrality) if degree_centrality else 0

        # Betweenness centrality (can be slow for large networks)
        if largest_subgraph.number_of_nodes() < 1000:  # Only calculate for smaller networks
            betweenness_centrality = nx.betweenness_centrality(largest_subgraph)
            metrics['max_betweenness_centrality'] = max(betweenness_centrality.values()) if betweenness_centrality else 0
            metrics['avg_betweenness_centrality'] = sum(betweenness_centrality.values()) / len(betweenness_centrality) if betweenness_centrality else 0

        # Clustering coefficient
        metrics['avg_clustering_coefficient'] = nx.average_clustering(largest_subgraph)

        return metrics

    def calculate_node_centrality_metrics(self, G: nx.Graph) -> pd.DataFrame:
        """Calculate centrality metrics for each node in the graph.

        Args:
            G: NetworkX graph to analyze

        Returns:
            DataFrame with node centrality metrics
        """
        # If graph is not connected, use the largest connected component
        if not nx.is_connected(G):
            largest_cc = max(nx.connected_components(G), key=len)
            subgraph = G.subgraph(largest_cc).copy()
        else:
            subgraph = G.copy()

        # Calculate centrality metrics
        print("Calculating degree centrality...")
        degree_centrality = nx.degree_centrality(subgraph)

        print("Calculating betweenness centrality...")
        betweenness_centrality = nx.betweenness_centrality(subgraph)

        print("Calculating closeness centrality...")
        closeness_centrality = nx.closeness_centrality(subgraph)

        # Create DataFrame
        centrality_df = pd.DataFrame({
            'node': list(degree_centrality.keys()),
            'degree_centrality': list(degree_centrality.values()),
            'betweenness_centrality': [betweenness_centrality.get(node, 0) for node in degree_centrality.keys()],
            'closeness_centrality': [closeness_centrality.get(node, 0) for node in degree_centrality.keys()]
        })

        return centrality_df

    def export_centrality_metrics(self, centrality_df: pd.DataFrame, filepath: str, format: str = 'csv') -> None:
        """Export centrality metrics to a file.

        Args:
            centrality_df: DataFrame with centrality metrics
            filepath: Path to save the file
            format: Format to save the file ('csv' or 'json')
        """
        if format.lower() == 'csv':
            centrality_df.to_csv(filepath, index=False)
        elif format.lower() == 'json':
            centrality_df.to_json(filepath, orient='records', indent=4)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'json'.")

        print(f"Centrality metrics exported to {filepath}")

    def add_community_to_centrality_metrics(self, centrality_df: pd.DataFrame, communities: Dict[Any, int]) -> pd.DataFrame:
        """Add community information to centrality metrics DataFrame.

        Args:
            centrality_df: DataFrame with centrality metrics
            communities: Dictionary mapping nodes to community IDs

        Returns:
            DataFrame with centrality metrics and community information
        """
        # Add community column
        centrality_df['community'] = centrality_df['node'].map(lambda x: communities.get(x, -1))
        return centrality_df

    def detect_communities(self, G: nx.Graph, algorithm: str = 'louvain') -> Tuple[Dict[Any, int], float]:
        """Detect communities in a graph using various algorithms.

        Args:
            G: NetworkX graph to analyze
            algorithm: Community detection algorithm to use ('louvain', 'label_propagation', 'greedy_modularity')

        Returns:
            Tuple of (community assignments, modularity score)
        """
        if algorithm == 'louvain':
            try:
                import community as community_louvain
                partition = community_louvain.best_partition(G)
                modularity = community_louvain.modularity(partition, G)
                return partition, modularity
            except ImportError:
                print("python-louvain package not installed. Falling back to greedy modularity.")
                algorithm = 'greedy_modularity'

        if algorithm == 'label_propagation':
            try:
                from networkx.algorithms import community
                communities = community.label_propagation_communities(G)
                # Convert to dictionary format
                partition = {}
                for i, comm in enumerate(communities):
                    for node in comm:
                        partition[node] = i
                # Calculate modularity
                modularity = community.modularity(G, communities)
                return partition, modularity
            except ImportError:
                print("NetworkX community algorithms not available. Falling back to greedy modularity.")
                algorithm = 'greedy_modularity'

        if algorithm == 'greedy_modularity':
            try:
                from networkx.algorithms import community
                communities = community.greedy_modularity_communities(G)
                # Convert to dictionary format
                partition = {}
                for i, comm in enumerate(communities):
                    for node in comm:
                        partition[node] = i
                # Calculate modularity
                modularity = community.modularity(G, communities)
                return partition, modularity
            except ImportError:
                print("NetworkX community algorithms not available.")
                return {node: 0 for node in G.nodes()}, 0.0

        # Default fallback
        return {node: 0 for node in G.nodes()}, 0.0

    def analyze_community_entity_distribution(self, G: nx.Graph, communities: Dict[Any, int], 
                                             entity_type: str = 'keyword') -> Dict[str, Any]:
        """Analyze the distribution of entities (keywords, authors, institutions) within each community.

        Args:
            G: NetworkX graph to analyze
            communities: Dictionary mapping nodes to community IDs
            entity_type: Type of entity to analyze ('keyword', 'author', 'institution')

        Returns:
            Dictionary with distribution analysis results
        """
        print(f"Analyzing {entity_type} distribution within communities...")

        # Group nodes by community
        community_nodes = {}
        for node, community_id in communities.items():
            if community_id not in community_nodes:
                community_nodes[community_id] = []
            community_nodes[community_id].append(node)

        # Get entity information based on entity_type
        entity_distributions = {}

        if entity_type == 'keyword':
            # For keyword network, the nodes themselves are keywords
            if 'coocurrencia_keywords' in str(list(G.nodes())[:1]):
                for community_id, nodes in community_nodes.items():
                    # Extract the actual keyword from the node ID (format: "coocurrencia_keywords_KEYWORD")
                    keywords = [node.split('_', 2)[2] if '_' in node else node for node in nodes]
                    entity_distributions[community_id] = self._count_entities(keywords)
            # For other networks, we need to query the database
            else:
                for community_id, nodes in community_nodes.items():
                    # For co-citation network, nodes are DOIs
                    if 'cocitacion' in str(list(G.nodes())[:1]):
                        dois = [node.split('_', 1)[1] if '_' in node else node for node in nodes]
                        keywords = self._get_keywords_for_papers(dois)
                    # For author network, nodes are author names
                    elif 'colaboracion_autores' in str(list(G.nodes())[:1]):
                        author_names = [node.split('_', 2)[2] if '_' in node else node for node in nodes]
                        keywords = self._get_keywords_for_authors(author_names)
                    else:
                        # For combined network or other networks
                        original_ids = []
                        for node in nodes:
                            attrs = G.nodes[node]
                            if 'id_original' in attrs:
                                original_ids.append(attrs['id_original'])
                            else:
                                original_ids.append(node)
                        keywords = self._get_keywords_for_papers(original_ids)

                    entity_distributions[community_id] = self._count_entities(keywords)

        elif entity_type == 'author':
            # For author network, the nodes themselves are authors
            if 'colaboracion_autores' in str(list(G.nodes())[:1]):
                for community_id, nodes in community_nodes.items():
                    # Extract the actual author name from the node ID
                    authors = [node.split('_', 2)[2] if '_' in node else node for node in nodes]
                    entity_distributions[community_id] = self._count_entities(authors)
            # For other networks, we need to query the database
            else:
                for community_id, nodes in community_nodes.items():
                    # For co-citation network, nodes are DOIs
                    if 'cocitacion' in str(list(G.nodes())[:1]):
                        dois = [node.split('_', 1)[1] if '_' in node else node for node in nodes]
                        authors = self._get_authors_for_papers(dois)
                    # For keyword network, nodes are keywords
                    elif 'coocurrencia_keywords' in str(list(G.nodes())[:1]):
                        keyword_names = [node.split('_', 2)[2] if '_' in node else node for node in nodes]
                        authors = self._get_authors_for_keywords(keyword_names)
                    else:
                        # For combined network or other networks
                        original_ids = []
                        for node in nodes:
                            attrs = G.nodes[node]
                            if 'id_original' in attrs:
                                original_ids.append(attrs['id_original'])
                            else:
                                original_ids.append(node)
                        authors = self._get_authors_for_papers(original_ids)

                    entity_distributions[community_id] = self._count_entities(authors)

        elif entity_type == 'institution':
            for community_id, nodes in community_nodes.items():
                # For co-citation network, nodes are DOIs
                if 'cocitacion' in str(list(G.nodes())[:1]):
                    dois = [node.split('_', 1)[1] if '_' in node else node for node in nodes]
                    institutions = self._get_institutions_for_papers(dois)
                # For author network, nodes are author names
                elif 'colaboracion_autores' in str(list(G.nodes())[:1]):
                    author_names = [node.split('_', 2)[2] if '_' in node else node for node in nodes]
                    institutions = self._get_institutions_for_authors(author_names)
                # For keyword network, nodes are keywords
                elif 'coocurrencia_keywords' in str(list(G.nodes())[:1]):
                    keyword_names = [node.split('_', 2)[2] if '_' in node else node for node in nodes]
                    institutions = self._get_institutions_for_keywords(keyword_names)
                else:
                    # For combined network or other networks
                    original_ids = []
                    for node in nodes:
                        attrs = G.nodes[node]
                        if 'id_original' in attrs:
                            original_ids.append(attrs['id_original'])
                        else:
                            original_ids.append(node)
                    institutions = self._get_institutions_for_papers(original_ids)

                entity_distributions[community_id] = self._count_entities(institutions)

        return entity_distributions

    def _count_entities(self, entities: list[str]) -> Dict[str, int]:
        """Count occurrences of entities in a list.

        Args:
            entities: list of entity names

        Returns:
            Dictionary mapping entity names to their counts
        """
        entity_counts = {}
        for entity in entities:
            if entity in entity_counts:
                entity_counts[entity] += 1
            else:
                entity_counts[entity] = 1

        # Sort by count in descending order
        return dict(sorted(entity_counts.items(), key=lambda x: x[1], reverse=True))

    def _get_keywords_for_papers(self, dois: list[str]) -> list[str]:
        """Get keywords for a list of papers.

        Args:
            dois: list of paper DOIs

        Returns:
            list of keywords
        """
        cypher_query = """
        MATCH (p:Paper)-[:HAS_KEYWORD]->(k:Keyword)
        WHERE p.doi IN $dois
        RETURN k.name AS keyword
        """
        results, meta = db.cypher_query(cypher_query, {"dois": dois})
        return [row[0] for row in results if row[0] is not None]

    def _get_authors_for_papers(self, dois: list[str]) -> list[str]:
        """Get authors for a list of papers.

        Args:
            dois: list of paper DOIs

        Returns:
            list of author names
        """
        cypher_query = """
        MATCH (p:Paper)<-[:AUTHORED]-(a:Author)
        WHERE p.doi IN $dois
        RETURN a.name AS author
        """
        results, meta = db.cypher_query(cypher_query, {"dois": dois})
        return [row[0] for row in results if row[0] is not None]

    def _get_institutions_for_papers(self, dois: list[str]) -> list[str]:
        """Get institutions for a list of papers.

        Args:
            dois: list of paper DOIs

        Returns:
            list of institution names
        """
        cypher_query = """
        MATCH (p:Paper)<-[:AUTHORED]-(a:Author)-[:AFFILIATED_WITH]->(i:Institution)
        WHERE p.doi IN $dois
        RETURN i.name AS institution
        """
        results, meta = db.cypher_query(cypher_query, {"dois": dois})
        return [row[0] for row in results if row[0] is not None]

    def _get_keywords_for_authors(self, author_names: list[str]) -> list[str]:
        """Get keywords for a list of authors.

        Args:
            author_names: list of author names

        Returns:
            list of keywords
        """
        cypher_query = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:HAS_KEYWORD]->(k:Keyword)
        WHERE a.name IN $author_names
        RETURN k.name AS keyword
        """
        results, meta = db.cypher_query(cypher_query, {"author_names": author_names})
        return [row[0] for row in results if row[0] is not None]

    def _get_authors_for_keywords(self, keyword_names: list[str]) -> list[str]:
        """Get authors for a list of keywords.

        Args:
            keyword_names: list of keyword names

        Returns:
            list of author names
        """
        cypher_query = """
        MATCH (k:Keyword)<-[:HAS_KEYWORD]-(p:Paper)<-[:AUTHORED]-(a:Author)
        WHERE k.name IN $keyword_names
        RETURN a.name AS author
        """
        results, meta = db.cypher_query(cypher_query, {"keyword_names": keyword_names})
        return [row[0] for row in results if row[0] is not None]

    def _get_institutions_for_authors(self, author_names: list[str]) -> list[str]:
        """Get institutions for a list of authors.

        Args:
            author_names: list of author names

        Returns:
            list of institution names
        """
        cypher_query = """
        MATCH (a:Author)-[:AFFILIATED_WITH]->(i:Institution)
        WHERE a.name IN $author_names
        RETURN i.name AS institution
        """
        results, meta = db.cypher_query(cypher_query, {"author_names": author_names})
        return [row[0] for row in results if row[0] is not None]

    def _get_institutions_for_keywords(self, keyword_names: list[str]) -> list[str]:
        """Get institutions for a list of keywords.

        Args:
            keyword_names: list of keyword names

        Returns:
            list of institution names
        """
        cypher_query = """
        MATCH (k:Keyword)<-[:HAS_KEYWORD]-(p:Paper)<-[:AUTHORED]-(a:Author)-[:AFFILIATED_WITH]->(i:Institution)
        WHERE k.name IN $keyword_names
        RETURN i.name AS institution
        """
        results, meta = db.cypher_query(cypher_query, {"keyword_names": keyword_names})
        return [row[0] for row in results if row[0] is not None]

    def visualize_entity_distribution(self, entity_distributions: Dict[int, Dict[str, int]], 
                                     entity_type: str, top_n: int = 10) -> Tuple[plt.Figure, Dict[int, pd.DataFrame]]:
        """Visualize the distribution of entities within communities.

        Args:
            entity_distributions: Dictionary mapping community IDs to entity count dictionaries
            entity_type: Type of entity ('keyword', 'author', 'institution')
            top_n: Number of top entities to include in the visualization

        Returns:
            Tuple of (matplotlib figure, dictionary of DataFrames with entity distributions)
        """
        import matplotlib.pyplot as plt
        import pandas as pd
        import seaborn as sns

        # Convert to DataFrames for easier manipulation
        community_dfs = {}
        for community_id, entity_counts in entity_distributions.items():
            df = pd.DataFrame(list(entity_counts.items()), columns=[entity_type, 'count'])
            df = df.sort_values('count', ascending=False).head(top_n)
            community_dfs[community_id] = df

        # Create a figure with subplots for each community (up to 9 communities)
        n_communities = min(len(community_dfs), 9)
        n_cols = min(3, n_communities)
        n_rows = (n_communities + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
        if n_communities == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        # Plot top entities for each community
        for i, (community_id, df) in enumerate(list(community_dfs.items())[:n_communities]):
            if df.empty:
                continue

            ax = axes[i]
            sns.barplot(x='count', y=entity_type, data=df, ax=ax)
            ax.set_title(f'Community {community_id}: Top {entity_type}s')
            ax.set_xlabel('Count')
            ax.set_ylabel(entity_type.capitalize())

        # Hide unused subplots
        for i in range(n_communities, len(axes)):
            axes[i].axis('off')

        plt.tight_layout()

        return fig, community_dfs

# Example usage
if __name__ == "__main__":
    analyzer = BibliometricNetworkAnalyzer()

    # Create co-citation relationships in Neo4j
    rel_count = analyzer.create_co_citation_relationships()
    print(f"Created {rel_count} CO_CITED_WITH relationships")

    # Extract co-citation network with report quality
    cocitation_network, quality_report = analyzer.extract_co_citation_network(min_weight=1)
    print(f"Co-citation network has {cocitation_network.number_of_nodes()} nodes and {cocitation_network.number_of_edges()} edges")

    # Display quality report
    print("\nQuality Report for Co-citation Network:")
    print(f"  Document count: {quality_report['document_count']} (Threshold: ≥200, Met: {quality_report['meets_volume_threshold']})")
    print(f"  DOI and references: {quality_report['doi_ref_percentage']:.2f}% (Threshold: ≥90%, Met: {quality_report['meets_doi_ref_threshold']})")
    print(f"  Temporal coverage: {quality_report['temporal_coverage']} (Threshold: 2000-2024, Met: {quality_report['meets_temporal_threshold']})")
    print(f"  Geographic diversity: {quality_report['country_count']} countries (Threshold: ≥5, Met: {quality_report['meets_geographic_threshold']})")
    print(f"  Key authors: {quality_report['recurring_authors']} recurring authors (Threshold: ≥10, Met: {quality_report['meets_author_threshold']})")
    print(f"  Source duplication: {quality_report['source_duplication_percentage']:.2f}%")

    # Display missing data percentages
    print("  Missing data percentages:")
    for field, percentage in quality_report['missing_data_percentages'].items():
        print(f"    {field}: {percentage:.2f}%")

    # Display overall quality score
    print(f"  Overall quality score: {quality_report['quality_score']:.2f}% ({quality_report['criteria_met_count']}/{quality_report['criteria_total_count']} criteria met)")

    # Display top authors if available
    if quality_report.get('top_authors'):
        print("  Top authors:")
        for author in quality_report['top_authors']:
            print(f"    {author['name']}: {author['paper_count']} papers")

    # Export the network
    os.makedirs("output", exist_ok=True)
    analyzer.export_graph_to_graphml(cocitation_network, "output/cocitation_network.graphml")
    analyzer.export_graph_to_csv(cocitation_network, "output/cocitation_nodes.csv", "output/cocitation_edges.csv")

    # Calculate network metrics
    metrics = analyzer.calculate_network_metrics(cocitation_network)
    print("\nNetwork metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Detect communities
    communities, modularity = analyzer.detect_communities(cocitation_network)
    print(f"Detected {len(set(communities.values()))} communities with modularity {modularity:.4f}")
