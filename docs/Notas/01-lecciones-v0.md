# Lecciones de v0 — postmortem y reglas de diseño

> Anti-patrones reales encontrados en el código de v0 de `bib2graph`, cada uno con la
> **regla de diseño** que la reescritura adopta en respuesta. Las referencias `archivo:línea`
> apuntan al código de v0 (ver [`referencia/arquitectura-v0.md`](03-referencia/arquitectura-v0.md)
> y [`referencia/roadmap-v0.md`](03-referencia/roadmap-v0.md)). Fecha: 2026-06-14.

Estas lecciones no son retórica: son la justificación concreta de la arquitectura objetivo
(ver [`ARCHITECTURE.md`](../ARCHITECTURE.md) §8) y de los ADRs en [`decisiones/`](../decisiones/).

---

## 1. Secreto embebido en el repositorio

**v0:** una clave de API de Semantic Scholar estaba **hardcodeada como fallback literal** en
`enriquecimiento.py:56` (`os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "L5Ejf...")`). Quedó en
el repo y en el historial de git.

**Regla:** **configuración inyectada, nunca secretos embebidos.** Ninguna clave aparece como
literal en el código; se inyecta por config/CLI o entorno. Si no hay clave, se usa el
endpoint público o se falla con un mensaje claro — nunca un default secreto.
→ ADR [0004](../decisiones/0004-enriquecimiento-opcional.md), contrato `Enricher` en
[`API.md`](../API.md) §3.

---

## 2. Código intestable

**v0:** el único test del repo (`tests/test_imports.py`) verificaba que el paquete
**importa**. No había cobertura de parsing, Cypher, métricas ni deduplicación. Era
consecuencia directa de tener Neo4j como sustrato: nada se podía probar sin servidor.

**Regla:** **el núcleo puro es la victoria de testabilidad.** El modelo de dominio, los
proyectores, los analizadores y los exportadores son funciones puras sin I/O, cubiertas por
tests unitarios con datos sintéticos.
→ ADR [0002](../decisiones/0002-modelo-agnostico-backend.md); Hitos 1–2 del
[`ROADMAP.md`](../ROADMAP.md).

---

## 3. Crashes latentes por *signature drift*

**v0:** la ingesta por directorio llamaba `process_directory(..., progress_callback=...)`
pero el método no aceptaba ese argumento (`TypeError` latente); el mismo problema en
enriquecimiento estaba **enmascarado por un `try/except TypeError`** que degradaba el
comportamiento en silencio.

**Regla:** **costuras con contratos estables y tipados.** Las interfaces (`Source`,
`Enricher`, `Store`, proyectores) se definen como Protocols/ABCs tipados; las llamadas
respetan la firma. Nada de `try/except` que oculte incompatibilidades de contrato.
→ [`API.md`](../API.md) (todas las costuras tipadas).

---

## 4. Drift de esquema entre docs y código

**v0:** un docstring de esquema (`analisis/agente_navegacion_grafo.py:7-37`) documentaba
`Institution.address` y una relación `Paper -[:CITED_BY]-> Paper` **inexistentes** en
`models.py`; otro punto pasaba `Paper(note=...)`, un campo que el modelo no tiene. Un agente
que confiara en esos docs generaba Cypher inválido.

**Regla:** **el modelo de dominio es la única fuente de verdad, documentada una vez.** El
`Corpus` y sus entidades se describen en un solo lugar ([`API.md`](../API.md) §1). No hay
docstrings paralelos que puedan divergir.
→ ADR [0002](../decisiones/0002-modelo-agnostico-backend.md).

---

## 5. Alcance muerto / publicidad falsa

**v0:** clientes de CrossRef (`Works()`) y Scopus (`ElsClient`) se **inicializaban pero
nunca se consultaban**; ramas de enriquecimiento de instituciones/keywords eran código
muerto; la entrada `csv`/`json` estaba listada como soportada pero lanzaba
`NotImplementedError`.

**Regla:** **solo se documenta y se construye lo que es real.** Las costuras futuras
(RIS/CSV, CrossRef/Scopus) se marcan **explícitamente como no implementadas**; no se cablean
clientes que no se usan ni se prometen formatos que no existen.
→ [`PRD.md`](../PRD.md) §5.2, [`API.md`](../API.md) (columnas de estado v1/futuro),
[`ROADMAP.md`](../ROADMAP.md) (costuras futuras).

---

## 6. Config dispersa con efectos de import

**v0:** tres definiciones separadas de `config.DATABASE_URL` y **dos contraseñas por defecto
distintas** (`"password"` en el paquete, `"12345678"` en los scripts de `analisis/`), cada
una seteada como **efecto de import** del módulo. El orden de imports importaba y los tests
aislados eran difíciles.

**Regla:** **configuración centralizada e inyectada; sin efectos de import.** Una sola fuente
de config, construida explícitamente y pasada a quien la necesita. Sin contraseñas por
defecto.
→ ADR [0003](../decisiones/0003-persistencia-opcional.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md) §6.

---

## 7. Dependencia no declarada / degradación silenciosa

**v0:** `python-louvain` (`import community`) se usaba para la detección de comunidades pero
**no figuraba en `pyproject.toml`**. Si faltaba, Louvain degradaba a modularidad voraz **en
silencio**, alterando resultados sin avisar.

**Regla:** **declarar lo que se importa; fallar fuerte, no en silencio.** Toda dependencia
usada está en `pyproject.toml` (núcleo o extra). Si falta una dependencia requerida, el error
es explícito y temprano, no una degradación oculta de resultados.
→ ADR [0005](../decisiones/0005-dependencias-extras.md), [`API.md`](../API.md) §6
(`detect_communities`).
