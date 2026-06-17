# Ejemplo: valoraciones en educación

Caso real reproducible — Ciclo B (ADR 0030, principio CLI-puro).

**Qué demuestra:** el ciclo completo `seed` → `curate` → `enrich` → `build` →
`networks` sobre un corpus bibliométrico real (pensamiento complejo + evaluación
educativa), y su reproducción offline sin acceso a internet.

## Corpus

- **~80 filas** (sembrado con `max_results: 80` — corpus chico, Ciclo B).
- Fuente: OpenAlex, ecuación de búsqueda v3 (procedencia en `equation.yaml`).
- Curación: 10 `accepted` (los de mayor `references_id`), 70 `candidate`.
  El `curacion.csv` commiteado es el ancla determinista del flujo (B1).
- `cited_by_id` poblado en los 10 accepted (`b2g enrich --max-citing 25`).
  La red de co-citación está presente (a diferencia del corpus del Ciclo 9b).
- Licencia de los metadatos: OpenAlex provee metadatos bajo CC0.
- Redes no vacías: `bibliographic_coupling`, `author_collab`,
  `institution_collab`, `keyword_cooccurrence`, `cocitation`.

## Armado desde cero (requiere red)

La secuencia es 100% CLI. Usá un workspace temporal fuera del repo:

```bash
# 1. Crear workspace temporal
b2g init /tmp/valoraciones-tmp
cd /tmp/valoraciones-tmp

# 2. Sembrar (requiere acceso a OpenAlex)
b2g seed --spec <ruta-al-repo>/examples/valoraciones/equation.yaml

# 3. Aplicar la curación congelada
b2g curate --from-csv <ruta-al-repo>/examples/valoraciones/curacion.csv

# 4. Enriquecer: poblar cited_by_id en los accepted (requiere red)
b2g enrich --max-citing 25

# 5. Tomar snapshot → copiar a examples/
b2g snapshot
cp snapshots/corpus.parquet <ruta-al-repo>/examples/valoraciones/corpus.parquet
```

**Nota:** el fetch de OpenAlex no es determinista bit-a-bit (el estado de la API
evoluciona). El `corpus.parquet` y `curacion.csv` commiteados son el ancla para
reproducir offline. Si regenerás con red, el parquet puede diferir levemente del
commiteado; para el gate de reproducibilidad usá el path offline de abajo.

## Reproducción offline (sin red)

Para correr el ciclo completo sobre el corpus congelado sin internet:

```bash
# 1. Crear workspace temporal
b2g init /tmp/valoraciones-offline
cd /tmp/valoraciones-offline

# 2. Restaurar el corpus congelado (sin red)
b2g restore --from-corpus <ruta-al-repo>/examples/valoraciones/corpus.parquet

# 3. Construir las redes
b2g build

# 4. (Opcional) Ver composición de comunidades
cat networks/bibliographic_coupling/clusters.csv

# 5. (Opcional) Exportar a GraphML para Gephi/VOSviewer
b2g export --format graphml
```

`b2g restore` carga las ~80 filas en `library.duckdb` con estado `FILTERED`
(el corpus ya fue curado y enriquecido; no se re-siembra, no se toca la red).
`b2g build` produce GraphML, `metrics.json` y `clusters.csv` en `networks/`.

## Procedencia

El `corpus.parquet` commiteado se generó con la secuencia del §Armado desde
cero. Los artefactos congelados son:

- **`corpus.parquet`**: corpus con ~80 filas, 10 accepted, `cited_by_id`
  poblado.
- **`curacion.csv`**: decisiones de curación (10 accepted = los de mayor
  `references_id`). Ancla determinista: aplicar este CSV al corpus sembrado
  produce el mismo estado de curación, independientemente de cuándo se corra.
- **`equation.yaml`**: parámetros de búsqueda (procedencia de la ecuación).

Los archivos fuente del PO (`*.duckdb`, `valoraciones_*`) están gitignoreados
y nunca se commitean.

## Limitaciones conocidas

- **Co-citación dispersa:** la red de co-citación existe pero es pequeña
  (los citants de los 10 accepted, capeados a 25 por paper). Para una
  co-citación más densa, aumentá `--max-citing` o aceptá más papers antes
  de enriquecer.
- **Corpus chico:** ~80 filas es una muestra intencional (Ciclo B, `max_results:
  80`). Para una cobertura bibliométrica más completa, subí `max_results` en
  `equation.yaml` y regenerá.
- **Fetch no determinista:** el estado de OpenAlex evoluciona; re-sembrar en
  otra fecha puede producir un parquet distinto. El parquet commiteado es el
  ancla de reproducibilidad.
