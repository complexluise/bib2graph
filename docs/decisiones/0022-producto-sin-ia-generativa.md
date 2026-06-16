# 0022 — El producto no usa IA generativa; la "inteligencia" del forrajeo es estructura bibliométrica

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Decidido por:** Product Owner humano (tras el red-team de la
  [`../Notas/06-critica-as-built-v0.2.md`](../Notas/06-critica-as-built-v0.2.md))
- **Relacionada con:** [0008](0008-wedge-forrajeo.md) (wedge = forrajeo; tensiones removidas),
  [0011](0011-thesaurus-multilingue.md) (thesaurus determinista, sin fallback LLM),
  [0020](0020-metodo-forrajeo-scent-filtros-reject.md) (scent = estructura bibliométrica),
  [`../Notas/04-direccion-ia-in-the-loop.md`](../Notas/04-direccion-ia-in-the-loop.md) (base de la
  "máquina de tensiones", ahora abandonada),
  [`../Notas/05-ciclo-investigacion-humano.md`](../Notas/05-ciclo-investigacion-humano.md)

## Contexto

El giro "IA in the loop" (Notas 04/05) proponía **dos puntos de inserción de IA** en el producto:
nº1 (forrajeo) y nº2 (sensemaking / "máquina de tensiones"). El red-team del AS-BUILT v0.2
([Nota 06](../Notas/06-critica-as-built-v0.2.md), RAÍZ 1) mostró que esa IA-en-el-producto es **casi
vapor**: el forrajeo rankea por un **conteo aritmético** (no bibliometría, no IA), la curación es
**100% humana**, y el único gancho de LLM (`explain_candidate`) es un `NotImplementedError`
permanente con el extra `[llm]` vacío. README/AI_DISCLOSURE/Nota 05, en cambio, **venden IA en el
producto** ("forrajeo y curación asistidos", "bibliometría como information scent para la IA").

Había, por tanto, drift entre lo que se promete y lo que existe, y una decisión estratégica
pendiente: ¿se construye la IA prometida o se reposiciona el claim?

## Decisión

**El producto NO usa IA generativa.** La "inteligencia" que asiste el forrajeo es **estructura
bibliométrica como *information scent***, **determinista y reproducible** (acoplamiento / co-citación
/ centralidad sobre el corpus curado), **sin LLM ni embeddings**.

1. **Se eliminan del producto** `explain_candidate`, el módulo `foraging/explain.py`, el extra
   `[llm]` y la idea de "thesaurus fuzzy con LLM". El scent **deja de ser** un conteo aritmético y
   pasa a consumir los **proyectores** (ADR [0020](0020-metodo-forrajeo-scent-filtros-reject.md)
   actualizado).
2. **La máquina de tensiones / sensemaking asistido por IA se retira del alcance por completo** — no
   se difiere a v2: se **borra** del producto y se reconcilian las Notas/ADRs que la insertaban (ADR
   [0008](0008-wedge-forrajeo.md) actualizado). El **sensemaking sigue siendo humano**, asistido por
   las redes (no por IA).
3. **Queda un solo sentido de "AI-in-the-loop":** el *desarrollo* de la librería es asistido por IA
   (ver [`../../AI_DISCLOSURE.md`](../../AI_DISCLOSURE.md)); el *producto* **no** usa IA. Ya no hay
   "dos inserciones de IA": hay **una inserción algorítmica** (forrajeo por estructura
   bibliométrica), que no es IA.

## Consecuencias

- **Honestidad total entre lo prometido y lo construido:** README, AI_DISCLOSURE, PRD y Nota 05 se
  reescriben a "una inserción algorítmica, sin IA en el producto". Desaparece la sobre-venta que la
  Nota 06 marcó.
- **Reproducibilidad de punta a punta:** sin LLM ni embeddings, el forrajeo, la curación y el
  análisis son **deterministas** — coherente con el ADR
  [0017](0017-reproducibilidad-historia-snapshot.md) (snapshot reproducible bit a bit).
- **Se pierde el "moat" candidato** (la detección de tensiones, Nota 04 §5). Trade-off asumido: el
  diferenciador de la V1 descansa en **biblioteca viva curada + ecuación consciente + estructura
  bibliométrica de primera clase + CLI agente-native abierto**, no en una capa de IA. Si en el
  futuro se quisiera una capa asistida, sería una **decisión nueva** (ADR nuevo), no un default.
- **Desaparece la rama de IA de la arquitectura** (ARCHITECTURE §3.5/§7): el grafo de dependencias
  no tiene un sub-árbol LLM; el forrajeo (costura) depende del **núcleo de proyección** (puro).
- **Recomendación para el `coder`:** borrar `foraging/explain.py` y el extra `[llm]` de
  `pyproject.toml`; quitar `explain_candidate` de la superficie pública; reescribir `foraging/scent.py`
  para consumir proyectores (ver ROADMAP Hito R1). Tratar las Notas 04/05 que prometían tensiones
  como historia, anotando qué se abandonó.
