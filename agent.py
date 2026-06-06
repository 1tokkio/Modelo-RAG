"""
agent.py — Agente conversacional con herramientas para Retail S.A.
Decide automáticamente si usar consulta, alerta o pedido según la pregunta del usuario.
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from rag import get_retriever
from memory import registrar

load_dotenv()

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("GITHUB_TOKEN"),
)

retriever = get_retriever()


# Herramientas disponibles para el agente

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consulta_inventario",
            "description": "Responde preguntas generales sobre el inventario, stock, productos o ventas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": "La pregunta del usuario sobre el inventario."
                    }
                },
                "required": ["pregunta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "alerta_reorden",
            "description": "Analiza si un SKU específico requiere reabastecimiento urgente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "El código SKU del producto a analizar. Ejemplo: ELEC-001"
                    }
                },
                "required": ["sku"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recomendar_pedido",
            "description": "Genera una recomendación de orden de compra para un SKU dado el stock actual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "El código SKU del producto."
                    },
                    "stock_actual": {
                        "type": "integer",
                        "description": "Stock actual en bodega."
                    }
                },
                "required": ["sku", "stock_actual"]
            }
        }
    }
]


# Implementación de cada herramienta 

def _recuperar_contexto(query: str) -> str:
    docs = retriever.invoke(query)
    return "\n\n".join(d.page_content for d in docs)


def consulta_inventario(pregunta: str) -> str:
    contexto = _recuperar_contexto(pregunta)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente especializado en gestión de inventario para Retail S.A. "
                    "Responde SOLO con información del contexto provisto. "
                    "Si no tienes datos suficientes, indícalo."
                )
            },
            {
                "role": "user",
                "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"
            }
        ]
    )
    return resp.choices[0].message.content


def alerta_reorden(sku: str) -> str:
    contexto = _recuperar_contexto(f"inventario stock ventas {sku}")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente de inventario para Retail S.A. "
                    "Analiza el SKU solicitado y responde en este formato:\n"
                    "ESTADO: [CRÍTICO / ALERTA / NORMAL]\n"
                    "ANÁLISIS: [resumen de stock actual vs mínimo]\n"
                    "ACCIÓN: [qué se debe hacer y cuándo]"
                )
            },
            {
                "role": "user",
                "content": f"Contexto:\n{contexto}\n\nAnaliza el SKU: {sku}"
            }
        ]
    )
    return resp.choices[0].message.content


def recomendar_pedido(sku: str, stock_actual: int) -> str:
    contexto = _recuperar_contexto(f"pedido reorden proveedor lead time {sku} demanda")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente de compras para Retail S.A. "
                    "Calcula la cantidad a pedir: 30 días de demanda + 20% buffer − stock actual. "
                    "Responde en este formato:\n"
                    "CANTIDAD SUGERIDA: [número] unidades\n"
                    "PROVEEDOR: [nombre]\n"
                    "FECHA LÍMITE DE PEDIDO: [considerando lead time]\n"
                    "COSTO ESTIMADO: [en CLP]\n"
                    "REQUIERE APROBACIÓN: [Sí / No]\n"
                    "JUSTIFICACIÓN: [basada en datos del contexto]"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Contexto:\n{contexto}\n\n"
                    f"SKU: {sku}\nStock actual: {stock_actual} unidades\n"
                    f"Genera la recomendación de pedido."
                )
            }
        ]
    )
    return resp.choices[0].message.content


# Mapa de herramientas 

TOOL_MAP = {
    "consulta_inventario": lambda args: consulta_inventario(**args),
    "alerta_reorden":      lambda args: alerta_reorden(**args),
    "recomendar_pedido":   lambda args: recomendar_pedido(**args),
}


# Bucle principal del agente 

def ejecutar_agente(mensaje_usuario: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Eres un agente inteligente de gestión de inventario para Retail S.A. "
                "Analiza la solicitud del usuario y usa la herramienta más apropiada. "
                "Si no necesitas ninguna herramienta, responde directamente."
            )
        },
        {"role": "user", "content": mensaje_usuario}
    ]

    # Primera llamada: el modelo decide qué herramienta usar
    respuesta = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        tools=TOOLS,
        tool_choice="auto",
        messages=messages,
    )

    mensaje = respuesta.choices[0].message

    # Si no llamó ninguna herramienta, devolver respuesta directa
    if not mensaje.tool_calls:
        resultado = mensaje.content
        registrar("agente", {"mensaje": mensaje_usuario}, {"respuesta": resultado})
        return resultado

    # Ejecutar cada herramienta llamada por el modelo
    messages.append(mensaje)

    for tool_call in mensaje.tool_calls:
        nombre = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        print(f"[Agente] Usando herramienta: {nombre} con {args}")

        resultado_herramienta = TOOL_MAP[nombre](args)

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": resultado_herramienta,
        })

    # Segunda llamada: el modelo sintetiza los resultados
    respuesta_final = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=messages,
    )

    respuesta_texto = respuesta_final.choices[0].message.content
    registrar("agente", {"mensaje": mensaje_usuario}, {"respuesta": respuesta_texto})
    return respuesta_texto


# Modo interactivo (ejecución directa) 

if __name__ == "__main__":
    print("=== Agente de Inventario Retail S.A. ===")
    print("Escribe tu consulta o 'salir' para terminar.\n")

    while True:
        entrada = input("Tú: ").strip()
        if entrada.lower() in ("salir", "exit", "q"):
            print("Agente: Hasta luego.")
            break
        if not entrada:
            continue

        print("Agente: pensando...")
        respuesta = ejecutar_agente(entrada)
        print(f"Agente: {respuesta}\n")
