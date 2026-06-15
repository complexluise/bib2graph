# 0012 — Credenciales de OpenAlex: email del pool cortés + API key opcional, inyectados

- **Estado:** Aceptada
- **Fecha:** 2026-06-15
- **Decidido por:** IA (Claude Opus 4.8), validado por el Product Owner humano
  (ver [`registro-ia.md`](registro-ia.md))
- **Relacionada con:** [0007](0007-openalex-backbone.md) (OpenAlex backbone),
  [0010](0010-agente-native-columna.md) (config inyectada); lecciones 1 y 6 de v0
- **Observado en:** [`../../exploracion/scripts/01_search_openalex.py`](../../exploracion/scripts/01_search_openalex.py)

## Contexto

OpenAlex es el backbone de datos de la V1 (ADR 0007). Su política de acceso cambió: **desde
feb-2026 ofrece una API key**, leída por el script de exploración de `OPENALEX_API_KEY` o
`~/.openalex/credentials`. Dos hechos relevantes:

- **Sin key, la API sigue funcionando** en el *polite pool* (rate limit más bajo, más lento, no
  rompe). El email del pool cortés se sigue pasando para un rate limit sano.
- El ARCHITECTURE/PRD describen "sin clave obligatoria (pool cortés con email)". El cambio de
  política introduce una **credencial opcional** que conviene dejar explícita antes del Hito 4
  (`OpenAlexSource`), no descubrirla al implementar.

## Decisión

`OpenAlexSource` acepta **dos credenciales, ambas inyectadas** (config / CLI / entorno), **nunca
embebidas** como literal (lección 1):

- **`email`** (pool cortés): recomendado, no obligatorio. Sin él se cae al pool anónimo.
- **`api_key`** (desde feb-2026): **opcional**. Si está, se usa para mejor rate limit; si falta,
  el source corre en *polite pool* y **no rompe** (sin degradación silenciosa de resultados, solo
  de velocidad — se avisa, lección 7).

Orden de resolución (no-secreto con default explícito; secreto sin default): argumento explícito
→ entorno (`OPENALEX_API_KEY`, email de config) → ausencia ⇒ polite pool. **Ningún default
secreto en código**, ningún `os.environ.get("...", "literal")` para la key.

## Consecuencias

- **El primer flujo de 10 minutos sigue corriendo sin claves obligatorias** (criterio del PRD
  §9/§10): la key solo sube el rate limit.
- **Reproducibilidad consciente:** el `Manifest` registra si se usó key (no la key) y la
  fecha/versión de OpenAlex, no el secreto.
- **Costo:** hay que documentar la variable y el archivo de credenciales en el `--help` del CLI y
  en el README cuando llegue el Hito 4, y testear ambos caminos (con y sin key) contra API
  mockeada — sin red en CI.
- No cambia el núcleo puro: las credenciales viven en la costura `Source`, inyectadas.
