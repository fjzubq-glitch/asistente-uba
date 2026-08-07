# -*- coding: utf-8 -*-
"""Tarea diaria unica para PythonAnywhere (plan free = 1 tarea diaria).

Ejecuta los ciclos de alarmas de AMBOS asistentes en una sola corrida:
- UBA: buenos dias (08:00 ARG) + recordatorios de eventos a 10 min.
- Vero: buenos dias (08:00 ARG).

Programar en Tasks de PythonAnywhere: daily a las 11:00 UTC (= 08:00 Argentina).
Los recordatorios a lo largo del dia siguen a cargo de los hilos de server.py
(activados por /ping y los webhooks), ya que el plan free no permite cron cada minuto.
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

from server import ejecutar_ciclo_uba, ejecutar_ciclo_vero  # noqa: E402

if __name__ == "__main__":
    ejecutar_ciclo_uba()
    ejecutar_ciclo_vero()