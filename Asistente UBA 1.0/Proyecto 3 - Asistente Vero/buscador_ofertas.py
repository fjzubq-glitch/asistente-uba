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
    """Formatea la lista de promociones a un formato legible para Telegram."""
    label_super = f" de {supermercado.upper()}" if supermercado and supermercado.lower() != "todos" else ""
    label_dia = f" para el día {dia.upper()}" if dia and dia.lower() != "todos" else ""
    
    if not promos:
        return f"🎉 ¡No encontré promociones cargadas{label_super}{label_dia}! Puedes agregar una diciendo, por ejemplo: 'Agregá promo Coto Banco Nación 30% los miércoles'."
        
    msg = f"🛒 *Promociones de Supermercados{label_super}{label_dia}:*\n\n"
    
    # Agrupar por supermercado
    grouped = {}
    for p in promos:
        super_name = p.get("supermercado", "Otros")
        if super_name not in grouped:
            grouped[super_name] = []
        grouped[super_name].append(p)
        
    for super_key, lista in grouped.items():
        msg += f"🔹 *{super_key.upper()}*\n"
        for p in lista:
            dias_str = ", ".join(p.get("dias", []))
            msg += f"  • *{p.get('descuento')}* con *{p.get('banco_tarjeta')}* (Días: {dias_str})\n"
            if p.get("condiciones"):
                msg += f"    _({p.get('condiciones')})_\n"
        msg += "\n"
        
    return msg.strip()

def obtener_enlaces_oficiales():
    """Retorna los enlaces web, Instagram y Facebook oficiales de los supermercados."""
    return {
        "Coto": {
            "web": "https://www.coto.com.ar/descuentos/",
            "instagram": "https://www.instagram.com/coto_ar/",
            "facebook": "https://www.facebook.com/coto/"
        },
        "Carrefour": {
            "web": "https://www.carrefour.com.ar/promociones",
            "instagram": "https://www.instagram.com/carrefourargentina/",
            "facebook": "https://www.facebook.com/CarrefourArgentina/"
        },
        "Día": {
            "web": "https://diaonline.supermercadosdia.com.ar/",
            "instagram": "https://www.instagram.com/diaargentina/",
            "facebook": "https://www.facebook.com/DiaArgentina/"
        }
    }

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
