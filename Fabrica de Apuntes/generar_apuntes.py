import os
import sys
import time
import argparse
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Reconfigurar salida estándar para UTF-8 en Windows y evitar UnicodeEncodeError con emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Configurar sesión global con reintentos para robustez ante fallas de red y límites de tasa (429)
session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
adapter = HTTPAdapter(max_retries=retries)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Cargar variables de entorno desde el archivo .env
load_dotenv()


# Configuración de Proveedores y Modelos por defecto
DEFAULT_PROVIDER = "gemini"
DEFAULT_MODELS = {
    "openrouter": "anthropic/claude-3.5-sonnet",
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile"
}

def llamar_api(prompt_sistema, prompt_usuario, provider, model, api_key):
    """
    Realiza la llamada HTTP al proveedor seleccionado (OpenRouter, Gemini o Groq)
    con reintentos manuales ante Rate Limits (429) y caídas de red intermitentes.
    """
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [{"text": f"SYSTEM PROMPT:\n{prompt_sistema}\n\nUSER PROMPT:\n{prompt_usuario}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }
    elif provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/franklinzg/asistente-uba",
            "X-Title": "Asistente UBA Derecho"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.2
        }
    elif provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.2
        }
    else:
        print(f"❌ Proveedor no soportado: {provider}")
        sys.exit(1)

    max_intentos = 5
    for intento in range(max_intentos):
        response = None
        try:
            response = session.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            
            if provider == "gemini":
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return data["choices"][0]["message"]["content"].strip()
                
        except Exception as e:
            is_429 = False
            if isinstance(e, requests.exceptions.HTTPError) and response is not None and response.status_code == 429:
                is_429 = True
            
            if is_429 and intento < max_intentos - 1:
                retry_after = 12  # Valor por defecto prudencial
                if response is not None and "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                else:
                    # Espera exponencial: 12s, 24s, 48s...
                    retry_after = 12 * (2 ** intento)
                
                print(f"⚠️ Límite de tasa detectado (429). Reintentando en {retry_after} segundos (Intento {intento+1}/{max_intentos})...")
                time.sleep(retry_after)
                continue
            
            # En caso de fallas de red intermitentes (como NameResolutionError), también reintentamos
            if isinstance(e, requests.exceptions.RequestException) and not is_429 and intento < max_intentos - 1:
                retry_after = 5 * (intento + 1)
                print(f"⚠️ Error de red/conexión: {e}. Reintentando en {retry_after} segundos (Intento {intento+1}/{max_intentos})...")
                time.sleep(retry_after)
                continue

            print(f"❌ Error al llamar a la API de {provider.capitalize()}: {e}")
            if response is not None and response.text:
                print(f"Detalle: {response.text}")
            raise RuntimeError(f"Falla crítica en la API de {provider.capitalize()}: {e}")


def enviar_notificacion_telegram(materia, clase, fecha, tema):
    """
    Envía una notificación por Telegram al usuario informando de la subida exitosa.
    """
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    if not telegram_token:
        print("[WARN] No se encontró la variable de entorno TELEGRAM_TOKEN. Omisión de notificación.")
        return False
        
    # 1. Intentar obtener el chat ID desde las variables de entorno
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    # 2. Si no está en el .env, intentar leer de la persistencia local del bot
    if not chat_id:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chat_id_path = os.path.join(base_dir, "Bot Telegram", "chat_id.txt")
        if os.path.exists(chat_id_path):
            try:
                with open(chat_id_path, "r", encoding="utf-8") as f:
                    chat_id = f.read().strip()
            except Exception as e:
                print(f"[WARN] Error al leer el chat_id desde {chat_id_path}: {e}")
            
    if not chat_id or chat_id == "0":
        print("[WARN] No se encontró un Chat ID válido (TELEGRAM_CHAT_ID en .env o chat_id.txt). Omisión de notificación.")
        return False

    mensaje = (
        f"📚 *¡Fábrica de Apuntes UBA Derecho!*\n\n"
        f"Se han procesado y subido correctamente los apuntes de clase a Notion:\n\n"
        f"📖 *Materia:* {materia}\n"
        f"🏫 *Clase:* {clase}\n"
        f"📅 *Fecha:* {fecha}\n"
        f"📌 *Tema:* {tema}\n\n"
        f"✅ *Documentos disponibles en Notion:*\n"
        f"1. Ficha + Handoff\n"
        f"2. Sistema MIT\n"
        f"3. Cuestionario + Casos\n"
    )
    
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    
    try:
        r = session.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print("[SUCCESS] Notificación enviada con éxito por Telegram.")
        return True
    except Exception as e:
        print(f"[WARN] No se pudo enviar la notificación por Telegram: {e}")
        return False


def agendar_active_recall_notion(asunto, fecha_iso, notion_token, database_id):
    """
    Crea una entrada de tarea en la base de datos de agenda de Notion para el bot Franklin.
    """
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Asunto": {"title": [{"text": {"content": asunto}}]},
            "Fecha y Hora": {"date": {"start": fecha_iso}},
            "Estado": {"status": {"name": "Pendiente"}},
            "Prioridad": {"select": {"name": "Normal"}}
        }
    }
    url = "https://api.notion.com/v1/pages"
    try:
        r = session.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[WARN] Error al agendar recordatorio en Notion: {e}")
        return False


def programar_active_recall_en_notion(tema, notion_token, database_id):
    """
    Programa los recordatorios de Active Recall (días 3, 7 y 21) en la agenda de Notion.
    Para cada día agenda una alerta la noche previa (21:00) y otra la mañana del estudio (08:00).
    """
    import datetime
    try:
        # Huso horario local aproximado (UTC-3)
        ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
        fechas_estudio = [(3, 2), (7, 6), (21, 20)]
        exitos = 0
        for (dia_estudio, dia_previo) in fechas_estudio:
            # Notificación noche previa a las 21:00
            fecha_noche_previa = ahora + datetime.timedelta(days=dia_previo)
            iso_noche = fecha_noche_previa.strftime(f"%Y-%m-%dT21:00:00-03:00")
            asunto_noche = f"¡Mañana toca repasar!: {tema} (Repaso Día {dia_estudio})"
            if agendar_active_recall_notion(asunto_noche, iso_noche, notion_token, database_id):
                exitos += 1
                
            # Notificación mañana del día a las 08:00
            fecha_manana = ahora + datetime.timedelta(days=dia_estudio)
            iso_manana = fecha_manana.strftime(f"%Y-%m-%dT08:00:00-03:00")
            asunto_manana = f"📚 A ESTUDIAR HOY: {tema} (Repaso Día {dia_estudio})"
            if agendar_active_recall_notion(asunto_manana, iso_manana, notion_token, database_id):
                exitos += 1
        return exitos == 6
    except Exception as e:
        print(f"[WARN] Falló la programación de Active Recall: {e}")
        return False


def ejecutar_con_fallback(prompt_sistema, prompt_usuario, provider_principal, model_override=None):
    """
    Intenta ejecutar la llamada a la API con el proveedor principal.
    Si falla críticamente y el proveedor principal es Gemini, realiza
    un fallback automático a Groq utilizando sus credenciales del entorno.
    """
    api_key_env = {
        "openrouter": "OPENROUTER_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY"
    }
    
    try:
        model = model_override if model_override else DEFAULT_MODELS[provider_principal]
        env_var = api_key_env[provider_principal]
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ValueError(f"No se encontró la variable de entorno {env_var}")
            
        return llamar_api(prompt_sistema, prompt_usuario, provider_principal, model, api_key)
        
    except Exception as principal_error:
        if provider_principal == "gemini":
            print(f"\n⚠️ [FALLBACK] La llamada a Gemini falló críticamente: {principal_error}")
            print("🚀 Iniciando fallback automático a GROQ...")
            
            try:
                fallback_provider = "groq"
                model_fallback = DEFAULT_MODELS[fallback_provider]
                env_var_fallback = api_key_env[fallback_provider]
                api_key_fallback = os.environ.get(env_var_fallback)
                
                if not api_key_fallback:
                    raise ValueError(f"No se encontró la variable de entorno {env_var_fallback} para el fallback")
                
                print(f"🤖 Utilizando proveedor de respaldo: {fallback_provider.upper()} | Modelo: {model_fallback}")
                return llamar_api(prompt_sistema, prompt_usuario, fallback_provider, model_fallback, api_key_fallback)
            except Exception as fallback_error:
                print(f"❌ [FALLBACK ERROR] El proveedor de respaldo Groq también falló: {fallback_error}")
                # Si el fallback también falla, salimos con error crítico
                sys.exit(1)
        else:
            print(f"❌ Error crítico sin proveedor de respaldo configurado: {principal_error}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Fábrica de Apuntes UBA Derecho - Procesador de Transcripciones")
    parser.add_argument("archivo_transcripcion", help="Ruta al archivo de texto (.txt) con la transcripción de la clase")
    parser.add_argument("--materia", required=True, help="Nombre de la materia (ej. Contratos, Administrativo)")
    parser.add_argument("--clase", required=True, help="Número de clase (ej. 1, 22)")
    parser.add_argument("--fecha", required=True, help="Fecha en formato DD-MM-YY")
    parser.add_argument("--tema", required=True, help="Tema principal de la clase (ej. Elementos del Contrato)")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["openrouter", "gemini", "groq"], 
                        help="Proveedor de API a utilizar (por defecto: gemini)")
    parser.add_argument("--model", help="Modelo específico a utilizar (opcional, tiene valores por defecto por proveedor)")
    parser.add_argument("--upload", action="store_true", help="Sube automáticamente los archivos generados a Notion")
    parser.add_argument("--parent-page", default="2361618c-4b73-8173-8126-e8d418984def", 
                        help="ID de la base de datos de materias en Notion (por defecto: base 'Materias')")
    
    args = parser.parse_args()
    
    # Resolver modelo por defecto
    model = args.model if args.model else DEFAULT_MODELS[args.provider]
    
    # Obtener API key correspondiente
    api_key_env = {
        "openrouter": "OPENROUTER_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY"
    }
    
    env_var = api_key_env[args.provider]
    api_key = os.environ.get(env_var)
    
    if not api_key:
        print(f"⚠️ No se encontró la variable de entorno {env_var}.")
        api_key = input(f"Introduce tu API Key de {args.provider.capitalize()} para continuar: ").strip()
        if not api_key:
            print("❌ Se requiere una API Key para continuar.")
            sys.exit(1)
            
    if not os.path.exists(args.archivo_transcripcion):
        print(f"❌ El archivo de transcripción '{args.archivo_transcripcion}' no existe.")
        sys.exit(1)
        
    with open(args.archivo_transcripcion, "r", encoding="utf-8") as f:
        transcripcion = f.read()
        
    print(f"📖 Transcripción cargada ({len(transcripcion)} caracteres).")
    print(f"🤖 Utilizando proveedor: {args.provider.upper()} | Modelo: {model}")
    
    # Cargar el perfil jurídico general
    perfil_asistente = """
Sos un asistente jurídico especializado en derecho argentino, orientado a acompañar a un estudiante avanzado de la UBA en su trabajo cotidiano de estudio, análisis y escritura jurídica. Tu función no es reemplazar el criterio del usuario sino potenciarlo: organizás la información, marcás los límites de lo que sabés, y ayudás a construir razonamiento jurídico sólido.
Tu utilidad no depende de parecer completo sino de ser confiable. Una respuesta corta y verificable vale más que una larga con datos dudosos.

Tono y estilo:
– Registro formal-preciso, coherente con la escritura jurídica argentina. Sin coloquialismos.
– La primera oración de cada respuesta contiene sustancia directa.
– Prosa continua para razonamiento jurídico. Usá listas solo para enumeraciones genuinamente paralelas.

Reglas de fuentes:
NORMAS: Citá artículos del CCC, la CN y leyes nacionales solo cuando tenés certeza razonable. Si no recordás el número exacto, describí el instituto con precisión y pedí verificación. Nunca fabricués un número de artículo.
JURISPRUDENCIA: Citá fallos solo cuando tenés certeza razonable del nombre del caso y su doctrina central. Nunca inventés nombres ni fechas.
DOCTRINA: Atribuí posiciones a autores solo cuando tenés certeza razonable. Si no, describí la posición como "posición mayoritaria" o "sector de la doctrina".

Distinción de planos:
Distinguí con claridad: [NORMA] Lo que dice el texto positivo vigente. [JURISPRUDENCIA] Cómo interpretaron y aplicaron esa norma los tribunales. [DOCTRINA] Qué sostienen los autores.

Manejo de incertidumbre:
Certeza razonable: afirmación directa con cita.
Probabilidad razonable: "la posición dominante es…"
Incertidumbre real: "no tengo certeza sobre este punto; verificá en [fuente]."
Cuando no sabés algo, decilo en la primera oración.

Regla de Marcadores de Incertidumbre:
Antes de clasificar cualquier elemento (Concepto de Oro, Satelital, cita normativa, jurisprudencial o doctrinaria) debés cruzar el fragmento correspondiente de la transcripción con estos marcadores si están presentes en la transcripción cruda:
- [dudoso], [nombre dudoso], [artículo dudoso], [número dudoso]: el dato no fue transcripto con seguridad. No puede ser la única fuente de un Concepto de Oro, ni de una cita textual atribuida al profesor. Si es la única fuente disponible para ese contenido, degradalo a Concepto Satelital y aclarará la incertidumbre explícitamente en el texto (ej. "el profesor menciona un artículo cuyo número no se pudo identificar con certeza; verificar").
- [inaudible]: el tramo no tiene contenido recuperable. Nunca se rellena por inferencia; si el tramo inaudible coincide con la única explicación de un concepto central de la clase, señalalo como vacío de información en el Handoff en vez de inventar contenido para completar la ficha.
- [REVISAR] (en la auditoría de transcripción externa): tratalo con el mismo criterio que [dudoso] — no lo uses como fuente única de un dato crítico sin aclarar la incertidumbre.
- [CONSISTENTE] (en la auditoría de transcripción externa): no equivale a "confirmado contra el audio real", solo significa que el texto no muestra señales internas de error. Podés citarlo con la certeza normal de esta guía, pero sin tratarlo como verificación externa definitiva.

Idioma de salida:
Todas las respuestas deben ser redactadas en español.
"""

    # Crear la carpeta de salida Universidad si no existe
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Universidad")
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n--- [1/3] Generando Paso 1: FICHA + HANDOFF ---")
    prompt_ficha_sistema = perfil_asistente + "\nObjetivo: Transformar una transcripción cruda en una Ficha académica y un bloque HANDOFF estructurado. Sigue la estructura de salida especificada en las instrucciones."
    prompt_ficha_usuario = f"""Materia: {args.materia}
Clase: {args.clase}
Fecha: {args.fecha}
Tema: {args.tema}

Estructura de salida requerida:
# 📄 PASO 1 — FICHA · Pegar en Notion: Ficha_{args.materia}_Clase{args.clase}_{args.fecha}

## ⚡ MÓDULO 1 — PORTADA RÁPIDA
### 📌 BLOQUE A — ¿De qué va la clase?
**Eje central:** [1-2 frases]
**Marco normativo:** Artículos, fallos, doctrina.
**⚖️ Fuente guía:** [El artículo o fallo que estructura la clase]

### 🎯 BLOQUE B — ¿Qué cae en examen?
**⭐ Marcado por el profesor:** [Frase textual si hay]
**🏆 Diferencias de 8+:** [Detalles técnicos o excepciones clave]
**🚨 Alerta de examen:** [Pregunta típica, fuentes obligatorias]
**📦 Trampa común:** Error típico y cómo evitarla.

## 🥇 MÓDULO 2 — CONCEPTOS DE ORO
[Máximo 4 conceptos. Formato por cada uno:]
**[O1] Concepto:** [Nombre]
**Definición de cátedra:** [Definición con cita si hay]
**Elementos esenciales:** [Bullets con consecuencias]
**Fuente:** [Art/Fallo]
**Consecuencias jurídicas:** ✅ Si se cumple... ❌ Si no se cumple...
**Relacionado con:** [Concepto]

## 🛰️ CONCEPTOS SATELITALES
[Máximo 4. Texto o Tabla según corresponda]

## 🔗 HANDOFF PARA PASO 2
Materia: {args.materia} · Clase: {args.clase} · Fecha: {args.fecha} · Tema: {args.tema}
**Conceptos Oro:** O1, O2...
**Satelitales:** S1, S2...
**Trampas detectadas:** T1, T2... (con ⚠️ automático)
**Distinciones clave:** D1, D2...
**Fuentes centrales:** A1, F1...

Generado con: {model} · Modo: Script

✅ Paso 1 completo.

TRANSCRIPCIÓN DE LA CLASE:
{transcripcion}
"""
    
    ficha_content = ejecutar_con_fallback(prompt_ficha_sistema, prompt_ficha_usuario, args.provider, args.model)
    ficha_path = os.path.join(output_dir, f"Ficha_{args.materia}_Clase{args.clase}_{args.fecha}.md")
    with open(ficha_path, "w", encoding="utf-8") as f:
        f.write(ficha_content)
    print(f"✅ Ficha académica creada en: {ficha_path}")
    
    print("\n--- [2/3] Generando Paso 2: SISTEMA MIT ---")
    prompt_mit_sistema = perfil_asistente + "\nObjetivo: Generar el puente entre el resumen y el cuestionario duro. Trabaja directamente sobre la transcripción de la clase, cruzando la consistencia con el Paso 1."
    prompt_mit_usuario = f"""Materia: {args.materia}
Tema: {args.tema}

Estructura de salida requerida:
# SISTEMA MIT — {args.materia}
**Tema:** {args.tema}

## ETAPA 1 — MAPA NUCLEAR (máximo 1 página)
Identificar los 5 conceptos centrales. Para cada uno:
- **Definición precisa:** según el material.
- **Función práctica:** para qué sirve en un caso real.
- **Conexión:** con cuál otro concepto se relaciona.
- **Error frecuente:** qué confunde el estudiante.
- **Alerta de clase:** advertencia explícita textual si la hay.

Regla de Consistencia de Conceptos:
Antes de definir los 5 conceptos del Mapa Nuclear del MIT, debés revisar los Conceptos de Oro (O1–O4) ya identificados en el Handoff del Paso 1 (provisto abajo). Debés priorizarlos y usarlos como base para estos 5 conceptos del MIT. Solo incorporá un concepto nuevo (no listado como Oro) si la relectura de la transcripción revela algo estructuralmente relevante que el Paso 1 omitió. En tal caso, agregá una línea aclaratoria al final del concepto: "Concepto añadido en Paso 2, no estaba en el Handoff: [motivo]".

**MATRIZ DE CONEXIONES:** 3-5 líneas mostrando cómo se relacionan los 5 conceptos como sistema.

## ETAPA 2 — TABLA DE ALERTAS DE EXAMEN
| Regla o idea central | Fuente (ley/clase/fallo) | Advertencia del profesor | Trampa típica de parcial/final |
[8-12 filas]

## ETAPA 3 — SIMULACRO DE ALTA DIFICULTAD (10 preguntas)
Actuar como profesor exigente. Combinar teoría, normativa y caso.
**PREGUNTA N° [n]**
[Texto de la pregunta]
* ▸ RESPUESTA ESPERADA: [3 a 6 líneas]
* ▸ ERROR TÍPICO: [Qué contesta un estudiante que memorizó pero no entendió]
* ▸ FUENTE PARA REPASAR SI FALLÁS: [Qué parte del cuaderno leer]
(La pregunta 10 debe ser integradora)

CONTENIDO GENERADO EN EL PASO 1 (FICHA Y HANDOFF):
{ficha_content}

TRANSCRIPCIÓN DE LA CLASE:
{transcripcion}
"""
    
    mit_content = ejecutar_con_fallback(prompt_mit_sistema, prompt_mit_usuario, args.provider, args.model)
    mit_path = os.path.join(output_dir, f"Sistema_MIT_{args.materia}_Clase{args.clase}_{args.fecha}.md")
    with open(mit_path, "w", encoding="utf-8") as f:
        f.write(mit_content)
    print(f"✅ Sistema MIT creado en: {mit_path}")
    
    print("\n--- [3/3] Generando Paso 3: CUESTIONARIO Y CASOS ---")
    prompt_cuestionario_sistema = perfil_asistente + "\nObjetivo: Basado EXCLUSIVAMENTE en la Ficha y el HANDOFF generados en el Paso 1, generar Cuestionario y Casos prácticos. Es un requerimiento crítico seguir la estructura de salida al pie de la letra, limitando el cuestionario a un máximo de 8 preguntas direccionadas y 1 pregunta integradora. No inventar preguntas adicionales."
    prompt_cuestionario_usuario = f"""Estructura de salida requerida de manera estricta y obligatoria (respetar saltos de línea, emojis y etiquetas):
# 📄 PASO 2A — CUESTIONARIO · Pegar en Notion: Cuestionario_{args.materia}_Clase{args.clase}_{args.fecha}

❓ 1. [Texto de la pregunta] · fuente [Cita exacta del Handoff] · [Etiquetas: 🎯 Pareto, ⚠️ Trampa o 🏆 Cae siempre]
1. [Punto 1 de la respuesta]
2. [Punto 2 de la respuesta]
*❌ Error típico: [error real del HANDOFF]*

[Generar hasta un máximo absoluto de 8 preguntas numeradas consecutivamente del 1 al 8 con el formato anterior. No generar más de 8 preguntas bajo ninguna circunstancia]

[Incluir tabla comparativa si hay distinciones D1/D2 en el Handoff]

❓ Integradora. [Texto del escenario del caso integrador con 2-4 subpreguntas encadenadas] 🏆 Cae siempre

## 🎯 Top Pareto
| Prioridad | Pregunta | Concepto clave |
| --- | --- | --- |
[🔴 Crítico, 🟠 Alto - listar las preguntas más relevantes de las 8 anteriores]

## 📜 Fuentes clave
| Fuente | Qué establece | Por qué importa en examen |
| --- | --- | --- |

---

# 📄 PASO 2B — CASOS · Pegar en Notion: Casos_{args.materia}_Clase{args.clase}_{args.fecha}
[Generar exactamente 3 Casos con el formato siguiente: Caso 1 (Simple O1/O2), Caso 2 (Trampa T1), Caso 3 (Complejo interclase o nivel intermedio)]

📌 **CASO [N] — [Título del caso]**
* **Nivel:** [Simple/Trampa/Complejo]
* **Conceptos:** [Conceptos Oro/Trampa involucrados]
* **⚖️ Fuentes:** [Fuentes normativas/jurisprudenciales involucradas]
* **Enunciado:** [Relato de hechos concretos con nombres de personas]

► Intentá resolverlo antes de seguir.

**Resolución**
* **Figura jurídica en juego:** [Identificación del instituto en 1 línea]
* **Razonamiento:** [Puntos 1, 2, 3 de la argumentación jurídica]
* **Respuesta:** [Resolución concreta de no más de 4 líneas]
* **⚠️ Error típico:** [Error o trampa asociada]
* **Link:** Relacionado con: P[N] del cuestionario

[Repetir estructura para Caso 2 y Caso 3]

## 📊 Mapa de cobertura
| Concepto | Caso | Pregunta | Riesgo |
| --- | --- | --- | --- |
[Tabla con los conceptos O, S, D, T, relacionando cada uno con su caso/pregunta, asignando riesgo Alto/Medio/Bajo y checkmarks]

✅ Paso 2 completo.

FICHA Y HANDOFF (PASO 1 GENERADO):
{ficha_content}
"""
    
    cuestionario_content = ejecutar_con_fallback(prompt_cuestionario_sistema, prompt_cuestionario_usuario, args.provider, args.model)
    cuestionario_path = os.path.join(output_dir, f"Cuestionario_y_Casos_{args.materia}_Clase{args.clase}_{args.fecha}.md")
    with open(cuestionario_path, "w", encoding="utf-8") as f:
        f.write(cuestionario_content)
    print(f"[SUCCESS] Cuestionario y Casos creados en: {cuestionario_path}")
    
    print("\n--- [4/4] Ejecutando Paso 4: AUDITORÍA DOCUMENTAL ---")
    prompt_auditoria_sistema = perfil_asistente + "\nObjetivo: Actuar como auditor documental de control de calidad. Contrastar minuciosamente los apuntes generados contra la transcripción original de la clase para verificar el respaldo y la veracidad de las citas y aserciones."
    prompt_auditoria_usuario = f"""Tenés que auditar los siguientes tres apuntes que fueron generados a partir de la transcripción original:

1. FICHA Y HANDOFF GENERADO:
{ficha_content}

2. SISTEMA MIT GENERADO:
{mit_content}

3. CUESTIONARIO Y CASOS GENERADO:
{cuestionario_content}

TRANSCRIPCIÓN ORIGINAL DE LA CLASE:
{transcripcion}

Instrucciones de Auditoría:
1. Analizá cada cita de leyes, artículos del Código Civil y Comercial (CCC), la Constitución Nacional (CN), fallos/jurisprudencia y posiciones doctrinarias que aparezcan en los tres apuntes.
2. Cruzalas contra la Transcripción Original. Confirmá si tienen respaldo literal o razonable en ella.
3. Si encontrás aserciones jurídicas o citas específicas que NO se mencionen en la transcripción ni tengan un sustento obvio de certeza razonable en la materia, identificalas como discrepancias.
4. Generá un reporte de salida estructurado usando EXACTAMENTE estas etiquetas de sección. Si no encontrás discrepancias en algún documento, poné "Ninguna". No agregues preámbulos ni explicaciones fuera de las etiquetas:

<<<AUDITORIA_FICHA>>>
[Detallá los puntos con discrepancia o "Ninguna"]

<<<AUDITORIA_MIT>>>
[Detallá los puntos con discrepancia o "Ninguna"]

<<<AUDITORIA_CUESTIONARIO>>>
[Detallá los puntos con discrepancia o "Ninguna"]
"""
    
    import re
    auditoria_content = ejecutar_con_fallback(prompt_auditoria_sistema, prompt_auditoria_usuario, args.provider, args.model)
    
    def extraer_seccion(texto, tag):
        pattern = f"<<<{tag}>>>\\n(.*?)(?=\\n<<<|$)"
        match = re.search(pattern, texto, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "Ninguna"
        
    auditoria_ficha = extraer_seccion(auditoria_content, "AUDITORIA_FICHA")
    auditoria_mit = extraer_seccion(auditoria_content, "AUDITORIA_MIT")
    auditoria_cuestionario = extraer_seccion(auditoria_content, "AUDITORIA_CUESTIONARIO")
    
    # Inyectar advertencias si existen y reescribir los archivos locales
    if auditoria_ficha and auditoria_ficha.lower() != "ninguna":
        print("[AUDITORÍA] Se detectaron discrepancias en la Ficha. Inyectando advertencias...")
        ficha_content += f"\n\n## ⚠️ Auditoría Documental — revisar\n{auditoria_ficha}"
        with open(ficha_path, "w", encoding="utf-8") as f:
            f.write(ficha_content)
            
    if auditoria_mit and auditoria_mit.lower() != "ninguna":
        print("[AUDITORÍA] Se detectaron discrepancias en el Sistema MIT. Inyectando advertencias...")
        mit_content += f"\n\n## ⚠️ Auditoría Documental — revisar\n{auditoria_mit}"
        with open(mit_path, "w", encoding="utf-8") as f:
            f.write(mit_content)
            
    if auditoria_cuestionario and auditoria_cuestionario.lower() != "ninguna":
        print("[AUDITORÍA] Se detectaron discrepancias en el Cuestionario y Casos. Inyectando advertencias...")
        cuestionario_content += f"\n\n## ⚠️ Auditoría Documental — revisar\n{auditoria_cuestionario}"
        with open(cuestionario_path, "w", encoding="utf-8") as f:
            f.write(cuestionario_content)
            
    print(f"\n[SUCCESS] Procesamiento y Auditoría completados con exito! Archivos actualizados en la carpeta Universidad.")

    # Carga automática a Notion si se solicita
    if args.upload:
        notion_token = os.environ.get("NOTION_TOKEN")
        if not notion_token:
            print("❌ Error: No se encontró la variable de entorno NOTION_TOKEN.")
            sys.exit(1)
            
        print("\n[INFO] Iniciando subida automatica a Notion...")
        try:
            # Importación dinámica para evitar dependencias circulares
            from subir_a_notion import obtener_o_crear_pagina_materia, subir_apuntes
            
            materia_page_id = obtener_o_crear_pagina_materia(notion_token, args.parent_page, args.materia)
            
            f1 = subir_apuntes(args.materia, args.clase, args.fecha, "Ficha + Handoff", ficha_path, notion_token, materia_page_id)
            f2 = subir_apuntes(args.materia, args.clase, args.fecha, "Sistema MIT", mit_path, notion_token, materia_page_id)
            f3 = subir_apuntes(args.materia, args.clase, args.fecha, "Cuestionario + Casos", cuestionario_path, notion_token, materia_page_id)
            print("\n[SUCCESS] Carga a Notion finalizada con exito!")
            
            # Enviar notificación por Telegram si al menos un documento se subió correctamente
            if f1 or f2 or f3:
                enviar_notificacion_telegram(args.materia, args.clase, args.fecha, args.tema)
                
                # Programar recordatorios de Active Recall para el bot Franklin
                db_agenda_id = os.environ.get("NOTION_DB_ID")
                if db_agenda_id:
                    print("\n[INFO] Programando recordatorios de Active Recall (días 3, 7 y 21) en la agenda de Franklin...")
                    tema_estudio = f"{args.materia} - Clase {args.clase}: {args.tema}"
                    if programar_active_recall_en_notion(tema_estudio, notion_token, db_agenda_id):
                        print("[SUCCESS] Recordatorios de Active Recall agendados con éxito en Notion.")
                    else:
                        print("[WARN] No se pudieron agendar todos los recordatorios en Notion.")
        except Exception as e:
            print(f"[ERROR] Error durante el proceso de carga a Notion: {e}")

if __name__ == "__main__":
    main()
