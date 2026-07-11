"""
agent.py — Agente ReAct de inventario con memoria de sesión y persistente.

Expone un AgentExecutor con 3 herramientas especializadas. La memoria de
corto plazo (ConversationBufferMemory) mantiene el contexto dentro de la
sesión activa; el historial de largo plazo persiste en JSON entre reinicios.
"""

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from rag import get_retriever

load_dotenv()

HISTORIAL_PATH = "./data/historial_agente.json"

_retriever = get_retriever()

_llm = ChatOpenAI(
    model="gpt-4o-mini",
    openai_api_key=os.getenv("GITHUB_TOKEN"),
    openai_api_base=os.getenv("OPENAI_BASE_URL"),
    temperature=0.1,
)

# Memoria de corto plazo: visible al agente en cada ciclo ReAct de la sesión
memoria_sesion = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=False,
)


# ---------------------------------------------------------------------------
# Herramientas del agente
# ---------------------------------------------------------------------------

@tool
def consulta_inventario(pregunta: str) -> str:
    """Responde preguntas generales sobre inventario, productos y políticas de Retail S.A."""
    docs = _retriever.invoke(pregunta)
    contexto = "\n\n".join(d.page_content for d in docs)
    respuesta = _llm.invoke(
        f"Eres asistente especializado en gestión de inventario para Retail S.A. "
        f"Responde SOLO con información del contexto provisto. "
        f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"
    )
    return respuesta.content


@tool
def analizar_sku(sku: str) -> str:
    """Analiza el estado de stock y genera alerta de reorden para un SKU específico (ej: ELEC-001)."""
    docs = _retriever.invoke(f"inventario stock ventas {sku}")
    contexto = "\n\n".join(d.page_content for d in docs)
    respuesta = _llm.invoke(
        f"Eres asistente de inventario de Retail S.A. "
        f"Analiza el SKU {sku} con este contexto:\n{contexto}\n"
        f"Responde en este formato:\n"
        f"ESTADO: [CRÍTICO / ALERTA / NORMAL]\n"
        f"ANÁLISIS: [stock actual vs mínimo y tendencia]\n"
        f"ACCIÓN: [qué hacer y cuándo]\n"
        f"FUENTE: [datos usados]"
    )
    return respuesta.content


@tool
def recomendar_pedido(entrada: str) -> str:
    """Recomienda cantidad a pedir para un SKU. Entrada: 'SKU STOCK_ACTUAL' (ej: 'ELEC-001 15')."""
    partes = entrada.strip().split()
    sku    = partes[0] if partes else entrada
    stock  = partes[1] if len(partes) > 1 else "no especificado"

    docs = _retriever.invoke(f"pedido proveedor lead time demanda {sku}")
    contexto = "\n\n".join(d.page_content for d in docs)
    respuesta = _llm.invoke(
        f"Eres asistente de compras de Retail S.A. "
        f"Fórmula de pedido: demanda_30d × 1.2 − stock_actual. "
        f"SKU: {sku}, Stock actual: {stock} unidades.\n"
        f"Contexto:\n{contexto}\n"
        f"Responde:\n"
        f"CANTIDAD SUGERIDA: [número] unidades\n"
        f"PROVEEDOR: [nombre]\n"
        f"FECHA LÍMITE DE PEDIDO: [considerando lead time]\n"
        f"COSTO ESTIMADO: [en CLP]\n"
        f"REQUIERE APROBACIÓN: [Sí/No — sobre $5.000.000 CLP sí]\n"
        f"JUSTIFICACIÓN: [basada en el contexto]"
    )
    return respuesta.content


# ---------------------------------------------------------------------------
# Prompt ReAct (definido localmente, sin depender de LangChain Hub)
# ---------------------------------------------------------------------------

_REACT_PROMPT = PromptTemplate.from_template(
    "Eres un agente de gestión de inventario para Retail S.A. con acceso a herramientas especializadas.\n"
    "Razona paso a paso antes de actuar. Si el usuario menciona un SKU, úsalo directamente en la herramienta correspondiente.\n\n"
    "Herramientas disponibles:\n{tools}\n\n"
    "Formato obligatorio:\n"
    "Thought: razona qué hacer\n"
    "Action: nombre exacto de la herramienta (una de [{tool_names}])\n"
    "Action Input: el input para la herramienta\n"
    "Observation: resultado de la herramienta\n"
    "... (repite hasta tener suficiente información)\n"
    "Thought: Tengo la respuesta final\n"
    "Final Answer: respuesta completa para el usuario\n\n"
    "Historial de conversación:\n{chat_history}\n\n"
    "Pregunta: {input}\n"
    "{agent_scratchpad}"
)

_TOOLS = [consulta_inventario, analizar_sku, recomendar_pedido]

_agent = create_react_agent(llm=_llm, tools=_TOOLS, prompt=_REACT_PROMPT)

executor = AgentExecutor(
    agent=_agent,
    tools=_TOOLS,
    memory=memoria_sesion,
    verbose=False,
    max_iterations=6,
    handle_parsing_errors=True,
)


# ---------------------------------------------------------------------------
# Memoria de largo plazo (JSON en disco)
# ---------------------------------------------------------------------------

def guardar_historial(pregunta: str, respuesta: str) -> None:
    """Agrega un par pregunta-respuesta al historial persistente."""
    os.makedirs("./data", exist_ok=True)
    historial = _leer_historial()
    historial.append({
        "timestamp": datetime.now().isoformat(),
        "pregunta":  pregunta,
        "respuesta": respuesta,
    })
    with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
        json.dump(historial[-200:], f, ensure_ascii=False, indent=2)


def obtener_historial(limite: int = 20) -> list:
    """Devuelve las últimas `limite` entradas del historial persistente."""
    return _leer_historial()[-limite:]


def _leer_historial() -> list:
    if not os.path.exists(HISTORIAL_PATH):
        return []
    try:
        with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
