# El ciclo humano de exploración bibliográfica (eje teórico)

Resumen operativo de la Nota 05 (`docs/Notas/05-ciclo-investigacion-humano.md`) para
la skill. Modela el ciclo **iterativo y no-lineal** de exploración bibliográfica y marca
**dónde asiste bib2graph** y dónde el juicio es **irreductiblemente humano**.

## El ciclo (no lineal: lazo 2→3→4→1)

| Paso | Qué pasa | Verbo bib2graph | Quién |
|---|---|---|---|
| 0 | Idea / pregunta difusa (Kuhlthau: alta incertidumbre) | — *(la entrevista asiste)* | **Humano** |
| 1 | Semillas (el "grano", pearl growing) | `seed --equation` / `seed --from-bib` | mixto |
| 2 | Chaining / forrajeo (snowballing back/forward) | `chain --depth --direction` | **Herramienta** |
| 3 | Browsing / diferenciar | `read top/show`, `build` | mixto |
| 4 | La query y la idea **mutan** (Bates: berrypicking) | refinar `--equation` / re-`seed` | **Humano** |
| 5 | Organizar en evidencia (concept matrix) | `build` + `read` | Herramienta |
| 6 | Sensemaking / tensiones | leer las redes | **Humano** |
| 7 | Curar la biblioteca (berry *growing*) | `curate accept/reject/filter`, `snapshot create` | **Humano** decide |
| 8 | Monitorear (alertas de lo nuevo) | `chain --since` | Herramienta |

## El punto clave

La **bibliometría es el information scent**: el candidato se prioriza por cuánto se
**acopla / co-cita / es central** respecto del corpus curado — **estructura, no IA**, y por
eso reproducible. Trade-off honesto: rankear por estructura presente sesga hacia lo
central/popular (efecto Mateo); el scent **prioriza**, la exhaustividad la sostienen los
filtros (PRISMA) en `curate`.

**Proveedor de datos:** por defecto `openalex`; se fija por investigación con
`b2g init --source {openalex,s2}` y `--source` lo pisa por invocación (precedencia:
`--source` > `workspace.json` > `openalex`). Cada proveedor tiene su **carril**: sembrar o
forrajear con `--source s2` escribe en el carril `s2` sin tocar `openalex`, y los dos
conviven en la misma investigación. No hay vista unificada: `build`, `read`, `curate`,
`status`, `export` y `snapshot` operan sobre **un** carril (el de `--source` o el de la
investigación). Para comparar proveedores, dos builds (`b2g build --source s2 --out-dir ...`; `export --format arrow` solo embebe la red de `networks/`).
La curación es del paper (un `id`), así que viaja entre carriles cuando el `id` coincide
(papers con DOI). `s2` necesita `S2_API_KEY` para sembrar (el forrajeo anda sin key) y no acepta `--exclude`/`--min-year`/`--max-year`/`--native`.

**Irreductiblemente humanos:** pasos 0, 4, 6, 7. La herramienta **no automatiza el juicio**:
asiste el forrajeo con estructura y le da al humano el material para el sensemaking.

## Tradiciones que lo fundamentan

- **Information Seeking (LIS):** Kuhlthau (ISP, dimensión afectiva), Ellis (chaining),
  Bates (berrypicking: la búsqueda no es lineal).
- **Foraging + Sensemaking (HCI):** Pirolli & Card (information scent, foraging/sensemaking loops).
- **Revisión sistemática:** Wohlin (snowballing), SALSA, Webster & Watson (concept matrix),
  vom Brocke (rigor del proceso), PRISMA.
