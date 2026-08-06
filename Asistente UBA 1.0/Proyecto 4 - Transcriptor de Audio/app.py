import os
import sys
import subprocess
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env local
load_dotenv()

app = Flask(__name__)

# Configuración de carpetas de almacenamiento
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "temp_uploads")
TRANSCRIPT_FOLDER = os.path.join(BASE_DIR, "transcripciones")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)

def transcribir_con_deepgram(ruta_audio, api_key):
    """
    Realiza la llamada directa a la API de Deepgram utilizando el modelo Nova-3.
    Usa peticiones HTTP directas para mayor robustez en cualquier entorno.
    """
    print("[DEEPGRAM] Enviando archivo a Deepgram Nova-3...")
    url = "https://api.deepgram.com/v1/listen?model=nova-3&language=es&smart_format=true"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/octet-stream"
    }
    
    with open(ruta_audio, "rb") as f:
        audio_data = f.read()
        
    response = requests.post(url, headers=headers, data=audio_data, timeout=300)
    response.raise_for_status()
    
    data = response.json()
    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        if not transcript:
            raise Exception("La transcripción devuelta por Deepgram está vacía.")
        return transcript
    except KeyError:
        raise Exception("Estructura de respuesta inesperada en la API de Deepgram.")

def transcribir_con_gemini(ruta_audio, api_key):
    """
    Mecanismo de fallback: Sube el audio a la API de archivos de Google y lo procesa
    utilizando el modelo multimodal Gemini 2.5 Flash.
    """
    print("[GEMINI FALLBACK] Iniciando carga de audio en Google GenAI File API...")
    try:
        from google import genai
    except ImportError:
        raise Exception("La librería 'google-genai' no está instalada. Ejecute pip install google-genai.")
        
    client = genai.Client(api_key=api_key)
    
    # 1. Subir el archivo de audio a la File API
    uploaded_file = client.files.upload(file=ruta_audio)
    print(f"[GEMINI FALLBACK] Archivo subido. Nombre remoto: {uploaded_file.name}. Procesando...")
    
    # 2. Monitorear el procesamiento del archivo en los servidores de Google
    import time
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(5)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise Exception("El procesamiento del audio en la API de Google falló.")
        
    print("[GEMINI FALLBACK] Archivo activo. Generando transcripción con Gemini 2.5 Flash...")
    
    # 3. Solicitar la transcripción estructurada en español
    prompt = (
        "Sos un transcriptor profesional de clases académicas. Transcribí de forma completa "
        "y literal todo el audio adjunto en idioma español. Conservá las pausas naturales de "
        "la clase organizando el texto en párrafos legibles. No resumas nada."
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file, prompt]
    )
    
    # 4. Eliminar el archivo de los servidores de Google para proteger la privacidad
    try:
        client.files.delete(name=uploaded_file.name)
        print("[GEMINI FALLBACK] Archivo temporal remoto eliminado con éxito.")
    except Exception as cleanup_err:
        print(f"[WARN] No se pudo eliminar el archivo remoto: {cleanup_err}")
        
    return response.text

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/transcribir", methods=["POST"])
def transcribir():
    # Obtener metadatos del formulario
    materia = request.form.get("materia", "General").strip()
    clase = request.form.get("clase", "0").strip()
    fecha = request.form.get("fecha", "00-00-00").strip()
    tema = request.form.get("tema", "Sin Tema").strip()
    auto_process = request.form.get("auto_process") == "true"
    upload_notion = request.form.get("upload_notion") == "true"
    
    # Validar archivo de audio
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "No se proporcionó ningún archivo de audio."}), 400
        
    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"success": False, "error": "Nombre de archivo no válido."}), 400
        
    # Guardar archivo de audio de forma temporal
    temp_audio_path = os.path.join(UPLOAD_FOLDER, audio_file.filename)
    audio_file.save(temp_audio_path)
    
    api_key_deepgram = os.environ.get("DEEPGRAM_API_KEY")
    api_key_gemini = os.environ.get("GEMINI_API_KEY")
    
    transcripcion_texto = None
    proveedor_exitoso = None
    log_flujo = []
    
    # 1. Intentar con Deepgram Nova-3
    try:
        log_flujo.append("🎙️ Intentando transcripción principal con Deepgram Nova-3...")
        if not api_key_deepgram or api_key_deepgram.startswith("tu_clave"):
            raise Exception("API Key de Deepgram no configurada o no válida.")
        
        transcripcion_texto = transcribir_con_deepgram(temp_audio_path, api_key_deepgram)
        proveedor_exitoso = "Deepgram Nova-3"
        log_flujo.append("✅ Transcripción de Deepgram finalizada exitosamente.")
        
    except Exception as e:
        error_deepgram = str(e)
        log_flujo.append(f"⚠️ Fallo en el canal principal (Deepgram): {error_deepgram}")
        
        # 2. Fallback a Gemini 2.5 Flash
        try:
            log_flujo.append("🔄 Activando plan de contingencia: Transcripción con Gemini 2.5 Flash...")
            if not api_key_gemini or api_key_gemini.startswith("tu_clave"):
                raise Exception("API Key de Gemini no configurada o no válida.")
                
            transcripcion_texto = transcribir_con_gemini(temp_audio_path, api_key_gemini)
            proveedor_exitoso = "Gemini 2.5 Flash (Backup)"
            log_flujo.append("✅ Transcripción de contingencia con Gemini finalizada exitosamente.")
            
        except Exception as e_gemini:
            # Limpiar archivo temporal antes de salir
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            log_flujo.append(f"❌ Error crítico en el canal de respaldo (Gemini): {e_gemini}")
            return jsonify({
                "success": False,
                "error": "Ambos canales de transcripción fallaron.",
                "logs": log_flujo
            }), 500

    # Limpiar el archivo de audio temporal local
    if os.path.exists(temp_audio_path):
        os.remove(temp_audio_path)
        
    # Guardar la transcripción de forma permanente
    nombre_txt = f"Transcripcion_{materia}_Clase{clase}_{fecha}.txt"
    # Reemplazar espacios y caracteres problemáticos para el nombre del archivo
    nombre_txt = nombre_txt.replace(" ", "_")
    ruta_txt = os.path.join(TRANSCRIPT_FOLDER, nombre_txt)
    
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(transcripcion_texto)
        
    log_flujo.append(f"📁 Transcripción guardada localmente en: {nombre_txt}")
    
    generacion_apuntes_log = ""
    apuntes_exito = False
    
    # 3. Integración opcional con Fábrica de Apuntes (Proyecto 2)
    if auto_process:
        log_flujo.append("⚙️ Iniciando puente de integración con Fábrica de Apuntes (Proyecto 2)...")
        proyecto2_dir = os.path.join(os.path.dirname(BASE_DIR), "Proyecto 2 - Fabrica de Apuntes")
        script_generar = os.path.join(proyecto2_dir, "generar_apuntes.py")
        
        if not os.path.exists(script_generar):
            log_flujo.append("❌ Error: No se encontró el script 'generar_apuntes.py' en la ruta esperada.")
        else:
            # Construir comando para invocar generar_apuntes.py
            # python generar_apuntes.py <ruta_txt> --materia <materia> --clase <clase> --fecha <fecha> --tema <tema>
            cmd = [
                sys.executable,
                script_generar,
                ruta_txt,
                "--materia", materia,
                "--clase", clase,
                "--fecha", fecha,
                "--tema", tema
            ]
            
            if upload_notion:
                cmd.append("--upload")
                log_flujo.append("📤 Se solicitó la subida automática de apuntes a Notion.")
                
            try:
                # Ejecutar script secundario
                # Cambiar Cwd al directorio del Proyecto 2 para que lea su propio .env y config correctamente
                result = subprocess.run(
                    cmd,
                    cwd=proyecto2_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                generacion_apuntes_log = result.stdout + "\n" + result.stderr
                if result.returncode == 0:
                    apuntes_exito = True
                    log_flujo.append("✅ Apuntes académicos generados correctamente por la Fábrica de Apuntes.")
                else:
                    log_flujo.append("⚠️ Ocurrió un error en la ejecución del script de la Fábrica de Apuntes.")
            except Exception as cmd_err:
                log_flujo.append(f"❌ Error al ejecutar el script de apuntes: {cmd_err}")
                
    return jsonify({
        "success": True,
        "proveedor": proveedor_exitoso,
        "archivo_texto": nombre_txt,
        "logs": log_flujo,
        "apuntes_procesados": auto_process,
        "apuntes_exito": apuntes_exito,
        "apuntes_logs": generacion_apuntes_log
    })

if __name__ == "__main__":
    print(f"🚀 Iniciando servidor del Transcriptor de Audio...")
    print(f"Carpeta de transcripciones: {TRANSCRIPT_FOLDER}")
    app.run(host="127.0.0.1", port=5000, debug=True)
