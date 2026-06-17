# Ejemplo: valoraciones en educación

Caso real reproducible sin red — gate del Ciclo #33 (ADR 0030).

**Qué demuestra:** el ciclo completo `restore` → `build` → `networks` sobre un
corpus bibliométrico real (pensamiento complejo + evaluación educativa), sin
acceso a internet.

## Corpus

- **137 filas** (reducción determinista del corpus original de 800 papers).
- Fuente: OpenAlex, ecuación de búsqueda v3 (procedencia en `equation.yaml`),
  ronda del 2026-06-16.
- Curación aplicada: 7 `accepted`, 0 `rejected`, 130 `candidate`. **Por qué solo 7 `accepted`
  (no 44):** el CSV de curación marcó 44 `accepted`, pero solo **7 de esos 44** existían en el
  corpus fuente reducido a este parquet; los otros 37 quedaron fuera del recorte (ver §Procedencia).
  No es una contradicción: el parquet trae las decisiones de los papers que efectivamente contiene.
- Licencia de los metadatos: OpenAlex provee metadatos bajo CC0.
- `cited_by_id` vacío en todo el corpus (el Enricher de co-citación no se corrió).
  La red de co-citación queda vacía; `Networks.quick` la omite graciosamente.
- Redes no vacías esperadas: `bibliographic_coupling` (132 nodos, ~3897 aristas),
  `author_collab`, `institution_collab`, `keyword_cooccurrence`.

## Receta reproducible (sin red)

### 1. Inicializar un workspace temporal

```bash
b2g init valoraciones-ejemplo
cd valoraciones-ejemplo
```

### 2. Restaurar el corpus congelado

```bash
b2g restore --from-corpus ../examples/valoraciones/corpus.parquet
```

Esto carga las 137 filas en `library.duckdb` con estado `FILTERED`
(el corpus ya fue curado; no se re-siembra, no se toca la red).

### 3. Construir las redes

```bash
b2g build
```

Genera las redes bibliométricas (acoplamiento, co-autoría, instituciones,
co-palabras). Escribe los GraphML, `metrics.json` y `clusters.csv` en `networks/`.

### 4. Ver la composición de comunidades

```bash
cat networks/bibliographic_coupling/clusters.csv
```

O para inspeccionar todas:

```bash
b2g status
```

### 5. (Opcional) Exportar a GraphML para Gephi/VOSviewer

```bash
b2g export --format graphml
```

Los archivos exportados quedan en `exports/`.

### 6. (Opcional) Cargar la ecuación de búsqueda para re-sembrar con red

Si tenés acceso a internet y querés actualizar el corpus desde OpenAlex:

```bash
b2g seed --spec ../examples/valoraciones/equation.yaml
```

Esto **no es el camino del gate**: requiere red y producirá un corpus distinto
según el estado actual de OpenAlex. El gate usa `restore`, no `seed`.

## Procedencia y regeneración

El `corpus.parquet` fue generado con el script `build_corpus.py` a partir de
dos archivos fuente locales del PO (gitignoreados, nunca commitados):

- `valoraciones_v3.duckdb.contaminado.bak`: corpus vivo de 800 filas (485 seeds
  + 315 candidatos por chaining), obtenido con la ecuación v3 (ecuación_id:
  `eq-20260616T225800`).
- `valoraciones_v3_curable_pre.csv`: 300 candidatos con curación real
  (44 `accepted`, 77 `rejected`, 179 `undecided`).

Para regenerar el parquet desde esos archivos (requiere tenerlos localmente):

```bash
uv run python examples/valoraciones/build_corpus.py
```

El criterio de reducción es determinista (sin aleatoriedad): incluye todos los
`accepted` del CSV **que estén presentes en el corpus fuente** (resultan 7 de
los 44 marcados; los 37 restantes no están en el `.bak`), los top-100 seeds por
cantidad de `references_id` (para que el acoplamiento bibliográfico tenga
aristas), y los top-30 candidatos con mayor `references_id`. Ver el docstring de
`build_corpus.py` para el detalle completo.

## Limitaciones conocidas

- **Co-citación vacía:** `cited_by_id` está en blanco en todo el corpus original.
  El Enricher de co-citación (Hito 8b, `b2g enrich`) requiere una segunda ronda
  de fetch contra OpenAlex. No se ejecutó para este corpus. La red de co-citación
  queda vacía; `Networks.quick` la omite con un aviso informativo en el log.
- **Curación parcial (en el CSV fuente):** de los 300 candidatos revisados, solo
  44 fueron marcados `accepted` (77 `rejected`, 179 `undecided`). De esos 44
  `accepted`, solo **7** entran en este parquet reducido (el resto no estaba en el
  recorte). Los `undecided` conservan `curation_status='candidate'`.
- **`min_year`/`max_year` en `equation.yaml`:** declarados pero no filtran contra
  OpenAlex todavía (trabajo futuro, ADR 0030 §Schema de equation.yaml).
- **Corpus reducido:** las 137 filas son una muestra determinista del corpus
  real de 800 papers, suficiente para redes no vacías y para el gate de
  reproducibilidad.
