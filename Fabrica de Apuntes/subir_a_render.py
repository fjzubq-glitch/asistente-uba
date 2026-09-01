#!/usr/bin/env python3
"""
subir_a_render.py — Envía archivos de Ficha/Cuestionario a Render para subida rápida a Notion.

Uso:
  python "Fabrica de Apuntes/subir_a_render.py" --materia "Contratos II" --clase 5

  # Con rutas explícitas:
  python "Fabrica de Apuntes/subir_a_render.py" --ficha "ruta/Ficha_...md" --cuestionario "ruta/Cuestionario_...md"

  # Automático (busca en Universidad/):
  python "Fabrica de Apuntes/subir_a_render.py" --auto
"""

import os
import sys
import re
import glob
import json
import argparse
import requests

RENDER_URL = "https://asistente-uba.onrender.com/subir-apuntes"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalizar_nombre_materia(materia_raw):
    m = materia_raw.strip().lower()
    if "comercial" in m:
        return "Derecho Comercial"
    elif "contratos" in m:
        return "Contratos II" if "ii" in m or "2" in m else "Contratos"
    elif "administrativo" in m:
        return "Derecho Administrativo"
    return materia_raw.strip()


def extraer_metadatos(filepath):
    filename = os.path.basename(filepath)
    materia, clase, fecha, tema = None, None, None, None

    match_nombre = re.search(
        r'(?:Ficha|Cuestionario(?:_y_Casos)?)_([A-Za-z0-9_\s]+)_Clase\s*([0-9]+)_([0-9]{2}[-_][0-9]{2}[-_][0-9]{2,4})',
        filename, re.IGNORECASE
    )
    if match_nombre:
        materia_raw = match_nombre.group(1).replace('_', ' ')
        materia = normalizar_nombre_materia(materia_raw)
        clase = match_nombre.group(2)
        fecha = match_nombre.group(3)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        match_eje = re.search(r'\*\s*\*\*Eje central:\*\*\s*(.+)', content)
        if match_eje:
            tema = match_eje.group(1).strip()

        if not tema:
            match_tema = re.search(r'Tema:\s*([^·\n]+)', content)
            if match_tema:
                tema = match_tema.group(1).strip()

        if not materia:
            match_mat = re.search(r'Materia:\s*([^·\n]+)', content)
            if match_mat:
                materia = normalizar_nombre_materia(match_mat.group(1))

        if not clase:
            match_clase = re.search(r'Clase:\s*([0-9]+)', content)
            if match_clase:
                clase = match_clase.group(1).strip()

        if not fecha:
            match_fecha = re.search(r'Fecha:\s*([0-9]{2}[-_][0-9]{2}[-_][0-9]{2,4})', content)
            if match_fecha:
                fecha = match_fecha.group(1).strip()
    except Exception as e:
        print(f"[WARN] No se pudo leer {filename}: {e}")

    return {
        "materia": materia or "Materia",
        "clase": clase or "1",
        "fecha": fecha or "00-00-00",
        "tema": tema or f"Clase {clase or '1'}"
    }


def buscar_parejas(directorio=None, materia=None, clase=None):
    dirs = []
    if directorio:
        dirs.append(directorio)
    else:
        univ = os.path.join(ROOT_DIR, "Universidad")
        dirs.append(univ)
        if os.path.exists(univ):
            for item in os.listdir(univ):
                sub = os.path.join(univ, item)
                if os.path.isdir(sub):
                    dirs.append(sub)

    fichas, cuestionarios = [], []
    for d in dirs:
        if not os.path.exists(d):
            continue
        for f in glob.glob(os.path.join(d, "*.md")):
            fname = os.path.basename(f)
            if fname.startswith("Ficha_"):
                fichas.append(f)
            elif fname.startswith("Cuestionario"):
                cuestionarios.append(f)

    parejas = []
    for ficha in fichas:
        meta_f = extraer_metadatos(ficha)
        if materia and normalizar_nombre_materia(materia) != meta_f["materia"]:
            continue
        if clase and str(clase) != str(meta_f["clase"]):
            continue

        cuest_match = None
        for cuest in cuestionarios:
            meta_c = extraer_metadatos(cuest)
            if meta_c["materia"] == meta_f["materia"] and meta_c["clase"] == meta_f["clase"]:
                cuest_match = cuest
                break

        parejas.append({"ficha": ficha, "cuestionario": cuest_match, "metadatos": meta_f})

    return parejas


def enviar_a_render(materia, clase, fecha, tema, ficha_content=None, cuestionario_content=None):
    payload = {
        "materia": materia,
        "clase": clase,
        "fecha": fecha,
        "tema": tema,
    }
    if ficha_content:
        payload["ficha"] = ficha_content
    if cuestionario_content:
        payload["cuestionario"] = cuestionario_content

    print(f"\n{'='*50}")
    print(f"Enviando a Render: {materia} Clase {clase}")
    print(f"{'='*50}")

    try:
        r = requests.post(RENDER_URL, json=payload, timeout=120)
        result = r.json()
        if r.status_code == 200 and result.get("ok"):
            print(f"[OK] {result.get('mensaje', 'Subido correctamente')}")
            return True
        else:
            print(f"[ERROR] {result.get('error', 'Error desconocido')} (HTTP {r.status_code})")
            return False
    except requests.Timeout:
        print(f"[ERROR] Timeout - Render tardó demasiado en responder")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Subir apuntes a Notion via Render (rápido)")
    parser.add_argument("--materia", type=str)
    parser.add_argument("--clase", type=str)
    parser.add_argument("--fecha", type=str)
    parser.add_argument("--tema", type=str)
    parser.add_argument("--directorio", type=str)
    parser.add_argument("--ficha", type=str)
    parser.add_argument("--cuestionario", type=str)
    parser.add_argument("--auto", action="store_true")

    args = parser.parse_args()

    if args.ficha or args.cuestionario:
        ref = args.ficha or args.cuestionario
        meta = extraer_metadatos(ref)
        if args.materia:
            meta["materia"] = normalizar_nombre_materia(args.materia)
        if args.clase:
            meta["clase"] = args.clase
        if args.fecha:
            meta["fecha"] = args.fecha
        if args.tema:
            meta["tema"] = args.tema

        ficha_content = None
        cuestionario_content = None
        if args.ficha and os.path.exists(args.ficha):
            with open(args.ficha, "r", encoding="utf-8") as f:
                ficha_content = f.read()
        if args.cuestionario and os.path.exists(args.cuestionario):
            with open(args.cuestionario, "r", encoding="utf-8") as f:
                cuestionario_content = f.read()

        enviar_a_render(meta["materia"], meta["clase"], meta["fecha"], meta["tema"], ficha_content, cuestionario_content)
        return

    parejas = buscar_parejas(args.directorio, args.materia, args.clase)

    if not parejas:
        print("No se encontraron parejas Ficha/Cuestionario.")
        return

    print(f"Se encontraron {len(parejas)} clase(s).")
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

        ficha_content = None
        cuestionario_content = None

        if p["ficha"] and os.path.exists(p["ficha"]):
            with open(p["ficha"], "r", encoding="utf-8") as f:
                ficha_content = f.read()
        if p["cuestionario"] and os.path.exists(p["cuestionario"]):
            with open(p["cuestionario"], "r", encoding="utf-8") as f:
                cuestionario_content = f.read()

        enviar_a_render(meta["materia"], meta["clase"], meta["fecha"], meta["tema"], ficha_content, cuestionario_content)


if __name__ == "__main__":
    main()
