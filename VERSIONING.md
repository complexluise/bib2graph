# Versionado — SemVer estricto

> `bib2graph` adopta [Semantic Versioning 2.0.0](https://semver.org/lang/es/)
> estricto. Este doc explica cómo se aplica y cómo se automatiza el proceso.

## La regla

Dado un versionado `MAJOR.MINOR.PATCH` (ej. `0.3.2`):

- **MAJOR** se incrementa cuando hay **cambios incompatibles** en la API
  pública (lo declarado en `docs/API.md`).
- **MINOR** se incrementa cuando hay **funcionalidad nueva compatible hacia
  atrás**.
- **PATCH** se incrementa cuando hay **bugfixes compatibles hacia atrás**.

## Mientras estemos en `0.y.z`

Mientras la versión mayor sea `0` (es decir, hasta que se publique `1.0.0`),
la API se considera **inestable**: cualquier cambio `MINOR` puede traer
cambios incompatibles. La regla durante `0.y` es:

- `0.MINOR.PATCH` → `0.(MINOR+1).0` cuando hay **cualquier cambio visible al
  usuario** (feature, refactor que toca la API, o breaking change).
- `0.y.PATCH` → `0.y.(PATCH+1)` solo para bugfixes internos que no cambian
  la API.

Una entrada `BREAKING:` en el CHANGELOG corresponde a un bump de MINOR (no
de MAJOR) mientras estemos en `0.y`. Al llegar a `1.0.0`, los breaking
cambies sí bumpan MAJOR.

## Congelar la API: `1.0.0`

`1.0.0` se publica cuando:

- La API pública de `docs/API.md` se considera estable y revisada.
- Hay cobertura de tests razonable sobre el núcleo y las costuras por
  defecto (BibtexSource, InMemoryStore/ParquetStore, los 4 proyectores).
- Hay al menos un caso real validado (estudio de semiconductores
  reproducido con la lib).
- Hay documentación de usuario completa (README + ejemplo end-to-end).

Hasta entonces, los breaking changes están permitidos y son **bienvenidos
si simplifican el diseño**, mientras estén justificados en un ADR y
documentados con `BREAKING:` en el commit.

## ¿Qué cuenta como "API pública"?

Lo declarado en `docs/API.md`:

- Clases, funciones y dataclasses exportadas desde `bib2graph` y sus
  submódulos.
- Los formatos de archivos de I/O: schema de la tabla Arrow, schema del
  `manifest.json`, formatos de export (GraphML, CSV).
- Los nombres de subcomandos del CLI y la forma del JSON de `--json`.
- Los nombres de extras de instalación (`[s2]`, `[neo4j]`, `[duckdb]`,
  `[dedup]`, `[viz]`).

Lo que **no** cuenta: funciones y clases privadas (prefijo `_`), módulos
internos, mensajes de error exactos, orden de columnas en exportaciones
CSV no documentado.

## Automatización

Las releases las maneja [`release-please`](https://github.com/googleapis/release-please):

1. Vos mergeás PRs a `main` con Conventional Commits bien escritos.
2. `release-please` abre un PR de release con:
   - `CHANGELOG.md` actualizado (sección nueva con Added/Changed/Fixed/...).
   - Bump de versión en `pyproject.toml`.
3. Revisás el PR de release. Si está bien, lo mergeás.
4. Al mergear, se taggea `vX.Y.Z` y se publica a PyPI (configurar en CI).

`cz bump --dry-run` te muestra, localmente, qué versión resultaría de los
commits acumulados sin necesidad de pushear.

## Versionado de snapshots y schemas

Independiente de la versión de la lib, cada `CorpusSnapshot` lleva su
`schema_version` en `manifest.json`. Si cambia el schema de la tabla
(agregar o renombrar columnas), bump de `schema_version` (formato propio:
`"0.1.0"`, `"0.2.0"`, etc.). La lib abre snapshots con `schema_version`
anterior con migración explícita; si la migración es imposible, falla
ruidoso con un mensaje claro.

## Ejemplos

| Cambio | Bump | Entrada CHANGELOG |
|--------|------|-------------------|
| `feat(networks): añadir NetworkSpec con loader YAML` (estando en `0.2.3`) | `0.3.0` | Added |
| `fix(bibtex): defensa ante campos faltantes` (estando en `0.2.3`) | `0.2.4` | Fixed |
| `refactor(corpus): cambiar firma de `Corpus.merge`` con `BREAKING CHANGE:` (estando en `0.2.3`) | `0.3.0` | BREAKING (sección Changed, con header) |
| `feat(cli): añadir subcomando `b2g inspect`` (estando en `1.2.3`) | `1.3.0` | Added |
| `fix(cli): exit code incorrecto en `b2g build --json`` (estando en `1.2.3`) | `1.2.4` | Fixed |
| Cualquier cambio en `0.y` que no sea bugfix | bump de MINOR | según tipo |
