"""
main.py — API principal del Agente de Inventario Retail S.A.

Expone los siguientes endpoints:
  GET  /              → frontend web
  POST /consulta      → consulta libre sobre el inventario
  POST /alerta        → análisis de reorden para un SKU
  POST /pedido        → recomendación de orden de compra
  GET  /metricas      → resumen de métricas de observabilidad
  GET  /eventos       → log de últimos N eventos
  GET  /analisis      → patrones detectados y recomendaciones
  POST /test-consistencia → mide la consistencia de respuestas para una misma pregunta

Cada endpoint mide por separado la latencia de la fase RAG (ChromaDB)
y la fase LLM (GitHub Models) antes de registrarlas en observability.py.
"""

import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI

from rag import get_retriever
from observability import registrar_llamada, obtener_resumen, obtener_eventos, obtener_analisis
from security import validar_input, validar_sku, verificar_rate_limit, sanitizar_respuesta

load_dotenv()

app = FastAPI(title="Retail S.A. — Agente de Inventario")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# El cliente apunta a GitHub Models usando el token de GitHub como clave de API
cliente_llm = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("GITHUB_TOKEN"),
)

# El retriever se construye una sola vez al iniciar el servidor
retriever = get_retriever()


# ---------------------------------------------------------------------------
# Modelos de entrada
# ---------------------------------------------------------------------------

class Pregunta(BaseModel):
    pregunta: str

class AlertaSKU(BaseModel):
    sku: str

class SolicitudPedido(BaseModel):
    sku: str
    stock_actual: int


# ---------------------------------------------------------------------------
# Endpoints de negocio
# ---------------------------------------------------------------------------

@app.get("/")
def frontend():
    return FileResponse("frontend.html")


@app.post("/consulta")
def consulta_general(body: Pregunta, request: Request):
    """Consulta libre sobre el inventario. El agente elige qué información recuperar."""
    ip       = request.client.host
    pregunta = validar_input(body.pregunta, "pregunta")
    verificar_rate_limit(ip)

    # Fase RAG: recuperar contexto semántico desde ChromaDB
    t0       = time.time()
    docs     = retriever.invoke(pregunta)
    contexto = "\n\n".join(d.page_content for d in docs)
    t_rag    = (time.time() - t0) * 1000

    # Fase LLM: generar respuesta con el contexto recuperado
    error_msg       = None
    respuesta_texto = ""
    t1 = time.time()
    try:
        respuesta = cliente_llm.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente especializado en gestión de inventario para Retail S.A. "
                        "Responde SOLO con información del contexto provisto. "
                        "Si no tienes datos suficientes, indícalo. "
                        "Sé directo y usa lenguaje claro para el jefe de compras."
                    ),
                },
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"},
            ],
        )
        respuesta_texto = sanitizar_respuesta(respuesta.choices[0].message.content)
        return {"respuesta": respuesta_texto}
    except Exception as e:
        error_msg = type(e).__name__
        raise
    finally:
        t_llm = (time.time() - t1) * 1000
        registrar_llamada(
            "consulta", pregunta, t_rag + t_llm,
            error_msg is None, error_msg, respuesta_texto,
            t_rag, t_llm,
        )


@app.post("/alerta")
def alerta_reorden(body: AlertaSKU, request: Request):
    """Analiza el estado de un SKU y determina si requiere reabastecimiento urgente."""
    ip  = request.client.host
    sku = validar_sku(body.sku)
    verificar_rate_limit(ip)

    t0       = time.time()
    docs     = retriever.invoke(f"inventario stock ventas {sku}")
    contexto = "\n\n".join(d.page_content for d in docs)
    t_rag    = (time.time() - t0) * 1000

    error_msg       = None
    respuesta_texto = ""
    t1 = time.time()
    try:
        respuesta = cliente_llm.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente de inventario para Retail S.A. "
                        "Analiza el SKU solicitado usando el contexto y responde en este formato:\n"
                        "ESTADO: [CRÍTICO / ALERTA / NORMAL]\n"
                        "ANÁLISIS: [resumen de stock actual vs mínimo y tendencia de ventas]\n"
                        "ACCIÓN: [qué se debe hacer y cuándo]\n"
                        "FUENTE: [qué datos usaste para esta conclusión]"
                    ),
                },
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nAnaliza el SKU: {sku}"},
            ],
        )
        respuesta_texto = respuesta.choices[0].message.content
        return {"sku": sku, "analisis": respuesta_texto}
    except Exception as e:
        error_msg = type(e).__name__
        raise
    finally:
        t_llm = (time.time() - t1) * 1000
        registrar_llamada(
            "alerta", sku, t_rag + t_llm,
            error_msg is None, error_msg, respuesta_texto,
            t_rag, t_llm,
        )


@app.post("/pedido")
def recomendar_pedido(body: SolicitudPedido, request: Request):
    """
    Genera una recomendación de orden de compra.
    Política interna: cantidad = demanda_30d × 1.2 − stock_actual.
    Pedidos sobre $5.000.000 CLP requieren aprobación gerencial.
    """
    ip  = request.client.host
    sku = validar_sku(body.sku)
    verificar_rate_limit(ip)

    t0       = time.time()
    docs     = retriever.invoke(f"pedido reorden proveedor lead time {sku} demanda ventas")
    contexto = "\n\n".join(d.page_content for d in docs)
    t_rag    = (time.time() - t0) * 1000

    error_msg       = None
    respuesta_texto = ""
    t1 = time.time()
    try:
        respuesta = cliente_llm.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente de compras para Retail S.A. "
                        "Calcula la cantidad a pedir: 30 días de demanda proyectada × 1.2 − stock actual. "
                        "Responde en este formato:\n"
                        "CANTIDAD SUGERIDA: [número] unidades\n"
                        "PROVEEDOR: [nombre]\n"
                        "FECHA LÍMITE DE PEDIDO: [considerando lead time del proveedor]\n"
                        "COSTO ESTIMADO: [en CLP]\n"
                        "REQUIERE APROBACIÓN: [Sí / No — pedidos sobre $5.000.000 CLP sí]\n"
                        "JUSTIFICACIÓN: [basada en datos del contexto]"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Contexto:\n{contexto}\n\n"
                        f"SKU: {sku}\n"
                        f"Stock actual: {body.stock_actual} unidades\n"
                        f"Genera la recomendación de pedido."
                    ),
                },
            ],
        )
        respuesta_texto = respuesta.choices[0].message.content
        return {"sku": sku, "stock_actual": body.stock_actual, "recomendacion": respuesta_texto}
    except Exception as e:
        error_msg = type(e).__name__
        raise
    finally:
        t_llm = (time.time() - t1) * 1000
        registrar_llamada(
            "pedido", sku, t_rag + t_llm,
            error_msg is None, error_msg, respuesta_texto,
            t_rag, t_llm,
        )


# ---------------------------------------------------------------------------
# Endpoints de observabilidad
# ---------------------------------------------------------------------------

@app.get("/metricas")
def metricas():
    """Devuelve el resumen acumulado de métricas (latencia, tokens, tasa de éxito, etc.)."""
    return obtener_resumen()


@app.get("/eventos")
def eventos(limite: int = 50):
    """Devuelve los últimos N eventos del log estructurado."""
    return {"eventos": obtener_eventos(limite)}


@app.get("/analisis")
def analisis():
    """Analiza el historial de eventos y devuelve patrones detectados y recomendaciones."""
    return obtener_analisis()


@app.post("/test-consistencia")
def test_consistencia(body: Pregunta):
    """
    Envía la misma pregunta tres veces al LLM y mide la similitud entre respuestas
    usando el índice de Jaccard. Devuelve una evaluación ALTA / MEDIA / BAJA.
    """
    pregunta = validar_input(body.pregunta, "pregunta")
    docs     = retriever.invoke(pregunta)
    contexto = "\n\n".join(d.page_content for d in docs)

    respuestas = []
    for _ in range(3):
        r = cliente_llm.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente de inventario para Retail S.A. "
                               "Responde SOLO con información del contexto.",
                },
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"},
            ],
        )
        respuestas.append(r.choices[0].message.content)

    def similitud_jaccard(a: str, b: str) -> float:
        """Similitud entre dos textos basada en palabras únicas compartidas."""
        palabras_a = set(a.lower().split())
        palabras_b = set(b.lower().split())
        if not palabras_a or not palabras_b:
            return 0.0
        return round(len(palabras_a & palabras_b) / len(palabras_a | palabras_b) * 100, 1)

    sim_12 = similitud_jaccard(respuestas[0], respuestas[1])
    sim_13 = similitud_jaccard(respuestas[0], respuestas[2])
    sim_23 = similitud_jaccard(respuestas[1], respuestas[2])
    consistencia_pct = round((sim_12 + sim_13 + sim_23) / 3, 1)

    return {
        "pregunta": pregunta,
        "consistencia_pct": consistencia_pct,
        "similitud_1_2": sim_12,
        "similitud_1_3": sim_13,
        "similitud_2_3": sim_23,
        "respuestas": respuestas,
        "evaluacion": (
            "ALTA"  if consistencia_pct >= 70 else
            "MEDIA" if consistencia_pct >= 40 else
            "BAJA"
        ),
    }
