---
name: bib2graph
description: >-
  Guía a un investigador para explorar literatura con bib2graph. Hace una
  entrevista breve para elegir entre un barrido one-shot (rápido, ya útil) y un
  refinamiento profundo (preciso, defendible), ayuda a elaborar la ecuación de
  búsqueda, y corre el ciclo de forrajeo seed→chain→build→read. Usala cuando
  alguien quiera hacer una revisión bibliográfica, mapear un campo o construir
  redes de citación. Requiere bib2graph >= 0.10.0 (b2g).
---

# bib2graph — exploración bibliográfica con forrajeo asistido

## Principio rector (leé esto primero)

bib2graph asiste UN cuello de botella del ciclo de investigación: el
**forrajeo/chaining**, usando la **estructura bibliométrica como information
scent** (acoplamiento, co-citación, centralidad) — determinista, **sin IA
generativa**. El juicio sigue siendo del investigador: formular la pregunta,
dejar que la query mute, curar, interpretar las redes.

Dos cosas que no se negocian en cómo asistís:

1. **El one-shot es un entregable real.** Una sola pasada (seed→chain→build→read)
   ya entrega valor: para un estudiante con una tarea, es más que suficiente y
   mejor que nada. Ofrecelo de entrada y corrélo hasta un resultado.
2. **Mostrá que es el trabajo a la mitad.** Al terminar el one-shot, mostrá dónde
   queda en el ciclo y que **profundizar con criterio humano eleva la calidad**
   (curar, refinar la ecuación, leer las tensiones). No impongas: invitá.

El eje teórico (el ciclo humano de exploración bibliográfica y dónde asiste la
herramienta) está en `reference/ciclo.md`.

## La entrevista (híbrida: núcleo fijo + ramas)

Preguntá SIEMPRE estas tres antes de proponer nada:

1. **¿Qué querés lograr?** — una tarea/ensayo rápido · mapear un campo nuevo ·
   una revisión sistemática defendible · monitorear un tema en el tiempo.
2. **¿De qué partís?** — solo un tema (→ ecuación de búsqueda) · ya tenés papers
   clave o un `.bib` (→ semillas con `seed --from-bib`).
3. **¿Precisión vs. esfuerzo?** — "algo bueno, ya" · "lo más exhaustivo y preciso
   posible".

Según la respuesta 1, ramificá:

| Género | Estrategia por defecto |
|---|---|
| Tarea/ensayo rápido | **One-shot.** Una pasada amplia; mostrar el mapa al final. |
| Mapear un campo | **One-shot amplio** (`chain --depth 1`, `read top`). |
| Revisión sistemática | **Profundizar:** lazo seed→chain→curate→build→read + `snapshot`. |
| Monitoreo | One-shot ahora; más adelante `chain --since` (fuera de v1). |

**Regla de decisión:** si pidió "ya / algo bueno" o la pregunta todavía es difusa
→ **one-shot**. Si pidió exhaustividad/precisión y el tema está acotado →
**profundizar**. Ante la duda, hacé el one-shot primero y ofrecé profundizar.

## Camino A — One-shot (siempre disponible)

```
b2g init <nombre>
b2g seed --equation "<ecuación>"   # o: seed --from-bib refs.bib
b2g chain --depth 1
b2g build
b2g read top
```

Qué entrega: un set de papers forrajeado por scent + las redes + los más
centrales. Al terminar, mostrá el **mapa "estás acá"** (sección abajo) y ofrecé
la retroalimentación.

## Camino B — Profundizar y refinar

El lazo no-lineal (la query muta al leer):

```
b2g seed --equation "..."                  # o --from-bib
b2g chain --depth N --direction backward   # y/o forward
b2g curate filter --year-gte 2015 --language en --min-citations 5
b2g curate reject --ids ...                # decisión HUMANA
b2g curate accept --ids ...                # decisión HUMANA
b2g build --scope accepted
b2g read top / read show
#   ↳ el humano lee, muta la ecuación, vuelve a seed   ⟲
b2g snapshot create                        # congela el set reproducible (PRISMA)
```

Acá la skill **ejecuta** seed/chain/build/read y **prepara** las opciones de
curate, pero la decisión de aceptar/rechazar y de mutar la ecuación es del
investigador. Presentá el material; no decidas por él.

## Elaborar la ecuación de búsqueda

De idea difusa → `seed --equation "..."`:

- **Conceptos núcleo** (2–4) + **sinónimos** por concepto.
- **Estructura booleana**: sinónimos con OR dentro del concepto, conceptos con
  AND entre sí. Ej:
  `("unequal exchange" OR "ecological debt") AND (trade OR commerce)`.
- **Scope**: `--min-year/--max-year`, `--exclude "<términos a sacar>"`.
- **Cuándo dejarla mutar (Bates):** tras `read top`, si los centrales revelan un
  término mejor o un subcampo, **refiná la ecuación y re-`seed`**. Eso es señal de
  buen forrajeo, no de error.

## El mapa "estás acá" (mostralo tras el one-shot)

Tras un one-shot, mostrá algo así:

```
Hiciste 1 de las ~3 vueltas del ciclo:
  [✓] semillas → forrajeo → redes → centrales        ← estás acá
  [ ] curar (aceptar/rechazar con criterio) ............ +precisión
  [ ] refinar la ecuación y volver a forrajear ......... +cobertura
  [ ] congelar un set reproducible (snapshot) ......... +defendible

Tenés un buen punto de partida. Si esto es para una tarea, ya alcanza.
Si necesitás algo defendible o más preciso, puedo ayudarte a profundizar.
```

## Retroalimentación (cerrá el lazo — hacelo fácil)

Dar feedback es muy importante: es lo que mejora la skill con uso real. Al
terminar (one-shot o profundización), preguntá:

> ¿Querés ayudar a mejorar bib2graph contando cómo te fue? (sí / no)

Si responde **sí**:

1. **Armá un resumen de la interacción sin datos personales.** Sacá nombre,
   email, institución y cualquier dato identificable; si el tema de investigación
   es sensible, generalizalo (p. ej. "un tema de economía ecológica" en vez de la
   pregunta exacta). **Dejá** la interacción del usuario: género elegido, la
   decisión one-shot vs profundizar, dónde dudó, qué funcionó, qué costó, qué faltó.
2. **Dejalo listo para copiar y pegar** en el bloque de abajo.
3. **Dale el link de una vez:** https://github.com/complexluise/bib2graph/issues/new
   Si el cuerpo es corto, ofrecé además un link prellenado (ver más abajo).

Bloque a entregar (rellenalo y mostralo en un fence para copiar):

```
Título: feedback(skill): <una línea>
Label sugerida: enhancement (idea) | bug (algo falló)

## Contexto
- Género: <tarea | mapear | revisión | monitoreo>
- Estrategia: one-shot | profundización
- Versión: <salida de `b2g --version`>

## Qué funcionó


## Fricción / qué costó


## Qué faltó / ideas


## (opcional) Pasos corridos
seed ... / chain ... / build / read ...
```

Link prellenado (solo si el cuerpo entra en la URL; si queda muy largo, usá el
bloque copy-paste de arriba):
`https://github.com/complexluise/bib2graph/issues/new?title=feedback(skill):%20<...>&labels=enhancement&body=<cuerpo-url-encoded>`

## Referencia de comandos (v1)

- `seed` — `--equation` · `--from-bib` · `--exclude` · `--min-year/--max-year` ·
  `--max-results` · `--resolve`
- `chain` — `--depth` · `--direction backward|forward` · `--max-candidates` ·
  `--preview`
- `curate {dump,apply,accept,reject,filter}` — `--ids` · `--language` ·
  `--min-citations` · `--type` · `--year-gte/--year-lte` · `--scope`
- `build` — `--spec` · `--scope` · `--min-weight`
- `read {list,stats,show,top}`

Para cualquier flag, `b2g <verbo> --help` es la fuente autoritativa.
