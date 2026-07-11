import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI

from rag import get_retriever
from observability import registrar_llamada, obtener_resumen, obtener_eventos, obtener_analisis
from security import validar_input, validar_sku, verificar_rate_limit, sanitizar_respuesta
from diagnostico import estado_completo
from agent import executor, obtener_historial, guardar_historial

load_dotenv()

app = FastAPI(title="Retail S.A. — Agente de Inventario")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

cliente_llm = OpenAI(
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


@app.get("/")
def frontend():
    return FileResponse("frontend.html")


@app.post("/consulta")
def consulta_general(body: Pregunta, request: Request):
    ip       = request.client.host
    pregunta = validar_input(body.pregunta, "pregunta")
    verificar_rate_limit(ip)

    error_msg       = None
    respuesta_texto = ""
    t_rag = t_llm = 0.0
    try:
        t0       = time.time()
        docs     = retriever.invoke(pregunta)
        contexto = "\n\n".join(d.page_content for d in docs)
        t_rag    = (time.time() - t0) * 1000

        t1       = time.time()
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
        t_llm           = (time.time() - t1) * 1000
        respuesta_texto = sanitizar_respuesta(respuesta.choices[0].message.content)
        return {"respuesta": respuesta_texto}
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=502, detail=f"Error: {type(e).__name__} — {str(e)}")
    finally:
        registrar_llamada("consulta", pregunta, t_rag + t_llm, error_msg is None, error_msg, respuesta_texto, t_rag, t_llm)


@app.post("/alerta")
def alerta_reorden(body: AlertaSKU, request: Request):
    ip  = request.client.host
    sku = validar_sku(body.sku)
    verificar_rate_limit(ip)

    error_msg       = None
    respuesta_texto = ""
    t_rag = t_llm = 0.0
    try:
        t0       = time.time()
        docs     = retriever.invoke(f"inventario stock ventas {sku}")
        contexto = "\n\n".join(d.page_content for d in docs)
        t_rag    = (time.time() - t0) * 1000

        t1       = time.time()
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
        t_llm           = (time.time() - t1) * 1000
        respuesta_texto = respuesta.choices[0].message.content
        return {"sku": sku, "analisis": respuesta_texto}
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=502, detail=f"Error: {type(e).__name__} — {str(e)}")
    finally:
        registrar_llamada("alerta", sku, t_rag + t_llm, error_msg is None, error_msg, respuesta_texto, t_rag, t_llm)


@app.post("/pedido")
def recomendar_pedido(body: SolicitudPedido, request: Request):
    ip  = request.client.host
    sku = validar_sku(body.sku)
    verificar_rate_limit(ip)

    error_msg       = None
    respuesta_texto = ""
    t_rag = t_llm = 0.0
    try:
        t0       = time.time()
        docs     = retriever.invoke(f"pedido reorden proveedor lead time {sku} demanda ventas")
        contexto = "\n\n".join(d.page_content for d in docs)
        t_rag    = (time.time() - t0) * 1000

        t1       = time.time()
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
        t_llm           = (time.time() - t1) * 1000
        respuesta_texto = respuesta.choices[0].message.content
        return {"sku": sku, "stock_actual": body.stock_actual, "recomendacion": respuesta_texto}
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=502, detail=f"Error: {type(e).__name__} — {str(e)}")
    finally:
        registrar_llamada("pedido", sku, t_rag + t_llm, error_msg is None, error_msg, respuesta_texto, t_rag, t_llm)


@app.post("/agente")
def agente(body: Pregunta, request: Request):
    """
    Endpoint del agente ReAct. El agente razona autónomamente y elige la herramienta
    adecuada (consulta_inventario, analizar_sku o recomendar_pedido) según la pregunta.
    Mantiene memoria de conversación dentro de la sesión y persiste el historial en disco.
    """
    ip       = request.client.host
    pregunta = validar_input(body.pregunta, "pregunta")
    verificar_rate_limit(ip)

    resultado = executor.invoke({"input": pregunta})
    respuesta = resultado.get("output", "")
    guardar_historial(pregunta, respuesta)
    return {"respuesta": respuesta}


@app.get("/historial")
def historial(limite: int = 20):
    """
    Historial persistente del agente. Devuelve los últimos intercambios pregunta-respuesta
    guardados en disco (memoria de largo plazo entre reinicios del servidor).
    """
    return {
        "historial": obtener_historial(limite),
        "memoria_sesion": len(executor.memory.chat_memory.messages),
    }


@app.get("/health")
def health():
    """Diagnóstico rápido del estado de cada componente del sistema."""
    return estado_completo()


@app.get("/metricas")
def metricas():
    return obtener_resumen()


@app.get("/eventos")
def eventos(limite: int = 50):
    return {"eventos": obtener_eventos(limite)}


@app.get("/analisis")
def analisis():
    return obtener_analisis()


@app.post("/test-consistencia")
def test_consistencia(body: Pregunta):
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
                    "content": "Eres un asistente de inventario para Retail S.A. Responde SOLO con información del contexto.",
                },
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"},
            ],
        )
        respuestas.append(r.choices[0].message.content)

    def jaccard(a: str, b: str) -> float:
        sa, sb = set(a.lower().split()), set(b.lower().split())
        if not sa or not sb:
            return 0.0
        return round(len(sa & sb) / len(sa | sb) * 100, 1)

    sim_12 = jaccard(respuestas[0], respuestas[1])
    sim_13 = jaccard(respuestas[0], respuestas[2])
    sim_23 = jaccard(respuestas[1], respuestas[2])
    consistencia = round((sim_12 + sim_13 + sim_23) / 3, 1)

    return {
        "pregunta": pregunta,
        "consistencia_pct": consistencia,
        "similitud_1_2": sim_12,
        "similitud_1_3": sim_13,
        "similitud_2_3": sim_23,
        "respuestas": respuestas,
        "evaluacion": "ALTA" if consistencia >= 70 else "MEDIA" if consistencia >= 40 else "BAJA",
    }
