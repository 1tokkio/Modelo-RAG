import re
import time
from collections import defaultdict
from fastapi import HTTPException

_rate_limit: dict = defaultdict(list)
RATE_LIMIT_VENTANA_SEG = 60
RATE_LIMIT_MAX_SOLICITUDES = 20

PATRONES_PELIGROSOS = [
    r"<script.*?>.*?</script>",
    r"(drop|delete|truncate|insert|update)\s+table",
    r"(exec|execute|eval)\s*\(",
    r"[;\|&`$]",
]

MAX_LONGITUD_ENTRADA = 1000


def validar_input(texto: str, campo: str = "entrada") -> str:
    if not texto or not texto.strip():
        raise HTTPException(status_code=400, detail=f"El campo '{campo}' no puede estar vacío.")

    if len(texto) > MAX_LONGITUD_ENTRADA:
        raise HTTPException(
            status_code=400,
            detail=f"El campo '{campo}' excede el límite de {MAX_LONGITUD_ENTRADA} caracteres."
        )

    texto_lower = texto.lower()
    for patron in PATRONES_PELIGROSOS:
        if re.search(patron, texto_lower, re.IGNORECASE | re.DOTALL):
            raise HTTPException(status_code=400, detail="Entrada no permitida por política de seguridad.")

    return texto.strip()


def validar_sku(sku: str) -> str:
    sku = sku.strip().upper()
    if not re.match(r"^[A-Z]{2,10}-\d{3,6}$", sku):
        raise HTTPException(
            status_code=400,
            detail="Formato de SKU inválido. Use el formato: CATEGORIA-NNN (ej: ELEC-001)."
        )
    return sku


def verificar_rate_limit(ip: str) -> None:
    ahora = time.time()
    ventana = _rate_limit[ip]

    _rate_limit[ip] = [t for t in ventana if ahora - t < RATE_LIMIT_VENTANA_SEG]

    if len(_rate_limit[ip]) >= RATE_LIMIT_MAX_SOLICITUDES:
        raise HTTPException(
            status_code=429,
            detail=f"Límite de {RATE_LIMIT_MAX_SOLICITUDES} solicitudes por minuto alcanzado."
        )

    _rate_limit[ip].append(ahora)


def sanitizar_respuesta(texto: str) -> str:
    datos_sensibles = [
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        r"\b\d{7,8}-[\dkK]\b",
    ]
    for patron in datos_sensibles:
        texto = re.sub(patron, "[DATO PROTEGIDO]", texto)
    return texto
