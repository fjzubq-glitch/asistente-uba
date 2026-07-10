from flask import Flask, request, jsonify
import sys
import os
import time
import datetime
import requests
import traceback
import re
import threading
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env local
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Archivos de persistencia local
CHAT_ID_FILE = os.path.join(BASE_DIR, "chat_id.txt")
LOG_FILE = os.path.join(BASE_DIR, "bot_errors.log")

# Agregar BASE_DIR al path para importar módulos locales
sys.path.append(BASE_DIR)
import google_calendar as gc
import buscador_ofertas as bo

# Cargar Chat ID
MI_CHAT_ID = "0"
if os.path.exists(CHAT_ID_FILE):
    try:
        with open(CHAT_ID_FILE, "r") as f:
            MI_CHAT_ID = f.read().strip()
    except Exception:
        pass

SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

session = requests.Session()

def registrar_error(seccion):
    """Registra el traceback de un error en un archivo local para depuración."""
    try:
        ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{ahora}] ERROR EN SECCIÓN (WEBHOOK): {seccion}\n")
            traceback.print_exc(file=f)
            f.write("----------------------------------------\n")
    except Exception:
        pass

def guardar_chat_id(chat_id):
    """Guarda el Chat ID de forma persistente."""
    global MI_CHAT_ID
    if MI_CHAT_ID != chat_id:
        MI_CHAT_ID = chat_id
        try:
            with open(CHAT_ID_FILE, "w") as f:
                f.write(MI_CHAT_ID)
        except Exception:
            registrar_error("guardar_chat_id")

def transcribir_audio(file_id):
    """Descarga un audio de Telegram y lo transcribe usando Groq Whisper."""
    try:
        r1 = session.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}", timeout=15).json()
        file_path = r1["result"]["file_path"]
        r2 = session.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}", timeout=20)
        temp_file = os.path.join(BASE_DIR, "audio_temp.ogg")
        with open(temp_file, "wb") as f:
            f.write(r2.content)
            
        url_audio = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers_audio = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        with open(temp_file, "rb") as f:
            files = {"file": ("audio_temp.ogg", f, "audio/ogg")}
            data = {"model": "whisper-large-v3-turbo"}
            r3 = session.post(url_audio, headers=headers_audio, files=files, data=data, timeout=30)
            
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return r3.json().get("text", "")
    except Exception:
        registrar_error("transcribir_audio")
        return ""

def llamar_llm(prompt_sistema, texto_usuario):
    """Realiza una consulta a Groq LLM."""
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

def revisar_alarmas():
    """Hilo de segundo plano para enviar notificaciones automáticas en la mañana."""
    global MI_CHAT_ID
    buenos_dias_enviado = False
    while True:
        # Recargar Chat ID del archivo por si otro hilo lo actualizó
        if os.path.exists(CHAT_ID_FILE):
            try:
                with open(CHAT_ID_FILE, "r") as f:
                    MI_CHAT_ID = f.read().strip()
            except Exception:
                pass

        if MI_CHAT_ID != "0":
            try:
                ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
                hoy_str = ahora.strftime("%Y-%m-%d")
                
                # Reporte Diario de Buenos Días a las 08:00 AM
                if ahora.hour == 8 and ahora.minute == 0 and not buenos_dias_enviado:
                    try:
                        eventos = gc.listar_eventos_dia(hoy_str)
                        if eventos is None:
                            agenda_text = "❌ (No pude conectar a Google Calendar)"
                        elif not eventos:
                            agenda_text = "🎉 ¡Hoy no tienes ningún evento agendado!"
                        else:
                            agenda_text = "📅 *Tu agenda para hoy:*\n"
                            for ev in eventos:
                                start = ev['start'].get('dateTime', ev['start'].get('date'))
                                summary = ev.get('summary', 'Sin título')
                                hora = ""
                                if 'T' in start:
                                    hora = " a las " + start.split('T')[1][:5]
                                agenda_text += f" • {summary}{hora}\n"
                    except Exception:
                        agenda_text = "❌ (Error leyendo Google Calendar)"
                        
                    dia_semana = bo.obtener_dia_espanol(ahora)
                    promos = bo.obtener_promos_dia(dia_semana)
                    promos_text = bo.formatear_promos_mensaje(promos, dia_semana)
                    
                    msg = f"🌅 *¡BUENOS DÍAS VERO!*\n\n{agenda_text}\n\n-----------------------------------\n\n{promos_text}"
                    session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
                    buenos_dias_enviado = True
                    
                if ahora.hour == 1:
                    buenos_dias_enviado = False
                    
            except Exception:
                registrar_error("revisar_alarmas")
        time.sleep(60)

hilo_iniciado = False
def asegurar_hilo_alarmas():
    """Asegura que el hilo de alarmas esté corriendo en segundo plano."""
    global hilo_iniciado
    if not hilo_iniciado:
        hilo = threading.Thread(target=revisar_alarmas, daemon=True)
        hilo.start()
        hilo_iniciado = True

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook_handler():
    """Manejador principal del Webhook enviado por Telegram."""
    asegurar_hilo_alarmas()
    try:
        update = request.get_json()
        if not update:
            return "No data", 400
            
        if "callback_query" in update:
            callback = update["callback_query"]
            chat_id = str(callback["message"]["chat"]["id"])
            callback_data = callback.get("data", "")
            
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            session.post(answer_url, json={"callback_query_id": callback["id"]}, timeout=10)
            
            if callback_data == "menu:agenda":
                msg_text = "📅 *¿Qué día deseas consultar de tu agenda?*"
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🌞 Ver Hoy", "callback_data": "agenda:hoy"},
                            {"text": "🌅 Ver Mañana", "callback_data": "agenda:manana"}
                        ]
                    ]
                }
                session.post(SEND_URL, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                
            elif callback_data == "menu:supermercados":
                msg_text = "🛒 *Selecciona un supermercado para ver la información:*"
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "COTO 🛒", "callback_data": "super:coto"},
                            {"text": "Carrefour 🛍️", "callback_data": "super:carrefour"},
                            {"text": "Día 🔴", "callback_data": "super:dia"}
                        ]
                    ]
                }
                session.post(SEND_URL, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                
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
                session.post(SEND_URL, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
                
            elif callback_data.startswith("super:"):
                super_key = callback_data.split(":")[1]
                super_display = super_key.capitalize()
                if super_display.lower() == "dia":
                    super_display = "Día"
                msg_text = f"🛍️ *¿Qué información necesitas de {super_display}?*"
                
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "💳 Descuentos Bancarios", "callback_data": f"info:{super_key}:promos"},
                            {"text": "🛒 Ofertas de Productos", "callback_data": f"info:{super_key}:productos"}
                        ]
                    ]
                }
                session.post(SEND_URL, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                
            elif callback_data.startswith("info:"):
                parts = callback_data.split(":")
                super_key = parts[1]
                info_type = parts[2]
                
                if info_type == "promos":
                    promos = bo.buscar_promociones_filtradas(super_key, "todos")
                    reply_text = bo.formatear_promos_mensaje(promos, super_key, "todos")
                else:
                    productos = bo.buscar_productos_filtrados(super_key)
                    reply_text = bo.formatear_productos_mensaje(productos, super_key)
                    
                session.post(SEND_URL, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
                
            return "OK", 200
            
        if "message" in update:
            msg = update["message"]
            if "chat" in msg:
                chat_id = str(msg["chat"]["id"])
                guardar_chat_id(chat_id)
                
                text = ""
                if "voice" in msg:
                    session.post(SEND_URL, json={"chat_id": MI_CHAT_ID, "text": "🎙️ Escuchando tu audio..."}, timeout=10)
                    text = transcribir_audio(msg["voice"]["file_id"])
                else:
                    text = msg.get("text", "")
                    
                if not text:
                    return "No text", 200
                    
                ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
                
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
   AGREGAR_PROMO: Supermercado|Banco o Tarjeta|Descuento|DiaDeLaSemana|Conditions
   (Ejemplo: AGREGAR_PROMO: Carrefour|Mercado Pago|10% de ahorro|martes|Con tarjeta prepaga)
5. Consultar ofertas en productos: Si el usuario pregunta por ofertas de productos específicos (ej. leche, aceite, fideos, yerba, qué mercadería está barata), responde EXACTAMENTE así:
   LEER_PRODUCTOS: Supermercado
   (Donde Supermercado puede ser coto, carrefour, día, o todos. Ejemplo: LEER_PRODUCTOS: coto, LEER_PRODUCTOS: todos)
6. Agregar oferta de producto: Si el usuario quiere registrar un precio u oferta de un producto, responde EXACTAMENTE así:
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
                                reply_text = f"✅ ¡Anotado en tu calendario!\n📌 {asunto}\n🕒 Para: {fecha}\n🔗 Enlace: {link}"
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
                            reply_text = f"🎉 ¡Día libre! No tienes nada agendado para el {fecha_dia}."
                        else:
                            reply_text = f"📅 *Tu agenda para el {fecha_dia}:*\n\n"
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
                            
                            exito = bo.agregar_nueva_promo(super_name, banco_tarjeta, descuento, dias, condiciones)
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
                                [
                                    {"text": "📅 Mi Agenda", "callback_data": "menu:agenda"},
                                    {"text": "🛒 Supermercados", "callback_data": "menu:supermercados"}
                                ]
                            ]
                        }
                        session.post(SEND_URL, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown", "reply_markup": keyboard}, timeout=10)
                        reply_text = ""
                        
                    elif match_buscar_producto:
                        termino = match_buscar_producto.group(1).strip()
                        productos = bo.buscar_productos_por_nombre(termino)
                        reply_text = bo.formatear_productos_mensaje(productos, f"que coinciden con '{termino}'")
                        
                    elif match_leer_enlaces:
                        filtro = match_leer_enlaces.group(1).strip()
                        reply_text = bo.formatear_enlaces_mensaje(filtro)
                        
                    else:
                        reply_text = ia_text
                        
                except Exception:
                    registrar_error("procesar_mensaje_ia")
                    reply_text = "❌ Ups, tuve un pequeño problema procesando tu mensaje."
                    
                if reply_text:
                    session.post(SEND_URL, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"}, timeout=10)
    except Exception:
        registrar_error("webhook_handler")
    return "OK", 200

@app.route("/ping", methods=["GET"])
def ping_handler():
    """Ruta para mantener activa la Web App en PythonAnywhere usando pings."""
    asegurar_hilo_alarmas()
    return f"OK - Thread active: {hilo_iniciado} - Chat ID: {MI_CHAT_ID}", 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    """Ruta de utilidad para registrar este webhook en Telegram."""
    webhook_url = f"https://franklinzg.pythonanywhere.com/{TELEGRAM_TOKEN}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    try:
        r = requests.get(url, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
