# 22 — Frontera y alcance de bib2graph (nota de separación)

> Qué es bib2graph y dónde se detiene **a propósito**. Esta nota existe para ser transparentes con
> quien la usa: dejar la frontera escrita, sin letra chica. Es la versión que habla al usuario; la
> decisión, una vez asentada, se gradúa a un ADR que habla a quien decide el código. Fecha: 2026-06-28.

---

> **bib2graph convierte una búsqueda en un corpus, redes de citación y un orden de lectura priorizado —deterministas, reproducibles y con procedencia—. Te lleva hasta la lectura y se detiene ahí: no interpreta, no gestiona tu investigación ni usa IA; el juicio queda tuyo.**

---

## Qué es

bib2graph hace **una** cosa, y la hace bien: toma una búsqueda —una ecuación sobre OpenAlex o un archivo `.bib`— y la transforma en material estructurado para empezar a leer con criterio. Concretamente, te entrega:

- **Un corpus** que crece siguiendo las citaciones (forward y backward chaining) y que **curás vos** —aceptar, rechazar, filtrar—.
- **Redes de citación** (acoplamiento, co-citación, co-autoría, instituciones, co-keywords), listas para Gephi, Cytoscape o networkx.
- **Un orden de lectura priorizado**: qué leer primero, según cuánto se acopla, co-cita o es central cada pieza dentro de tu corpus.
- **Procedencia** de todo: la cadena de búsqueda exacta, la fecha, los topes, la versión — para reconstruir y reportar cómo llegaste a lo que llegaste.

Tres propiedades lo definen, y ninguna es decorativa:

- **Determinista** — mismo input, mismo output. No hay azar ni modelo opaco en el medio.
- **Reproducible** — cualquiera puede correr lo mismo y obtener lo mismo. Eso lo vuelve defendible ante un revisor.
- **Con procedencia** — cómo lo hallaste viaja pegado al resultado. No hay magia que no puedas auditar.

## Qué no es (y por qué, a propósito)

Tan importante como lo que hace es lo que **elige no hacer**:

- **No interpreta.** No te dice qué significan los clusters, no decide qué deberías citar, no escribe tu estado del arte. Te muestra la estructura; el sentido lo construís vos leyendo.
- **No gestiona tu investigación.** No tiene usuarios, ni proyectos, ni colecciones, ni anotaciones. No es un Zotero ni un Mendeley. Administra **un** corpus reproducible, no tu biblioteca a través de toda tu carrera.
- **No usa IA.** El descubrimiento es **estructura bibliométrica determinista** —acoplamiento, co-citación, centralidad—, no un modelo de lenguaje. Por eso es reproducible y reportable, y por eso no puede "alucinar" un paper que no existe.

Esto no son carencias: son **la frontera**. Una herramienta que se limita a propósito es una herramienta en la que podés confiar y que podés reportar con honestidad. El día que bib2graph empezara a decidir por vos —qué es relevante, qué significa, qué citar— dejaría de ser auditable y se volvería justo lo que la buena investigación debe evitar: una caja que disfraza una elección de autoridad.

## Por qué esta frontera

- **Una cosa bien hecha.** Es más útil un motor afilado y predecible que una suite que hace de todo a medias. Si querés encadenarlo con otras herramientas —tuyas, de terceros, o las que vengan— podés, porque su salida es limpia, abierta y versionada.
- **El juicio es tuyo, y eso es deliberado.** bib2graph asiste el trabajo *mecánico* —seguir citas a mano agota y se hace mal justo cuando estás cansado—. El trabajo *de criterio* —formular la pregunta, dejar que mute al leer, interpretar las tensiones, decidir qué entra— sigue siendo humano. La herramienta te lleva hasta la lectura; el trabajo de verdad, el de pensar, empieza ahí y es tuyo.
- **Honestidad reportable.** Una corrida de bib2graph **no es** una revisión sistemática PRISMA, y no pretende serlo. Es un barrido exploratorio, reproducible y documentado, que reduce el sesgo de empezar tu lectura solo por lo que ya recordabas. Reportarlo así —con modestia y con la procedencia a la vista— es más fuerte, no más débil.

## El principio de diseño: la frontera se sostiene sola

Esta nota no enumera una lista cerrada de exclusiones; declara un **principio**.

> Si una funcionalidad es muy distinta de *"convertir una búsqueda en estructura navegable"* —aunque sea una parte legítima del ciclo de investigación— **no entra en bib2graph: se construye al lado, como otra herramienta**.

La frontera no se ensancha para acomodar lo nuevo. Lo nuevo se construye afuera y, si hace falta, se conecta consumiendo la salida limpia y versionada de bib2graph. Gestionar una biblioteca a través de proyectos, interpretar las tensiones de un campo, asistir la escritura: son trabajo real y parte del ciclo, pero son **otras** cosas, y mezclarlas adentro degradaría lo único que bib2graph promete ser —un motor determinista y confiable—.

El principio es **fractal**: la misma disciplina que separa bib2graph de lo demás separa después módulo de módulo dentro del código, y esta nota (que habla al usuario) del ADR (que habla a quien decide el código). Trazar la línea con claridad, en cada nivel, es lo que mantiene cada pieza comprensible y confiable.

## Dónde encaja en tu ciclo

El ciclo de exploración bibliográfica es iterativo: sembrás, seguís citas, la pregunta muta, volvés a sembrar; después organizás, interpretás, escribís. bib2graph vive en el tramo del **forrajeo** —de la semilla a un corpus navegable con su orden de lectura— y se retira antes de la interpretación y la escritura. No te acompaña en todo el ciclo a propósito: hace bien su tramo y te entrega el material limpio para el tuyo. Lo que sigue —pensar, enmarcar, escribir— es tuyo, con tu juicio y con las herramientas que elijas.

---

*bib2graph es software libre (GPL-3.0). El código es la fuente de verdad; esta nota fija la intención.*
