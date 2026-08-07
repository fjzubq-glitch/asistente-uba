# -*- coding: utf-8 -*-
"""Smoke tests de las funciones puras del proyecto (sin red, sin credenciales)."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Asistente Vero"))

from server import (  # noqa: E402
    formatear_fecha_humana,
    buenos_dias_ya_enviado_hoy,
    marcar_buenos_dias_enviado,
    _cargar_chats,
    _registrar_chat,
)
import buscador_ofertas as bo  # noqa: E402


def test_formatear_fecha_humana():
    assert formatear_fecha_humana("2026-08-08") == "08/08/2026"
    assert formatear_fecha_humana("2026-08-08T10:30") == "08/08/2026 a las 10:30 hs"
    assert formatear_fecha_humana("") == ""
    assert formatear_fecha_humana(None) == ""
    assert formatear_fecha_humana("texto raro") == "texto raro"


def test_buenos_dias_idempotencia():
    with tempfile.TemporaryDirectory() as d:
        state = os.path.join(d, "state.txt")
        assert buenos_dias_ya_enviado_hoy(state) is False
        marcar_buenos_dias_enviado(state)
        assert buenos_dias_ya_enviado_hoy(state) is True


def test_chats_registry():
    with tempfile.TemporaryDirectory() as d:
        chats_path = os.path.join(d, "chats.json")
        legacy = os.path.join(d, "chat_id.txt")
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("12345")

        # Migración desde chat_id.txt
        loaded = _cargar_chats(chats_path, legacy)
        assert loaded == ["12345"]
        assert os.path.exists(chats_path)

        # Registro idempotente
        lista = _registrar_chat(chats_path, legacy, "67890")
        assert "12345" in lista and "67890" in lista
        lista2 = _registrar_chat(chats_path, legacy, "67890")
        assert len(lista2) == 2


def test_cache_precios_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        orig = bo.CACHE_FILE
        bo.CACHE_FILE = os.path.join(d, "cache.json")
        try:
            assert bo.guardar_cache_precios({"leche": {"ts": 100, "data": []}}) is True
            cache = bo.cargar_cache_precios()
            assert cache["leche"]["ts"] == 100
        finally:
            bo.CACHE_FILE = orig


if __name__ == "__main__":
    tests = [
        test_formatear_fecha_humana,
        test_buenos_dias_idempotencia,
        test_chats_registry,
        test_cache_precios_roundtrip,
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print("ALL TESTS PASSED")
