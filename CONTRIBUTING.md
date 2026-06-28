# Contribuir a bib2graph

> Gracias por querer contribuir. Este proyecto pone el **orden** por delante de
> la velocidad: cada cambio pasa por Conventional Commits, pre-commit, y un PR
> revisado. Es la única forma de mantener una librería testeable y reproducible.

## Setup local

El proyecto se gestiona con [**uv**](https://docs.astral.sh/uv/). uv crea el
entorno, fija la versión de Python (`.python-version` → 3.12) y resuelve las
dependencias contra el lockfile (`uv.lock`).

```bash
git clone https://github.com/complexluise/bib2graph.git
cd bib2graph
git checkout dev            # se trabaja sobre dev (rama de integración)
uv sync                     # crea .venv, instala núcleo + dev-dependencies desde uv.lock
uv run pre-commit install   # hooks de pre-commit
```

`uv sync` instala el núcleo (incluye DuckDB y el cliente OpenAlex) y las
`dev-dependencies` (`pytest`, `mypy`, `ruff`, `commitizen`, `pre-commit`). Para
una capacidad opcional, agregá su extra: `uv sync --extra dedup` (ídem `zotero`,
`s2`, `neo4j`, `viz`, `bibtex`). Para excluir las dev-deps: `uv sync --no-dev`.
*(El extra `[llm]` se eliminó: el producto no usa IA generativa — ADR 0022.)*

Comandos del día a día (siempre con `uv run`, sin activar el venv a mano), tal
como los corre el CI (`.github/workflows/ci.yml`):

```bash
uv run ruff check .              # lint (exploracion/ excluido)
uv run ruff format --check .     # formato (verificación)
uv run mypy src                  # tipos (strict)
uv run pytest                    # tests
```

Para tocar dependencias, usá uv (NO edites `[project.dependencies]` a mano):
`uv add <paquete>` (núcleo), `uv add --dev <paquete>` (desarrollo),
`uv add --optional <extra> <paquete>` (capacidad opcional). uv actualiza
`pyproject.toml` y `uv.lock` juntos.

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

**Alcance sugerido** (los paquetes del núcleo): `corpus`, `sources`, `foraging`,
`preprocessors`, `filters`, `enrichers`, `networks`, `exporters`, `stores`,
`cli`, `arch`, `docs`, `release`.

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
uv run cz commit          # interactivo, te pregunta tipo/alcance/descripción
uv run cz bump --dry-run  # ver qué versión resultaría de los commits acumulados
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
uv run pytest                          # toda la suite
uv run pytest -m unit                  # solo unitarios
uv run pytest -m integration           # solo integración
uv run pytest tests/unit/test_corpus.py -xvs   # un archivo puntual
```

## Modelo de ramas y flujo (importante)

El proyecto usa un modelo **GitFlow-lite** con dos ramas de larga vida:

- **`dev`** — rama de **integración** y **default del repo**. Acá se **acumula** el
  trabajo. Protegida: no se pushea directo, todo entra por PR con CI verde.
- **`main`** — rama **estable / de release**. Protegida (estricta). **Solo** recibe
  `dev` cuando se libera, y el PR de release. No se trabaja directo sobre `main`.

Flujo de un cambio:

```
1. ramear desde dev        git checkout dev && git pull && git checkout -b feat/lo-que-sea
2. commitear               Conventional Commits (ver arriba)
3. push + abrir PR a dev   gh pr create --base dev               ← TU PR (manual)
4. CI corre solo           lint + test (3.11/3.12)               ← automático
5. merge a dev             gh pr merge --squash                  ← 1 commit limpio por idea
```

**Hay dos tipos de PR — no confundirlos:**

1. **Tu PR de trabajo** (`feat/...` → `dev`): lo creás vos a mano. Es donde ocurre
   la revisión y el CI hace de gate. Mergealo con **squash** (un commit conventional
   por idea).
2. **El PR de release** (`chore(main): release X.Y.Z`): lo crea **automáticamente
   `release-please`** cuando hay commits liberables en `main`. No lo creás vos; se
   queda esperando hasta que lo mergees (ver §Releases).

**Liberar una versión** (cuando hay varias cosas acumuladas en `dev`, no por cada
cambio):

```
1. PR dev → main           gh pr create --base main --head dev
2. merge con MERGE COMMIT   (NO squash: release-please necesita ver los feat/fix)
3. release-please abre el PR de release en main (CHANGELOG + bump)
4. mergeás ese PR          → tag vX.Y.Z + GitHub Release
```

> **Caveat:** el PR de release **no dispara CI** (los commits del `GITHUB_TOKEN` no
> disparan workflows). Hasta que exista el secret `RELEASE_PLEASE_TOKEN` (un PAT), se
> mergea con **bypass de admin** ("merge without waiting for requirements"). Ver
> [`VERSIONING.md`](./VERSIONING.md).

## Estructura de un PR

- **Título:** conventional commit resumido (idealmente el commit de merge es
  `feat: ...` y el PR title coincide).
- **Descripción:** qué, por qué, cómo se probó. Si cambia la API pública,
  link al ADR o PR de discusión.
- **Tamaño:** chico. Un PR = una idea. Mezclar refactor + feature es válido
  si es la única forma de hacer el feature, pero decirlo explícito.
- **Checklist:** `ruff check` + `mypy` + `pytest` corriendo limpio. CI lo
  valida igual; el checklist es cortesía para el revisor.
- **¿Si el PR cambia un ADR firmado, reescribiste los docs vivos para reflejarlo?**
  (`docs/ARCHITECTURE.md`/`API.md`/`PRD.md` describen el **presente**: si la decisión cambió, el doc
  vivo se reescribe al nuevo presente y el debate queda en el ADR — ver AGENTS.md §Documentación viva).

## Antes de mergear

1. **CI verde** (lint, types, tests) — lo exige la protección de rama; es el gate.
2. **Aprobación:** la protección pide **0 aprobaciones** (proyecto de un solo
   dev: no podés aprobar tu propio PR). Cuando entren colaboradores, se sube el
   mínimo a 1 — ahí la regla "al menos una aprobación" aplica.
3. Si cambia un contrato público (`docs/API.md`), ADR nuevo en
   `docs/decisiones/` aprobado **antes** de mergear el código.
4. Si toca el método bibliométrico, actualizar `docs/Notas/metodología.md` en el
   mismo PR.

> **Protección de rama:** `main` es **estricta** (la rama del PR debe estar
> actualizada con `main` antes de mergear → si `main` avanzó, `git merge
> origin/main` + push y el CI re-corre). `dev` es no-estricta (menos fricción).
> En ambas: PR obligatorio + CI verde. El owner puede hacer bypass de admin como
> válvula de escape (`enforce_admins: false`).

## Releases

Las releases las maneja **`release-please`** desde los Conventional Commits que
llegan a **`main`** (vía el merge `dev → main`). Cuando hay commits liberables,
abre/actualiza **solo** el PR `chore(main): release X.Y.Z` con el `CHANGELOG.md`
y el bump de versión ya hechos; al mergearlo se crea el tag `vX.Y.Z` y el GitHub
Release. No publica a PyPI (por ahora, solo GitHub Releases). Versionado pre-1.0:
`feat`→minor, `fix`→patch, breaking→minor. Detalle y el rol del PAT
`RELEASE_PLEASE_TOKEN` en [`VERSIONING.md`](./VERSIONING.md).
