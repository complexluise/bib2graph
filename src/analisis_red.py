"""
Network analysis module for bibliometric analysis of semiconductor supply chain.

This module provides functionality for extracting co-citation networks from the Neo4j database
and exporting them for analysis in external tools.
"""

import os
import networkx as nx
from neomodel import db, config
from typing import Dict, List, Any, Optional, Tuple
from src.models import Paper, Author, Keyword, Institution, Funder

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
        # Cypher query to create CO_CITED_WITH relationships
        cypher_query = """
        MATCH (p1:Paper)-[:REFERENCES]->(ref:Paper)<-[:REFERENCES]-(p2:Paper)
        WHERE p1 <> p2
        WITH p1, p2, COUNT(ref) AS shared_refs
        WHERE shared_refs > 0
        MERGE (p1)-[r:CO_CITED_WITH]-(p2)
        ON CREATE SET r.weight = shared_refs
        RETURN COUNT(r) AS relationship_count
        """

        results, meta = db.cypher_query(cypher_query)
        return results[0][0] if results else 0

    def extract_co_citation_network(self, min_weight: int = 1) -> nx.Graph:
        """Extract co-citation network from Neo4j.

        Args:
            min_weight: Minimum weight of CO_CITED_WITH relationships to include

        Returns:
            NetworkX graph representing the co-citation network
        """
        # Create an empty undirected graph
        G = nx.Graph()

        # Cypher query to get papers
        paper_query = """
        MATCH (p:Paper)
        RETURN p.doi AS doi, p.title AS title, p.year AS year
        """

        # Cypher query to get co-citation relationships
        cocitation_query = """
        MATCH (p1:Paper)-[r:CO_CITED_WITH]-(p2:Paper)
        WHERE r.weight >= $min_weight
        RETURN p1.doi AS source, p2.doi AS target, r.weight AS weight
        """

        # Add nodes (papers)
        results, meta = db.cypher_query(paper_query)
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            if record['doi']:  # Only add papers with DOIs
                G.add_node(
                    record['doi'],
                    title=record['title'],
                    year=record['year']
                )

        # Add edges (co-citation relationships)
        results, meta = db.cypher_query(cocitation_query, {"min_weight": min_weight})
        # Convert results to dictionary format
        columns = [col for col in meta]
        for row in results:
            record = dict(zip(columns, row))
            if record['source'] and record['target']:  # Only add relationships with valid DOIs
                G.add_edge(
                    record['source'],
                    record['target'],
                    weight=record['weight']
                )

        return G

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

# Example usage
if __name__ == "__main__":
    analyzer = BibliometricNetworkAnalyzer()

    # Create co-citation relationships in Neo4j
    rel_count = analyzer.create_co_citation_relationships()
    print(f"Created {rel_count} CO_CITED_WITH relationships")

    # Extract co-citation network
    cocitation_network = analyzer.extract_co_citation_network(min_weight=1)
    print(f"Co-citation network has {cocitation_network.number_of_nodes()} nodes and {cocitation_network.number_of_edges()} edges")

    # Export the network
    os.makedirs("output", exist_ok=True)
    analyzer.export_graph_to_graphml(cocitation_network, "output/cocitation_network.graphml")
    analyzer.export_graph_to_csv(cocitation_network, "output/cocitation_nodes.csv", "output/cocitation_edges.csv")

    # Calculate network metrics
    metrics = analyzer.calculate_network_metrics(cocitation_network)
    print("Network metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    # Detect communities
    communities, modularity = analyzer.detect_communities(cocitation_network)
    print(f"Detected {len(set(communities.values()))} communities with modularity {modularity:.4f}")
