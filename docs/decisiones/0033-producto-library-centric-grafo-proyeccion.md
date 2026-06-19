# 0033 — Producto library-centric: la Biblioteca es la superficie primaria; el grafo es proyección

- **Estado:** Propuesta
- **Fecha:** 2026-06-18
- **Refina a:** [0027](0027-pivote-posicionamiento-gui-local.md) (pivote de posicionamiento GUI).
  0027 fijó *qué* es el producto (GUI local opt-in para semi-técnicos, diferenciador = diff de
  rondas). Este ADR **no lo revierte**: precisa **por dónde entra el usuario** a esa GUI tras el
  feedback real del MVP. No reabre 0027 (firmado); lo refina con un bloque nuevo.
- **Relacionada con:** [0009](0009-biblioteca-viva-duckdb.md) (biblioteca viva = unidad de trabajo),
  [0032](0032-capa-servicios-duena-del-flujo.md) (el servicio dueño del flujo lo habilita),
  [0034](0034-etiquetado-tabla-tags-lateral.md) (etiquetado, parte del ejercicio bibliotecario).
- **Encuadre:** [Nota 16](../Notas/16-retroalimentacion-gui-mvp.md) §Re-priorización/§H1 +
  [Nota 18](../Notas/18-flujo-canonico-biblioteca.md). **Decidido por el PO (2026-06-18).**
- **Epic:** GUI local [#34](https://github.com/complexluise/bib2graph/issues/34).

## Contexto

El MVP de la GUI (G1–G5, v0.7.0) entregó el **vertical mínimo entrando por el grafo**: levantar
`b2g gui`, ver la red de la operación y curar candidatos sobre ella. Dos rondas de feedback real
—la prueba en vivo del PO (Nota 16) y la validación de un tercero desde TestPyPI (Nota 17)— mostraron
dos cosas convergentes:

1. **El grafo se cuelga a escala normal** (489 nodos / 20.535 aristas, corpus real; Nota 16 §H2,
   confirmado por el tercero en Nota 17). No es caso extremo: es escala corriente.
2. **Falta la otra mitad del trabajo:** un lugar para **buscar, navegar, inspeccionar y etiquetar**
   el corpus como biblioteca viva, independiente de la topología de la red (Nota 16 §H1).

La conclusión de producto del PO: **la red es el destino del flujo, no la puerta de entrada.** El
trabajo real es el **ejercicio bibliotecario** sobre la biblioteca viva (la Épica C del PRD §7, que
ya existía pero no era la superficie primaria de la GUI). La red es una **proyección** que se computa
cuando la curación lo amerita.

Esto **no contradice** 0027 (GUI local tool-for-thought para semi-técnicos): lo precisa. El
diferenciador "diff de rondas / git de la investigación" sigue en pie; opera **sobre la biblioteca
curada**, que es justamente lo que la vista de Biblioteca permite construir.

## Decisión

**El producto es library-centric: la vista de Biblioteca (buscar / navegar / inspeccionar /
etiquetar / curar sobre la biblioteca viva) es la superficie primaria de la GUI; el grafo es una
proyección downstream que se visita cuando la curación lo amerita.**

1. **La vista de Biblioteca es prioridad 1 de la iterada**, no una feature más. Cubre: lista del
   corpus acumulado, **búsqueda (texto + campos + filtros — las tres)**, ficha del paper,
   **etiquetado** (tags libres; ADR 0034) y curación (accept/reject, ya existe). Es el ejercicio del
   oficio bibliotecario sobre el corpus, independiente del grafo.

2. **El grafo baja a "después de curar".** Sigue siendo un destino legítimo y sus bugs son reales
   (cap de nodos; bug del nodo negro, Nota 16 §H2/§H4) — se arreglan, pero **dejan de ser la puerta de
   entrada**. La proyección se computa sobre lo curado.

3. **Encuadre, no modelo de datos nuevo.** Esta decisión es de **producto/posicionamiento**: no
   cambia el `Corpus`, el `CycleState` ni el contrato. Lo habilita la capa de servicios dueña del
   flujo (ADR 0032: `search_papers`, `tags`) + el etiquetado lateral (ADR 0034).

4. **BIBFRAME 2.0 queda FUERA de alcance** como modelo de datos (Nota 16 §H1b). La deriva "esto parece
   software de bibliotecas" es señal para **resistir** la catalogación interoperable RDF, no para
   abrazarla: tensiona el posicionamiento tool-for-thought de 0027. Lo útil para la taxonomía (fase 2)
   se toma sin el modelo entero: **SKOS** para vocabularios + **Topics/Concepts de OpenAlex** ya
   presentes en el dato + el tesauro propio (ADR 0011/0031). BIBFRAME es reabrible solo si aparece el
   requisito real de intercambio catalográfico con una institución.

## Consecuencias

- (+) **El producto cubre el trabajo real** (curar la biblioteca), no solo la operación de grafo. La
  GUI deja de ser una data-app de visualización y pasa a ser el tool-for-thought que 0027 prometía.
- (+) **Reordena el backlog con criterio:** Biblioteca (búsqueda/tags) sube; grafo (cap + bugs) baja a
  "después de curar". Sin perder que los bugs del grafo son reales.
- (+) **No reabre 0027 ni rompe el contrato:** es un refinamiento de la puerta de entrada, no del
  modelo de producto ni de datos.
- (−) **Más superficie de GUI en la iterada** (vista de Biblioteca completa: lista, búsqueda, filtros,
  ficha, tags). Asumido como el núcleo del valor, no como adorno.
- (−) **El esfuerzo de visualización del grafo** (cap de nodos, controles, spike de framework) no
  desaparece: se difiere, no se cancela. Hay que comunicar que el grafo "ya casi anda" no es el foco
  inmediato.
- (−) **Tentación recurrente de BIBFRAME/catalogación:** cada vez que el etiquetado crezca hacia
  taxonomía reaparecerá. Este ADR fija el límite (SKOS + OpenAlex topics, no BIBFRAME) para no
  re-litigarlo cada iterada.
