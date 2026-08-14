# Proyecto 2: Fábrica de Apuntes UBA Derecho

Este proyecto es un sistema automatizado que procesa transcripciones crudas de clases y genera 3 archivos Markdown organizados y estructurados.

## Perfil del Asistente Jurídico (Aplicar Siempre)
Este perfil está cargado en las reglas globales del agente (`.agents/AGENTS.md`) para asegurar consistencia en el tono formal-preciso argentino, el respeto de fuentes y la gestión de la incertidumbre.

---

## PROMPT 1 COMPLETO: FICHA + HANDOFF
**Objetivo**: Transformar una transcripción cruda en una Ficha académica y un bloque HANDOFF estructurado.
**Reglas**:
* Lenguaje técnico argentino.
* Frases textuales entre comillas.
* Negrita para conceptos clave.
* Sin HTML.
* Nunca inventar artículos.
* Marcas de examen (ej. *"esto lo tomo"*) entran siempre a Oro.

### Estructura de salida:
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
* **Elementos esenciales:** [Bullets con consecuencias]
* **Fuente:** [Art/Fallo]
* **Consecuencias jurídicas:** ✅ Si se cumple... ❌ Si no se cumple...
* **Relacionado con:** [Concepto]

## 🛰️ CONCEPTOS SATELITALES
[Máximo 4. Texto (S1) o Tabla (S2) según corresponda]

## 🔗 HANDOFF PARA PASO 2
Materia: X · Clase: N · Fecha: DD-MM-YY · Tema: Y
* **Conceptos Oro:** O1, O2...
* **Satelitales:** S1, S2...
* **Trampas detectadas:** T1, T2... (con ⚠️ automático)
* **Distinciones clave:** D1, D2...
* **Fuentes centrales:** A1, F1...

✅ Paso 1 completo.
```

---

## PROMPT MIT COMPLETO: MAPA, TRAMPAS Y SIMULACRO (Paso 2 — MIT)
**Objetivo**: Generar el puente entre el resumen y el cuestionario duro. Trabaja directamente sobre la transcripción de la clase cruzando consistencia con el Paso 1.

### Estructura de salida:
```markdown
# SISTEMA MIT — [MATERIA]
**Tema:** [Tema]

## ETAPA 1 — MAPA NUCLEAR (máximo 1 página)
Identificar los 5 conceptos centrales (priorizando los Conceptos de Oro O1-O4 del Handoff del Paso 1). Para cada uno:
* **Definición precisa:** según el material.
* **Función práctica:** para qué sirve en un caso real.
* **Conexión:** con cuál otro concepto se relaciona.
* **Error frecuente:** qué confunde el estudiante.
* **Alerta de clase:** advertencia explícita textual si la hay.
*[Si se añade un concepto no listado en el Handoff del Paso 1, agregar al final: "Concepto añadido en Paso 2, no estaba en el Handoff: [motivo]"]*

**MATRIZ DE CONEXIONES:** 3-5 líneas mostrando cómo se relacionan los 5 conceptos como sistema.

## ETAPA 2 — TABLA DE ALERTAS DE EXAMEN
| Regla o idea central | Fuente (ley/clase/fallo) | Advertencia del profesor | Trampa típica de parcial/final |
| --- | --- | --- | --- |
[8-12 filas]

## ETAPA 3 — SIMULACRO DE ALTA DIFICULTAD (10 preguntas)
Actuar como profesor exigente. Combinar teoría, normativa y caso.

**PREGUNTA N° [n]**
[Texto de la pregunta]
* ▸ RESPUESTA ESPERADA: [3 a 6 líneas]
* ▸ ERROR TÍPICO: [Qué contesta un estudiante que memorizó pero no entendió]
* ▸ FUENTE PARA REPASAR SI FALLÁS: [Qué parte del cuaderno leer]

(La pregunta 10 debe ser integradora)
```

---

## PROMPT 2 COMPLETO: CUESTIONARIO + CASOS
**Objetivo**: Basado EXCLUSIVAMENTE en la Ficha y el HANDOFF, generar Cuestionario y Casos.

### Estructura de salida:
```markdown
# 📄 PASO 2A — CUESTIONARIO · Pegar en Notion: Cuestionario_[Materia]_Clase[N]_[DD-MM-YY]

[Máximo 8 preguntas + 1 integradora. Formato por cada una:]

❓ 1. [Texto] · [Etiquetas: 🎯 Pareto, ⚠️ Trampa, 🏆 Cae siempre]
1. [Punto 1 respuesta]
2. [Punto 2 respuesta]
*❌ Error típico: [error real del HANDOFF]*

[Incluir tabla comparativa si hay distinciones D1/D2 en el Handoff]

❓ Integradora. [2-4 subpreguntas encadenadas] 🏆 Cae siempre

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

## 📊 Mapa de cobertura
| Concepto | Caso | Pregunta | Riesgo |
| --- | --- | --- | --- |
[Tabla con todos los O, S, D, T, asignando Alto/Medio/Bajo y checkmarks]

✅ Paso 2 completo.
```

---

## EJEMPLO GOLD STANDARD (CLASE 22 CONTRATOS)
*Generado originalmente con Claude Opus 4.6, mostrando el rigor y nivel de detalle esperado.*

### Fragmento de FICHA (Ejemplo de Concepto Oro)
**[O1] Concepto: Marco normativo aplicable al contrato**
* **Definición de cátedra:** Antes de redactar cualquier contrato debe identificarse el marco normativo aplicable en un orden de prelación: Constitución Nacional, Código Civil y Comercial, y leyes especiales. A este marco genérico se suma el específico: normas reglamentarias de autoridades de aplicación (ej. Banco Central), y usos y costumbres.
* **Elementos esenciales:**
  - Jerarquía genérica (CN → CCyC → leyes especiales) → determina el piso normativo
  - Normas específicas por tipo contractual → determinan cláusulas obligatorias o prohibidas
* **Fuente:** norma general sobre jerarquía normativa — número no citado en clase
* **Consecuencias jurídicas:**
  - ✅ Si se identifica correctamente → el contrato respeta las prohibiciones y parámetros legales
  - ❌ Si no se identifica → riesgo de nulidad parcial o sustitución automática
* **Textual del profesor:** *"Yo no puedo mandarme a redactar contratos sin saber el marco normativo general bajo el cual vamos a encausar el contrato."*

### Fragmento de MIT (Ejemplo de Simulacro)
**PREGUNTA N° 3**
¿Por qué la profesora insiste en que el abogado redactor "no es parte del contrato", y qué elemento eseencial se vincula con esta advertencia cuando actúan personas jurídicas?
* ▸ RESPUESTA ESPERADA: Porque el rol del abogado es auditar la validez del acto, no su conveniencia comercial. Al auditar "Partes / Consentimiento" en personas jurídicas, debe exigir y verificar los instrumentos representativos (acta de directorio inscripta, poderes vigentes con alcance suficiente) para asegurar que quien firma obliga válidamente a la sociedad.
* ▸ ERROR TÍPICO: Creer que verificar la identidad en el DNI es suficiente cuando se negocia con una SA o SRL.
* ▸ FUENTE PARA REPASAR SI FALLÁS: Transcripción de clase, segmento sobre Elementos Esenciales y Rol del Abogado.

### Fragmento de CUESTIONARIO (Ejemplo de Pregunta)
❓ 2. Explicá por qué el título que las partes asignan a un contrato no determina su naturaleza jurídica, con un ejemplo concreto de la clase · fuente D2 · ⚠️ Trampa de examen · 🎯 Pareto
1. La naturaleza jurídica del negocio surge del contenido real de las obligaciones pactadas, no de la denominación elegida por las partes.
2. Un instrumento titulado "boleto de compraventa" puede constituir en realidad un contrato de mutuo si la sustancia del negocio es un préstamo de dinero con obligación de restitución más interés.
3. La calificación errónea del título no exime de las consecuencias jurídicas propias de la figura real.
* **❌ Error típico: confundir el título del contrato con su naturaleza jurídica real (T1).**
* **Textual del profesor:** *"No importa que yo le puse 'boleto de compraventa', porque el 'boleto de compraventa' no me va a definir qué tipo de contrato es, sino la naturaleza de todo el negocio."*

---

## REGLA DE MARCADORES DE INCERTIDUMBRE (APLICAR SIEMPRE)
Antes de clasificar cualquier dato en la Ficha, MIT o Cuestionario, cruzá el fragmento de la transcripción cruda con estos marcadores:
- `[dudoso]`, `[nombre dudoso]`, `[artículo dudoso]`, `[número dudoso]`: El dato no fue oído con claridad. No puede ser fuente única de un Concepto de Oro ni de una cita textual. Debés degradarlo a Concepto Satelital indicando la incertidumbre en el texto (ej. *"el profesor hace referencia a un artículo de número no verificado; verificar"*).
- `[inaudible]`: El tramo no es recuperable. Nunca infieras o inventes contenido para rellenarlo. Si coincide con una definición clave, reportala en el Handoff como vacío de información.
- `[REVISAR]` (Auditoría de Transcripción): Tratalo bajo el mismo criterio que los marcadores dudosos.
- `[CONSISTENTE]` (Auditoría de Transcripción): Significa que el texto no presenta errores sintácticos internos, pero no equivale a una verificación externa definitiva. Utilizalo con la precaución habitual del perfil.

---

## ETAPA 4: AUDITORÍA DOCUMENTAL (PRE-NOTION)
Es el paso final del pipeline, a ejecutarse tras el Prompt 3. Consiste en contrastar minuciosamente las citas normativas, doctrinarias o de fallos de los apuntes generados contra la transcripción original. Si detectás alguna cita que carece de base en la transcripción, no la borres en silencio: añadí una sección al pie del apunte correspondiente titulada:
```markdown
## ⚠️ Auditoría Documental — revisar
- **[Concepto/Cita bajo duda]:** [Motivo por el cual la cita o aserción carece de sustento directo en la transcripción o es inconsistente].
```
Si el documento está libre de discrepancias, no se inyecta ninguna advertencia y se procede a guardar y subir normalmente.
