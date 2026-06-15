# Registro de decisiones tomadas por la IA

> Bitácora de las decisiones que **tomó la IA** (Claude) de forma autónoma mientras avanza el
> ROADMAP hacia la v1.0, por pedido del Product Owner humano. Complementa el
> [registro de ADRs](README.md): las decisiones **arquitectónicas** van a un ADR numerado (con
> la línea `Decidido por: IA`); las decisiones **de implementación / proceso** más chicas se
> anotan acá.
>
> Convención: cada decisión registra **fecha**, **qué se decidió**, **por qué**, su
> **reversibilidad** y si fue **validada por el humano**. Si una decisión de la IA resulta
> equivocada, se corrige con una entrada nueva (no se reescribe la historia).

## Cómo se marca la autoría de la IA

- **ADRs:** campo `- **Decidido por:** IA (Claude ...)` en el encabezado.
- **Commits:** los hace la IA; el trailer `Co-Authored-By: Claude` ya lo refleja.
- **Decisiones de proceso/implementación:** una entrada en este archivo.

---

## 2026-06-15 — Sprint 0 (preparación / andamiaje)

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 0.1 | **`httpx` como cliente OpenAlex** (en vez de `pyalex` u otro SDK) | Testeable con `httpx.MockTransport` sin red en CI; control fino de la query y del reporte de traducción (ADR 0007) | Media: cambiar de cliente afecta solo la costura `OpenAlexSource` | Pendiente (asumida) |
| 0.2 | **`python-louvain` en el núcleo**, no en un extra | Louvain es la detección de comunidades por defecto (API.md §8); declararlo evita el bug de v0 (lección 7) | Alta: mover a extra `[community]` es trivial | Pendiente (asumida) |
| 0.3 | **`dev` en `[tool.uv] dev-dependencies`**, no como extra publicable | uv 0.4.16 no estabiliza PEP 735; así las dev-deps no se publican a PyPI | Alta | Sí (uv-native pedido por el humano) |
| 0.4 | **Pin de Python 3.12** en `.python-version` (`requires-python >=3.11`) | 3.12 estable y disponible local; deja 3.11 como piso de compatibilidad | Alta | Pendiente (asumida) |
| 0.5 | **Smoke tests mínimos del Hito 0** (import sin efectos + placeholder CLI), no más | Disciplina TDD selectiva del ROADMAP: testear solo lo que tiene contrato/riesgo | Alta | Sí (criterio del ROADMAP) |
| 0.6 | **ADR 0012** (credenciales OpenAlex: email + key opcional inyectados) | Cerrar el detalle de la key obligatoria-desde-feb-2026 antes del Hito 4 | N/A (registro) | Sí (el humano pidió el ADR) |
| 0.7 | **Commits a `main`** (sin feature branches ni GitHub por ahora) | El repo es solo-local sin remoto; la historia previa ya commitea docs a `main` | Alta | Sí (humano: "no GitHub por el momento") |

> **Decisiones del Product Owner humano** (no de la IA, registradas para contexto): adoptar uv;
> alcance de v0.1 = Hitos 1–4; objetivo v1.0 vía `/feature-cycle`; sin GitHub por ahora.

---

## 2026-06-15 — Hito 1 (Corpus: núcleo de la tabla canónica)

> Las decisiones **arquitectónicas** de este hito (D1 `id` estable, D2 `corpus_hash`
> order-independent, D3 reglas de `merge`, D4 `provenance` como log append-only, y la igualdad de
> `Corpus` vía `corpus_hash`) van en el ADR
> [0013](0013-identidad-hash-merge-corpus.md), no como filas acá. Lo de abajo son las decisiones
> **de implementación / proceso** del hito.

| # | Decisión | Por qué | Reversibilidad | Validada por humano |
|---|----------|---------|----------------|---------------------|
| 1.1 | **Manifest D5: campos obligatorios sin default vs opcionales con default** (`schema_version`, `corpus_hash`, `lib_version`, `created_at` obligatorios; `equations=[]`, `chaining=None`, `preprocessors=[]`, `filters=[]`, `enrichers=[]`, `openalex_version=None`). El `Corpus` en memoria lleva `corpus_hash=""` y el hash real se sella en `snapshot()`/`CorpusSnapshot` | Un Manifest se puede construir desde un `Corpus` recién sembrado sin conocer aún el contenido completo; obligar todo rompería la semántica de valor. El hash es derivable del contenido, no un dato de entrada | Alta: agregar/quitar defaults no rompe el parquet ni el contrato público (round-trip JSON) | Sí (PO proxy) |
| 1.2 | **`schema_version` D6: solo se escribe y round-tripea en Hito 1** (sin lógica de rechazo por incompatibilidad) | No hay todavía migraciones ni un store vivo donde versiones distintas convivan; agregar rechazo ahora sería especular. Se difiere al hito con migraciones sobre DuckDB (ADR 0009) | Alta: agregar la lógica de compatibilidad es aditivo | Sí (PO proxy) |
| 1.3 | **Fix de determinismo: `Corpus.__eq__` canónico vía `corpus_hash` + orden de `merge` por primera aparición** (antes `__eq__` usaba `pa.Table.equals`, sensible al orden) | `pa.Table.equals` daba falsos negativos ante el mismo contenido en distinto orden de filas/listas y era frágil ante `PYTHONHASHSEED` (21 tests bajo 12 seeds). La igualdad por `corpus_hash` es consistente con D2; `merge` emite un orden determinista para snapshots diffeables | Media: cambia la semántica observable de `==` y del orden de filas; revertir exigiría re-tocar tests. Consistente con el ADR 0013 | Sí (PO proxy; verifier PASA) |

> Las decisiones D1–D4 (arquitectónicas) están en el ADR
> [0013](0013-identidad-hash-merge-corpus.md). El símbolo público `SchemaError` se exporta desde
> `__init__.py` (ver `API.md` §1).
