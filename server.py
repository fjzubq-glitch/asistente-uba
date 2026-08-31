from flask import Flask, request, jsonify
import sys
import os
import time
import datetime
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import traceback
import re
import threading
from dotenv import load_dotenv

# Cargar variables de entorno de forma robusta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UBA_DIR = os.path.join(BASE_DIR, "Bot Telegram")
VERO_DIR = os.path.join(BASE_DIR, "Asistente Vero")

# Cargar .env de la raíz y de Vero
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(VERO_DIR, ".env"))

# URL base pública del servidor (sin barra final). Configurable por entorno.
WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_BASE_URL", "https://localhost:5000").rstrip("/")

app = Flask(__name__)

def ahora_argentina():
    """Devuelve el datetime actual en hora de Argentina (UTC-3)."""
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)


def formatear_fecha_humana(fecha_str):
    """Convierte una fecha ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM) al formato legible DD/MM/YYYY."""
    if not fecha_str:
        return ""
    try:
        if "T" in fecha_str:
            dt_obj = datetime.datetime.strptime(fecha_str[:16], "%Y-%m-%dT%H:%M")
            return dt_obj.strftime("%d/%m/%Y a las %H:%M hs")
        else:
            dt_obj = datetime.datetime.strptime(fecha_str.strip(), "%Y-%m-%d")
            return dt_obj.strftime("%d/%m/%Y")
    except Exception:
        return fecha_str

# ==========================================
# CONFIGURACIÓN GENERAL Y LLM (GROQ)
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "groq/compound-mini"

session = requests.Session()
retry = Retry(connect=3, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

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
    try:
        data = r.json()
    except ValueError:
        raise Exception(f"Fallo en API de Groq (Status {r.status_code}, respuesta no JSON): {r.text[:300]}")
    if r.status_code != 200 or "choices" not in data:
        raise Exception(f"Fallo en API de Groq (Status {r.status_code}): {data}")
    return data["choices"][0]["message"]["content"].strip()





# ==========================================
# BOT 1: ASISTENTE UBA (NOTION)
# ==========================================
TELEGRAM_TOKEN_UBA = os.environ.get("TELEGRAM_TOKEN")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID = os.environ.get("NOTION_DB_ID")

CHAT_ID_FILE_UBA = os.path.join(UBA_DIR, "chat_id.txt")
CHATS_FILE_UBA = os.path.join(UBA_DIR, "chats.json")
BUENOS_DIAS_STATE_UBA = os.path.join(UBA_DIR, "ultimo_buenos_dias.txt")
LOG_FILE_UBA = os.path.join(UBA_DIR, "bot_errors.log")

MI_CHAT_ID_UBA = "0"
if os.path.exists(CHAT_ID_FILE_UBA):
    try:
        with open(CHAT_ID_FILE_UBA, "r") as f:
            MI_CHAT_ID_UBA = f.read().strip()
    except Exception:
        pass


def _cargar_chats(path, legacy_file):
    """Carga la lista de chat_ids autorizados. Migra desde el archivo escalar legacy si es el primer uso."""
    chats = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                chats = [str(c) for c in data if str(c).strip()]
        except Exception:
            chats = []
    if not chats and legacy_file and os.path.exists(legacy_file):
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                legacy = f.read().strip()
            if legacy and legacy != "0":
                chats = [legacy]
                _guardar_chats(path, chats)
        except Exception:
            pass
    return chats


def _guardar_chats(path, chats):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chats, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _registrar_chat(path, legacy_file, chat_id):
    """Agrega un chat_id a la lista autorizada (idempotente) y devuelve la lista actualizada."""
    chats = _cargar_chats(path, legacy_file)
    if chat_id not in chats:
        chats.append(chat_id)
        _guardar_chats(path, chats)
    return chats


def buenos_dias_ya_enviado_hoy(state_file):
    if not os.path.exists(state_file):
        return False
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return f.read().strip() == ahora_argentina().strftime("%Y-%m-%d")
    except Exception:
        return False


def marcar_buenos_dias_enviado(state_file):
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            f.write(ahora_argentina().strftime("%Y-%m-%d"))
    except Exception:
        pass


def enviar_telegram_retry(send_url, payload, intentos=2, espera=2.0, timeout=10):
    """Envía un mensaje a Telegram con reintentos básicos. Devuelve True si se confirmó."""
    for i in range(intentos):
        try:
            r = session.post(send_url, json=payload, timeout=timeout)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        if i < intentos - 1:
            time.sleep(espera)
    return False


notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def registrar_error_uba(seccion):
    try:
        ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE_UBA, "a", encoding="utf-8") as f:
            f.write(f"\n[{ahora}] ERROR EN UBA: {seccion}\n")
            traceback.print_exc(file=f)
            f.write("----------------------------------------\n")
    except Exception:
        pass

def guardar_chat_id_uba(chat_id):
    global MI_CHAT_ID_UBA
    if MI_CHAT_ID_UBA != chat_id:
        MI_CHAT_ID_UBA = chat_id
        try:
            with open(CHAT_ID_FILE_UBA, "w") as f:
                f.write(MI_CHAT_ID_UBA)
        except Exception:
            registrar_error_uba("guardar_chat_id")
    _registrar_chat(CHATS_FILE_UBA, CHAT_ID_FILE_UBA, chat_id)

def transcribir_audio_uba(file_id):
    try:
        r1 = session.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN_UBA}/getFile?file_id={file_id}", timeout=15).json()
        file_path = r1["result"]["file_path"]
        r2 = session.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN_UBA}/{file_path}", timeout=20)
        temp_file = os.path.join(UBA_DIR, "audio_temp_uba.ogg")
        with open(temp_file, "wb") as f:
            f.write(r2.content)
        url_audio = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers_audio = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        with open(temp_file, "rb") as f:
            files = {"file": ("audio_temp_uba.ogg", f, "audio/ogg")}
            data = {"model": "whisper-large-v3-turbo"}
            r3 = session.post(url_audio, headers=headers_audio, files=files, data=data, timeout=30)
        os.remove(temp_file)
        return r3.json().get("text", "")
    except Exception:
        registrar_error_uba("transcribir_audio")
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
        registrar_error_uba("agendar_en_notion")
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
        registrar_error_uba("programar_active_recall")
        return False

def leer_pendientes_dia(fecha_str=None):
    try:
        if not fecha_str:
            fecha_str = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%Y-%m-%d")
        data = {
            "filter": {"property": "Fecha y Hora", "date": {"equals": fecha_str}},
            "sorts": [{"property": "Fecha y Hora", "direction": "ascending"}]
        }
        resp = session.post(f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query", headers=notion_headers, json=data, timeout=10)
        if resp.status_code != 200: return "❌ Hubo un error leyendo tu Notion."
        resultados = resp.json().get("results", [])
        fecha_formateada = formatear_fecha_humana(fecha_str)
        if not resultados: return f"🎉 ¡Día libre! No tienes nada agendado para el {fecha_formateada}."
        texto = f"📅 *Tu Agenda para el {fecha_formateada}:*\n\n"
        for item in resultados:
            props = item["properties"]
            asunto = props["Asunto"]["title"][0]["text"]["content"] if props["Asunto"]["title"] else "Sin nombre"
            estado = props["Estado"]["status"]["name"] if props["Estado"]["status"] else "Pendiente"
            fecha_item = props["Fecha y Hora"]["date"]["start"]
            hora = " a las " + fecha_item.split("T")[1][:5] if "T" in fecha_item else ""
            icono = "✅" if estado == "Completado" else "🔹"
            texto += f"{icono} {asunto}{hora}\n"
        return texto
    except Exception:
        registrar_error_uba("leer_pendientes_dia")
        return "❌ Error al intentar leer la agenda de Notion."

def cargar_chat_id_uba():
    global MI_CHAT_ID_UBA
    if os.path.exists(CHAT_ID_FILE_UBA):
        try:
            with open(CHAT_ID_FILE_UBA, "r") as f:
                MI_CHAT_ID_UBA = f.read().strip()
        except Exception:
            pass
    return MI_CHAT_ID_UBA


def ejecutar_ciclo_uba():
    """Un ciclo de alarmas del Asistente UBA. Diseñado para ser invocado una vez por proceso
    (desde un hilo o desde un cronjob), de forma idempotente."""
    global MI_CHAT_ID_UBA
    send_url_uba = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_UBA}/sendMessage"
    MI_CHAT_ID_UBA = cargar_chat_id_uba()
    chats = _cargar_chats(CHATS_FILE_UBA, CHAT_ID_FILE_UBA)
    if not chats:
        return
    try:
        ahora = ahora_argentina()
        hoy_str = ahora.strftime("%Y-%m-%d")

        # Buenos días (entre 8:00 y 8:09 ARG, una vez por día)
        if ahora.hour == 8 and ahora.minute < 10 and not buenos_dias_ya_enviado_hoy(BUENOS_DIAS_STATE_UBA):
            msg = f"🌅 *¡BUENOS DÍAS!*\n\n{leer_pendientes_dia()}"
            for chat in chats:
                enviar_telegram_retry(send_url_uba, {"chat_id": chat, "text": msg})
            marcar_buenos_dias_enviado(BUENOS_DIAS_STATE_UBA)

        # Recordatorios: eventos que vencen en los próximos 10 minutos
        data = {
            "filter": {"property": "Fecha y Hora", "date": {"equals": hoy_str}},
            "sorts": [{"property": "Fecha y Hora", "direction": "ascending"}]
        }
        resp = session.post(f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query", headers=notion_headers, json=data, timeout=10)
        if resp.status_code != 200:
            return
        for item in resp.json().get("results", []):
            props = item["properties"]
            estado = props["Estado"]["status"]["name"] if props["Estado"]["status"] else "Pendiente"
            if estado == "Completado":
                continue
            fecha_str = props["Fecha y Hora"]["date"]["start"]
            if "T" not in fecha_str:
                continue
            hora_evento = datetime.datetime.strptime(fecha_str[:16], "%Y-%m-%dT%H:%M")
            diff = hora_evento - ahora.replace(tzinfo=None)
            if 0 <= diff.total_seconds() <= 600:
                asunto = props["Asunto"]["title"][0]["text"]["content"]
                for chat in chats:
                    enviar_telegram_retry(send_url_uba, {"chat_id": chat, "text": f"🚨 *¡RECORDATORIO!* 🚨\n\n👉 {asunto}"})
                session.patch(f"https://api.notion.com/v1/pages/{item['id']}", headers=notion_headers, json={"properties": {"Estado": {"status": {"name": "Completado"}}}})
    except Exception:
        registrar_error_uba("ciclo_uba")


def revisar_alarmas_uba():
    """Bucle continuo que mantiene los ciclos de alarma (modo compatible por hilo)."""
    while True:
        ejecutar_ciclo_uba()
        time.sleep(60)


# ==========================================
# BOT 2: ASISTENTE PARA VERO (GOOGLE CALENDAR & PROMOS)
# ==========================================
sys.path.append(VERO_DIR)
try:
    import google_calendar as gc
    import buscador_ofertas as bo
    VEROS_MODULOS_OK = True
except Exception:
    gc = None
    bo = None
    VEROS_MODULOS_OK = False

TELEGRAM_TOKEN_VERO = os.environ.get("VERO_TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_TOKEN")

CHAT_ID_FILE_VERO = os.path.join(VERO_DIR, "chat_id.txt")
CHATS_FILE_VERO = os.path.join(VERO_DIR, "chats.json")
BUENOS_DIAS_STATE_VERO = os.path.join(VERO_DIR, "ultimo_buenos_dias.txt")
LOG_FILE_VERO = os.path.join(VERO_DIR, "bot_errors.log")

MI_CHAT_ID_VERO = "0"
if os.path.exists(CHAT_ID_FILE_VERO):
    try:
        with open(CHAT_ID_FILE_VERO, "r") as f:
            MI_CHAT_ID_VERO = f.read().strip()
    except Exception:
        pass

def registrar_error_vero(seccion):
    try:
        ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE_VERO, "a", encoding="utf-8") as f:
            f.write(f"\n[{ahora}] ERROR EN VERO: {seccion}\n")
            traceback.print_exc(file=f)
            f.write("----------------------------------------\n")
    except Exception:
        pass

def guardar_chat_id_vero(chat_id):
    global MI_CHAT_ID_VERO
    if MI_CHAT_ID_VERO != chat_id:
        MI_CHAT_ID_VERO = chat_id
        try:
            with open(CHAT_ID_FILE_VERO, "w") as f:
                f.write(MI_CHAT_ID_VERO)
        except Exception:
            registrar_error_vero("guardar_chat_id")
    _registrar_chat(CHATS_FILE_VERO, CHAT_ID_FILE_VERO, chat_id)

def transcribir_audio_vero(file_id):
    try:
        r1 = session.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN_VERO}/getFile?file_id={file_id}", timeout=15).json()
        file_path = r1["result"]["file_path"]
        r2 = session.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN_VERO}/{file_path}", timeout=20)
        temp_file = os.path.join(VERO_DIR, "audio_temp_vero.ogg")
        with open(temp_file, "wb") as f:
            f.write(r2.content)
        url_audio = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers_audio = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        with open(temp_file, "rb") as f:
            files = {"file": ("audio_temp_vero.ogg", f, "audio/ogg")}
            data = {"model": "whisper-large-v3-turbo"}
            r3 = session.post(url_audio, headers=headers_audio, files=files, data=data, timeout=30)
        os.remove(temp_file)
        return r3.json().get("text", "")
    except Exception:
        registrar_error_vero("transcribir_audio")
        return ""

def cargar_chat_id_vero():
    global MI_CHAT_ID_VERO
    if os.path.exists(CHAT_ID_FILE_VERO):
        try:
            with open(CHAT_ID_FILE_VERO, "r") as f:
                MI_CHAT_ID_VERO = f.read().strip()
        except Exception:
            pass
    return MI_CHAT_ID_VERO


def ejecutar_ciclo_vero():
    """Un ciclo de alarmas del Asistente Vero. Idempotente, apto para hilo o cronjob."""
    if not VEROS_MODULOS_OK:
        return
    global MI_CHAT_ID_VERO
    send_url_vero = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_VERO}/sendMessage"
    MI_CHAT_ID_VERO = cargar_chat_id_vero()
    chats = _cargar_chats(CHATS_FILE_VERO, CHAT_ID_FILE_VERO)
    if not chats:
        return
    try:
        ahora = ahora_argentina()
        hoy_str = ahora.strftime("%Y-%m-%d")

        # Buenos días (entre 8:00 y 8:09 ARG, una vez por día)
        if ahora.hour == 8 and ahora.minute < 10 and not buenos_dias_ya_enviado_hoy(BUENOS_DIAS_STATE_VERO):
            try:
                eventos = gc.listar_eventos_dia(hoy_str)
            except Exception:
                eventos = None
            if eventos is None:
                agenda_text = "❌ (No pude conectar a Google Calendar)"
            elif not eventos:
                agenda_text = "🎉 ¡Hoy no tienes ningún evento agendado!"
            else:
                agenda_text = "📅 *Tu agenda para hoy:*\n"
                for ev in eventos:
                    start = ev["start"].get("dateTime", ev["start"].get("date"))
                    summary = ev.get("summary", "Sin título")
                    hora = ""
                    if "T" in start:
                        hora = " a las " + start.split("T")[1][:5]
                    agenda_text += f" • {summary}{hora}\n"

            dia_semana = bo.obtener_dia_espanol(ahora)
            promos = bo.obtener_promos_dia(dia_semana)
            promos_text = bo.formatear_promos_mensaje(promos, None, dia_semana)

            msg = f"🌅 *¡BUENOS DÍAS VERO!*\n\n{agenda_text}\n\n-----------------------------------\n\n{promos_text}"
            for chat in chats:
                enviar_telegram_retry(send_url_vero, {"chat_id": chat, "text": msg, "parse_mode": "Markdown"})
            marcar_buenos_dias_enviado(BUENOS_DIAS_STATE_VERO)
    except Exception:
        registrar_error_vero("ciclo_vero")


def revisar_alarmas_vero():
    """Bucle continuo que mantiene los ciclos de alarma (modo compatible por hilo)."""
    while True:
        ejecutar_ciclo_vero()
        time.sleep(60)


# ==========================================
# MANEJADOR DE HILOS UNIFICADO
# ==========================================
hilo_uba_iniciado = False
hilo_vero_iniciado = False

def asegurar_hilos_alarmas():
    global hilo_uba_iniciado, hilo_vero_iniciado
    if not hilo_uba_iniciado:
        hilo_uba = threading.Thread(target=revisar_alarmas_uba, daemon=True)
        hilo_uba.start()
        hilo_uba_iniciado = True
    if not hilo_vero_iniciado:
        hilo_vero = threading.Thread(target=revisar_alarmas_vero, daemon=True)
        hilo_vero.start()
        hilo_vero_iniciado = True


# ==========================================
# RUTAS DE FLASK
# ==========================================

# 1. Ruta para el bot UBA
@app.route(f"/{TELEGRAM_TOKEN_UBA}", methods=["POST"])
def webhook_handler_uba():
    asegurar_hilos_alarmas()
    try:
        update = request.get_json()
        if not update or "message" not in update:
            return "OK", 200
            
        msg = update["message"]
        if "chat" not in msg:
            return "OK", 200
            
        chat_id = str(msg["chat"]["id"])
        guardar_chat_id_uba(chat_id)
        
        text = ""
        send_url_uba = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_UBA}/sendMessage"
        if "voice" in msg:
            session.post(send_url_uba, json={"chat_id": chat_id, "text": "🎙️ Escuchando audio..."}, timeout=10)
            text = transcribir_audio_uba(msg["voice"]["file_id"])
        else:
            text = msg.get("text", "")
            
        if text:
            ahora = ahora_argentina()
            SYSTEM_PROMPT = f"""Eres un asistente personal y de estudios inteligente y eficiente. Fecha actual: {ahora.strftime("%Y-%m-%dT%H:%M:00-03:00")}.
REGLAS:
1. Agendar evento: Responde EXCLUSIVAMENTE: AGENDAR: Asunto|YYYY-MM-DDTHH:MM:00-03:00
2. Leer agenda de un día: Responde EXCLUSIVAMENTE: LEER_DIA: YYYY-MM-DD
   (Ejemplo para hoy, mañana o cualquier otro día, calcula la fecha correcta: LEER_DIA: 2026-07-11)
3. Active Recall: Responde EXCLUSIVAMENTE: ACTIVE_RECALL: Tema
4. Asistencia personal: Responde a cualquier otra consulta de forma concisa y servicial, ayudando al usuario con sus estudios y tareas diarias.
5. NO uses formato markdown."""
            
            try:
                ia_text = llamar_llm(SYSTEM_PROMPT, text)
                match_agendar = re.search(r"AGENDAR:\s*(.*?)\|(.*?)(?:>|$)", ia_text)
                match_leer_dia = re.search(r"LEER_DIA:\s*([\d-]+)", ia_text)
                match_active_recall = re.search(r"ACTIVE_RECALL:\s*(.*?)(?:>|$)", ia_text)
                
                if match_agendar:
                    asunto = match_agendar.group(1).strip()
                    fecha = match_agendar.group(2).strip().rstrip(">").strip()
                    exito = agendar_en_notion(asunto, fecha)
                    fecha_formateada = formatear_fecha_humana(fecha)
                    reply_text = f"✅ ¡Anotado!\n📌 {asunto}\n🕒 Para: {fecha_formateada}" if exito else "❌ Error guardando en Notion."
                elif match_leer_dia:
                    fecha_dia = match_leer_dia.group(1).strip()
                    reply_text = leer_pendientes_dia(fecha_dia)
                elif match_active_recall:
                    tema = match_active_recall.group(1).strip().rstrip(">").strip()
                    session.post(send_url_uba, json={"chat_id": chat_id, "text": f"🧠 ¡Activando Repetición Espaciada para '{tema}'!"}, timeout=10)
                    reply_text = f"✅ ¡Listo! Alertas programadas para Día 3, 7 y 21." if programar_active_recall(tema) else "❌ Error en Notion."
                else:
                    reply_text = f"⚖️ {ia_text}"
            except Exception:
                registrar_error_uba("procesar_mensaje_ia")
                reply_text = "❌ Error procesando el mensaje."
                
            session.post(send_url_uba, json={"chat_id": chat_id, "text": reply_text}, timeout=400)
    except Exception:
        registrar_error_uba("webhook_handler_uba")
    return "OK", 200


# 2. Ruta para el bot de Vero
@app.route(f"/{TELEGRAM_TOKEN_VERO}", methods=["POST"])
def webhook_handler_vero():
    asegurar_hilos_alarmas()
    if not VEROS_MODULOS_OK:
        return "OK", 200
    try:
        update = request.get_json()
        if not update:
            return "OK", 200
            
        if "callback_query" in update:
            callback = update["callback_query"]
            chat_id = str(callback["message"]["chat"]["id"])
            callback_data = callback.get("data", "")
            
            # Responder al callback para quitar el estado de carga en Telegram
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_VERO}/answerCallbackQuery"
            session.post(answer_url, json={"callback_query_id": callback["id"]}, timeout=10)
            
            send_url_vero = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_VERO}/sendMessage"
            
            if callback_data == "menu:agenda":
                msg_text = "📅 *¿Qué día deseas consultar de tu agenda?*"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🌞 Ver Hoy", "callback_data": "agenda:hoy"}],
                        [{"text": "🌅 Ver Mañana", "callback_data": "agenda:manana"}]
                    ]
                }
                session.post(send_url_vero, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                
            elif callback_data == "menu:supermercados":
                msg_text = "🛒 *Selecciona un supermercado para ver la información:*"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "COTO 🛒", "callback_data": "super:coto"}],
                        [{"text": "Carrefour 🛍️", "callback_data": "super:carrefour"}],
                        [{"text": "Día 🔴", "callback_data": "super:dia"}]
                    ]
                }
                session.post(send_url_vero, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                
            elif callback_data.startswith("agenda:"):
                dia_tipo = callback_data.split(":")[1]
                ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
                if dia_tipo == "hoy":
                    fecha_dia = ahora.strftime("%Y-%m-%d")
                else:
                    fecha_dia = (ahora + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    
                eventos = gc.listar_eventos_dia(fecha_dia)
                if eventos is None:
                    reply_text = "❌ Error al leer Google Calendar. Verifica que la cuenta esté vinculada."
                elif not eventos:
                    fecha_formateada = formatear_fecha_humana(fecha_dia)
                    reply_text = f"🎉 ¡Día libre! No tienes nada agendado para el {fecha_formateada}."
                else:
                    fecha_formateada = formatear_fecha_humana(fecha_dia)
                    reply_text = f"📅 *Tu agenda para el {fecha_formateada}:*\n\n"
                    for ev in eventos:
                        start = ev['start'].get('dateTime', ev['start'].get('date'))
                        summary = ev.get('summary', 'Sin título')
                        hora = ""
                        if 'T' in start:
                            hora = " a las " + start.split('T')[1][:5]
                        reply_text += f"🔹 {summary}{hora}\n"
                session.post(send_url_vero, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
                
            elif callback_data.startswith("super:"):
                super_key = callback_data.split(":")[1]
                super_display = super_key.capitalize()
                if super_display.lower() == "dia":
                    super_display = "Día"
                msg_text = f"🛍️ *¿Qué información necesitas de {super_display}?*"
                
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "💳 Descuentos Bancarios", "callback_data": f"info:{super_key}:promos"}],
                        [{"text": "🛒 Ofertas de Productos", "callback_data": f"info:{super_key}:productos"}]
                    ]
                }
                session.post(send_url_vero, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                
            elif callback_data.startswith("info:"):
                parts = callback_data.split(":")
                super_key = parts[1]
                info_type = parts[2]
                
                if info_type == "promos":
                    promos_hoy = bo.buscar_promociones_filtradas(super_key, "hoy")
                    reply_text = bo.formatear_promos_mensaje(promos_hoy, super_key, "hoy")
                    
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "📅 Ver resto de la semana", "callback_data": f"rest_promos:{super_key}"}
                            ]
                        ]
                    }
                    session.post(send_url_vero, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                else:
                    productos = bo.buscar_productos_filtrados(super_key)
                    reply_text = bo.formatear_productos_mensaje(productos, super_key)
                    session.post(send_url_vero, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
                    
            elif callback_data.startswith("rest_promos:"):
                super_key = callback_data.split(":")[1]
                promos = bo.buscar_promociones_filtradas(super_key, "todos")
                dia_hoy = bo.obtener_dia_espanol()
                promos_otros = [p for p in promos if dia_hoy not in [d.lower().strip() for d in p.get("dias", [])]]
                
                reply_text = bo.formatear_promos_mensaje(promos_otros, super_key, "resto")
                session.post(send_url_vero, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
                
            return "OK", 200
            
        if "message" not in update:
            return "OK", 200
            
        msg = update["message"]
        if "chat" not in msg:
            return "OK", 200
            
        chat_id = str(msg["chat"]["id"])
        guardar_chat_id_vero(chat_id)
        
        text = ""
        send_url_vero = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_VERO}/sendMessage"
        if "voice" in msg:
            session.post(send_url_vero, json={"chat_id": chat_id, "text": "🎙️ Escuchando tu audio..."}, timeout=10)
            text = transcribir_audio_vero(msg["voice"]["file_id"])
        else:
            text = msg.get("text", "")
            
        if text:
            # Comando secreto de diagnostico para probar el estado del proxy en caliente
            if text.lower().strip() == "diagnostico_proxy":
                cwd = os.getcwd()
                files_in_cwd = os.listdir(cwd)
                
                env_exists = os.path.exists(os.path.join(BASE_DIR, ".env"))
                env_in_vero = os.path.exists(os.path.join(VERO_DIR, ".env"))
                
                env_lines = []
                if env_exists:
                    try:
                        with open(os.path.join(BASE_DIR, ".env"), "r", encoding="utf-8") as f:
                            for l in f:
                                l_strip = l.strip()
                                if l_strip and not l_strip.startswith("#"):
                                    parts = l_strip.split("=", 1)
                                    key = parts[0].strip()
                                    val = parts[1].strip() if len(parts) > 1 else ""
                                    anon_val = val[:5] + "..." if len(val) > 5 else "***"
                                    env_lines.append(f"• `{key}={anon_val}`")
                    except Exception as ex:
                        env_lines.append(f"Error leyendo .env: {ex}")
                else:
                    env_lines.append("No se encontró el archivo `.env` en la raíz.")
                
                proxy_url = os.environ.get("GOOGLE_SCRIPT_PROXY_URL")
                has_proxy = bool(proxy_url)
                proxy_snippet = proxy_url[:40] + "..." if has_proxy else "Ninguno"
                
                test_status = "No testeado"
                if has_proxy:
                    try:
                        r_test = requests.get(proxy_url.strip() + "?url=https%3A%2F%2Fsuperprecio.ar%2Fsearchgrouped%3Fsearch%3Dleche", timeout=12)
                        test_status = f"Status {r_test.status_code}, Length {len(r_test.text)}"
                        if "product-row" in r_test.text:
                            test_status += " (HTML con product-rows)"
                        else:
                            test_status += " (HTML sin product-rows)"
                    except Exception as ex:
                        test_status = f"Error: {ex}"
                
                interesantes = [f for f in files_in_cwd if f.startswith(".") or "env" in f.lower() or f.endswith(".py") or f.endswith(".txt")]
                
                reply = (
                    f"⚙️ *Diagnóstico del Proxy de Vero:*\n\n"
                    f"• *Cwd:* `{cwd}`\n"
                    f"• *Archivo:* `{__file__}`\n"
                    f"• *Proxy Configurado:* `{has_proxy}`\n"
                    f"• *URL del Proxy:* `{proxy_snippet}`\n"
                    f"• *Prueba de conexión:* `{test_status}`\n\n"
                    f"• *Archivos encontrados:* `{', '.join(interesantes)}`\n"
                    f"• *¿Existe .env en raíz?:* `{env_exists}`\n"
                    f"• *¿Existe .env en subcarpeta?:* `{env_in_vero}`\n\n"
                    f"📋 *Contenido de .env (anonimizado):*\n" + "\n".join(env_lines)
                )
                session.post(send_url_vero, json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"}, timeout=10)
                return "OK", 200

        if text:
            ahora = ahora_argentina()
            
            SYSTEM_PROMPT = f"""Eres un asistente personal inteligente, cálido y eficiente para Vero. Fecha y hora actuales: {ahora.strftime("%Y-%m-%dT%H:%M:00-03:00")}.
Tu objetivo es ayudarla a gestionar su agenda en Google Calendar y recordar las ofertas de supermercados.

REGLAS DE RESPUESTA EXCLUSIVA PARA COMANDOS (Si detectas una acción, responde ÚNICAMENTE el comando correspondiente):
1. Agendar evento: Si el usuario quiere guardar algo en el calendario, responde EXACTAMENTE así:
   AGENDAR: Asunto|YYYY-MM-DDTHH:MM:00-03:00|DuracionMinutos|Descripcion
   (Ejemplo: AGENDAR: Turno Dentista|2026-07-15T10:00:00-03:00|60|Turno con el Dr. Pérez)
2. Leer agenda de un día: Si el usuario quiere saber sus eventos de un día específico, responde EXACTAMENTE así:
   LEER_DIA: YYYY-MM-DD
   (Ejemplo para hoy: LEER_DIA: {ahora.strftime("%Y-%m-%d")})
3. Consultar promociones/descuentos bancarios: Si el usuario pregunta por descuentos de tarjetas, bancos o reintegros generales de los supermercados, responde EXACTAMENTE así:
   LEER_PROMOS: Supermercado|DiaDeLaSemana
   (Donde Supermercado puede ser coto, carrefour, día, o todos. DiaDeLaSemana puede ser hoy, lunes, martes, miércoles, jueves, viernes, sábado, domingo, o todos. Ejemplo: LEER_PROMOS: coto|hoy, LEER_PROMOS: todos|miércoles)
4. Agregar promoción/descuento: Si el usuario quiere guardar una nueva promoción bancaria, responde EXACTAMENTE así:
   AGREGAR_PROMO: Supermercado|Banco o Tarjeta|Descuento|DiaDeLaSemana|Condiciones
   (Ejemplo: AGREGAR_PROMO: Carrefour|Mercado Pago|10% de ahorro|martes|Con tarjeta prepaga)
5. Consultar ofertas en productos: Si el usuario pregunta por ofertas de productos específicos (ej. leche, aceite, fideos, yerba, qué mercadería está barata), responde EXACTAMENTE así:
   LEER_PRODUCTOS: Supermercado
   (Donde Supermercado puede ser coto, carrefour, día, o todos. Ejemplo: LEER_PRODUCTOS: coto, LEER_PRODUCTOS: todos)
6. Agregar oferta de producto: Si el usuario quiere registrar un precio u oferta de un producto (ej. 'anotá que la leche en Día está a $920'), responde EXACTAMENTE así:
   AGREGAR_PRODUCTO: Supermercado|Producto|Precio|Condiciones
   (Ejemplo: AGREGAR_PRODUCTO: Día|Leche Sachet|$920|Club Dia)
7. Mostrar menú inicial de opciones: Si el usuario saluda, dice 'hola', 'buenas', 'menú', 'start', o pregunta de forma genérica qué puede hacer, responde EXACTAMENTE así:
   MOSTRAR_MENU_INICIAL
8. Buscar producto específico en oferta: Si el usuario pregunta dónde hay oferta de un alimento o producto específico (ej: 'dónde hay asado barato?', 'buscá ofertas de leche', 'precios de fideos'), responde EXACTAMENTE así:
   BUSCAR_PRODUCTO: Termino
   (Donde Termino es la palabra clave del producto a buscar. Ejemplo: BUSCAR_PRODUCTO: asado, BUSCAR_PRODUCTO: leche)
9. Consultar enlaces oficiales de billeteras o supermercados: Si el usuario pide enlaces, links, páginas web, Facebook o Instagram de billeteras virtuales (Mercado Pago, Cuenta DNI, MODO, Ualá, Personal Pay, Brubank) o supermercados (Coto, Carrefour, Día), responde EXACTAMENTE así:
   LEER_ENLACES: BilleteraOSupermercado
   (Donde BilleteraOSupermercado es la clave a buscar. Claves disponibles: mercadopago, cuentadni, modo, uala, personalpay, brubank, coto, carrefour, dia, o todos. Ejemplo: LEER_ENLACES: mercadopago, LEER_ENLACES: todos)

REGLAS PARA CONVERSACIÓN GENERAL:
10. Si no coincide con ningún comando, responde de forma atenta, simpática y natural como su asistente personal, sin usar formato markdown sofisticado y en español.
11. Si te pide el Facebook, el Instagram o la página oficial de ofertas de Coto, Carrefour o Día, proporciónaselos amablemente con estos enlaces oficiales:
   - Coto: Web (https://www.coto.com.ar/descuentos/), Instagram (https://www.instagram.com/coto_ar/), Facebook (https://www.facebook.com/coto/)
   - Carrefour: Web (https://www.carrefour.com.ar/promociones), Instagram (https://www.instagram.com/carrefourargentina/), Facebook (https://www.facebook.com/CarrefourArgentina/)
   - Día: Web (https://diaonline.supermercadosdia.com.ar/), Instagram (https://www.instagram.com/diaargentina/), Facebook (https://www.facebook.com/DiaArgentina/)"""
            
            try:
                ia_text = llamar_llm(SYSTEM_PROMPT, text)
                reply_text = ""
                
                match_agendar = re.search(r"AGENDAR:\s*(.*)", ia_text)
                match_leer_dia = re.search(r"LEER_DIA:\s*([\d-]+)", ia_text)
                match_leer_promos = re.search(r"LEER_PROMOS:\s*([a-zA-ZáéíóúñÑ|]+)", ia_text)
                match_agregar_promo = re.search(r"AGREGAR_PROMO:\s*(.*)", ia_text)
                match_leer_productos = re.search(r"LEER_PRODUCTOS:\s*([a-zA-ZáéíóúñÑ]+)", ia_text)
                match_agregar_producto = re.search(r"AGREGAR_PRODUCTO:\s*(.*)", ia_text)
                match_mostrar_menu_inicial = re.search(r"MOSTRAR_MENU_INICIAL", ia_text)
                match_buscar_producto = re.search(r"BUSCAR_PRODUCTO:\s*(.*)", ia_text)
                match_leer_enlaces = re.search(r"LEER_ENLACES:\s*([a-zA-ZáéíóúñÑ]+)", ia_text)
                
                if match_agendar:
                    parts = match_agendar.group(1).strip().split("|")
                    if len(parts) >= 2:
                        asunto = parts[0].strip()
                        fecha = parts[1].strip()
                        duracion = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 60
                        desc = parts[3].strip() if len(parts) > 3 else "Agendado por Asistente Vero"
                        
                        link = gc.agendar_evento(asunto, fecha, duracion, desc)
                        if link:
                            fecha_formateada = formatear_fecha_humana(fecha)
                            reply_text = f"✅ ¡Anotado en tu calendario!\n📌 {asunto}\n🕒 Para: {fecha_formateada}\n🔗 Enlace: {link}"
                        else:
                            reply_text = "❌ Hubo un error al intentar agendar en Google Calendar. ¿Tienes el archivo credentials.json configurado?"
                    else:
                        reply_text = "❌ No pude entender el formato para agendar."
                        
                elif match_leer_dia:
                    fecha_dia = match_leer_dia.group(1).strip()
                    eventos = gc.listar_eventos_dia(fecha_dia)
                    if eventos is None:
                        reply_text = "❌ Error al leer Google Calendar."
                    elif not eventos:
                        fecha_formateada = formatear_fecha_humana(fecha_dia)
                        reply_text = f"🎉 ¡Día libre! No tienes nada agendado para el {fecha_formateada}."
                    else:
                        fecha_formateada = formatear_fecha_humana(fecha_dia)
                        reply_text = f"📅 *Tu agenda para el {fecha_formateada}:*\n\n"
                        for ev in eventos:
                            start = ev['start'].get('dateTime', ev['start'].get('date'))
                            summary = ev.get('summary', 'Sin título')
                            hora = ""
                            if 'T' in start:
                                hora = " a las " + start.split('T')[1][:5]
                            reply_text += f"🔹 {summary}{hora}\n"
                            
                elif match_leer_promos:
                    parts = match_leer_promos.group(1).strip().split("|")
                    supermercado = parts[0].strip() if len(parts) > 0 else "todos"
                    dia_semana = parts[1].strip() if len(parts) > 1 else "todos"
                    promos = bo.buscar_promociones_filtradas(supermercado, dia_semana)
                    reply_text = bo.formatear_promos_mensaje(promos, supermercado, dia_semana)
                    
                elif match_agregar_promo:
                    parts = match_agregar_promo.group(1).strip().split("|")
                    if len(parts) >= 4:
                        super_name = parts[0].strip()
                        banco_tarjeta = parts[1].strip()
                        descuento = parts[2].strip()
                        dias = parts[3].strip()
                        condiciones = parts[4].strip() if len(parts) > 4 else ""
                        
                        exito = bo.agregar_nueva_promo(super_name, banco_tarjeta, discount=descuento, dias=dias, condiciones=condiciones)
                        if exito:
                            reply_text = f"✅ ¡Promoción guardada!\n🛍️ {super_name}\n💳 {banco_tarjeta} ({descuento})\n📅 Días: {dias}"
                        else:
                            reply_text = "❌ Error al guardar la promoción."
                    else:
                        reply_text = "❌ Error al interpretar la promoción."
                        
                elif match_leer_productos:
                    supermercado = match_leer_productos.group(1).strip()
                    productos = bo.buscar_productos_filtrados(supermercado)
                    reply_text = bo.formatear_productos_mensaje(productos, supermercado)
                    
                elif match_agregar_producto:
                    parts = match_agregar_producto.group(1).strip().split("|")
                    if len(parts) >= 3:
                        super_name = parts[0].strip()
                        prod = parts[1].strip()
                        precio = parts[2].strip()
                        cond = parts[3].strip() if len(parts) > 3 else ""
                        exito = bo.agregar_nuevo_producto(super_name, prod, precio, cond)
                        if exito:
                            reply_text = f"✅ ¡Oferta de producto guardada!\n🛍️ {super_name}\n📦 {prod}: {precio}"
                        else:
                            reply_text = "❌ Error al guardar la oferta de producto."
                    else:
                        reply_text = "❌ Error al interpretar la oferta del producto."
                        
                elif match_mostrar_menu_inicial:
                    msg_text = "👋 *¡Hola Vero! ¿En qué te puedo ayudar hoy?*"
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "📅 Mi Agenda", "callback_data": "menu:agenda"}],
                            [{"text": "🛒 Supermercados", "callback_data": "menu:supermercados"}]
                        ]
                    }
                    session.post(send_url_vero, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                    reply_text = ""
                    
                elif match_buscar_producto:
                    termino = match_buscar_producto.group(1).strip()
                    locales, online = bo.buscar_productos_por_nombre(termino)
                    reply_text = bo.formatear_resultado_busqueda(locales, online, termino)
                    
                elif match_leer_enlaces:
                    filtro = match_leer_enlaces.group(1).strip()
                    reply_text = bo.formatear_enlaces_mensaje(filtro)
                    
                else:
                    reply_text = ia_text
                    
            except Exception:
                registrar_error_vero("procesar_mensaje_ia")
                reply_text = "❌ Ups, tuve un pequeño problema procesando tu mensaje."
                
            if reply_text:
                session.post(send_url_vero, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
    except Exception:
        registrar_error_vero("webhook_handler_vero")
    return "OK", 200


# 3. Ruta de Ping (Mantiene activos los hilos de alarmas)
@app.route("/ping", methods=["GET"])
def ping_handler():
    asegurar_hilos_alarmas()
    return f"OK - UBA Thread: {hilo_uba_iniciado} - Vero Thread: {hilo_vero_iniciado}", 200


# Ruta de diagnóstico de logs
@app.route("/logs", methods=["GET"])
def ver_logs():
    logs_uba = ""
    logs_vero = ""
    
    if os.path.exists(LOG_FILE_UBA):
        try:
            with open(LOG_FILE_UBA, "r", encoding="utf-8") as f:
                lineas = f.readlines()
                logs_uba = "".join(lineas[-100:])
        except Exception as e:
            logs_uba = f"Error leyendo logs UBA: {e}"
    else:
        logs_uba = "No existe el archivo de logs de UBA."
        
    if os.path.exists(LOG_FILE_VERO):
        try:
            with open(LOG_FILE_VERO, "r", encoding="utf-8") as f:
                lineas = f.readlines()
                logs_vero = "".join(lineas[-100:])
        except Exception as e:
            logs_vero = f"Error leyendo logs Vero: {e}"
    else:
        logs_vero = "No existe el archivo de logs de Vero."
        
    return f"--- LOGS UBA ---\n{logs_uba}\n\n--- LOGS VERO ---\n{logs_vero}", 200, {'Content-Type': 'text/plain; charset=utf-8'}


# 4. Ruta para registrar el Webhook de UBA
@app.route("/set_webhook", methods=["GET"])
def set_webhook_uba():
    webhook_url = f"{WEBHOOK_BASE_URL}/{TELEGRAM_TOKEN_UBA}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_UBA}/setWebhook?url={webhook_url}"
    try:
        r = requests.get(url, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 5. Ruta para registrar el Webhook de Vero
@app.route("/set_webhook_vero", methods=["GET"])
def set_webhook_vero():
    webhook_url = f"{WEBHOOK_BASE_URL}/{TELEGRAM_TOKEN_VERO}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_VERO}/setWebhook?url={webhook_url}"
    try:
        r = requests.get(url, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
