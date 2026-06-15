# Declaración de uso de IA y estado experimental

## Estado: experimental (alpha)

bib2graph está en desarrollo activo y se considera **experimental**. Mientras la versión
mayor sea `0` (`0.y.z`), la API pública —lo declarado en [`docs/API.md`](docs/API.md)— es
**inestable**: cualquier release `MINOR` puede introducir cambios incompatibles (ver
[`VERSIONING.md`](VERSIONING.md)). No la uses todavía como dependencia estable en producción.

## Cómo se construye: AI-in-the-loop (humano en el lazo)

Este proyecto se desarrolla con un proceso explícito de **inteligencia artificial en el lazo,
con dirección y revisión humana**:

- **La persona (Product Owner)** plantea el problema, fija el alcance, toma las decisiones de
  diseño y **revisa y aprueba** cada cambio. La responsabilidad final es humana.
- **Los asistentes de IA** (modelos de código) implementan el código, los tests y la
  documentación bajo esa dirección, y proponen opciones cuando hay una decisión que tomar.
- **Trazabilidad:** las decisiones de arquitectura se registran como [ADRs](docs/decisiones/);
  las decisiones que tomó la IA durante la construcción quedan en
  [`registro-ia.md`](docs/decisiones/registro-ia.md); el flujo de cambio (encuadre →
  implementación → revisión adversarial → sincronía de docs) está en
  [`CONTRIBUTING.md`](CONTRIBUTING.md).

### Dos sentidos de "AI in the loop"

Conviene no confundirlos, porque ambos están presentes a propósito:

1. **Desarrollo asistido por IA** — el *código* de la librería se escribe con asistencia de IA
   (este documento).
2. **IA en el producto** — la *librería* usa IA y heurísticas en el lazo de exploración
   bibliográfica: el forrajeo rankea candidatos por *information scent* y la curación es
   asistida (la persona acepta/rechaza). Ver el [PRD](docs/PRD.md) y el método de forrajeo
   ([ADR 0020](docs/decisiones/0020-metodo-forrajeo-scent-filtros-reject.md)).

## Qué implica para vos

- **Verificá las salidas.** La reproducibilidad es un objetivo de diseño (cada
  `CorpusSnapshot` lleva su manifiesto con versiones de lib, schema y fuente), pero la validez
  científica de un análisis es responsabilidad de quien lo corre.
- **Esperá cambios.** Los breaking changes son bienvenidos si simplifican el diseño, mientras
  estén justificados en un ADR y marcados `BREAKING:` en el commit.
- **Reportá problemas.** Issues y feedback son muy bienvenidos en esta etapa.

## Licencia

MIT — ver [`LICENSE`](LICENSE). El software se entrega "tal cual", sin garantías de ningún
tipo, según los términos de la licencia.
