# Nota 33 — Arco a v1.0: comprender el pasado para leer las ligaduras del futuro

> **Estado:** BORRADOR de trabajo. Síntesis para revisar en frío otro día.
> No decide nada todavía: no crea milestones ni ADR. Sesión de encuadre 2026-07-18.
> Género: igual que la Nota 29 (backlog/plan). Cuando cuaje → milestones (roadmap = trabajo)
> + ADR del arco (gate = decisión, va al repo por PR).

## Por qué esta nota

Tenemos superficie estable (10 verbos agent-native, workspace canónico, motor determinista
sin IA). Es momento de mirar **más allá de 0.13.0** y encaminarnos a **v1.0** (~10 iteraciones).
El principio de la sesión: *comprender el pasado para comprender las ligaduras del futuro* —
no sumar features al azar, sino ver qué nos obliga lo ya decidido.

## Dónde estamos (el pasado, comprimido)

- **12 releases** (0.1 → 0.12). **Todos los hitos funcionales del PRD (0–9) están construidos**:
  núcleo puro, forrajeo con *scent* bibliométrico, CLI agent-native de 10 verbos, workspace
  canónico, curación CSV, gate de reproducibilidad en CI.
- **48 ADRs** (40 aceptados, 5 en estado *Propuesta*: 0032, 0033, 0034, 0045, 0046).
- **0.13.0 en vuelo** (milestone, 10 issues): **cimientos multi-proveedor** — Semantic Scholar,
  DOAJ, `external_ids`, e identidad de papers **sin DOI**. Varios `decisions-needed`
  (#254 política sin-DOI, #253 precedencia de merge, #251 selector `--source`).

## El gate de v1.0

Criterio heredado del ROADMAP (`docs/ROADMAP/README.md`, ~línea 141):

> **API congelada + un caso real reproducido por alguien distinto del autor + publicación en PyPI.**

**Decisión de la sesión (2026-07-18): MANTENER los 3 criterios + AGREGAR un "algo más" por
definir.** Candidatos para ese "+": docs de estado del arte completas, o la migración a la org
`sostaina` consumada, o algo que aparezca al revisar. → **PENDIENTE de definir con el PO.**

Lo importante: a v1.0 **no le falta funcionalidad, le falta cerrar contratos y validar afuera.**

## Las ligaduras (lo que el pasado obliga a respetar rumbo a 1.0)

1. **Determinismo sin IA es sagrado** (ADR 0022 / 0047). Nada en el arco mete IA en el motor;
   la IA vive en Atalaya (producto separado).
2. **Identidad DOI-first, agnóstica al proveedor** (ADR 0036). Todo lo multi-proveedor cuelga
   de acá; *papers sin DOI* es el hueco abierto (#254).
3. **Superficie = el ciclo, no acumulación** (ADR 0037 / 0038). Congelar la API = **cerrar la
   superficie**, no seguir sumando verbos.
4. **Envelope agent-native versionado** (ADR 0021 / 0043). Congelar = cerrar las **3 grietas**
   del ADR 0045 (`error.subcode`, `data.workspace`, `schema meta`).
5. **Blocker operativo**: migración a `sostaina` + **PyPI trusted-publishing** (hoy solo hay
   GitHub Releases). Ver memoria `migracion-owner-sostaina`.
6. **Deuda de ADRs en estado *Propuesta*** que tocan contratos (0032 service layer, 0034 tags,
   0045, 0046). Congelar la API **fuerza a resolverlos o deprecarlos** antes de 1.0.

## Arco propuesto a v1.0 (~9 iteraciones — BORRADOR)

Hay **dos tramos con naturaleza distinta** (matiz del PO, 2026-07-18):

**Tramo A — derivado del pasado y las ligaduras (firme-ish).** Sale de decisiones ya
tomadas y de la deuda que el pasado obliga a cerrar. Se puede planificar como ingeniería.

| Versión | Tema | De dónde sale |
|---|---|---|
| **0.13.0** *(en curso)* | Cimientos multi-proveedor: identidad + S2 + DOAJ | milestone actual |
| **0.14.0** ← *decidido como próxima* | **Completar multi-proveedor**: precedencia de merge (#253), `external_ids` cross-motor (#255/#120), política sin-DOI (#254) | decisions-needed 0.13 |
| **0.15.0** | Cerrar contratos del Tramo A: D2 del 0050 (`source_kind` + migración on-read de `chaining:*`) + implementación del 0052 (red tipada en el Arrow del corpus) + errores de Click en `--json` como envelope (#283, enmienda al 0021). [Las 3 grietas del ADR 0045 se cerraron en 0.12.0 con #258/#259/#260; la fila original acá estaba desactualizada — sincronizada 2026-10-11.] | ADR 0050 §D2, [0052](https://github.com/complexluise/bib2graph/blob/main/docs/decisiones/0052-red-tipada-en-arrow-corpus.md), [#283](https://github.com/complexluise/bib2graph/issues/283) |

**Tramo B — zona de ESTABILIZACIÓN, alimentada por validación de usuarios (PROVISIONAL).**
De 0.16 en adelante los temas son "para estabilizar" y **NO están cerrados**: van a recibir
tareas de **experiencia de usuario que todavía no conocemos**, que emergen de validar con
muchos usuarios. **El PO (Luis) corre esa validación.** Estos temas son placeholders razonables,
no un plan de ingeniería fijo — el lazo RETROALIMENTAR (`/cosechar-sesion` → issues/Discussions)
los va a reordenar y expandir.

| Versión | Tema *(placeholder, se conforma con feedback)* | De dónde sale |
|---|---|---|
| **0.16.0** | Rendimiento honesto: acoplamiento O(n²)→sparse, rate-limit honesto, GraphML rico | #206 (repo gemelo BibGraph) |
| **0.17.0** | Import multi-formato (RIS/EndNote/CSV) *si entra en scope de 1.0* | ADR 0035 fase 2 |
| **0.18.0** | Infra de release: migración a `sostaina` + PyPI trusted-publishing | memoria + gate 1.0 |
| **0.19.0** | Ensayo de reproducción externa (un tercero corre el ciclo con archivos congelados; recoger fricciones) | criterio v1.0 |
| **0.20.0 / RC** | Auditoría de congelación de API (resolver/deprecar ADRs *Propuesta*, sellar superficie) | ligadura 3 y 6 |
| **1.0.0** | API congelada + reproducción externa validada + PyPI | gate |

> **La cola no se planifica desde el escritorio, se descubre con usuarios.** La validación de
> UX con muchos usuarios (a cargo del PO) va a inyectar tareas al Tramo B que hoy no están en
> la tabla. El número de versiones y su contenido exacto son tentativos; lo firme es el Tramo A
> y el *gate* de 1.0.

Son ~9 pasos después de 0.13 → coincide con la intuición de "~10 iteraciones".

## Backlog a ubicar (no decidido)

- **#256** epic multi-proveedor (post-S2) → paraguas de 0.13/0.14.
- **#205** colaboración por Git como flujo de primera clase → probablemente **post-1.0** o Discussion.
- **#263 / #262** skills (auditar-proyecto, variante /retro-ciclo) → tooling, se pliega oportunista.
- **#235** benchmark @slow huérfano en CI → higiene, cae en 0.16 (rendimiento).

## Decisiones tomadas en la sesión (2026-07-18)

- ✅ Gate v1.0 = **mantener 3 criterios + algo más (por definir)**.
- ✅ 0.14.0 = **completar multi-proveedor**.
- ✅ Registro = **esta nota** (no milestones ni ADR todavía; "lo miro otro día").
- ✅ Limpieza: borrados caches regenerables + worktree huérfano `agent-aa303cfc4bc16564b`.
- ✅ El arco tiene **dos tramos**: A (0.13–0.15, firme, derivado del pasado) y B (0.16→1.0,
  zona de estabilización PROVISIONAL). El Tramo B se conforma con **validación de UX con muchos
  usuarios**, que **corre el PO (Luis)**; sus tareas hoy no se conocen y no se planifican desde
  el escritorio → entran por el lazo RETROALIMENTAR (`/cosechar-sesion`).

## Qué falta decidir (para la próxima vez que mires esto)

1. Definir el **"+ algo más"** del gate de v1.0.
2. ¿El arco se sella como **ADR** (decisión estructural) + **milestones** 0.14→1.0, o se deja fluido?
3. Import multi-formato (0.17): ¿**dentro** o **fuera** del scope de 1.0?
4. Confirmar si **rendimiento #206** merece versión propia o se reparte.
