"""
Funciones principales para el análisis bibliométrico de la cadena de suministro de semiconductores.

Este módulo contiene las funciones principales que implementan los componentes del pipeline de datos:
1. Ingesta de datos de varias fuentes
2. Enriquecimiento de datos usando APIs externas
3. Extracción y análisis de redes

Estas funciones son utilizadas por la interfaz de línea de comandos (CLI) y también pueden
ser importadas y utilizadas directamente en scripts o aplicaciones Python.
"""

import os
import logging
from typing import Dict, Optional

from tqdm import tqdm

from bib2graph import BibliometricDataLoader
from bib2graph.enriquecimiento import BibliometricDataEnricher
from bib2graph.analisis_red import BibliometricNetworkAnalyzer
from bib2graph.config import (
    Neo4jConfig, TIPOS_REDES, ALGORITMOS_COMUNIDAD, TIPOS_ARCHIVOS_SOPORTADOS,
    PESO_MINIMO_PREDETERMINADO, DIRECTORIO_SALIDA_PREDETERMINADO, ALGORITMO_COMUNIDAD_PREDETERMINADO, 
    TIPO_RED_PREDETERMINADO
)

# Configure logging
logger = logging.getLogger(__name__)


def ingestar_datos(
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
    if current_file_type and current_file_type not in TIPOS_ARCHIVOS_SOPORTADOS:
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


def enriquecer_datos(
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


def crear_relaciones_red(
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

    if network_type == 'cocitacion':
        rel_count = analyzer.create_co_citation_relationships()
        logger.info(f"Creadas {rel_count} relaciones CO_CITED_WITH")
    elif network_type == 'autor':
        rel_count = analyzer.create_author_collaboration_relationships()
        logger.info(f"Creadas {rel_count} relaciones COLLABORATED_WITH entre autores")
    elif network_type == 'institucion':
        rel_count = analyzer.create_institution_collaboration_relationships()
        logger.info(f"Creadas {rel_count} relaciones COLLABORATED_WITH entre instituciones")
    elif network_type == 'palabra_clave':
        rel_count = analyzer.create_keyword_co_occurrence_relationships()
        logger.info(f"Creadas {rel_count} relaciones CO_OCCURS_WITH entre palabras clave")

    logger.info("Relaciones de red creadas en Neo4j")


def analizar_red(
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

        # Create subdirectories for different types of results
        redes_dir = os.path.join(output_dir, "redes")
        datos_dir = os.path.join(output_dir, "datos")
        visualizaciones_dir = os.path.join(output_dir, "visualizaciones")
        metricas_dir = os.path.join(output_dir, "metricas")
        comunidades_dir = os.path.join(output_dir, "comunidades")

        # Create subdirectories
        os.makedirs(redes_dir, exist_ok=True)
        os.makedirs(datos_dir, exist_ok=True)
        os.makedirs(visualizaciones_dir, exist_ok=True)
        os.makedirs(metricas_dir, exist_ok=True)
        os.makedirs(comunidades_dir, exist_ok=True)

        # Extract the requested network
    logger.info(f"Extrayendo red de tipo {network_type}...")

    if dry_run:
        logger.info(f"[MODO SIMULACIÓN] Se simularía la extracción de la red {network_type}")
        logger.info("[MODO SIMULACIÓN] Se simularía el cálculo de métricas y detección de comunidades")
        logger.info("[MODO SIMULACIÓN] Se simularía la exportación de resultados")
        logger.info("Fase de análisis de red completada (simulación)")
        return

    network_name = TIPOS_REDES.get(network_type, network_type)

    # Extract the requested network with progress reporting
    with tqdm(total=5, desc="Análisis de red", unit="paso") as progress_bar:
        if network_name == "cocitacion":
            network, quality_report = analyzer.extract_co_citation_network(min_weight=min_weight)

            logger.info("Informe de calidad para la red de co-citación:")
            logger.info(f"  Recuento de documentos: {quality_report['document_count']} (Umbral: ≥200, Cumplido: {quality_report['meets_volume_threshold']})")
            logger.info(f"  DOI y referencias: {quality_report['doi_ref_percentage']:.2f}% (Umbral: ≥90%, Cumplido: {quality_report['meets_doi_ref_threshold']})")
            logger.info(f"  Cobertura temporal: {quality_report['temporal_coverage']} (Umbral: 2000-2024, Cumplido: {quality_report['meets_temporal_threshold']})")
            logger.info(f"  Diversidad geográfica: {quality_report['country_count']} países (Umbral: ≥5, Cumplido: {quality_report['meets_geographic_threshold']})")
            logger.info(f"  Autores clave: {quality_report['recurring_authors']} autores recurrentes (Umbral: ≥10, Cumplido: {quality_report['meets_author_threshold']})")
            logger.info(f"  Duplicación de fuentes: {quality_report['source_duplication_percentage']:.2f}%")

            logger.info("  Porcentajes de datos faltantes:")
            for field, percentage in quality_report['missing_data_percentages'].items():
                logger.info(f"    {field}: {percentage:.2f}%")

            logger.info(f"  Puntuación de calidad general: {quality_report['quality_score']:.2f}% ({quality_report['criteria_met_count']}/{quality_report['criteria_total_count']} criterios cumplidos)")

            if quality_report.get('top_authors'):
                logger.info("  Autores principales:")
                for author in quality_report['top_authors']:
                    logger.info(f"    {author['name']}: {author['paper_count']} artículos")

        elif network_name == 'colaboracion_autor':
            network = analyzer.extract_author_collaboration_network()
        elif network_name == 'colaboracion_institucion':
            network = analyzer.extract_institution_collaboration_network()
        elif network_name == 'coocurrencia_palabra_clave':
            network = analyzer.extract_keyword_co_occurrence_network()

        # Check if network is empty and exit if true
        if network.number_of_nodes() == 0:
            logger.warning(f"La red de {network_type} está vacía. No hay nada que analizar.")
            return
        progress_bar.update(1)

        logger.info(
            f"Red de {network_type} tiene {network.number_of_nodes()} nodos y {network.number_of_edges()} aristas")

        # Export the network
        progress_bar.set_description("Exportando red")
        graphml_path = os.path.join(redes_dir, f"{network_name}_network.graphml")
        nodes_path = os.path.join(datos_dir, f"{network_name}_nodes.csv")
        edges_path = os.path.join(datos_dir, f"{network_name}_edges.csv")

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


def ejecutar_pipeline_completo(
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

    if not dry_run:
        analyzer = BibliometricNetworkAnalyzer(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
    else:
        analyzer = None

    # Run each step of the pipeline with progress reporting
    with tqdm(total=3, desc="Pipeline completo", unit="fase") as progress_bar:
        progress_bar.set_description("Ingesta de datos")
        ingestar_datos(input_path, file_type, neo4j_uri, neo4j_user, neo4j_password, dry_run)
        progress_bar.update(1)

        progress_bar.set_description("Enriquecimiento de datos")
        enriquecer_datos(neo4j_uri, neo4j_user, neo4j_password, dry_run)
        progress_bar.update(1)

        progress_bar.set_description("Análisis de red")
        if not dry_run:
            crear_relaciones_red(analyzer, network_type, dry_run)
            analizar_red(analyzer, network_type, min_weight, output_dir, community_algorithm, dry_run)
        else:
            logger.info("[MODO SIMULACIÓN] Se simularía el análisis de red")
        progress_bar.update(1)

    logger.info("Pipeline completo de análisis bibliométrico finalizado")
