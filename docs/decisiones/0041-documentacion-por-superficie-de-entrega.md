# 0041 — Organizar la documentación por superficie de entrega (no por tipo de lector): dos superficies + un mediador

- **Estado:** Aceptada
- **Fecha:** 2026-06-29
- **Decidido por:** **Product Owner humano** (decisión acordada 2026-06-29). Las decisiones
  concretas —**no** forkear el sitio mkdocs por audiencia y mantener Diátaxis; publicar un
  **`llms.txt`** en la raíz del sitio como puerta para IA externa; usar la persona como **veneer de
  navegación** (tres puertas por intención hacia un mismo cuerpo); y **subir `AGENTS.md` al nav**—
  son **decisiones del PO**. El **encuadre** —*"la documentación se organiza por **superficie de
  entrega**, no por tipo de lector: los tres usuarios no son tres árboles de documentación, son **dos
  superficies + un mediador**; y la experiencia del **agente que opera bib2graph** (Claude / ChatGPT
  / Minimax, con herramientas + Python) es un objetivo de **primera clase** de la documentación, no un
  subproducto"*— es **síntesis de la IA (architect) validada por el PO**.
- **Relacionada con:** [0039](0039-skill-comando-meta-distribucion.md) (la skill de Claude Code es la
  **doc operativa** del humano no-técnico mediada por IA; vive **vendoreada en el wheel**, no en el
  sitio — este ADR la nombra como **pieza del ecosistema**, no como sección de mkdocs),
  [0010](0010-agente-native-columna.md)/[0021](0021-cli-agente-native-contrato.md) (CLI
  agente-native: la superficie machine-legible del sitio —Referencia + `llms.txt`— **publica** el
  mismo contrato que el CLI expone),
  [0037](0037-superficie-cli-10-verbos-ciclo.md)/[0038](0038-destino-verbos-huerfanos-0037.md) (los
  10 verbos del ciclo son lo que la Referencia del CLI autogenerada y el `llms.txt` deben enseñar,
  exactos a la versión publicada),
  [0040](0040-retiro-gui-local.md) (tras el retiro de la GUI la **única frontera** es la CLI
  agente-native; este ADR alinea la documentación con esa frontera).
- **No introduce IA** (coherente con [0022](0022-producto-sin-ia-generativa.md)): es **organización
  de documentación**. `llms.txt` es un artefacto **markdown** que una IA cliente lee; bib2graph no
  embebe ni invoca ningún modelo. El alcance de este ADR es la **documentación del motor
  determinista**, no un producto.
- **No cambia ningún contrato público.** No toca el envelope `schema="1"`, los exit codes ni el FSM
  ([0021](0021-cli-agente-native-contrato.md)); no altera `docs/API.md` como contrato (lo **publica**
  mejor). Es net-new: ningún ADR gobernaba hasta hoy la **estructura de la documentación**.
- **Origen:** la frontera bib2graph (motor determinista) vs. producto, y la constatación de que
  bib2graph lo consumen cada vez más **agentes con herramientas y Python** (Claude Code, ChatGPT,
  Minimax) además de humanos.

## Contexto

bib2graph lo consumen hoy tres clases de usuario:

1. Un **humano no-técnico** que interactúa **vía un asistente de IA** (le pide a su agente que use
   bib2graph; no escribe comandos a mano).
2. **Una IA que opera el repo o el paquete** (Claude Code dentro del clon; ChatGPT / Minimax fuera de
   él, ayudando a alguien que hizo `pip install`).
3. Un **desarrollador** que contribuye a la librería.

La tentación natural es mapear estos tres usuarios a **tres árboles de documentación** —forkear el
sitio mkdocs en caminos por audiencia—. Eso **duplicaría contenido** (el mismo quickstart contado
tres veces) y generaría **drift**: justo lo que el sitio ya combate con `include-markdown` y fuente
única (`mkdocs.yml` reusa `API.md`, `ARCHITECTURE.md`, los ADRs y los `.md` de raíz; no copia).

El error del mapeo "un lector = un árbol" es confundir **lector** con **superficie de entrega** —el
canal físico por donde la documentación llega—. Tres lectores no implican tres cuerpos de
documentación; implican distintas **puertas** al **mismo** cuerpo. Cuando se separan las superficies
reales, los tres lectores colapsan en **dos superficies + un mediador**:

- **Agente DENTRO del repo** (p. ej. Claude Code): lee **`AGENTS.md` y el código fuente**, **no** el
  sitio renderizado. mkdocs **no le sirve** a este lector — ya tiene el árbol de archivos. Su puerta
  es `AGENTS.md` (canónica, puertas adentro).
- **Agente FUERA del repo** (p. ej. ChatGPT / Minimax ayudando a alguien que hizo `pip install` y
  **no** clona el repo, pero tiene **herramientas + Python**): necesita una **puerta publicada y
  machine-legible**. **Hoy ese es el hueco real**: no hay un punto de entrada estable, pensado para
  una IA, en el sitio público.
- **Humano navegando**: ese sí es el público del **sitio mkdocs**. El desarrollador es un humano
  navegando con una intención distinta (contribuir), no una tercera superficie.

El sitio ya es **Diátaxis** (Empezar/Tutoriales/Guías/Referencia/Explicación, ver `mkdocs.yml`
`nav:`). Diátaxis sirve **a la vez** al humano y a la IA: la sección **Referencia** es por naturaleza
machine-grade (la API de Python por `mkdocstrings`, el CLI por `mkdocs-click`, los contratos en
`API.md`). El problema no es la estructura del sitio; es **la falta de una puerta para la IA externa**
y el riesgo de forkearlo por audiencia.

## Decisión

**La documentación de bib2graph se organiza por superficie de entrega: dos superficies (agente dentro
del repo / humano-y-agente navegando el sitio) más un mediador (la puerta machine-legible para la IA
externa). NO se forkea el sitio por audiencia; las tres intenciones de uso entran por puertas de
navegación distintas a un mismo cuerpo Diátaxis.** La **experiencia del agente que opera bib2graph**
(Claude / ChatGPT / Minimax, con herramientas + Python) es un **objetivo de primera clase** de la
documentación.

### (1) Mantener Diátaxis; no forkear el sitio por audiencia

La estructura del sitio (Empezar / Tutoriales / Guías / Referencia / Explicación) se **conserva**.
Sirve al humano y a la IA a la vez; la **Referencia** es la cara machine-grade y se mantiene
autogenerada (mkdocstrings + mkdocs-click) para que no derive de la verdad del código. **No** se crea
un árbol "para IA" ni un árbol "para devs" paralelos: sería el quickstart contado tres veces y drift
garantizado. Un edificio, no tres edificios.

### (2) Publicar `llms.txt` en la raíz del sitio — la puerta de la IA externa

Se agrega un **`llms.txt`** en la raíz del sitio publicado (`/llms.txt`), siguiendo el estándar
emergente [llmstxt.org](https://llmstxt.org), con un **`llms-full.txt`** opcional para el volcado
extendido. Es la **versión pública** de lo que `AGENTS.md` hace puertas adentro: un mapa conciso,
machine-legible, de qué es bib2graph, cómo se instala, cuál es el ciclo (los 10 verbos del 0037) y
dónde está la Referencia. Cierra el hueco del **agente FUERA del repo**: un ChatGPT / Minimax con
acceso a la web y a Python puede leer `/llms.txt`, entender la superficie y operar el CLI sin clonar.

**Debe ser derivado, no escrito a mano**: su fuente natural es `AGENTS.md` + la referencia del CLI
autogenerada (mkdocs-click); generarlo en el build evita el drift que un `llms.txt` redactado a mano
reintroduciría. *(El **cómo** generarlo —script/plugin en el pipeline de `mkdocs build`— es trabajo
del `coder`; este ADR fija que existe, dónde vive y de qué se deriva, no la implementación.)*

### (3) La persona como veneer de navegación, no como fork de contenido

En `docs/index.md` se ofrecen **tres puertas de entrada por intención** que **enrutan al mismo cuerpo
Diátaxis**:

- **(a) "Quiero explorar literatura"** → Empezar / Tutoriales / Guías.
- **(b) "Soy una IA y voy a operar bib2graph"** → `llms.txt` + Referencia (CLI/API) + `AGENTS.md`.
- **(c) "Quiero contribuir"** → Contribuir / Arquitectura / ADRs.

**Tres puertas, un edificio.** La persona vive en la **navegación** (un veneer de enrutamiento), no
en el **contenido** (que sigue siendo único). Ningún cuerpo de texto se duplica: las puertas son
enlaces a las secciones que ya existen.

### (4) Subir `AGENTS.md` al nav del sitio — la bisagra entre superficies

`AGENTS.md` hoy **no aparece** en el nav (`mkdocs.yml` lo excluye implícitamente; solo lo ven los
agentes dentro del repo). Se **sube al nav** como **bisagra explícita** entre superficies:
enlazable y citable desde el sitio, vía el mismo patrón `include-markdown` que ya usa
`docs/contributing.md` para `CONTRIBUTING.md` (un shim fino que incluye `../AGENTS.md`). Así la
puerta (b) tiene un destino navegable y el `llms.txt` un ancla pública, sin duplicar la verdad de
`AGENTS.md`.

### El objetivo de primera clase: cómo operar bib2graph desde una IA

Este ADR fija como **objetivo de diseño** que un agente con herramientas + Python pueda operar
bib2graph leyendo la documentación. Las dos rutas, explícitas:

- **Agente DENTRO del repo** (Claude Code) → lee `AGENTS.md` + el código. Ya cubierto; el sitio no le
  agrega nada.
- **Agente FUERA del repo** (ChatGPT / Minimax, tras `pip install bib2graph`) → lee **`/llms.txt`** en
  el sitio + la **Referencia del CLI** publicada (los 10 verbos del 0037, exactos a la versión) y
  corre el ciclo `init→seed→chain→build→read` leyendo `status` como mapa.

La **skill de bib2graph** ([ADR 0039](0039-skill-comando-meta-distribucion.md)) es la **doc operativa
del humano no-técnico mediada por IA**: vive **vendoreada en el wheel** y se instala con `b2g skill
add`, **no** es una sección del sitio. Es **pieza del ecosistema** de documentación —complementa este
ADR— pero su superficie de entrega es el wheel, no mkdocs.

## Consecuencias

**Lo que se gana**

- **Una sola fuente de verdad con puertas por intención.** Se evita el fork por audiencia y el
  quickstart triplicado; el sitio sigue siendo el cuerpo único que `include-markdown` ya garantiza.
- **Se cierra el hueco de la IA externa.** `llms.txt` da a un agente fuera del repo una puerta
  estable y machine-legible; deja de depender de "que el modelo adivine" navegando HTML pensado para
  humanos.
- **La experiencia del agente queda como objetivo declarado, no accidental.** Las dos rutas
  (dentro/fuera del repo) están nombradas; la documentación se diseña para que un agente opere el
  CLI, no solo para que un humano lea.
- **`AGENTS.md` deja de ser invisible en el sitio.** Pasa a ser bisagra citable entre superficies,
  reusando el patrón de shim que ya existe — sin duplicar contenido.

**Lo que cuesta**

- **Mantener `llms.txt` sincronizado.** Es el costo central: un `llms.txt` que enseña verbos que ya
  no existen **miente** (mismo riesgo que el 0039 cerró para la skill con el version-lock). Mitigación
  obligatoria: **generarlo** del `AGENTS.md` + la referencia del CLI en el build, no a mano. Un
  `llms.txt` escrito a mano es drift diferido.
- **Tocar el `nav` y el pipeline de build.** Subir `AGENTS.md` al nav (shim + entrada en `mkdocs.yml`)
  y generar `llms.txt` en `mkdocs build` son cambios de **config/build** → trabajo del `coder`; este
  ADR los **recomienda y encuadra**, no los implementa.
- **`docs/index.md` gana las tres puertas por intención.** Es trabajo de redacción (documental), no
  de duplicación: las puertas enlazan a secciones existentes.
- **Convención de doc nueva que vigilar.** "Superficie de entrega, no tipo de lector" hay que
  sostenerla en cada incorporación: la tentación de forkear por audiencia volverá; este ADR es el
  ancla para rechazarla.

## Alternativas

- **Forkear el sitio mkdocs en tres caminos por audiencia** (humano / IA / dev). **Descartada:**
  triplica el contenido (mismo quickstart tres veces), reintroduce el drift que `include-markdown` y
  la fuente única combaten, y confunde **lector** con **superficie de entrega**. Tres lectores no son
  tres edificios; son tres puertas al mismo edificio.
- **Abandonar Diátaxis por una estructura "agents-first" propia.** **Descartada:** Diátaxis ya sirve a
  humano e IA a la vez —la Referencia es machine-grade por construcción— y es un estándar reconocible.
  Reinventar la estructura perdería esa legibilidad sin resolver el hueco real (la puerta para IA
  externa), que `llms.txt` cubre sin tocar la estructura.
- **No publicar `llms.txt`; confiar en que la IA externa navegue el HTML.** **Descartada:** deja el
  hueco abierto. Un sitio HTML pensado para humanos es un mal punto de entrada para un agente sin
  contexto; `llms.txt` es el estándar emergente justamente para esto y es **derivable** de fuentes que
  ya mantenemos.
- **Escribir `llms.txt` a mano.** **Descartada:** reintroduce el drift que todo el sitio combate (un
  `llms.txt` que enseña una superficie vieja miente, igual que una skill desfasada en el 0039). Debe
  **generarse** de `AGENTS.md` + la referencia del CLI; si hoy no hay generador, el `coder` lo
  construye antes de publicarlo.
- **Documentar la operación-por-IA solo en la skill (0039) y no en el sitio.** **Descartada:** la
  skill cubre al **humano no-técnico con Claude Code**; **no** cubre al agente externo (ChatGPT /
  Minimax) ni a quien no instala la skill. La puerta pública del sitio (`llms.txt` + Referencia) y la
  skill son **complementarias**, no sustitutas: distintas superficies de entrega del mismo motor.
