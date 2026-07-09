import json
import os
import statistics
from datetime import datetime

try:
    import psutil
    _proceso = psutil.Process()
    _PSUTIL = True
except ImportError:
    _proceso = None
    _PSUTIL = False

METRICAS_PATH = "./data/metricas.json"
EVENTS_PATH   = "./data/agent_events.jsonl"
AUDIT_PATH    = "./data/audit.log"

_METRICAS_BASE = {
    "total_consultas": 0,
    "total_errores": 0,
    "latencias_ms": [],
    "latencias_rag_ms": [],
    "latencias_llm_ms": [],
    "errores_por_tipo": {},
    "consultas_por_endpoint": {},
    "tokens_estimados_total": 0,
    "ram_mb_muestras": [],
    "cpu_pct_muestras": [],
}


def _cargar_metricas() -> dict:
    if os.path.exists(METRICAS_PATH):
        with open(METRICAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(_METRICAS_BASE)


def _guardar_metricas(datos: dict) -> None:
    os.makedirs("./data", exist_ok=True)
    with open(METRICAS_PATH, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _registrar_evento(evento: dict) -> None:
    os.makedirs("./data", exist_ok=True)
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def _percentil(valores: list, p: int) -> float:
    if not valores:
        return 0.0
    ordenado = sorted(valores)
    idx = int(len(ordenado) * p / 100)
    return round(ordenado[min(idx, len(ordenado) - 1)], 2)


def registrar_audit(ip: str, accion: str, detalle: str = "") -> None:
    os.makedirs("./data", exist_ok=True)
    linea = f"[{datetime.now().isoformat()}] IP={ip} ACCION={accion} {detalle}\n"
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(linea)


def registrar_llamada(
    endpoint: str,
    pregunta: str,
    latencia_total_ms: float,
    exito: bool,
    error: str = None,
    respuesta: str = "",
    latencia_rag_ms: float = 0,
    latencia_llm_ms: float = 0,
) -> None:
    datos = _cargar_metricas()

    datos["total_consultas"] += 1
    datos["latencias_ms"].append(round(latencia_total_ms, 2))
    datos["latencias_rag_ms"].append(round(latencia_rag_ms, 2))
    datos["latencias_llm_ms"].append(round(latencia_llm_ms, 2))
    datos["consultas_por_endpoint"][endpoint] = datos["consultas_por_endpoint"].get(endpoint, 0) + 1

    tokens_estimados = (len(pregunta) + len(respuesta)) // 4
    datos["tokens_estimados_total"] += tokens_estimados

    if _PSUTIL:
        datos["ram_mb_muestras"].append(round(_proceso.memory_info().rss / 1024 / 1024, 1))
        datos["cpu_pct_muestras"].append(round(_proceso.cpu_percent(interval=None), 1))

    if not exito:
        datos["total_errores"] += 1
        # Guardar solo el tipo de excepción como clave del contador (antes del primer ":")
        tipo_error = error.split(":")[0] if error else "unknown"
        datos["errores_por_tipo"][tipo_error] = datos["errores_por_tipo"].get(tipo_error, 0) + 1

    _guardar_metricas(datos)

    promedio = sum(datos["latencias_ms"]) / len(datos["latencias_ms"])
    es_anomalia = latencia_total_ms > promedio * 2 and len(datos["latencias_ms"]) > 5

    evento = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "latencia_ms": round(latencia_total_ms, 2),
        "latencia_rag_ms": round(latencia_rag_ms, 2),
        "latencia_llm_ms": round(latencia_llm_ms, 2),
        "tokens_estimados": tokens_estimados,
        "exito": exito,
        "error": error,          # mensaje completo: "AuthenticationError: ..."
        "anomalia": es_anomalia,
        "nivel": "ERROR" if not exito else ("WARNING" if es_anomalia else "INFO"),
    }
    _registrar_evento(evento)


def obtener_resumen() -> dict:
    datos     = _cargar_metricas()
    latencias = datos["latencias_ms"]
    ram       = datos.get("ram_mb_muestras", [])
    cpu       = datos.get("cpu_pct_muestras", [])
    total     = datos["total_consultas"]
    errores   = datos["total_errores"]

    return {
        "total_consultas": total,
        "total_errores": errores,
        "tasa_exito_pct": round((total - errores) / total * 100, 1) if total > 0 else 100.0,
        "latencia_promedio_ms": round(statistics.mean(latencias), 2) if latencias else 0,
        "latencia_max_ms": max(latencias) if latencias else 0,
        "latencia_min_ms": min(latencias) if latencias else 0,
        "p50_ms": _percentil(latencias, 50),
        "p95_ms": _percentil(latencias, 95),
        "p99_ms": _percentil(latencias, 99),
        "latencia_rag_promedio_ms": round(statistics.mean(datos["latencias_rag_ms"]), 2) if datos["latencias_rag_ms"] else 0,
        "latencia_llm_promedio_ms": round(statistics.mean(datos["latencias_llm_ms"]), 2) if datos["latencias_llm_ms"] else 0,
        "tokens_estimados_total": datos["tokens_estimados_total"],
        "ram_mb_promedio": round(statistics.mean(ram), 1) if ram else 0,
        "cpu_pct_promedio": round(statistics.mean(cpu), 1) if cpu else 0,
        "consultas_por_endpoint": datos["consultas_por_endpoint"],
        "errores_por_tipo": datos["errores_por_tipo"],
        "ultimas_latencias": latencias[-30:],
        "ultimas_latencias_rag": datos["latencias_rag_ms"][-30:],
        "ultimas_latencias_llm": datos["latencias_llm_ms"][-30:],
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


def obtener_analisis() -> dict:
    datos     = _cargar_metricas()
    eventos   = obtener_eventos(200)
    latencias = datos["latencias_ms"]

    anomalias     = [e for e in eventos if e.get("anomalia")]
    eventos_error = [e for e in eventos if not e.get("exito")]

    endpoint_lento = ""
    lat_max        = 0
    for ep in datos["consultas_por_endpoint"]:
        lats = [e["latencia_ms"] for e in eventos if e["endpoint"] == ep]
        if lats:
            avg = sum(lats) / len(lats)
            if avg > lat_max:
                lat_max        = avg
                endpoint_lento = ep

    conteo_horas = {}
    for e in eventos:
        hora = e["timestamp"][11:13] + ":00"
        conteo_horas[hora] = conteo_horas.get(hora, 0) + 1
    hora_pico = max(conteo_horas, key=conteo_horas.get) if conteo_horas else "N/A"

    patrones = []
    if anomalias:
        patrones.append(f"{len(anomalias)} consultas con latencia > 2× el promedio detectadas.")
    if eventos_error:
        tipo = max(datos["errores_por_tipo"], key=datos["errores_por_tipo"].get)
        patrones.append(f"Error más frecuente: {tipo} ({datos['errores_por_tipo'][tipo]} ocurrencias).")
    if endpoint_lento:
        patrones.append(f"Endpoint más lento: /{endpoint_lento} ({round(lat_max)} ms promedio).")
    if hora_pico != "N/A":
        patrones.append(f"Hora pico de uso: {hora_pico} ({conteo_horas.get(hora_pico, 0)} consultas).")

    recomendaciones = []
    lats_rag = datos.get("latencias_rag_ms", [])
    lats_llm = datos.get("latencias_llm_ms", [])
    if lats_rag and lats_llm:
        avg_rag = statistics.mean(lats_rag)
        avg_llm = statistics.mean(lats_llm)
        if avg_llm > avg_rag * 3:
            recomendaciones.append("El LLM representa >75% de la latencia. Evaluar caché de respuestas frecuentes.")
        if avg_rag > 500:
            recomendaciones.append("Latencia RAG elevada (>500 ms). Considerar reducir k=4 a k=2 o usar índice HNSW.")
    if datos["total_errores"] / max(datos["total_consultas"], 1) > 0.1:
        recomendaciones.append("Tasa de error >10%. Revisar conectividad con GitHub Models y validez del token.")
    if len(anomalias) > 3:
        recomendaciones.append("Múltiples anomalías de latencia. Implementar circuit breaker y timeout explícito.")

    return {
        "total_anomalias": len(anomalias),
        "umbral_anomalia_ms": _percentil(latencias, 95),
        "endpoint_mas_lento": endpoint_lento,
        "latencia_promedio_endpoint_ms": round(lat_max, 2),
        "hora_pico": hora_pico,
        "patrones_detectados": patrones,
        "recomendaciones": recomendaciones,
        "errores_recientes": [
            {"timestamp": e["timestamp"], "endpoint": e["endpoint"], "error": e["error"]}
            for e in eventos_error[-5:]
        ],
    }
