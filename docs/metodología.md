
# Documento Metodológico: Análisis de Redes de Cocitación en Investigación Bibliométrica

## Introducción

El presente documento describe la metodología utilizada para la construcción, análisis y visualización de redes de cocitación en el contexto de un estudio bibliométrico sobre la cadena de semiconductores. La metodología implementada se basa en técnicas avanzadas de análisis de redes sociales aplicadas a datos bibliográficos, utilizando una arquitectura de base de datos orientada a grafos para representar las relaciones entre documentos científicos.

## Fundamento Teórico

Las redes de cocitación son una herramienta fundamental en los estudios bibliométricos que permiten identificar la estructura intelectual de un campo de investigación. Dos documentos se consideran cocitados cuando ambos son referenciados por un tercer documento. La frecuencia con la que dos documentos son cocitados se interpreta como una medida de similitud temática o conceptual entre ellos, bajo la premisa de que los documentos frecuentemente cocitados abordan temas relacionados o complementarios.

## Arquitectura del Sistema

El sistema implementado sigue una arquitectura modular que consta de los siguientes componentes principales:

1. **Modelo de Datos**: Implementado en Neo4j, una base de datos orientada a grafos, que permite representar de manera natural las relaciones entre entidades bibliográficas.
2. **Cargador de Datos Bibliométricos**: Responsable de la ingesta de datos desde fuentes bibliográficas como archivos BibTeX.
3. **Enriquecedor de Datos**: Amplía la información de los documentos mediante consultas a APIs externas como Semantic Scholar y Scopus.
4. **Analizador de Redes**: Construye y analiza las redes de cocitación, calculando métricas y detectando comunidades.

## Metodología

### 1. Recolección y Preparación de Datos

El proceso comienza con la recolección de datos bibliográficos de fuentes como Web of Science, Scopus o bases de datos especializadas. Los datos se obtienen en formato BibTeX y se procesan para su ingesta en la base de datos Neo4j. Durante esta fase:

- Se extraen metadatos básicos como título, autores, año de publicación, DOI, etc.
- Se normalizan los nombres de autores e instituciones para evitar duplicidades.
- Se identifican y extraen las referencias bibliográficas de cada documento.

### 2. Enriquecimiento de Datos

Para mejorar la calidad y completitud de los datos, se implementa un proceso de enriquecimiento que:

- Consulta APIs externas como Semantic Scholar y Scopus para obtener información adicional.
- Completa datos faltantes como abstracts, keywords, y afiliaciones institucionales.
- Normaliza y estandariza la información obtenida de diferentes fuentes.

### 3. Construcción de la Red de Cocitación

La red de cocitación se construye mediante el siguiente algoritmo:

1. Se identifican todos los documentos semilla (is_seed=True) en la base de datos.
2. Para cada par de documentos (p1, p2), se cuentan las referencias compartidas.
3. Se crea una relación CO_CITED_WITH entre p1 y p2 con un peso igual al número de referencias compartidas.
4. Se filtran las relaciones con un peso mínimo definido por el usuario (por defecto, 1).

La implementación en Cypher (lenguaje de consulta de Neo4j) es la siguiente:

```cypher
MATCH (p1:Paper {is_seed: True})-[:REFERENCES]->(ref:Paper)<-[:REFERENCES]-(p2:Paper {is_seed: True})
WHERE p1 <> p2
WITH p1, p2, COUNT(ref) AS shared_refs
WHERE shared_refs > 0
MERGE (p1)-[r:CO_CITED_WITH]-(p2)
ON CREATE SET r.weight = shared_refs
```

### 4. Evaluación de Calidad de la Red

Para garantizar la validez y representatividad de la red de cocitación, se evalúan los siguientes criterios de calidad:

- **Volumen documental**: Se verifica que la red contenga un número mínimo de documentos (≥200).
- **Completitud de DOI y referencias**: Se calcula el porcentaje de documentos con DOI y referencias (umbral ≥90%).
- **Cobertura temporal**: Se evalúa si la red abarca un período significativo (2000-2024).
- **Diversidad geográfica**: Se verifica la presencia de instituciones de al menos 5 países diferentes.
- **Participación de autores clave**: Se identifica la presencia de autores recurrentes (≥10).

Estos criterios se combinan en una puntuación global de calidad que permite evaluar la robustez de la red construida.

### 5. Análisis de la Red

Una vez construida la red, se realizan diversos análisis:

#### 5.1 Métricas Básicas
- **Tamaño de la red**: Número de nodos (documentos) y aristas (relaciones de cocitación).
- **Densidad**: Proporción de conexiones existentes respecto al total posible.
- **Componentes conectados**: Identificación del componente principal y fragmentos aislados.

#### 5.2 Análisis de Centralidad
- **Centralidad de grado**: Identifica documentos con mayor número de conexiones.
- **Centralidad de intermediación**: Identifica documentos que actúan como puentes entre diferentes áreas temáticas.
- **Coeficiente de agrupamiento**: Mide la tendencia de los nodos a formar grupos cohesivos.

#### 5.3 Detección de Comunidades
Se implementan tres algoritmos de detección de comunidades:

- **Louvain**: Optimiza la modularidad mediante un enfoque jerárquico.
- **Propagación de etiquetas**: Asigna comunidades basándose en las etiquetas predominantes de los vecinos.
- **Modularidad voraz**: Fusiona comunidades para maximizar la modularidad global.

La elección del algoritmo depende de las características específicas de la red y los objetivos del análisis.

### 6. Visualización y Exportación

Los resultados del análisis se exportan en formatos estándar:

- **GraphML**: Para su visualización en herramientas especializadas como Gephi.
- **CSV**: Archivos separados para nodos y aristas, facilitando análisis adicionales en herramientas estadísticas.

## Validación Metodológica

La metodología implementada se basa en principios establecidos en la literatura bibliométrica y cienciométrica, incorporando mejores prácticas de:

1. **Normalización de datos**: Reducción de ambigüedades en nombres de autores e instituciones.
2. **Filtrado de ruido**: Eliminación de relaciones débiles mediante umbrales de peso mínimo.
3. **Evaluación de calidad**: Aplicación de criterios objetivos para evaluar la representatividad de la red.
4. **Análisis multidimensional**: Combinación de diferentes métricas y técnicas de análisis.

## Limitaciones y Consideraciones

Es importante reconocer las siguientes limitaciones:

1. **Dependencia de la calidad de los datos de origen**: La precisión de las referencias bibliográficas afecta directamente la estructura de la red.
2. **Sesgo temporal**: Los documentos más recientes tienen menos probabilidad de ser cocitados debido a su menor tiempo de exposición.
3. **Complejidad computacional**: El análisis de redes grandes puede requerir recursos computacionales significativos.

## Conclusiones

La metodología presentada proporciona un marco robusto para el análisis de redes de cocitación, permitiendo identificar la estructura intelectual del campo de investigación sobre semiconductores. El enfoque basado en grafos facilita la representación natural de las relaciones bibliográficas, mientras que las técnicas de análisis de redes sociales permiten descubrir patrones y estructuras no evidentes mediante métodos bibliométricos tradicionales.

Esta metodología puede adaptarse a otros campos de investigación, ajustando los parámetros y criterios de calidad según las características específicas de cada dominio.