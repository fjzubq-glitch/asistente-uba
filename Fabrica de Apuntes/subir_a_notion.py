import os
import sys
import re
import requests

NOTION_VERSION = "2022-06-28"

def obtener_cabeceras(notion_token):
    return {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def obtener_o_crear_database(notion_token, parent_page_id):
    """
    Busca la base de datos 'Fábrica de Apuntes - UBA Derecho' bajo la página padre.
    Si no existe, la crea con las propiedades requeridas.
    """
    headers = obtener_cabeceras(notion_token)
    
    # 1. Buscar si ya existe la base de datos
    search_url = "https://api.notion.com/v1/search"
    search_payload = {
        "query": "Fábrica de Apuntes - UBA Derecho",
        "filter": {
            "value": "database",
            "property": "object"
        }
    }
    
    try:
        r = requests.post(search_url, headers=headers, json=search_payload, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        
        # Verificar que la base de datos no esté archivada y coincida con el padre
        for db in results:
            if db.get("title", [{}])[0].get("plain_text", "") == "Fábrica de Apuntes - UBA Derecho" and not db.get("archived", False):
                parent = db.get("parent", {})
                if parent.get("page_id") == parent_page_id or parent.get("page_id") == parent_page_id.replace("-", ""):
                    print(f"[INFO] Base de datos existente encontrada. ID: {db['id']}")
                    return db["id"]
    except Exception as e:
        print(f"[WARN] Error al buscar base de datos: {e}")

    # 2. Si no existe, crear la base de datos
    print("[INFO] Creando nueva base de datos 'Fabrica de Apuntes - UBA Derecho'...")
    create_url = "https://api.notion.com/v1/databases"
    db_payload = {
        "parent": {
            "type": "page_id",
            "page_id": parent_page_id
        },
        "title": [
            {
                "type": "text",
                "text": {
                    "content": "Fábrica de Apuntes - UBA Derecho"
                }
            }
        ],
        "properties": {
            "Nombre": {
                "title": {}
            },
            "Materia": {
                "select": {
                    "options": [
                        {"name": "Contratos II", "color": "blue"},
                        {"name": "Derecho Comercial", "color": "green"}
                    ]
                }
            },
            "Clase": {
                "number": {
                    "format": "number"
                }
            },
            "Tipo": {
                "select": {
                    "options": [
                        {"name": "Ficha + Handoff", "color": "orange"},
                        {"name": "Sistema MIT", "color": "purple"},
                        {"name": "Cuestionario + Casos", "color": "red"}
                    ]
                }
            },
            "Fecha": {
                "date": {}
            }
        }
    }
    
    try:
        r = requests.post(create_url, headers=headers, json=db_payload, timeout=20)
        r.raise_for_status()
        new_db_id = r.json()["id"]
        print(f"[SUCCESS] Base de datos creada con exito. ID: {new_db_id}")
        return new_db_id
    except Exception as e:
        print(f"[ERROR] Fallo critico al crear la base de datos en Notion: {e}")
        if 'r' in locals() and r.text:
            print(f"Detalle de la respuesta del servidor: {r.text}")
        sys.exit(1)

def convertir_texto_enriquecido(texto):
    """
    Parsea las negritas (**) de Markdown y genera el formato de texto enriquecido de Notion.
    Limpia los caracteres vacíos de Notion para evitar errores de validación.
    """
    parts = texto.split("**")
    rich_text = []
    for i, part in enumerate(parts):
        if not part:
            continue
        is_bold = (i % 2 == 1)
        rich_text.append({
            "type": "text",
            "text": {"content": part},
            "annotations": {
                "bold": is_bold
            }
        })
    if not rich_text:
        rich_text = [{"type": "text", "text": {"content": ""}}]
    return rich_text

def parsear_markdown_a_bloques(markdown_text):
    """
    Convierte un texto Markdown en una lista de bloques JSON compatibles con la API de Notion.
    Soporta títulos (#, ##, ###), viñetas (-), listas numeradas (1.) y tablas (|).
    """
    lines = markdown_text.split("\n")
    blocks = []
    
    in_table = False
    table_rows = []
    
    for line in lines:
        stripped = line.strip()
        
        # Procesar tablas
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            if "---" in stripped:
                continue
            cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
            table_rows.append(cells)
            continue
        elif in_table:
            # Fin de la tabla, procesarla y agregar bloque
            if table_rows:
                num_cols = len(table_rows[0])
                table_block = {
                    "object": "block",
                    "type": "table",
                    "table": {
                        "table_width": num_cols,
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": []
                    }
                }
                for row in table_rows:
                    row_cells = []
                    for cell in row:
                        row_cells.append(convertir_texto_enriquecido(cell))
                    while len(row_cells) < num_cols:
                        row_cells.append([{"type": "text", "text": {"content": ""}}])
                    table_block["table"]["children"].append({
                        "object": "block",
                        "type": "table_row",
                        "table_row": {
                            "cells": row_cells
                        }
                    })
                blocks.append(table_block)
            table_rows = []
            in_table = False
            
        if not stripped:
            continue
            
        # Encabezados
        if stripped.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": convertir_texto_enriquecido(stripped[2:])
                }
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": convertir_texto_enriquecido(stripped[3:])
                }
            })
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": convertir_texto_enriquecido(stripped[4:])
                }
            })
        # Listas de viñetas
        elif stripped.startswith("- ") or stripped.startswith("* "):
            # Remover marcas visuales adicionales si las hay
            content = stripped[2:]
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": convertir_texto_enriquecido(content)
                }
            })
        # Listas numeradas
        elif re.match(r"^\d+\.\s+", stripped):
            match = re.match(r"^(\d+)\.\s+(.*)", stripped)
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": convertir_texto_enriquecido(match.group(2))
                }
            })
        # Párrafos normales
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": convertir_texto_enriquecido(stripped)
                }
            })
            
    # Cerrar tabla pendiente si el archivo termina con una tabla
    if in_table and table_rows:
        num_cols = len(table_rows[0])
        table_block = {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": num_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": []
            }
        }
        for row in table_rows:
            row_cells = []
            for cell in row:
                row_cells.append(convertir_texto_enriquecido(cell))
            while len(row_cells) < num_cols:
                row_cells.append([{"type": "text", "text": {"content": ""}}])
            table_block["table"]["children"].append({
                "object": "block",
                "type": "table_row",
                "table_row": {
                    "cells": row_cells
                }
            })
        blocks.append(table_block)
        
    return blocks

def subir_pagina_notion(notion_token, db_id, properties, blocks):
    """
    Crea una página en la base de datos de Notion.
    Maneja el límite máximo de 100 bloques por lote de la API de Notion.
    """
    url = "https://api.notion.com/v1/pages"
    headers = obtener_cabeceras(notion_token)
    
    # Separar los primeros 100 bloques para la creación inicial
    initial_blocks = blocks[:100]
    remaining_blocks = blocks[100:]
    
    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": initial_blocks
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    page_id = response.json()["id"]
    
    # Añadir bloques restantes en lotes de 100
    if remaining_blocks:
        append_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        for i in range(0, len(remaining_blocks), 100):
            chunk = remaining_blocks[i:i+100]
            append_payload = {"children": chunk}
            append_resp = requests.patch(append_url, headers=headers, json=append_payload, timeout=20)
            append_resp.raise_for_status()
            
    return page_id

def subir_apuntes(materia, clase, fecha, tipo_documento, filepath, notion_token, db_id):
    """
    Lee un archivo Markdown local y lo sube como página a la base de datos de Notion.
    """
    if not os.path.exists(filepath):
        print(f"[WARN] El archivo local '{filepath}' no se encuentra disponible para subir.")
        return False
        
    print(f"[INFO] Subiendo '{tipo_documento}' desde '{os.path.basename(filepath)}'...")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    blocks = parsear_markdown_a_bloques(content)
    
    # Convertir formato de fecha de DD-MM-YY a YYYY-MM-DD
    # Asume año 2026 para cuatrimestre actual si viene en dos dígitos
    fecha_split = fecha.split("-")
    if len(fecha_split) == 3:
        dia, mes, anio = fecha_split
        # Si el año viene en formato corto (2 dígitos)
        if len(anio) == 2:
            anio = "20" + anio
        fecha_iso = f"{anio}-{mes}-{dia}"
    else:
        fecha_iso = fecha # si ya viene formateada
        
    nombre_pagina = f"{tipo_documento} - {materia} - Clase {clase} ({fecha})"
    
    properties = {
        "Nombre": {
            "title": [
                {
                    "text": {
                        "content": nombre_pagina
                    }
                }
            ]
        },
        "Materia": {
            "select": {
                "name": materia
            }
        },
        "Clase": {
            "number": int(clase)
        },
        "Tipo": {
            "select": {
                "name": tipo_documento
            }
        },
        "Fecha": {
            "date": {
                "start": fecha_iso
            }
        }
    }
    
    try:
        page_id = subir_pagina_notion(notion_token, db_id, properties, blocks)
        print(f"[SUCCESS] Subido con exito. Pagina ID: {page_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Error al subir la pagina a Notion: {e}")
        if 'response' in locals() and response.text:
            print(f"Detalle del error del servidor: {response.text}")
        return False
