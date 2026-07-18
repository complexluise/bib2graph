# 0047 — Frontera de alcance de bib2graph: el motor termina en la lectura; lo demás es otra herramienta

- **Estado:** Aceptada
- **Fecha:** 2026-07-18
- **Decidido por:** mixto. La **frontera de alcance** (dónde termina bib2graph a propósito) y el
  **principio de diseño** ("si es muy distinto, se construye al lado, no adentro") son **decisión del
  Product Owner humano**. El **encuadre de tres capas** (mecanismo / política / amplificación) y la
  **redacción de la frase-ancla** son **síntesis de la IA (arquitecto) validada por el PO**.
- **Gradúa la [Nota 22](../Notas/22-frontera-y-alcance-de-bib2graph.md)** ("Frontera y alcance de
  bib2graph", 2026-06-28). La Nota 22 es la versión que **habla al usuario** (transparencia sobre
  dónde se detiene la herramienta); este ADR es la versión que **habla a quien decide el código**:
  fija la misma frontera como **decisión canónica** para gobernar qué se construye adentro, qué se
  corta y qué se mueve. La Nota 22 queda como texto de cara al usuario; este ADR es su forma
  normativa. (Es exactamente el "graduar a ADR" que la propia nota anticipa en su encabezado.)
- **Relacionada con:** [0022](0022-producto-sin-ia-generativa.md) (**el motor no usa IA generativa**:
  este ADR lo generaliza de "no IA" a la frontera de alcance completa, sin tocar ni relajar 0022, que
  queda literal e intacto porque bib2graph **es** el motor), [0028](0028-arquitectura-gui-api-capa-servicios.md)
  (la **capa `service/` neutral** + los reads se **conservan** —enmienda de [0040](0040-retiro-gui-local.md)—:
  son la costura técnica por la que un producto externo consume la salida limpia sin acoplarse al
  motor), [0021](0021-cli-agente-native-contrato.md) (el **contrato** —envelope `schema="1"`, exit
  codes, FSM— es la superficie versionada que hace la salida encadenable),
  [0010](0010-agente-native-columna.md) (la CLI agente-native como columna primaria: las **skills** —la
  capa de política— orquestan las primitivas sin meter juicio en el motor),
  [0037](0037-superficie-cli-10-verbos-ciclo.md)/[0038](0038-destino-verbos-huerfanos-0037.md) (la
  **superficie de 10 verbos** del ciclo; la frase-ancla de este ADR es el criterio contra el que se
  audita esa superficie). No introduce IA (coherente con 0022).
- **Origen / secuencia de flujo:** fase DECIDIR — la frontera ya cuajó con el PO en la Nota 22; este
  ADR la **registra en el repo**. Ancla el **Bloque D del release 0.12.0** (poda + frontera fusionados):
  provee el criterio de la **auditoría de superficie ([#196](https://github.com/complexluise/bib2graph/issues/196))**
  y justifica los **cortes de la poda ([#207](https://github.com/complexluise/bib2graph/issues/207))**.

## Contexto

bib2graph es software libre (GPL-3.0) y, cada vez que crece, aparece la tentación de absorber más del
ciclo de investigación: gestionar una biblioteca a través de proyectos, interpretar las tensiones de
un campo, asistir la escritura. La Nota 22 (2026-06-28) fijó, de cara al usuario, **dónde se detiene la
herramienta a propósito** y **por qué**. Esa frontera ya está decidida con el PO, pero vivía solo como
nota-al-usuario; no había un ADR normativo que la volviera criterio de diseño para el código.

Al mismo tiempo, el **Bloque D del 0.12.0** fusiona dos trabajos —la **auditoría de superficie**
(#196) y la **poda** (#207)— que necesitan un **criterio explícito y citable** para decidir, comando por
comando y flag por flag, qué se mantiene, qué se corta y qué se mueve afuera. Sin una frontera
registrada como decisión, esos cortes serían opinión; con ella, son aplicación de un principio.

Hay además una tensión de fondo que conviene resolver por escrito: existe un **producto comercial** de
sostaina (aún sin nombre público en la Nota 22) que **sí** amplifica el trabajo con IA. La pregunta que
este ADR cierra no es "qué es el producto", sino **"¿qué NO es bib2graph, y por qué eso lo hace más
confiable, no más pobre?"**. La frontera se define de forma **intrínseca** —desde lo que el motor es—,
no por referencia a un producto externo del que el motor no debe depender.

## Decisión

Se registra como decisión canónica la **frontera de alcance de bib2graph**, articulada en tres partes.

### 1. La frase-ancla (intrínseca, es el corazón del ADR)

> **bib2graph convierte una búsqueda en un corpus, redes de citación y un orden de lectura priorizado
> —deterministas, reproducibles y con procedencia—. Te lleva hasta la lectura y se detiene ahí: no
> interpreta, no gestiona tu investigación ni usa IA; el juicio queda tuyo.**

Es la frontera **intrínseca**: describe qué es y dónde termina bib2graph **sin nombrar ningún producto
externo**. Esto es deliberado: el motor **no depende** de que exista algo aguas abajo. Sirve tal cual
esté solo, encadenado con herramientas de terceros, o alimentando un producto propio. La frase es el
**criterio operativo** contra el que se decide cada comando/flag en la auditoría de frontera (#196).

### 2. Las tres capas (encuadre)

La frontera separa tres capas con responsabilidades distintas que **no se mezclan**:

1. **bib2graph = el mecanismo.** Motor **determinista, reproducible, mono-usuario, local, sin IA**.
   Convierte una búsqueda en estructura navegable (corpus + redes + orden de lectura) con procedencia.
   Su constitución —determinista, sin IA, sin juicio— es la de un instrumento, no la de un asistente.
2. **Skills / agentes = la política.** El **método** aplicado **sobre** las primitivas del motor
   (orquestar el ciclo, encadenar verbos, aplicar un protocolo de forrajeo). La política vive **afuera**
   del motor y lo consume; no le inyecta juicio ni estado propio.
3. **El producto = la amplificación.** La **IA asiste, el humano cura, la procedencia es explícita**.
   Es donde ocurre la interpretación asistida. Vive en otra herramienta, aguas abajo, consumiendo la
   salida limpia y versionada del motor.

### 3. El principio de diseño (fractal)

> Si una funcionalidad es muy distinta de *"convertir una búsqueda en estructura navegable"* —aunque
> sea una parte legítima del ciclo de investigación— **no entra en bib2graph: se construye al lado,
> como otra herramienta**.

La frontera **no se ensancha** para acomodar lo nuevo; lo nuevo se construye afuera y, si hace falta, se
conecta consumiendo la salida del motor. El principio es **fractal**: la misma disciplina que separa
bib2graph del producto separa después módulo de módulo dentro del código, y esta decisión (para el
código) de la Nota 22 (para el usuario).

### Corolario: el caso difícil (diff / blindspots) queda resuelto

Cuando una función parece pisar la línea (p. ej. el **diff entre corpus / detección de blindspots**), la
regla es: **bib2graph COMPUTA el dato, el producto lo INTERPRETA.** El motor puede calcular, como
**función pura con procedencia**, qué papers entraron o salieron entre dos corridas, o qué zonas de la
red quedaron poco cubiertas. Eso es cómputo determinista y auditable, y **cae dentro** de la frontera.
Lo que **no** hace el motor es decir qué significa esa diferencia, si importa, o qué deberías leer por
eso: esa lectura es interpretación, y vive en el producto. **El cómputo abierto no debilita el
producto**; le entrega materia prima honesta sobre la que amplificar.

## Consecuencias

- **Este ADR provee el criterio de la auditoría de frontera (#196) y justifica los cortes de la poda
  (#207).** La frase-ancla se vuelve la pregunta única contra la que se clasifica cada comando/flag del
  Bloque D del 0.12.0: **se mantiene** (encaja en "convertir una búsqueda en estructura navegable"), **se
  corta** (no encaja y no aporta al mecanismo), o **se mueve** (es trabajo real pero de otra capa). Sin
  este ADR, los cortes de #207 serían opinión; con él, son aplicación de un principio registrado.
- **[0022](0022-producto-sin-ia-generativa.md) queda intacto y literal.** Este ADR **no** lo relaja ni
  lo enmienda: lo **subsume** en una frontera más amplia. "No usa IA" pasa de ser una regla aislada a ser
  **una** de las tres exclusiones (no interpreta / no gestiona / no usa IA) que definen el borde. El
  motor sigue sin IA generativa, por las mismas razones (reproducibilidad, honestidad reportable).
- **La costura técnica ya existe y se conserva.** La capa **`service/` neutral** + los reads
  ([0028](0028-arquitectura-gui-api-capa-servicios.md), conservados por
  [0040](0040-retiro-gui-local.md)) y el **envelope `schema="1"`** del contrato CLI
  ([0021](0021-cli-agente-native-contrato.md)) son exactamente el punto por donde un producto externo
  consume la salida limpia **sin acoplarse** al motor. La frontera no exige código nuevo: **ratifica** una
  arquitectura ya construida.
- **La salida sigue siendo encadenable.** Al no absorber interpretación ni gestión, bib2graph mantiene su
  salida abierta, versionada y auditable; cualquiera —la política (skills), un producto propio, o
  herramientas de terceros— puede construir encima sin negociar con el motor.
- **Costo aceptado:** bib2graph **no acompaña el ciclo completo** a propósito. Un usuario que quiera
  interpretación asistida, gestión de biblioteca a través de proyectos, o ayuda a la escritura, **no** la
  encuentra en el motor; la encuentra (si existe) en otra herramienta. Es el precio de "una cosa bien
  hecha", y es deliberado: una herramienta que se limita a propósito es una en la que se puede confiar y
  que se puede reportar con honestidad.
- **Regla para futuras propuestas.** Toda propuesta de feature se evalúa primero contra la frase-ancla.
  Si cae del lado de interpretar / gestionar / usar IA, la respuesta por defecto es **"al lado, no
  adentro"**, salvo ADR que revierta esta frontera. Reabrir la frontera **exige un ADR nuevo** que
  supersede a este; no se ensancha por conveniencia de un ticket.

## Alternativas

- **Dejar la frontera solo como Nota 22 (statu quo).** **Rechazada:** una nota-al-usuario no es criterio
  normativo para el código. La auditoría #196 y la poda #207 necesitan un ADR **citable** que respalde
  los cortes; sin él, cada corte se re-discute como opinión y la frontera se erosiona ticket a ticket.
- **Definir la frontera por referencia al producto ("bib2graph es todo lo que el producto no hace").**
  **Rechazada:** ataría el motor a algo externo y variable, y filtraría *naming* comercial a un ADR de
  un proyecto open source. La frontera **intrínseca** (frase-ancla) es más fuerte: el motor se sostiene
  solo, con o sin producto aguas abajo. Por eso este ADR **no** fija el nombre del producto.
- **Ampliar bib2graph para cubrir más del ciclo (interpretación / gestión de biblioteca / escritura
  asistida).** **Rechazada:** mezclar esas capas adentro degradaría lo único que el motor promete ser
  —determinista, reproducible, auditable— y rompería [0022](0022-producto-sin-ia-generativa.md). "Suite
  que hace de todo a medias" es justo lo que la frontera evita.
- **Prohibir en bib2graph todo cómputo que el producto podría interpretar (p. ej. el diff/blindspots),
  por miedo a pisar la línea o a "regalar" valor.** **Rechazada:** confunde **computar** con
  **interpretar**. El motor puede y debe computar el dato como función pura con procedencia; la
  interpretación es lo que queda afuera. El cómputo abierto no compite con el producto: lo alimenta.
