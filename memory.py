"""
memory.py — Historial de consultas persistido en JSON.
"""

import json
import os
from datetime import datetime

MEMORY_FILE = "./data/historial.json"


def _cargar() -> list:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar(historial: list) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def registrar(tipo: str, entrada: dict, salida: dict) -> None:
    historial = _cargar()
    historial.append({
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "tipo": tipo,
        "entrada": entrada,
        "salida": salida,
    })
    _guardar(historial)


def obtener_historial() -> list:
    return _cargar()
