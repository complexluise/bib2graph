# exploracion/ — sandbox de validación del caso IED

> **Qué es esto.** Scripts sueltos para **validar el caso de uso "intercambio
> ecológicamente desigual" (IED)** contra librerías externas (`pyalex`,
> `bibtexparser`, `networkx`). Sirve para **probar conceptos** y **tomar postura**
> sobre las tensiones del diseño de `bib2graph` antes de empezar a construir el núcleo.
>
> **Qué NO es.** No es código de `bib2graph`. No se importa desde
> `src/bib2graph/`. No se promueve a costuras del paquete. Es material de
> exploración, no producto.
>
> **Por qué existe fuera de `src/`.** El ROADMAP vigente (Hito 0 → núcleo puro
> primero) prohíbe traer librerías como `pyalex` o `bibtexparser` al núcleo. Estos
> scripts rompen esa prohibición a propósito: necesitan esas librerías para
> responder "¿la combinación de redes + IED entrega valor?". Si la respuesta es
> sí, el siguiente paso es **diseñar la costura** que el núcleo sí va a tener
> (no copiar este código adentro).

## Caso de uso

**Intercambio ecológicamente desigual (IED):** asimetrías Norte-Sur en el comercio
mundial, deuda ecológica, huella ecológica transferida. El objetivo del sandbox es
probar si la combinación de:

- una **biblioteca semilla** de literatura sobre IED (papers que vos curás),
- **OpenAlex** para enriquecer (referencias, citas, afiliaciones),
- las **4 redes bibliométricas** (co-citación, co-autoría, co-word, coupling),

expone de manera útil las **asimetrías de poder epistémico y geográfico** del campo:
quién publica sobre IED, desde dónde, con qué collaborations, citando a quién.

## Estructura

```
exploracion/
  README.md                     # este archivo
  requirements-exploracion.txt  # libs externas usadas acá
  scripts/
    01_search_openalex.py       # query OpenAlex -> CSV
    02_load_bibtex.py           # parser .bib -> CSV (mismo schema)
    03_merge_corpus.py          # une, dedup, dump parquet
    04_build_networks.py        # 4 redes -> GraphML (--coupling-scope seeds|full)
    05_metrics_report.py        # centralidad, asimetrías, asortatividad, informe
    06_apply_thesaurus.py       # aplica thesaurus IED a keywords
    _schema.py                  # schema común a todos los scripts
  datos/
    semillas_ied.bib            # input inicial curado
    thesaurus_ied.json          # thesaurus multilingüe manual (en/es/pt)
    openalex_ied.csv            # salida de 01 (datos reales)
    corpus_ied.csv              # salida de 03
    corpus_ied.parquet          # misma, formato columnar
    redes/                      # GraphML por tipo de red
  informe_ied.md                # auto: datos cuantitativos (se regenera)
  informe_ied_lectura_1.md      # v1: sintético, 21 papers (2026-06-14)
  informe_ied_lectura_2.md      # v2: mixto, 103 papers (2026-06-14)
```

## Cómo correrlo

```bash
pip install -r requirements-exploracion.txt
python scripts/01_search_openalex.py   # red: requiere API key o polite pool
python scripts/02_load_bibtex.py       # offline, sobre datos/semillas_ied.bib
python scripts/03_merge_corpus.py      # une las dos fuentes
python scripts/04_build_networks.py    # produce 4 GraphML en datos/redes/
python scripts/05_metrics_report.py    # produce informe_ied.md
```

Los scripts 02-05 corren **offline** sobre los datos sintéticos que viven en
`datos/`. El 01 sólo se usa para datos reales (requiere cuenta de OpenAlex con
API key gratis desde feb-2026).

## Convenciones de la sandbox

- **Schema común** en CSV: `id,doi,title,year,abstract,authors_raw,authors_id,
  authors_affiliations,keywords_raw,keywords_id,references_doi,source,
  language,is_seed`. Es **exploratorio**: lo más cercano al schema canónico
  propuesto en `docs/ARCHITECTURE.md` §3, con la libertad de romperlo si los
  datos reales lo exigen.
- **Idempotente**: correr dos veces no duplica.
- **Defensivo con campos faltantes**: refleja la regla del AGENTS.md para
  `bibtexparser` (campos opcionales faltan seguido).
- **Sin red salvo en 01**: los demás scripts usan los dumps locales.
- **Sin secretos en código**: la API key de OpenAlex se lee de
  `OPENALEX_API_KEY` (env var) o `~/.openalex/credentials`.

## Decisiones y tensiones que se registran en `informe_ied.md`

Cada vez que la sandbox fuerza una decisión que el `bib2graph` real va a tener
que tomar, se anota en el informe con el formato:

- **Decisión:** qué hicimos acá.
- **Por qué:** qué evidenció.
- **Implicación para el diseño:** qué contracto del núcleo se ve afectado.
- **Pendiente:** qué no se pudo validar.

## Estado

- [x] Estructura y README
- [ ] requirements + seeds sintéticos
- [ ] scripts 01-05
- [ ] pipeline end-to-end corrido
- [ ] informe con tensiones
