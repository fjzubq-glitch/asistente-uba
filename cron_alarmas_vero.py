# -*- coding: utf-8 -*-
"""Punto de entrada para programar las alarmas del Asistente Vero desde
PythonAnywhere (pestaña Tasks) o cualquier cron de sistema.

Ejecuta un UNICO ciclo idempotente (buenos dias a las 8:00 ARG).
No deja hilos colgados: termina apenas termina de procesar.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Cargar el entorno de la raiz y el especifico de Vero antes de importar server
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(BASE_DIR, "Asistente Vero", ".env"))

from server import ejecutar_ciclo_vero  # noqa: E402

if __name__ == "__main__":
    ejecutar_ciclo_vero()