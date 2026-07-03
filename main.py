import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI

from rag import get_retriever
from observability import registrar_llamada, obtener_resumen, obtener_eventos
from security import validar_input, validar_sku, verificar_rate_limit, sanitizar_respuesta

load_dotenv()

app = FastAPI(title="Retail S.A. — Agente de Inventario")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("GITHUB_TOKEN"),
)

retriever = get_retriever()


class Pregunta(BaseModel):
    pregunta: str

class AlertaSKU(BaseModel):
    sku: str

class SolicitudPedido(BaseModel):
    sku: str
    stock_actual: int


def recuperar_contexto(query: str) -> str:
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)


@app.get("/")
def frontend():
    return FileResponse("frontend.html")


@app.post("/consulta")
def consulta_general(body: Pregunta, request: Request):
    ip = request.client.host
    verificar_rate_limit(ip)
    pregunta = validar_input(body.pregunta, "pregunta")

    inicio = time.time()
    error_msg = None
    respuesta_texto = ""
    try:
        contexto = recuperar_contexto(pregunta)
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
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"}
            ]
        )
        respuesta_texto = respuesta.choices[0].message.content
        respuesta_texto = sanitizar_respuesta(respuesta_texto)
        return {"respuesta": respuesta_texto}
    except Exception as e:
        error_msg = type(e).__name__
        raise
    finally:
        latencia = (time.time() - inicio) * 1000
        registrar_llamada("consulta", pregunta, latencia, error_msg is None, error_msg, respuesta_texto)


@app.post("/alerta")
def alerta_reorden(body: AlertaSKU, request: Request):
    ip = request.client.host
    verificar_rate_limit(ip)
    sku = validar_sku(body.sku)

    inicio = time.time()
    error_msg = None
    respuesta_texto = ""
    try:
        contexto = recuperar_contexto(f"inventario stock ventas {sku}")
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
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nAnaliza el SKU: {sku}"}
            ]
        )
        respuesta_texto = respuesta.choices[0].message.content
        return {"sku": sku, "analisis": respuesta_texto}
    except Exception as e:
        error_msg = type(e).__name__
        raise
    finally:
        latencia = (time.time() - inicio) * 1000
        registrar_llamada("alerta", sku, latencia, error_msg is None, error_msg, respuesta_texto)


@app.post("/pedido")
def recomendar_pedido(body: SolicitudPedido, request: Request):
    ip = request.client.host
    verificar_rate_limit(ip)
    sku = validar_sku(body.sku)

    inicio = time.time()
    error_msg = None
    respuesta_texto = ""
    try:
        contexto = recuperar_contexto(f"pedido reorden proveedor lead time {sku} demanda ventas")
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
                        f"SKU: {sku}\n"
                        f"Stock actual: {body.stock_actual} unidades\n"
                        f"Genera la recomendación de pedido."
                    )
                }
            ]
        )
        respuesta_texto = respuesta.choices[0].message.content
        return {"sku": sku, "stock_actual": body.stock_actual, "recomendacion": respuesta_texto}
    except Exception as e:
        error_msg = type(e).__name__
        raise
    finally:
        latencia = (time.time() - inicio) * 1000
        registrar_llamada("pedido", sku, latencia, error_msg is None, error_msg, respuesta_texto)


@app.get("/metricas")
def metricas():
    return obtener_resumen()


@app.get("/eventos")
def eventos(limite: int = 50):
    return {"eventos": obtener_eventos(limite)}
