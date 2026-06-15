# ROADMAP — bib2graph

> Este roadmap **no es una wishlist**: cada ítem está anclado a algo real encontrado en el
> código. Es el insumo de scoping para el refactor que viene. Fecha: 2026-06-14.
> Las decisiones de arquitectura/contrato deben llevarse al PO antes de ejecutarlas; aquí
> se enmarcan, no se deciden.

## Cómo leer esto

Cada ítem cita su evidencia (`archivo:línea`) y propone una dirección. La prioridad sugerida
es: primero **bugs/seguridad que afectan correctitud**, después **deuda que frena el refactor**,
después **mejoras de alcance**.

---

## A. Bugs reales (afectan correctitud hoy)

### A1. `process_directory` crashea por kwarg inexistente
`main.py:269` llama `loader.process_directory(input_path, progress_callback=...)`, pero la
firma real es `process_directory(self, directory)` (`consigue_los_articulos.py:195`). La
ingesta por **directorio** lanza `TypeError`. La ingesta por archivo no pasa por ahí, así que
el bug está latente.
**Dirección:** unificar la interfaz de progreso (callback opcional) o quitar el argumento.

### A2. `enrich_all_papers` igual, pero enmascarado
`main.py:325` pasa `progress_callback=` a `enrich_all_papers(self)` (`enriquecimiento.py:313`),
que tampoco lo acepta. Acá un `try/except TypeError` (`main.py:326`) lo degrada silenciosamente:
se pierde la barra de progreso y se re-ejecuta el método entero. Es un parche, no una solución.
**Dirección:** misma que A1; el patrón callback debería existir o no, no a medias.

### A3. `Paper(note=...)` — campo inexistente
`create_graph_nodes` pasa `note=paper_data.get('note', '')` (`consigue_los_articulos.py:121`),
pero `Paper` (`models.py:18`) **no tiene** propiedad `note`. neomodel lo ignora o falla según
config; en cualquier caso es dato silenciosamente perdido.
**Dirección:** agregar `note` al modelo o quitar el kwarg.

### A4. `normalize_metadata` asume `research-areas` siempre presente
`consigue_los_articulos.py:84` usa `entry['research-areas']` (acceso directo, no `.get`).
Un BibTeX sin ese campo lanza `KeyError` en la ingesta. El resto de campos usa `.get`.
**Dirección:** uniformar a `.get(..., '')`.

### A5. Código muerto en enriquecimiento de instituciones/keywords
`update_neo4j_with_enriched_data` (`enriquecimiento.py:264-289`) procesa
`enriched_data['institutions']` y `['keywords']`, pero `enrich_from_semantic_scholar` nunca
rellena esas claves (solo `citations/references/authors`). Nunca se ejecuta.
**Dirección:** o se conecta una fuente que las llene (ver C1/C2), o se elimina.

---

## B. Seguridad y configuración (bloqueantes del refactor)

### B1. API key embebida en el código
`enriquecimiento.py:56` tiene una **clave de Semantic Scholar hardcodeada** como fallback:
`os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "L5Ejf...")`. Es un secreto en el repo (y en el
historial de git). Debe revocarse y eliminarse.
**Dirección:** rotar la clave ya; leer solo de entorno/CLI, sin default literal.

### B2. Credenciales Neo4j hardcodeadas y triple-definidas
`NEO4J_PASSWORD = "password"` aparece a nivel de módulo en `consigue_los_articulos.py:19`,
`enriquecimiento.py:50` y `analisis_red.py:19`, y cada módulo setea `config.DATABASE_URL`
**al importarse**. Además los scripts de `analisis/` usan otro default (`"12345678"`,
`centralidad_keywords.py:27`, `agente_navegacion_grafo.py:46`). Hay tres rutas de conexión
conviviendo y dos contraseñas-default distintas.
**Dirección:** una única fuente de configuración de conexión (`Neo4jConfig` / función factory);
quitar los side-effects de import; sin defaults de contraseña.

### B3. `.env` no se autocarga
`python-dotenv` no es dependencia (`pyproject.toml`), así que el `.env` que el README documenta
(`README.md:48-62`) **no se lee solo**. El usuario tiene que exportar variables o pasar flags.
Es una fricción documentada como "gotcha" en CLAUDE.md y README.
**Dirección:** agregar `python-dotenv` y cargarlo en el entry point — o documentar que es
deliberado. Decisión del PO (afecta el contrato de la CLI).

### B4. `SCOPUS_API_KEY` / cliente Scopus inicializado pero sin uso
`enriquecimiento.py:57,77-79` arma un `ElsClient` si hay key, pero nunca se consulta Scopus.
**Dirección:** ver C2.

---

## C. Alcance prometido vs. real

### C1. CrossRef declarado, no usado
`Works()` se instancia en `BibliometricDataEnricher.__init__` (`enriquecimiento.py:74`) y
CrossRef aparece en docstrings y en el README como fuente, pero no hay ninguna llamada de
enriquecimiento contra CrossRef.
**Dirección:** decidir con el PO si CrossRef entra (rellenar metadatos faltantes, fechas, DOIs)
o se quita de las promesas. No inventar la integración sin decisión de producto.

### C2. Scopus igual (ver B4).

### C3. `csv` / `json` listados como entrada pero no implementados
`normalize_metadata` lanza `NotImplementedError` para `csv` y `json`
(`consigue_los_articulos.py:66,99`), aunque `process_directory` los rutea
(`consigue_los_articulos.py:204-209`). Solo `bibtex` está en `TIPOS_ARCHIVOS_SOPORTADOS`.
**Dirección:** implementar o eliminar las ramas; alinear documentación.

---

## D. Deuda estructural (lo que hace caro el refactor)

### D1. Sin cobertura real de tests
`tests/test_imports.py` solo verifica que el paquete importa y que existe `__version__`.
No hay tests de parsing BibTeX, de las consultas Cypher, de las métricas, ni de la
deduplicación. Refactorizar sin red de seguridad es arriesgado.
**Dirección:** antes del refactor grande, tests de caracterización sobre las piezas puras
(normalización, `similar_names`, preprocesamiento de keywords, métricas sobre grafos sintéticos)
y, si es viable, contra una Neo4j efímera (Testcontainers).

### D2. `analisis_red.py` es un monolito (~1000+ líneas, una sola clase)
`BibliometricNetworkAnalyzer` mezcla: creación de relaciones (Cypher), extracción a NetworkX,
informe de calidad, métricas, comunidades, exportación y consultas auxiliares. Es la unidad
más grande del paquete.
**Dirección:** separar responsabilidades (construcción de red / extracción / métricas /
exportación / quality report) en módulos cohesivos. Habilita testear cada pieza.

### D3. Config con side-effects en import (acoplada a B2)
Importar cualquier módulo de fase ejecuta `config.DATABASE_URL = ...` con la contraseña default.
Esto hace que el orden de imports importe y dificulta tests aislados.
**Dirección:** mover la configuración de conexión a la construcción de la clase (ya se hace en
`__init__`), eliminar la asignación a nivel de módulo.

### D4. Split español/inglés sin frontera explícita
CLI/español ↔ internals/inglés es una decisión válida, pero el mapeo vive en un solo dict
(`TIPOS_REDES`) y los nombres de red interna se comparan por string en cadenas if/elif
(`main.py:366-377`, `440-467`). Frágil: agregar una red toca varios lugares.
**Dirección:** centralizar el registro de tipos de red (clave CLI → método de creación →
método de extracción) en una estructura de datos única.

### D5. Drift de esquema entre `models.py` y `analisis/agente_navegacion_grafo.py`
El docstring de esquema en `agente_navegacion_grafo.py:7-37` declara `Institution` con
`address` y una relación `Paper -[:CITED_BY]-> Paper`, ninguna de las cuales existe en
`models.py` (Institution solo tiene `name`; la relación es `CITED`). Un agente que confíe en
ese docstring generará Cypher inválido.
**Dirección:** generar/derivar la doc de esquema desde `models.py` (fuente única), o al menos
corregir el docstring y marcar `models.py` como autoritativo. **Doc-only, lo puede tomar el
arquitecto.**

### D6. Artefactos de runtime versionados / sueltos en la raíz
`bibliometria.log` (~55 MB) está en el árbol de trabajo, junto a `findings.md`, `logs/`,
`resultados/`, `dist/`. Ruido que conviene limpiar antes del refactor (revisar `.gitignore`).
**Dirección:** confirmar qué está trackeado y mover/ignorar artefactos generados.

---

## E. Mejoras de robustez (ancladas en gotchas reales)

### E1. Enriquecimiento sin checkpoint
`enrich_all_papers` (`enriquecimiento.py:313`) re-procesa todos los papers desde cero tras una
falla. Es idempotente (get-or-create) pero costoso a ~0.25 RPS — con cientos de papers son horas.
**Dirección:** marcar papers ya enriquecidos (flag o timestamp) y saltarlos al reanudar.

### E2. Encoding Unicode en Windows
Sin `PYTHONIOENCODING=utf-8`, `enriquecer` crashea en consolas `cp1252` (documentado en
README y CLAUDE.md). Hay un workaround puntual (`title_safe = ...encode('ascii', 'replace')`,
`enriquecimiento.py:301`) pero los `print` de otros métodos no están protegidos.
**Dirección:** forzar UTF-8 en el arranque o reemplazar `print` por logging configurado.

### E3. `print` vs `logging` mezclados
La clase enriquecedora usa `print` (`enriquecimiento.py:130,224,261,...`) mientras el resto del
paquete usa `logging`. Inconsistente para diagnóstico.
**Dirección:** unificar en `logging`.

### E4. Manejo de rate limit primitivo
429 hace `time.sleep(60)` y **descarta** ese paper (`enriquecimiento.py:133-136`) en vez de
reintentar. Combinado con E1, esos papers quedan sin enriquecer hasta una corrida completa nueva.
**Dirección:** reintento con backoff que no pierda el paper.

---

## Secuencia sugerida para el refactor

1. **Higiene de seguridad primero:** B1 (rotar key), B2 (credenciales). No tocar nada más
   hasta cerrar esto.
2. **Red de seguridad:** D1 (tests de caracterización de piezas puras).
3. **Bugs latentes:** A1–A5.
4. **Decisiones de producto con el PO:** C1/C2 (CrossRef/Scopus dentro o fuera), B3 (`.env`),
   C3 (csv/json). Estas reabren el alcance — necesitan registro de decisión.
5. **Reestructuración:** D2–D4 (romper el monolito, centralizar config y el registro de redes).
6. **Robustez:** E1–E4.
7. **Doc-only en paralelo (arquitecto):** D5 (drift de esquema), D6 (limpieza de artefactos).
