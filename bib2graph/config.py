"""
Módulo de configuración centralizada para bib2graph.

Este módulo contiene valores por defecto para la conexión a Neo4j y otras constantes
compartidas en todo el paquete.
"""

import os
from typing import Dict, Optional

class Neo4jConfig:
    """Configuración para la conexión a Neo4j.

    Esta clase carga los parámetros de conexión a Neo4j desde variables de entorno
    con valores predeterminados sensatos.

    Attributes:
        uri: La URI para conectarse a la base de datos Neo4j.
        user: El nombre de usuario para la autenticación de Neo4j.
        password: La contraseña para la autenticación de Neo4j.
    """

    def __init__(self) -> None:
        """Inicializa la configuración de Neo4j con valores de variables de entorno."""
        self.uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user: str = os.getenv("NEO4J_USER", "neo4j")
        self.password: Optional[str] = os.getenv("NEO4J_PASSWORD")  # Sin valor predeterminado por seguridad

    def as_dict(self) -> Dict[str, Optional[str]]:
        """Convierte la configuración a un diccionario.

        Returns:
            Diccionario con los parámetros de conexión a Neo4j.
        """
        return {
            "uri": self.uri,
            "user": self.user,
            "password": self.password
        }

# Constantes para tipos de redes soportados
TIPOS_REDES = {
    'cocitacion': 'cocitacion',
    'autor': 'colaboracion_autor',
    'institucion': 'colaboracion_institucion',
    'palabra_clave': 'coocurrencia_palabra_clave'
}

# Constantes para algoritmos de detección de comunidades
ALGORITMOS_COMUNIDAD = ['louvain', 'propagacion_etiquetas', 'modularidad_voraz']

# Constantes para tipos de archivos soportados
TIPOS_ARCHIVOS_SOPORTADOS = ['bibtex']

# Valores predeterminados para parámetros de análisis
PESO_MINIMO_PREDETERMINADO = 1
DIRECTORIO_SALIDA_PREDETERMINADO = 'salida'
ALGORITMO_COMUNIDAD_PREDETERMINADO = 'louvain'
TIPO_RED_PREDETERMINADO = 'cocitacion'

# Versión del paquete
from bib2graph import __version__
VERSION = __version__
