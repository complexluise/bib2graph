# examples/bibtex — Siembra desde BibTeX

Demuestra el camino `b2g seed --from-bib` (issue #50): sembrar un corpus
desde un archivo BibTeX local, sin necesidad de red ni credenciales de OpenAlex.

## Cuándo usarlo

Cuando tenés acceso institucional a bases de datos detrás de paywall (Scopus,
Web of Science, IEEE, etc.) y podés exportar las referencias como `.bib`.
`BibtexSource` extrae el mínimo universal: título, año, autores, keywords,
abstract, DOI, venue, editorial.

## Archivo de ejemplo: `sample.bib`

10 entradas sobre intercambio ecológico desigual, con variedad deliberada de
campos faltantes para ejercitar el parser defensivo:

- Entrada completa con todos los campos
- Sin abstract
- Sin keywords
- Sin DOI
- Sin autores (`author` ausente)
- Sin año (`year` ausente)
- Capítulo de libro (`booktitle` en vez de `journal`)
- Sin campo de afiliación

## Receta completa (100% CLI)

```bash
# 1. Crear workspace e ingresar
b2g init demo-bibtex
cd demo-bibtex

# 2. Sembrar desde el archivo BibTeX (sin red)
b2g seed --from-bib ../examples/bibtex/sample.bib

# 3. Verificar el estado del corpus
b2g status --json

# 4. Construir las redes bibliométricas
b2g build

# 5. (Opcional) exportar el grafo de coupling bibliográfico
b2g export --format graphml
```

## Notas

- Los papers sin título se omiten (campo obligatorio del schema canónico).
- Los campos faltantes (`abstract`, `keywords`, `doi`, etc.) quedan `null`
  en el corpus — sin error.
- `b2g seed --from-bib` es mutuamente excluyente con `--equation` y `--spec`;
  también es incompatible con los flags de OpenAlex (`--min-year`, `--max-year`,
  `--exclude`, `--native`, `--email`, `--max-results`).
- El estado del lazo transiciona a `SEEDED` (igual que la siembra desde OpenAlex).
- Si `bibtexparser` no está instalado, el comando termina con exit 3 y un
  mensaje accionable: `uv sync --extra bibtex`.
