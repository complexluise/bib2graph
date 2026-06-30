# 27 — El recibo de demo: bib2graph como functor honesto, el kernel de juicio mínimo y cómo hacer explícito el one-shot

> **Fecha:** 2026-06-27. **Estado:** desarrollo de idea (note-first). Disparada por
> la lectura crítica de Evgeny Poberezkin, *"The Future of Software Engineering"*
> (feb-2026) cruzada con el estado real de la superficie CLI 0.10.0
> ([ADR 0037](../decisiones/0037-superficie-cli-10-verbos-ciclo.md),
> [ADR 0038](../decisiones/0038-destino-verbos-huerfanos-0037.md)).
>
> **Tesis:** el artículo describe un futuro donde el software se "compila" por una
> cadena de functores (propósito → capacidad → diseño → código → deploy) y aposta a
> que eso requiere un *Artificial Intellect* que todavía no existe. **bib2graph ya
> tiene tres de las piezas de ese compilador funcionando en `dev`** —el ciclo como
> functor chain, `status` como verificador determinista en la frontera, y `maturity`
> como recibo— y **no necesita AGI para tenerlas, porque las apoya en verificación
> determinista, no en cumplimiento probabilístico de un LLM.** El one-shot agents-first
> (intencional, para demo) es el lugar donde esas piezas se podrían volver deshonestas
> —cruzar fronteras en silencio— y el trabajo es hacerlo **explícito**: que el demo
> deje recibo de lo que asumió. Engancha con la [Nota 05](05-ciclo-investigacion-humano.md)
> (fundamentación del ciclo) y la [Nota 20](20_ciclo_investigacion_hallazgos_teoricos.md)
> (hallazgos del corpus).

---

## 0. El disparador

El artículo de Poberezkin hace una apuesta fuerte y una observación correcta. La
observación: *lo difícil del software siempre fue especificar, no escribir código*;
con LLMs, especificar es **la única parte que sigue requiriendo una persona**. La
apuesta: el software del futuro se "compila" a través de una cadena de **functores**
—transformaciones que preservan estructura entre capas (propósito, capacidad, diseño,
código, criterios de aceptación, deploy)— y si cada functor adyacente es correcto, el
mapeo punta-a-punta es correcto *por un teorema de teoría de categorías, no por
conocimiento empírico*. Pero el artículo condiciona todo a un **AGI hipotético** que
sepa "verificar constraints en cada frontera de functor", y descarta los sistemas
actuales por "esconder el problema detrás de retries y orquestación determinista".

Ahí el artículo se contradice solo: llama *esconder el problema* a la verificación
determinista cuando la usan los LLMs de hoy, y *el futuro* a la misma verificación
determinista cuando la usaría su AGI. **Es la misma arquitectura con dos nombres.** Y
esa contradicción es exactamente la grieta por donde bib2graph entra: el verificador
determinista en la frontera **no requiere AGI, ya está construido.**

El segundo disparador es una aclaración del PO: el one-shot del ciclo agents-first es
**intencional, y es para demo** —que un LLM pueda correr el ciclo de punta a punta
para *mostrarlo*. Justamente por eso importa que sea **explícito**: un demo honesto no
es el que esconde dónde se saltó el rigor, es el que lo **declara**.

---

## 1. bib2graph ya es el compilador de functores honesto

El reporte de superficie (2026-06-27) confirma que tres de las seis piezas que el
artículo pone en el futuro ya están en `dev`:

| Idea del artículo (futuro con AGI) | Pieza en bib2graph hoy | Dónde |
|---|---|---|
| Functor entre capas adyacentes | El ciclo `init→seed→chain→build→read`; cada verbo *es* un functor entre dos capas del ciclo de investigación | [ADR 0037 §verbos](../decisiones/0037-superficie-cli-10-verbos-ciclo.md) (tabla 82-94) |
| Verificación de constraints en la frontera del functor | `status.readiness` + `status.build_preview`: **función pura, determinista, fuente única con los proyectores**; predice si una red saldría vacía *sin proyectar el grafo* y da el `fix_command` exacto | `src/bib2graph/cli/commands/status.py:39-168`, `src/bib2graph/networks/facade.py:437-515` |
| El "recibo" de lo que se compiló y cómo | El bloque `maturity: {curated, scope, empty_networks}` que `build` estampa en el artefacto | [ADR 0037 §f](../decisiones/0037-superficie-cli-10-verbos-ciclo.md), [ADR 0038](../decisiones/0038-destino-verbos-huerfanos-0037.md) (P3) |

Esto da vuelta el argumento del artículo. Poberezkin necesita un AGI porque cree que
verificar la frontera de un functor requiere *entender*. No requiere entender: requiere
un **predicado determinista sobre el estado del corpus**, que es justo lo que
`predict_build_preview` ya hace cuando dice *"0/15 papers con `keywords_id` → la red de
keywords saldría vacía → `b2g seed --resolve`"*. Eso es el oráculo en la frontera del
functor `chain → build`, y no tiene una sola línea de IA generativa (coherente con el
[ADR 0022](../decisiones/0022-producto-sin-ia-generativa.md)).

**La consecuencia profunda:** el "moat" del que habla el artículo —cuando la generación
se vuelve commodity, el valor migra al verificador— bib2graph lo tiene del lado correcto.
El verbo que más valor concentra no es el que *genera* (build), es el que *rechaza o
advierte* (status). Esa es la apuesta arquitectónica correcta, y conviene nombrarla
como tal.

---

## 2. La grieta: la verificación es información, no registro

El reporte trae la frase clave: *"No hay gates programáticos —`status` expone la
información para que el agente decida no avanzar, pero el CLI no bloquea transiciones."*

Esto es **correcto por diseño** (un gate duro mataría el demo, y mataría la autonomía
del agente que el ADR 0021 quiere preservar). Pero abre un hueco: cuando el one-shot
cruza una frontera en `readiness.ready == False` —porque un demo tiene que correr de
punta a punta sí o sí— ese cruce es **silencioso**. Y "silencioso" es exactamente la
palabra con la que el artículo condena al vibecoding: *el sistema esconde dónde se
rompió el rigor; nadie sabe qué hace más allá de cierto umbral*.

El antídoto no es poner gates. Es hacer que **el cruce deje cicatriz**. La idea
unificadora: **generalizar el `maturity` block —que ya existe— de "¿se curó?" a un
recibo completo de lo que el one-shot asumió en cada frontera.** Tres campos nuevos,
cada uno aterrizando una tensión distinta del artículo.

### 2.1 `crossed_red` — fronteras cruzadas en rojo *(verificación → registro)*

Cada vez que el one-shot avanzó con `status.readiness.ready == False`, se estampa en
el recibo: **qué frontera** (p. ej. `chain` con 0/N seeds con `source_id`), **qué razón**
daba el readiness, y **qué `fix_command` se ignoró**. No bloquea —deja recibo. Esto
convierte el `readiness` advisory que ya existe en algo **auditable** sin cambiar su
naturaleza: la misma información, pero persistida como hecho del artefacto en vez de
impresa y olvidada.

> Esto responde directo a la matemática de compliance del artículo (70%→50%→35% por
> nivel de delegación de LLMs). Esa cascada asume *fallas independientes y sin
> verificación entre niveles*. Con un recibo de `crossed_red`, las fronteras dejan de
> ser independientes: cada una declara su estado, y el límite ya no es 0.7ⁿ sino la
> tasa de falsos del verificador determinista —un problema mucho mejor.

### 2.2 `assumed_judgment` — el kernel de juicio humano que el demo simula

El one-shot saltea curación (`--scope all`, sin `accept`/`reject`) y elige
pregunta/fuentes por default. Esos son **exactamente** los puntos donde el Product
Owner es irreemplazable según el artículo —la "capa de sabiduría": decidir *qué
construir, para quién, qué trade-off es aceptable*. El error de diseño de casi todos
los sistemas human-in-the-loop es dejar al humano *en todas partes*. El trabajo de
ingeniería es el contrario: **hacer ese kernel lo más chico y crujiente posible**, y
que el demo **declare qué partes de ese kernel simuló**.

El recibo lista, entonces: *"curación omitida (scope=all); N papers que un humano
probablemente habría revisado [heurística]; pregunta de investigación tomada por
default"*. Con esto, el kernel de juicio mínimo deja de ser un aura inanalizable y se
vuelve **una superficie con tipos**: el conjunto declarado de decisiones que solo un
humano toma, y que el one-shot marca como *simuladas* cuando corre solo.

> Definir ese conjunto es, además, definir qué significa "Product Owner" en el flujo de
> bib2graph (engancha con [Nota 05](05-ciclo-investigacion-humano.md) y el rol del PO en
> [`/feature-cycle`](../../.claude) ). El humano no aprueba cada paso: responde en las
> fronteras marcadas como `assumed_judgment`.

### 2.3 `orphans` — trazabilidad río arriba *(el functor de verdad)*

Un functor "preserva estructura" solo si **nada queda colgando**: cada objeto de una
capa mapea a algo en la adyacente. `build_preview` ya detecta el huérfano **río abajo**
(red que *saldría* vacía). Falta el huérfano **río arriba**: nodos del grafo construido
que no trazan a ninguna seed ni a la pregunta de investigación. En una investigación
real eso es deuda silenciosa; en un demo es **la cicatriz visible de la velocidad**, y
es chequeable determinísticamente sobre el grafo que `build` ya produce.

Acá el uso honesto de la idea categorial **no es** probar corrección punta-a-punta
(eso es el teatro del artículo, que depende de un `if` —que el sistema *sea*
formalizable como tipo— que nunca se cobra). El uso honesto es la **propagación de
cambios y la detección de huérfanos**: cuando algo cambia río arriba (una seed se
quita, la pregunta se reformula), qué nodos quedan sin sustento. Eso es trazabilidad,
no demostración —y es lo que un grafo de entidades-y-morfismos como el de bib2graph
sabe hacer.

---

## 3. Por qué esto cierra el argumento

Con los tres campos, **el one-shot deja de competir con el rigor y pasa a
instrumentarlo.** Es el mismo functor chain, corrido con todos los gates en verde por
default, pero que **imprime el recibo** de lo que asumió. Eso lo vuelve una herramienta
de demostración legítima en vez de un truco de vibecoding.

Y de yapa, da gratis el modo no-demo. El **modo riguroso es el mismo pipeline con
`crossed_red` vacío y `assumed_judgment` resuelto** —porque un humano respondió en cada
frontera marcada. No hay dos arquitecturas (una "demo" y una "seria"): hay una sola, y
el recibo mide *cuánto humano tuvo*. El demo es el extremo `crossed_red = todo,
assumed_judgment = todo`; la investigación pulida es el extremo opuesto; todo lo demás
es un punto intermedio honesto y declarado.

Esto es, exactamente, lo que el artículo dice que hace falta para que el software del
futuro no sea vibecoding —*"hacer explícito dónde se violan los constraints antes de
que se compongan"*— pero construido sobre lo que ya existe en `dev`, sin esperar al
*Artificial Intellect*.

---

## 4. Qué sigue (no es código todavía)

Esto es desarrollo de idea. El camino del flujo sería:

1. **Esta nota** (hecho) — captura el argumento y lo engancha con el corpus teórico.
2. **Discusión / decisión**: si la idea del *recibo de demo* cuaja con el PO, graduar a
   **ADR** el contrato del `maturity` extendido — toca [`docs/API.md`](../API.md) (campo
   por contrato público), por lo que requiere ADR antes de mergear (regla de CLAUDE.md).
   Candidato: extender el §f del ADR 0037 / P3 del ADR 0038 en vez de un ADR nuevo.
3. **Issues** acotados, en este orden de menor a mayor juicio humano involucrado:
   - `crossed_red`: registrar cruces de `readiness.ready == False` en `maturity`
     (cambio chico, fuente única ya existe en `status.py`).
   - `orphans`: predicado determinista de huérfanos río arriba sobre el grafo de `build`
     (paralelo a `predict_build_preview` en `facade.py`).
   - `assumed_judgment`: lo más delicado —requiere **declarar primero el conjunto
     canónico de decisiones-de-PO** (el kernel mínimo) antes de poder marcarlas como
     simuladas. Probablemente su propia nota/ADR.

### Preguntas abiertas

- **¿`crossed_red` es por-corrida o acumulativo?** Un workspace que corrió el one-shot
  y después se curó a mano, ¿borra el recibo o lo versiona? (Relaciona con `snapshot`.)
- **¿El kernel de juicio mínimo es fijo o por-dominio?** ¿"elegir la pregunta" es
  siempre PO, o hay investigaciones donde una pregunta-default es aceptable?
- **¿Dónde vive el recibo?** ¿Solo en el artefacto de `build`, o `status` lo expone como
  un cuarto campo del envelope (junto a `next_best_action`/`readiness`/`build_preview`)
  para que el agente lo lea *antes* de avanzar?
- **Heurística de `assumed_judgment` sin IA**: ¿con qué predicado determinista se marca
  "este paper probablemente lo habría rechazado un humano" sin caer en IA generativa
  (ADR 0022)? Quizás no se marca el paper, solo se declara *"curación omitida"* y se
  deja el juicio afuera.
