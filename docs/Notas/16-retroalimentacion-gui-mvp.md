# 16 — Retroalimentación de la GUI (MVP v0.7.0, prueba en vivo)

> ⚠️ **NOTA DE SESIÓN — no es decisión ni ADR.** Captura el uso real del MVP de la GUI
> (G1–G5, v0.7.0) por el PO probando como investigador. El objetivo es acumular huecos de
> UX, faltantes de vistas y mejoras del grafo que la próxima iterada debe absorber. Fecha:
> 2026-06-18. Documentos hermanos: [`07-frontend-tool-for-thought.md`](07-frontend-tool-for-thought.md)
> (visión GUI), [`12-arquitectura-gui-encuadre.md`](12-arquitectura-gui-encuadre.md) (arquitectura),
> ADR 0027 (posicionamiento) / 0028 (capa de servicios). Alimenta el **Gate #34** (validación
> con tercero) y la "iterada más" (issue #104 / epic #34).

## Tesis de la sesión

El MVP entregó el **vertical mínimo**: levantar `b2g gui`, ver el grafo de la operación y
curar candidatos. Probándolo de verdad aparecen los faltantes estructurales — no bugs del
contrato, sino que **falta superficie de producto** para ejercer el trabajo bibliotecario
completo. Esta nota los lista para priorizar la siguiente iterada.

> **Setup de la prueba:** install **desde TestPyPI** (el camino real de producción, no el
> editable del repo — alineado con [`verificar-camino-real`]). Los bugs de abajo se ven en
> ese paquete.

## Re-priorización (cambio de secuencia — lo más importante de la sesión)

El grafo se **cuelga** con una red de **489 nodos / 20.535 aristas** (ver H2) — y eso fuerza
una conclusión de producto, no solo un fix: **las redes van DESPUÉS, no primero.** La
secuencia correcta es:

1. **Primero la interfaz de Biblioteca**: buscar, navegar y **curar** el corpus (H1).
2. **Después el grafo**: una vez curado, *eso* es lo que uno quiere ver en la red — aunque
   no siempre sea el grafo lo que se quiera mirar.

Es decir, la red es el **destino** del flujo, no la puerta de entrada. El MVP entró por el
grafo (vertical mínimo de la operación); la iterada debe **invertir el orden**: la Biblioteca
(curación) es el núcleo, el grafo es la proyección final sobre lo ya curado. Esto reordena el
backlog: **H1 sube a prioridad 1; el grafo (H2/H4) baja a "después de curar"** — sin perder
que sus bugs son reales y hay que arreglarlos para cuando se use.

## Hallazgos

### H1 — Falta la **vista de Biblioteca** (la biblioteca viva)

Hoy existe la **vista de grafo**, que es la vista de la *operación* (curar candidatos sobre
la red). Pero falta la otra mitad del trabajo: una **vista de biblioteca** donde el
investigador pueda **buscar, ver y etiquetar** — ejercer el oficio bibliotecario sobre el
corpus como **biblioteca viva** (ADR 0009), no solo sobre el grafo.

- **Qué es:** un lugar para navegar el corpus acumulado (papers ya en el store), buscarlos,
  inspeccionar su ficha y **etiquetarlos** (curación/clasificación manual), independientemente
  de la topología de la red.
- **Por qué importa:** la red es una *proyección* del corpus; el corpus es la unidad de
  trabajo real del bibliotecario. Sin esta vista, la GUI solo cubre la operación de grafo y
  no el ejercicio de mantener viva la biblioteca.
- **Etiquetado (decidido por el PO):** arrancar con **tags libres**; el objetivo es moverse
  luego a una **taxonomía**, pero eso requiere varias cosas (vocabulario controlado,
  migración de tags→términos, UI de jerarquía). → tags libres ahora, taxonomía como fase 2.
- **Búsqueda (decidido por el PO):** las **tres** — texto + campos + filtros. Un **buscador
  con filtros es el mínimo** de la vista.
- **Pendiente:** qué lecturas de servicio hacen falta (¿`service.reads` ya cubre
  listar+buscar+filtrar papers, o falta endpoint?), y cómo persistir los tags en el store.

### H1b — ¿Adoptar BIBFRAME 2.0 como modelo? (pregunta del PO)

El PO nota la deriva ("siento que vamos a mitad de un software de bibliotecas") y propone
evaluar **BIBFRAME 2.0**. **Recomendación: NO adoptarlo como modelo de datos.** Análisis:

- **BIBFRAME 2.0** es el modelo linked-data de la Library of Congress para **reemplazar
  MARC** en catalogación e **intercambio entre instituciones** (Work / Instance / Item +
  Agents / Subjects en RDF). Está optimizado para un problema que bib2graph **no tiene**
  (descripción catalográfica interoperable), y es pesadísimo (RDF, URIs, vocabularios, la
  partición Work/Instance/Item).
- La columna vertebral de bib2graph es **OpenAlex** (Work-centric, ya trae concepts/topics
  por paper) + **redes de citación**. Eso ya es un modelo de trabajo; meter BIBFRAME lo
  re-modelaría entero como RDF sin pagar ningún beneficio del flujo actual.
- La sensación de "software de bibliotecas todo dárораo" es la **señal para resistir** la
  adopción completa, no para abrazarla. Tensiona directamente el **posicionamiento (ADR
  0027)**: bib2graph es tool-for-thought / investigación, no un catálogo institucional.
- **Lo útil sí se puede tomar sin el modelo entero:** para la taxonomía (fase 2), el estándar
  liviano correcto es **SKOS** (linked data *para vocabularios/tesauros*), no BIBFRAME. Y el
  vocabulario puede salir de algo que **ya está en el dato**: los **Topics/Concepts de
  OpenAlex** (atados a cada paper) y/o el tesauro propio (ADR 0031). Si más adelante hace
  falta exportar/interoperar, mapear tags→SKOS es barato; BIBFRAME sería re-fundar el producto.
- **Veredicto:** tags libres → vocabulario controlado (OpenAlex topics + tesauro 0031) →
  SKOS si hace falta interoperar. **BIBFRAME 2.0 fuera de alcance** (revisitable solo si
  aparece el requisito de intercambio catalográfico con una institución).

### H2 — La **vista de grafo** necesita mejoras (rendimiento + estética + controles)

El grafo actual tiene tres problemas que se notan al usarlo con corpus reales:

1. **Escala (BLOQUEANTE):** con **489 nodos / 20.535 aristas el grafo se cuelga**
   ("literal se queda"). No es "se ve grande" — es **inusable** a esa escala, que para un
   corpus real es chica. Hay que **limitarlo** (cap de nodos/aristas, top-N por centralidad,
   filtro por cluster, render incremental) **antes** de pintar. Este es el hallazgo que
   motiva la re-priorización (grafo va después de curar).
2. **Estética:** a veces **se ve feo** (layout apelmazado / ilegible).
3. **Controles:** debería haber **controles de usuario** para que dibujar el grafo sea
   fácil (ajustar layout, filtros, densidad, agrupar, re-correr el layout).

- **Posible cambio técnico:** evaluar un framework como **Sigma.js** (WebGL) en lugar de /
  además de Cytoscape — **solo si trae ventaja real** (rendimiento en grafos grandes). NO
  cambiar por cambiar; medir primero contra Cytoscape/fcose actual con un grafo grande real.
- **Criterio:** la ventaja a probar es *renderizar grafos grandes fluido*; la estética y los
  controles son requisito independiente del framework (se pueden mejorar sin migrar).

### H4 — BUG: click en un nodo del grafo → **se pone todo negro**

Al hacer **click sobre un nodo** del grafo, **la vista entera se vuelve negra**. Es un bug
de la GUI buildeada (visto en el install de TestPyPI), no un faltante de producto.

- **Severidad:** alto — rompe la interacción básica de selección de nodo.
- **Hipótesis a investigar (sin diagnosticar aún):** estilo de selección de Cytoscape que
  pinta todo (selector `:selected` / `core` mal aplicado), un re-layout/re-render que
  colapsa, o un error JS no capturado que tumba el canvas. **Diagnosticar la causa raíz antes
  de tocar** (no parchar a ciegas).
- **Repro:** `b2g gui` (paquete TestPyPI) → abrir un grafo → click en cualquier nodo.

### H3 — La documentación está **demasiado densa** (consolidar y aligerar)

La doc se escribió **a la par del trabajo**, iterando — por eso acumuló capas y muestra
**muchas cosas que pueden confundir al usuario**. Ahora que la visión está estabilizada
(v0.7.0, MVP entregado), tiene sentido **consolidar la visión actual y reescribir la doc más
ligera**: menos superficie, podar lo histórico/intermedio, dejar lo que un usuario nuevo
necesita.

- **Qué podar:** ADRs/notas/roadmap que reflejan el camino recorrido (drift, iteraciones
  superadas), no el estado actual. Conservarlos como histórico, pero **sacarlos de la ruta
  de lectura del usuario**.
- **Qué consolidar:** una entrada clara y corta (README / Quickstart / "qué es esto") que
  refleje la visión consolidada, sin obligar a leer el registro de decisiones.
- **Alinear con** [`doc-mantenimiento`] (anti doc-bloat: carpeta por hitos, índice limpio).
- **Ojo:** separar **doc de usuario** (ligera, de cara afuera) de **doc de agentes/dev**
  (AGENTS.md, ADRs) — la densidad molesta sobre todo en la primera.

## Próximos pasos (no decididos — para priorizar con el PO)

- [ ] Definir alcance de la **vista de Biblioteca** (H1): búsqueda + ficha + etiquetado.
      Revisar si la capa de servicios (`service.reads`) ya soporta listar/buscar papers o
      hay que sumar lecturas + endpoints API.
- [ ] **Spike de rendimiento del grafo** (H2): medir Cytoscape/fcose vs. Sigma.js con un
      grafo grande real (p.ej. `valoraciones`) antes de decidir migración.
- [ ] Diseñar **controles del grafo** (cap de nodos, filtros, re-layout) — independiente del
      framework.
- [ ] **Aligerar la documentación** (H3): consolidar la visión v0.7.0 en una ruta de lectura
      corta de usuario; podar el histórico de la ruta principal (mantenerlo como archivo).
- [ ] Cerrar el modelo de etiquetado: tags libres ahora, **SKOS + OpenAlex topics** para la
      taxonomía fase 2; **BIBFRAME 2.0 descartado** como modelo (H1b).
