# Changelog

Todos los cambios notables de `bib2graph` se documentan acá. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es/1.1.0/), y este proyecto
adopta [Semantic Versioning](https://semver.org/lang/es/) (ver
[`VERSIONING.md`](./VERSIONING.md)).

Este changelog lo **gestiona `release-please`** (ya conectado; ver
[`VERSIONING.md`](./VERSIONING.md) y ADR 0006): su PR de release actualiza esta sección
desde los Conventional Commits y bumpea `pyproject.toml`. Al mergear ese PR se crea el tag
`vX.Y.Z` y el GitHub Release. Las secciones por debajo de `[0.3.0]` son el historial previo a
la conexión del tooling (se mantuvieron a mano); de acá en adelante las gestiona el bot.

## [0.10.1](https://github.com/complexluise/bib2graph/compare/v0.10.0...v0.10.1) (2026-06-30)


### Bug Fixes

* **export:** escribir CSV en utf-8-sig (BOM) para Excel-Windows ([#216](https://github.com/complexluise/bib2graph/issues/216)) ([66339a7](https://github.com/complexluise/bib2graph/commit/66339a787debb04e88413147cfc8d7e22916ae2f))

## [0.10.0](https://github.com/complexluise/bib2graph/compare/v0.9.0...v0.10.0) (2026-06-28)


### ⚠ BREAKING CHANGES

* **cli:** se elimina el subcomando b2g gui y el extra [gui]; el wheel ya no vendorea frontend.

### Features

* **build:** absorber networks via --spec + --scope/--min-weight + diagnóstico red-vacía ([#159](https://github.com/complexluise/bib2graph/issues/159)) ([#169](https://github.com/complexluise/bib2graph/issues/169)) ([c4aee24](https://github.com/complexluise/bib2graph/commit/c4aee240bc6c3b95650bf2f0015025ff60e2b970))
* **chain:** absorber monitor como chain --since (forrajeo incremental) ([#158](https://github.com/complexluise/bib2graph/issues/158)) ([#176](https://github.com/complexluise/bib2graph/issues/176)) ([6541663](https://github.com/complexluise/bib2graph/commit/6541663a29eaf41f3427f9dd1370dda7a994c5dd))
* **cli:** --json unificado por decorador + B2G_JSON env + stdout puro enforced ([#151](https://github.com/complexluise/bib2graph/issues/151)) ([#168](https://github.com/complexluise/bib2graph/issues/168)) ([214d230](https://github.com/complexluise/bib2graph/commit/214d2308029a492ddc8b892eda5fc281482d8a75))
* **cli:** absorber enrich en chain/build ([#162](https://github.com/complexluise/bib2graph/issues/162)) ([#178](https://github.com/complexluise/bib2graph/issues/178)) ([df9fea2](https://github.com/complexluise/bib2graph/commit/df9fea29c1176e88f31f8fc2a0d2c7d5cf2a2d88))
* **cli:** aliases de retrocompat con aviso de deprecación + entry-point bib2graph ([#165](https://github.com/complexluise/bib2graph/issues/165)) ([#180](https://github.com/complexluise/bib2graph/issues/180)) ([d4cdf0b](https://github.com/complexluise/bib2graph/commit/d4cdf0b53aa9f5d5c8e2a784917001d436bccb7e))
* **cli:** grupo noun-verb read {list,stats,show} absorbiendo inspect ([#156](https://github.com/complexluise/bib2graph/issues/156)) ([#170](https://github.com/complexluise/bib2graph/issues/170)) ([d00fe8c](https://github.com/complexluise/bib2graph/commit/d00fe8cad323a95dff8236672be8b061de2b9829))
* **cli:** maturity-stamp en artefactos one-shot (build/snapshot/read top) ([#160](https://github.com/complexluise/bib2graph/issues/160)) ([#173](https://github.com/complexluise/bib2graph/issues/173)) ([8697144](https://github.com/complexluise/bib2graph/commit/8697144e9b15f99767bcaf8d2ab2541956f64832))
* **cli:** retirar la GUI local (api/SPA/b2g gui) — fuera del foco de la librería ([#197](https://github.com/complexluise/bib2graph/issues/197)) ([fa19291](https://github.com/complexluise/bib2graph/commit/fa1929154a9972f65dbecd722b6cbd03d5ced805))
* **cli:** status como mapa — next_best_action, readiness y preview por-red (ADR 0037 §e) ([#153](https://github.com/complexluise/bib2graph/issues/153)) ([726272b](https://github.com/complexluise/bib2graph/commit/726272b82bfd4e99d408f7e8e480711caac523cb))
* **read:** read top — centrales + co-citación con título (salida de investigación) ([#157](https://github.com/complexluise/bib2graph/issues/157)) ([#171](https://github.com/complexluise/bib2graph/issues/171)) ([b66ac4a](https://github.com/complexluise/bib2graph/commit/b66ac4a69ff6b885bc7e93aa273a6016eace386d))
* **skill:** distribuir skill de Claude Code end-user vía `b2g skill add` ([#188](https://github.com/complexluise/bib2graph/issues/188)) ([#192](https://github.com/complexluise/bib2graph/issues/192)) ([29b3f13](https://github.com/complexluise/bib2graph/commit/29b3f139051be90ce20471dc6d434641f59e5752))
* **skill:** salida agéntica explícita en `skill add` (ruta + cómo opera + leelo) ([#194](https://github.com/complexluise/bib2graph/issues/194)) ([9c81be8](https://github.com/complexluise/bib2graph/commit/9c81be8f0c32e0d65a0ce8d98c2d271a8199d073))


### Bug Fixes

* **provenance:** persistir manifest.enrichers vía enricher_log ([#141](https://github.com/complexluise/bib2graph/issues/141)) ([#198](https://github.com/complexluise/bib2graph/issues/198)) ([c489064](https://github.com/complexluise/bib2graph/commit/c48906466d6a8ff638faf16e9576901c12eb0765))


### Performance Improvements

* **test:** eliminar build redundante en idempotencia de comunidades (~-24%) ([#189](https://github.com/complexluise/bib2graph/issues/189)) ([50a9f68](https://github.com/complexluise/bib2graph/commit/50a9f68afe64760d4c65761a88876a21e0871790))


### Documentation

* **adr:** 0037 — superficie CLI 0.10.0 (10 verbos agents-first que mapean el ciclo) ([#150](https://github.com/complexluise/bib2graph/issues/150)) ([35099b1](https://github.com/complexluise/bib2graph/commit/35099b14702f7f6c26f0d5135bb8d05fd5158f24))
* **adr:** 0038 — destino de los 5 verbos huérfanos del 0037 (10 verbos verificable) ([#154](https://github.com/complexluise/bib2graph/issues/154)) ([a8af1e5](https://github.com/complexluise/bib2graph/commit/a8af1e5731d8fa7146a370cf2d4dab72a170fe94))
* alinear docs vivos al presente de v0.10.0 ([#191](https://github.com/complexluise/bib2graph/issues/191)) ([#199](https://github.com/complexluise/bib2graph/issues/199)) ([bc36b2c](https://github.com/complexluise/bib2graph/commit/bc36b2c26a970865ab33d128fea328cde3e05cfa))
* **api:** consolidar superficie CLI 0.10.0 + enmiendas ADR 0025/0031/0038 ([#166](https://github.com/complexluise/bib2graph/issues/166)) ([#181](https://github.com/complexluise/bib2graph/issues/181)) ([fc7c9b6](https://github.com/complexluise/bib2graph/commit/fc7c9b6c96ce6c9c68afdb3e52dd688e368d7415))
* **notas:** Nota 21 — descomposición de la suite de tests para poda ([#184](https://github.com/complexluise/bib2graph/issues/184)) ([#185](https://github.com/complexluise/bib2graph/issues/185)) ([272d87c](https://github.com/complexluise/bib2graph/commit/272d87c0e5eeb4b0b0ad84670809c9d87cfcb7b1))

## [0.9.0](https://github.com/complexluise/bib2graph/compare/v0.8.0...v0.9.0) (2026-06-25)


### Features

* **cli:** preview del crecimiento del chaining antes del fetch ([#89](https://github.com/complexluise/bib2graph/issues/89)) ([#144](https://github.com/complexluise/bib2graph/issues/144)) ([e89e1ec](https://github.com/complexluise/bib2graph/commit/e89e1ec42157417093c265f6574b71daac09adaf))
* **networks:** cablear assortativity_attribute + composición ([#90](https://github.com/complexluise/bib2graph/issues/90)) ([#143](https://github.com/complexluise/bib2graph/issues/143)) ([27fce62](https://github.com/complexluise/bib2graph/commit/27fce6235caf49348c3737c7f359dd3db02ed9d9))


### Bug Fixes

* **provenance:** b2g filter registra el filtro (manifest + procedencia) ([#126](https://github.com/complexluise/bib2graph/issues/126)) ([#140](https://github.com/complexluise/bib2graph/issues/140)) ([3eb20da](https://github.com/complexluise/bib2graph/commit/3eb20dae27b6976709cc93587821cc1571bcfbea))
* **seed:** cerrar el backend clonado correcto en reseed ([#93](https://github.com/complexluise/bib2graph/issues/93)) ([#142](https://github.com/complexluise/bib2graph/issues/142)) ([d0a3239](https://github.com/complexluise/bib2graph/commit/d0a32393035084ab0d699d4418fb83825f5d7576))


### Documentation

* README install (uv recomendado) + limpieza de AI_DISCLOSURE ([#133](https://github.com/complexluise/bib2graph/issues/133)) ([5bb99f9](https://github.com/complexluise/bib2graph/commit/5bb99f97b93507ff83030fca2cf5ee1f8c8ae8fa))
* sincronizar PRD/ARCHITECTURE con el 0.8 (Tier 1 — hechos) ([#135](https://github.com/complexluise/bib2graph/issues/135)) ([49ecdbe](https://github.com/complexluise/bib2graph/commit/49ecdbe25afdf485c46d1298f160d2e73ee217df))

## [0.8.0](https://github.com/complexluise/bib2graph/compare/v0.7.0...v0.8.0) (2026-06-22)


### ⚠ BREAKING CHANGES

* **core:** la columna openalex_id del corpus se renombra a source_id y el id canónico cambia de prefijo oa: a doi:/src:. service/reads.get_paper devuelve source_id (rompe la GUI a propósito, #117). Workspaces legacy necesitan re-key.

### Features

* **backends:** tabla lateral external_ids (ADR 0036, infra opción C) ([#118](https://github.com/complexluise/bib2graph/issues/118)) ([ec55c77](https://github.com/complexluise/bib2graph/commit/ec55c77920a505d1aed5a4df1e712655956e1c88))
* **cli:** b2g resolve + seed --from-bib --resolve — flujo BibTeX e2e ([#110](https://github.com/complexluise/bib2graph/issues/110), [#112](https://github.com/complexluise/bib2graph/issues/112)) ([#123](https://github.com/complexluise/bib2graph/issues/123)) ([aeda285](https://github.com/complexluise/bib2graph/commit/aeda285d844165c862912ed91daff645b59293ba))
* **core:** identidad source-agnóstica — source_id + DOI ancla (ADR 0036) ([#119](https://github.com/complexluise/bib2graph/issues/119)) ([4a5d982](https://github.com/complexluise/bib2graph/commit/4a5d982871518f16e5ae18c6430859d5c4136cee))
* **networks:** keyword_filter en NetworkSpec para sub-redes temáticas ([#116](https://github.com/complexluise/bib2graph/issues/116)) ([b58d200](https://github.com/complexluise/bib2graph/commit/b58d2004771e232713b2bc22e48b0a9d847d347f)), closes [#113](https://github.com/complexluise/bib2graph/issues/113)


### Documentation

* **adr:** 0036 identidad source-agnóstica (DOI ancla, source_id genérico) ([#114](https://github.com/complexluise/bib2graph/issues/114)) ([3777e33](https://github.com/complexluise/bib2graph/commit/3777e33051e1a96a1575ec43d27cb0e863ecabbe))
* **adr:** graduar 0035 a Aceptada (ingesta doble puerta + resolución DOI) ([#122](https://github.com/complexluise/bib2graph/issues/122)) ([8bd5257](https://github.com/complexluise/bib2graph/commit/8bd5257b0aa480bd182f674e2a94e5608eedf431))
* **api:** sincronizar API.md/ARCHITECTURE con source_id (ADR 0036) ([#121](https://github.com/complexluise/bib2graph/issues/121)) ([9d35628](https://github.com/complexluise/bib2graph/commit/9d35628b38aff81f80416d13e3326ac017942004))
* encuadre flujo biblioteca + ADRs 0032-0035 (Propuesta) ([#106](https://github.com/complexluise/bib2graph/issues/106)) ([814bd45](https://github.com/complexluise/bib2graph/commit/814bd45f87ea6b3a922e8b3b62db65e57f97b91f))
* **notas:** 19 — QA del CLI, límites y análisis de superficie (sesión 0.8) ([#128](https://github.com/complexluise/bib2graph/issues/128)) ([1fc6d91](https://github.com/complexluise/bib2graph/commit/1fc6d9190140726c2c5c90a7a622762c3c4f404d))
* **notas:** sesiones e2e — anomalías ML (14) + hueco capa lectura/análisis (15) ([#107](https://github.com/complexluise/bib2graph/issues/107)) ([39dd14d](https://github.com/complexluise/bib2graph/commit/39dd14d10c5d9f3a4489ac45656b60c2c09a3b61))

## [0.7.0](https://github.com/complexluise/bib2graph/compare/v0.6.0...v0.7.0) (2026-06-18)


### Features

* **api:** API local FastAPI + b2g gui + service/curate (G3) ([6cca1e0](https://github.com/complexluise/bib2graph/commit/6cca1e099925023511402cb5f1e0f57e7f6f9529))
* **build:** wheel incluye el frontend (force-include) + job CI frontend (G5) ([f90a0f6](https://github.com/complexluise/bib2graph/commit/f90a0f6d3b5ea3147c35ccf7cec5e54a52c46e02))
* **gui:** MVP de la GUI local (G1–G5) — capa de servicios + API + frontend + empaquetado ([feed3e4](https://github.com/complexluise/bib2graph/commit/feed3e4da2f97d2c8a22ed1359c255112b464d6a))
* **gui:** SPA frontend D-2 "Observatorio" + wiring del token (G4) ([c40c81d](https://github.com/complexluise/bib2graph/commit/c40c81db7c22f35d07564bb2961e175ca1fd538d))
* **service:** capa de servicios neutral; CLI como adaptador (G1) ([e9ea4b7](https://github.com/complexluise/bib2graph/commit/e9ea4b7f7e9c97d400a99e774b4a0b574c5bb496))
* **service:** lecturas read-only para la GUI (G2) ([fc80c5d](https://github.com/complexluise/bib2graph/commit/fc80c5dfcd5f2c71e8f84140be8efab0a9c651d0))


### Bug Fixes

* **build:** force-include rompía el editable install sin frontend (.gitkeep) ([0ac9c77](https://github.com/complexluise/bib2graph/commit/0ac9c77104813f42f98d9fa3e06baecb9f4a442a))
* **gui:** GET / devolvía 422 en vez de servir la SPA ([9ed70b1](https://github.com/complexluise/bib2graph/commit/9ed70b1d27f688aad711f68a06628a30159d9325))


### Documentation

* **api:** documentar capa service/ (API.md §0 + AGENTS estructura) ([4c57f45](https://github.com/complexluise/bib2graph/commit/4c57f454360d53ea08b5653983a54d19f42562ff))
* documentar API local (G3 AS-BUILT) ([87f3fca](https://github.com/complexluise/bib2graph/commit/87f3fca566b08b58836bcc3cf79a990ebe7704f3))
* documentar frontend G4 (AS-BUILT) ([5d1913e](https://github.com/complexluise/bib2graph/commit/5d1913ef104ff128e1320cfac82e0f26296e0ec9))
* documentar lecturas service/ (G2 AS-BUILT) ([7b57f6a](https://github.com/complexluise/bib2graph/commit/7b57f6a28c25af44464ea5eb46778f0b2c5f09ea))
* G5 AS-BUILT + MVP GUI completo (G1–G5) ([460d398](https://github.com/complexluise/bib2graph/commit/460d398f9f7c67bdf20de435f297f9a3d5793d81))
* **gui:** preparar terreno GUI — capa de servicios + ADR 0027/0028 + TARGET ([#98](https://github.com/complexluise/bib2graph/issues/98)) ([6ff6d20](https://github.com/complexluise/bib2graph/commit/6ff6d201afca0aef6ece8a72e49a4edaf51d5278))
* **roadmap:** roadmap del MVP GUI (tramo 05, hitos G1–G5) ([d73d472](https://github.com/complexluise/bib2graph/commit/d73d47218e772dc45f38899665e5a536ccda4564))

## [0.6.0](https://github.com/complexluise/bib2graph/compare/v0.5.0...v0.6.0) (2026-06-18)


### ⚠ BREAKING CHANGES

* **cli:** la opción global --store se elimina por completo del CLI. Pasarla produce el error estándar de Click ("No such option: --store"). El modo degenerado (.duckdb suelto sin workspace.json) deja de resolverse: la única unidad de persistencia es la carpeta con workspace.json. Un .duckdb legacy se adopta con `b2g init .`.

### Features

* **cli:** eliminar --store y el modo degenerado; workspace única forma canónica ([#75](https://github.com/complexluise/bib2graph/issues/75)) ([#85](https://github.com/complexluise/bib2graph/issues/85)) ([a5e46a2](https://github.com/complexluise/bib2graph/commit/a5e46a262081a20ba4841cfebd99fb2c4800211e))
* **networks:** b2g build --corpus-scope (filtrar redes por curación) ([#56](https://github.com/complexluise/bib2graph/issues/56)) ([#82](https://github.com/complexluise/bib2graph/issues/82)) ([cb3df4b](https://github.com/complexluise/bib2graph/commit/cb3df4baf3c6366272a98984146d2e28a81a8021))
* **preprocess:** auto normalize+dedup en ingesta, rapidfuzz core, b2g thesaurus ([#88](https://github.com/complexluise/bib2graph/issues/88)) ([#94](https://github.com/complexluise/bib2graph/issues/94)) ([d09aeae](https://github.com/complexluise/bib2graph/commit/d09aeaeac351401ba26df723cc4afa053f61ceff))


### Bug Fixes

* **curate:** --dump excluye semillas; agrega --scope y columnas de revisión ([#72](https://github.com/complexluise/bib2graph/issues/72), [#58](https://github.com/complexluise/bib2graph/issues/58), [#59](https://github.com/complexluise/bib2graph/issues/59)) ([#81](https://github.com/complexluise/bib2graph/issues/81)) ([daf268c](https://github.com/complexluise/bib2graph/commit/daf268caa3914e6a77db23b3f700790d26a2004f))
* **foraging:** backward chaining deja de persistir placeholders fantasma ([#54](https://github.com/complexluise/bib2graph/issues/54)) ([#79](https://github.com/complexluise/bib2graph/issues/79)) ([e26ec2b](https://github.com/complexluise/bib2graph/commit/e26ec2bcbab69dd3d43a10784507b2e3ecbc36dc))
* **foraging:** forward chaining materializa metadata real ([#78](https://github.com/complexluise/bib2graph/issues/78)) ([#80](https://github.com/complexluise/bib2graph/issues/80)) ([ec640d9](https://github.com/complexluise/bib2graph/commit/ec640d953eb48f772ae7f40d59c21a61da37679e))


### Documentation

* ejemplo YAML, clusters.csv solo redes de paper, curación auto opt-in; versiona notas 11/13 ([#73](https://github.com/complexluise/bib2graph/issues/73), [#74](https://github.com/complexluise/bib2graph/issues/74), [#65](https://github.com/complexluise/bib2graph/issues/65)) ([#83](https://github.com/complexluise/bib2graph/issues/83)) ([3e3429e](https://github.com/complexluise/bib2graph/commit/3e3429e226d2f97eb4e762cfe59591625e6507bc))
* **features:** corregir B3 — el scent es bibliométrico (R4), no frecuencia de enlace ([#91](https://github.com/complexluise/bib2graph/issues/91)) ([8c8e81b](https://github.com/complexluise/bib2graph/commit/8c8e81b74826cb3b7e4b83d47ff3fc423d9c4701))
* **features:** escenarios BDD/Gherkin por historia de usuario (PRD §7) + freshness PRD ([#87](https://github.com/complexluise/bib2graph/issues/87)) ([cac4c5f](https://github.com/complexluise/bib2graph/commit/cac4c5ffdab2c21757bec7d1007432bdd44cdb0d))
* **roadmap:** B3 scent — R4 hecho, no pendiente (traza + banner) ([#92](https://github.com/complexluise/bib2graph/issues/92)) ([1a53115](https://github.com/complexluise/bib2graph/commit/1a531152aba3adcc1a329a4284b905172a647717))
* sanear coherencia de artefactos de entrada (README, conteos, residuos) ([#70](https://github.com/complexluise/bib2graph/issues/70)) ([984edc8](https://github.com/complexluise/bib2graph/commit/984edc83993e28cb70db7fd8dedef63b27ba85da))

## [0.5.0](https://github.com/complexluise/bib2graph/compare/v0.4.0...v0.5.0) (2026-06-17)


### Features

* **cli:** b2g curate — dump + import de curación por CSV ([#22](https://github.com/complexluise/bib2graph/issues/22), [#26](https://github.com/complexluise/bib2graph/issues/26)) ([#44](https://github.com/complexluise/bib2graph/issues/44)) ([04bce5a](https://github.com/complexluise/bib2graph/commit/04bce5adffda754f03d0fd96a7306208126e41ab))
* **cli:** equation.yaml cargable (seed --spec) + b2g restore offline (9a, [#33](https://github.com/complexluise/bib2graph/issues/33)) ([#51](https://github.com/complexluise/bib2graph/issues/51)) ([23436ef](https://github.com/complexluise/bib2graph/commit/23436efdd3deffc51679e2deb9e6b80091b06e80))
* **examples:** valoraciones reproducible 100% por CLI (Ciclo B) ([#67](https://github.com/complexluise/bib2graph/issues/67)) ([be75b4a](https://github.com/complexluise/bib2graph/commit/be75b4a71670e3d3c64cfa3a111808f9539c4efa))
* **examples:** workspace valoraciones + gate de reproducibilidad R2 (9b, cierra [#33](https://github.com/complexluise/bib2graph/issues/33)) ([#52](https://github.com/complexluise/bib2graph/issues/52)) ([c7dfba7](https://github.com/complexluise/bib2graph/commit/c7dfba710090195baed0d225f9dbf75c5412e797))
* **foraging:** forward chaining batcheado con cap por semilla ([#21](https://github.com/complexluise/bib2graph/issues/21)) ([#42](https://github.com/complexluise/bib2graph/issues/42)) ([58a394d](https://github.com/complexluise/bib2graph/commit/58a394d9f973ed244ffb3ec9d4a190897d4430cb))
* **networks:** capa declarativa NetworkSpec YAML + b2g networks (Hito 9) ([#47](https://github.com/complexluise/bib2graph/issues/47)) ([8d15c24](https://github.com/complexluise/bib2graph/commit/8d15c24a185ae51d794c20b8bc98b28bb600acdb))
* **networks:** capa decorate — labels + atributos legibles en nodos ([#25](https://github.com/complexluise/bib2graph/issues/25)) ([#43](https://github.com/complexluise/bib2graph/issues/43)) ([9c4597c](https://github.com/complexluise/bib2graph/commit/9c4597c95102acbf3c9ecf410c45d8cfce976b44))
* **networks:** tabla de clusters a CSV ([#31](https://github.com/complexluise/bib2graph/issues/31)) ([#46](https://github.com/complexluise/bib2graph/issues/46)) ([49cf28b](https://github.com/complexluise/bib2graph/commit/49cf28b4cf7d8f05416e60ae4ac4f53e0fd58984))
* **seed:** b2g seed --from-bib + filtro de año real ([#50](https://github.com/complexluise/bib2graph/issues/50), Ciclo 10) ([#53](https://github.com/complexluise/bib2graph/issues/53)) ([f4d3b8a](https://github.com/complexluise/bib2graph/commit/f4d3b8a70a60dd4d47e0c0b422dd268e54bf4186))
* **sources/cli:** seed --max-results + negaciones --exclude ([#14](https://github.com/complexluise/bib2graph/issues/14), [#30](https://github.com/complexluise/bib2graph/issues/30)) ([#45](https://github.com/complexluise/bib2graph/issues/45)) ([882e7fa](https://github.com/complexluise/bib2graph/commit/882e7fa3f8dcef0fdbf81050419445dfc4453b83))
* **workspace:** snapshot/export por ambiente + aviso de staleness ([#32](https://github.com/complexluise/bib2graph/issues/32)) ([#49](https://github.com/complexluise/bib2graph/issues/49)) ([861daa9](https://github.com/complexluise/bib2graph/commit/861daa96b6706c7ed64f474e3ecece709911119f))
* **workspace:** workspace por investigación — b2g init + resolución ambiente (ADR 0029) ([#41](https://github.com/complexluise/bib2graph/issues/41)) ([23bf94e](https://github.com/complexluise/bib2graph/commit/23bf94e93a96cb388faf55cefbf093a398460dd3))


### Bug Fixes

* **sources:** filtro --exclude mal-formado en OpenAlex ([#30](https://github.com/complexluise/bib2graph/issues/30)) ([#66](https://github.com/complexluise/bib2graph/issues/66)) ([8c9ea88](https://github.com/complexluise/bib2graph/commit/8c9ea88c9eada832b45796d4fc002a56e8614df2))


### Documentation

* API.md §7.1, ADR 0014 nota AS-BUILT, AGENTS (437), ROADMAP. Cierra [#25](https://github.com/complexluise/bib2graph/issues/25). ([9c4597c](https://github.com/complexluise/bib2graph/commit/9c4597c95102acbf3c9ecf410c45d8cfce976b44))
* **arch:** ADR 0029 workspace por investigación (Propuesta) + propagación ([#40](https://github.com/complexluise/bib2graph/issues/40)) ([37cce84](https://github.com/complexluise/bib2graph/commit/37cce84d19d3b2aace0dd8c77ea2cacb88731538))
* mover notas de referencia a docs/Notas/ + gitignore datos de usuario ([#27](https://github.com/complexluise/bib2graph/issues/27)) ([87e66a6](https://github.com/complexluise/bib2graph/commit/87e66a69cbfd49704dd275707215a9c335c8c339))
* **notas:** commitear Nota 09 (sesión QA — ecología de valoraciones) ([#36](https://github.com/complexluise/bib2graph/issues/36)) ([ca43163](https://github.com/complexluise/bib2graph/commit/ca43163d2df85730d48aedfedfef6c510b932d46))
* **notas:** explorar frontend tool-for-thought + revisión de referentes ([#24](https://github.com/complexluise/bib2graph/issues/24)) ([4f50b95](https://github.com/complexluise/bib2graph/commit/4f50b95339c08cdab6393e6fc13a77437332c0b3))
* **notas:** Nota 10 — tensiones RESUELTAS + mapeo a issues ([#35](https://github.com/complexluise/bib2graph/issues/35)) ([0a2cbe8](https://github.com/complexluise/bib2graph/commit/0a2cbe86bb4801b4ef1e875ec81cb9e0f1be9ed2))
* **notas:** Nota 12 — encuadre de arquitectura GUI (decisiones A-G propuestas) ([#37](https://github.com/complexluise/bib2graph/issues/37)) ([dcee48d](https://github.com/complexluise/bib2graph/commit/dcee48dce2498ea8a99ffb06e334d152057f8e0e))
* **notas:** síntesis de contextualización GUI (descomposición 07/08/09) ([#28](https://github.com/complexluise/bib2graph/issues/28)) ([e4de811](https://github.com/complexluise/bib2graph/commit/e4de811b9ea92cbc4cdf42aa2e3341160ae025bb))
* **roadmap:** reevaluación pre-GUI — Hitos 1–9 hechos, 10 a la GUI, 11 descartado ([#48](https://github.com/complexluise/bib2graph/issues/48)) ([af34a82](https://github.com/complexluise/bib2graph/commit/af34a82a8fcd6c212c9d25c48bc8168ad6daadf4))

## [0.4.0](https://github.com/complexluise/bib2graph/compare/v0.3.2...v0.4.0) (2026-06-16)


### Features

* **enrichers:** costura Enricher + resolución references→DOI (Hito 8a) ([#10](https://github.com/complexluise/bib2graph/issues/10))
* **enrichers:** co-citación end-to-end poblando cited_by_id (Hito 8b — completa el Hito 8) ([#11](https://github.com/complexluise/bib2graph/issues/11))
* **preprocessors:** dedup fuzzy determinista con rapidfuzz (Hito 7) ([#12](https://github.com/complexluise/bib2graph/issues/12))


### Bug Fixes

* **ci:** fijar release-please target-branch a main ([#16](https://github.com/complexluise/bib2graph/issues/16)) ([314774f](https://github.com/complexluise/bib2graph/commit/314774fd2bd534cece9a39cc24d4a46de0334f78))

## [0.3.2](https://github.com/complexluise/bib2graph/compare/v0.3.1...v0.3.2) (2026-06-16)


### Documentation

* **agents:** documentar el flujo GitFlow-lite en AGENTS.md + crear CLAUDE.md ([#8](https://github.com/complexluise/bib2graph/issues/8)) ([76254a7](https://github.com/complexluise/bib2graph/commit/76254a7bdd2678edb7f1e35e1e0a050622d3f811))
* **arch:** ADR 0024 (orden D3 vía _seq) + saneamiento de coherencia ([e6f0e51](https://github.com/complexluise/bib2graph/commit/e6f0e5124bf3da8f1e900ed75128e06198e839d0))
* **contributing:** documentar el flujo GitFlow-lite (dev/main) + CI en dev ([665988c](https://github.com/complexluise/bib2graph/commit/665988cd6e84fd6523779c280d3245e5156ca43d))
* **contributing:** flujo GitFlow-lite (dev/main) + CI en dev ([1e17869](https://github.com/complexluise/bib2graph/commit/1e17869e81e9d2ddf932d4baacdd542fe5051155))

## [0.3.1](https://github.com/complexluise/bib2graph/compare/v0.3.0...v0.3.1) (2026-06-16)


### Documentation

* ROADMAP a carpeta + saneamiento de coherencia y enlaces ([82e69c3](https://github.com/complexluise/bib2graph/commit/82e69c3206e8dfc0cd3cb724d9a709e0864d17d9))
* ROADMAP a carpeta + saneamiento de coherencia y enlaces ([7aa0a4e](https://github.com/complexluise/bib2graph/commit/7aa0a4e15d253cb583f2ab213a3ed00f3e408721))

## [Unreleased]

## [0.3.0] - 2026-06-16

> **Remediación R1–R5 + cleanup.** Cierra la brecha AS-BUILT↔TARGET del red-team (Nota 06):
> identidad≠procedencia (hash determinista), ciclo de dominio `cycle.py`, scent bibliométrico
> sin IA generativa, robustez/hardening, comando `monitor`. El `corpus_hash` cambia a propósito
> (breaking interno) — de ahí el corte v0.3.

> **Modelo nuevo bloqueado por el PO (2026-06-15)** tras el red-team del AS-BUILT v0.2
> ([Nota 06](docs/Notas/06-critica-as-built-v0.2.md)): el **producto no usa IA generativa** (ADR
> 0022); **capa base** `constants`/`models`/`schemas` única (ADR 0023); enmiendas a
> 0008/0011/0016/0017/0020/0021. La **tanda de remediación R1–R5** del [roadmap](docs/ROADMAP/README.md) lo
> implementa **antes** de los Hitos 7–11. Esta sección documenta el diseño nuevo; el código se
> entrega por hito R.

### Added (cleanup pre-v0.3 — **2026-06-16**)
- **Comando `b2g monitor`** (12° subcomando): re-chequea OpenAlex por **citantes nuevos** del corpus
  (forward chaining), mergea los candidatos nuevos a la biblioteca viva y **transiciona a `MONITORED`**
  (paso 8 del ciclo, Ellis). `data = {new_candidates, total_papers, loop_state, round}`, envelope
  `schema="1"`; `--email` para el polite pool; sin corpus/estado previo → `DataError` (exit 2). Con esto
  **`MONITORED` deja de ser inalcanzable** (cierra el seguimiento de R3/R5). ADR 0021 (enmienda) / 0016.

### Changed (cleanup pre-v0.3 — **2026-06-16**)
- **Alias `LoopState = CycleState` RETIRADO**: el código usa **solo `CycleState`** (de
  `bib2graph.cycle`); se eliminó de `backends/duckdb.py` y `stores/duckdb.py` (cierra la recomendación
  "a retirar pre-1.0" de R3). Una sola clase para el concepto del ciclo.

### Fixed (cleanup pre-v0.3 — **2026-06-16**)
- **`merge` de `DuckDBBackend` ya NO interpola ids crudos en el SQL** (footgun de la Nota 06,
  `backends/duckdb.py:417,423`): se reemplazó el `... id IN ('<id>',...) ORDER BY CASE id WHEN ...` por
  leer las filas y **ordenar en Python** por orden de aparición antes de reinsertar. Orden determinista
  D3 preservado; sin SQL construido con datos. (La alternativa CTE quedó descartada.) ADR 0013 (AS-BUILT).

### Changed (modelo / docs — diseño objetivo)
- **El producto NO usa IA generativa** (ADR 0022, **Hito R4 ✅ 2026-06-16**): el *information scent*
  del forrajeo deja de ser una heurística de frecuencia de enlace y pasa a **scent bibliométrico
  determinista** que consume el primitivo `collect_item_to_papers` de los proyectores, **sin LLM ni
  embeddings**. As-built: backward = **fuerza de co-citación con el corpus**; forward = **fuerza de
  citación directa al corpus** (señal primaria; el AS-BUILT inicial midió acoplamiento puro y degeneraba
  a 0 con referencias ralas → corregido a citación directa **dentro de R4**:
  `forward_score(Y) = |{ref ∈ Y.references_id : ref ∈ corpus_ids}|`); **centralidad diferida**.
  Un solo sentido de "AI-in-the-loop": el desarrollo es asistido por IA; el producto no.
- **Identidad ≠ procedencia** (ADR 0017 enmendado, **Hito R2 ✅ 2026-06-16**): el `corpus_hash` se
  computa **solo sobre contenido bibliográfico** (excluye `provenance`/timestamps; incluye
  `curation_status`); el reloj se inyecta desde la **frontera CLI** (`accept`/`reject`/`filter` pasan
  `decided_at`), con un **fallback `datetime.now(UTC)`** para uso como librería (no afecta la
  identidad); Louvain corre con `random_state` derivado del content-hash → **snapshot reproducible
  bit a bit**. (`resolution` de Louvain **diferido a Hito 9**, NetworkSpec.)
- **Ciclo = FSM cíclico de dominio** (`cycle.py`, ADR 0016 enmendado, **Hito R3 ✅ 2026-06-16**):
  `SEEDED→FORAGED→FILTERED→BUILT→MONITORED` con **`reseed`** (loop-back a `SEEDED` + contador de
  **ronda**, acumula) de primera clase. El enum de estados **sale del backend** a `bib2graph.cycle`
  (dominio puro; el backend solo persiste — columna `round` en `loop_state_log`; alias transicional
  `LoopState = CycleState`, a retirar pre-1.0); `seed` con estado previo se trata como `reseed`;
  `chain`/`filter`/`build` derivan su destino de `apply_transition` (fuente única). **Curación
  transversal** visible en `b2g status`: campos `curation_available`/`round` **aditivos** que mantienen
  `schema="1"` (ADR 0021 enmendado). `MONITORED` está en el modelo, sin comando que lo dispare aún.
- **Capa base de vocabulario + modelos** (ADR 0023): `constants.py` (`Col`/`CurationStatus`/
  `NetworkKind`) como fuente única de literales; `ProvenanceEvent(BaseModel)` con parseo que **falla
  ruidoso**; `PaperRow` ⇄ `CORPUS_SCHEMA` de una sola fuente (Hito R1).

### Removed (diseño objetivo)
- **`explain_candidate`, `foraging/explain.py` y el extra `[llm]`** **eliminados** (ADR 0022,
  **Hito R4 ✅ 2026-06-16**): el producto no usa IA generativa (verificable: el import falla, el extra
  no está en `pyproject.toml`).
- **La "máquina de tensiones"** (antigua "inserción de IA nº2") se **retira del producto** —no se
  difiere a v2, se borra (ADR 0008 enmendado). El **fallback semántico/LLM del thesaurus** también se
  retira (ADR 0011 enmendado): el thesaurus es curado y determinista.

### Fixed (**Hito R5 ✅ 2026-06-16**)
- **UTF-8 en la frontera CLI** (`cli/__init__.py:main` → `_force_utf8()`): el envelope `--json`
  (`ensure_ascii=False`) y `--help` dejan de corromper acentos en Windows cp1252 (Nota 06 RAÍZ 3).
- **Fin del O(n²) en carga**: los cuatro loaders (seed/load OpenAlex, BibTeX, Forager) usan el bulk
  `Corpus.from_arrow` (+ helper `_rows_with_ids`) en vez del loop `add_paper`/`_clone` que re-upserteaba
  la tabla entera por fila.
- **`fetch_citing` con retry/backoff** ante 429/5xx (exponential backoff, 3 intentos). *(El **batching
  por OR** queda diferido —mejora de performance, el N+1 persiste pero ahora es resiliente al
  rate-limit—; ver ROADMAP Hito R5.)*
- **Footguns de la Nota 06** colapsados/eliminados: rama muerta de `OSError` en `_errors.py`;
  `except Exception` de `detect_communities` (`facade.py`) que enmascaraba fallos; param muerto `g` de
  `cocitation_quality_report`; `Literal` duplicado de `NetworkSpec.kind` → `NetworkKind` (fuente única).

### Changed (cambios de comportamiento — **Hito R5 ✅ 2026-06-16**)
> Endurecen el contrato (la Nota 06 los pidió: "sin no-ops silenciosos"). No tocan `schema="1"` ni los
> exit codes externos; sí cambian qué pasa ante entradas inválidas.
- **Filtros PRISMA LANZAN ante campo/operador desconocido** (`ValueError` accionable). Antes era un
  no-op silencioso (`return True` → no filtraba, escondiendo el error).
- **`status`/`validate` ya NO auto-crean el store** ante un typo en `--store` (`open_store_readonly` →
  `StoreError` si el archivo no existe). Antes creaban un `.duckdb` vacío en silencio.
- **`.bib` con error de parseo grave LANZA** `ValueError`; un `.bib` vacío / con entradas sin título
  → `UserWarning`. Antes se tragaba en silencio.
- **`AttributeError` ya no se mapea a exit 3 en `@handle_errors`**: la capacidad-de-source-faltante se
  convierte en `DependencyError` (exit 3) con un pre-check `hasattr` en el comando `chain`; un
  `AttributeError` genuino se propaga limpio (no se disfraza de "capacidad no disponible").
- **`Manifest.lib_version` desconocida = `"unknown"`** (antes `"0.0.0"`): no se inventa una versión
  falsa que mienta sobre la reproducibilidad.

> **Tanda de remediación R1–R5 COMPLETA** (2026-06-16). Próximo: **Hito 7** (deduplicación fuzzy,
> extra `[dedup]`).

## [0.2.0] - 2026-06-15

> **Hitos 5 y 6.** Forrajeo + CLI agente-native: el flujo `seed → chain → filter →
> build → export` corre de una **ecuación** a un **GraphML** **sin escribir código**,
> sobre la biblioteca viva. v0.2 con capacidades completas **del flujo** (no del producto:
> co-citación end-to-end y `explain_candidate`/`[llm]` quedan como stubs/futuros). Tag local
> anotado `v0.2.0` (publicación pendiente).

### Added
- **Forrajeo** (`Forager`: chaining backward/forward, ranking por *information
  scent* = **frecuencia de enlace** —heurística determinista, no IA/LLM—, `preview`
  sin red, filtros PRISMA que marcan `rejected`, `Preprocessor` + thesaurus
  multilingüe). `explain_candidate` (extra `[llm]`) es **stub**. ADR 0008/0011/0020.
- **CLI agente-native `b2g`** (`cli/`): 11 subcomandos (`seed`/`chain`/`filter`/
  `accept`/`reject`/`build`/`export`/`snapshot`/`status`/`inspect`/`validate`),
  envelope `--json` versionado, exit codes 0–5, `--store` global sin estado,
  transiciones `LoopState` automáticas. ADR 0021.

## [0.1.0] - 2026-06-15

> **Hitos 1–4 (+ rework 1.5).** Pipeline mínimo end-to-end: de una **ecuación de
> búsqueda a las redes bibliométricas desde código Python**, sobre una biblioteca
> viva en DuckDB. Tag local anotado `v0.1.0` (publicación pendiente).

### Added
- **Núcleo `Corpus`** (tabla canónica Arrow + Pydantic v2): identidad estable
  (`id`), `merge` idempotente, `accept`/`reject` con `provenance` (log de
  eventos), `snapshot`/`CorpusSnapshot` con `corpus_hash` reproducible. ADR 0013.
- **`TabularBackend` (Protocol) + `InMemoryBackend`** (núcleo puro) y
  **`DuckDBBackend`** (biblioteca viva por defecto: mutación por SQL, `LoopState`,
  single-writer); `DuckDBStore` como fachada de costura. El núcleo no importa
  `duckdb` (carga perezosa). ADR 0015/0016/0019.
- **Redes** (`networks/`): proyectores (acoplamiento, co-citación, co-autoría,
  instituciones, co-word), analizadores (métricas, centralidad, comunidades,
  asortatividad, calidad), exportadores GraphML/CSV, `Networks.quick`. ADR 0014.
- **Costuras `Source`** (`OpenAlexSource` con traducción de ecuación + reporte de
  límites; `BibtexSource`, extra `[bibtex]`). ADR 0007/0012/0017/0018.
- **2º giro** (ADR 0015–0019): `Corpus` sobre `TabularBackend`, máquina de estados
  del lazo (`LoopState`), reproducibilidad por snapshot sellado, `Source`
  agnóstico (mínimo universal vs enriquecimiento), concurrencia single-writer.
- **Migración a uv** como gestor del proyecto (lockfile, `.python-version`,
  dev-dependencies); `docs/decisiones/registro-ia.md` (decisiones tomadas por la
  IA); ADR 0012–0020; reescritura de PRD/ARCHITECTURE/API/ROADMAP/README.

### Changed
- **OpenAlex** es el backbone de datos (ADR 0007); BibTeX pasa a `Source`
  secundaria. **Persistencia por defecto: biblioteca viva DuckDB** como backend
  del `Corpus` (ADR 0009/0015); el snapshot es un export sellado, no el modelo.

### Deprecated
- **Snapshot inmutable / `InMemoryStore` / `ParquetStore` como persistencia por
  defecto** (premisa de ADR 0003 y de la versión previa de 0006): superados por
  la biblioteca viva en DuckDB. `ParquetStore` queda declarado, no implementado.
