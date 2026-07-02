# 30 — Paper citable con DOI (JOSS) + soporte first-class en español

> **Género:** nota de dirección (nota primero; no es ADR ni doc canónico).
> **Origen:** charla PO ↔ agente: "quiero hacer un paper de bib2graph, con DOI, que se pueda
> citar en investigación" → ¿el paper debe ir en inglés? → si sí, ¿cómo dar soporte first-class
> a hispanohablantes sin sacrificar eso?
> **Para qué:** fijar el camino (JOSS + Zenodo) y dejar registrado, sin ejecutar todavía, qué le
> falta al repo para cumplir el checklist de revisión de JOSS.
> **Relacionadas:** `25-multiproveedor-requerimientos.md` (misión hispana), `28-marco-software-donde-nos-paramos.md`
> (insumo natural para el "Statement of Need" del paper), `docs-espanol-neutro-tuteo` (memoria:
> docs del sitio siempre en español neutro tuteando).

---

## Decisión de rumbo

- **Vía elegida: JOSS** (Journal of Open Source Software). Gratis, revisión pública en GitHub,
  semanas no meses, da DOI vía Crossref al aceptar. Requiere `paper.md` corto (resumen +
  statement of need) + `paper.bib`, apoyado en la documentación existente — no un paper largo
  desde cero.
- **Idioma:** el `paper.md` de JOSS **debe ir en inglés** (idioma de revisión editorial e
  indexación en Crossref). Eso **no** obliga a traducir el sitio: la documentación (mkdocs) sigue
  en **español neutro** como hoy — ese es el soporte first-class a hispanohablantes. El paper es
  un artefacto aparte y corto que enlaza a esa documentación.
- Único punto de fricción real: los revisores de JOSS instalan y prueban el software siguiendo
  las instrucciones del README — conviene que el *quickstart* mínimo tenga versión en inglés (o
  README bilingüe) para que puedan seguirlo sin traducir, aunque el resto del sitio quede en
  español.

---

## Checklist de JOSS — estado as-built (auditado 2026-07-01)

| Requisito JOSS | Estado | Evidencia / gap |
|---|---|---|
| Licencia OSI-approved | ✅ | `LICENSE` = GPL-3.0-or-later, declarada en `pyproject.toml` |
| Repositorio público con control de versiones | ✅ | GitHub, 259 commits |
| Tests automatizados | ✅ | 66 archivos `test_*.py`, gate corre `pytest` |
| Instrucciones de instalación | ✅ | README §Instalación |
| Ejemplo de uso | ✅ | README §Quickstart |
| Documentación de API | ✅ | `docs/reference/python-api.md` |
| Guías de comunidad (contribuir/soporte/reportar) | ⚠️ parcial | `CONTRIBUTING.md` cubre setup/commits/tests/releases; falta sección explícita de "cómo pedir soporte" / "cómo reportar un bug" orientada a usuarxs externxs (hoy es más para contribuir código) |
| **Statement of Need** explícito | ⚠️ falta | README tiene "Qué hace" pero no un statement of need al estilo JOSS (a quién sirve, qué problema resuelve, comparación con alternativas). La Nota 28 (§3 "Prior art y huecos") ya tiene el material — falta destilarlo a inglés y forma de paper |
| Autoría nombrada con afiliación/ORCID | ❌ falta | `pyproject.toml` solo dice `"Equipo bib2graph"`; JOSS pide personas reales con afiliación (ORCID opcional pero recomendado) |
| Política de autoría IA | ⚠️ a decidir | `git log` tiene commits co-autorados por "Claude"; JOSS exige autores humanos — hay que decidir cómo se declara el uso de IA (acknowledgment, no autoría) antes de listar autores en el paper |
| `paper.md` + `paper.bib` | ❌ falta | no existen todavía |
| Archivo permanente con DOI (Zenodo / Software Heritage) | ❌ falta | no hay `.zenodo.json` ni integración GitHub↔Zenodo; JOSS exige un archivo depositado que matchee versión/título/autores antes de aceptar |
| `CITATION.cff` | ❌ falta | no existe; no es requisito duro de JOSS pero GitHub lo usa para "Cite this repository" y ayuda a la citabilidad general |
| Alcance ("substantial scholarly effort", no utilidad menor) | ✅ probable | 259 commits, arquitectura documentada en profundidad (Notas 20–29, ADRs); único matiz: el repo tiene ~2 semanas de historia calendario (2026-06-15 → 2026-06-30) — no es un requisito de JOSS pero puede salir en la revisión editorial |

---

## Lo que falta hacer (no ejecutado — solo mapa)

1. Decidir autoría real para el paper: nombres, afiliación, ORCID de quién corresponda; decidir
   cómo declarar la contribución de IA (agradecimiento, no autoría).
2. Escribir sección explícita de soporte/reporte de bugs en `CONTRIBUTING.md` (o README) para
   usuarxs, no solo contribuidores de código.
3. Destilar la Nota 28 (§3 prior art, §4 frases-ancla) a un **Statement of Need** en inglés,
   corto y defendible.
4. Redactar `paper.md` (summary + statement of need + referencias) y `paper.bib`.
5. Agregar `CITATION.cff`.
6. Conectar el repo a Zenodo (GitHub integration) y archivar el release que se someta a JOSS,
   con versión/título/autores idénticos al paper.

Nota primero — esto es el mapa del checklist, no la ejecución. Próximo paso natural: decidir
autoría (punto 1) antes de tocar nada más, porque condiciona el resto.

---

## Actualización (2026-07-01): esto es de mediano plazo, no ahora

Dos cambios de rumbo que aplazan todo lo de arriba:

- **Licencia:** GPL-3.0 no sirve si la idea es que una empresa pueda usar bib2graph sin
  obligación de copyleft. Cambiar a **algo tipo Apache-2.0** (o MIT) — sigue siendo open source
  (OSI-approved, no rompe el requisito de JOSS), pero permite uso comercial sin las restricciones
  de la GPL. Pendiente: auditar si hay dependencias GPL que impidan el cambio de licencia antes
  de ejecutarlo.
- **Timing:** el paper (JOSS) y el archivo con DOI **no tienen sentido todavía**. Hoy bib2graph
  "abarca varias cosas" — falta que decante a una versión más estable y más **Unix** (que
  resuelva bien **un** problema, filo con `frontera-bib2graph-vs-producto`) antes de intentar
  publicarlo como paper citable. Publicar ahora sería citar una superficie que todavía se está
  recortando.

**Conclusión:** esta nota queda como mapa de mediano plazo. No es el próximo paso de esta
semana ni del próximo hito — se retoma cuando (a) el alcance esté recortado a algo más Unix y
(b) la licencia ya sea permisiva.
