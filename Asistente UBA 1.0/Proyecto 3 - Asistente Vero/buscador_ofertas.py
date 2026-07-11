import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
import urllib.parse

# Directorio base del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMOS_FILE = os.path.join(BASE_DIR, "promociones.json")
PRODUCTS_FILE = os.path.join(BASE_DIR, "productos_oferta.json")

def cargar_promos():
    """Carga las promociones del archivo JSON."""
    if not os.path.exists(PROMOS_FILE):
        return []
    try:
        with open(PROMOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando promociones: {e}")
        return []

def guardar_promos(promos):
    """Guarda las promociones en el archivo JSON."""
    try:
        with open(PROMOS_FILE, "w", encoding="utf-8") as f:
            json.dump(promos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando promociones: {e}")
        return False

def obtener_dia_espanol(dt=None):
    """Retorna el día de la semana actual en español y minúsculas."""
    if dt is None:
        # Asumimos zona horaria UTC-3 (Argentina)
        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return dias[dt.weekday()]

def obtener_promos_dia(dia_nombre=None):
    """
    Retorna la lista de promociones activas para un día de la semana específico.
    Si dia_nombre es None, usa el día actual.
    """
    if not dia_nombre:
        dia_nombre = obtener_dia_espanol()
    else:
        dia_nombre = dia_nombre.lower().strip()
        
    promos = cargar_promos()
    promos_filtradas = []
    for p in promos:
        if dia_nombre in [d.lower() for d in p.get("dias", [])]:
            promos_filtradas.append(p)
    return promos_filtradas

def agregar_nueva_promo(supermercado, banco_tarjeta, descuento, dias, condiciones=""):
    """
    Agrega una nueva promoción a la base de datos local.
    dias debe ser una lista de strings (ej: ['lunes', 'martes']) o un string separado por comas.
    """
    if isinstance(dias, str):
        dias = [d.strip().lower() for d in dias.split(",") if d.strip()]
    else:
        dias = [d.strip().lower() for d in dias]
        
    promos = cargar_promos()
    nueva = {
        "supermercado": supermercado.strip(),
        "banco_tarjeta": banco_tarjeta.strip(),
        "descuento": descuento.strip(),
        "dias": dias,
        "condiciones": condiciones.strip()
    }
    promos.append(nueva)
    return guardar_promos(promos)

def buscar_promos_web(query):
    """
    Intenta realizar una búsqueda web de ofertas y promociones usando DuckDuckGo HTML.
    Tiene manejo de excepciones y retorna una lista de resultados si tiene éxito.
    """
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.8"
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            results = []
            result_divs = soup.find_all('div', class_='result')
            for div in result_divs[:5]:
                title_a = div.find('a', class_='result__url')
                snippet_a = div.find('a', class_='result__snippet')
                if title_a:
                    title = title_a.get_text(strip=True)
                    link = title_a.get('href')
                    snippet = snippet_a.get_text(strip=True) if snippet_a else ""
                    results.append({
                        "title": title,
                        "link": link,
                        "snippet": snippet
                    })
            return results
        else:
            print(f"Búsqueda web falló con status {r.status_code}")
            return []
    except Exception as e:
        print(f"Error realizando búsqueda web: {e}")
        return []

def buscar_promociones_filtradas(supermercado=None, dia=None):
    """
    Busca promociones en la base de datos local filtrando por supermercado y/o día de la semana.
    """
    promos = cargar_promos()
    
    if supermercado and supermercado.lower().strip() != "todos":
        super_name = supermercado.lower().strip()
        if super_name == "dia":
            super_name = "día"
        promos = [p for p in promos if p.get("supermercado", "").lower().strip() == super_name]
        
    if dia and dia.lower().strip() != "todos":
        dia_name = dia.lower().strip()
        if dia_name == "hoy":
            dia_name = obtener_dia_espanol()
        promos = [p for p in promos if dia_name in [d.lower().strip() for d in p.get("dias", [])]]
        
    return promos

def formatear_promos_mensaje(promos, supermercado=None, dia=None):
    """Formatea la lista de promociones a un formato legible para Telegram, priorizando el día actual."""
    label_super = f" de {supermercado.upper()}" if supermercado and supermercado.lower() != "todos" else ""
    label_dia = f" para el día {dia.upper()}" if dia and dia.lower() != "todos" else ""
    
    if not promos:
        return f"🎉 ¡No encontré promociones cargadas{label_super}{label_dia}! Puedes agregar una diciendo, por ejemplo: 'Agregá promo Coto Banco Nación 30% los miércoles'."
        
    if dia == "resto":
        msg = f"📅 *Descuentos{label_super} para el resto de la semana:*\n\n"
        grouped_otros = {}
        for p in promos:
            s_name = p.get("supermercado", "Otros")
            if s_name not in grouped_otros:
                grouped_otros[s_name] = []
            grouped_otros[s_name].append(p)
            
        for super_key, lista in grouped_otros.items():
            msg += f"🔸 *{super_key.upper()}*\n"
            for p in lista:
                dias_str = ", ".join(p.get("dias", []))
                msg += f"  • *{p.get('descuento')}* con *{p.get('banco_tarjeta')}* (Días: {dias_str})\n"
                if p.get("condiciones"):
                    msg += f"    _({p.get('condiciones')})_\n"
        return msg.strip()
        
    dia_hoy = obtener_dia_espanol()
    
    # Separar promociones de hoy y del resto de la semana
    promos_hoy = []
    promos_otros = []
    
    for p in promos:
        dias_p = [d.lower().strip() for d in p.get("dias", [])]
        if dia_hoy in dias_p:
            promos_hoy.append(p)
        else:
            promos_otros.append(p)
            
    msg = f"🛒 *Promociones de Supermercados{label_super}:*\n\n"
    
    # 1. Mostrar las de hoy primero
    if promos_hoy:
        msg += f"📌 *DESCUENTOS PARA HOY ({dia_hoy.upper()}):*\n"
        grouped_hoy = {}
        for p in promos_hoy:
            s_name = p.get("supermercado", "Otros")
            if s_name not in grouped_hoy:
                grouped_hoy[s_name] = []
            grouped_hoy[s_name].append(p)
            
        for super_key, lista in grouped_hoy.items():
            msg += f"🔸 *{super_key.upper()}*\n"
            for p in lista:
                msg += f"  • *{p.get('descuento')}* con *{p.get('banco_tarjeta')}*\n"
                if p.get("condiciones"):
                    msg += f"    _({p.get('condiciones')})_\n"
        msg += "\n"
        
    # 2. Mostrar las del resto de la semana
    # Si el usuario solicitó específicamente "hoy" o "resto", no mostramos el resto general.
    if promos_otros and (dia is None or (dia.lower().strip() != "hoy" and dia.lower().strip() != "resto")):
        msg += "📅 *DESCUENTOS PARA EL RESTO DE LA SEMANA:*\n"
        grouped_otros = {}
        for p in promos_otros:
            s_name = p.get("supermercado", "Otros")
            if s_name not in grouped_otros:
                grouped_otros[s_name] = []
            grouped_otros[s_name].append(p)
            
        for super_key, lista in grouped_otros.items():
            msg += f"🔸 *{super_key.upper()}*\n"
            for p in lista:
                dias_str = ", ".join(p.get("dias", []))
                msg += f"  • *{p.get('descuento')}* con *{p.get('banco_tarjeta')}* (Días: {dias_str})\n"
                if p.get("condiciones"):
                    msg += f"    _({p.get('condiciones')})_\n"
        msg += "\n"
        
    return msg.strip()

def obtener_enlaces_oficiales():
    """Retorna los enlaces oficiales de los supermercados y billeteras virtuales."""
    return {
        "mercadopago": {
            "nombre": "Mercado Pago",
            "links": [
                ("Sitio oficial", "https://www.mercadopago.com.ar"),
                ("Promociones generales", "https://promociones.mercadopago.com.ar"),
                ("Promos QR", "https://www.mercadopago.com.ar/c/promocionesqr")
            ]
        },
        "cuentadni": {
            "nombre": "Cuenta DNI",
            "links": [
                ("Sitio oficial", "https://www.bancoprovincia.com.ar/cuentadni"),
                ("Beneficios supermercados", "https://www.bancoprovincia.com.ar/cuentadni/contenidos/cdniBeneficios/detalle/supermercados"),
                ("Nota oficial supermercados", "https://www.bancoprovincia.com.ar/Noticias/MasNoticias/todas-las-promociones-de-cuenta-dni-en-supermercados-3031")
            ]
        },
        "modo": {
            "nombre": "MODO",
            "links": [
                ("Sitio oficial", "https://www.modo.com.ar")
            ]
        },
        "uala": {
            "nombre": "Ualá",
            "links": [
                ("Sitio oficial", "https://www.uala.com.ar"),
                ("Promociones", "https://www.uala.com.ar/promociones"),
                ("Programa Ualá Más", "https://www.uala.com.ar/uala-mas")
            ]
        },
        "personalpay": {
            "nombre": "Personal Pay",
            "links": [
                ("Sitio oficial", "https://www.personal.com.ar/pay"),
                ("Google Play", "https://play.google.com/store/apps/details?id=ar.com.personalpay&hl=es_AR"),
                ("App Store", "https://apps.apple.com/ar/app/personal-pay-billetera-virtual/id1548817439")
            ]
        },
        "brubank": {
            "nombre": "Brubank",
            "links": [
                ("Sitio oficial", "https://www.brubank.com"),
                ("Promociones (help)", "https://help.brubank.com/es/collections/2846519-promociones"),
                ("Promociones disponibles", "https://help.brubank.com/es/collections/3832828-promociones-disponibles"),
                ("Promo Coto", "https://help.brubank.com/es/articles/13977196-30-de-descuento-los-jueves-en-supermercados-coto")
            ]
        },
        "coto": {
            "nombre": "Coto",
            "links": [
                ("Canales oficiales", "https://www.coto.com.ar/canales-de-contacto-oficiales/"),
                ("Sitio Promociones", "https://www.coto.com.ar/descuentos/"),
                ("Instagram", "https://www.instagram.com/coto_ar"),
                ("Facebook", "https://www.facebook.com/coto")
            ]
        },
        "carrefour": {
            "nombre": "Carrefour",
            "links": [
                ("Sitio Promociones", "https://www.carrefour.com.ar/promociones"),
                ("Instagram", "https://www.instagram.com/carrefourargentina"),
                ("Facebook", "https://www.facebook.com/CarrefourArgentina")
            ]
        },
        "dia": {
            "nombre": "Día",
            "links": [
                ("Medios de pago y promos", "https://diaonline.supermercadosdia.com.ar/medios-de-pago-y-promociones"),
                ("Sitio Promociones", "https://diaonline.supermercadosdia.com.ar/"),
                ("Instagram", "https://www.instagram.com/diaargentina"),
                ("Facebook", "https://www.facebook.com/DiaArgentina")
            ]
        }
    }

def formatear_enlaces_mensaje(filtro):
    """Retorna los enlaces formateados en un mensaje Markdown según el filtro indicado."""
    enlaces = obtener_enlaces_oficiales()
    filtro_key = filtro.lower().strip().replace(" ", "").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    
    if filtro_key == "todos":
        msg = "🔗 *Enlaces Oficiales de Billeteras y Supermercados:*\n\n"
        for key, info in enlaces.items():
            msg += f"🔸 *{info['nombre']}*\n"
            for label, url in info["links"]:
                msg += f"  • [{label}]({url})\n"
            msg += "\n"
        return msg.strip()
        
    if filtro_key in enlaces:
        info = enlaces[filtro_key]
        msg = f"🔗 *Enlaces oficiales de {info['nombre']}:*\n\n"
        for label, url in info["links"]:
            msg += f"• [{label}]({url})\n"
        return msg.strip()
        
    # Búsqueda difusa
    for key, info in enlaces.items():
        if filtro_key in key or key in filtro_key:
            msg = f"🔗 *Enlaces oficiales de {info['nombre']}:*\n\n"
            for label, url in info["links"]:
                msg += f"• [{label}]({url})\n"
            return msg.strip()
            
    return f"❌ No encontré enlaces oficiales para '{filtro}'."

def cargar_productos():
    """Carga los productos de oferta desde el archivo JSON."""
    if not os.path.exists(PRODUCTS_FILE):
        return []
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando productos de oferta: {e}")
        return []

def guardar_productos(productos):
    """Guarda los productos de oferta en el archivo JSON."""
    try:
        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(productos, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando productos de oferta: {e}")
        return False

def buscar_productos_filtrados(supermercado=None):
    """Filtra productos de oferta por supermercado."""
    productos = cargar_productos()
    if supermercado and supermercado.lower().strip() != "todos":
        super_name = supermercado.lower().strip()
        if super_name == "dia":
            super_name = "día"
        productos = [p for p in productos if p.get("supermercado", "").lower().strip() == super_name]
    return productos

def agregar_nuevo_producto(supermercado, producto, precio, condiciones=None):
    """Agrega una oferta de producto al archivo local."""
    productos = cargar_productos()
    
    super_name = supermercado.strip().capitalize()
    if super_name.lower() == "dia":
        super_name = "Día"
        
    nuevo = {
        "supermercado": super_name,
        "producto": producto.strip(),
        "precio": precio.strip(),
        "condiciones": condiciones.strip() if condiciones else ""
    }
    productos.append(nuevo)
    return guardar_productos(productos)

def formatear_productos_mensaje(productos, supermercado=None):
    """Formatea la lista de productos de oferta para Telegram."""
    label_super = f" de {supermercado.upper()}" if supermercado and supermercado.lower() != "todos" else ""
    
    if not productos:
        return f"🎉 ¡No encontré ofertas de productos{label_super} cargadas! Puedes agregar una diciendo: 'Agregá oferta Coto Yerba Playadito a $3400'."
        
    msg = f"🛍️ *Ofertas en Productos{label_super}:*\n\n"
    
    grouped = {}
    for p in productos:
        super_name = p.get("supermercado", "Otros")
        if super_name not in grouped:
            grouped[super_name] = []
        grouped[super_name].append(p)
        
    for super_key, lista in grouped.items():
        msg += f"🔸 *{super_key.upper()}*\n"
        for p in lista:
            msg += f"  • *{p.get('producto')}*: {p.get('precio')}\n"
            if p.get("condiciones"):
                msg += f"    _({p.get('condiciones')})_\n"
        msg += "\n"
        
    return msg.strip()

def buscar_precios_online(termino):
    """Busca en superprecio.ar los precios comparativos en tiempo real de un producto (opcionalmente a través de Google Apps Script proxy)."""
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse
    import os
    
    try:
        # Cargar variables de entorno de forma redundante desde los directorios posibles (.env en root o en el subproyecto)
        from dotenv import load_dotenv
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(BASE_DIR, ".env"))
        load_dotenv(os.path.join(BASE_DIR, "Proyecto 3 - Asistente Vero", ".env"))
        load_dotenv(os.path.join(os.path.dirname(BASE_DIR), ".env"))
        
        # Reemplazar espacios por '+' para evitar problemas de formato
        term_formatted = termino.replace(" ", "+")
        target_url = f"https://superprecio.ar/searchgrouped?search={term_formatted}"
        
        # Leer URL de proxy de Google Apps Script (útil para el tier gratuito de PythonAnywhere)
        proxy_base_url = os.environ.get("GOOGLE_SCRIPT_PROXY_URL")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        
        # Log diagnóstico
        log_path = "bot_errors.log"
        
        if proxy_base_url:
            request_url = f"{proxy_base_url.strip()}?url={urllib.parse.quote(target_url, safe='')}"
            r = requests.get(request_url, headers=headers, timeout=15)
        else:
            r = requests.get(target_url, headers=headers, timeout=10)
            
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[DIAGNOSTIC] Query: {termino} | Status: {r.status_code} | Length: {len(r.text)} | Using Proxy: {bool(proxy_base_url)}\n")
        except Exception:
            pass
            
        if r.status_code != 200:
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[DIAGNOSTIC] Non-200 response: {r.text[:300]}\n")
            except Exception:
                pass
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        products = []
        rows = soup.find_all(class_='product-row')
        
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[DIAGNOSTIC] Rows found in HTML: {len(rows)}\n")
                if len(rows) == 0:
                    f.write(f"[DIAGNOSTIC] First 500 chars of HTML: {r.text[:500]}\n")
        except Exception:
            pass
            
        for row in rows:
            title_el = row.find(class_='product-title')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            
            market_prices = []
            for box in row.find_all(class_='price-box'):
                market_name = box.get('data-market-name', '').strip()
                price_el = box.find(class_='price-box-price')
                price = price_el.get_text(strip=True) if price_el else ''
                link = box.get('data-bs-link', '').strip()
                
                # Normalizar nombres de super a los que usa Vero
                market_lower = market_name.lower()
                if "coto" in market_lower:
                    market_name = "Coto"
                elif "carrefour" in market_lower:
                    market_name = "Carrefour"
                elif "dia" in market_lower or "día" in market_lower:
                    market_name = "Día"
                elif "jumbo" in market_lower:
                    market_name = "Jumbo"
                elif "disco" in market_lower:
                    market_name = "Disco"
                elif "vea" in market_lower:
                    market_name = "Vea"
                elif "chango" in market_lower or "mas" in market_lower:
                    market_name = "Chango Más"
                
                if market_name and price:
                    market_prices.append({
                        "supermercado": market_name,
                        "precio": price,
                        "link": link
                    })
            
            if market_prices:
                products.append({
                    "producto": title,
                    "precios": market_prices
                })
                
        return products
    except Exception as e:
        print(f"Error en buscar_precios_online: {e}")
        try:
            with open("bot_errors.log", "a", encoding="utf-8") as f:
                f.write(f"[DIAGNOSTIC] Exception: {e}\n")
        except Exception:
            pass
        return []

def buscar_productos_por_nombre(termino):
    """Busca productos en la base de datos local y en superprecio.ar en tiempo real."""
    import unicodedata
    
    # 1. Búsqueda local
    productos_locales = cargar_productos()
    termino_clean = termino.lower().strip()
    
    def normalizar(txt):
        return "".join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').lower()
        
    termino_norm = normalizar(termino_clean)
    coincidencias_locales = []
    for p in productos_locales:
        prod_norm = normalizar(p.get("producto", ""))
        super_norm = normalizar(p.get("supermercado", ""))
        if termino_norm in prod_norm or termino_norm in super_norm:
            coincidencias_locales.append(p)
            
    # 2. Búsqueda online en superprecio.ar (con timeout corto)
    coincidencias_online = buscar_precios_online(termino_clean)
    
    return coincidencias_locales, coincidencias_online

def formatear_resultado_busqueda(locales, online, termino):
    """Formatea la respuesta consolidada de búsqueda local y online en Markdown."""
    if not locales and not online:
        return f"🔍 No encontré ofertas cargadas ni precios online para *'{termino}'*."
        
    msg = f"🔍 *Resultados de búsqueda para '{termino}':*\n\n"
    
    # Ofertas cargadas manualmente (locales)
    if locales:
        msg += "📌 *Ofertas de Canasta Básica (Base de Datos):*\n"
        grouped = {}
        for p in locales:
            s_name = p.get("supermercado", "Otros")
            if s_name not in grouped:
                grouped[s_name] = []
            grouped[s_name].append(p)
            
        for s_name, lista in grouped.items():
            msg += f"🔸 *{s_name.upper()}*\n"
            for p in lista:
                msg += f"  • *{p.get('producto')}*: {p.get('precio')}\n"
                if p.get("condiciones"):
                    msg += f"    _({p.get('condiciones')})_\n"
        msg += "\n"
        
    # Precios comparativos online (online)
    if online:
        msg += "🌐 *Precios comparados en tiempo real (online):*\n"
        # Mostrar los primeros 5 productos para no saturar Telegram
        for idx, p in enumerate(online[:5]):
            msg += f"🔹 *{p['producto']}*\n"
            
            # Ordenar precios de menor a mayor
            try:
                def get_val(pr):
                    val_str = pr["precio"].replace("$", "").replace(".", "").replace(",", ".").strip()
                    return float(val_str)
                precios_ordenados = sorted(p["precios"], key=get_val)
            except Exception:
                precios_ordenados = p["precios"]
                
            for pr in precios_ordenados:
                super_display = pr["supermercado"]
                if super_display in ["Coto", "Carrefour", "Día"]:
                    super_display = f"*{super_display}*"
                    
                if pr["link"]:
                    msg += f"  • {super_display}: [{pr['precio']}]({pr['link']})\n"
                else:
                    msg += f"  • {super_display}: {pr['precio']}\n"
            msg += "\n"
            
    return msg.strip()
