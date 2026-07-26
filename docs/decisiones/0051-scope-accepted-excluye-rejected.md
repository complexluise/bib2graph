# 0051 — `--scope accepted` excluye a los `rejected` (rechazar semillas se refleja en el scope aceptado)

- **Estado:** **Aceptada** (2026-07-26). El PO eligió la **opción (a)** del issue
  [#307](https://github.com/complexluise/bib2graph/issues/307). Implementada en **0.14.0**
  (`corpus.py::scoped`), aditiva sobre el envelope (no bumpea `schema="1"`).
- **Fecha:** 2026-07-26
- **Decidido por:** la **bifurcación de fondo la decidió el Product Owner** (opción (a) vs. scope nuevo
  vs. documentar la no-exclusión); el **encuadre** —que (a) es la coherente con PRISMA y con los
  consumidores que hacen `.exclude(rejected)`, y que el cambio es aditivo sin tocar el contrato del
  envelope— es síntesis de la IA (architect). Milestone **0.14.0**.
- **Origen:** issue [#307](https://github.com/complexluise/bib2graph/issues/307) (hallazgo de QA de la
  sesión capstone): con 398 semillas, `curate filter --year-gte 2015` rechazó 99 papers, pero
  `export --format arrow --scope accepted` seguía devolviendo **398 filas** —los `rejected` no salían
  del scope `accepted`.
- **Enmienda a [0021](0021-cli-agente-native-contrato.md)** (semántica de `--scope`) y a la definición
  de `Corpus.scoped('accepted')` (§1.2 de `docs/API.md`). **No** toca la FSM
  ([0016](0016-maquina-estados-lazo.md)) ni la precedencia de inclusión manual de
  [0044](0044-precedencia-inclusion-manual-en-curate.md) (ver Consecuencias).

## Contexto

`Corpus.scoped('accepted')` (`corpus.py`) definía el scope como
`is_seed == True OR curation_status == 'accepted'`. **No** excluía a los `rejected`. Como casi todo
corpus real es *seed-heavy* (las semillas dominan), rechazar una semilla vía `curate reject` o
`curate filter` **no se reflejaba** en el scope `accepted`: la semilla rechazada seguía apareciendo
porque la rama `is_seed == True` la incluía sin más.

Consecuencias del bug, verificadas en uso real (#307):

- **La curación PRISMA de semillas quedaba inefectiva en `accepted`.** El scope pensado para "el
  corpus que sobrevivió a la curación" incluía papers explícitamente rechazados.
- **Inconsistencia con consumidores downstream.** Un consumidor que hace
  `.exclude(curation_status='rejected')` sobre el Arrow obtenía un conjunto distinto del que devolvía
  `--scope accepted` para el mismo corpus.
- **No existía ningún scope que diera "todo menos rejected".** Ni `accepted` ni `seeds_only` excluían
  rechazados; solo `curate filter` marcaba el estado, sin scope que lo consumiera.

El issue #307 planteó tres opciones: **(a)** `scoped('accepted')` →
`(is_seed OR accepted) AND status != 'rejected'`; **(b)** un scope nuevo `curated`/`not_rejected`;
**(c)** documentar explícitamente que la rechazación no aplica a semillas.

## Decisión

Se adopta la **opción (a)**. `Corpus.scoped('accepted')` pasa a ser:

```
(is_seed == True OR curation_status == 'accepted') AND curation_status != 'rejected'
```

Una semilla **rechazada** queda **excluida** de `accepted`, aunque sea semilla. El scope "aceptado"
refleja la curación PRISMA también sobre las semillas.

**Por qué (a) y no (b)/(c):**

- **(a) es la semántica que el usuario ya espera** de "aceptado": un paper rechazado no debería salir
  en el scope de los que sobrevivieron. Es lo que hace el consumidor downstream con
  `.exclude(rejected)` —(a) alinea `--scope accepted` con esa convención sin pedirle al consumidor que
  post-filtre.
- **(b) un scope nuevo** multiplicaría el vocabulario de `--scope` (hoy `all`/`accepted`/`seeds`) sin
  resolver la inconsistencia: `accepted` seguiría incluyendo rechazados y el usuario tendría que
  descubrir un tercer token para lo que ya esperaba de `accepted`. **Descartada.**
- **(c) documentar la no-exclusión** deja el footgun en pie: el scope pensado para curación no
  reflejaría la curación. **Descartada.**

### Alcance: `seeds_only` NO cambia (decisión explícita, no omisión)

`Corpus.scoped('seeds_only')` sigue siendo `is_seed == True` **sin** excluir rejected: una semilla
rechazada **sí** aparece en `seeds_only`. Es **deliberado**, no deuda:

- `seeds_only` responde una pregunta **estructural** —"¿cuál fue el conjunto de partida?"— no una de
  **curación**. Es el scope que reconstruye la cohorte sembrada original (p. ej. para el numerador de
  un diagrama PRISMA: "de N semillas, se excluyeron K"). Excluir los rechazados ahí **borraría** la
  información que PRISMA necesita mostrar.
- La exclusión de rechazados es propia del scope **`accepted`** ("lo que sobrevivió"); `seeds_only`
  es su complemento estructural ("lo que entró"). Alinear ambos colapsaría dos preguntas distintas.

El comentario `NOTA(#307)` en `corpus.py::scoped` (rama `seeds_only`) queda como marca de que la
no-exclusión es **decidida acá**, no pendiente. Si en el futuro apareciera una necesidad real de un
"seeds sin rechazados", sería un scope o flag nuevo con su propio issue —no un cambio silencioso a
`seeds_only`.

## Consecuencias

**Lo que se gana**

- **`--scope accepted` refleja la curación.** Rechazar una semilla (por `curate reject` o
  `curate filter`) ahora la saca del export/proyección `accepted`, como el usuario espera.
- **Coherencia con consumidores externos.** `--scope accepted` coincide con
  `.exclude(curation_status='rejected')` sobre el Arrow —no hay dos verdades para "el corpus aceptado".
- **La curación PRISMA de semillas es efectiva** end-to-end: filtrar por año/idioma/tipo sí encoge el
  scope aceptado.

**Lo que cuesta / a tener en cuenta**

- **Cambio de contrato (BREAKING de comportamiento, no de forma).** El mismo corpus + el mismo
  `--scope accepted` puede devolver **menos filas** que antes (las rechazadas). Un consumidor que
  dependía de que `accepted` incluyera rechazados (improbable, contra-intuitivo) vería el cambio. El
  envelope **no** cambia de forma (`schema="1"` intacto); es la **semántica del scope** la que cambia.
- **`corpus_hash` de un `scoped('accepted')` cambia** cuando hay rechazados en juego (el subconjunto es
  otro). La pureza/determinismo de `scoped` se mantiene: dos llamadas con el mismo scope sobre el mismo
  corpus siguen dando el mismo hash.
- **No toca [0044](0044-precedencia-inclusion-manual-en-curate.md).** La precedencia "la inclusión
  manual gana" es de `curate filter` (qué **marca** rejected); este ADR es sobre qué **lee** el scope
  `accepted`. Un paper `accepted` explícito nunca es `rejected` a la vez (los estados son mutuamente
  excluyentes en `curation_status`), así que la rama `is_seed OR accepted` y el `AND != rejected` no se
  pisan: un aceptado explícito nunca cae por el nuevo `AND`.

## Alternativas

- **(b) scope nuevo `curated`/`not_rejected`.** Descartada: agrega vocabulario sin arreglar que
  `accepted` incluya rechazados; el usuario seguiría necesitando descubrir el token nuevo para lo que
  ya espera de `accepted`.
- **(c) documentar que la rechazación no aplica a semillas.** Descartada: deja el footgun; el scope
  pensado para curación no reflejaría la curación.
- **Alinear también `seeds_only`** (excluir rejected ahí). Descartada: `seeds_only` es estructural
  ("qué entró"), no de curación; excluir rechazados borraría el numerador PRISMA. Ver §Alcance.
