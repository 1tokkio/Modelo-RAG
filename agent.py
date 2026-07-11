import json
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from rag import get_retriever

load_dotenv()

HISTORIAL_PATH = "./data/historial_agente.json"

_retriever = get_retriever()

_llm = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("GITHUB_TOKEN"),
)

# Memoria de corto plazo: lista de mensajes de la sesión activa (en RAM)
_memoria_sesion: list[dict] = []


# Herramientas del agente

def consulta_inventario(pregunta: str) -> str:
    """Responde preguntas generales sobre inventario, productos y políticas de Retail S.A."""
    docs = _retriever.invoke(pregunta)
    contexto = "\n\n".join(d.page_content for d in docs)
    resp = _llm.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": (
                "Eres asistente especializado en gestión de inventario para Retail S.A. "
                "Responde SOLO con información del contexto provisto."
            )},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {pregunta}"},
        ],
    )
    return resp.choices[0].message.content


def analizar_sku(sku: str) -> str:
    """Analiza el estado de stock y genera alerta de reorden para un SKU específico."""
    docs = _retriever.invoke(f"inventario stock ventas {sku}")
    contexto = "\n\n".join(d.page_content for d in docs)
    resp = _llm.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": (
                "Eres asistente de inventario de Retail S.A. "
                "Responde en este formato exacto:\n"
                "ESTADO: [CRÍTICO / ALERTA / NORMAL]\n"
                "ANÁLISIS: [stock actual vs mínimo y tendencia]\n"
                "ACCIÓN: [qué hacer y cuándo]\n"
                "FUENTE: [datos usados]"
            )},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\nAnaliza el SKU: {sku}"},
        ],
    )
    return resp.choices[0].message.content


def recomendar_pedido(entrada: str) -> str:
    """Recomienda cantidad a pedir. Entrada esperada: 'SKU STOCK_ACTUAL' (ej: 'ELEC-001 15')."""
    partes = entrada.strip().split()
    sku   = partes[0] if partes else entrada
    stock = partes[1] if len(partes) > 1 else "no especificado"

    docs = _retriever.invoke(f"pedido proveedor lead time demanda {sku}")
    contexto = "\n\n".join(d.page_content for d in docs)
    resp = _llm.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role": "system", "content": (
                "Eres asistente de compras de Retail S.A. "
                "Fórmula: cantidad = demanda_30d × 1.2 − stock_actual. "
                "Responde en este formato:\n"
                "CANTIDAD SUGERIDA: [número] unidades\n"
                "PROVEEDOR: [nombre]\n"
                "FECHA LÍMITE DE PEDIDO: [considerando lead time]\n"
                "COSTO ESTIMADO: [en CLP]\n"
                "REQUIERE APROBACIÓN: [Sí/No — sobre $5.000.000 CLP sí]\n"
                "JUSTIFICACIÓN: [basada en el contexto]"
            )},
            {"role": "user", "content": (
                f"Contexto:\n{contexto}\n\n"
                f"SKU: {sku}\nStock actual: {stock} unidades\n"
                f"Genera la recomendación de pedido."
            )},
        ],
    )
    return resp.choices[0].message.content


_HERRAMIENTAS = {
    "consulta_inventario": consulta_inventario,
    "analizar_sku":        analizar_sku,
    "recomendar_pedido":   recomendar_pedido,
}

_DESCRIPCION_HERRAMIENTAS = (
    "- consulta_inventario(pregunta): Responde preguntas generales sobre el inventario, "
    "productos, stock y políticas de Retail S.A.\n"
    "- analizar_sku(sku): Analiza el estado de stock de un SKU específico (ej: ELEC-001) "
    "y genera alerta de reorden si corresponde.\n"
    "- recomendar_pedido(sku stock_actual): Calcula la cantidad a pedir para un SKU. "
    "Pasa el SKU y el stock actual separados por espacio (ej: 'ELEC-001 15')."
)

_SYSTEM_REACT = (
    "Eres un agente de gestión de inventario para Retail S.A. "
    "Tienes acceso a estas herramientas:\n"
    f"{_DESCRIPCION_HERRAMIENTAS}\n\n"
    "Sigue este formato en cada paso:\n"
    "Thought: [razona qué hacer]\n"
    "Action: [nombre exacto de la herramienta]\n"
    "Action Input: [el input para la herramienta]\n\n"
    "Cuando tengas la respuesta completa, escribe:\n"
    "Thought: Tengo la respuesta final\n"
    "Final Answer: [respuesta completa para el usuario]"
)


# ---------------------------------------------------------------------------
# Ciclo ReAct manual: Thought → Action → Observation → ... → Final Answer
# ---------------------------------------------------------------------------

def ejecutar_agente(pregunta: str, max_iter: int = 6) -> str:
    """
    Ciclo ReAct implementado manualmente.
    El LLM razona (Thought), elige una herramienta (Action), recibe el resultado
    (Observation) y repite hasta emitir Final Answer o agotar max_iter.
    """
    mensajes = [{"role": "system", "content": _SYSTEM_REACT}]

    # Inyectar historial de sesión (últimos 10 mensajes)
    mensajes.extend(_memoria_sesion[-10:])
    mensajes.append({"role": "user", "content": pregunta})

    for _ in range(max_iter):
        resp = _llm.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=mensajes,
        )
        texto = resp.choices[0].message.content.strip()
        mensajes.append({"role": "assistant", "content": texto})

        if "Final Answer:" in texto:
            return texto.split("Final Answer:", 1)[-1].strip()

        # Parsear Action y Action Input del texto generado por el LLM
        action      = _extraer_linea(texto, "Action:")
        action_input = _extraer_linea(texto, "Action Input:")

        if action and action in _HERRAMIENTAS:
            observation = _HERRAMIENTAS[action](action_input)
            mensajes.append({"role": "user", "content": f"Observation: {observation}"})
        else:
            # Si el LLM no generó una acción válida, pedirle que continúe
            mensajes.append({"role": "user", "content": "Observation: Herramienta no reconocida. Usa solo las herramientas disponibles."})

    return "No se pudo completar el razonamiento. Intenta reformular la pregunta."


def _extraer_linea(texto: str, prefijo: str) -> str:
    """Extrae el valor de una línea con formato 'Prefijo: valor'."""
    for linea in texto.splitlines():
        if linea.strip().startswith(prefijo):
            return linea.split(prefijo, 1)[-1].strip()
    return ""


# ---------------------------------------------------------------------------
# Memoria de sesión (RAM) — se actualiza desde main.py tras cada respuesta
# ---------------------------------------------------------------------------

def agregar_a_memoria_sesion(pregunta: str, respuesta: str) -> None:
    _memoria_sesion.append({"role": "user",      "content": pregunta})
    _memoria_sesion.append({"role": "assistant", "content": respuesta})


def conteo_mensajes_sesion() -> int:
    return len(_memoria_sesion)


# ---------------------------------------------------------------------------
# Memoria de largo plazo (JSON en disco)
# ---------------------------------------------------------------------------

def guardar_historial(pregunta: str, respuesta: str) -> None:
    """Persiste el par pregunta-respuesta en disco (sobrevive reinicios del servidor)."""
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
