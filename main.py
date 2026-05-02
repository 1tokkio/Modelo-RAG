"""
main.py — API FastAPI para el agente de inventario Retail S.A.
Endpoints:
  POST /consulta  →  consulta general de inventario
  POST /alerta    →  análisis de SKU específico y alerta de reorden
  POST /pedido    →  recomendación de orden de compra
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from rag import get_retriever

load_dotenv()

app = FastAPI(title="Retail S.A. — Agente de Inventario")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cliente OpenAI apuntando a GitHub Models
client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("GITHUB_TOKEN"),
)

retriever = get_retriever()


# ── Modelos de entrada ────────────────────────────────────────────────────────

class Pregunta(BaseModel):
    pregunta: str

class AlertaSKU(BaseModel):
    sku: str

class SolicitudPedido(BaseModel):
    sku: str
    stock_actual: int


# ── Utilidad: recuperar contexto RAG ─────────────────────────────────────────

def recuperar_contexto(query: str) -> str:
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)


# ── Endpoint 1: consulta general ─────────────────────────────────────────────

@app.post("/consulta")
def consulta_general(body: Pregunta):
    """
    Consulta libre sobre el estado del inventario.
    Ejemplo: 'qué productos tienen stock crítico'
    """
    contexto = recuperar_contexto(body.pregunta)

    respuesta = client.chat.completions.create(
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
                )
            },
            {
                "role": "user",
                "content": f"Contexto:\n{contexto}\n\nPregunta: {body.pregunta}"
            }
        ]
    )

    return {"respuesta": respuesta.choices[0].message.content}


# ── Endpoint 2: alerta de reorden por SKU ────────────────────────────────────

@app.post("/alerta")
def alerta_reorden(body: AlertaSKU):
    """
    Analiza el estado de un SKU específico y determina si requiere reabastecimiento.
    Ejemplo: {"sku": "ELEC-001"}
    """
    contexto = recuperar_contexto(f"inventario stock ventas {body.sku}")

    respuesta = client.chat.completions.create(
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
                )
            },
            {
                "role": "user",
                "content": f"Contexto:\n{contexto}\n\nAnaliza el SKU: {body.sku}"
            }
        ]
    )

    return {
        "sku": body.sku,
        "analisis": respuesta.choices[0].message.content
    }


# ── Endpoint 3: recomendación de pedido ──────────────────────────────────────

@app.post("/pedido")
def recomendar_pedido(body: SolicitudPedido):
    """
    Genera una recomendación de orden de compra para un SKU dado el stock actual.
    Ejemplo: {"sku": "ELEC-001", "stock_actual": 8}
    """
    contexto = recuperar_contexto(
        f"pedido reorden proveedor lead time {body.sku} demanda ventas"
    )

    respuesta = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente de compras para Retail S.A. "
                    "Calcula la cantidad a pedir usando la política interna: "
                    "30 días de demanda proyectada + 20% buffer de seguridad − stock actual. "
                    "Responde en este formato:\n"
                    "CANTIDAD SUGERIDA: [número] unidades\n"
                    "PROVEEDOR: [nombre]\n"
                    "FECHA LÍMITE DE PEDIDO: [considerando lead time]\n"
                    "COSTO ESTIMADO: [en CLP]\n"
                    "REQUIERE APROBACIÓN: [Sí / No — pedidos sobre $5.000.000 CLP sí]\n"
                    "JUSTIFICACIÓN: [basada en datos del contexto]"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Contexto:\n{contexto}\n\n"
                    f"SKU: {body.sku}\n"
                    f"Stock actual: {body.stock_actual} unidades\n"
                    f"Genera la recomendación de pedido."
                )
            }
        ]
    )

    return {
        "sku": body.sku,
        "stock_actual": body.stock_actual,
        "recomendacion": respuesta.choices[0].message.content
    }
