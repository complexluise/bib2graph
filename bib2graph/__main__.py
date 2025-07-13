"""
Punto de entrada para la interfaz de línea de comandos (CLI) de bib2graph.

Este módulo sirve como punto de entrada cuando el paquete se ejecuta como un script
(por ejemplo, con 'python -m bib2graph'). Importa y ejecuta la función main() del
módulo cli.py, que implementa la interfaz de línea de comandos usando Click.

Ejemplos:
    # Ejecutar el pipeline completo con configuración predeterminada
    python -m bib2graph completo

    # Ingestar datos desde un archivo BibTeX
    python -m bib2graph ingestar --input data/savedrecs.bib --tipo-archivo bibtex

    # Analizar una red de co-citación con peso mínimo de 2
    python -m bib2graph analizar --tipo-red cocitacion --peso-minimo 2

    # Enriquecer datos usando APIs externas
    python -m bib2graph enriquecer

    # Ejecutar en modo simulación (sin efectos en la base de datos)
    python -m bib2graph completo --simulacion

    # Mostrar la versión del paquete
    python -m bib2graph --version
"""

from bib2graph.cli import main

if __name__ == "__main__":
    main()
