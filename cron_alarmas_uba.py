# -*- coding: utf-8 -*-
"""Punto de entrada para programar las alarmas del Asistente UBA desde
PythonAnywhere (pestaña Tasks) o cualquier cron de sistema.

Ejecuta un UNICO ciclo idempotente: manda buenos dias a las 8:00 ARG y
envia recordatorios de eventos que vencen en los proximos 10 minutos.
No deja hilos colgados: termina apenas termina de procesar.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Cargar entorno antes de importar server
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from server import ejecutar_ciclo_uba  # noqa: E402

if __name__ == "__main__":
    ejecutar_ciclo_uba()