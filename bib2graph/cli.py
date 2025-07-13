"""
CLI para el análisis bibliométrico de la cadena de suministro de semiconductores.

Este módulo proporciona una interfaz de línea de comandos para el pipeline de análisis
bibliométrico, utilizando Click para definir los comandos y opciones.

Ejemplos:
    # Ejecutar el pipeline completo con configuración predeterminada
    bib2graph completo

    # Ingestar datos desde un archivo BibTeX
    bib2graph ingestar --input data/savedrecs.bib --tipo-archivo bibtex

    # Analizar una red de co-citación con peso mínimo de 2
    bib2graph analizar --tipo-red cocitation --peso-minimo 2

    # Enriquecer datos usando APIs externas
    bib2graph enriquecer

    # Ejecutar en modo simulación (sin efectos en la base de datos)
    bib2graph completo --simulacion

    # Mostrar la versión del paquete
    bib2graph --version
"""

import sys
import click
import logging

from bib2graph.config import (
    Neo4jConfig, TIPOS_REDES, ALGORITMOS_COMUNIDAD, TIPOS_ARCHIVOS_SOPORTADOS,
    PESO_MINIMO_PREDETERMINADO, DIRECTORIO_SALIDA_PREDETERMINADO, ALGORITMO_COMUNIDAD_PREDETERMINADO, 
    TIPO_RED_PREDETERMINADO, VERSION
)
from bib2graph.main import (
    ingestar_datos, enriquecer_datos, crear_relaciones_red, analizar_red, ejecutar_pipeline_completo
)
from bib2graph.analisis_red import BibliometricNetworkAnalyzer

# Configure logging
logger = logging.getLogger(__name__)

# Opciones comunes para todos los comandos
neo4j_options = [
    click.option('--neo4j-uri', default=Neo4jConfig().uri,
                 help='URI de conexión a Neo4j (predeterminado: desde entorno o localhost)'),
    click.option('--neo4j-user', default=Neo4jConfig().user,
                 help='Nombre de usuario de Neo4j (predeterminado: desde entorno o "neo4j")'),
    click.option('--neo4j-password', default=Neo4jConfig().password,
                 help='Contraseña de Neo4j (predeterminado: desde entorno)'),
    click.option('--simulacion', is_flag=True,
                 help='Ejecuta en modo simulación sin realizar cambios en la base de datos')
]

def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


@click.group(invoke_without_command=True)
@click.version_option(version=VERSION)
@click.pass_context
def cli(ctx):
    """Pipeline de análisis bibliométrico para la cadena de suministro de semiconductores."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command('ingestar')
@click.option('--input', required=True, help='Archivo o directorio de entrada que contiene datos bibliométricos')
@click.option('--tipo-archivo', type=click.Choice(TIPOS_ARCHIVOS_SOPORTADOS),
              help='Tipo de archivo de entrada (requerido si el tipo no puede inferirse de la extensión)')
@add_options(neo4j_options)
def ingestar_cmd(input, tipo_archivo, neo4j_uri, neo4j_user, neo4j_password, simulacion):
    """Ingesta datos de varias fuentes en Neo4j."""
    ingestar_datos(input, tipo_archivo, neo4j_uri, neo4j_user, neo4j_password, simulacion)


@cli.command('enriquecer')
@add_options(neo4j_options)
def enriquecer_cmd(neo4j_uri, neo4j_user, neo4j_password, simulacion):
    """Enriquece datos en Neo4j usando APIs externas."""
    enriquecer_datos(neo4j_uri, neo4j_user, neo4j_password, simulacion)


@cli.command('crear-relaciones')
@click.option('--tipo-red', type=click.Choice(list(TIPOS_REDES.keys())),
              default=TIPO_RED_PREDETERMINADO, help='Tipo de red para la que crear relaciones')
@add_options(neo4j_options)
def crear_relaciones_cmd(tipo_red, neo4j_uri, neo4j_user, neo4j_password, simulacion):
    """Crea relaciones necesarias para extraer redes."""
    if simulacion:
        logger.info("[MODO SIMULACIÓN] Se simularía la creación de relaciones de red")
        return
    
    analyzer = BibliometricNetworkAnalyzer(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )
    crear_relaciones_red(analyzer, tipo_red, simulacion)


@cli.command('analizar')
@click.option('--tipo-red', type=click.Choice(list(TIPOS_REDES.keys())),
              default=TIPO_RED_PREDETERMINADO, help='Tipo de red a extraer y analizar')
@click.option('--peso-minimo', type=int, default=PESO_MINIMO_PREDETERMINADO,
              help='Peso mínimo para relaciones en la red')
@click.option('--directorio-salida', default=DIRECTORIO_SALIDA_PREDETERMINADO,
              help='Directorio para archivos de salida (se creará si no existe)')
@click.option('--algoritmo-comunidad', type=click.Choice(ALGORITMOS_COMUNIDAD),
              default=ALGORITMO_COMUNIDAD_PREDETERMINADO, help='Algoritmo a usar para detección de comunidades')
@add_options(neo4j_options)
def analizar_cmd(tipo_red, peso_minimo, directorio_salida, algoritmo_comunidad, 
                neo4j_uri, neo4j_user, neo4j_password, simulacion):
    """Extrae y analiza redes desde Neo4j."""
    if simulacion:
        logger.info(f"[MODO SIMULACIÓN] Se simularía el análisis de red {tipo_red}")
        return
    
    analyzer = BibliometricNetworkAnalyzer(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )
    analizar_red(analyzer, tipo_red, peso_minimo, directorio_salida, algoritmo_comunidad, simulacion)


@cli.command('completo')
@click.option('--input', help='Archivo o directorio de entrada que contiene datos bibliométricos')
@click.option('--tipo-archivo', type=click.Choice(TIPOS_ARCHIVOS_SOPORTADOS),
              help='Tipo de archivo de entrada (requerido si el tipo no puede inferirse de la extensión)')
@click.option('--tipo-red', type=click.Choice(list(TIPOS_REDES.keys())),
              default=TIPO_RED_PREDETERMINADO, help='Tipo de red a extraer y analizar')
@click.option('--peso-minimo', type=int, default=PESO_MINIMO_PREDETERMINADO,
              help='Peso mínimo para relaciones en la red')
@click.option('--directorio-salida', default=DIRECTORIO_SALIDA_PREDETERMINADO,
              help='Directorio para archivos de salida (se creará si no existe)')
@click.option('--algoritmo-comunidad', type=click.Choice(ALGORITMOS_COMUNIDAD),
              default=ALGORITMO_COMUNIDAD_PREDETERMINADO, help='Algoritmo a usar para detección de comunidades')
@add_options(neo4j_options)
def completo_cmd(input, tipo_archivo, tipo_red, peso_minimo, directorio_salida, algoritmo_comunidad,
                neo4j_uri, neo4j_user, neo4j_password, simulacion):
    """Ejecuta el pipeline completo de análisis bibliométrico."""
    ejecutar_pipeline_completo(
        input_path=input,
        file_type=tipo_archivo,
        network_type=tipo_red,
        min_weight=peso_minimo,
        output_dir=directorio_salida,
        community_algorithm=algoritmo_comunidad,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        dry_run=simulacion
    )


def main():
    """Punto de entrada principal para la aplicación."""
    try:
        cli()
    except Exception as e:
        logger.exception(f"Error en la ejecución del pipeline: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()