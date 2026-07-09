import sys
import os
import time
import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import traceback
import re
import threading
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")


# Archivos de persistencia y logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_ID_FILE = os.path.join(BASE_DIR, "chat_id.txt")
LOG_FILE = os.path.join(BASE_DIR, "bot_errors.log")

# Cargar Chat ID persistido si existe
MI_CHAT_ID = "0"
if os.path.exists(CHAT_ID_FILE):
    try:
        with open(CHAT_ID_FILE, "r") as f:
            MI_CHAT_ID = f.read().strip()
    except Exception:
        pass

URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}
session = requests.Session()

retry = Retry(connect=3, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

def registrar_error(seccion):
    """
    Registra el traceback de un error en un archivo local para depuración.
    """
    try:
        ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{ahora}] ERROR EN SECCIÓN: {seccion}\n")
            traceback.print_exc(file=f)
            f.write("----------------------------------------\n")
    except Exception:
        pass

def guardar_chat_id(chat_id):
    """
    Guarda el Chat ID del usuario de forma persistente.
    """
    global MI_CHAT_ID
    if MI_CHAT_ID != chat_id:
        MI_CHAT_ID = chat_id
        try:
            with open(CHAT_ID_FILE, "w") as f:
                f.write(MI_CHAT_ID)
        except Exception:
            registrar_error("guardar_chat_id")

def transcribir_audio(file_id):
    try:
        r1 = session.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}", timeout=15).json()
        file_path = r1["result"]["file_path"]
        r2 = session.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}", timeout=20)
        temp_file = "audio_temp.ogg"
        with open(temp_file, "wb") as f:
            f.write(r2.content)
        url_audio = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers_audio = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        with open(temp_file, "rb") as f:
            files = {"file": ("audio_temp.ogg", f, "audio/ogg")}
            data = {"model": "whisper-large-v3-turbo"}
            r3 = session.post(url_audio, headers=headers_audio, files=files, data=data, timeout=30)
        os.remove(temp_file)
        return r3.json().get("text", "")
    except Exception as e:
        registrar_error("transcribir_audio")
        return ""

def agendar_en_notion(asunto, fecha_iso):
    try:
        data = {
            "parent": {"database_id": NOTION_DB_ID},
            "properties": {
                "Asunto": {"title": [{"text": {"content": asunto}}]},
                "Fecha y Hora": {"date": {"start": fecha_iso}},
                "Estado": {"status": {"name": "Pendiente"}},
                "Prioridad": {"select": {"name": "Normal"}}
            }
        }
        resp = session.post("https://api.notion.com/v1/pages", headers=notion_headers, json=data, timeout=10)
        return resp.status_code == 200
    except Exception:
        registrar_error("agendar_en_notion")
        return False

def programar_active_recall(tema):
    try:
        ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
        fechas_estudio = [(3, 2), (7, 6), (21, 20)]
        exitos = 0
        for (dia_estudio, dia_previo) in fechas_estudio:
            fecha_noche_previa = ahora + datetime.timedelta(days=dia_previo)
            iso_noche = fecha_noche_previa.strftime(f"%Y-%m-%dT21:00:00-03:00")
            asunto_noche = f"¡Mañana toca repasar!: {tema} (Repaso Día {dia_estudio})"
            if agendar_en_notion(asunto_noche, iso_noche): exitos += 1
            fecha_manana = ahora + datetime.timedelta(days=dia_estudio)
            iso_manana = fecha_manana.strftime(f"%Y-%m-%dT08:00:00-03:00")
            asunto_manana = f"📚 A ESTUDIAR HOY: {tema} (Repaso Día {dia_estudio})"
            if agendar_en_notion(asunto_manana, iso_manana): exitos += 1
        return exitos == 6
    except Exception:
        registrar_error("programar_active_recall")
        return False

def leer_pendientes_hoy():
    try:
        hoy = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%Y-%m-%d")
        data = {
            "filter": {"property": "Fecha y Hora", "date": {"equals": hoy}},
            "sorts": [{"property": "Fecha y Hora", "direction": "ascending"}]
        }
        resp = session.post(f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query", headers=notion_headers, json=data, timeout=10)
        if resp.status_code != 200: return "❌ Hubo un error leyendo tu Notion."
        resultados = resp.json().get("results", [])
        if not resultados: return "🎉 ¡Día libre! No tienes nada agendado para hoy."
        texto = "📅 *Tu Agenda para Hoy:*\n\n"
        for item in resultados:
            props = item["properties"]
            asunto = props["Asunto"]["title"][0]["text"]["content"] if props["Asunto"]["title"] else "Sin nombre"
            estado = props["Estado"]["status"]["name"] if props["Estado"]["status"] else "Pendiente"
            fecha_str = props["Fecha y Hora"]["date"]["start"]
            hora = " a las " + fecha_str.split("T")[1][:5] if "T" in fecha_str else ""
            icono = "✅" if estado == "Completado" else "🔹"
            texto += f"{icono} {asunto}{hora}\n"
        return texto
    except Exception:
        registrar_error("leer_pendientes_hoy")
        return "❌ Error al intentar leer la agenda de Notion."

def revisar_alarmas():
    global MI_CHAT_ID
    buenos_dias_enviado = False
    while True:
        if MI_CHAT_ID != "0":
            try:
                ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
                hoy_str = ahora.strftime("%Y-%m-%d")
                
                # Reporte Buenos Días
                if ahora.hour == 8 and ahora.minute == 0 and not buenos_dias_enviado:
                    msg = f"🌅 *¡BUENOS DÍAS!*\n\n{leer_pendientes_hoy()}"
                    session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": msg}, timeout=10)
                    buenos_dias_enviado = True
                if ahora.hour == 1:
                    buenos_dias_enviado = False
                
                # Proceso de Alertas
                data = {
                    "filter": {"property": "Fecha y Hora", "date": {"equals": hoy_str}},
                    "sorts": [{"property": "Fecha y Hora", "direction": "ascending"}]
                }
                resp = session.post(f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query", headers=notion_headers, json=data, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json().get("results", []):
                        props = item["properties"]
                        estado = props["Estado"]["status"]["name"] if props["Estado"]["status"] else "Pendiente"
                        if estado != "Completado":
                            fecha_str = props["Fecha y Hora"]["date"]["start"]
                            if "T" in fecha_str:
                                hora_evento = datetime.datetime.strptime(fecha_str[:16], "%Y-%m-%dT%H:%M")
                                diff = hora_evento - ahora.replace(tzinfo=None)
                                if 0 <= diff.total_seconds() <= 600:
                                    asunto = props["Asunto"]["title"][0]["text"]["content"]
                                    session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": f"🚨 *¡RECORDATORIO!* 🚨\n\n👉 {asunto}"}, timeout=10)
                                    session.patch(f"https://api.notion.com/v1/pages/{item['id']}", headers=notion_headers, json={"properties": {"Estado": {"status": {"name": "Completado"}}}})
            except Exception:
                registrar_error("revisar_alarmas")
        time.sleep(60)

# Lanzar hilo de alarmas
threading.Thread(target=revisar_alarmas, daemon=True).start()

offset = None
try:
    resp = session.get(URL, timeout=10).json()
    if resp.get("ok") and resp.get("result"):
        offset = resp["result"][-1]["update_id"] + 1
except Exception:
    registrar_error("inicializar_offset")

def llamar_llm(prompt_sistema, texto_usuario):
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": texto_usuario}
        ],
        "temperature": 0.3
    }
    r = session.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=20)
    return r.json()["choices"][0]["message"]["content"].strip()

# Bucle principal de escucha
while True:
    try:
        req_url = f"{URL}?timeout=10"
        if offset:
            req_url += f"&offset={offset}"
        response = session.get(req_url, timeout=20).json()
        if response.get("ok") and response.get("result"):
            for msg in response["result"]:
                offset = msg["update_id"] + 1
                if "message" in msg and "chat" in msg["message"]:
                    chat_id = str(msg["message"]["chat"]["id"])
                    guardar_chat_id(chat_id)
                    
                    text = ""
                    if "voice" in msg["message"]:
                        session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": "🎙️ Escuchando audio..."}, timeout=10)
                        text = transcribir_audio(msg["message"]["voice"]["file_id"])
                    else:
                        text = msg["message"].get("text", "")
                    
                    if not text:
                        continue
                    
                    ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
                    SYSTEM_PROMPT = f"""Eres un asistente personal y de estudios inteligente y eficiente. Fecha actual: {ahora.strftime("%Y-%m-%dT%H:%M:00-03:00")}.
REGLAS:
1. Agendar evento: Responde EXCLUSIVAMENTE: AGENDAR: Asunto|YYYY-MM-DDTHH:MM:00-03:00
2. Leer agenda: Responde EXCLUSIVAMENTE: LEER_HOY
3. Active Recall: Responde EXCLUSIVAMENTE: ACTIVE_RECALL: Tema
4. Asistencia personal: Responde a cualquier otra consulta de forma concisa y servicial, ayudando al usuario con sus estudios y tareas diarias.
5. NO uses formato markdown."""
                    
                    try:
                        ia_text = llamar_llm(SYSTEM_PROMPT, text)
                        if "AGENDAR:" in ia_text:
                            match = re.search(r"AGENDAR:\s*(.*?)\|(.*?)(?:>|$)", ia_text)
                            if match:
                                asunto = match.group(1).strip()
                                fecha = match.group(2).strip().rstrip(">").strip()
                                exito = agendar_en_notion(asunto, fecha)
                                reply_text = f"✅ ¡Anotado!\n📌 {asunto}\n🕒 Para: {fecha}" if exito else "❌ Error guardando en Notion."
                            else: reply_text = "❌ Error entendiendo la fecha."
                        elif "ACTIVE_RECALL:" in ia_text:
                            match = re.search(r"ACTIVE_RECALL:\s*(.*?)(?:>|$)", ia_text)
                            if match:
                                tema = match.group(1).strip().rstrip(">").strip()
                                session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": f"🧠 ¡Activando Repetición Espaciada para '{tema}'!"}, timeout=10)
                                reply_text = f"✅ ¡Listo! Alertas programadas para Día 3, 7 y 21." if programar_active_recall(tema) else "❌ Error en Notion."
                            else: reply_text = "❌ Error procesando el active recall."
                        elif "LEER_HOY" in ia_text: reply_text = leer_pendientes_hoy()
                        else: reply_text = f"⚖️ {ia_text}"
                    except Exception:
                        registrar_error("procesar_mensaje_ia")
                        reply_text = "❌ Error procesando el mensaje."
                    
                    session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": reply_text}, timeout=10)
    except Exception:
        registrar_error("bucle_principal")
    time.sleep(1)
