# Proyecto 2: Fábrica de Apuntes UBA Derecho

Este proyecto es un sistema automatizado que procesa transcripciones crudas de clases y genera 2 archivos Markdown organizados y estructurados más un proceso de auditoría y carga automatizada a Notion.

## Perfil del Asistente Jurídico (Aplicar Siempre)
Este perfil está cargado en las reglas globales del agente (`.agents/AGENTS.md`) para asegurar consistencia en el tono formal-preciso argentino, el respeto de fuentes y la gestión de la incertidumbre.

---

## PROMPT 1 COMPLETO: FICHA + HANDOFF (Paso 1)
**Objetivo**: Transformar una transcripción cruda en una Ficha académica completa (con mapa de conceptos y tabla de alertas integrados) y un bloque HANDOFF estructurado para el Paso 2.

### Parámetros de entrada:
- Materia: [Nombre de la materia]
- Clase: [Número]
- Fecha: [DD-MM-YY]
- Tema: [Tema principal]
- Transcripción: [Texto crudo]

### Estructura de salida requerida:
```markdown
# 📄 PASO 1 — FICHA · Pegar en Notion: Ficha_[Materia]_Clase[N]_[DD-MM-YY]

## ⚡ MÓDULO 1 — PORTADA RÁPIDA

### 📌 BLOQUE A — ¿De qué va la clase?
* **Eje central:** [1-2 frases]
* **Marco normativo:** Artículos, fallos, doctrina.
* **⚖️ Fuente guía:** [El artículo o fallo que estructura la clase]

### 🎯 BLOQUE B — ¿Qué cae en examen?
* **⭐ Marcado por el profesor:** [Frase textual si hay]
* **🏆 Diferencias de 8+:** [Detalles técnicos o excepciones clave]
* **🚨 Alerta de examen:** [Pregunta típica, fuentes obligatorias]
* **📦 Trampa común:** Error típico y cómo evitarla.

## 🥇 MÓDULO 2 — CONCEPTOS DE ORO
[Máximo 4 conceptos. Formato por cada uno:]

**[O1] Concepto:** [Nombre]
* **Definición de cátedra:** [Definición con cita si hay]
* **Elementos esenciales:**
  1. [Primer elemento o requisito a memorizar como conjunto]
  2. [Segundo elemento o requisito]
  3. [Tercer elemento o requisito]
* **Función práctica:** [1 línea: para qué sirve este concepto en un caso real]
* **Fuente:** [Art/Fallo]
* **Consecuencias jurídicas:** ✅ Si se cumple... ❌ Si no se cumple...
* **Conexión:** [1 sola línea, formato flecha. Ej: "→ O3 (este concepto es la base normativa que O3 termina cristalizando)". Nunca un párrafo.]
* **Error frecuente:** [Qué confunde el estudiante entre este concepto y otro cercano]

Regla obligatoria de listas: El campo "Elementos esenciales" debe usar obligatoriamente numeración arábiga (1. 2. 3. 4.) para indicar la cantidad exacta de requisitos a memorizar como conjunto cerrado. Queda prohibido usar guiones o viñetas simples en Elementos esenciales.

Regla de selección de Conceptos de Oro: Un bloque temático califica como Concepto de Oro también cuando la docente le dedicó un tramo extenso y detallado de la clase (procedimientos, instituciones, pasos de un trámite, distinciones prácticas), aun si no está anclado a un artículo específico de una norma. La duración y el nivel de detalle dedicado en clase es señal de relevancia de examen tan válida como la existencia de una cita normativa. No relegar automáticamente a Concepto Satelital un bloque solo por carecer de artículo de código.

## 🛰️ CONCEPTOS SATELITALES
[Máximo 4. Texto (S1) o Tabla (S2) según corresponda]

## 🗺️ MÓDULO 3 — MAPA DE CONEXIONES (una sola vez, no repetir por concepto)
[Máximo 4-6 líneas en formato lista o diagrama de flechas mostrando el flujo entre O1→O2→O3→O4. Prohibido usar prosa en párrafo largo. Ejemplo de formato esperado:
O1 (etapa histórica) → produce → O2 (teoría del acto)
O2 → es superado por → O3 (art. 320 CCC)
O3 → se aplica mediante → O4 (categorías operativas)]

## 📋 MÓDULO 4 — TABLA DE ALERTAS DE EXAMEN
| Regla o idea central | Fuente (ley/clase/fallo) | Advertencia del profesor | Trampa típica de parcial/final |
| --- | --- | --- | --- |
[6-10 filas. Priorizar filas que ya correspondan a T1, T2, etc. del Handoff, no inventar filas nuevas sin base en la transcripción.]

## 🔗 HANDOFF PARA PASO 2
Materia: [Materia] · Clase: [N] · Fecha: [DD-MM-YY] · Tema: [Tema]
* **Conceptos Oro:** O1, O2...
* **Satelitales:** S1, S2...
* **Trampas detectadas:** T1, T2... (con ⚠️ automático)
* **Distinciones clave:** D1, D2...
* **Fuentes centrales:** A1, F1...

Generado con: [Modelo] · Modo: [Interactivo/Script]

✅ Paso 1 completo.
```

---

## PROMPT 2 COMPLETO: CUESTIONARIO + CASOS (Paso 2)
**Objetivo**: Basado EXCLUSIVAMENTE en la Ficha y el HANDOFF generados en el Paso 1, generar Cuestionario y Casos prácticos.

### Parámetros de entrada:
- Contenido del Paso 1 (Ficha y Handoff)

### Estructura de salida requerida:
```markdown
# 📄 PASO 2A — CUESTIONARIO · Pegar en Notion: Cuestionario_[Materia]_Clase[N]_[DD-MM-YY]
[Máximo 8 preguntas. Formato por cada una:]

❓ 1. [Texto] · fuente [X] · [Etiquetas: 🎯 Pareto, ⚠️ Trampa, 🏆 Cae siempre]
• [Explicación o respuesta si consta de un solo punto]
O bien (si consta de dos o más puntos):
(a) [Primer punto de la respuesta]
(b) [Segundo punto de la respuesta]
*❌ Error típico: [error real del HANDOFF]*

Regla de formato de respuestas (preguntas 1-8):
- Si la respuesta consta de un solo punto: usar viñeta simple (•).
- Si la respuesta consta de dos o más puntos: usar letras entre paréntesis (a) (b) (c). Prohibido usar numeración arábiga 1. 2. o guiones.

[Incluir tabla comparativa si hay distinciones D1/D2 en el Handoff]

❓ Integradora. [Enunciado: hechos concretos con nombres de personajes, situación fáctica completa] · 🏆 Cae siempre

Preguntas:
(a) [Pregunta 1, formulada como oración interrogativa completa]
(b) [Pregunta 2, formulada como oración interrogativa completa]
(c) [Pregunta 3 si existe, formulada como oración interrogativa completa]

► Intentá resolverlo antes de seguir.

**Resolución**
* (a) [Respuesta a la pregunta (a), 2-4 líneas]
* (b) [Respuesta a la pregunta (b), 2-4 líneas]
* (c) [Respuesta a la pregunta (c) si existe, 2-4 líneas]
* ⚠️ Error típico: [error que comete un alumno que memorizó pero no integró los conceptos]

Regla obligatoria: ninguna pregunta del Cuestionario, incluida la integradora, puede publicarse sin su resolución esperada. La integradora no es la excepción. El bloque "Preguntas:" de la pregunta integradora es de aparición forzosa y debe listar cada subpregunta (a)(b)(c) como oración interrogativa completa, en el mismo orden en que se responde en la Resolución. Prohibido saltar directo de los hechos a la Resolución sin mostrar las preguntas.

## 🎯 Top Pareto
| Prioridad | Pregunta | Concepto clave |
| --- | --- | --- |
[🔴 Crítico, 🟠 Alto]

## 📜 Fuentes clave
| Fuente | Qué establece | Por qué importa en examen |
| --- | --- | --- |

---

# 📄 PASO 2B — CASOS · Pegar en Notion: Casos_[Materia]_Clase[N]_[DD-MM-YY]
[3 Casos: Caso 1 (Simple O1/O2), Caso 2 (Trampa T1), Caso 3 (Complejo interclase o nivel intermedio)]

📌 **CASO [N] — [Título]**
* **Nivel:** [Simple/Trampa/Complejo]
* **Conceptos:** [O1, T1...]
* **⚖️ Fuentes:** [A1, F1...]
* **Enunciado:** [Hechos concretos. Personajes con nombres.]

► Intentá resolverlo antes de seguir.

**Resolución**
* **Figura jurídica en juego:** [1 línea]
* **Razonamiento:** [1, 2, 3...]
* **Respuesta:** [Máx 4 líneas]
* **⚠️ Error típico:** [T1 del Handoff]
* **Link:** Relacionado con: P[N] del cuestionario

Regla de complejidad del Caso 3: El Caso 3 (nivel Complejo) debe incluir, cuando el contenido de la clase lo permita, un sub-escenario contrafáctico: una pregunta adicional que invierta o modifique una premisa clave del enunciado original para testear si el alumno comprende el concepto desde el ángulo opuesto (ej. 'si tal circunstancia hubiera sido diferente, ¿cambiaría la solución?'). Esto eleva el caso de aplicación directa a aplicación comparativa.

Regla de anclaje de hechos en Casos: Al construir los hechos de cada Caso, revisar primero si la transcripción de la clase contiene ejemplos concretos mencionados por la docente (situaciones, objetos, nombres de casos reales, anécdotas). Si existen, usarlos como base de los hechos del Caso, adaptando nombres de personajes pero manteniendo el objeto/situación real mencionada en clase, en lugar de inventar un escenario genérico. Esto ancla mejor el caso a la memoria real de la clase. Solo inventar un escenario completamente nuevo si la transcripción no ofrece ejemplos aprovechables para ese Concepto de Oro.

## 📊 Mapa de cobertura
| Concepto | Caso | Pregunta | Riesgo |
| --- | --- | --- | --- |
[Tabla con todos los O, S, D, T, asignando Alto/Medio/Bajo y checkmarks]

✅ Paso 2 completo.
```

---

## PROMPT 3 COMPLETO: AUDITORÍA DOCUMENTAL PRE-NOTION (Paso 3)
**Objetivo**: Actuar como auditor documental de control de calidad. Contrastar minuciosamente los apuntes generados contra la transcripción original de la clase para verificar el respaldo y la veracidad de las citas y aserciones.

### Parámetros de entrada:
1. Ficha y Handoff generado
2. Cuestionario y Casos generado
3. Transcripción Original de la Clase

### Instrucciones de Auditoría:
```markdown
1. Analizá cada cita de leyes, artículos del Código Civil y Comercial (CCC), la Constitución Nacional (CN), fallos/jurisprudencia y posiciones doctrinarias que aparezcan en los dos apuntes.
2. Cruzalas contra la Transcripción Original. Confirmá si tienen respaldo literal o razonable en ella.
3. Si encontrás aserciones jurídicas o citas específicas que NO se mencionen en la transcripción ni tengan un sustento obvio de certeza razonable en la materia, identificalas como discrepancias.
4. Generá un reporte de salida estructurado usando EXACTAMENTE estas etiquetas de sección. Si no encontrás discrepancias en algún documento, poné "Ninguna":

<<<AUDITORIA_FICHA>>>
[Detallá los puntos con discrepancia o "Ninguna"]

<<<AUDITORIA_CUESTIONARIO>>>
[Detallá los puntos con discrepancia o "Ninguna"]

Regla de inyección en archivos:
Si se reportan discrepancias para un documento, se debe añadir al pie de dicho archivo la sección:

## ⚠️ Auditoría Documental — revisar
- **[Concepto/Cita bajo duda]:** [Motivo por el cual la cita o aserción carece de sustento directo en la transcripción o es inconsistente].
```

---

## REGLA DE MARCADORES DE INCERTIDUMBRE (APLICAR SIEMPRE)
Antes de clasificar cualquier dato en la Ficha o Cuestionario, cruzá el fragmento de la transcripción cruda con estos marcadores:
- `[dudoso]`, `[nombre dudoso]`, `[artículo dudoso]`, `[número dudoso]`: El dato no fue oído con claridad. No puede ser fuente única de un Concepto de Oro ni de una cita textual. Debés degradarlo a Concepto Satelital indicando la incertidumbre en el texto (ej. *"el profesor hace referencia a un artículo de número no verificado; verificar"*).
- `[inaudible]`: El tramo no es recuperable. Nunca infieras o inventes contenido para rellenarlo. Si coincide con una definición clave, reportala en el Handoff como vacío de información.
- `[REVISAR]` (Auditoría de Transcripción): Tratalo bajo el mismo criterio que los marcadores dudosos.
- `[CONSISTENTE]` (Auditoría de Transcripción): Significa que el texto no presenta errores sintácticos internos, pero no equivale a una verificación externa definitiva. Utilizalo con la precaución habitual del perfil.
