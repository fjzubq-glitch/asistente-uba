#!/usr/bin/env python3
"""
subir_apuntes_existentes.py — Plan B / Ingesta Directa de Apuntes (Fábrica de Apuntes UBA)

Este script implementa la Opción B: toma archivos Markdown de Ficha y Cuestionario/Casos
previamente redactados o generados externamente, los valida, extrae sus metadatos y ejecuta
directamente la subida a Notion, la notificación por Telegram y el agendado de Active Recall en Franklin.

Uso:
  # Por materia y clase (busca automáticamente en Universidad/ y sus subcarpetas):
  python "Fabrica de Apuntes/subir_apuntes_existentes.py" --materia "Derecho Comercial" --clase 2

  # Indicando una carpeta específica:
  python "Fabrica de Apuntes/subir_apuntes_existentes.py" --directorio "Universidad/Contratos II"

  # Indicando las rutas directas de los archivos:
  python "Fabrica de Apuntes/subir_apuntes_existentes.py" --ficha "ruta/Ficha_...md" --cuestionario "ruta/Cuestionario_...md"

  # Modo automático (escanea y procesa parejas de Ficha y Cuestionario):
  python "Fabrica de Apuntes/subir_apuntes_existentes.py" --auto
"""

import os
import sys
import re
import glob
import argparse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Asegurar que el directorio de scripts esté en el PYTHONPATH
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from subir_a_notion import subir_apuntes, obtener_o_crear_pagina_materia
from generar_apuntes import enviar_notificacion_telegram, programar_active_recall_en_notion


def normalizar_nombre_materia(materia_raw):
    """
    Normaliza el nombre de la materia a los estándares de la cátedra.
    """
    m = materia_raw.strip().lower()
    if "comercial" in m:
        return "Derecho Comercial"
    elif "contratos" in m:
        return "Contratos II" if "ii" in m or "2" in m else "Contratos"
    elif "administrativo" in m:
        return "Derecho Administrativo"
    return materia_raw.strip()


def extraer_metadatos_de_archivo(filepath):
    """
    Intenta extraer materia, clase, fecha y tema a partir del nombre del archivo y su contenido.
    """
    filename = os.path.basename(filepath)
    materia, clase, fecha, tema = None, None, None, None

    # 1. Analizar el nombre del archivo con expresiones regulares
    # Patrones comunes:
    # Ficha_DerechoComercial_Clase2_14-08-26.md
    # Ficha_Contratos II_Clase1_13-08-26.md
    # Cuestionario_y_Casos_Comercial_Clase1_07-07-26.md
    match_nombre = re.search(r'(?:Ficha|Cuestionario(?:_y_Casos)?)_([A-Za-z0-9_\s]+)_Clase([0-9]+)_([0-9]{2}-[0-9]{2}-[0-9]{2,4})', filename, re.IGNORECASE)
    if match_nombre:
        materia_raw = match_nombre.group(1).replace('_', ' ')
        materia = normalizar_nombre_materia(materia_raw)
        clase = match_nombre.group(2)
        fecha = match_nombre.group(3)

    # 2. Leer contenido para obtener o complementar datos
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Buscar Tema / Eje central en el contenido
            match_eje = re.search(r'\*\s*\*\*Eje central:\*\*\s*(.+)', content)
            if match_eje:
                tema = match_eje.group(1).strip()
            
            if not tema:
                match_tema_handoff = re.search(r'Tema:\s*([^·\n]+)', content)
                if match_tema_handoff:
                    tema = match_tema_handoff.group(1).strip()

            if not materia:
                match_mat_handoff = re.search(r'Materia:\s*([^·\n]+)', content)
                if match_mat_handoff:
                    materia = normalizar_nombre_materia(match_mat_handoff.group(1))

            if not clase:
                match_clase_handoff = re.search(r'Clase:\s*([0-9]+)', content)
                if match_clase_handoff:
                    clase = match_clase_handoff.group(1).strip()

            if not fecha:
                match_fecha_handoff = re.search(r'Fecha:\s*([0-9]{2}-[0-9]{2}-[0-9]{2,4})', content)
                if match_fecha_handoff:
                    fecha = match_fecha_handoff.group(1).strip()

        except Exception as e:
            print(f"[WARN] No se pudo leer contenido completo de {filename}: {e}")

    if not tema:
        tema = f"Clase {clase or 'N'}"

    return {
        "materia": materia or "Materia",
        "clase": clase or "1",
        "fecha": fecha or "00-00-00",
        "tema": tema
    }


def buscar_parejas_archivos(directorio_base=None, materia=None, clase=None):
    """
    Busca parejas de archivos (Ficha y Cuestionario) en el directorio indicado o en las carpetas estándar.
    """
    directorios_a_buscar = []
    if directorio_base:
        directorios_a_buscar.append(directorio_base)
    else:
        univ_dir = os.path.join(ROOT_DIR, "Universidad")
        directorios_a_buscar.append(univ_dir)
        # Buscar en subdirectorios de Universidad
        if os.path.exists(univ_dir):
            for item in os.listdir(univ_dir):
                subpath = os.path.join(univ_dir, item)
                if os.path.isdir(subpath):
                    directorios_a_buscar.append(subpath)

    fichas = []
    cuestionarios = []

    for d in directorios_a_buscar:
        if not os.path.exists(d):
            continue
        for f in glob.glob(os.path.join(d, "*.md")):
            fname = os.path.basename(f)
            if fname.startswith("Ficha_"):
                fichas.append(f)
            elif fname.startswith("Cuestionario"):
                cuestionarios.append(f)

    parejas = []

    # Si se especificó materia y/o clase, filtrar
    for ficha in fichas:
        meta_f = extraer_metadatos_de_archivo(ficha)
        if materia and normalizar_nombre_materia(materia) != meta_f["materia"]:
            continue
        if clase and str(clase) != str(meta_f["clase"]):
            continue

        # Buscar el cuestionario correspondiente
        cuestionario_match = None
        for cuest in cuestionarios:
            meta_c = extraer_metadatos_de_archivo(cuest)
            if meta_c["materia"] == meta_f["materia"] and meta_c["clase"] == meta_f["clase"]:
                cuestionario_match = cuest
                break

        parejas.append({
            "ficha": ficha,
            "cuestionario": cuestionario_match,
            "metadatos": meta_f
        })

    return parejas


def procesar_subida_clase(ficha_path, cuestionario_path, metadatos, parent_page_id=None):
    """
    Ejecuta el ciclo completo de subida a Notion, notificación Telegram y Active Recall.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    if not notion_token:
        print("[ERROR] No se encontró la variable de entorno NOTION_TOKEN.")
        return False

    materia = metadatos["materia"]
    clase = metadatos["clase"]
    fecha = metadatos["fecha"]
    tema = metadatos["tema"]

    print(f"\n==================================================")
    print(f"🚀 Procesando subida — Plan B (Ingesta Directa)")
    print(f"📖 Materia: {materia}")
    print(f"🏫 Clase:   {clase}")
    print(f"📅 Fecha:   {fecha}")
    print(f"📌 Tema:    {tema}")
    print(f"📄 Ficha:        {os.path.basename(ficha_path) if ficha_path else 'No provista'}")
    print(f"📝 Cuestionario: {os.path.basename(cuestionario_path) if cuestionario_path else 'No provisto'}")
    print(f"==================================================\n")

    materia_page_id = None
    if parent_page_id:
        try:
            materia_page_id = obtener_o_crear_pagina_materia(notion_token, parent_page_id, materia)
        except Exception as e:
            print(f"[WARN] No se pudo obtener página de materia: {e}")

    f1 = False
    f2 = False

    if ficha_path and os.path.exists(ficha_path):
        print(f"[INFO] Subiendo Ficha académica...")
        f1 = subir_apuntes(materia, clase, fecha, "Ficha + Handoff", ficha_path, notion_token, materia_page_id)
    else:
        print(f"[WARN] Archivo de Ficha no encontrado o no provisto.")

    if cuestionario_path and os.path.exists(cuestionario_path):
        print(f"[INFO] Subiendo Cuestionario y Casos...")
        f2 = subir_apuntes(materia, clase, fecha, "Cuestionario + Casos", cuestionario_path, notion_token, materia_page_id)
    else:
        print(f"[WARN] Archivo de Cuestionario no encontrado o no provisto.")

    if f1 or f2:
        print(f"\n✅ [SUCCESS] Documentos subidos exitosamente a Notion.")

        # 1. Notificación por Telegram
        print(f"[INFO] Enviando notificación a Telegram...")
        enviar_notificacion_telegram(materia, clase, fecha, tema)

        # 2. Recordatorios de Active Recall para Franklin
        db_agenda_id = os.environ.get("NOTION_DB_ID")
        if db_agenda_id:
            print(f"[INFO] Programando recordatorios de Active Recall (días 3, 7 y 21) en la agenda de Franklin...")
            tema_estudio = f"{materia} - Clase {clase}: {tema}"
            if programar_active_recall_en_notion(tema_estudio, notion_token, db_agenda_id):
                print(f"✅ [SUCCESS] Recordatorios de Active Recall agendados correctamente.")
            else:
                print(f"[WARN] No se pudieron agendar todos los recordatorios.")
        return True
    else:
        print(f"❌ [ERROR] No se pudo subir ningún documento.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Subir apuntes existentes a Notion (Plan B / Ingesta Directa)")
    parser.add_argument("--materia", type=str, help="Nombre de la materia (ej. 'Contratos II', 'Derecho Comercial')")
    parser.add_argument("--clase", type=str, help="Número de clase (ej. '1', '2')")
    parser.add_argument("--fecha", type=str, help="Fecha en formato DD-MM-AA")
    parser.add_argument("--tema", type=str, help="Tema de la clase")
    parser.add_argument("--directorio", type=str, help="Ruta a la carpeta que contiene los archivos Markdown")
    parser.add_argument("--ficha", type=str, help="Ruta explícita al archivo de Ficha Markdown")
    parser.add_argument("--cuestionario", type=str, help="Ruta explícita al archivo de Cuestionario Markdown")
    parser.add_argument("--parent-page", type=str, default=None, help="ID de la base de datos de materias en Notion")
    parser.add_argument("--auto", action="store_true", help="Escanear y procesar automáticamente todas las parejas encontradas")

    args = parser.parse_args()

    # Caso 1: Se especificaron rutas explícitas de archivos
    if args.ficha or args.cuestionario:
        ref_file = args.ficha or args.cuestionario
        meta = extraer_metadatos_de_archivo(ref_file)
        if args.materia:
            meta["materia"] = normalizar_nombre_materia(args.materia)
        if args.clase:
            meta["clase"] = args.clase
        if args.fecha:
            meta["fecha"] = args.fecha
        if args.tema:
            meta["tema"] = args.tema

        procesar_subida_clase(args.ficha, args.cuestionario, meta, args.parent_page)
        return

    # Caso 2: Buscar parejas por materia/clase o escaneo
    parejas = buscar_parejas_archivos(args.directorio, args.materia, args.clase)

    if not parejas:
        print("⚠️ No se encontraron parejas de Ficha/Cuestionario para procesar.")
        print("Asegurate de haber colocado los archivos en 'Universidad/', 'Universidad/Contratos II/' o 'Universidad/Derecho Comercial/'")
        print("con los nombres estándar: Ficha_Materia_ClaseN_Fecha.md y Cuestionario_y_Casos_Materia_ClaseN_Fecha.md")
        return

    print(f"📦 Se encontraron {len(parejas)} clase(s) lista(s) para procesar.")
    for p in parejas:
        meta = p["metadatos"]
        if args.materia:
            meta["materia"] = normalizar_nombre_materia(args.materia)
        if args.clase:
            meta["clase"] = args.clase
        if args.fecha:
            meta["fecha"] = args.fecha
        if args.tema:
            meta["tema"] = args.tema

        procesar_subida_clase(p["ficha"], p["cuestionario"], meta, args.parent_page)


if __name__ == "__main__":
    main()
