# API — superficie pública de bib2graph

> Contratos de las costuras y del núcleo: el "producto" que ve quien la integra o la extiende.
> Son **bocetos de interfaz** (firmas + docstrings), no la implementación: el código es la fuente de
> verdad última y este doc describe el contrato que ese código cumple. Diseño de fondo en
> [`ARCHITECTURE.md`](ARCHITECTURE.md); método en [`Notas/metodología.md`](Notas/metodología.md).
>
> El `Corpus` es una **tabla Arrow validada con Pydantic v2** (ADR
> [0006](decisiones/0006-tabla-canonica-y-networkspec.md)) respaldada por un **`TabularBackend`**
> (`InMemoryBackend` puro / `DuckDBBackend` por defecto; ADR
> [0015](decisiones/0015-corpus-tabular-backend.md)); `Paper`/`Author`/`Keyword`/`Institution` son
> **vistas derivadas**, no tipos. El estado del lazo (`CycleState`) vive en el backend persistente (ADR
> [0016](decisiones/0016-maquina-estados-lazo.md)). El contrato `Source` separa **mínimo universal vs
> enriquecimiento opcional** (ADR [0018](decisiones/0018-source-agnostico-calidad.md)). El **producto
> no usa IA generativa** (ADR [0022](decisiones/0022-producto-sin-ia-generativa.md)): la asistencia del
> forrajeo es estructura bibliométrica determinista (*information scent*).
>
> La superficie pública —núcleo, costuras, capa de servicios neutral `service/`, y el **CLI de 10
> verbos** (ADR [0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md)/[0038](decisiones/0038-destino-verbos-huerfanos-0037.md))—
> está **construida**; lo marcado **`futuro`** está declarado pero no implementado (no falsamente
> prometido). Las firmas de abajo se verifican contra `src/bib2graph/`.

## Convenciones

- Tipado estático en todas las firmas públicas. Las costuras se definen como `Protocol` o ABC.
- **Funciones puras** en el núcleo (proyectores, analizadores, preprocesador): sin red, sin
  estado global. El estado (biblioteca viva + `LoopState`) vive en el backend persistente
  (`DuckDBBackend`), no en la sesión.
- Estado de implementación: **`v1`** vs **`futuro`** (declarado, NO implementado — marcado como
  tal, no falsamente prometido; lección 5 de v0).

### Convenciones del CLI agente-native (ADR 0010 / 0021)

El CLI `b2g` (paquete `bib2graph.cli`, entry point `b2g = "bib2graph.cli:main"`) cumple el contrato del
ADR [0021](decisiones/0021-cli-agente-native-contrato.md). Cada subcomando lleva `--json` (envelope
estable/versionado, también activable con **`B2G_JSON=1`**, ver §Envelope JSON) y exit codes (`0` éxito
· `1` uso · `2` datos · `3` dependencia · `4` red · `5` store/snapshot corrupto o bloqueado). **Sin
estado entre invocaciones:** el estado vive en el `library.duckdb` del **workspace** (opción global
**opcional** `--workspace`; `--store` fue eliminada en #75).

**Superficie 0.10.0 — 10 verbos del ciclo + 3 grupos noun-verb + `skill`** (ADR
[0037](decisiones/0037-superficie-cli-10-verbos-ciclo.md)/[0038](decisiones/0038-destino-verbos-huerfanos-0037.md)/[0039](decisiones/0039-skill-comando-meta-distribucion.md)).
La superficie mapea 1:1 el ciclo (*más es menos*); el conteo es **verificable contra `b2g --help`**:

- **10 verbos del ciclo:** `init`, `seed`, `chain`, `curate` (grupo), `build`, `read` (grupo),
  `export`, `snapshot` (grupo), `status`, `validate`. (El par EXPORT/SNAPSHOT cuenta como uno; ADR 0037.)
- **3 grupos noun-verb:** `read {list,stats,show,top}`, `curate {dump,apply,accept,reject,filter}`,
  `snapshot {create,restore}`. Un grupo **sin subcomando** imprime ayuda y sale **exit 0**; el `command`
  del envelope usa la **ruta completa** (`"read list"`).
- **1 comando meta** fuera del set de 10 (no es un paso del ciclo): **`skill add`** (ADR 0039).
- **Aliases deprecados** (vivos con aviso a stderr, retiro **0.11.0**): `accept`, `reject`, `filter`,
  `inspect`, `monitor`, `networks`, `enrich`, `restore`, `resolve` (ver §Avisos de deprecación).
  **`thesaurus` NO es alias: se retiró por completo** (su capacidad es `build --thesaurus`, #164).

**`status`** expone el ciclo: estado actual del FSM (`SEEDED/FORAGED/FILTERED/BUILT/MONITORED`, dominio
en `bib2graph.cycle`), `transitions_available`, `curation_available` (`accept`/`reject` siempre
disponibles, curación transversal), `round` (contador de ronda con `reseed`), conteos por
`curation_status`, `workspace: {root, source}`, `networks_cache_stale: bool` (+ `warnings` accionable
cuando la cache de `networks/` quedó obsoleta — avisa, NO regenera) y `referenced_not_fetched` (nº de
IDs que el backward chaining observó sin materializar; §4/§5). Todos campos aditivos, `schema="1"`
intacto. **`validate`** chequea la consistencia del workspace (read-only).

**`init`** (ADR [0029](decisiones/0029-workspace-por-investigacion.md)): scaffold de un workspace.
`b2g init <name>` crea `<name>/` con `workspace.json` + `library.duckdb` +
`networks/`/`snapshots/`/`exports/`; **`b2g init .`** inicializa el cwd (adopta un `.duckdb` legacy). Si
la carpeta ya es workspace → `WorkspaceExistsError`. **NO transiciona.** `data = {root, name, ...}`.

**`seed`** (ADR [0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)): **TRES modos
mutuamente excluyentes** (exactamente uno; ninguno o más de uno → exit 1):

- **`--equation '<texto>'`** — ecuación cruda (modo OpenAlex directo, con red).
- **`--spec equation.yaml`** — la misma siembra parametrizada por un YAML versionable (clave raíz
  `equation:`, modelo `EquationSpec`, §2; paridad 1:1 flag ⇄ campo).
- **`--from-bib <archivo.bib>`** — siembra desde BibTeX local **sin red** (`BibtexSource.load`);
  `is_seed=True`/`candidate`, transiciona a `SEEDED` (o reseed → ronda++). `data = {papers_added,
  total_papers, round, reseeded}` (sin `executed_query`/`translation_report`). Falta `bibtexparser`
  (`[bibtex]`) → `DependencyError` exit 3; archivo inexistente / `.bib` mal formado → `DataError` exit 2.
  - **`--resolve`** (solo con `--from-bib`): tras cargar, encadena la resolución DOI→`source_id` (=
    correr `b2g resolve`) reusando el store abierto; suma `data["resolve"]`. **`--email`** se permite
    con `--from-bib` solo junto a `--resolve` (se propaga al polite pool).

Flags OpenAlex (**solo con `--equation`/`--spec`**): **`--max-results INT`** (default del source 200;
muestras chicas); **`--exclude TEXT`** (repetible) = negaciones quirúrgicas inyectadas **dentro** de la
única expresión `title_and_abstract.search:((query) AND NOT "<término>")` (campo no repetido), en el
`translation_report`; **`--min-year`/`--max-year`** filtran contra OpenAlex
(`from_publication_date`/`to_publication_date` como predicado separado por coma, fuera del `search`);
**`--native`** = query cruda (sin traducción; min/max-year no aplican). **Combinar cualquier flag
OpenAlex con `--from-bib` → exit 1** (salvo `--email` junto a `--resolve`). **No existe
`seed --from-corpus`** (rehidratar un parquet curado es `snapshot restore`).

**`chain`** (paso CHAIN): expande el corpus con candidatos rankeados por *information scent*
(forward/backward batcheado, §5). **`--direction [backward|forward|both]`** (default `both`),
**`--depth`** (solo 1), **`--max-candidates`**, **`--max-citing`** (presupuesto de citantes por semilla
en forward, default 50), **`--email`**, **`--preview`** (dry-run sin red ni transición: backward exacto
desde `references_id`; forward exacto solo si hay `cited_by_id`). Transiciona a **`FORAGED`** y corre
**automática la pasada refs→DOI** (§Enricher absorbido): el `--json` suma `data["enrichment"]`. `data =
{candidates_found, new_candidates, total_papers, direction, depth, ranking_preview, observed_refs_count,
loop_state, round, enrichment}`.

- **`--since` (forrajeo incremental, absorbe `monitor`):** trae **solo citantes desde** una fecha
  (**ISO `YYYY-MM-DD`** o atajo `90d`/`6m`/`1y`, parseado en `cli/_options.py::parse_since`). **Fuerza
  forward** y transiciona a **`MONITORED`**. `backward + --since` → exit 1; `both + --since` → la ventana
  aplica solo al tramo forward. Sin corpus/estado previo → `DataError` exit 2 (sugiere `b2g seed`). **No
  existe estado `CHAINED`.** El alias `monitor` delega aquí.

**Enricher absorbido en `chain`/`build` (#162):** el `OpenAlexEnricher` (§3) no es verbo propio. La
pasada **refs→DOI** corre automática en `chain`; la pasada **co-citación** (`cited_by`) corre automática
en `build` cuando hay semillas aceptadas (no-op de red sin ellas). Por eso **`build` ya NO es
estrictamente "sin red"** (ADR 0025 enmendado). Ambos suman `data["enrichment"]`. El alias `b2g enrich`
corre ambas pasadas y **NO transiciona**.

**`curate {dump,apply,accept,reject,filter}`** (grupo noun-verb, #155). **La transición la define el
VERBO:** solo **`curate filter`→`FILTERED`**; el resto transversal. **BREAKING:** la forma-flag
`curate --dump`/`--from-csv`/`--all` fue **eliminada sin alias**. Lógica fuente única en
`service/curate.py`.

- **`curate dump`** escribe un CSV revisable offline. **`--out`** override (default
  `<workspace>/exports/curacion.csv`); **`--scope [candidates|seeds|all]`** (default `candidates`:
  `candidate AND NOT is_seed`; `seeds` = `is_seed`; `all` = todo). Sin candidatos → error que sugiere
  `--scope all`/`b2g chain`. Columnas (16, orden estable): `id, source_id, title, year, authors, venue,
  doi, keywords, cited_by_count, references_count, is_seed, openalex_url, scent_score, cluster, decision,
  note` — **editables solo `decision`/`note`**. `cited_by_count`/`references_count`/`scent_score`/`cluster`
  salen vacías (placeholders, no fallan). `data = {csv_path, papers_exported, columns}`.
- **`curate apply <csv>`** aplica decisiones en lote (`accepted`→accept, `rejected`→reject,
  `undecided`→no-op; case-insensitive). **Idempotente** (`decided_at` inyectado en la frontera CLI, R2).
  CSV sin `id`/`decision` o `decision` inválida → `DataError` exit 2. IDs huérfanos → `not_found_count` +
  aviso (no no-op silencioso). `data = {accepted_count, rejected_count, skipped_count, not_found_count,
  total_rows}`. **`note` se ignora en apply** (advisory).
- **`curate accept --ids ... [--by NOMBRE]`** / **`curate reject --ids ... [--by NOMBRE]`** — por ID
  (uno-a-uno o lote). Comparten `accept_papers`/`reject_papers` con los verbos sueltos `accept`/`reject`
  (alias deprecados).
- **`curate filter`** (`--year-gte`/`--year-lte`, `--language`, `--type`, `--min-citations`): aplica
  inclusión/exclusión PRISMA **marcando `rejected`** (no borra) con conteo por paso. **Transiciona a
  `FILTERED`.** Comparte `filter_corpus(store_path, *, year_gte, year_lte, language, type_in,
  min_citations, decided_at)` con el verbo suelto `filter`.

**`build` y `export` separados** (ADR 0021 §B). `build` computa `Networks.quick` (4-5 redes) y escribe
a `<workspace>/networks/<kind>/` (transiciona a `BUILT`); `export --format graphml|csv` **relee** esos
artefactos (`ws.networks_dir`) y los serializa (sin transición). **`export --out-dir`** override
opcional (default `<workspace>/exports/`).

`build` tiene **dos modos**: **quick** (sin `--spec`) y **declarativo** (**`build --spec <redes.yaml>`**:
`load_specs` con clave raíz `networks:` → `Networks.build` por red; helper único `_build_from_spec_file`).
**Ambos transicionan a `BUILT` y sellan `networks/.corpus_hash`** (decisión D1; a diferencia del alias
`networks`, que es transversal). Flags:

- **`--scope [all|accepted|seeds]`** (default `all`): filtra el corpus por curación **antes** de
  proyectar (`Corpus.scoped`, §1.2). `accepted` = `is_seed` + aceptados; `seeds` = solo semillas. El
  `.corpus_hash` se sella con el corpus **filtrado**; `clusters.csv`/`decorate` reflejan ese subset.
  Scope con **0 papers** → **exit 0** + `warning` (no error). **No confundir con `NetworkSpec.scope`**
  (§10, por-red sobre `is_seed`). **`--corpus-scope [all|accepted|seeds_only]`** = alias deprecado
  (oculto en `--help`, vocab interno; precede a `--scope` si se pasan ambos).
- **`--min-weight N`** (solo quick): descarta aristas con peso < N. Con `--spec` se usa el `min_weight`
  por-red del YAML; pasarlo junto a `--spec` emite warning y se ignora.
- **`--thesaurus <archivo>`** (#164): aplica un thesaurus multilingüe (JSON ADR 0011) sobre
  `keywords_id` **antes** de scopear/proyectar, persiste con `persist_replace` (§4.1) y suma
  `data["thesaurus"] = {keywords_mapped, keywords_total, aliases_loaded, applied_at}`. Inexistente/mal
  formado → `DataError` exit 2.
- **`--email` / `--max-citing INT`**: parametrizan la pasada `cited_by` (co-citación; ver Enricher
  absorbido).

**Artefactos por red:** todas escriben `network.graphml` + `metrics.json`; **`clusters.csv` solo las
redes de paper** (`bibliographic_coupling`, `cocitation`) con comunidades (las de
autor/institución/keyword devuelven `[]` y omiten el archivo, por diseño). **Diagnóstico de red-vacía:**
`build` reusa `predict_build_preview` (la **misma** fuente que `status`, no-divergencia por-corpus) y lo
emite en `data["empty_networks"]` (lista de `{kind, reason, fix_command}`, separada de `data["warnings"]`
corpus-level). **`--json.data`:** `networks_built`, `artifacts_dir`, `corpus_hash`, `scope` (token CLI),
`corpus_scope` (vocab interno, backward-compat), `networks` (con `clusters_csv` condicional), `warnings`,
`empty_networks`, `maturity` (ver Apéndice), `enrichment`, `thesaurus` (si se pasó `--thesaurus`).

**`snapshot {create, restore}`** (grupo noun-verb, #163). Fuente única en `service/snapshot.py`. La
transición la define el verbo.

- **`snapshot create`** (= ex `snapshot` plano, BREAKING sin alias): sella una foto reproducible
  (parquet + `manifest.json`, ADR 0017). **`--out-dir`** override opcional (default
  `<workspace>/snapshots/`). **NO transiciona.** `data = {snapshot_dir, corpus_hash, total_papers,
  schema_version, maturity}`.
- **`snapshot restore --from-corpus <parquet>`** (= ex verbo plano `restore`): **rehidrata un corpus ya
  curado SIN red** (lee con `CORPUS_SCHEMA`, `Corpus.from_arrow`, merge+dedup+persist; cero llamadas a
  OpenAlex). **Preserva la curación** (`decision`/`curation_status`/`is_seed`, D3). **Transiciona a
  `FILTERED`** (reusa la transición permisiva `filter`; válida desde cualquier estado, incluido store
  vacío). Parquet inexistente o schema no canónico → `DataError` exit 2. `data = {papers_loaded,
  total_papers, state, round}`. El verbo suelto `restore` es alias deprecado (`command="restore"`).

**`read {list,stats,show,top}`** (grupo noun-verb, #156/#157): lectura pura del corpus (no transiciona).
Lógica en `service/reads.py` (§0.1).

- **`read list`** — filtros AND combinables: `--query TEXT` (substring case-insensitive sobre el
  **título**), `--status {candidate,accepted,rejected}`, `--seeds`/`--candidates` (por `is_seed`),
  `--year INT`. `data = {papers: [{id, title, year, curation_status, is_seed}], count}`.
- **`read stats --group-by {status,year,is_seed}`** (default `status`): conteos agrupados. `data =
  {group_by, total, groups: [{key, count}]}`. `--group-by` inválido → exit 1 (UsageError de `Choice`).
- **`read show --id <ID>`**: delega en `get_paper` (resuelve **id | doi | source_id**, prioridad
  id>doi>source_id, ADR 0036). `data` = la fila completa del corpus (~14 campos). `--id` sin match →
  `DataError` exit 2.
- **`read top`** — la **salida de investigación**: dos bloques sobre redes recomputadas en lectura (**no
  requiere `build`**). **`--top N`/`-n`** (default 10), **`--kind`** (`Choice` sobre los 5 `NetworkKind`,
  **default `bibliographic_coupling`** porque es robusto en el one-shot frío: no necesita
  `chain --forward`). `data = {kind, top, central: [{id, title, degree_centrality, community?}],
  cocitation: [{source, source_title, target, target_title, weight}], reason?, fix_command?, maturity}`.
  `central` = top N nodos de `--kind` por `degree_centrality`; `cocitation` = **SIEMPRE** la red
  cocitation, top N aristas por `weight`. **Honest-empty (exit 0, no error):** cocitación vacía (sin
  `cited_by_id`) → bloque `[]` + `reason`/`fix_command` (de `predict_build_preview`). `--kind` inválido →
  exit 1; `n <= 0` o red que falla genuinamente → `DataError` exit 2.

**`skill add [--user|--project] [--force]`** (comando meta, ADR
[0039](decisiones/0039-skill-comando-meta-distribucion.md)): **instala la skill de Claude Code end-user**
que enseña al agente a usar bib2graph (los 10 verbos + el one-shot `init→seed→chain→build→read`). La
skill viaja **vendoreada en el wheel** bajo `src/bib2graph/skill/` (`SKILL.md` + `reference/`, fuente
commiteada vía `packages = ["src/bib2graph"]`): el version-lock skill==cli garantiza que la skill enseñe
los verbos que el CLI expone. `skill add` **copia** la skill al directorio del cliente: **`--user`**
(default) → `~/.claude/skills/bib2graph/`, **`--project`** → `.claude/skills/bib2graph/`. **Idempotente**;
si el destino existe y difiere falla accionable y **`--force`** pisa. **Funciona SIN workspace** y emite
`--json` `schema="1"` **sin transición de FSM**. La skill es markdown sin dependencias Python (la IA está
en el Claude Code del usuario, no en el producto; ADR 0022). `data = {install_path, scope, installed,
already_present, skill_md, reference_dir, how_to}`.

**`resolve`** (alias deprecado): resuelve los DOIs del corpus a `source_id` de OpenAlex (cierra el GAP del
flujo BibTeX: sin `source_id`, `chain` da 0). Filtra `doi != NULL AND source_id IS NULL`, consulta
OpenAlex (`OpenAlexSource.fetch_dois_to_openalex_ids` vía `service/resolve.py::resolve_dois`) y puebla
`source_id`; **idempotente**, persiste con `persist_replace`. **`--email`** (polite pool). `data =
{resolved, total_with_doi, already_resolved, total_papers}`. **NO transiciona.** Red caída → `NetworkError`
exit 4; store bloqueado → `StoreError` exit 5. Encadenable en `seed --from-bib --resolve`.

**`networks --spec` / `inspect`** (alias deprecados): `networks --spec <redes.yaml>` construye redes desde
el YAML pero **NO transiciona ni sella `.corpus_hash`** (ad-hoc transversal) — usá `build --spec`
(paso BUILD pleno). `inspect` lo absorben `read show` (papers) y `status` (manifest/FSM).

**`--workspace` global (OPCIONAL).** Va en el grupo `b2g`, **antes** del subcomando. **`--store` fue
ELIMINADA** (#75, BREAKING): pasarla da el error estándar de Click (`No such option`). El modo degenerado
(`.duckdb` suelto) **dejó de existir**; un `.duckdb` legacy se adopta con `b2g init .`. **Resolución
ambiente** (precedencia): (1) `--workspace` explícito, (2) `B2G_WORKSPACE` (env), (3) **walk-up** del cwd
buscando `workspace.json`. Sin ninguno → error accionable que sugiere `b2g init`.

**Transiciones automáticas del ciclo** (ADR 0021 §F): `seed`→`SEEDED` (con estado previo = `reseed`,
ronda++), `chain`→`FORAGED`, `chain --since`→`MONITORED`, `curate filter`→`FILTERED`, `build`→`BUILT`,
`snapshot restore`→`FILTERED`. El resto (`read`, `export`, `snapshot create`, `status`, `validate`,
`curate {dump,apply,accept,reject}`, los alias `enrich`/`networks`/`resolve`) **no transiciona**. El
estado destino lo dicta `bib2graph.cycle.apply_transition` (fuente única; los comandos no hardcodean el
destino).

**Envelope JSON común y versionado** (ADR 0021 §C): en modo `--json`, cada subcomando emite **un objeto
JSON** con `schema="1"`:

```json
{
  "schema": "1",
  "ok": true,
  "command": "seed",
  "exit_code": 0,
  "data": { },
  "warnings": [],
  "error": null
}
```

En error conocido: `ok=false`, `data={}`, `error={"code": <CODE>, "message": <accionable>}`. Los exit
codes se mapean **por tipo de error** (ADR 0021 §D): `DataError`→2, `ImportError`/`DependencyError`/
`NotImplementedError`→3, `httpx.HTTPError`→4, `StoreLockedError`/`OSError`→5. `AttributeError` **no** se
mapea (un bug real no se disfraza de "capacidad faltante"); la capacidad-de-source-faltante se convierte
en `DependencyError` con un **pre-check `hasattr` en el comando** (p. ej. `chain` antes del `Forager`).

**Borde: el error de uso sale SIN envelope.** Ante una opción requerida faltante, una opción desconocida
(p. ej. `--store`) o ningún workspace resoluble, Click aborta el parseo **antes** de entrar al comando:
mensaje de uso en **stderr** + exit 1, **sin** envelope. El envelope solo cubre errores **dentro** de la
ejecución del comando.

**stdout puro en modo JSON (ENFORCED, #151).** En modo JSON (por `--json` o `B2G_JSON`) stdout emite
**exactamente una línea** (el envelope), también en el camino de error (`ok=false` → envelope en stdout).
El texto humano va a **stderr**.

**`B2G_JSON` — modo JSON por entorno (#151).** Además de `--json` (post-verbo: `b2g <cmd> --json`), el
modo JSON se activa con `B2G_JSON` truthy (`1`/`true`/`yes`, case-insensitive) en **todos** los comandos.
Precedencia: `--json` explícito gana; no existe `--no-json`. Recomendación agents-first: `export
B2G_JSON=1` una vez y correr el ciclo sin repetir el flag. Aditivo: envelope/exit codes/FSM no cambian.

**Apéndice — bloque `maturity` del one-shot (#160, ADR 0037 §f).** Los artefactos del camino **one-shot**
llevan un bloque **aditivo** `data["maturity"]` que **se autodeclara borrador sin pulir** (honestidad por
construcción), para que ni un agente que optimiza por `exit 0` ni un humano apurado confundan un one-shot
con un resultado terminado. **`schema="1"` intacto.**

```json
"maturity": {"curated": false, "scope": "all", "saturated": false, "empty_networks": []}
```

**Forma estable: SIEMPRE 4 claves** (orden y tipos fijos):

| clave | tipo | regla de derivación |
|---|---|---|
| `curated` | `bool` | `true` si el corpus **completo** (pre-scope) tiene ≥1 paper con `curation_status` ∈ {`accepted`, `rejected`}. Independiente del scope y del FSM. |
| `scope` | `str` \| `null` | el **token CLI** (`all`/`accepted`/`seeds`, no el vocab interno `seeds_only`). En `snapshot create` y `read top` es `"all"`. |
| `saturated` | `bool` | **`false` constante** en one-shot (no sobre-afirmar; gancho futuro: convergencia de `referenced_refs_count()`). |
| `empty_networks` | `list[str]` | **solo los tokens `kind`** de las redes vacías (`reason`/`fix_command` no se duplican: viven en `data["empty_networks"]`). |

Aparece **siempre** en `build` (incl. early-return de corpus vacío), `snapshot create` y `read top`;
**ausente** en `read list`/`read stats`/`read show`. Lo calcula la función pura
`service.maturity.compute_maturity(corpus, *, scope, empty_network_kinds)` (§0).

### Avisos de deprecación (ADR [0038](decisiones/0038-destino-verbos-huerfanos-0037.md) P1)

La consolidación 0.10.0 retira solapamientos **sin romper de una**: los nombres viejos siguen
funcionando durante 0.10.x con un **aviso de deprecación**, y **se eliminan en 0.11.0** (criterio por
versión, no fecha). El helper único es `cli/_deprecation.py::emit_deprecation`.

**Formato canónico** (exacto):

```text
AVISO: '<viejo>' está deprecado y se eliminará en 0.11.0; usá '<nuevo>'.
```

- **Canal: stderr SIEMPRE** (modo humano y modo `--json`), nunca stdout — preserva el stdout puro de
  una línea-envelope (#151). En `--json`, el mismo mensaje se propaga además al **`warnings[]`
  top-level** del envelope (no a `data`), enhebrado vía `build_envelope(..., warnings=[msg])`.
- **No cambia el contrato:** el alias delega en la misma lógica de servicio (fuente única) y conserva
  su `command`/envelope; `schema="1"`, exit codes y FSM intactos.

**Los 9 verbos deprecados** (alias vivo con aviso → forma canónica):

| Alias deprecado | Forma canónica |
|---|---|
| `b2g accept` | `b2g curate accept` |
| `b2g reject` | `b2g curate reject` |
| `b2g filter` | `b2g curate filter` |
| `b2g inspect` | `b2g read show` (papers) / `b2g status` (manifest/FSM) |
| `b2g monitor` | `b2g chain --since` |
| `b2g networks` | `b2g build --spec` |
| `b2g enrich` | `b2g chain` (refs→DOI) + `b2g build` (co-citación) |
| `b2g restore` | `b2g snapshot restore` |
| `b2g resolve` | `b2g seed --resolve` |

**Además** (mismo corte 0.11.0):

- **Entry-point `bib2graph` → `b2g`** (`main_bib2graph_alias` emite el aviso y delega en `main`).
- **Opción `build --corpus-scope` → `build --scope`** (deprecación de **flag**, oculta en `--help`;
  el vocab viejo `seeds_only` sigue aceptado y tiene precedencia si se pasan ambos).

**`thesaurus` NO está en esta lista:** se **retiró por completo** (sin alias). Su capacidad vive como
`b2g build --thesaurus <archivo>` (#164, ver §`build`).

---

## 0. Capa de servicios `service/` — contrato neutral compartido (ADR 0028)

`src/bib2graph/service/` es la **capa de servicios neutral** de la que el CLI es un adaptador delgado
(ADR [0028](decisiones/0028-arquitectura-gui-api-capa-servicios.md), inversión de dependencia ports &
adapters). Aloja **el contrato** (envelope versionado + jerarquía de errores + mapeo error→código) y
las **lecturas read-only del corpus** (`service/reads.py`, §0.1, que consume el grupo CLI `read`). El
contrato externo del CLI (envelope `schema="1"`, exit codes 0–5, ADR 0021) **no cambia**.

**Invariante de neutralidad de transporte (estricta).** `service/` es **agnóstica de transporte**:
**sin `print`, `sin sys.exit`, sin Click, sin FastAPI**. Es el límite que mantiene el contrato
reutilizable por cualquier adaptador. El I/O (`emit`/`emit_human` en `cli/_envelope.py`,
`handle_errors`/`_emit_error_envelope` en `cli/_errors.py`) **se queda en el adaptador CLI**.

**Contrato público** (re-exportado desde `bib2graph.service.__init__`):

```python
# service/envelope.py — envelope JSON común y versionado
ENVELOPE_SCHEMA_VERSION: str = "1"   # versión del contrato del envelope (ADR 0021)

def build_envelope(
    *,
    command: str,
    ok: bool,
    data: dict[str, Any],
    exit_code: int,
    warnings: list[str] | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Construye el envelope JSON estable del contrato (schema="1").
    {schema, ok, command, exit_code, data, warnings, error}. Función pura, sin I/O."""


# service/errors.py — jerarquía de errores tipados (ADR 0021)
class B2GError(Exception):
    """Base de los errores accionables. Atributos de clase: exit_code: int, code: str;
    instancia: .message. Subclases con su (exit_code, code):"""
    exit_code: int = 1
    code: str = "B2G_ERROR"

class UsageError(B2GError):      exit_code = 1; code = "USAGE_ERROR"       # uso (opción faltante/inválida)
class DataError(B2GError):       exit_code = 2; code = "DATA_ERROR"        # schema/ids/filtro inválido
class DependencyError(B2GError): exit_code = 3; code = "DEPENDENCY_ERROR"  # ImportError / capacidad faltante
class NetworkError(B2GError):    exit_code = 4; code = "NETWORK_ERROR"     # httpx.HTTPError / timeout
class StoreError(B2GError):      exit_code = 5; code = "STORE_ERROR"       # store/snapshot bloqueado o corrupto


def code_for(exc: BaseException) -> int:
    """Mapeo PURO error→exit code (0–5, ADR 0021), sin I/O ni sys.exit:
    B2GError → su .exit_code; OSError (incl. StoreLockedError) → 5; ImportError → 3;
    httpx.HTTPError → 4. Excepción no mapeada → TypeError (el llamador decide).
    Lo usan la capa de servicio y los adaptadores para derivar exit code / HTTP status
    sin duplicar la política."""


# service/maturity.py — bloque maturity del one-shot (#160, ADR 0037 §f / 0038 P3)
def compute_maturity(
    corpus: Corpus, *, scope: str | None, empty_network_kinds: list[str]
) -> dict[str, Any]:
    """Bloque maturity para el --json de build/snapshot create/read top (ver Apéndice maturity).
    Función PURA, sin I/O. Devuelve EXACTAMENTE 4 claves:
    {curated: bool, scope: str|None, saturated: bool, empty_networks: list[str]}.
    curated = corpus tiene ≥1 paper con curation_status ∈ {accepted, rejected};
    saturated = False constante (one-shot never over-claims; gancho futuro referenced_refs_count);
    empty_networks = solo los kind (reason/fix_command NO se duplican)."""
```

**Adaptadores (el contrato se re-exporta, no se duplica).** `cli/_envelope.py` y `cli/_errors.py`
hacen `from bib2graph.service... import ...` y re-exportan los **mismos objetos**, así que los imports
existentes del CLI y los tests (`from bib2graph.cli._envelope import build_envelope`,
`from bib2graph.cli._errors import B2GError, DataError, …`) siguen funcionando sin cambios. El
decorador `handle_errors` (CLI) conserva su propia escalera `try/except` por tipo de error + el
`sys.exit` y la emisión del envelope de error; `code_for` es el mapeo puro disponible para cualquier
adaptador. El mapeo de `code_for` y el de `handle_errors` describen la **misma política** (ADR 0021 §D).

### 0.1 Lecturas de servicio `service/reads.py` — lecturas read-only del corpus

`src/bib2graph/service/reads.py` expone las **lecturas read-only del corpus** que consume el **grupo
CLI `read`** (`list_papers`, `corpus_stats`, `get_paper`, `get_top` — §Grupo `read`), re-exportadas
desde `bib2graph.service.__init__`. Cada una recibe un **`Workspace` ya resuelto** (la resolución
ambiente vive en el adaptador CLI, ADR 0029), abre el store **read-only**, y devuelve un
`dict`/`list[dict]` **serializable** o lanza un `B2GError` tipado. **Sin red, sin mutación, sin
transición de ciclo**; determinismo R2 (mismo corpus → misma lectura).

El módulo conserva además funciones de lectura más ricas (`get_workspace`, `list_rounds`, `get_scent`,
`get_network`, `compare_rounds`) que hoy ningún comando consume (su poda opcional es trabajo de
limpieza, [#191](https://github.com/complexluise/bib2graph/issues/191)), más la **resolución inversa
id→DOI/URL** (`resolve_doi`, `resolve_url`; [#212](https://github.com/complexluise/bib2graph/issues/212),
aditiva, devuelven `None` sin lanzar). Decisiones de modelado:
**ronda = snapshot sellado** (no el contador `loop_round`), `get_scent` = **score de acoplamiento real
+ vecinos**, `get_network` = **red de la ronda viva recomputada**.

```python
def get_workspace(ws: Workspace) -> dict[str, Any]:
    """Estado del workspace activo. Devuelve:
    {name, root, created_at, bib2graph_version, source, loop_state (str|None),
     round (int), total_papers (int), counts_by_status (dict[str,int]),
     transitions_available (list[str]), curation_available (list[str]),
     networks_cache_stale (bool)}. Raises StoreError."""

def list_rounds(ws: Workspace) -> list[dict[str, Any]]:
    """Snapshots sellados (vía Workspace.list_snapshots()) + una entrada sintética "live".
    Por snapshot: {id, corpus_hash, created_at, total_papers, schema_version}.
    Entrada viva: {id="live", round, loop_state, total_papers}. Raises StoreError.
    Ronda = snapshot (B-G2-1 Opción A); el contador loop_round se ve en la entrada "live"."""

def get_paper(ws: Workspace, ident: str) -> dict[str, Any]:
    """Fila del corpus (CORPUS_SCHEMA) resuelta por identidad source-agnóstica
    (ADR 0036): `ident` matchea contra **id | doi | source_id**, con prioridad
    `id` > `doi` > `source_id` (devuelve el primer match). Devuelve:
    {id, source_id, doi, title, year, abstract, is_seed, curation_status,
     authors_raw, authors_id, keywords_id, references_id, cited_by_id,
     provenance (list, parseada del JSON)}.
    Raises DataError si `ident` no matchea ningún id/doi/source_id;
    StoreError si el store falla. `read show --id` delega en esta lectura
    (§Convenciones CLI · grupo `read`)."""

def get_scent(ws: Workspace, paper_id: str) -> dict[str, Any]:
    """Score de acoplamiento bibliográfico real + vecinos compartidos (B-G2-2). Devuelve:
    {paper_id, score (int = nº de corpus-papers con >=1 referencia compartida),
     coupling (list[{paper_id, title, weight}], ordenada por peso desc),
     references (list[{paper_id, title}] resueltas al corpus),
     cited_by (list[{paper_id, title}] resueltos al corpus)}.
    Raises DataError si el id no existe; StoreError si el store falla."""

def get_network(ws: Workspace, kind: str) -> dict[str, Any]:
    """Red de la ronda VIVA recomputada con Networks.build + decorate (B-G2-3; función pura,
    Louvain seeded por corpus_hash, R2). `kind` en NetworkKind del núcleo
    (bibliographic_coupling, cocitation, author_collab, institution_collab,
     keyword_cooccurrence). Devuelve:
    {nodes (list[{id, label, degree_centrality, community?, year?, is_seed?, curation_status?}]),
     edges (list[{source, target, weight}]),
     metrics ({n_nodes, n_edges, density, num_components, avg_clustering, n_communities})}.
    Raises DataError si kind es inválido o la red no se puede construir; StoreError si el store falla."""

def compare_rounds(ws: Workspace, round_a: str, round_b: str) -> dict[str, Any]:
    """EL DIFERENCIADOR (ADR 0027). Diff entre dos snapshots por Col.ID; "live" usa el corpus vivo.
    Devuelve:
    {round_a, round_b, added_paper_ids (ids en b no en a), removed_paper_ids (ids en a no en b),
     mutated_hubs ([], DIFERIDO — requiere redes por snapshot, B-G2-3),
     metrics_change (list[{metric, before, after}], hoy con n_papers; las métricas por red
       solo aparecen si ambos snapshots tienen networks/<kind>/metrics.json, que hoy no se
       materializa por snapshot)}.
    Raises DataError si un snapshot no existe o no tiene corpus.parquet; StoreError si el store falla."""


# --- Lecturas detrás del grupo CLI `read` (#156/#157; ver §Grupo `read`) ---

def list_papers(ws: Workspace, *, query=None, status=None, is_seed=None, year=None) -> dict[str, Any]:
    """Lista mínima del corpus con filtros AND (todos opcionales). Devuelve:
    {papers: [{id, title, year, curation_status, is_seed}], count: int}.
    query = substring case-insensitive sobre el título; status = curation_status exacto;
    is_seed True/False; year exacto. Raises StoreError. (Detrás de `read list`.)"""

def corpus_stats(ws: Workspace, *, group_by="status") -> dict[str, Any]:
    """Conteos agrupados por status (default) | year | is_seed. Devuelve:
    {group_by, total, groups: [{key, count}]}. Raises DataError si group_by inválido;
    StoreError si el store falla. (Detrás de `read stats`.)"""

def get_top(ws: Workspace, *, n=10, kind="bibliographic_coupling") -> dict[str, Any]:
    """Salida de investigación (#157): nodos centrales + pares de co-citación con título,
    sobre redes recomputadas (NO requiere `build`; mismo camino que get_network). Devuelve:
    {kind, top, central: [{id, title, degree_centrality, community?}],
     cocitation: [{source, source_title, target, target_title, weight}], reason?, fix_command?,
     maturity}.
    `central` = top n nodos de la red `kind` por degree_centrality desc (título completo en redes
    de paper; label de entidad en author/institution/keyword). `cocitation` = SIEMPRE la red
    cocitation, top n aristas por weight desc.
    Honest-empty: co-citación vacía (sin cited_by_id) → bloque [] + reason/fix_command
    (de predict_build_preview), NO error. `maturity` (aditivo, #160, ver Apéndice `maturity`):
    SIEMPRE presente, scope="all", empty_networks=["cocitation"] si la co-citación quedó vacía.
    Raises DataError si kind inválido, n <= 0, o la red
    falla genuinamente; StoreError si el store falla. (Detrás de `read top`.)"""


# --- Resolución inversa id→DOI/URL (#212, opción 1; sin red, sobre el corpus cargado) ---

def resolve_doi(ws: Workspace, paper_id: str) -> str | None:
    """DOI desnudo del paper con `Col.ID == paper_id`, o `None`. Devuelve `None`
    (NO lanza DataError) cuando el id no existe, el paper no tiene DOI, o el DOI es
    cadena vacía `""` (mismo criterio de "vacío = ausente" que networks/decorate.py).
    Sin red: opera sobre el corpus ya cargado. Raises StoreError si el store falla."""

def resolve_url(ws: Workspace, paper_id: str) -> str | None:
    """URL canónica `https://doi.org/<doi>` del paper, o `None` en los mismos casos
    que resolve_doi (id inexistente / sin DOI / DOI vacío). Deriva vía
    `doi_to_url(resolve_doi(...))`. Sin red. Raises StoreError si el store falla.
    `doi_to_url(doi: str|None) -> str|None` (bib2graph.constants) es la FUENTE ÚNICA
    de la derivación DOI→URL, compartida con la decoración del atributo `url` de redes
    (#209, ver §8 nota) — sin drift."""
```

**Nota de fidelidad al núcleo.** Las lecturas no inventan campos que el núcleo no sostiene:
`get_paper` expone `authors_raw`/`authors_id` (no objetos autor con ORCID), `get_network` no entrega
`modularity` ni un id de red persistido, y `compare_rounds` deja `mutated_hubs=[]` mientras no haya
redes por snapshot.

## 1. Modelo de dominio — `Corpus`

Wrapper sobre un **`TabularBackend`** (Protocol) cuyo contenido es una **tabla Arrow** (`pa.Table`)
con schema fijo por paper, validada con **Pydantic v2** (ADR 0006). El `Corpus` **delega las
mutaciones** al backend (ADR [0015](decisiones/0015-corpus-tabular-backend.md)): los métodos
siguen devolviendo un `Corpus` (semántica de valor a nivel de API), pero `accept`/`reject`/
`merge`/`add_paper` no reconstruyen la tabla entera en memoria — piden la operación al backend.

- **`InMemoryBackend`** — puro, sin I/O: *working set* efímero y backend de los **tests** (el
  núcleo se testea sin DuckDB). Es el comportamiento del Hito 1, movido al backend.
- **`DuckDBBackend`** — la **biblioteca viva** (ADR 0009): archivo `.duckdb` o `:memory:`,
  mutaciones por SQL `UPDATE`/`MERGE` por `id`. Es el **backend por defecto** con persistencia, y
  donde vive el `LoopState` (ADR [0016](decisiones/0016-maquina-estados-lazo.md)).

Las reglas de identidad/hash/merge (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md),
D1/D2/D3) son **contrato que cada backend cumple** (InMemory en Python, DuckDB en SQL).
`corpus.to_arrow()` es el puente estable a los proyectores/analizadores puros (§7–§8): **solo
cambia el contenedor, no el núcleo de análisis**.

**Símbolos públicos del Hito 1/1.5** (`from bib2graph import ...`): `Corpus`, `Manifest`,
`CorpusSnapshot`, `SchemaError` (la excepción de contrato que lanzan `Corpus.from_arrow()` y
`add_paper()` al violarse el schema canónico), y —del rework del Hito 1.5— `TabularBackend`
(Protocol) e `InMemoryBackend` (ver §1.4).

### 1.1 Schema de la tabla (columnas canónicas)

| Columna | Tipo Arrow | Nullable | Notas |
|---|---|---|---|
| `id` | `string` | no | id interno estable (hash de `doi`/`source_id`; ver §1.1 *Identidad*, ADR [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md)) |
| `source_id` | `string` | sí | id del **motor de extracción** que entregó el paper (p. ej. `W...` para OpenAlex). Agnóstico al motor (ADR [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md)): el nombre del motor vive en `provenance.source`, no en la columna |
| `doi` | `string` | sí | DOI normalizado |
| `title` | `string` | no | título completo |
| `year` | `int32` | sí | año de publicación |
| `abstract` | `string` | sí | |
| `source` | `string` | sí | revista / venue |
| `language` | `string` | sí | código ISO 639-1 |
| `publisher` | `string` | sí | atributo, no entidad |
| `research_areas` | `list[string]` | — | atributos, no entidades |
| `is_seed` | `bool` | no | `True` si entró por la ecuación/semilla; `False` si lo trajo el chaining |
| `curation_status` | `string` | no | `candidate` / `accepted` / `rejected` (biblioteca viva) |
| `provenance` | `string` | sí | JSON: **lista de eventos** (log append-only). Cada evento `{action, equation_id, chaining_hop, source, fetched_at, decided_by, decided_at}`. Ver nota abajo (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md)) |
| `authors_raw` / `authors_id` | `list[string]` | — | nombres crudos / ids canónicos (ORCID si hay) |
| `authors_affiliations` | `list[string]` | — | **per-autor** (de OpenAlex `authorships`); habilita geografía/asortatividad |
| `keywords_raw` / `keywords_id` | `list[string]` | — | crudos / canónicos (post-thesaurus) |
| `institutions_raw` / `institutions_id` | `list[string]` | — | crudos / ids canónicos (ROR si hay) |
| `references_id` | `list[string]` | — | obras citadas (ids OpenAlex); **vienen de OpenAlex**, no de un Enricher |
| `references_doi` | `list[string]` | — | refs resueltas a DOI (las puebla un Enricher opt-in; OpenAlex las da como URLs internas) |
| `cited_by_id` | `list[string]` | — | citantes (ids OpenAlex); habilita forward chaining y co-citación |

El schema exacto vive en `bib2graph.schemas`. La validación se hace en `Corpus.from_arrow()` y en
cada `Source.seed()/load()`.

> **Tabla lateral `external_ids(paper_id, engine, id)`** (ADR
> [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md), opción C — **infra presente, sin
> poblar**): el backend expone `external_ids_for(paper_id)`/`all_external_ids()` para registrar 1↔N los
> IDs que cada motor asignó al mismo paper (unificados por DOI). Su consumo (cruce cross-motor) está
> diferido a la llegada del 2º motor (#120); hoy la identidad/dedup se resuelven solo por el `id`
> canónico (DOI primero).

**`provenance` es un log append-only** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md),
D4), no un objeto único: la columna `string` guarda un JSON que es una **lista de eventos**. Cada
evento tiene la forma:

```json
{
  "action": "fetched | accepted | rejected",
  "equation_id": "string | null",
  "chaining_hop": "int | null",
  "source": "string | null",
  "fetched_at": "ISO8601 | null",
  "decided_by": "string | null",
  "decided_at": "ISO8601 | null"
}
```

`accept()`/`reject()` **agregan** un evento (`action='accepted'`/`'rejected'`, con `decided_by` y
`decided_at`) sin borrar los previos. `None`/cadena vacía equivalen a "sin eventos".

**`id` estable y determinista** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md), D1;
precedencia invertida por ADR [0036](decisiones/0036-identidad-source-id-agnostica-doi-ancla.md), D1'):
`id = f"{prefix}:{sha256(valor)[:16]}"` con precedencia `doi` normalizado (`doi:`) → `source_id`
(`src:`) → `title+year` (`tt:`). El **DOI es el ancla universal e interoperable entre motores** (un
paper con DOI tiene el mismo `id` venga de OpenAlex, de Semantic Scholar o de un `.bib`); `source_id`
es el fallback para papers sin DOI, antes de caer a `title+year` (frágil). El mismo paper produce el
mismo `id` entre corridas; es la base de la dedup en `merge` y en la biblioteca viva.

### 1.2 `Corpus` (wrapper)

```python
class Corpus:
    """Wrapper sobre un TabularBackend + un Manifest (ADR 0015).

    Lo que circula por el pipeline: Source lo siembra, el Forager lo expande,
    el humano lo cura, el Preprocessor lo normaliza, el backend lo persiste (biblioteca
    viva), los Projectors lo consumen vía to_arrow(). Las mutaciones se DELEGAN al
    backend (InMemoryBackend puro / DuckDBBackend por defecto): la API mantiene
    semántica de valor (devuelve Corpus), pero no copia la tabla entera en memoria.
    """
    manifest: Manifest

    @classmethod
    def from_arrow(cls, table: pa.Table, *, backend: "TabularBackend | None" = None) -> "Corpus":
        """Valida con Pydantic y construye el Corpus sobre `backend` (default InMemoryBackend).
        Falla ruidoso si el schema no coincide."""

    def to_arrow(self) -> pa.Table:
        """Materializa el contenido del backend como pa.Table. Puente a los proyectores puros."""
    def seeds(self) -> pa.Table:        """Vista is_seed == True."""
    def candidates(self) -> pa.Table:   """Vista curation_status == 'candidate'."""
    def accepted(self) -> pa.Table:     """Vista curation_status == 'accepted' (la biblioteca curada)."""

    def scoped(self, scope: str) -> "Corpus":
        """Vista PURA por estado de curación: devuelve un Corpus NUEVO con el subconjunto de filas
        (no muta el original). Valores: `'all'` = corpus completo; `'accepted'` = `is_seed == True`
        OR `curation_status == 'accepted'`; `'seeds_only'` = `is_seed == True`. Scope inválido →
        `ValueError` accionable. Determinista: dos llamadas con el mismo scope dan corpora con el
        mismo `corpus_hash` (subset estable). `'all'` reusa el backend; los otros materializan el
        filtro en un `InMemoryBackend`. Lo usa `b2g build --scope` (vocab CLI `seeds`→`seeds_only`;
        alias deprecado `--corpus-scope` usa este vocab interno) para sellar el hash del
        corpus FILTRADO. Issue #56 / #159. **NO confundir con `NetworkSpec.scope`** (§10): aquel es un
        eje por-red (`full`/`seeds_only`) sobre `is_seed`; `scoped()` filtra el corpus entero por
        curación antes de proyectar."""

    def with_manifest(self, manifest: Manifest) -> "Corpus":
        """Devuelve un Corpus nuevo con el MISMO contenido y otro Manifest (semántica de valor:
        el original no muta). No toca el backend; el `corpus_hash` no cambia (el hash es sobre la
        tabla, no sobre el Manifest). API canónica para que las costuras (Source/Forager/Filter)
        sellen su metadata —p. ej. `OpenAlexSource.seed()` puebla `openalex_version`/`equations`—
        sin reconstruir el corpus. v1 (Hito 4)."""

    def add_paper(self, row: dict) -> "Corpus":
        """Valida la fila (PaperRow) y agrega el paper. Calcula `id` (D1) si no viene."""
    def merge(self, other: "Corpus") -> "Corpus":
        """Combina deduplicando por `id` (idempotente). Combinación por campo: escalar no-nulo
        gana (ambos no-nulos → `other`); columnas de lista = unión deduplicada (preserva `None`);
        `curation_status` por decisión humana más reciente (`provenance.decided_at`), fallback
        `accepted`>`rejected`>`candidate`; `provenance` = unión de eventos únicos (log).
        Orden de filas: **primera aparición** (filas de `self` en orden, luego las nuevas de
        `other`). Ver ADR 0013 (D3)."""
    def accept(self, ids: list[str], *, by: str = "human", decided_at: datetime | None = None) -> "Corpus":
        """Marca papers como 'accepted' y AGREGA un evento al log de provenance. Devuelve Corpus nuevo.
        `decided_at` se inyecta desde la frontera CLI (Hito R2, ADR 0017); `None` → el backend usa
        `datetime.now(UTC)` como fallback de librería. El `decided_at` NO entra al `corpus_hash`."""
    def reject(self, ids: list[str], *, by: str = "human", decided_at: datetime | None = None) -> "Corpus": ...
    def materialize(self, view: Literal["author", "keyword", "institution"]) -> pa.Table: ...
    def snapshot(self, path: Path) -> "CorpusSnapshot":
        """Exporta una FOTO sellada del estado actual (parquet + manifest.json) para reportar/
        reproducir. CALCULA el `corpus_hash` real (D2) y lo escribe en el Manifest del snapshot.
        NO es la persistencia (eso es el Store DuckDB); es un export derivable."""

    def __eq__(self, other: object) -> bool:
        """Igualdad canónica vía `corpus_hash` (D2): mismo contenido semántico, insensible al
        orden de filas y al orden interno de las columnas de lista; no compara el Manifest.
        Robusta ante cualquier `PYTHONHASHSEED`. Ver ADR 0013."""
```

**Notas de contrato** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md)):

- **`__eq__` es por `corpus_hash`, no por `pa.Table.equals`:** dos `Corpus` con el mismo contenido en
  distinto orden de filas (o de listas) son iguales. El `corpus_hash` **excluye `provenance`/timestamps**
  (identidad = contenido bibliográfico; la procedencia audita, no identifica) pero **incluye
  `curation_status`** (contenido curado), nunca campos volátiles del Manifest (D2).
- **`merge` emite filas en orden determinista** (primera aparición): habilita diffs y snapshots
  reproducibles. Es idempotente: `c.merge(c) == c`.

**Backend y estado del lazo** (ADR [0015](decisiones/0015-corpus-tabular-backend.md) /
[0016](decisiones/0016-maquina-estados-lazo.md)):

- **Las mutaciones se delegan al `TabularBackend`.** D1/D2/D3 son contrato que cada backend cumple
  (InMemory en Python, DuckDB por SQL). El `corpus_hash` (D2) se computa siempre sobre `to_arrow()`.
- **El `CycleState`** (`SEEDED → FORAGED → FILTERED → BUILT → MONITORED`, transiciones permisivas) vive
  en el **backend persistente** (`DuckDBBackend`), no en el `Corpus` efímero (tabla `loop_state_log`
  append-only; estado actual = última fila), expuesto vía `loop_state()`/`set_loop_state()` (§4) y
  `b2g status`.

### 1.3 `Manifest` y `CorpusSnapshot`

```python
class Manifest(BaseModel):
    """Metadatos del Corpus. Se serializa a manifest.json junto al parquet del snapshot."""
    # Obligatorios (sin default) — D5
    schema_version: str
    corpus_hash: str
    lib_version: str
    created_at: datetime
    # Con default — D5
    openalex_version: str | None = None          # versión/fecha del snapshot de OpenAlex usado
    equations: list[EquationRef] = []            # ecuaciones + query OpenAlex ejecutada + reporte de traducción
    chaining: ChainingParams | None = None       # profundidad, topes, dirección
    preprocessors: list[PreprocRef] = []         # normalize + thesaurus aplicados
    filters: list[FilterStep] = []               # criterios incl/excl con conteos (flujo PRISMA)
    enrichers: list[EnricherRef] = []            # opcional (resolución de refs / 2º nivel)

class CorpusSnapshot:
    """Carpeta con corpus.parquet + manifest.json: EXPORT sellado del estado vivo en un instante.
    Reproducible y versionable (git-lfs / DVC). No es la biblioteca viva, es su foto."""
    path: Path
    manifest: Manifest

    @property
    def corpus(self) -> Corpus: ...
```

**Notas de contrato** (ADR [0013](decisiones/0013-identidad-hash-merge-corpus.md); D5/D6):

- **`corpus_hash` se calcula al sellar:** el Manifest en memoria lleva `corpus_hash=""` (placeholder);
  el hash real (D2) se computa en `snapshot()` y vive en `CorpusSnapshot.manifest`.
- **Obligatorios** (D5): `schema_version`, `corpus_hash`, `lib_version`, `created_at`; el resto con
  default. Si `importlib.metadata` no resuelve la versión instalada, `lib_version = "unknown"` (no
  `"0.0.0"` inventado — honesto sobre la reproducibilidad).
- **`schema_version`** (D6): se escribe y round-tripea; el rechazo por incompatibilidad + migraciones
  sobre el store vivo es futuro.

### 1.4 `TabularBackend` (Protocol) e `InMemoryBackend`

El **contenedor** del `Corpus` es un `TabularBackend` (Protocol `@runtime_checkable`); el `Corpus`
**delega** en él (ADR [0015](decisiones/0015-corpus-tabular-backend.md)). El núcleo depende **solo
del Protocol** (no de `duckdb`). Las **mutaciones tienen semántica de valor**: cada operación
devuelve una **instancia nueva** del backend; la original no muta. `id` ya viene calculado por
`Corpus.add_paper` (D1 se valida antes de delegar). Las reglas D1/D2/D3 (ADR
[0013](decisiones/0013-identidad-hash-merge-corpus.md)) son **contrato de este Protocol**: cada
implementación las cumple a su manera (InMemory en Python, DuckDB en SQL).

```python
@runtime_checkable
class TabularBackend(Protocol):
    """Respalda el contenido del Corpus. Cumple D1/D2/D3 (ADR 0013).
    Implementaciones: InMemoryBackend (puro, tests) / DuckDBBackend (biblioteca viva, Hito 3)."""

    def to_arrow(self) -> pa.Table: ...
        # Contenido completo como tabla Arrow canónica. Puente a los proyectores puros.
    def add_paper(self, row: dict) -> "TabularBackend": ...
        # `id` ya calculado y fila ya validada por Corpus.add_paper. Devuelve backend nuevo.
    def merge(self, other_table: pa.Table) -> "TabularBackend": ...
        # Fusión D3: orden por primera aparición (filas de self, luego nuevas), dedup por `id`.
    def apply_curation(self, ids: list[str], *, action: str, by: str,
                       decided_at: str | None = None) -> "TabularBackend": ...
        # accept/reject: AGREGA un evento al log `provenance` (action/decided_by/decided_at).
        # `decided_at` (ISO8601 UTC) inyectado desde la frontera (Hito R2, ADR 0017);
        # `None` → fallback `datetime.now(UTC)` (uso como librería). NO entra al corpus_hash.
    def filter_view(self, view: Literal["seeds", "candidates", "accepted"]) -> pa.Table: ...
        # Vista filtrada (is_seed / curation_status == 'candidate' | 'accepted').
    def corpus_hash(self) -> str: ...        # D2, order-independent, sobre el contenido
    def __len__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...   # igualdad canónica por corpus_hash (D2)

    # AS-BUILT #54 (2026-06-17): tabla hermana `referenced_but_not_fetched` (append-only, par de
    # loop_state_log) — los IDs que el backward chaining OBSERVA sin materializar en el corpus (§5).
    # FUERA de la tabla `corpus` y del corpus_hash (son estado, no contenido; ADR 0017).
    def add_referenced_refs(self, ref_ids: list[str], *, cycle_round: int) -> "TabularBackend": ...
        # Registra IDs observados (idempotente por existencia de `ref_id`; observed_at = now() del backend).
    def referenced_refs_count(self) -> int: ...    # nº de IDs observados distintos
    def referenced_refs(self) -> pa.Table: ...     # los IDs observados (ref_id, cycle_round, observed_at)
```

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `InMemoryBackend` | **v1** | **Núcleo puro, sin I/O.** *Working set* efímero y backend de los tests (el núcleo se testea sin DuckDB). Semántica de valor; hereda la lógica del Hito 1 (mutación en Python sobre listas de dicts, table-rebuild). No persiste. |
| `DuckDBBackend` | **v1, por defecto** | La **biblioteca viva** (ADR 0009/0015): **construido** (Hito 3). Mutación por SQL puro (`INSERT … ON CONFLICT (id) DO UPDATE` + merge D3 en SQL/UDF), persiste entre corridas (`.duckdb` o `:memory:`), aloja el `LoopState` (ADR 0016). Pasa la suite de contrato de backend (D1/D2/D3). Carga **perezosa** (PEP 562): no se importa con `import bib2graph`. Ver §4. |

`TabularBackend` e `InMemoryBackend` son **símbolos públicos v1** (`from bib2graph import
TabularBackend, InMemoryBackend`). El contrato D1/D2/D3 se verifica con una **suite parametrizada
por backend** (`tests/unit/test_backends.py`), ahora parametrizada **también con `DuckDBBackend`**
(Hito 3, construido): el backend SQL cumple los mismos invariantes que el InMemory.

---

## 2. Costura `Source` — sembrar un corpus

El contrato `Source` es **agnóstico de la forma de OpenAlex** (ADR
[0018](decisiones/0018-source-agnostico-calidad.md)): separa lo que **todo** corpus necesita para
existir de lo que **algunas** fuentes pueden o no entregar.

- **Mínimo universal** (obligatorio para toda `Source`): `id`, `title`, `year`, `authors_raw`,
  `keywords_raw`. Habilita ya las redes de **co-autoría** y **co-ocurrencia de keywords**.
- **Enriquecimiento opcional** (la `Source` puede omitirlo; el schema admite nulos): `references_id`
  / `references_doi`, `cited_by_id`, `authors_affiliations` (per-autor), `institutions_id`.
  Habilita acoplamiento, co-citación, redes de instituciones y asortatividad geográfica.

Una `Source` que solo provee el mínimo es **ciudadana legítima** (habilita fuentes
latinoamericanas — SciELO, Redalyc, La Referencia — sin obligarlas a entregar lo que no tienen);
los proyectores de enriquecimiento producen redes parciales sobre esos papers y lo **reportan**
(no fallan). *(El contrato se declara en v0.1; las fuentes nuevas e impl son posteriores.)*

```python
class Source(Protocol):
    """Convierte una entrada externa en un Corpus. Acceso a campos DEFENSIVO (sin KeyError).
    Debe entregar el MÍNIMO UNIVERSAL (id, title, year, authors_raw, keywords_raw); el
    enriquecimiento (refs/citantes/afiliaciones/instituciones) es OPCIONAL (ADR 0018)."""

    def seed(self, query: str, *, exclude: list[str] | None = None) -> "SeedResult":
        """Siembra desde una ecuación de búsqueda. Devuelve el Corpus + la query ejecutada
        y el reporte de traducción (qué mapeó, qué se aproximó, qué se descartó).
        `exclude` (negaciones quirúrgicas, opcional): cada término se inyecta DENTRO de la
        única expresión `title_and_abstract.search:((query) AND NOT "<término>")` (el campo
        NO se repite) y se REPORTA en el
        translation_report (query visible, ejercicio consciente). Las comillas internas del
        término se sanean. Ignorado con `native=True` (query cruda). Una Source que no siembra
        por ecuación (p. ej. BibtexSource) lanza NotImplementedError."""
    def load(self, path: str) -> Corpus:
        """Siembra desde un archivo (export/pearls). is_seed=True."""

class SeedResult(BaseModel):
    corpus: Corpus
    executed_query: str        # la query OpenAlex EXACTA ejecutada (consciencia, ADR 0007)
    translation_report: list[str]   # mapeos limpios / aproximados / descartados (p. ej. NEAR no soportado) + negaciones aplicadas (exclude, #30)
```

**Capa declarativa de la ecuación — `EquationSpec` + `load_equation_spec`** (Ciclo 9a, ADR
[0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md); `src/bib2graph/sources/equation.py`).
Empaqueta los parámetros de `b2g seed` en un YAML versionable (el artefacto "qué se busca"), **análogo
a `NetworkSpec`/`load_specs`** del Hito 9. Clave raíz **`equation:`** (objeto, **no** lista — una
ecuación por archivo). El modo `b2g seed --spec equation.yaml` (§convenciones CLI) carga la spec y la
mapea a `run_seed`; equivale a `--equation` + flags.

```python
class EquationSpec(BaseModel):
    """Configuración declarativa de una ecuación de búsqueda (ADR 0030).
    model_config = ConfigDict(extra="forbid"): campo desconocido en el YAML → error accionable."""
    query: str                          # requerido (no vacío) — la ecuación de búsqueda
    exclude: list[str] = []             # #30 — AND NOT "…" DENTRO de la search:((query) AND NOT "…")
    max_results: int | None = None      # #14 — tope (None → default del source, 200)
    native: bool = False                # passthrough crudo a OpenAlex (sin traducción)
    min_year: int | None = None         # filtra: from_publication_date contra OpenAlex
    max_year: int | None = None         # filtra: to_publication_date contra OpenAlex

def load_equation_spec(path: str | Path) -> EquationSpec:
    """Carga/valida la EquationSpec desde un YAML (clave raíz `equation:`).
    Errores accionables (mismo patrón que `load_specs`): YAML malformado → ValueError;
    clave raíz ausente → ValueError; campo desconocido/tipo incorrecto → ValueError
    citando archivo + campo. Importación perezosa de PyYAML."""
```

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `OpenAlexSource` | **v1** | **Referencia/backbone**, sobre `httpx`. Entrega mínimo + enriquecimiento (refs inline + afiliaciones per-autor + instituciones; `cited_by_id` lo puebla el chaining/Enricher, no el seed). Traducción **passthrough**: envuelve la ecuación en `title_and_abstract.search:(...)` y **reporta** los límites WoS (NEAR/comodín/tags) sin traducirlos. Flag `native=True` (query cruda). **Negaciones (`exclude`):** cada `AND NOT "<término>"` se inyecta **dentro** de la única expresión `search:((query) AND NOT "<término>")` (campo no repetido; el filtro de año queda como predicado separado por coma, fuera del `search`) y se reporta en el `translation_report`; ignorado con `native`. Credenciales inyectadas (arg → `OPENALEX_API_KEY` → `~/.openalex/credentials` → polite pool; ADR 0012). Cursor paging con tope `max_results` (default 200). Puebla `Manifest.openalex_version` (ADR 0017). `transport` inyectable (tests sin red). Un **429** (rate limit del pool anónimo) en `seed()` → `NetworkError` (exit 4) con mensaje **accionable**: declarar `--email` mueve la petición al polite pool (remedio primario); api_key opcional (ADR 0012, #210). |
| `BibtexSource` | **v1, secundaria** | Sembrar desde *pearls* vía `load()`. Extra **`[bibtex]`** (import perezoso de `bibtexparser`); acceso defensivo (campos faltantes sin `KeyError`). Mínimo universal. `seed()` lanza `NotImplementedError`. `.bib` con error grave → `ValueError`; sin entradas válidas → `UserWarning` (no no-op silencioso). Carga bulk con `from_arrow`. |
| `ScieloSource` / `RedalycSource` / `LaReferenciaSource` | futuro | Fuentes regionales, mínimo universal. Declaradas, no implementadas (ADR 0018). |
| `RisSource` / `CsvSource` | futuro | No implementados. |

**Capacidades de `OpenAlexSource` fuera del Protocol `Source`** (específicas del backbone; las consumen
el `Forager` y el `Enricher`):

- **`fetch_citing(openalex_id) -> list[dict]`** (singular, forward chaining): `GET works?filter=cites:`,
  con retry/backoff ante 429/5xx. Al **agotar** los reintentos con **429** → `NetworkError` (exit 4)
  **accionable** (polite pool/`--email`; ADR 0012, #210); los 5xx agotados conservan
  `httpx.HTTPStatusError`. Asimetría deliberada: solo el 429 tiene remedio del lado del usuario.
- **`fetch_citing_batch(ids, *, max_per_paper, since=None) -> dict[seed_id, list[citer_id]]`**: trae los
  citantes **batcheando por OR** (`cites:W1|W2|...`, lotes ≤50), pagina por cursor y **atribuye página a
  página** con **presupuesto por semilla** (corta cuando todas alcanzan `max_per_paper`; sin starvation).
  **`since`** filtra a los publicados desde esa fecha (`from_publication_date`; lo usa `chain --since`).
  Lo consume el Enricher para poblar `cited_by_id`.
- **`fetch_citing_batch_with_works(ids, *, max_per_paper, since=None) -> tuple[dict[...], dict[citer_id,
  work]]`**: variante que **conserva la metadata** (`works_map`) que la misma request ya trae (cero red
  extra). La consume el Forager para materializar filas reales en el forward (no placeholders).
- **`fetch_dois_for(ids) -> dict`**: resuelve `references_id`→DOI batcheando por OR (≤100, `select=id,doi`).
- **`fetch_works_by_ids(ids) -> Corpus`**: materializa works desde sus IDs OpenAlex (batcheo OR ≤100).
  Devuelve un `Corpus` con `is_seed=False`, `candidate`, `provenance[action="fetched_by_id"]`; IDs
  inexistentes se omiten sin error; orden determinista; lista vacía → `Corpus` vacío sin tocar la red. Es
  el primitivo que materializaría lo observado por el backward chaining. Centraliza el mapeo JSON→Arrow
  vía `_work_to_row` (parametrizado por `is_seed`/`action`/`chaining_hop`/`source_tag`).

**Reporte de cobertura/calidad** (concepto declarado, concreto **futuro**; ADR 0018): por seed/source,
mide % de refs resueltas, % con DOI, distribución idioma/región y completitud del enriquecimiento;
alimenta el juicio de cuándo cambiar de Source. Se declara como contrato (función pura sobre `pa.Table`),
sin cablearse vacío.

### 2.1 Convención `examples/` — corpus de ejemplo commiteado

`examples/` es la **única** excepción al `.gitignore` de datos de usuario (ADR
[0030](decisiones/0030-ecuacion-declarativa-corpus-ejemplo.md)): un corpus real, curado y reducido
(CC0/OpenAlex) commiteado al árbol como **caso real reproducible sin red**. Reglas:

- **Un ejemplo = una carpeta de propósito único** (`examples/<nombre>/`), autocontenida, con:
  **`corpus.parquet`** (curado y congelado, schema `CORPUS_SCHEMA`; **parquet/CSV, NUNCA `.duckdb`**),
  **`equation.yaml`** (ecuación de procedencia, `EquationSpec`), **`curacion.csv`** (decisiones de
  curación congeladas que `b2g curate apply` consume — receta determinista) y **`README.md`** (la
  procedencia: la **receta CLI**, no un script).
- **Cómo se restaura:** `b2g snapshot restore --from-corpus examples/<nombre>/corpus.parquet` rehidrata
  el corpus **sin red**, preserva la curación y transiciona a `FILTERED`; luego `build` corre localmente.
- **`.gitignore`:** `!examples/` trackea el ejemplo; `examples/**/*.duckdb` protege de que un store vivo
  se cuele.
- **Ejemplos existentes:**
  - **`examples/valoraciones/`**: ~80 filas (70 `candidate` + 10 `accepted`), armado **100% por CLI**
    (`seed --spec equation.yaml` → `curate apply curacion.csv` → `build --max-citing 25` →
    `snapshot create`). Co-citación presente (rala) + las otras 4 redes sustanciales. Verificado por el
    gate R2 (`tests/unit/test_example_r2_gate.py`: `corpus_hash` + comunidades Louvain estables).
  - **`examples/bibtex/`**: un `sample.bib` chico (10 entradas, con
    variedad deliberada de campos faltantes para ejercitar el parser defensivo) + `README.md` con la
    receta 100% CLI (`b2g init` → `b2g seed --from-bib examples/bibtex/sample.bib` → `b2g build`).
    Demuestra el segundo camino de seed (BibTeX local, sin red). El `.bib` queda trackeado por la
    excepción `!examples/` ya existente.

---

## 3. Costura `Enricher` — señal extra (opt-in, ya NO estructural)

Con OpenAlex como backbone, refs y citantes **ya vienen en el corpus** (ADR 0007). El `Enricher`
queda opt-in para **resolver `references` a DOI** y el **segundo nivel de fetch** (poblar `cited_by_id`
≡ citantes compartidos) que habilita la **co-citación end-to-end**. Vive en el **núcleo sobre OpenAlex**
(ADR [0025](decisiones/0025-enricher-cocitacion-openalex.md)), **no** en `[s2]` (reservado para un
futuro `SemanticScholarEnricher`). **No se invoca por verbo propio** (#162): la pasada refs→DOI corre
automática en `chain` y la de co-citación en `build` (helper único `cli/_enrich.py::enrich_corpus`); el
verbo `b2g enrich` sobrevive como alias deprecado.

```python
@runtime_checkable
class Enricher(Protocol):
    """Config (API keys) INYECTADA, nunca embebida. Sin ramas muertas. Rate limit/reintentos
    sin perder papers. Idempotente. NO transiciona el CycleState (ortogonal al lazo, ADR 0025)."""
    def enrich(self, corpus: Corpus) -> Corpus: ...
```

| Implementación | Estado | Aporta |
|----------------|--------|--------|
| `OpenAlexEnricher` | **v1, opt-in** | `enrich(corpus)` hace **2 pasadas**. **refs→DOI:** resuelve los `references_id` únicos batcheando por OR (≤100, `select=id,doi`), rellena `references_doi` y registra un `EnricherRef` idempotente en el `Manifest`. **co-citación:** para las **semillas aceptadas** trae sus citantes vía `OpenAlexSource.fetch_citing_batch` (§2) y **mergea sus `openalex_id` en `cited_by_id`** (unión idempotente); **no** materializa citantes como filas (no crece el corpus). Constructor con **`max_citing_per_paper`** (tope por semilla). Frontera: el Source hace I/O + atribución; el Enricher **solo une**. |
| `SemanticScholarEnricher` | futuro | señal de citas adicional (reserva del `[s2]`, no estructural) |
| `CrossRefEnricher` / `ScopusEnricher` | futuro | No implementados. |

---

## 4. Costura `Store` / backend de persistencia (biblioteca viva)

La persistencia por defecto es el **`DuckDBBackend`** del `Corpus` (ADR
[0015](decisiones/0015-corpus-tabular-backend.md)): no un `Store` que persiste un `Corpus` Arrow
aparte, sino el **backend por defecto** del `Corpus` (mutaciones por SQL). El `Store` sigue siendo la
**costura/punto de extensión** para destinos externos opt-in (Zotero, Neo4j). El `CycleState` (ADR 0016)
vive en el backend persistente.

El contrato `TabularBackend` (Protocol) y su firma completa viven en **§1.4** (`to_arrow`, `add_paper`,
`merge`, `apply_curation`, `filter_view`, `corpus_hash`, `__len__`, `__eq__`, y la tabla hermana
append-only `referenced_but_not_fetched` vía `add_referenced_refs`/`referenced_refs_count`/
`referenced_refs`, fuera del `corpus_hash`; §1.4 + §5). El `Store` de abajo es la costura de
persistencia/intercambio **externa**, distinta del backend del `Corpus`.

```python
class Store(Protocol):
    """Costura de persistencia/intercambio externa. El respaldo por defecto del Corpus es el
    DuckDBBackend; esta costura cubre destinos opt-in (Zotero, Neo4j) y export (Parquet)."""
    def persist(self, corpus: Corpus) -> None:
        """Funde el corpus en la biblioteca viva (merge idempotente + log de procedencia)."""
    def load(self) -> Corpus:
        """Devuelve el corpus ACUMULADO (estado entre corridas)."""
```

| Implementación | Estado | Notas |
|----------------|--------|-------|
| `DuckDBBackend` | **v1, por defecto** | **Biblioteca viva** (ADR 0009/0015): backend del `Corpus`, stateful, acumula entre corridas, **mutación por SQL puro** (`INSERT … ON CONFLICT (id) DO UPDATE` + merge D3 en SQL/UDF), log de procedencia/curación + `LoopState`, query SQL. Es **núcleo**, no extra. `:memory:` o archivo. (El `DuckDBStore` es su fachada de costura.) |
| `InMemoryBackend` | **v1** | Backend puro (tests + working set efímero). Sin I/O. No persiste. |
| `ParquetStore` | **futuro (no implementado)** | Formato de **export/intercambio** del snapshot. Hoy lo cubre `Corpus.snapshot()` (parquet + `manifest.json`); un `Store` de export dedicado solo se construye si hace falta (lección 5: no se publica vacío). |
| `ZoteroStore` | **futuro (V1.1, `[zotero]`)** | Sincroniza la biblioteca con una colección Zotero. Costura, no el corazón. |
| `Neo4jStore` | **futuro (post-V1, `[neo4j]`)** | Adaptador tabla→grafo para Cypher. Ya no es sustrato (ADR 0002). |

> **Concurrencia (ADR [0019](decisiones/0019-concurrencia-diferida.md)):** DuckDB es
> single-writer. V1 asume **1 archivo `.duckdb` = 1 escritor** (lecturas concurrentes OK). Si el
> archivo está bloqueado por otro escritor, `DuckDBBackend`/`DuckDBStore` lanzan `StoreLockedError`
> (subclase de `OSError`); el CLI (Hito 6) lo mapea al exit code `5`. Multi-escritor concurrente es
> post-v1.0.

### 4.1 `DuckDBStore` — fachada de costura + extensiones del backend

`DuckDBStore(path)` (en `bib2graph.stores.duckdb`, re-exportado perezosamente como
`bib2graph.DuckDBStore`) implementa el Protocol `Store` (`persist`/`load`) delegando en un
`DuckDBBackend` sobre el archivo. `load()` devuelve un `Corpus` respaldado por ese backend (las
mutaciones subsiguientes tocan el archivo en disco).

```python
class DuckDBStore:
    def __init__(self, path: str | Path) -> None: ...   # abre/crea el .duckdb; StoreLockedError si bloqueado
    def persist(self, corpus: Corpus) -> None: ...       # merge idempotente por id (upsert-concat D3) en la biblioteca viva
    def persist_replace(self, corpus: Corpus) -> None: ...# DELETE+INSERT de la tabla `corpus`: el estado en disco
                                                          # queda EXACTAMENTE el corpus dado; preserva las tablas
                                                          # hermanas (loop_state_log, referenced_but_not_fetched)
    def load(self) -> Corpus: ...                         # corpus acumulado, respaldado por el DuckDBBackend
    @property
    def backend(self) -> "DuckDBBackend": ...            # acceso al backend para las extensiones de abajo
```

> **`persist_replace` vs `persist` (#88, ADR [0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)).**
> La **ingesta automática** (`seed`/`seed_from_bib`/`chain`/`restore`) y la pasada **`build
> --thesaurus`** (#164) persisten
> con **`persist_replace`** (→ `DuckDBBackend.overwrite_corpus`, DELETE+INSERT reasignando `_seq`
> desde 0, ADR 0024), porque ya tienen el corpus **completo, normalizado y deduplicado** en memoria y
> el upsert-concat D3 (`persist`) **reintroduciría** las variantes que el dedup cross-biblioteca acaba
> de colapsar. **`persist`/upsert queda intacto** para el resto de los llamadores (caso "mismo paper
> desde dos fuentes", D3). Ambos preservan las tablas hermanas.

**Procedencia del `Manifest` persistida entre cargas.** Los bloques de procedencia del `Manifest`
(§1.3) que no son contenido del corpus se guardan en **tablas hermanas** del `.duckdb` y `DuckDBStore.load()`
los **reconstruye** al rehidratar, para que sobrevivan a un ciclo persist/load:

- **`manifest.filters`** ⇄ tabla **`filter_log`** — vía `DuckDBBackend.persist_filter_steps()` /
  `load_filter_steps()` (#126).
- **`manifest.enrichers`** ⇄ tabla **`enricher_log`** — vía `DuckDBBackend.persist_enricher_refs()` /
  `load_enricher_refs()` (#141), **mismo patrón** que `filters`: la pasada de enriquecimiento
  (`chain` refs→DOI, `build` co-citación) sella sus `EnricherRef` y `load()` los recompone, así el
  snapshot reporta qué enriquecimiento se aplicó sin re-correrlo.

**Extensiones del `DuckDBBackend`, FUERA del Protocol `Store`/`TabularBackend`** (se acceden vía
`store.backend.…`): son específicas de DuckDB y no parte del contrato genérico:

```python
class DuckDBBackend:
    # ... cumple TabularBackend (§1.4) ...
    def loop_state(self) -> "CycleState | None": ...     # estado actual del ciclo (None si no hubo transiciones)
    def loop_round(self) -> int: ...                     # contador de ronda (0 sin estado; 1 primera; 2+ re-sembrados)
    def set_loop_state(self, state: "CycleState", *, cycle_round: int | None = None) -> None: ...
                                                         # registra una transición + ronda (log append-only, permisiva)
    def query(self, sql: str) -> pa.Table: ...           # consulta SQL de SOLO lectura sobre el corpus
```

**El ciclo es un concepto de dominio puro** (`bib2graph.cycle`); el backend **solo lo persiste**:

```python
# bib2graph/cycle.py — dominio puro, sin DuckDB (ADR 0016 enmendado, R3)
class CycleState(StrEnum):
    SEEDED = "SEEDED"; FORAGED = "FORAGED"; FILTERED = "FILTERED"; BUILT = "BUILT"; MONITORED = "MONITORED"

def apply_transition(state: CycleState | None, action: str, round: int) -> tuple[CycleState, int]: ...
    # reseed → (SEEDED, round+1); seed/chain/filter/build/monitor → estado de cadena, misma ronda
def available_transitions(state: CycleState | None) -> list[str]: ...   # transiciones de ciclo desde el estado
CURATION_ACTIONS: list[str] = ["accept", "reject"]                      # transversal: siempre disponible, no transiciona
```

El estado + la **ronda** se persisten en `loop_state_log` (append-only; estado actual = última fila;
columna `round`); las transiciones son **permisivas** (ADR 0016: no se bloquea ningún salto). `reseed`
es de **primera clase** (loop-back a `SEEDED` + ronda++, acumula sobre lo curado); `seed.py` lo cablea
cuando hay estado previo. **Fuente única de verdad:** `chain`/`filter`/`build` derivan su destino de
`apply_transition`, no de un literal. **`MONITORED`** es **alcanzable** vía **`b2g chain --since`**
(#158, forrajeo incremental; el alias deprecado `b2g monitor` delega), que dispara
`apply_transition(state, "monitor", round)` (paso 8 del ciclo).
El comando `b2g status` consume `loop_state()`/`loop_round()`/`available_transitions()` y expone
`curation_available`/`round` (ver §convenciones CLI).

> **Carga perezosa (PEP 562):** `DuckDBBackend` y `DuckDBStore` se exponen vía `__getattr__` en
> `bib2graph/__init__.py`, de modo que **`import bib2graph` NO importa `duckdb`** (el núcleo
> permanece puro y testeable sin DuckDB). Solo `bib2graph.DuckDBBackend` / `bib2graph.DuckDBStore`
> cargan el módulo bajo demanda. `CycleState` y `StoreLockedError` se
> importan desde `bib2graph.backends.duckdb` (o `bib2graph.stores.duckdb`); `bib2graph.cycle`
> (`CycleState`/`apply_transition`/`available_transitions`/`CURATION_ACTIONS`) es **núcleo puro**, sin
> DuckDB.

---

## 5. Núcleo — Forrajeo / chaining (asistencia algorítmica, SIN IA)

El *information scent* es **estructura bibliométrica de cita con el corpus** (ADR
[0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)). Es una **función pura** sobre el
primitivo `collect_item_to_papers` (índice `{ref → corpus-papers que lo citan}`):

- **Backward** (puro, local): scent = **fuerza de co-citación con el corpus** = nº de corpus-papers
  que listan al candidato en `references_id`. No toca la red (las refs ya vienen en el corpus).
- **Forward** (requiere red): scent = **fuerza de citación directa al corpus**
  (`forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|`, emite con `direct > 0`) — señal
  primaria robusta. Exige traer los citantes vía `source.fetch_citing(...)`.
- **Centralidad** del candidato: **diferida** (viz).

El ranking es descendente por scent con **desempate por `id` ascendente** (estable ante cualquier
`PYTHONHASHSEED`).

```python
Direction = Literal["backward", "forward", "both"]   # bib2graph.foraging.Direction

class Forager:
    """Orquesta el chaining sobre un Source, rankeando candidatos por *information scent*
    bibliométrico (co-citación backward / citación directa forward, ADR 0008/0020/0022).
    El scent consume el primitivo de proyectores. Solo el Forager toca la red; el núcleo
    de scent es puro."""
    def __init__(self, source: Source, *, depth: int = 1, max_candidates: int | None = None,
                 max_citing_per_paper: int = 50) -> None:
        """depth=1 por defecto; depth>1 lanza NotImplementedError (futuro v0.3+).
        max_candidates = tope configurable del ranking (None = sin límite).
        max_citing_per_paper = tope de citantes POR SEMILLA en el forward batcheado (default 50;
        acota el fetch vía fetch_citing_batch; CLI `--max-citing`). AS-BUILT #21 (2026-06-16)."""

    def preview(self, corpus: Corpus, *, direction: Direction = "both") -> "GrowthPreview":
        """'Esta expansión sumaría ~N papers' SIN traerlos. Opera SOLO localmente, SIN red.
        Backward: estimación EXACTA local desde references_id. Forward: NO estimable sin red
        (cited_by_id está vacío tras el seed) → estima el nº de SEMILLAS a forrajear (is_seed,
        SIN filtrar curation_status) con by_direction['forward']=0 y forward_requires_fetch=True;
        el conteo de citantes reales solo llega con chain(). NO muta el corpus."""

    def chain(self, corpus: Corpus, *, direction: Direction = "both",
              since: date | None = None) -> "RankedCandidates":
        """Computa candidatos (curation_status='candidate', is_seed=False) rankeados por scent.
        Devuelve SOLO los candidatos nuevos (no mergeados): el humano hace
        corpus.merge(ranked.corpus). NO muta el corpus de entrada. Sella Manifest.chaining.
        `since` (#158, forrajeo incremental): propaga a fetch_citing_batch(since=) →
        from_publication_date en OpenAlex; solo afecta el tramo forward. Lo usa `b2g chain --since`
        (transición a MONITORED)."""

class GrowthPreview(BaseModel):
    estimated_new: int             # total estimable localmente (forward=0 si requiere fetch)
    by_direction: dict[str, int]   # {'backward': N, 'forward': 0 si requiere fetch}
    direction: Direction
    forward_requires_fetch: bool = False   # True si se pidió forward/both → forward desconocido sin red

class RankedCandidates(BaseModel):
    corpus: Corpus                     # SOLO los candidatos nuevos (no mergeado con el corpus semilla).
                                       # Forward (#78): materializa filas con metadata REAL (título/año/
                                       # autores), NO placeholders — vía fetch_citing_batch_with_works.
                                       # Backward (#54): NO materializa filas — observa, ver observed_refs.
    ranking: list[tuple[str, float]]   # (id, information_scent), desc scent / asc id
    observed_refs: list[str] = []      # AS-BUILT #54 (2026-06-17): IDs observados por el backward SIN
                                       # materializarlos en .corpus (orden de ranking, respeta
                                       # max_candidates). El backward observa; el forward materializa.
                                       # b2g chain los persiste en `referenced_but_not_fetched` (§4),
                                       # fuera del corpus_hash. Materializar = diferido a #71.

# RETIRADO (ADR 0022): `explain_candidate` y el extra `[llm]` se ELIMINAN del producto.
# El producto no usa IA generativa. El "porqué" de un candidato lo explica la ESTRUCTURA
# VISIBLE (con qué del corpus se acopla/co-cita), no un LLM. Ver ROADMAP Hito R4.
# (En el AS-BUILT v0.2 existía como stub gateado en [llm]; la remediación lo borra.)
```

**Notas de contrato** (ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)):

- **Forward chaining requiere `source.fetch_citing_batch(ids, *, max_per_paper)`** (§2, capacidad de
  `OpenAlexSource`, **no** del Protocol `Source` — una source de solo-mínimo no habilita forward). El
  comando `chain` hace un **pre-check `hasattr`** y lanza `DependencyError` (exit 3) si el source no lo
  soporta (un `AttributeError` genuino no se disfraza de "source sin forward").
- **Forward batcheado + cap por semilla:** `fetch_citing_batch` batchea por OR (≤50) con presupuesto por
  semilla (`max_citing_per_paper`, default 50 — CLI `--max-citing`), sin N+1. El **alcance del forward es
  `is_seed=True`** (todas las semillas, **sin** filtrar `curation_status`): el chaining precede a la
  curación. La restricción a `accepted` es del **Enricher** (co-citación, §3), no del Forager.
- **Backward observa sin contaminar:** no crea filas-fantasma en el corpus; los IDs observados salen por
  **`RankedCandidates.observed_refs`** y `b2g chain` los persiste en la tabla hermana
  **`referenced_but_not_fetched`** (§4), **fuera del `corpus_hash`**. **Forward sí materializa** filas con
  metadata real (vía `fetch_citing_batch_with_works`, §2; cero red extra). Asimetría deliberada.
- **`preview` y `chain` no mutan** el corpus de entrada (semántica de valor). `fetch_citing` (singular,
  con retry/backoff ante 429/5xx) sigue disponible; el forward lo consume vía la variante batcheada.

---

## 6. Núcleo — `Preprocessor` + filtros PRISMA

```python
class Preprocessor:
    """Determinístico e idempotente. La parte fuzzy vive en §11 (ahora núcleo, no extra). Registra un
    PreprocRef en el Manifest por cada operación aplicada. `applied_at` se inyecta desde la frontera
    (R2): un único datetime.now(UTC) por invocación, igual que `decided_at` en curación."""
    def normalize(self, corpus: Corpus, *, applied_at: datetime | None = None) -> Corpus:
        """Normalización CONSERVADORA (decisión b=A): authors_id (lowercase + quitar acentos +
        colapso de espacios) y language (subtag ISO 639-1 primario). SIN fuzzy (eso es el dedup,
        §11), SIN columna de periodización. Idempotente. NO muta el corpus de entrada. Corre
        AUTOMÁTICAMENTE en la ingesta (helper `normalize_and_dedup`, ADR 0031)."""
    def apply_thesaurus(self, corpus: Corpus, thesaurus: dict | Path, *,
                        applied_at: datetime | None = None) -> Corpus:
        """Lee keywords_raw y SOBRESCRIBE keywords_id con los conceptos canónicos del thesaurus
        multilingüe CURADO (en/es/pt), dict canónico→aliases en JSON o Path a ese JSON.
        Determinista e idempotente (ADR 0011). SIN fallback semántico/LLM (ADR 0011 enmendado /
        0022): lo que no matchea queda fuera, sin inventar conceptos con un modelo. Paso EXPLÍCITO
        (flag `b2g build --thesaurus`, #164), NO automático: requiere el mapeo del usuario (ADR 0031)."""
```

**Filtros de inclusión/exclusión** (funciones puras, flujo PRISMA; ADR
[0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)):

```python
class FilterCriterion(BaseModel):
    field: Literal["year", "type", "language", "min_citations"]
    op: Literal["gte", "lte", "in", "not_in", "eq"]
    value: int | str | list[str]
    # year: gte/lte · type: in/not_in (sobre research_areas) · language: eq/in/not_in
    # min_citations: gte (sobre len(cited_by_id))

def apply_filter(corpus: Corpus, criterion: FilterCriterion) -> tuple[Corpus, FilterStep]: ...
def apply_filters(corpus: Corpus, criteria: list[FilterCriterion]) -> tuple[Corpus, list[FilterStep]]:
    """Encadena los criterios en orden y SELLA Manifest.filters con todos los pasos
    (reemplaza: una corrida = una secuencia PRISMA). Devuelve (corpus_final, [FilterStep, ...])."""
```

**Notas de contrato** (ADR [0020](decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)):

- **Los filtros MARCAN `rejected`, NO borran:** un paper excluido queda en la tabla con
  `curation_status='rejected'` vía `corpus.reject(...)` (con el criterio en `provenance`), nunca se
  borra. La exclusión es curación **reversible y auditable** (biblioteca viva, ADR 0009/0013).
- **Conteo PRISMA por paso:** cada `FilterStep` lleva `count_before`/`count_after` sobre los papers
  **no-rejected** (candidate + accepted).
- **`keywords_id` es post-thesaurus:** los proyectores de co-ocurrencia de keywords (§7) deben correr
  **después** de `apply_thesaurus`.
- **Campo/operador desconocido LANZA** `ValueError` accionable (lista los válidos); no es no-op
  silencioso (endurece el flujo PRISMA, sin exclusiones perdidas).
- **Símbolos públicos** (`from bib2graph import ...`): `Forager`, `GrowthPreview`, `RankedCandidates`,
  `Preprocessor`, `FilterCriterion`, `apply_filters`. `apply_filter` (singular) desde
  `bib2graph.filters`.

---

## 7. Núcleo — `Projector` (funciones puras)

```python
class Projector(Protocol):
    def project(self, table: pa.Table, *, min_weight: int = 1,
                scope: Literal["full", "seeds_only"] = "full") -> nx.Graph: ...
```

| Proyector | Estado | Insumo | Scope por defecto | Requiere Enricher |
|-----------|--------|--------|-------------------|-------------------|
| `BibliographicCouplingProjector` | **v1** | `references_id` | **`full`** (corpus completo) | No (refs ya en corpus) |
| `AuthorCollaborationProjector` | **v1** | `authors_id` | `full` | No |
| `InstitutionCollaborationProjector` | **v1** | `institutions_id` | `full` | No |
| `KeywordCoOccurrenceProjector` | **v1** | `keywords_id` (post-thesaurus) | `full` | No |
| `CoCitationProjector` | **v1** | `cited_by_id` + citas de citantes | `seeds_only` | **Sí** (2º nivel de fetch) |

El **acoplamiento** (barato, mira adelante) es ciudadano de primera y opera sobre el **corpus
completo** (crítica #2). La **co-citación** es la más cara (segundo nivel de fetch).

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **Peso = conteo crudo** de ítems compartidos (D1); `min_weight` (default 1) descarta aristas
  con `weight < min_weight`. Sin normalización (Salton/Jaccard) en v1.
- **Tipo de nodo** (D2): co-autoría / instituciones / co-word → la **entidad** es el nodo
  (`authors_id` / `institutions_id` / `keywords_id`); acoplamiento / co-citación → el **paper**
  (`id`) es el nodo.
- **Co-citación:** el `CoCitationProjector` cuenta **`cited_by_id` compartido** = los **citantes
  compartidos** de la metodología (la frase "citantes con sus citas" ≡ `cited_by_id` compartido).
  Proyecta con scope `seeds_only`. La co-citación es **end-to-end**: la pasada `cited_by` que corre
  automática en `build` (cuando hay aceptadas) puebla `cited_by_id` con el 2º nivel de fetch del
  `OpenAlexEnricher` (ADR 0007/0025), y `Networks.quick` la incluye cuando esa columna está poblada (§10).
- **Los proyectores siguen PUROS — NO setean atributos de nodo** (ADR 0014): producen
  un `nx.Graph` con **ids crudos** como nodos (`doi:…`, `I185261750`, un ORCID), **sin** `label`. La
  legibilidad (label + atributos) la inyecta la **capa `decorate` (§7.1)**, que es la **frontera**
  entre la proyección pura y el export. Esta separación es deliberada (ADR 0014).

---

## 7.1 Frontera — `decorate` (label legible + atributos de nodo)

`bib2graph.networks.decorate` es la **capa de frontera** entre los proyectores puros (§7) y los
exportadores (§9). Los proyectores devuelven grafos con **ids crudos** como nodos y **sin atributos**;
`decorate` transforma esos ids en **labels legibles** e inyecta atributos de
curación/comunidad/centralidad, para que las redes no salgan ilegibles en Gephi/VOSviewer/Cytoscape.

```python
LABEL_MAX_CHARS: int = 60   # tope del label de paper; título largo → truncado + "..."

def decorate_graph(graph: nx.Graph, table: pa.Table, kind: str, *,
                   communities: dict[Any, int] | None = None) -> None:
    """Inyecta label + atributos en los nodos del grafo IN-PLACE (no copia; el llamador/
    exporter copia si necesita preservar el original). No muta el corpus ni la tabla.
    Determinista; no importa duckdb (núcleo puro)."""

def decorate(artifact: NetworkArtifact, table: pa.Table) -> None:
    """Atajo sobre decorate_graph: extrae kind y communities del NetworkArtifact.
    Es el punto de integración en facade.py (_build_artifact)."""
```

`networks/__init__.py` re-exporta `decorate`/`decorate_graph`.

**Atributos de nodo inyectados:**

| Atributo | Kinds | Origen |
|---|---|---|
| `label` | todos | string legible (mapeo por kind, abajo) |
| `degree_centrality` | todos | `float`, vía `nx.degree_centrality` |
| `year` | paper (coupling/cocitation) | `int` (ausente si `None` en el corpus) |
| `doi` | paper (coupling/cocitation) | `string` desde `Col.DOI` (DOI desnudo/normalizado, p. ej. `10.1234/abc`); **ausente si el paper no tiene DOI** (mismo criterio que `year`) |
| `url` | paper (coupling/cocitation) | `string` derivada `https://doi.org/<doi>`; **solo presente si hay DOI** (no es columna del corpus, ver nota abajo) |
| `is_seed` | paper | `bool` |
| `curation_status` | paper | `string` |
| `community` | todos | `int`, **solo** si se provee `artifact.communities` |

`doi`/`url` aplican **solo a paper-kinds** (`bibliographic_coupling` y `cocitation`); los nodos de
autor/institución/keyword **no los reciben**. `url` es **derivada** (`https://doi.org/<doi>`), no una
columna del corpus: el DOI es la única identidad de primera clase (ADR 0036) y la URL es una expansión
trivial determinista a la hora de decorar. La derivación vive en `doi_to_url(doi: str|None) -> str|None`
(`bib2graph.constants`), **fuente única** compartida con `resolve_url` (§0.1, #212) — sin drift.
Ausencia condicional como `year`: sin DOI truthy, el nodo no
recibe ni `doi` ni `url`. Los exporters CSV/GraphML (§9) los propagan **automáticamente** cuando están
presentes (son genéricos y omiten `None`) — sin cambios en exporters.

**Mapeo de `label` por `NetworkKind`:**

| Kind | Nodo | `label` |
|---|---|---|
| `bibliographic_coupling` / `cocitation` | paper (`id`) | `"título (año)"`, truncado a `LABEL_MAX_CHARS` (60) + `"..."`; fallback al id crudo si no hay título |
| `author_collab` | `authors_id` | `authors_raw` correlativo al `authors_id` (fallback al id) |
| `institution_collab` | `institutions_id` | `institutions_raw` correlativo (fallback al id) |
| `keyword_cooccurrence` | `keywords_id` | la keyword (ya legible) |
| (kind desconocido) | — | fallback al id crudo (extensible, no falla) |

**Cableado:** `decorate` se aplica en `facade.py:_build_artifact`, de modo que `Networks.quick` /
`Networks.build` (§10) ya devuelven **artefactos decorados** y `b2g build`/`export` salen con `label`
legible sin pasos extra. **Los proyectores (§7) NO se tocan** (siguen puros, ADR 0014): la decoración
es la única capa que sabe de labels.

---

## 7.2 Núcleo — `cluster_table` (resumen de comunidades)

`bib2graph.networks.cluster_table` es una **función pura** que cruza los nodos de una red con el
corpus para producir **una fila de resumen por comunidad** (quién/qué/cuándo cae en cada comunidad),
base del `clusters.csv` que escribe `b2g build`. Con `--scope`, `build` le pasa el corpus **filtrado**,
así que sus conteos cuadran con los nodos del grafo (sin drift).

```python
def cluster_table(table: pa.Table, artifact: NetworkArtifact) -> list[dict[str, Any]]:
    """Una fila por comunidad de `artifact.communities`. Función pura (sin red, sin duckdb).
    Cruza nodo→fila por Col.ID (id canónico), NUNCA por source_id. Devuelve [] si el kind
    no es de paper o si no hay comunidades. Orden determinista por `cluster` ascendente."""
```

`networks/__init__.py` re-exporta `cluster_table`. **Solo aplica a redes de paper**
(`bibliographic_coupling`/`cocitation`); para autor/institución/keyword devuelve `[]` (no crash), por
eso `clusters.csv` se emite **únicamente** para esas dos redes.

**Columnas de cada fila** (orden estable):

| Columna | Tipo | Origen |
|---|---|---|
| `cluster` | `int` | id de comunidad |
| `size` | `int` | nº de nodos en la comunidad (incluye nodos sin match en el corpus) |
| `seed_count` | `int` | nodos con `is_seed=True` |
| `candidate_count` | `int` | nodos con `curation_status='candidate'` |
| `accepted_count` | `int` | nodos con `curation_status='accepted'` |
| `year_min` / `year_max` | `int \| None` | rango de año (`None` si ningún nodo tiene año) |
| `year_mean` | `float \| None` | media de año redondeada a 1 decimal (`None` si no hay años) |
| `top_authors` | `list[str]` | hasta 5 autores más frecuentes, de **`authors_raw`** |
| `top_keywords` | `list[str]` | hasta 5 keywords más frecuentes, de **`keywords_id`** (post-thesaurus) |

**Notas de contrato:**

- **Cruce por `Col.ID`, no `source_id`:** el nodo del grafo **es** un `Col.ID` (`doi:…`/`src:…`);
  indexar por `source_id` daría 0 cruces. Un nodo sin match en el corpus suma al `size` pero no aporta
  año/autores/keywords.
- **Determinista** (ADR 0017): el top de autores/keywords se ordena por `(-frecuencia, nombre asc)`,
  reproducible independiente del método de clustering y de `PYTHONHASHSEED`.
- **Pura:** sin red ni `duckdb`. Combina con `community_composition` (§8, % por categoría del atributo).

---

## 8. Núcleo — `Analyzer` (funciones puras)

```python
def network_metrics(g: nx.Graph) -> dict:
    """Densidad, nº de componentes, clustering promedio."""

def centrality(g: nx.Graph) -> dict:
    """Centralidad de grado e intermediación por nodo."""

def detect_communities(g: nx.Graph, method: str = "louvain", *,
                       random_state: int | None = None) -> dict:
    """method ∈ {'louvain', 'label_prop', 'greedy_modularity'}. Louvain requiere
    `python-louvain` (DECLARADO); si falta, FALLA explícito (lección 7).
    `random_state` (Hito R2, ADR 0017): semilla determinista de Louvain. `facade.py` la
    deriva del `corpus_hash` de contenido (`_louvain_seed_from_hash`) → comunidades
    reproducibles entre corridas. `None` = Louvain sin semilla. (`resolution`: Hito 9.)"""

def assortativity(g: nx.Graph, *, attribute: str | None = None,
                  by_degree: bool = True, proxy: str | None = None) -> dict:
    """Asortatividad por un ATRIBUTO categórico configurable (p. ej. 'region') y/o por grado.
    `attribute` y sus categorías son config del USUARIO (no hardcodear; crítica #5).
    `proxy` documenta si el atributo es un proxy (p. ej. 'affiliation_per_paper'): se reporta
    en el output como disclaimer ('fácil pero consciente'). Validado en el sandbox IED."""

def community_composition(g: nx.Graph, communities: dict, attribute: str) -> dict:
    """% de cada categoría del atributo dentro de cada comunidad.
    (Composición bibliográfica de las comunidades de una red de paper → `cluster_table`, §7.2.)"""

def cocitation_quality_report(corpus: Corpus, g: nx.Graph, *,
                              thresholds: "QualityThresholds | None" = None) -> dict:
    """Informe de calidad (metodología §4). Umbrales CONFIGURABLES (no fijos del estudio de
    semiconductores; crítica #5). Defaults sensatos si thresholds is None."""

class QualityThresholds(BaseModel):
    min_volume: int = 200
    min_doi_refs_pct: float = 0.90
    min_countries: int = 5
    min_recurrent_authors: int = 10
```

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **`assortativity` con `proxy`** añade una clave `proxy_disclaimer` al dict de salida (D4): el
  atributo es un proxy del campo real, no el campo real ("fácil pero consciente").
- **`cocitation_quality_report` devuelve `{criterio: {valor, umbral, pasa, ...}}` + `overall_pass`**
  (sin score ponderado; D6). El criterio `min_countries` usa `institutions_id` como **proxy** de
  países (cuenta ids de institución únicos) y lo marca con un disclaimer en su entrada; el lookup
  ROR→país real llega en el Hito 8.

---

## 9. Núcleo — `Exporter`

```python
class Exporter(Protocol):
    def export(self, g: nx.Graph, results: dict, out_dir: str) -> None: ...

class GraphMLExporter: ...   # v1 — para Gephi / VOSviewer / Cytoscape
class CsvExporter: ...       # v1 — nodos.csv + aristas.csv para pandas
```

**Notas de contrato** (Hito 2, ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md), D5):

- **`CsvExporter`** escribe `aristas.csv` (`source,target,weight`) y `nodos.csv` (`id,label` +
  atributos de nodo + métricas de `results` —degree/betweenness/community— unidas por id). Orden
  de filas determinista. El `label` (y `year`/`doi`/`url`/`is_seed`/`curation_status`/`community`) lo
  inyecta la capa `decorate` (§7.1) antes del export, no el exporter; `doi`/`url` salen solo en
  paper-kinds y solo cuando el paper tiene DOI.
- **`GraphMLExporter`** escribe esos atributos como node attributes, **omite** los atributos con
  valor `None` (Gephi / `nx.write_graphml` no los admiten) y **no muta** el grafo original (opera
  sobre una copia).
- **`clusters.csv` (AS-BUILT #31):** además de `network.graphml` + `metrics.json`, **`b2g build`**
  escribe `<networks_dir>/<kind>/clusters.csv` cuando la red es de **paper** y tiene comunidades
  (`cluster_table` no vacío, §7.2). Una fila por comunidad; las columnas de lista (`top_authors`/
  `top_keywords`) se serializan **con separador `|`**. No lo emite un `Exporter` —lo arma el comando
  `build` a partir de `cluster_table`—; las redes sin comunidades o no-paper no generan el archivo.
  **Solo lo generan `bibliographic_coupling` y `cocitation`**: `author_collab`, `institution_collab`
  y `keyword_cooccurrence` emiten `network.graphml` + `metrics.json` pero **no** `clusters.csv`, por
  diseño (sus nodos no son papers; ver §7.2).

---

## 10. Capa declarativa — `NetworkSpec`

```python
class NetworkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")   # Hito 9: campo desconocido en el YAML → error
                                                 # accionable (no se ignora en silencio)
    kind: NetworkKind        # R5: enum de constants.py (fuente única, ADR 0023);
                             # antes era un Literal[...] duplicado (eliminado)
    min_weight: int = 1
    min_year: int | None = None
    max_year: int | None = None
    scope: Literal["full", "seeds_only"] = "full"
    clustering: Literal["louvain", "label_prop", "greedy_modularity"] | None = "louvain"
    resolution: float = 1.0  # Hito 9: resolución de Louvain (python-louvain best_partition).
                             # Default 1.0 = comportamiento anterior. Ignorado en label_prop/
                             # greedy_modularity (sin error). FUERA del corpus_hash (param de spec,
                             # no de contenido — como min_weight/scope; el seed de Louvain sigue
                             # siendo función pura del corpus_hash, R2).
    assortativity_attribute: str | None = None     # p. ej. "region"
    layout: Literal["spring", "kamada_kawai", "circular"] | None = None
    keyword_filter: list[str] | None = None  # Issue #113: sub-red temática. Filtra el corpus ANTES
                                             # de proyectar a los papers cuyo keywords_raw matchee
                                             # (ANY, substring, case-insensitive) algún término.
                                             # None/[] = sin filtro. Param de spec, FUERA del
                                             # corpus_hash (como min_weight/scope).


def load_specs(path: str | Path) -> list[NetworkSpec]:
    """Carga y valida una lista de NetworkSpec desde YAML (Hito 9). Re-exportada desde
    bib2graph.networks. Clave raíz `networks:` = lista; cada entrada se valida con
    NetworkSpec(**entry) (no se redefine el schema). Errores accionables (ValueError):
    YAML malformado, falta de raíz `networks:`, entrada no-dict, y ValidationError citando
    archivo + `red #<idx>` (0-based) + campo."""

class NetworkArtifact:
    graph: nx.Graph
    metrics: dict
    communities: dict | None
    assortativity: dict | None
    layout: dict | None
    spec: NetworkSpec

class Networks:
    @staticmethod
    def build(corpus: Corpus, spec: NetworkSpec) -> NetworkArtifact: ...
    @staticmethod
    def quick(corpus: Corpus) -> list[NetworkArtifact]:
        """Arma las specs razonables y devuelve sus artefactos (caso 'investigador, baja
        fricción'). Devuelve **4 o 5 redes**: coupling (full), co-autoría, institución, co-word
        siempre; la **co-citación** se incluye (→5) cuando el corpus tiene `cited_by_id` poblado
        (tras la pasada `cited_by` de `build`) y se **omite graceful** (log) si está vacío (→4).
        Los artefactos vienen **decorados** (label legible + atributos de nodo, §7.1)."""
```

**Modo quick** cubre baja fricción; **modo spec** (YAML) cubre el pipeline declarativo versionable, vía
`load_specs(redes.yaml)` + `Networks.build` por red (subcomando `build --spec`, §convenciones CLI).

**Notas de contrato** (ADR [0014](decisiones/0014-proyeccion-redes-pesos-asortatividad.md)):

- **`Networks.quick` arma 4 o 5 redes:** coupling `full`, co-autoría, institución y co-word **siempre**
  (4); suma la **co-citación** (→5) cuando el corpus tiene `cited_by_id` poblado (2º nivel de fetch del
  Enricher, ADR 0025), y la omite avisando por log (→4) si esa columna está vacía.
- **Artefactos decorados:** `Networks.build`/`quick` devuelven artefactos con `label` legible + atributos
  de nodo (vía `decorate`, §7.1); los proyectores (§7) siguen puros (ADR 0014). El símbolo público
  re-exportado desde `bib2graph` es `NetworkArtifact` (`NetworkSpec` se importa desde `bib2graph.networks`).
- **`resolution`** (Louvain) e **`keyword_filter`** (issue #113, sub-red temática: filtra el corpus a los
  papers cuyo `keywords_raw` matchee ANY substring case-insensitive antes de proyectar) son params de
  spec, **fuera del `corpus_hash`** (como `min_weight`/`scope`): el seed de Louvain sigue siendo función
  pura del `corpus_hash` (R2).
- **`load_specs`** (clave raíz `networks:` = lista; cada entrada se valida con `NetworkSpec(**entry)`)
  da errores accionables (`ValueError`): YAML malformado, falta de raíz, entrada no-dict, o
  `ValidationError` citando archivo + `red #<idx>` + campo.

**Campos válidos de cada entrada del YAML** (`kind` obligatorio, resto con default; `extra="forbid"` →
campo desconocido se rechaza con `ValueError`; **`name:` NO es un campo** — anotá con comentario `#`):

| Campo | Valores / tipo | Default |
|---|---|---|
| `kind` | `bibliographic_coupling` · `cocitation` · `author_collab` · `institution_collab` · `keyword_cooccurrence` | **(obligatorio)** |
| `min_weight` | `int` | `1` |
| `min_year` / `max_year` | `int` | `null` |
| `scope` | `full` · `seeds_only` | `full` |
| `clustering` | `louvain` · `label_prop` · `greedy_modularity` · `null` | `louvain` |
| `resolution` | `float` (solo Louvain) | `1.0` |
| `assortativity_attribute` | `str` (p. ej. `region`) | `null` |
| `layout` | `spring` · `kamada_kawai` · `circular` · `null` | `null` |
| `keyword_filter` | `list[str]` (ANY substring sobre `keywords_raw`) | `null` |

```yaml
networks:
  - kind: bibliographic_coupling
    min_weight: 2
    resolution: 1.5
  - kind: keyword_cooccurrence
    keyword_filter: ["complex", "ecolog"]
```

---

## 11. Deduplicación fuzzy — AUTOMÁTICA en la ingesta (`rapidfuzz` núcleo)

**Dedup fuzzy determinista** con `rapidfuzz` (núcleo desde #88): el complemento aproximado de la
normalización conservadora del `Preprocessor` (§6). Las funciones siguen exportadas desde
`bib2graph.preprocessors`, pero **se invocan automáticamente** desde el helper canónico
`preprocessors.pipeline::normalize_and_dedup`, no a mano. Operan sobre la columna `_id`
(`authors_id`/`keywords_id`), **nunca** sobre `_raw`.

```python
# Helper canónico — punto único de la ingesta (preprocessors/pipeline.py;
# re-exportado por compat desde cli/_ingest.py → el import viejo
# `from bib2graph.cli._ingest import normalize_and_dedup` sigue vivo, no es breaking)
def normalize_and_dedup(corpus: Corpus, *, applied_at: datetime | None = None) -> Corpus:
    """normalize → deduplicate_authors(0.92) → deduplicate_keywords(0.90), en ese orden, sobre el
    corpus COMPLETO YA MERGEADO (existing + incoming) ⇒ dedup CROSS-BIBLIOTECA. NO aplica thesaurus
    (eso es el flag explícito `b2g build --thesaurus`, #164). `applied_at` se inyecta desde la frontera (R2)."""

# Funciones de librería (ADR 0026, intactas; ahora invocadas por el helper, no a mano)
def deduplicate_authors(corpus: Corpus, *, threshold: float = 0.92) -> Corpus:
    """Colapsa variantes de `authors_id` por similitud de nombres (fuzzy DETERMINISTA). Lo trivial
    ya lo hizo el Preprocessor (§6); esto es el complemento aproximado."""

def deduplicate_keywords(corpus: Corpus, *, threshold: float = 0.90) -> Corpus:
    """Colapsa variantes de `keywords_id` fuera del thesaurus por similitud de cadenas."""
```

**Notas de contrato** (ADR [0026](decisiones/0026-dedup-fuzzy-determinista.md) /
[0031](decisiones/0031-preprocesamiento-automatico-en-ingesta.md)):

- **Automático en la ingesta, cross-biblioteca:** las cuatro rutas
  (`seed`/`seed_from_bib`/`chain`/`restore`) hacen `existing.merge(incoming)` →
  `normalize_and_dedup(corpus_completo)` → `store.persist_replace(...)`. Corre sobre el corpus
  **completo** (no el lote) para deduplicar contra toda la biblioteca acumulada; se persiste con
  **`persist_replace`** (§4.1) porque el upsert-concat D3 reintroduciría las variantes colapsadas.
  `build` sigue **puro** (el corpus ya entra deduplicado).
- **`threshold` por-campo** (autores `0.92` / keywords `0.90`): `rapidfuzz.fuzz.token_sort_ratio` (0–100)
  contra `threshold * 100`. Umbrales fijos como **constantes públicas** `THRESHOLD_AUTHORS` /
  `THRESHOLD_KEYWORDS` de `bib2graph.preprocessors` (fuente única en `preprocessors.pipeline`, issue
  #175): el umbral compartido por la ingesta y el `restore` es **uno solo**, sin copias que diverjan.
- **Determinista e idempotente:** los pares ≥ umbral forman **componentes conexas** vía Union-Find; el
  **canónico** del cluster es la variante más frecuente (desempate por `id` ascendente); se preserva el
  **orden de primera aparición** y **nunca se toca `_raw`**. Mismo corpus + threshold + versión de
  `rapidfuzz` → mismo resultado (verificado cross-`PYTHONHASHSEED`); converge en una pasada. **NO usa
  IA** (similitud de cadenas, no semántica/LLM; ADR 0022). Registra un `PreprocRef` en el `Manifest`
  (`{library, rapidfuzz_version, scorer, threshold, n_clusters_collapsed}`).
- **`rapidfuzz` en el núcleo:** `rapidfuzz>=3,<4` en `[project.dependencies]` (ya no hay extra `[dedup]`).
- **Campos en V1:** autores + keywords. **Instituciones diferidas**; `splink` (record-linkage
  probabilístico) diferido a post-V1 (ADR 0026). **Deuda conocida:** el dedup por ingesta es O(n²) sobre
  el corpus completo (optimización futura). La **revisión asistida de clusters ambiguos** (sugerir N
  canónicos determinista vía scores, sin IA → el humano elige) requiere superficie interactiva y no está;
  hoy el dedup aplica el canónico determinista sin confirmar.

---

## 12. Ejemplo de uso (ecuación → biblioteca viva → redes)

### 12.1 Por CLI agente-native (el camino canónico)

Se **inicia el workspace una vez** y, trabajando **dentro** de su carpeta, los comandos se resuelven por
ambiente. Con `B2G_JSON=1`, una línea JSON por comando (un agente corre el ciclo sin repetir `--json`):

```bash
b2g init ied                                     # crea ./ied/ (workspace.json + library.duckdb + …)
cd ied                                            # a partir de acá el workspace se resuelve por cwd
export B2G_JSON=1
b2g seed --equation '"unequal ecological exchange"' --max-results 50 \
         --exclude "blockchain" --email tu@correo.org  # --exclude (repetible): negaciones en el translation_report
b2g chain --direction both --max-candidates 300   # → FORAGED (+ pasada refs→DOI automática)
b2g curate dump                                   # vuelca candidatos a exports/curacion.csv (revisar offline)
b2g curate apply curacion.csv                     # aplica accepted/rejected en lote
b2g build --max-citing 50 --email tu@correo.org   # → BUILT; co-citación (cited_by) sobre las aceptadas
b2g read top --kind bibliographic_coupling        # salida de investigación (nodos centrales + co-citación)
b2g export --format graphml                        # serializa networks/ a exports/
b2g snapshot create                                # foto reproducible (parquet + manifest.json)
b2g status                                         # CycleState + round + curation_available + workspace
```

Migración de un `.duckdb` legacy: corré **`b2g init .`** en su carpeta para adoptarlo como workspace.
El **modo declarativo** se invoca con **`b2g build --spec redes.yaml`** (carga `load_specs` → `Networks.build`
por red, escribe `networks/<kind>/`, transiciona a `BUILT` y sella `.corpus_hash`).

### 12.2 Como librería Python

El mismo dominio sin CLI (el núcleo es puro y testeable; el forrajeo y el store hacen I/O):

```python
from pathlib import Path
from bib2graph import (
    OpenAlexSource, Forager, Preprocessor, DuckDBStore, Networks, GraphMLExporter,
    FilterCriterion, apply_filters,
)

# 1) Sembrar (query ejecutada + reporte de traducción visibles)
seed = OpenAlexSource(email="tu@correo.org").seed(
    '"unequal ecological exchange" OR "intercambio ecológico desigual"')
print(seed.executed_query, "\n".join(seed.translation_report))

# 2) Forrajear (depth=1; backward observa sin materializar, forward materializa filas reales)
forager = Forager(OpenAlexSource(email="tu@correo.org"), depth=1, max_candidates=300)
ranked = forager.chain(seed.corpus)

# 3) Curar + normalizar + thesaurus determinista
corpus = seed.corpus.merge(ranked.corpus).accept(ids=[...]).reject(ids=[...])
corpus = Preprocessor().normalize(corpus)
corpus = Preprocessor().apply_thesaurus(corpus, Path("thesaurus_ied.json"))

# 4) Filtrar (PRISMA: marca rejected, no borra) + persistir + snapshot + redes
corpus, steps = apply_filters(corpus, [
    FilterCriterion(field="year", op="gte", value=2010),
    FilterCriterion(field="language", op="in", value=["en", "es", "pt"]),
])
store = DuckDBStore(Path("ied/library.duckdb")); store.persist(corpus)
snap = store.load().snapshot(Path("ied/snapshots/ied"))
for art in Networks.quick(snap.corpus):
    GraphMLExporter().export(art.graph, art.metrics, out_dir=Path(f"ied/networks/{art.spec.kind}"))
```

`DuckDBStore` se importa desde `bib2graph` (re-export **perezoso** vía PEP 562, §4.1): `import bib2graph`
no arrastra duckdb.
