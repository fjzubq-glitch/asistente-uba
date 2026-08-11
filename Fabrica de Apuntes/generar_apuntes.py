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
    prompt_mit_sistema = perfil_asistente + "\nObjetivo: Generar el puente entre el resumen y el cuestionario duro. Trabaja directamente sobre la transcripción de la clase."
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

**MATRIZ DE CONEXIONES:** 3-5 líneas mostrando cómo se relacionan los 5 conceptos como sistema.

## ETAPA 2 — TABLA DE ALERTAS DE EXAMEN
| Regla o idea central | Fuente (ley/clase/fallo) | Advertencia del profesor | Trampa típica de parcial/final |
[8-12 filas]

## ETAPA 3 — SIMULACRO DE ALTA DIFICULTAD (10 preguntas)
Actuar como profesor exigente. Combinar teoría, normativa y caso.
**PREGUNTA N° [n]**
[Texto de la pregunta]
▸ RESPUESTA ESPERADA: [3 a 6 líneas]
▸ ERROR TÍPICO: [Qué contesta un estudiante que memorizó pero no entendió]
▸ FUENTE PARA REPASAR SI FALLÁS: [Qué parte del cuaderno leer]
(La pregunta 10 debe ser integradora)

TRANSCRIPCIÓN DE LA CLASE:
{transcripcion}
"""
    
    mit_content = ejecutar_con_fallback(prompt_mit_sistema, prompt_mit_usuario, args.provider, args.model)
    mit_path = os.path.join(output_dir, f"Sistema_MIT_{args.materia}_Clase{args.clase}_{args.fecha}.md")
    with open(mit_path, "w", encoding="utf-8") as f:
        f.write(mit_content)
    print(f"✅ Sistema MIT creado en: {mit_path}")
    
    print("\n--- [3/3] Generando Paso 3: CUESTIONARIO Y CASOS ---")
    prompt_cuestionario_sistema = perfil_asistente + "\nObjetivo: Basado EXCLUSIVAMENTE en la Ficha y el HANDOFF generados en el Paso 1, generar Cuestionario y Casos prácticos."
    prompt_cuestionario_usuario = f"""Estructura de salida requerida:
# 📄 PASO 2A — CUESTIONARIO · Pegar en Notion: Cuestionario_{args.materia}_Clase{args.clase}_{args.fecha}
[Máximo 8 preguntas + 1 integradora. Formato por cada una:]
❓ 1. [Texto] · fuente [X] · [Etiquetas: 🎯 Pareto, ⚠️ Trampa, 🏆 Cae siempre]
1. [Punto 1 respuesta]
2. [Punto 2 respuesta]
*❌ Error típico: [error real del HANDOFF]*

[Incluir tabla comparativa si hay distinciones D1/D2 en el Handoff]

❓ Integradora. [2-4 subpreguntas encadenadas] 🏆 Cae siempre

## 🎯 Top Pareto
| Prioridad | Pregunta | Concepto clave |
[🔴 Crítico, 🟠 Alto]

## 📜 Fuentes clave
| Fuente | Qué establece | Por qué importa en examen |

---

# 📄 PASO 2B — CASOS · Pegar en Notion: Casos_{args.materia}_Clase{args.clase}_{args.fecha}
[3 Casos: Caso 1 (Simple O1/O2), Caso 2 (Trampa T1), Caso 3 (Complejo interclase o nivel intermedio)]

📌 **CASO [N] — [Título]**
Nivel: [Simple/Trampa/Complejo]
Conceptos: [O1, T1...]
⚖️ Fuentes: [A1, F1...]
**Enunciado:** [Hechos concretos. Personajes con nombres.]
► Intentá resolverlo antes de seguir.
**Resolución**
Figura jurídica en juego: [1 línea]
Razonamiento: [1, 2, 3...]
Respuesta: [Máx 4 líneas]
⚠️ Error típico: [T1 del Handoff]
Relacionado con: P[N] del cuestionario

## 📊 Mapa de cobertura
| Concepto | Caso | Pregunta | Riesgo |
[Tabla con todos los O, S, D, T, asignando Alto/Medio/Bajo y checkmarks]

✅ Paso 2 completo.

FICHA Y HANDOFF (PASO 1 GENERADO):
{ficha_content}
"""
    
    cuestionario_content = ejecutar_con_fallback(prompt_cuestionario_sistema, prompt_cuestionario_usuario, args.provider, args.model)
    cuestionario_path = os.path.join(output_dir, f"Cuestionario_y_Casos_{args.materia}_Clase{args.clase}_{args.fecha}.md")
    with open(cuestionario_path, "w", encoding="utf-8") as f:
        f.write(cuestionario_content)
    print(f"[SUCCESS] Cuestionario y Casos creados en: {cuestionario_path}")
    
    print(f"\n[SUCCESS] Procesamiento completado con exito! Todos los archivos se han guardado en la carpeta Universidad.")

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
        except Exception as e:
            print(f"[ERROR] Error durante el proceso de carga a Notion: {e}")

if __name__ == "__main__":
    main()
