import json
import os
import time
from datetime import datetime

METRICAS_PATH = "./data/metricas.json"
EVENTS_PATH = "./data/agent_events.jsonl"


def _cargar_metricas() -> dict:
    if os.path.exists(METRICAS_PATH):
        with open(METRICAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total_consultas": 0,
        "total_errores": 0,
        "latencias_ms": [],
        "errores_por_tipo": {},
        "consultas_por_endpoint": {},
        "tokens_estimados_total": 0,
    }


def _guardar_metricas(datos: dict) -> None:
    os.makedirs("./data", exist_ok=True)
    with open(METRICAS_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _registrar_evento(evento: dict) -> None:
    os.makedirs("./data", exist_ok=True)
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def registrar_llamada(endpoint: str, pregunta: str, latencia_ms: float,
                      exito: bool, error: str = None, respuesta: str = "") -> None:
    datos = _cargar_metricas()

    datos["total_consultas"] += 1
    datos["latencias_ms"].append(round(latencia_ms, 2))

    datos["consultas_por_endpoint"][endpoint] = (
        datos["consultas_por_endpoint"].get(endpoint, 0) + 1
    )

    tokens_estimados = (len(pregunta) + len(respuesta)) // 4
    datos["tokens_estimados_total"] += tokens_estimados

    if not exito:
        datos["total_errores"] += 1
        tipo_error = error or "unknown"
        datos["errores_por_tipo"][tipo_error] = (
            datos["errores_por_tipo"].get(tipo_error, 0) + 1
        )

    _guardar_metricas(datos)

    evento = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "latencia_ms": round(latencia_ms, 2),
        "tokens_estimados": tokens_estimados,
        "exito": exito,
        "error": error,
    }
    _registrar_evento(evento)


def obtener_resumen() -> dict:
    datos = _cargar_metricas()
    latencias = datos["latencias_ms"]

    if latencias:
        latencia_promedio = round(sum(latencias) / len(latencias), 2)
        latencia_max = max(latencias)
        latencia_min = min(latencias)
    else:
        latencia_promedio = latencia_max = latencia_min = 0

    total = datos["total_consultas"]
    errores = datos["total_errores"]
    tasa_exito = round((total - errores) / total * 100, 1) if total > 0 else 100.0

    return {
        "total_consultas": total,
        "total_errores": errores,
        "tasa_exito_pct": tasa_exito,
        "latencia_promedio_ms": latencia_promedio,
        "latencia_max_ms": latencia_max,
        "latencia_min_ms": latencia_min,
        "tokens_estimados_total": datos["tokens_estimados_total"],
        "consultas_por_endpoint": datos["consultas_por_endpoint"],
        "errores_por_tipo": datos["errores_por_tipo"],
        "ultimas_latencias": latencias[-20:],
    }


def obtener_eventos(limite: int = 50) -> list:
    if not os.path.exists(EVENTS_PATH):
        return []
    eventos = []
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                eventos.append(json.loads(linea))
    return eventos[-limite:]
