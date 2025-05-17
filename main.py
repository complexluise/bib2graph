"""
Main script for bibliometric analysis of semiconductor supply chain.

This script ties together all components of the data pipeline:
1. Data ingestion from various sources
2. Enrichment of data using external APIs
3. Network extraction and analysis
"""

import os
import argparse
import logging
from src.consigue_los_articulos import BibliometricDataLoader
from src.enriquecimiento import BibliometricDataEnricher
from src.analisis_red import BibliometricNetworkAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bibliometria.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Neo4jConfig:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")  # Usa un valor por defecto solo si es seguro

    def as_dict(self):
        return {
            "uri": self.uri,
            "user": self.user,
            "password": self.password
        }


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Bibliometric analysis pipeline for semiconductor supply chain')
    
    # Main operation mode
    parser.add_argument('--mode', type=str, choices=['ingest', 'enrich', 'analyze', 'full'], 
                        default='full', help='Operation mode')
    
    # Data ingestion options
    parser.add_argument('--input', type=str, help='Input file or directory')
    parser.add_argument('--file-type', type=str, choices=['csv', 'bibtex', 'json'], 
                        help='Type of input file')
    
    # Network analysis options
    parser.add_argument('--network-type', type=str, 
                        choices=['cocitation', 'author', 'institution', 'keyword'], 
                        default='cocitation', help='Type of network to extract')
    parser.add_argument('--min-weight', type=int, default=1, 
                        help='Minimum weight for relationships')
    parser.add_argument('--output-dir', type=str, default='output', 
                        help='Directory for output files')
    parser.add_argument('--community-algorithm', type=str, 
                        choices=['louvain', 'label_propagation', 'greedy_modularity'], 
                        default='louvain', help='Community detection algorithm')
    neo4j_config = Neo4jConfig()
    # Neo4j connection options
    parser.add_argument('--neo4j-uri', type=str, default=neo4j_config.uri,
                        help='Neo4j connection URI')
    parser.add_argument('--neo4j-user', type=str, default=neo4j_config.user,
                        help='Neo4j username')
    parser.add_argument('--neo4j-password', type=str, default=neo4j_config.password,
                        help='Neo4j password')
    
    return parser.parse_args()

def ingest_data(args):
    """Ingest data from various sources into Neo4j."""
    logger.info("Starting data ingestion phase")
    
    # Initialize data loader
    loader = BibliometricDataLoader(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password
    )
    
    # Process input file or directory
    if args.input:
        if os.path.isdir(args.input):
            logger.info(f"Processing directory: {args.input}")
            loader.process_directory(args.input)
        elif os.path.isfile(args.input):
            if not args.file_type:
                # Try to infer file type from extension
                ext = os.path.splitext(args.input)[1].lower()
                if ext == '.csv':
                    file_type = 'csv'
                elif ext in ['.bib', '.bibtex']:
                    file_type = 'bibtex'
                elif ext == '.json':
                    file_type = 'json'
                else:
                    logger.error(f"Could not infer file type from extension: {ext}")
                    return
            else:
                file_type = args.file_type
                
            logger.info(f"Processing file: {args.input} (type: {file_type})")
            loader.process_file(args.input, file_type)
        else:
            logger.error(f"Input path does not exist: {args.input}")
    else:
        # Default behavior: process the sample data file if it exists
        default_file = "data/Citación semiconductores comercio internacional.txt"
        if os.path.exists(default_file):
            logger.info(f"Processing default file: {default_file}")
            loader.process_file(default_file, 'csv')
        else:
            logger.error("No input specified and default file not found")
    
    logger.info("Data ingestion phase completed")

def enrich_data(args):
    """Enrich data in Neo4j using external APIs."""
    logger.info("Starting data enrichment phase")
    
    # Initialize data enricher
    enricher = BibliometricDataEnricher(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password
    )
    
    # Enrich all papers
    enricher.enrich_all_papers()
    
    logger.info("Data enrichment phase completed")

def analyze_network(args):
    """Extract and analyze networks from Neo4j."""
    logger.info("Starting network analysis phase")
    
    # Initialize network analyzer
    analyzer = BibliometricNetworkAnalyzer(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password
    )
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create co-citation relationships if needed
    if args.network_type == 'cocitation':
        rel_count = analyzer.create_co_citation_relationships()
        logger.info(f"Created {rel_count} CO_CITED_WITH relationships")
    
    # Extract the requested network
    if args.network_type == 'cocitation':
        network = analyzer.extract_co_citation_network(min_weight=args.min_weight)
        network_name = "cocitation"
    elif args.network_type == 'author':
        network = analyzer.extract_author_collaboration_network()
        network_name = "author_collaboration"
    elif args.network_type == 'institution':
        network = analyzer.extract_institution_collaboration_network()
        network_name = "institution_collaboration"
    elif args.network_type == 'keyword':
        network = analyzer.extract_keyword_co_occurrence_network()
        network_name = "keyword_cooccurrence"
    
    logger.info(f"{args.network_type} network has {network.number_of_nodes()} nodes and {network.number_of_edges()} edges")
    
    # Export the network
    graphml_path = os.path.join(args.output_dir, f"{network_name}_network.graphml")
    nodes_path = os.path.join(args.output_dir, f"{network_name}_nodes.csv")
    edges_path = os.path.join(args.output_dir, f"{network_name}_edges.csv")
    
    analyzer.export_graph_to_graphml(network, graphml_path)
    analyzer.export_graph_to_csv(network, nodes_path, edges_path)
    
    logger.info(f"Exported network to {graphml_path}, {nodes_path}, and {edges_path}")
    
    # Calculate network metrics
    metrics = analyzer.calculate_network_metrics(network)
    logger.info("Network metrics:")
    for key, value in metrics.items():
        logger.info(f"  {key}: {value}")
    
    # Detect communities
    communities, modularity = analyzer.detect_communities(network, algorithm=args.community_algorithm)
    logger.info(f"Detected {len(set(communities.values()))} communities with modularity {modularity:.4f}")
    
    logger.info("Network analysis phase completed")

def run_full_pipeline(args):
    """Run the full pipeline: ingest, enrich, and analyze."""
    ingest_data(args)
    enrich_data(args)
    analyze_network(args)

    logger.info("Bibliometric analysis pipeline completed")

def main():
    """Main entry point for the application."""
    args = parse_arguments()
    
    logger.info("Starting bibliometric analysis pipeline")
    
    try:
        if args.mode == 'ingest':
            ingest_data(args)
        elif args.mode == 'enrich':
            enrich_data(args)
        elif args.mode == 'analyze':
            analyze_network(args)
        elif args.mode == 'full':
             run_full_pipeline(args)
    except Exception as e:
        logger.exception(f"Error in pipeline execution: {e}")


if __name__ == "__main__":
    main()
