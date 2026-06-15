# 0008 — Wedge de la V1: forrajeo asistido; la máquina de tensiones se difiere a v2

- **Estado:** Aceptada
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
  contexto que hace buena la detección de tensiones).
