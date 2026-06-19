# 15 — El hueco persistente del CLI: la capa de lectura y análisis

> ⚠️ **NOTA DE SESIÓN — no es decisión ni ADR.** Consolida el feedback de uso real del CLI
> `b2g` acumulado en tres sesiones de e2e/QA y nombra el hueco que se repite. Fecha: 2026-06-18.
> Documentos hermanos / antecedentes directos:
> [`09-sesion-qa-prueba-ecologia-valoraciones.md`](09-sesion-qa-prueba-ecologia-valoraciones.md)
> (QA valoraciones → issues #14/#21/#22/#25/#26),
> [`14-sesion-e2e-anomalias-ml.md`](14-sesion-e2e-anomalias-ml.md) (e2e anomalías ML → huecos
> G1–G4 de lectura). Esta nota suma la 3ª sesión (corrupción ⨉ ciencia de redes, corrida única
> sobre los 5 flujos A–E) y unifica.

## Tesis: el CLI **produce** pero no deja **leer** ni **analizar**

Tres sesiones de uso real, tres veces el mismo final: el ciclo se corre **entero por CLI** (sembrar
→ forrajear → curar → redes → snapshot), pero para **responder la pregunta de investigación** hubo
que bajar a Python y reescribir, otra vez, la misma capa de análisis (`scripts/analizar.py` +
`scripts/figuras.py`, copiados casi idénticos entre `ml-anomalias/` y `corrupcion-redes/`).

La frontera se movió, pero no desapareció — **se corrió de "producir" a "leer/analizar":**

| Sesión | Lo que el CLI ya cubría | Lo que hubo que hacer en Python |
|---|---|---|
| **09** (valoraciones) | casi nada (CLI incompleto) | sembrar, exportar redes, dump CSV, curación |
| **14** (anomalías ML) | sembrar → build → snapshot (CLI puro) | **leer** el corpus (listar, facetar por año, buscar) |
| **15** (corrupción) | los 5 flujos A–E completos | **analizar**: rankear centrales, lecturas fundacionales, facetas |

Lo de 09 se cerró (#14/#21/#22/#25/#26/#31 + `--exclude`). Lo de 14 sigue abierto. Lo de 15 es
nuevo y **más profundo**: no es solo que no se pueda *ver* el corpus, es que no se puede *obtener el
resultado* (las lecturas centrales y fundacionales) sin un tool externo.

## Lo nuevo de esta sesión (corrida de los 5 flujos)

La corrida e2e fue **verde end-to-end** (los 5 flujos del `docs/features/` pasaron; los gaps
`@pendiente` se comportaron como documentados — ver `prueba_e2e/corrupcion-redes/qa/qa-log.md`). El
CLI **operó** perfecto. Lo que faltó fue todo lo que viene *después* de operar.

### H1. El ranking del forrajeo es ilegible: `{id, scent}` sin título

`b2g chain` devuelve `data.ranking_preview` como lista de `{id, scent}` — **IDs crudos de OpenAlex**.
El forrajeo existe justamente para decir *"leé esto próximo"*, pero su salida no dice **qué** es cada
candidato. Para saber qué eran los top por scent hubo que `OpenAlexSource.fetch_works_by_ids(...)` en
Python. El producto del comando más "information-foraging" del tool es opaco desde el CLI.

### H2. No hay forma de obtener las lecturas centrales desde el CLI

El gesto central del investigador —*"¿cuáles son los papers centrales? acepto ese núcleo"*— no tiene
camino CLI. Lo que hice para aceptar los 25 centrales:

```
b2g build                              # genera GraphML con degree_centrality (capa decorate)
→ Python: nx.read_graphml + degree_centrality + ordenar + extraer node ids
→ b2g accept --ids <25 ids>
```

La centralidad **se calcula** (la capa `decorate` la mete en el GraphML, #25) pero **no es
consultable**: no hay `b2g top`, `b2g rank`, ni `accept --top-central N`. El dato existe, encerrado
en un `.graphml` que el humano no abre a mano.

### H3. Las lecturas fundacionales no son una salida del CLI

El output más valioso de una revisión —el **canon co-citado** (Baker & Faulkner 1993, Wasserman &
Faust 1994, …)— se computó 100% en Python (frecuencia de `references_id` + fetch de títulos).
`clusters.csv` (#31) existe y es útil, pero es **nivel-cluster**, no la **lista rankeada de lecturas**.
No hay `b2g references --top` ni equivalente.

### H4. Facetas seguimos sin tenerlas (confirma G2 de la nota 14)

El histograma por año —la métrica que respondió *"¿qué tan actual/profundo es el campo?"*— otra vez
salió de Python. `status` cuenta por `curation_status` y nada más.

### H5 (menor, contrato). `filter.steps[].criterion` sale `None`

Los pasos PRISMA traen `count_before/count_after/excluded` correctos, pero el nombre legible del
criterio (`criterion`) viene `None`. El conteo es fiel; falta etiquetar **qué** criterio fue cada paso.

### H6 (menor, descubribilidad). La 5ª red aparece sin pista

`b2g build` da 4 redes en silencio si no hay `cited_by_id`; que la co-citación necesita `enrich`
previo solo se sabe leyendo los docs. Un `warning` accionable ("corré `enrich` para la 5ª red")
cerraría el hueco.

### Buena práctica registrada (no es gap)

Descarté un **falso positivo**: "status sin workspace → exit 2" era `uv run b2g` corriendo **fuera
del proyecto uv** ("program not found"), no un fallo de b2g — dentro del proyecto da exit 1 correcto.
Lección de QA: verificar el entorno antes de reportar un exit code anómalo.

## El hueco unificado y su forma: una **superficie CLI de lectura/análisis**

Las tres sesiones apuntan al mismo faltante. El `scripts/analizar.py` que se reescribe cada vez
**es la especificación del comando que falta**. Propuesta consolidada (renumera P6–P8 de la nota 14):

| ID | Comando propuesto | Cierra | Qué hace |
|---|---|---|---|
| **P6** | `b2g list [--limit --sort-by --status --grep --json]` | G1, G3 (n.14) | listar/filtrar/ordenar filas del corpus |
| **P7** | `b2g stats` / facetas en `status` (`--group-by year\|lang\|type`) | G2 (n.14), H4 | distribución del corpus sin Python |
| **P9** | `b2g top` / `b2g rank` (papers por centralidad; refs por co-citación) | H2, H3 | **la salida de investigación**: lecturas centrales + fundacionales como tabla rankeada |
| **P10** | `ranking_preview` con título (no solo `{id, scent}`) | H1 | el forrajeo dice **qué** leer, no un ID |
| **P11** | `accept --top-central N` / `accept --from-ranking` | H2 | aceptar el núcleo central sin pasar por GraphML+Python |
| — | `criterion` legible en `filter.steps` | H5 | etiquetar el paso PRISMA |
| — | warning de "5ª red requiere enrich" en `build` | H6 | descubribilidad |

`b2g top`/`rank` (P9) es el de mayor palanca: es **el resultado** que el investigador busca, hoy
encerrado en GraphML/parquet. Con él (+ P10/P11) el lazo *forrajear → leer lo central → curar* se
cierra sin salir del CLI.

## Por qué importa más allá del CLI (gancho con la GUI #34)

La GUI (`docs/ROADMAP/05-gui.md`) va a necesitar **exactamente esta capa**: listar, facetar, rankear
centrales y fundacionales, leer candidatos del forrajeo con su título. Hoy esa lógica vive
**tres veces en scripts ad-hoc** y **cero veces en el producto**. Construir la superficie de
lectura/análisis en el CLI (la API agente-native, ADR 0010) le da a la GUI su backend natural: la
GUI sería una vista sobre `b2g list/top/rank --json`, no una reimplementación. El `analizar.py`
recurrente no es ruido: es el contrato pendiente entre el núcleo y cualquier frontera (CLI o GUI).

## Lecciones

1. **El script que se reescribe cada sesión es un comando faltante.** Tres veces el mismo
   `analizar.py` ⇒ `b2g list/top/rank` no es opcional.
2. **Producir ≠ entregar.** El CLI genera artefactos (GraphML, parquet, clusters.csv); el
   investigador quiere *lecturas rankeadas*. El último tramo —de artefacto a respuesta— sigue siendo
   manual.
3. **La salida del forrajeo debe ser legible.** Un ranking de IDs sin título contradice el propósito
   del *information scent* (H1).
4. **El dato ya existe; falta exponerlo.** Centralidad, co-citación y facetas se computan en el
   núcleo (`decorate`, proyectores, `metrics.json`); el hueco es de **superficie CLI**, no de cálculo.
