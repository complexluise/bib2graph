# 19 — QA del CLI: uso real, límites y análisis de superficie

> ⚠️ **NOTA DE SESIÓN — no es decisión ni ADR.** Captura el uso hands-on del CLI `b2g`
> (build 0.8, identidad `source_id` / ADR 0036) en una sesión de QA/dogfooding del 2026-06-22.
> El objetivo es dejar por escrito **cómo se usa el CLI de punta a punta, qué límites aparecen,
> y dónde la superficie es redundante o mejorable**. Los hallazgos accionables ya están en issues
> (#124, #125, #126); el debate de **superficie de comandos** (§3) se promovió a la
> Discussion [#127](https://github.com/complexluise/bib2graph/discussions/127). Documentos hermanos: [`09-sesion-qa-prueba-ecologia-valoraciones.md`](09-sesion-qa-prueba-ecologia-valoraciones.md),
> [`15-cli-capa-lectura-analisis.md`](15-cli-capa-lectura-analisis.md), [`17-validacion-tercero-gate34.md`](17-validacion-tercero-gate34.md).

## 1. El recorrido real (guía de uso, lo que efectivamente se corrió)

Todo offline salvo donde se indica. El flujo canónico que se ejercitó:

```
b2g init <ws>                                         # crea el workspace (library.duckdb + workspace.json)
b2g --workspace <ws> seed --from-bib refs.bib         # ingesta de archivo (sin red) → corpus
b2g --workspace <ws> status                           # estado del lazo (CycleState) + conteos
b2g --workspace <ws> curate --dump --out d.csv --scope all   # exporta a CSV para revisión
b2g --workspace <ws> curate --from-csv curacion.csv   # reimporta decisiones (accept/reject en lote)
b2g --workspace <ws> accept --ids doi:… --ids src:…   # curación puntual por id
b2g --workspace <ws> filter --language en --language es  # filtros PRISMA (marca rejected)
b2g --workspace <ws> build --corpus-scope all         # 5 redes (Networks.quick)
b2g --workspace <ws> networks --spec spec.yaml        # redes declarativas (con keyword_filter)
b2g --workspace <ws> inspect --id doi:…               # ficha de un paper (read-only)
b2g --workspace <ws> validate                         # schema + consistencia del store
b2g --workspace <ws> snapshot                         # foto sellada (parquet + corpus_hash)
b2g --workspace <ws> export --format graphml          # re-serializa artefactos de build
b2g --workspace <ws> restore --from-corpus corpus.parquet  # rehidrata corpus congelado
```

**Online (no ejercitado por bloqueo externo, ver §2):** `seed --equation`, `resolve`, `chain`,
`enrich`, `monitor`.

**Lo que se siente bien al usarlo:**
- **Envelope `--json` consistente** (`{schema, ok, command, exit_code, data, warnings, error}`) en
  todos los comandos → scripteable y agente-native de verdad.
- **Resolución por ambiente del workspace** (`--workspace` > `B2G_WORKSPACE` > walk-up): trabajás
  "dentro" de la carpeta y los comandos se resuelven solos. Limpio.
- **Errores accionables:** p. ej. `export` sin build previo → exit 2 con "ejecutá `b2g build` primero";
  el 429 de OpenAlex → error claro, sin crash.
- **Identidad `source_id` (0036)** transparente: `accept`/`inspect`/`curate` por id andan con los
  prefijos nuevos `doi:`/`src:`/`tt:` sin fricción; el GraphML trae `id` + `label` legible.
- **Reproducibilidad:** `corpus_hash` sellado en build/snapshot, `restore` desde parquet.

## 2. Límites encontrados (ya en issues)

- **(BLOQUEANTE externo) OpenAlex requiere API key desde feb-2026** → todo el flujo online da 429.
  El `mailto` polite-pool que usa la librería es un no-op; el tier gratis es 100 créditos/día.
  La librería ni siquiera puede mandar una key todavía. → **#124** (alta).
- **`filter` no deja rastro del filtrado:** el manifest queda `filters: []` y el evento `rejected`
  por-paper trae `source: None` sin criterio → no se puede reconstruir el flujo **PRISMA**. → **#126**
  (media, pre-existente).
- **Warning de `uv` en cada comando** (`tool.uv.dev-dependencies` deprecado) → ensucia toda la
  salida (y los `--json` si no se filtra). → **#125** (baja).
- **Fricción de entorno (no del CLI):** en Windows + git-bash hay *path-mangling* — los paths `/tmp/…`
  pasados como **argumento** a `b2g` se traducen a Windows, pero dentro de strings (p. ej. de Python)
  no. No es bug de la librería; conviene documentarlo para usuarios Windows.

## 3. Análisis de superficie: ¿redundante? ¿qué mejorar?

20 subcomandos. El núcleo conceptual es **ingestar → curar → enriquecer → proyectar redes →
exportar**, más inspección. Observaciones sobre solapamientos:

| Solapamiento | Detalle | Sugerencia |
|---|---|---|
| **`build` vs `networks`** | Ambos **construyen redes**. `build` = quick (5 redes default); `networks --spec` = declarativo YAML. Dos comandos para lo mismo confunde. | Unificar: `b2g build` (sin spec → quick) y `b2g build --spec` (declarativo). O renombrar para que la relación sea obvia. |
| **`accept`/`reject` vs `curate --from-csv`** | Curación puntual por `--ids` vs lote por CSV. Justificado (single vs batch) pero son 3 puertas de curación + el alias deprecado `--all`. | Considerar un grupo `b2g curate {dump,import,accept,reject}` para que la curación viva bajo un comando. |
| **`export` vs salida de `build`** | `build` ya escribe `network.graphml`; `export` re-serializa. Útil para CSV / re-export, pero solapado para GraphML. | Dejar claro en la ayuda que `export` es para *formatos adicionales / re-serializar*, no un paso obligatorio. |
| **`status` vs `inspect`** | Ambos muestran estado. `status` = lazo + conteos; `inspect` = manifest/paper. | OK, pero podrían converger (`inspect` sin args = lo que hoy da `status`). |
| **`monitor` vs `chain` forward** | Ambos buscan citantes nuevos en OpenAlex. | Aclarar la diferencia en la ayuda (monitor = re-chequeo incremental; chain = expansión rankeada). |
| **`resolve` subcomando + `seed --from-bib --resolve`** | Dual a propósito (ADR 0035: dos adaptadores, un servicio). | Correcto — no tocar; solo documentar el patrón. |
| **`--all` vs `--scope all`** (en `curate`) | `--all` es alias deprecado. | Quitar en una limpieza futura. |

**Lo que falta (no redundante, hueco real):**
- **API key / política de auth+rate-limit por proveedor** (#124) — y generalizable a todo motor.
- **Trazabilidad del filtrado / PRISMA** en el manifest (#126).
- **Preview de costo/créditos** antes de pegarle a un motor (encaja con #89 y #124).

## 4. Recomendaciones (priorizadas)

1. **#124 (alta):** soporte de API key de OpenAlex + cliente consciente de créditos. Sin esto el
   flujo online (la mitad del producto) está muerto. Generalizar a política por proveedor (#120).
2. **#126 (media):** que `filter` registre el paso en el manifest y el motivo en la procedencia —
   es el propósito declarado de PRISMA.
3. **Superficie (baja, limpieza):** unificar `build`/`networks`; agrupar curación; quitar `--all`;
   afinar las ayudas de los comandos solapados.
4. **#125 (baja):** silenciar el warning de uv (migrar a `dependency-groups`).

## 5. Veredicto

El CLI 0.8 es **coherente, scripteable y robusto** offline: el refactor a `source_id` no rompió
nada y los features nuevos (`keyword_filter`, flujo BibTeX) andan. La superficie tiene **redundancias
menores** (sobre todo `build`/`networks` y las puertas de curación) que conviene limpiar, pero nada
estructural. El límite real para uso pleno es **externo** (API key de OpenAlex, #124).
