# Retail S.A. — Agente de Inventario con RAG y Observabilidad

Agente de soporte a decisiones para gestión de inventario. Responde consultas sobre
stock, genera alertas de reorden y recomienda órdenes de compra usando un pipeline
RAG (Retrieval-Augmented Generation) con ChromaDB y GPT-4o-mini.

---

## Arquitectura

```
Usuario → FastAPI (main.py)
               │
       ┌───────┴────────┐
       │                │
  Pipeline RAG      Seguridad (security.py)
  (rag.py)          validación + rate limit
  ChromaDB
       │
  GPT-4o-mini
  (GitHub Models)
       │
  Observabilidad (observability.py)
  metricas.json + agent_events.jsonl
```

---

## Estructura del proyecto

```
├── main.py              # API FastAPI — 8 endpoints
├── rag.py               # Pipeline RAG: carga, indexa y recupera desde ChromaDB
├── observability.py     # Métricas, latencia RAG/LLM, logs y detección de anomalías
├── security.py          # Validación de entradas, rate limiting y sanitización
├── frontend.html        # Interfaz ERP con dashboard de observabilidad
├── data/
│   ├── inventario.txt           # Base de conocimiento (fuente de verdad)
│   ├── metricas.json            # Métricas acumuladas (se genera automáticamente)
│   ├── agent_events.jsonl       # Log de eventos por consulta (se genera automáticamente)
│   └── audit.log                # Log de eventos de seguridad (se genera automáticamente)
├── chroma_db/           # Índice vectorial persistido (se genera automáticamente)
├── .env.example         # Plantilla de variables de entorno
└── requirements.txt     # Dependencias Python
```

---

## Instalación y ejecución

```powershell
# 1. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
Copy-Item .env.example .env
# Editar .env y completar GITHUB_TOKEN

# 4. Iniciar el servidor
uvicorn main:app --reload
```

La primera vez, el servidor construye el índice vectorial en `chroma_db/` automáticamente.

- Frontend: `http://127.0.0.1:8000`
- Documentación interactiva: `http://127.0.0.1:8000/docs`

Variables requeridas en `.env`:
```
OPENAI_BASE_URL="https://models.inference.ai.azure.com"
OPENAI_EMBEDDINGS_URL="https://models.github.ai/inference"
GITHUB_TOKEN="tu_token_aqui"
```

---

## Endpoints

| Endpoint              | Método | Cuerpo de entrada                       | Descripción                                 |
|-----------------------|--------|-----------------------------------------|---------------------------------------------|
| `/`                   | GET    | —                                       | Interfaz web con dashboard                  |
| `/consulta`           | POST   | `{"pregunta": "..."}`                   | Consulta libre sobre el inventario          |
| `/alerta`             | POST   | `{"sku": "ELEC-001"}`                   | Análisis de reorden para un SKU             |
| `/pedido`             | POST   | `{"sku": "ELEC-001", "stock_actual": 8}`| Recomendación de orden de compra            |
| `/metricas`           | GET    | —                                       | Métricas acumuladas (latencia, tokens, etc.)|
| `/eventos`            | GET    | `?limite=50`                            | Últimos N eventos del log                   |
| `/analisis`           | GET    | —                                       | Patrones detectados y recomendaciones       |
| `/test-consistencia`  | POST   | `{"pregunta": "..."}`                   | Similitud Jaccard entre 3 respuestas        |

---

## Observabilidad

Cada consulta registra automáticamente:

- **Latencia RAG** — tiempo de recuperación semántica en ChromaDB
- **Latencia LLM** — tiempo de inferencia en GPT-4o-mini
- **Tokens estimados** — consumo acumulado
- **Nivel de log** — INFO / WARNING (anomalía) / ERROR
- **Anomalía** — marcada si la latencia supera 2× el promedio histórico

El dashboard (sección lateral del frontend) muestra en tiempo real:
- KPIs: total consultas, tasa de éxito, latencia promedio, tokens
- Percentiles P50 / P95 / P99
- Gráfico de latencia con puntos rojos en anomalías
- Desglose RAG vs LLM por consulta
- Distribución por endpoint y tasa de éxito/error
- Patrones detectados y recomendaciones automáticas

---

## Seguridad

- **Validación de entrada**: rechazo de XSS, SQL injection y caracteres de shell; límite de 1.000 caracteres
- **Validación de SKU**: formato estricto `CATEGORIA-NNN` (ej: `ELEC-001`)
- **Rate limiting**: 20 solicitudes por IP cada 60 segundos; bloqueos registrados en `audit.log`
- **Sanitización de salida**: datos sensibles (tarjetas, correos, RUTs) reemplazados por `[DATO PROTEGIDO]`

---

## Regenerar el índice vectorial

Necesario solo si se modifica `data/inventario.txt`:

```powershell
Remove-Item -Recurse -Force chroma_db
uvicorn main:app --reload
```

---

## Referencias

- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. arXiv:2005.11401
- Chase, H. (2022). *LangChain*. https://github.com/langchain-ai/langchain
- Chroma. (2024). *ChromaDB Documentation*. https://docs.trychroma.com
- Microsoft. (2024). *GitHub Models*. https://github.com/marketplace/models

---

ISY0101 — Ingeniería de Soluciones con IA · DuocUC 2025
