# Declaración de uso de IA y estado experimental

## Estado: experimental (alpha)

bib2graph está en desarrollo activo y es **experimental**. Mientras la versión mayor sea `0`,
la API pública es **inestable**: cualquier release menor puede traer cambios incompatibles
(ver [`VERSIONING.md`](VERSIONING.md)). No la uses todavía como dependencia estable en producción.

## Cómo se construye: con la IA en el lazo, bajo dirección humana

bib2graph se desarrolla con un proceso explícito de **IA asistida, con dirección y revisión humana**:

- **La persona (Product Owner)** plantea el problema, fija el alcance, toma las decisiones de
  diseño y **revisa y aprueba cada cambio**. La responsabilidad final es humana.
- **Los asistentes de IA** implementan el código, los tests y la documentación bajo esa
  dirección, y proponen opciones cuando hay que decidir.
- **Trazabilidad:** las decisiones de diseño y las que tomó la IA durante la construcción quedan
  registradas en el repositorio (`docs/decisiones/`), y el flujo de cambio está en
  [`CONTRIBUTING.md`](CONTRIBUTING.md).

## El producto no usa IA generativa

La IA asiste el **desarrollo** de la librería, no su funcionamiento. El producto en sí **no usa
IA generativa**:

- El **ranking del forrajeo** (qué candidatos sugerir al expandir el corpus) es **estructura
  bibliométrica** —acoplamiento, co-citación, centralidad del candidato respecto del corpus
  curado—: **determinista y reproducible, sin LLM ni embeddings**. Es estructura, no IA.
- La **curación** es una decisión **100% humana**: la persona acepta o rechaza, sin un modelo
  en el medio.
- El **análisis** (leer las redes: quién apoya o refuta a quién) lo hace quien investiga, no un
  modelo.

El diferenciador no es "más IA": es una biblioteca de literatura **curada, abierta y
reproducible** que el investigador posee.

## Qué implica para vos

- **Verificá las salidas.** La reproducibilidad es un objetivo de diseño (cada snapshot lleva
  su manifiesto con versiones de librería, schema y fuente), pero la validez científica de un
  análisis es responsabilidad de quien lo corre.
- **Esperá cambios.** Mientras estemos en `0.x`, la API puede cambiar entre releases menores.
- **Reportá problemas.** Issues y feedback son muy bienvenidos en esta etapa.

## Licencia

**GNU General Public License v3.0 o posterior (GPL-3.0-or-later)** — ver [`LICENSE`](LICENSE).
Es **copyleft fuerte**: cualquiera puede usar, estudiar, modificar y redistribuir bib2graph,
pero **todo trabajo derivado que se distribuya debe seguir siendo libre y con el código fuente
abierto bajo la misma licencia**. Así queda garantizado que la herramienta siga siendo de la
comunidad y no pueda capturarse en un producto propietario cerrado. El software se entrega
"tal cual", sin garantías de ningún tipo, según los términos de la licencia.
