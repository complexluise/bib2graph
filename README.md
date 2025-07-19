
# bib2graph

Un paquete de Python para el procesamiento de datos bibliométricos y análisis de redes.

[![PyPI version](https://img.shields.io/pypi/v/bib2graph.svg)](https://pypi.org/project/bib2graph/)
[![License](https://img.shields.io/github/license/complexluise/bib2graph.svg)](https://github.com/complexluise/bib2graph/blob/main/LICENSE)
[![Python Versions](https://img.shields.io/pypi/pyversions/bib2graph.svg)](https://pypi.org/project/bib2graph/)

## Descripción

`bib2graph` es un pipeline de datos completo para el análisis bibliométrico de publicaciones científicas. Transforma datos bibliográficos en representaciones de red para análisis avanzados. El pipeline consta de tres fases principales:

1. **Ingesta de Datos**: Analiza y normaliza metadatos bibliográficos desde BibTeX y los carga en una base de datos de grafos Neo4j.

2. **Enriquecimiento de Datos**: Consulta APIs externas (Semantic Scholar, CrossRef, Scopus) para obtener metadatos adicionales como citas, referencias completas, ORCIDs de autores e información de financiamiento.

3. **Extracción de Redes**: Genera varias redes para análisis, incluyendo redes de co-citación, redes de colaboración entre autores, redes de colaboración institucional y redes de co-ocurrencia de palabras clave.

## Arquitectura

La arquitectura del sistema consta de tres módulos principales:

1. **Módulo de Ingesta de Datos** (`consigue_los_articulos.py`): Responsable de cargar datos desde diferentes fuentes y normalizarlos para su almacenamiento en Neo4j.

2. **Módulo de Enriquecimiento de Datos** (`enriquecimiento.py`): Consulta APIs externas para obtener metadatos adicionales y actualizar la base de datos.

3. **Módulo de Análisis de Redes** (`analisis_red.py`): Extrae diferentes tipos de redes del grafo y las exporta para análisis posterior.

## Requisitos

- Python 3.12 o superior
- Base de datos Neo4j (instalación local o en la nube)
- Claves de API para servicios externos (opcional):
  - API de Semantic Scholar
  - API de Scopus

## Instalación

### Desde PyPI (Recomendado)

```bash
pip install bib2graph
```

### Desde el Código Fuente

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/complexluise/bib2graph.git
   cd bib2graph
   ```

2. Instalar dependencias con Poetry:
   ```bash
   poetry install
   ```

### Configuración

Configurar variables de entorno para las claves de API y la conexión a Neo4j (opcional):

```bash
# Para Linux/macOS
export SEMANTIC_SCHOLAR_API_KEY="tu_clave_api"
export SCOPUS_API_KEY="tu_clave_api"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="tu_contraseña"

# Para Windows (PowerShell)
$env:SEMANTIC_SCHOLAR_API_KEY="tu_clave_api"
$env:SCOPUS_API_KEY="tu_clave_api"
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="tu_contraseña"
```

## Uso

El script principal proporciona una interfaz de línea de comandos para ejecutar el pipeline completo o fases individuales:

### Ejecutar el pipeline completo:
```bash
bib2graph completo
```

### Ejecutar solo la fase de ingesta de datos:
```bash
bib2graph ingestar --input data/file.bib --tipo-archivo bibtex
```

### Ejecutar solo la fase de enriquecimiento de datos:
```bash
bib2graph enriquecer
```

### Ejecutar solo la fase de análisis de redes:
```bash
bib2graph analizar --tipo-red cocitacion --directorio-salida results
```

### Ejecutar en modo simulación (sin efectos en la base de datos):
```bash
bib2graph completo --simulacion
```

### Mostrar la versión del paquete:
```bash
bib2graph --version
```

### Opciones disponibles:

#### Opciones comunes:
```
--neo4j-uri         URI de conexión a Neo4j
--neo4j-user        Nombre de usuario de Neo4j
--neo4j-password    Contraseña de Neo4j
--simulacion        Ejecuta en modo simulación sin realizar cambios en la base de datos
```

#### Comando 'ingestar':
```
--input             Archivo o directorio de entrada que contiene datos bibliométricos
--tipo-archivo      Tipo de archivo de entrada (bibtex)
```

#### Comando 'analizar':
```
--tipo-red          Tipo de red a extraer y analizar (cocitacion, autor, institucion, palabra_clave)
--peso-minimo       Peso mínimo para relaciones en la red
--directorio-salida Directorio para archivos de salida
--algoritmo-comunidad  Algoritmo a usar para detección de comunidades (louvain, label_propagation, greedy_modularity)
```

#### Comando 'completo':
```
--input             Archivo o directorio de entrada que contiene datos bibliométricos
--tipo-archivo      Tipo de archivo de entrada (bibtex)
--tipo-red          Tipo de red a extraer y analizar (cocitacion, autor, institucion, palabra_clave)
--peso-minimo       Peso mínimo para relaciones en la red
--directorio-salida Directorio para archivos de salida
--algoritmo-comunidad  Algoritmo a usar para detección de comunidades (louvain, label_propagation, greedy_modularity)
```

## Ejemplos

### Procesar un archivo BibTeX y generar una red de co-citación:
```bash
bib2graph completo --input data/references.bib --tipo-red cocitacion --directorio-salida results
```

### Generar una red de colaboración entre autores:
```bash
bib2graph analizar --tipo-red autor --directorio-salida results
```

### Generar una red de co-ocurrencia de palabras clave:
```bash
bib2graph analizar --tipo-red palabra_clave --directorio-salida results
```

### Procesar un archivo BibTeX con un peso mínimo de arista de 2:
```bash
bib2graph completo --input data/references.bib --tipo-archivo bibtex --tipo-red cocitacion --peso-minimo 2 --directorio-salida results
```

### Crear relaciones de red sin realizar análisis:
```bash
bib2graph crear-relaciones --tipo-red cocitacion
```

## Estructura del Proyecto

```
bib2graph/
├── data/                      # Directorio de datos de entrada
│   └── references.bib         # Archivo BibTeX de ejemplo
├── bib2graph/                 # Código fuente
│   ├── __init__.py            # Inicialización del paquete
│   ├── __main__.py            # Punto de entrada del paquete
│   ├── cli.py                 # Interfaz de línea de comandos
│   ├── config.py              # Configuración y constantes
│   ├── consigue_los_articulos.py  # Módulo de ingesta de datos
│   ├── enriquecimiento.py     # Módulo de enriquecimiento de datos
│   ├── analisis_red.py        # Módulo de análisis de redes
│   ├── models.py              # Modelos de datos
│   ├── queries.py             # Consultas a la base de datos
│   └── main.py                # Funciones principales del pipeline
├── results/                   # Resultados generados
├── tests/                     # Pruebas unitarias
├── pyproject.toml             # Configuración de Poetry
├── .github/                   # Flujos de trabajo de GitHub
│   └── workflows/             # Flujos de trabajo de CI/CD
└── README.md                  # Documentación
```

## Licencia

Este proyecto está licenciado bajo la Licencia Apache 2.0 - consulte el archivo [LICENSE](LICENSE) para más detalles.

## Contribuciones

¡Las contribuciones son bienvenidas! No dude en enviar un Pull Request.

## Cita

Si utiliza bib2graph en su investigación, por favor cítelo como:

```
Higuera-Calderon, L. E. (2025). bib2graph: Un paquete de Python para el procesamiento de datos bibliométricos y análisis de redes. 
https://github.com/complexluise/bib2graph
```
