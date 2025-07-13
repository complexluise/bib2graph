"""
Script principal para el análisis bibliométrico de la cadena de suministro de semiconductores.

Este script une todos los componentes del pipeline de datos:
1. Ingesta de datos de varias fuentes
2. Enriquecimiento de datos usando APIs externas
3. Extracción y análisis de redes

Ejemplos:
    # Ejecutar el pipeline completo con configuración predeterminada
    python main.py --mode full

    # Ingestar datos desde un archivo BibTeX
    python main.py --mode ingest --input data/savedrecs.bib --file-type bibtex

    # Analizar una red de co-citación con peso mínimo de 2
    python main.py --mode analyze --network-type cocitation --min-weight 2

    # Enriquecer datos usando APIs externas
    python main.py --mode enrich

    # Ejecutar en modo simulación (sin efectos en la base de datos)
    python main.py --mode full --dry-run

    # Mostrar la versión del paquete
    python main.py --version
"""

import os
import argparse
import logging
import sys
from typing import Dict, Optional
from tqdm import tqdm

from bib2graph import BibliometricDataLoader
from bib2graph.enriquecimiento import BibliometricDataEnricher
from bib2graph.analisis_red import BibliometricNetworkAnalyzer
from bib2graph.config import (
    Neo4jConfig, NETWORK_TYPES, COMMUNITY_ALGORITHMS, SUPPORTED_FILE_TYPES,
    DEFAULT_MIN_WEIGHT, DEFAULT_OUTPUT_DIR, DEFAULT_COMMUNITY_ALGORITHM, 
    DEFAULT_NETWORK_TYPE, VERSION
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("../bibliometria.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Analiza los argumentos de la línea de comandos.

    Esta función configura la interfaz de línea de comandos para el pipeline de análisis
    bibliométrico, definiendo todas las opciones disponibles y sus valores predeterminados.

    Returns:
        Argumentos de línea de comandos analizados.

    Examples:
        Para ejecutar el pipeline completo:
            python main.py --mode full

        Para ingestar datos desde un archivo BibTeX:
            python main.py --mode ingest --input data/savedrecs.bib --file-type bibtex

        Para analizar una red de co-citación:
            python main.py --mode analyze --network-type cocitation --min-weight 2

        Para ejecutar en modo simulación (sin efectos en la base de datos):
            python main.py --mode full --dry-run

        Para mostrar la versión del paquete:
            python main.py --version
    """
    parser = argparse.ArgumentParser(
        description='Pipeline de análisis bibliométrico para la cadena de suministro de semiconductores',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Ejecutar el pipeline completo con configuración predeterminada
  python main.py --mode full

  # Ingestar datos desde un archivo BibTeX
  python main.py --mode ingest --input data/savedrecs.bib --file-type bibtex

  # Analizar una red de co-citación con peso mínimo de 2
  python main.py --mode analyze --network-type cocitation --min-weight 2

  # Enriquecer datos usando APIs externas
  python main.py --mode enrich

  # Ejecutar en modo simulación (sin efectos en la base de datos)
  python main.py --mode full --dry-run

  # Mostrar la versión del paquete
  python main.py --version
        """
    )

    # Version flag
    parser.add_argument('--version', action='store_true',
                        help='Muestra la versión del paquete y sale')

    # Main operation mode
    parser.add_argument('--mode', type=str,
                        choices=['ingest', 'enrich', 'create-relations', 'analyze', 'full'],
                        default='full', 
                        help='Modo de operación (ingestar datos, enriquecer datos, crear relaciones de red, analizar redes, o ejecutar pipeline completo)')

    # Data ingestion options
    parser.add_argument('--input', type=str, 
                        help='Archivo o directorio de entrada que contiene datos bibliométricos')
    parser.add_argument('--file-type', type=str, 
                        choices=SUPPORTED_FILE_TYPES,
                        help='Tipo de archivo de entrada (requerido para ingesta si el tipo no puede inferirse de la extensión)')

    # Network analysis options
    parser.add_argument('--network-type', type=str,
                        choices=list(NETWORK_TYPES.keys()),
                        default=DEFAULT_NETWORK_TYPE, 
                        help='Tipo de red a extraer y analizar')
    parser.add_argument('--min-weight', type=int, default=DEFAULT_MIN_WEIGHT,
                        help='Peso mínimo para relaciones en la red')
    parser.add_argument('--output-dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help='Directorio para archivos de salida (se creará si no existe)')
    parser.add_argument('--community-algorithm', type=str,
                        choices=COMMUNITY_ALGORITHMS,
                        default=DEFAULT_COMMUNITY_ALGORITHM, 
                        help='Algoritmo a usar para detección de comunidades')

    # Dry run flag
    parser.add_argument('--dry-run', action='store_true',
                        help='Ejecuta en modo simulación sin realizar cambios en la base de datos')

    # Neo4j connection options
    neo4j_config = Neo4jConfig()
    parser.add_argument('--neo4j-uri', type=str, default=neo4j_config.uri,
                        help='URI de conexión a Neo4j (predeterminado: desde entorno o localhost)')
    parser.add_argument('--neo4j-user', type=str, default=neo4j_config.user,
                        help='Nombre de usuario de Neo4j (predeterminado: desde entorno o "neo4j")')
    parser.add_argument('--neo4j-password', type=str, default=neo4j_config.password,
                        help='Contraseña de Neo4j (predeterminado: desde entorno)')

    return parser.parse_args()


def ingest_data(
    input_path: Optional[str], 
    file_type: Optional[str], 
    neo4j_uri: str, 
    neo4j_user: str, 
    neo4j_password: Optional[str],
    dry_run: bool = False
) -> None:
    """Ingesta datos de varias fuentes en Neo4j.

    Esta función carga datos bibliométricos desde archivos o directorios en una base de datos Neo4j.
    Soporta formatos de archivo BibTeX.

    Args:
        input_path: Ruta al archivo o directorio de entrada.
        file_type: Tipo de archivo de entrada ('bibtex'). Si es None, intentará inferir desde la extensión.
        neo4j_uri: URI para conectarse a la base de datos Neo4j.
        neo4j_user: Nombre de usuario para autenticación de Neo4j.
        neo4j_password: Contraseña para autenticación de Neo4j.
        dry_run: Si es True, simula la operación sin realizar cambios en la base de datos.

    Raises:
        ValueError: Si no se especifica una ruta de entrada o si faltan credenciales de Neo4j.
        FileNotFoundError: Si la ruta de entrada no existe.
        NotImplementedError: Si el tipo de archivo no es soportado.

    Returns:
        None
    """
    logger.info("Iniciando fase de ingesta de datos")

    # Validate required parameters
    if not input_path:
        logger.error("No se especificó archivo o directorio de entrada")
        raise ValueError("Se requiere entrada para la ingesta")

    if not os.path.exists(input_path):
        logger.error(f"La ruta de entrada no existe: {input_path}")
        raise FileNotFoundError(input_path)

    if not neo4j_password and not dry_run:
        logger.error("No se proporcionó contraseña para Neo4j")
        raise ValueError("Se requiere contraseña para Neo4j")

    # Determine file type
    current_file_type = file_type
    if os.path.isfile(input_path) and not current_file_type:
        ext = os.path.splitext(input_path)[1].lower()
        current_file_type = {
            '.bibtex': 'bibtex',
            '.bib': 'bibtex',
        }.get(ext)
        if not current_file_type:
            logger.error(f"No se pudo inferir el tipo de archivo desde la extensión: {ext}")
            raise NotImplementedError(f"Tipo de archivo no soportado: {ext}")

    # Check if file type is supported
    if current_file_type and current_file_type not in SUPPORTED_FILE_TYPES:
        logger.error(f"Tipo de archivo no soportado: {current_file_type}")
        raise NotImplementedError(f"Tipo de archivo no soportado: {current_file_type}")

    if dry_run:
        if os.path.isdir(input_path):
            logger.info(f"[MODO SIMULACIÓN] Se procesaría el directorio: {input_path}")
        else:
            logger.info(f"[MODO SIMULACIÓN] Se procesaría el archivo: {input_path} (tipo: {current_file_type})")
        logger.info("Fase de ingesta de datos completada (simulación)")
        return

    # Initialize data loader
    loader = BibliometricDataLoader(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    # Process input
    if os.path.isdir(input_path):
        logger.info(f"Procesando directorio: {input_path}")
        with tqdm(desc="Ingesta de datos", unit="archivo") as progress_bar:
            loader.process_directory(input_path, progress_callback=lambda: progress_bar.update(1))
    else:
        logger.info(f"Procesando archivo: {input_path} (tipo: {current_file_type})")
        loader.process_file(input_path, current_file_type)

    logger.info("Fase de ingesta de datos completada")



def enrich_data(
    neo4j_uri: str, 
    neo4j_user: str, 
    neo4j_password: Optional[str],
    dry_run: bool = False
) -> None:
    """Enriquece datos en Neo4j usando APIs externas.

    Esta función enriquece datos bibliométricos almacenados en Neo4j obteniendo información
    adicional de APIs externas como Semantic Scholar, Crossref y Scopus.

    Args:
        neo4j_uri: URI para conectarse a la base de datos Neo4j.
        neo4j_user: Nombre de usuario para autenticación de Neo4j.
        neo4j_password: Contraseña para autenticación de Neo4j.
        dry_run: Si es True, simula la operación sin realizar cambios en la base de datos.

    Raises:
        ValueError: Si faltan credenciales de Neo4j.

    Returns:
        None
    """
    logger.info("Iniciando fase de enriquecimiento de datos")

    # Validate required parameters
    if not neo4j_password and not dry_run:
        logger.error("No se proporcionó contraseña para Neo4j")
        raise ValueError("Se requiere contraseña para Neo4j")

    if dry_run:
        logger.info("[MODO SIMULACIÓN] Se simularía el enriquecimiento de todos los artículos")
        logger.info("Fase de enriquecimiento de datos completada (simulación)")
        return

    # Initialize data enricher
    enricher = BibliometricDataEnricher(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    # Enrich all papers with progress reporting
    logger.info("Enriqueciendo todos los artículos...")
    try:
        with tqdm(desc="Enriquecimiento de datos", unit="artículo") as progress_bar:
            enricher.enrich_all_papers(progress_callback=lambda: progress_bar.update(1))
    except TypeError:
        # Fallback if progress_callback is not supported
        logger.info("Usando método de enriquecimiento sin reporte de progreso")
        enricher.enrich_all_papers()

    logger.info("Fase de enriquecimiento de datos completada")


def create_network_relations(
    analyzer: BibliometricNetworkAnalyzer,
    network_type: str,
    dry_run: bool = False
) -> None:
    """Crea relaciones necesarias para extraer redes.

    Esta función crea las relaciones necesarias en Neo4j para el tipo de red especificado.
    Estas relaciones se utilizan posteriormente para la extracción y análisis de redes.

    Args:
        analyzer: Instancia inicializada de BibliometricNetworkAnalyzer.
        network_type: Tipo de red para la que crear relaciones ('cocitation', 'author', etc.).
        dry_run: Si es True, simula la operación sin realizar cambios en la base de datos.

    Returns:
        None
    """
    logger.info("Creando relaciones de red en Neo4j (preprocesamiento)")

    if dry_run:
        logger.info("[MODO SIMULACIÓN] Se simularía la creación de relaciones de red")
        return

    if network_type == 'cocitation':
        rel_count = analyzer.create_co_citation_relationships()
        logger.info(f"Creadas {rel_count} relaciones CO_CITED_WITH")
    # You can add more cases based on network type
    # elif network_type == 'author':
    #     ...

    logger.info("Relaciones de red creadas en Neo4j")


def analyze_network(
    analyzer: BibliometricNetworkAnalyzer,
    network_type: str,
    min_weight: int,
    output_dir: str,
    community_algorithm: str,
    dry_run: bool = False
) -> None:
    """Extrae y analiza redes desde Neo4j.

    Esta función crea las relaciones necesarias, extrae el tipo de red especificado,
    lo analiza, calcula métricas, detecta comunidades y exporta los resultados a archivos.

    Args:
        analyzer: Instancia inicializada de BibliometricNetworkAnalyzer.
        network_type: Tipo de red a extraer ('cocitation', 'author', 'institution', 'keyword').
        min_weight: Peso mínimo para relaciones en la red.
        output_dir: Directorio para archivos de salida.
        community_algorithm: Algoritmo a usar para detección de comunidades.
        dry_run: Si es True, simula la operación sin realizar cambios en la base de datos.

    Returns:
        None
    """
    logger.info("Iniciando fase de análisis de red")

    # Create output directory if it doesn't exist
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)

    # Create necessary relationships if needed
    create_network_relations(analyzer, network_type, dry_run)

    # Extract the requested network
    logger.info(f"Extrayendo red de tipo {network_type}...")

    if dry_run:
        logger.info(f"[MODO SIMULACIÓN] Se simularía la extracción de la red {network_type}")
        logger.info("[MODO SIMULACIÓN] Se simularía el cálculo de métricas y detección de comunidades")
        logger.info("[MODO SIMULACIÓN] Se simularía la exportación de resultados")
        logger.info("Fase de análisis de red completada (simulación)")
        return

    network_name = NETWORK_TYPES.get(network_type, network_type)

    # Extract the requested network with progress reporting
    with tqdm(total=5, desc="Análisis de red", unit="paso") as progress_bar:
        if network_type == 'cocitation':
            network_result = analyzer.extract_co_citation_network(min_weight=min_weight)
            # Handle the new return format (network, quality_report)
            if isinstance(network_result, tuple) and len(network_result) == 2:
                network, quality_report = network_result
                # Log quality report
                logger.info("Informe de calidad para la red de co-citación:")
                logger.info(f"  Recuento de documentos: {quality_report['document_count']} (Umbral: ≥200, Cumplido: {quality_report['meets_volume_threshold']})")
                logger.info(f"  DOI y referencias: {quality_report['doi_ref_percentage']:.2f}% (Umbral: ≥90%, Cumplido: {quality_report['meets_doi_ref_threshold']})")
                logger.info(f"  Cobertura temporal: {quality_report['temporal_coverage']} (Umbral: 2000-2024, Cumplido: {quality_report['meets_temporal_threshold']})")
                logger.info(f"  Diversidad geográfica: {quality_report['country_count']} países (Umbral: ≥5, Cumplido: {quality_report['meets_geographic_threshold']})")
                logger.info(f"  Autores clave: {quality_report['recurring_authors']} autores recurrentes (Umbral: ≥10, Cumplido: {quality_report['meets_author_threshold']})")
                logger.info(f"  Duplicación de fuentes: {quality_report['source_duplication_percentage']:.2f}%")

                # Log missing data percentages
                logger.info("  Porcentajes de datos faltantes:")
                for field, percentage in quality_report['missing_data_percentages'].items():
                    logger.info(f"    {field}: {percentage:.2f}%")

                # Log overall quality score
                logger.info(f"  Puntuación de calidad general: {quality_report['quality_score']:.2f}% ({quality_report['criteria_met_count']}/{quality_report['criteria_total_count']} criterios cumplidos)")

                # Log top authors if available
                if quality_report.get('top_authors'):
                    logger.info("  Autores principales:")
                    for author in quality_report['top_authors']:
                        logger.info(f"    {author['name']}: {author['paper_count']} artículos")
            else:
                # Fallback for backward compatibility
                network = network_result
        elif network_type == 'author':
            network = analyzer.extract_author_collaboration_network()
        elif network_type == 'institution':
            network = analyzer.extract_institution_collaboration_network()
        elif network_type == 'keyword':
            network = analyzer.extract_keyword_co_occurrence_network()

        progress_bar.update(1)

        logger.info(
            f"Red de {network_type} tiene {network.number_of_nodes()} nodos y {network.number_of_edges()} aristas")

        # Export the network
        progress_bar.set_description("Exportando red")
        graphml_path = os.path.join(output_dir, f"{network_name}_network.graphml")
        nodes_path = os.path.join(output_dir, f"{network_name}_nodes.csv")
        edges_path = os.path.join(output_dir, f"{network_name}_edges.csv")

        analyzer.export_graph_to_graphml(network, graphml_path)
        analyzer.export_graph_to_csv(network, nodes_path, edges_path)

        logger.info(f"Red exportada a {graphml_path}, {nodes_path}, y {edges_path}")
        progress_bar.update(1)

        # Calculate network metrics
        progress_bar.set_description("Calculando métricas")
        metrics = analyzer.calculate_network_metrics(network)
        logger.info("Métricas de red:")
        for key, value in metrics.items():
            logger.info(f"  {key}: {value}")
        progress_bar.update(1)

        # Detect communities
        progress_bar.set_description("Detectando comunidades")
        communities, modularity = analyzer.detect_communities(network, algorithm=community_algorithm)
        logger.info(f"Detectadas {len(set(communities.values()))} comunidades con modularidad {modularity:.4f}")
        progress_bar.update(1)

        # Final step
        progress_bar.set_description("Finalizando")
        progress_bar.update(1)

    logger.info("Fase de análisis de red completada")


def run_full_pipeline(
    input_path: Optional[str],
    file_type: Optional[str],
    network_type: str,
    min_weight: int,
    output_dir: str,
    community_algorithm: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: Optional[str],
    dry_run: bool = False
) -> None:
    """Ejecuta el pipeline completo de análisis bibliométrico.

    Esta función ejecuta el pipeline completo: ingesta de datos, enriquecimiento de datos,
    y análisis de redes en secuencia.

    Args:
        input_path: Ruta al archivo o directorio de entrada.
        file_type: Tipo de archivo de entrada ('bibtex').
        network_type: Tipo de red a extraer.
        min_weight: Peso mínimo para relaciones en la red.
        output_dir: Directorio para archivos de salida.
        community_algorithm: Algoritmo a usar para detección de comunidades.
        neo4j_uri: URI para conectarse a la base de datos Neo4j.
        neo4j_user: Nombre de usuario para autenticación de Neo4j.
        neo4j_password: Contraseña para autenticación de Neo4j.
        dry_run: Si es True, simula la operación sin realizar cambios en la base de datos.

    Returns:
        None
    """
    logger.info("Iniciando pipeline completo de análisis bibliométrico")

    if dry_run:
        logger.info("[MODO SIMULACIÓN] Ejecutando pipeline en modo simulación")

    # Initialize the network analyzer once and reuse it
    if not dry_run:
        analyzer = BibliometricNetworkAnalyzer(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
    else:
        # In dry-run mode, we don't need to connect to Neo4j
        analyzer = None

    # Run each step of the pipeline with progress reporting
    with tqdm(total=3, desc="Pipeline completo", unit="fase") as progress_bar:
        progress_bar.set_description("Ingesta de datos")
        ingest_data(input_path, file_type, neo4j_uri, neo4j_user, neo4j_password, dry_run)
        progress_bar.update(1)

        progress_bar.set_description("Enriquecimiento de datos")
        enrich_data(neo4j_uri, neo4j_user, neo4j_password, dry_run)
        progress_bar.update(1)

        progress_bar.set_description("Análisis de red")
        if not dry_run:
            analyze_network(analyzer, network_type, min_weight, output_dir, community_algorithm, dry_run)
        else:
            logger.info("[MODO SIMULACIÓN] Se simularía el análisis de red")
        progress_bar.update(1)

    logger.info("Pipeline completo de análisis bibliométrico finalizado")


def main() -> None:
    """Punto de entrada principal para la aplicación.

    Esta función analiza los argumentos de la línea de comandos y ejecuta el componente
    apropiado del pipeline según el modo especificado.

    Returns:
        None
    """
    args = parse_arguments()

    # Handle version flag
    if args.version:
        print(f"bib2graph versión {VERSION}")
        return

    logger.info("Iniciando pipeline de análisis bibliométrico")

    try:
        # Initialize the network analyzer once if needed and not in dry-run mode
        analyzer = None
        if args.mode in ['create-relations', 'analyze'] and not args.dry_run:
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
                neo4j_password=args.neo4j_password,
                dry_run=args.dry_run
            )
        elif args.mode == 'enrich':
            enrich_data(
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password,
                dry_run=args.dry_run
            )
        elif args.mode == 'create-relations':
            if args.dry_run:
                logger.info("[MODO SIMULACIÓN] Se simularía la creación de relaciones de red")
            else:
                create_network_relations(
                    analyzer=analyzer,
                    network_type=args.network_type,
                    dry_run=args.dry_run
                )
        elif args.mode == 'analyze':
            if args.dry_run and not analyzer:
                logger.info("[MODO SIMULACIÓN] Se simularía el análisis de red")
            else:
                analyze_network(
                    analyzer=analyzer,
                    network_type=args.network_type,
                    min_weight=args.min_weight,
                    output_dir=args.output_dir,
                    community_algorithm=args.community_algorithm,
                    dry_run=args.dry_run
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
                neo4j_password=args.neo4j_password,
                dry_run=args.dry_run
            )
    except Exception as e:
        logger.exception(f"Error en la ejecución del pipeline: {e}")


if __name__ == "__main__":
    main()
