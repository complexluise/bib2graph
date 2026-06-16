# 0008 — Wedge de la V1: forrajeo asistido por estructura bibliométrica (la máquina de tensiones se retira del producto)

- **Estado:** Aceptada · **enmendada 2026-06-15** (la máquina de tensiones ya no se difiere: se
  retira del producto; el forrajeo se asiste por estructura bibliométrica, sin IA — ver "Enmienda")
- **Fecha:** 2026-06-15
- **Relacionada con:** [0007](0007-openalex-backbone.md),
  [`../Notas/04-direccion-ia-in-the-loop.md`](../Notas/04-direccion-ia-in-the-loop.md),
  [`../Notas/05-ciclo-investigacion-humano.md`](../Notas/05-ciclo-investigacion-humano.md)

## Contexto

El giro "IA in the loop" abre **dos puntos de inserción de IA** en el ciclo de investigación
humano (Nota 05 §4): **nº1 — forrajeo/chaining** (pasos 2–3 del ciclo) y **nº2 —
sensemaking/tensiones** (paso 6). La inserción nº2 (la **máquina de tensiones**: clasificar
citas en apoya / refuta / escuelas en conflicto) es el **candidato a *moat*** (Nota 04 §5), pero
es **frontera de investigación**: Scite lo hace cerrado y pago; ContraCrow / SemanticCite lo
abordan en research. Intentarla en la V1 explota el alcance (crítica #1 de la Nota 04 §6).

La Nota 05 §6 dejó la pregunta abierta: ¿la primera versión ataca la inserción 1 o la 2?

## Decisión

La **V1 ataca solo la inserción nº1: forrajeo asistido**. El flujo es
**ecuación → chaining rankeado por *information scent* → curación → redes**. La **máquina de
tensiones se difiere explícitamente a v2**. Los pasos 5 (organizar en evidencia, parcial), 6
(tensiones) y 8 (monitoreo) del ciclo quedan fuera de la V1 (ver [`../PRD.md`](../PRD.md) §2).

## Consecuencias

- **Wedge entregable y ya validado**: el sandbox de intercambio ecológico desigual
  ([`../exploracion/informe_ied_lectura_2.md`](../../exploracion/informe_ied_lectura_2.md)) corre
  este flujo end-to-end con datos reales de OpenAlex.
- La **diferenciación de la V1** descansa en: ecuación consciente + reporte de traducción,
  biblioteca viva curada, ranking por estructura bibliométrica y CLI agente-native — **no** en
  el moat de tensiones.
- **Costo**: el moat llega después; riesgo de parecerse a los *citation-chasers*
  (ResearchRabbit, Inciteful), mitigado por la biblioteca viva y la consciencia de la ecuación.
- v2 retomará la inserción nº2 sobre el mismo sustrato (la biblioteca viva ya curada es el
  contexto que hace buena la detección de tensiones). *(Superado por la enmienda de abajo: la
  máquina de tensiones se retira del producto, no se difiere.)*

## Enmienda — 2026-06-15 (la máquina de tensiones se retira del producto; el forrajeo no usa IA)

> Motivada por el red-team del AS-BUILT v0.2
> ([Nota 06](../Notas/06-critica-as-built-v0.2.md), RAÍZ 1) y la decisión del PO de que **el producto
> no usa IA generativa** (ADR [0022](0022-producto-sin-ia-generativa.md)). El cuerpo del ADR (arriba)
> queda como historia; esta enmienda corrige dos cosas.

1. **La máquina de tensiones (inserción de IA nº2) se RETIRA del producto — no se difiere a v2.** No
   es "moat futuro": se **borra** del alcance y de las Notas/ADRs como inserción de IA. El
   **sensemaking sigue siendo humano**, asistido por las redes (no por IA). Ya **no hay "dos puntos
   de inserción de IA"**: queda **una inserción algorítmica** (el forrajeo), que no es IA.
2. **El forrajeo se asiste por estructura bibliométrica determinista**, no por IA: el *information
   scent* usa los proyectores (acoplamiento / co-citación / centralidad), sin LLM (ADR
   [0020](0020-metodo-forrajeo-scent-filtros-reject.md) enmendado). El "porqué" de un candidato lo da
   la estructura visible; no hay `explain_candidate` ni `[llm]`.

**Diferenciador de la V1 (revisado):** ecuación consciente + reporte de traducción, biblioteca viva
curada, **estructura bibliométrica de primera clase como olfato** y CLI agente-native **abierto** —
no un moat de IA. Si en el futuro se quisiera una capa asistida por IA, sería un **ADR nuevo**, no un
default reactivado.
