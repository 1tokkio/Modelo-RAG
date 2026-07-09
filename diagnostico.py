"""
diagnostico.py — Auditor independiente del estado del sistema.

Verifica cada componente por separado sin depender del flujo normal de main.py,
lo que permite detectar fallos del LLM incluso cuando la API sigue respondiendo.
"""

import os
import time

from dotenv import load_dotenv
from openai import OpenAI, AuthenticationError, APIConnectionError, APIStatusError

load_dotenv()


def verificar_llm() -> dict:
    """
    Prueba la conexión al LLM con una llamada mínima real.
    Distingue entre error de autenticación, error de red y otros fallos.
    """
    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("GITHUB_TOKEN"),
    )
    t0 = time.time()
    try:
        client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=5,
            messages=[{"role": "user", "content": "responde: ok"}],
        )
        return {
            "estado": "OK",
            "latencia_ms": round((time.time() - t0) * 1000, 2),
            "error": None,
        }
    except AuthenticationError:
        return {"estado": "ERROR_AUTH", "latencia_ms": None, "error": "Token inválido o expirado. Verifica GITHUB_TOKEN en .env"}
    except APIConnectionError as e:
        return {"estado": "ERROR_CONEXION", "latencia_ms": None, "error": f"Sin conexión al endpoint: {str(e)}"}
    except APIStatusError as e:
        return {"estado": f"ERROR_HTTP_{e.status_code}", "latencia_ms": None, "error": str(e.message)}
    except Exception as e:
        return {"estado": "ERROR", "latencia_ms": None, "error": f"{type(e).__name__}: {str(e)}"}


def verificar_embeddings() -> dict:
    """
    Prueba el endpoint de embeddings (distinto al del LLM).
    Los embeddings usan OPENAI_EMBEDDINGS_URL y también requieren el GITHUB_TOKEN.
    """
    from openai import OpenAI as _OpenAI
    client = _OpenAI(
        base_url=os.getenv("OPENAI_EMBEDDINGS_URL"),
        api_key=os.getenv("GITHUB_TOKEN"),
    )
    t0 = time.time()
    try:
        client.embeddings.create(model="text-embedding-3-small", input="test")
        return {"estado": "OK", "latencia_ms": round((time.time() - t0) * 1000, 2), "error": None}
    except AuthenticationError:
        return {"estado": "ERROR_AUTH", "latencia_ms": None, "error": "Token inválido para el endpoint de embeddings"}
    except APIConnectionError as e:
        return {"estado": "ERROR_CONEXION", "latencia_ms": None, "error": f"Sin conexión al endpoint de embeddings: {str(e)}"}
    except APIStatusError as e:
        return {"estado": f"ERROR_HTTP_{e.status_code}", "latencia_ms": None, "error": str(e.message)}
    except Exception as e:
        return {"estado": "ERROR", "latencia_ms": None, "error": f"{type(e).__name__}: {str(e)}"}


def verificar_chromadb() -> dict:
    """Comprueba que el índice vectorial exista en disco y no esté vacío."""
    chroma_dir = "./chroma_db"
    if not os.path.exists(chroma_dir):
        return {"estado": "SIN_INDICE", "error": "chroma_db/ no existe — inicia el servidor para generarlo"}
    if not os.listdir(chroma_dir):
        return {"estado": "INDICE_VACIO", "error": "chroma_db/ está vacío — elimínalo y reinicia el servidor"}
    return {"estado": "OK", "error": None}


def verificar_datos() -> dict:
    """Comprueba que el archivo de base de conocimiento esté presente."""
    ruta = "./data/inventario.txt"
    if not os.path.exists(ruta):
        return {"estado": "SIN_ARCHIVO", "error": "data/inventario.txt no encontrado"}
    size = os.path.getsize(ruta)
    return {"estado": "OK", "error": None, "bytes": size}


def estado_completo() -> dict:
    """Ejecuta los cuatro diagnósticos y devuelve el estado global del sistema."""
    llm        = verificar_llm()
    embeddings = verificar_embeddings()
    chroma     = verificar_chromadb()
    datos      = verificar_datos()

    componentes_ok = all(c["estado"] == "OK" for c in [llm, embeddings, chroma, datos])

    return {
        "sistema":    "OK" if componentes_ok else "DEGRADADO",
        "llm":        llm,
        "embeddings": embeddings,
        "chromadb":   chroma,
        "datos":      datos,
    }
