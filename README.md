# Retail S.A. — Agente de Inventario con RAG y Observabilidad

Agente de soporte a decisiones para gestión de inventario, con sistema completo de observabilidad: métricas, logs estructurados y dashboard visual.

## Arquitectura

```
Usuario → FastAPI (main.py)
               ↓
         Pipeline RAG (rag.py)
         ChromaDB + text-embedding-3-small
               ↓
         GPT-4o-mini (GitHub Models)
               ↓
         Observabilidad (observability.py) → metricas.json + agent_events.jsonl
         Seguridad (security.py)           → validación, rate limit, sanitización
```

## Estructura

```
├── main.py                      # API FastAPI — 5 endpoints
├── rag.py                       # Pipeline RAG con ChromaDB
├── observability.py             # Métricas, latencia y logs
├── security.py                  # Validación, rate limiting y sanitización
├── frontend.html                # UI con dashboard integrado
├── data/
│   ├── inventario.txt           # Base de conocimiento
│   ├── metricas.json            # Métricas acumuladas (auto-generado)
│   └── agent_events.jsonl       # Log de eventos (auto-generado)
├── .env.example
└── requirements.txt
```

## Instalación

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Variables requeridas en `.env`:
```
OPENAI_BASE_URL="https://models.inference.ai.azure.com"
OPENAI_EMBEDDINGS_URL="https://models.github.ai/inference"
GITHUB_TOKEN="tu_token_aqui"
```

## Ejecución

```bash
uvicorn main:app --reload
```

Servidor en `http://127.0.0.1:8000` · Swagger en `http://127.0.0.1:8000/docs`

La primera vez construye el índice vectorial en `chroma_db/` automáticamente.

## Endpoints

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Frontend con dashboard integrado |
| `/consulta` | POST | Consulta libre sobre inventario |
| `/alerta` | POST | Análisis y alerta de reorden por SKU |
| `/pedido` | POST | Recomendación de orden de compra |
| `/metricas` | GET | Resumen de métricas de observabilidad |
| `/eventos` | GET | Log de últimos eventos del agente |

## Observabilidad

Cada consulta registra automáticamente:
- Latencia en milisegundos
- Tokens estimados consumidos
- Estado (éxito / error) y tipo de error
- Endpoint invocado y timestamp

El **Dashboard** (sección lateral del frontend) visualiza en tiempo real:
- KPIs: total consultas, tasa de éxito, latencia promedio, tokens
- Gráfico de latencia por consulta
- Distribución de consultas por endpoint
- Tasa de éxito vs errores
- Errores por tipo

## Seguridad

- Validación de formato para SKUs (`CATEGORIA-NNN`)
- Sanitización de inputs con detección de patrones peligrosos
- Rate limiting: 20 solicitudes por minuto por IP
- Protección de datos sensibles en respuestas

## Regenerar base vectorial

```powershell
Remove-Item -Recurse -Force chroma_db
uvicorn main:app --reload
```

## Referencias

- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. arXiv:2005.11401
- Chase, H. (2022). *LangChain*. https://github.com/langchain-ai/langchain
- Chroma. (2024). *ChromaDB Documentation*. https://docs.trychroma.com
- Microsoft. (2024). *GitHub Models*. https://github.com/marketplace/models

---

ISY0101 — Ingeniería de Soluciones con IA · DuocUC 2025
