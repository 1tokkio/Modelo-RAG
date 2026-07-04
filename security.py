"""
security.py — Validación de entradas, rate limiting y sanitización de salidas.

Todas las funciones de este módulo son invocadas desde main.py antes de
procesar cualquier request, asegurando que ni el LLM ni ChromaDB reciban
datos malformados o potencialmente peligrosos.
"""

import re
import time
from collections import defaultdict
from fastapi import HTTPException
from observability import registrar_audit

# Ventana de rate limiting: máximo 20 solicitudes por IP cada 60 segundos
RATE_LIMIT_VENTANA_SEG      = 60
RATE_LIMIT_MAX_SOLICITUDES  = 20
MAX_LONGITUD_ENTRADA        = 1000

# Historial de timestamps por IP (solo se mantiene en memoria durante la sesión)
_historial_ips: dict = defaultdict(list)

# Patrones que indican intentos de inyección o ejecución de código
_PATRONES_PELIGROSOS = [
    r"<script.*?>.*?</script>",                          # XSS
    r"(drop|delete|truncate|insert|update)\s+table",     # SQL injection
    r"(exec|execute|eval)\s*\(",                         # ejecución de código
    r"[;\|&`$]",                                         # caracteres de shell
]


def validar_input(texto: str, campo: str = "entrada") -> str:
    """
    Valida y limpia un texto libre antes de enviarlo al pipeline RAG/LLM.
    Lanza HTTP 400 si el texto está vacío, es muy largo o contiene patrones peligrosos.
    """
    if not texto or not texto.strip():
        raise HTTPException(
            status_code=400,
            detail=f"El campo '{campo}' no puede estar vacío."
        )
    if len(texto) > MAX_LONGITUD_ENTRADA:
        raise HTTPException(
            status_code=400,
            detail=f"El campo '{campo}' excede el límite de {MAX_LONGITUD_ENTRADA} caracteres."
        )
    texto_lower = texto.lower()
    for patron in _PATRONES_PELIGROSOS:
        if re.search(patron, texto_lower, re.IGNORECASE | re.DOTALL):
            raise HTTPException(
                status_code=400,
                detail="Entrada no permitida por política de seguridad."
            )
    return texto.strip()


def validar_sku(sku: str) -> str:
    """
    Valida que el SKU tenga el formato CATEGORIA-NNN (ej: ELEC-001).
    Normaliza a mayúsculas antes de validar.
    Lanza HTTP 400 si el formato no coincide.
    """
    sku = sku.strip().upper()
    if not re.match(r"^[A-Z]{2,10}-\d{3,6}$", sku):
        raise HTTPException(
            status_code=400,
            detail="Formato de SKU inválido. Use el formato: CATEGORIA-NNN (ej: ELEC-001)."
        )
    return sku


def verificar_rate_limit(ip: str) -> None:
    """
    Implementa una ventana deslizante por IP.
    Lanza HTTP 429 y registra en el log de auditoría si se supera el límite.
    """
    ahora = time.time()
    # Eliminar timestamps fuera de la ventana activa
    _historial_ips[ip] = [
        t for t in _historial_ips[ip]
        if ahora - t < RATE_LIMIT_VENTANA_SEG
    ]
    if len(_historial_ips[ip]) >= RATE_LIMIT_MAX_SOLICITUDES:
        registrar_audit(
            ip,
            "RATE_LIMIT_BLOQUEADO",
            f"solicitudes={len(_historial_ips[ip])} ventana={RATE_LIMIT_VENTANA_SEG}s"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Límite de {RATE_LIMIT_MAX_SOLICITUDES} solicitudes por minuto alcanzado."
        )
    _historial_ips[ip].append(ahora)


def sanitizar_respuesta(texto: str) -> str:
    """
    Elimina datos sensibles del texto generado por el LLM antes de enviarlo al cliente.
    Reemplaza números de tarjeta, correos y RUTs chilenos por '[DATO PROTEGIDO]'.
    """
    patrones_sensibles = [
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",           # tarjeta de crédito
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", # correo electrónico
        r"\b\d{7,8}-[\dkK]\b",                                   # RUT chileno
    ]
    for patron in patrones_sensibles:
        texto = re.sub(patron, "[DATO PROTEGIDO]", texto)
    return texto
