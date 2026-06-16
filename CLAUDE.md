# CLAUDE.md

Guía para agentes (Claude Code y otros). La **fuente canónica** —estado del proyecto,
comandos, convenciones de código, estructura de paquetes, tests— es **[`AGENTS.md`](AGENTS.md)**:
leéla antes de tocar nada. Este archivo solo fija lo mínimo imprescindible para no duplicar
(evitar drift); el detalle vive en `AGENTS.md` y `CONTRIBUTING.md`.

## Flujo de trabajo básico (NO te lo saltes)

Modelo **GitFlow-lite** — detalle en [`AGENTS.md`](AGENTS.md) §Flujo de trabajo y
[`CONTRIBUTING.md`](CONTRIBUTING.md):

- **`dev`** = rama de integración y default del repo (acá se acumula el trabajo).
  **`main`** = estable/release. **Ambas protegidas**: PR + CI verde obligatorios, nunca pushear directo.
- **Un cambio:** ramear desde `dev` → commits Conventional Commits → `gh pr create --base dev`
  → CI verde → `gh pr merge --squash`.
- **Liberar** (cuando hay varias cosas en `dev`): PR `dev → main` con **merge commit** →
  `release-please` abre el PR de release → mergearlo crea tag + GitHub Release. **No** bumpees
  versión ni edites `CHANGELOG.md` a mano.
- **Dos tipos de PR:** el de trabajo (manual, a `dev`) y el de release (lo crea release-please solo).

## Reglas que no se negocian

- **uv** para todo (`uv sync`, `uv run …`); no `pip`, no editar `[project.dependencies]` a mano.
- **Conventional Commits** estricto. Un PR = una idea, con sus tests.
- Gate antes de PR: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`.
- **Leer `docs/ROADMAP/` antes de empezar un hito** (historias del PRD §7, DoD, tests TDD).
- Cambios a contratos públicos (`docs/API.md`) → ADR nuevo en `docs/decisiones/` antes de mergear.
