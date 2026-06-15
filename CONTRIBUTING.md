# Contribuir a bib2graph

> Gracias por querer contribuir. Este proyecto pone el **orden** por delante de
> la velocidad: cada cambio pasa por Conventional Commits, pre-commit, y un PR
> revisado. Es la única forma de mantener una librería testeable y reproducible.

## Setup local

```bash
git clone https://github.com/<org>/bib2graph.git
cd bib2graph
python -m venv .venv && source .venv/bin/activate   # o .venv\Scripts\activate en Windows
pip install -e ".[dev]"                              # extras de desarrollo
pre-commit install                                   # hooks de pre-commit
```

`pip install -e ".[dev]"` instala: dependencias del núcleo, todos los extras
de uso, `pytest`, `mypy`, `ruff` y las herramientas de release.

## Commits: Conventional Commits

Este proyecto usa [Conventional Commits](https://www.conventionalcommits.org/)
estricto. El formato:

```
<tipo>(<alcance opcional>): <descripción corta en imperativo, español, sin punto final>

<cuerpo opcional: por qué, no qué>

<footer opcional: BREAKING CHANGE: ... o referencia a issue>
```

**Tipos permitidos** (los mapea `release-please` a secciones del CHANGELOG):

| Tipo | Sección del CHANGELOG | Ejemplo |
|------|----------------------|---------|
| `feat` | Added | `feat(networks): añadir NetworkSpec con loader YAML` |
| `fix` | Fixed | `fix(bibtex): defensa ante campos faltantes en BibtexSource` |
| `refactor` | Changed | `refactor(corpus): extraer validación a schemas.py` |
| `perf` | Changed | `perf(projector): usar groupby en vez de doble loop` |
| `docs` | (no release) | `docs(arch): aclarar tensiones resueltas en ADR 0006` |
| `test` | (no release) | `test(corpus): añadir tests de merge idempotente` |
| `chore` | (no release) | `chore(deps): bump pydantic a 2.6` |
| `build` | (no release) | `build(ci): añadir ruff a GitHub Actions` |
| `ci` | (no release) | `ci: cachear pip en Actions` |
| `style` | (no release) | `style: aplicar ruff format` |

**Alcance sugerido** (los paquetes del núcleo): `corpus`, `sources`,
`enrichers`, `preprocessors`, `networks`, `exporters`, `stores`, `cli`, `arch`,
`docs`, `release`.

**Breaking changes:** en el footer, en una línea propia:

```
feat(networks): cambiar firma de Networks.build

BREAKING CHANGE: Networks.build ahora devuelve NetworkArtifact (grafo + métricas + clusters)
en vez de solo el grafo. Migrar callers existentes.
```

Esto fuerza un bump **MAJOR** (o MINOR si estamos en `0.y`) y una entrada
`BREAKING:` en el CHANGELOG. Más en [`VERSIONING.md`](./VERSIONING.md).

### Herramienta: commitizen

Para evitar memorizar el formato, usá `cz commit`:

```bash
cz commit          # interactivo, te pregunta tipo/alcance/descripción
cz bump --dry-run  # ver qué versión resultaría de los commits acumulados
```

## Estilo de código

Todo en [`AGENTS.md`](./AGENTS.md) §Convenciones. Resumen ejecutivo:

- **PEP 8 + `ruff format`** (ancho 88). El formatter decide; no se discute.
- **Tipado estático** en todas las firmas públicas (`mypy` en CI).
- **Docstrings en español** (una línea para triviales, `Args/Returns/Raises`
  para el resto).
- **Sin comentarios innecesarios.** Los docstrings justifican el *por qué*.
- **No hay efectos de import.** Importar un módulo nunca toca config, red,
  disco ni estado global.
- **Fallar fuerte, no en silencio** (lección 7 de v0). Si falta una dependencia
  requerida, error explícito y temprano.
- **Acceso defensivo a campos de entrada** con `.get()` (lección de v0 con
  `research-areas`).

## Tests

- **Núcleo sin red ni servidores.** Tests unitarios con datos sintéticos.
- **Costuras con I/O con mocks.** `responses` o `httpx.MockTransport` para
  APIs externas. **Sin red en CI.**
- **Neo4j / DuckDB efímeros** (Testcontainers o in-process) o mocks del
  driver, marcados como `@pytest.mark.integration`.
- Cada test corre en aislamiento. No fixtures compartidas con estado mutable.

```bash
pytest                          # toda la suite
pytest -m unit                  # solo unitarios
pytest -m integration           # solo integración
pytest tests/test_corpus.py::TestCorpus::test_merge_idempotent -xvs   # un test puntual
```

## Estructura de un PR

- **Título:** conventional commit resumido (idealmente el commit de merge es
  `feat: ...` y el PR title coincide).
- **Descripción:** qué, por qué, cómo se probó. Si cambia la API pública,
  link al ADR o PR de discusión.
- **Tamaño:** chico. Un PR = una idea. Mezclar refactor + feature es válido
  si es la única forma de hacer el feature, pero decirlo explícito.
- **Checklist:** `ruff check` + `mypy` + `pytest` corriendo limpio. CI lo
  valida igual; el checklist es cortesía para el revisor.

## Antes de mergear

1. CI verde (lint, types, tests, build).
2. Al menos una aprobación.
3. Si cambia un contrato público (`docs/API.md`), ADR nuevo en
   `docs/decisiones/` aprobado **antes** de mergear el código.
4. Si toca el método bibliométrico, actualizar `docs/metodología.md` en el
   mismo PR.

## Releases

Las releases las maneja `release-please` desde los Conventional Commits
mergeados a `main`. El PR de release se revisa (CHANGELOG.md + bump de
versión) y al mergearlo se taggea y publica. Detalle en
[`VERSIONING.md`](./VERSIONING.md).
