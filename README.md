# Retail S.A. — Agente de Inventario con LLM y RAG

Solución de soporte a decisiones en gestión de inventario, implementada con LangChain, FastAPI y GitHub Models.

## Descripción

Sistema que recibe consultas sobre inventario, analiza el estado de productos por SKU y genera recomendaciones de pedido, usando un pipeline RAG sobre la base de conocimiento interna de la empresa.

## Tecnologías

- Python 3.10+
- FastAPI — API REST
- LangChain — orquestación del pipeline RAG
- ChromaDB — base de datos vectorial
- GitHub Models (Azure Inference API) — LLM y embeddings
- GPT-4o-mini — generación de respuestas
- text-embedding-3-small — embeddings semánticos

## Estructura

```
retailsa-rag/
├── main.py              # API FastAPI con los 3 endpoints
├── rag.py               # Pipeline RAG con ChromaDB
├── data/
│   └── inventario.txt   # Base de conocimiento
├── frontend.html        # Frontend para pruebas
├── .env.example         # Plantilla de variables de entorno
├── .gitignore
└── README.md
```

## Instalación

**1. Clonar el repositorio**
```bash
git clone https://github.com/tu-usuario/retailsa-rag.git
cd retailsa-rag
```

**2. Crear y activar entorno virtual**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

**3. Instalar dependencias**
```bash
pip install -r requirements.txt
```

**4. Configurar variables de entorno**
```bash
cp .env.example .env
```
Edita `.env` con tu token de GitHub Models:
```
OPENAI_BASE_URL="https://models.inference.ai.azure.com"
OPENAI_EMBEDDINGS_URL="https://models.github.ai/inference"
GITHUB_TOKEN="tu_token_aqui"
```

## Ejecución

```bash
uvicorn main:app --reload
```

La primera vez construye el índice vectorial en `chroma_db/`. Las siguientes veces lo carga desde disco.

Servidor disponible en: `http://127.0.0.1:8000`

## Pruebas

**Opción 1 — Frontend visual**  
Abre `frontend.html` en el navegador con el servidor corriendo.

**Opción 2 — Swagger UI**  
Abre `http://127.0.0.1:8000/docs`

**Opción 3 — curl**
```bash
curl -X POST http://127.0.0.1:8000/consulta \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "qué productos tienen stock crítico"}'

curl -X POST http://127.0.0.1:8000/alerta \
  -H "Content-Type: application/json" \
  -d '{"sku": "ELEC-001"}'

curl -X POST http://127.0.0.1:8000/pedido \
  -H "Content-Type: application/json" \
  -d '{"sku": "ELEC-001", "stock_actual": 8}'
```

## Endpoints

| Endpoint | Descripción |
|---|---|
| `POST /consulta` | Consulta libre sobre inventario |
| `POST /alerta` | Análisis de estado de un SKU específico |
| `POST /pedido` | Recomendación de orden de compra |

## Regenerar base vectorial

Si modificas `data/inventario.txt`, elimina `chroma_db/` y reinicia:
```bash
# Windows
Remove-Item -Recurse -Force chroma_db

# Mac/Linux
rm -rf chroma_db
```

## Autores

- ISY0101 — Ingeniería de Soluciones con IA
- DuocUC — 2025
