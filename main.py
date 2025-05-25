"""
Main script for bibliometric analysis of semiconductor supply chain.

This script ties together all components of the data pipeline:
1. Data ingestion from various sources
2. Enrichment of data using external APIs
3. Network extraction and analysis

Examples:
    # Run the full pipeline with default settings
    python main.py --mode full

    # Ingest data from a BibTeX file
    python main.py --mode ingest --input data/savedrecs.bib --file-type bibtex

    # Analyze a co-citation network with minimum weight of 2
    python main.py --mode analyze --network-type cocitation --min-weight 2

    # Enrich data using external APIs
    python main.py --mode enrich
"""

import os
import argparse
import logging
from typing import Dict, List, Any, Optional, Tuple

from bibtexparser.customization import author

from bib2graph.consigue_los_articulos import BibliometricDataLoader
from bib2graph.enriquecimiento import BibliometricDataEnricher
from bib2graph.analisis_red import BibliometricNetworkAnalyzer

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
    """Configuration class for Neo4j connection parameters.

    This class loads Neo4j connection parameters from environment variables
    with sensible defaults.

    Attributes:
        uri: The URI for connecting to Neo4j database.
        user: The username for Neo4j authentication.
        password: The password for Neo4j authentication.
    """

    def __init__(self) -> None:
        """Initialize Neo4j configuration with values from environment variables."""
        self.uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user: str = os.getenv("NEO4J_USER", "neo4j")
        self.password: Optional[str] = os.getenv("NEO4J_PASSWORD")  # No default for security

    def as_dict(self) -> Dict[str, Optional[str]]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary containing Neo4j connection parameters.
        """
        return {
            "uri": self.uri,
            "user": self.user,
            "password": self.password
        }


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    This function sets up the command-line interface for the bibliometric analysis
    pipeline, defining all available options and their default values.

    Returns:
        Parsed command line arguments.

    Examples:
        To run the full pipeline:
            python main.py --mode full

        To ingest data from a BibTeX file:
            python main.py --mode ingest --input data/savedrecs.bib --file-type bibtex

        To analyze a co-citation network:
            python main.py --mode analyze --network-type cocitation --min-weight 2
    """
    parser = argparse.ArgumentParser(
        description='Bibliometric analysis pipeline for semiconductor supply chain',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run the full pipeline with default settings
  python main.py --mode full

  # Ingest data from a BibTeX file
  python main.py --mode ingest --input data/savedrecs.bib --file-type bibtex

  # Analyze a co-citation network with minimum weight of 2
  python main.py --mode analyze --network-type cocitation --min-weight 2

  # Enrich data using external APIs
  python main.py --mode enrich
        """
    )

    # Main operation mode
    parser.add_argument('--mode', type=str,
                        choices=['ingest', 'enrich', 'create-relations', 'analyze', 'full'],
                        default='full', 
                        help='Operation mode (ingest data, enrich data, create network relations, analyze networks, or run full pipeline)')

    # Data ingestion options
    parser.add_argument('--input', type=str, 
                        help='Input file or directory containing bibliometric data')
    parser.add_argument('--file-type', type=str, 
                        choices=['csv', 'bibtex', 'json'],
                        help='Type of input file (required for ingestion if file type cannot be inferred from extension)')

    # Network analysis options
    parser.add_argument('--network-type', type=str,
                        choices=['cocitation', 'author', 'institution', 'keyword'],
                        default='cocitation', 
                        help='Type of network to extract and analyze')
    parser.add_argument('--min-weight', type=int, default=1,
                        help='Minimum weight for relationships in the network')
    parser.add_argument('--output-dir', type=str, default='output',
                        help='Directory for output files (will be created if it does not exist)')
    parser.add_argument('--community-algorithm', type=str,
                        choices=['louvain', 'label_propagation', 'greedy_modularity'],
                        default='louvain', 
                        help='Algorithm to use for community detection')

    # Neo4j connection options
    neo4j_config = Neo4jConfig()
    parser.add_argument('--neo4j-uri', type=str, default=neo4j_config.uri,
                        help='Neo4j connection URI (default: from environment or localhost)')
    parser.add_argument('--neo4j-user', type=str, default=neo4j_config.user,
                        help='Neo4j username (default: from environment or "neo4j")')
    parser.add_argument('--neo4j-password', type=str, default=neo4j_config.password,
                        help='Neo4j password (default: from environment)')

    return parser.parse_args()


def ingest_data(
    input_path: Optional[str], 
    file_type: Optional[str], 
    neo4j_uri: str, 
    neo4j_user: str, 
    neo4j_password: Optional[str]
) -> None:
    """Ingest data from various sources into Neo4j.

    This function loads bibliometric data from files or directories into a Neo4j database.
    It supports CSV, BibTeX, and JSON file formats.

    Args:
        input_path: Path to the input file or directory.
        file_type: Type of input file ('csv', 'bibtex', or 'json'). If None, will try to infer from file extension.
        neo4j_uri: URI for connecting to Neo4j database.
        neo4j_user: Username for Neo4j authentication.
        neo4j_password: Password for Neo4j authentication.

    Raises:
        ValueError: If no input path is specified.
        FileNotFoundError: If the input path does not exist.

    Returns:
        None
    """
    logger.info("Starting data ingestion phase")

    # Initialize data loader
    loader = BibliometricDataLoader(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    if not input_path:
        logger.error("No input file or directory specified")
        raise ValueError("Input required for ingestion")

    if not os.path.exists(input_path):
        logger.error(f"Input path does not exist: {input_path}")
        raise FileNotFoundError(input_path)

    if os.path.isdir(input_path):
        logger.info(f"Processing directory: {input_path}")
        loader.process_directory(input_path)
        logger.info("Data ingestion phase completed")
        return

    if os.path.isfile(input_path):
        # Determine file type
        current_file_type = file_type
        if not current_file_type:
            ext = os.path.splitext(input_path)[1].lower()
            current_file_type = {
                '.bibtex': 'bibtex',
                '.bib': 'bibtex',
            }.get(ext)
            if not current_file_type:
                logger.error(f"Could not infer file type from extension: {ext}")
                raise NotImplementedError(f"Unsupported file type: {ext}")

        logger.info(f"Processing file: {input_path} (type: {current_file_type})")
        loader.process_file(input_path, current_file_type)
        logger.info("Data ingestion phase completed")
        return



def enrich_data(
    neo4j_uri: str, 
    neo4j_user: str, 
    neo4j_password: Optional[str]
) -> None:
    """Enrich data in Neo4j using external APIs.

    This function enriches bibliometric data stored in Neo4j by fetching additional
    information from external APIs like Semantic Scholar, Crossref, and Scopus.

    Args:
        neo4j_uri: URI for connecting to Neo4j database.
        neo4j_user: Username for Neo4j authentication.
        neo4j_password: Password for Neo4j authentication.

    Returns:
        None
    """
    logger.info("Starting data enrichment phase")

    # Initialize data enricher
    enricher = BibliometricDataEnricher(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    # Enrich all papers
    enricher.enrich_all_papers()

    logger.info("Data enrichment phase completed")


def create_network_relations(
    analyzer: BibliometricNetworkAnalyzer,
    network_type: str
) -> None:
    """Create relations necessary for extracting networks.

    This function creates the necessary relationships in Neo4j for the specified
    network type. These relationships are used later for network extraction and analysis.

    Args:
        analyzer: Initialized BibliometricNetworkAnalyzer instance.
        network_type: Type of network to create relations for ('cocitation', 'author', etc.).

    Returns:
        None
    """
    logger.info("Creating network relations in Neo4j (preprocessing)")

    if network_type == 'cocitation':
        rel_count = analyzer.create_co_citation_relationships()
        logger.info(f"Created {rel_count} CO_CITED_WITH relationships")
    # You can add more cases based on network type
    # elif network_type == 'author':
    #     ...

    logger.info("Network relations created in Neo4j")


def extract_and_analyze_network(
    analyzer: BibliometricNetworkAnalyzer,
    network_type: str,
    min_weight: int,
    output_dir: str,
    community_algorithm: str
) -> None:
    """Extract and analyze networks from Neo4j.

    Note: This function is similar to analyze_network() and might be consolidated
    in a future refactoring. The main difference is that analyze_network() also
    creates the necessary relationships before extracting the network.

    This function extracts the specified network type from Neo4j, analyzes it,
    calculates metrics, detects communities, and exports the results to files.

    Args:
        analyzer: Initialized BibliometricNetworkAnalyzer instance.
        network_type: Type of network to extract ('cocitation', 'author', 'institution', 'keyword').
        min_weight: Minimum weight for relationships in the network.
        output_dir: Directory for output files.
        community_algorithm: Algorithm to use for community detection.

    Returns:
        None
    """
    logger.info("Starting network extraction and analysis phase")

    os.makedirs(output_dir, exist_ok=True)

    # Extract the requested network
    if network_type == 'cocitation':
        network_result = analyzer.extract_co_citation_network(min_weight=min_weight)
        # Handle the new return format (network, quality_report)
        if isinstance(network_result, tuple) and len(network_result) == 2:
            network, quality_report = network_result
            # Log quality report
            logger.info("Quality Report for Co-citation Network:")
            logger.info(f"  Document count: {quality_report['document_count']} (Threshold: ≥200, Met: {quality_report['meets_volume_threshold']})")
            logger.info(f"  DOI and references: {quality_report['doi_ref_percentage']:.2f}% (Threshold: ≥90%, Met: {quality_report['meets_doi_ref_threshold']})")
            logger.info(f"  Temporal coverage: {quality_report['temporal_coverage']} (Threshold: 2000-2024, Met: {quality_report['meets_temporal_threshold']})")
            logger.info(f"  Geographic diversity: {quality_report['country_count']} countries (Threshold: ≥5, Met: {quality_report['meets_geographic_threshold']})")
            logger.info(f"  Key authors: {quality_report['recurring_authors']} recurring authors (Threshold: ≥10, Met: {quality_report['meets_author_threshold']})")
            logger.info(f"  Source duplication: {quality_report['source_duplication_percentage']:.2f}%")

            # Log missing data percentages
            logger.info("  Missing data percentages:")
            for field, percentage in quality_report['missing_data_percentages'].items():
                logger.info(f"    {field}: {percentage:.2f}%")

            # Log overall quality score
            logger.info(f"  Overall quality score: {quality_report['quality_score']:.2f}% ({quality_report['criteria_met_count']}/{quality_report['criteria_total_count']} criteria met)")

            # Log top authors if available
            if quality_report.get('top_authors'):
                logger.info("  Top authors:")
                for author in quality_report['top_authors']:
                    logger.info(f"    {author['name']}: {author['paper_count']} papers")
        else:
            # Fallback for backward compatibility
            network = network_result
        network_name = "cocitation"
    elif network_type == 'author':
        network = analyzer.extract_author_collaboration_network()
        network_name = "author_collaboration"
    elif network_type == 'institution':
        network = analyzer.extract_institution_collaboration_network()
        network_name = "institution_collaboration"
    elif network_type == 'keyword':
        network = analyzer.extract_keyword_co_occurrence_network()
        network_name = "keyword_cooccurrence"

    logger.info(
        f"{network_type} network has {network.number_of_nodes()} nodes and {network.number_of_edges()} edges")

    # Export results
    graphml_path = os.path.join(output_dir, f"{network_name}_network.graphml")
    nodes_path = os.path.join(output_dir, f"{network_name}_nodes.csv")
    edges_path = os.path.join(output_dir, f"{network_name}_edges.csv")

    analyzer.export_graph_to_graphml(network, graphml_path)
    analyzer.export_graph_to_csv(network, nodes_path, edges_path)

    logger.info(f"Exported network to {graphml_path}, {nodes_path}, and {edges_path}")

    # Calculate network metrics
    metrics = analyzer.calculate_network_metrics(network)
    logger.info("Network metrics:")
    for key, value in metrics.items():
        logger.info(f"  {key}: {value}")

    # Detect communities
    communities, modularity = analyzer.detect_communities(network, algorithm=community_algorithm)
    logger.info(f"Detected {len(set(communities.values()))} communities with modularity {modularity:.4f}")

    logger.info("Network extraction and analysis phase completed")


def analyze_network(
    analyzer: BibliometricNetworkAnalyzer,
    network_type: str,
    min_weight: int,
    output_dir: str,
    community_algorithm: str
) -> None:
    """Extract and analyze networks from Neo4j.

    This function creates necessary relationships, extracts the specified network type,
    analyzes it, calculates metrics, detects communities, and exports the results to files.

    Args:
        analyzer: Initialized BibliometricNetworkAnalyzer instance.
        network_type: Type of network to extract ('cocitation', 'author', 'institution', 'keyword').
        min_weight: Minimum weight for relationships in the network.
        output_dir: Directory for output files.
        community_algorithm: Algorithm to use for community detection.

    Returns:
        None
    """
    logger.info("Starting network analysis phase")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create necessary relationships if needed
    if network_type == 'cocitation':
        rel_count = analyzer.create_co_citation_relationships()
        logger.info(f"Created {rel_count} CO_CITED_WITH relationships")
    #if network_type == 'author':
    #    # complete
    #    author_count = analyzer.create_author_collaboration_network

    # Extract the requested network
    if network_type == 'cocitation':
        network_result = analyzer.extract_co_citation_network(min_weight=min_weight)
        # Handle the new return format (network, quality_report)
        if isinstance(network_result, tuple) and len(network_result) == 2:
            network, quality_report = network_result
            # Log quality report
            logger.info("Quality Report for Co-citation Network:")
            logger.info(f"  Document count: {quality_report['document_count']} (Threshold: ≥200, Met: {quality_report['meets_volume_threshold']})")
            logger.info(f"  DOI and references: {quality_report['doi_ref_percentage']:.2f}% (Threshold: ≥90%, Met: {quality_report['meets_doi_ref_threshold']})")
            logger.info(f"  Temporal coverage: {quality_report['temporal_coverage']} (Threshold: 2000-2024, Met: {quality_report['meets_temporal_threshold']})")
            logger.info(f"  Geographic diversity: {quality_report['country_count']} countries (Threshold: ≥5, Met: {quality_report['meets_geographic_threshold']})")
            logger.info(f"  Key authors: {quality_report['recurring_authors']} recurring authors (Threshold: ≥10, Met: {quality_report['meets_author_threshold']})")
            logger.info(f"  Source duplication: {quality_report['source_duplication_percentage']:.2f}%")

            # Log missing data percentages
            logger.info("  Missing data percentages:")
            for field, percentage in quality_report['missing_data_percentages'].items():
                logger.info(f"    {field}: {percentage:.2f}%")

            # Log overall quality score
            logger.info(f"  Overall quality score: {quality_report['quality_score']:.2f}% ({quality_report['criteria_met_count']}/{quality_report['criteria_total_count']} criteria met)")

            # Log top authors if available
            if quality_report.get('top_authors'):
                logger.info("  Top authors:")
                for author in quality_report['top_authors']:
                    logger.info(f"    {author['name']}: {author['paper_count']} papers")
        else:
            # Fallback for backward compatibility
            network = network_result
        network_name = "cocitation"
    elif network_type == 'author':
        network = analyzer.extract_author_collaboration_network()
        network_name = "author_collaboration"
    elif network_type == 'institution':
        network = analyzer.extract_institution_collaboration_network()  # TODO: No se ha creado institution_collaboration
        network_name = "institution_collaboration"
    elif network_type == 'keyword':
        network = analyzer.extract_keyword_co_occurrence_network()
        network_name = "keyword_cooccurrence"

    logger.info(
        f"{network_type} network has {network.number_of_nodes()} nodes and {network.number_of_edges()} edges")

    # Export the network
    graphml_path = os.path.join(output_dir, f"{network_name}_network.graphml")
    nodes_path = os.path.join(output_dir, f"{network_name}_nodes.csv")
    edges_path = os.path.join(output_dir, f"{network_name}_edges.csv")

    analyzer.export_graph_to_graphml(network, graphml_path)
    analyzer.export_graph_to_csv(network, nodes_path, edges_path)

    logger.info(f"Exported network to {graphml_path}, {nodes_path}, and {edges_path}")

    # Calculate network metrics
    metrics = analyzer.calculate_network_metrics(network)
    logger.info("Network metrics:")
    for key, value in metrics.items():
        logger.info(f"  {key}: {value}")

    # Detect communities
    communities, modularity = analyzer.detect_communities(network, algorithm=community_algorithm)
    logger.info(f"Detected {len(set(communities.values()))} communities with modularity {modularity:.4f}")

    logger.info("Network analysis phase completed")


def run_full_pipeline(
    input_path: Optional[str],
    file_type: Optional[str],
    network_type: str,
    min_weight: int,
    output_dir: str,
    community_algorithm: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: Optional[str]
) -> None:
    """Run the full bibliometric analysis pipeline.

    This function runs the complete pipeline: data ingestion, data enrichment,
    and network analysis in sequence.

    Args:
        input_path: Path to the input file or directory.
        file_type: Type of input file ('csv', 'bibtex', or 'json').
        network_type: Type of network to extract.
        min_weight: Minimum weight for relationships in the network.
        output_dir: Directory for output files.
        community_algorithm: Algorithm to use for community detection.
        neo4j_uri: URI for connecting to Neo4j database.
        neo4j_user: Username for Neo4j authentication.
        neo4j_password: Password for Neo4j authentication.

    Returns:
        None
    """
    # Initialize the network analyzer once and reuse it
    analyzer = BibliometricNetworkAnalyzer(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    # Run each step of the pipeline
    ingest_data(input_path, file_type, neo4j_uri, neo4j_user, neo4j_password)
    enrich_data(neo4j_uri, neo4j_user, neo4j_password)
    analyze_network(analyzer, network_type, min_weight, output_dir, community_algorithm)

    logger.info("Bibliometric analysis pipeline completed")


def main() -> None:
    """Main entry point for the application.

    This function parses command line arguments and runs the appropriate
    pipeline component based on the specified mode.

    Returns:
        None
    """
    args = parse_arguments()

    logger.info("Starting bibliometric analysis pipeline")

    try:
        # Initialize the network analyzer once if needed
        if args.mode in ['create-relations', 'analyze', 'full']:
            analyzer = BibliometricNetworkAnalyzer(
                uri=args.neo4j_uri,
                user=args.neo4j_user,
                password=args.neo4j_password
            )

        # Run the appropriate pipeline component
        if args.mode == 'ingest':
            ingest_data(
                input_path=args.input,
                file_type=args.file_type,
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password
            )
        elif args.mode == 'enrich':
            enrich_data(
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password
            )
        elif args.mode == 'create-relations':
            create_network_relations(
                analyzer=analyzer,
                network_type=args.network_type
            )
        elif args.mode == 'analyze':
            # We have two similar functions: extract_and_analyze_network and analyze_network
            # For consistency with the CLI documentation, we use analyze_network
            analyze_network(
                analyzer=analyzer,
                network_type=args.network_type,
                min_weight=args.min_weight,
                output_dir=args.output_dir,
                community_algorithm=args.community_algorithm
            )
        elif args.mode == 'full':
            run_full_pipeline(
                input_path=args.input,
                file_type=args.file_type,
                network_type=args.network_type,
                min_weight=args.min_weight,
                output_dir=args.output_dir,
                community_algorithm=args.community_algorithm,
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password
            )
    except Exception as e:
        logger.exception(f"Error in pipeline execution: {e}")


if __name__ == "__main__":
    main()
