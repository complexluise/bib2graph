# Plantilla de release

> Copiá esto en el cuerpo del PR de release (lo abre `release-please`
> automáticamente; revisalo antes de mergear). Si la release la hacés a
> mano, completá las secciones que apliquen.

## Release

- **Versión anterior:** `vX.Y.Z`
- **Versión nueva:** `vA.B.C`
- **Tipo de bump:** `major` / `minor` / `patch`
- **Fecha de release:** YYYY-MM-DD
- **Rama de release:** `main`

## Resumen ejecutivo

<!-- Una o dos frases: qué trae esta release y por qué importa. -->

## Cambios incluidos

<!-- Lista los PRs mergeados desde la última release, agrupados por sección
     del CHANGELOG. `release-please` lo auto-genera desde los Conventional
     Commits; revisá que la agrupación sea coherente. -->

### Added

- (PR #N) feat(alcance): descripción corta.

### Changed

- (PR #N) refactor(alcance): descripción corta.

### Fixed

- (PR #N) fix(alcance): descripción corta.

### BREAKING CHANGES

<!-- Solo si hay. Pegá cada footer `BREAKING CHANGE:` de los commits y
     un fragmento de migración. -->

- **`función_x(arg_y)` → `función_x(arg_y, *, nuevo_arg=False)`**
  Migración: agregar `nuevo_arg=False` a las llamadas existentes.

## Compatibilidad

- **Python soportado:** 3.11, 3.12 (verificar en `pyproject.toml`).
- **Plataformas testeadas:** Linux, macOS, Windows.
- **Dependencias nuevas:** listar si las hay, con justificación.
- **Dependencias removidas:** listar si las hay, con migración.

## Checklist de release

- [ ] `CHANGELOG.md` actualizado y revisado.
- [ ] `pyproject.toml` con la versión nueva.
- [ ] `pre-commit run --all-files` limpio localmente.
- [ ] `pytest` + `mypy` + `ruff check` verde en CI.
- [ ] Tag `vA.B.C` creado al mergear.
- [ ] PyPI publish verificado (si aplica).
- [ ] GitHub Release publicado con notas.
- [ ] Documentación publicada (Read the Docs o equivalente).
- [ ] Anuncio en el canal que corresponda (opcional).

## Notas para el revisor

<!-- Cualquier cosa que el revisor deba mirar con cuidado: cambios de
     schema, ADRs nuevos que se aprobaron, decisiones de deuda técnica
     que se dejaron para después, etc. -->
