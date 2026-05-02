# Retail Agent — Agente de Gestión de Inventario con LLM y RAG

**ISY0101 Ingeniería de Soluciones con IA | DuocUC | 2025**

Agente inteligente que apoya las decisiones de reabastecimiento de inventario para Retail S.A., combinando datos internos del ERP con contexto externo (clima, feriados, tendencias) mediante un pipeline RAG + GPT-4o.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| LLM | OpenAI GPT-4o |
| Framework agente/RAG | LangChain 0.3 |
| Vector store | ChromaDB (persistente local) |
| Embeddings | OpenAI text-embedding-3-small |
| ERP | Odoo 17 (simulado con mock REST) |

## Estructura del proyecto

```
Modelo-RAG/
├── main.py              # Punto de entrada — agente interactivo y modo demo
├── rag/
│   ├── pipeline.py      # Pipeline RAG: indexación, retriever, chain
│   ├── loader.py        # Conversión de datos internos/externos a documentos
│   └── prompts.py       # System prompt y templates del agente
├── erp/
│   └── odoo_mock.py     # Simulación de la API REST de Odoo 17
├── data/
│   └── sample_data.py   # Datos de ejemplo: ventas, stock, contexto externo
├── requirements.txt
└── README.md
```

## Instalación

### Requisitos previos
- Python 3.11 o superior
- Cuenta OpenAI con acceso a GPT-4o y API key activa

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/1tokkio/Modelo-RAG.git
cd Modelo-RAG

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar la API key de OpenAI
cp .env.example .env
# Editar .env y agregar tu clave:
# OPENAI_API_KEY=sk-...
```

### Archivo .env
```
OPENAI_API_KEY=sk-tu-clave-aqui
```

## Ejecución

### Modo interactivo (chat)
```bash
python main.py
```

Comandos disponibles en el chat:
- `/alertas` — Muestra alertas automáticas de reorden del ERP
- `/erp` — Estado actual del inventario
- `/pedido` — Crear una orden de compra manualmente
- `/salir` — Terminar la sesión

### Modo demo (casos de uso predefinidos)
```bash
python main.py --demo
```
Ejecuta 5 casos de uso representativos: análisis de alertas, SKU específico, impacto climático, creación de orden de compra y consulta de política interna.

### Reconstruir índice vectorial
```bash
python main.py --rebuild
```
Útil cuando los datos del ERP se actualizan. Elimina y reconstruye ChromaDB desde cero.

### Probar módulos por separado
```bash
# Test del ERP mock
python erp/odoo_mock.py

# Test del loader de documentos
python rag/loader.py

# Test del pipeline RAG (requiere API key)
python rag/pipeline.py
```

## Flujo del sistema

```
Usuario (lenguaje natural)
        ↓
   RetailSurRAGPipeline.query()
        ↓
   ChromaDB Retriever (MMR, top-5)
   ┌─────────────────────────────┐
   │  Fuentes internas (ERP):    │
   │  · Historial ventas         │
   │  · Stock actual             │
   │  · Políticas de compra      │
   │                             │
   │  Fuentes externas:          │
   │  · Clima (Open-Meteo)       │
   │  · Feriados (OpenHolidays)  │
   │  · Tendencias (Trends)      │
   └─────────────────────────────┘
        ↓
   GPT-4o (temperatura=0.1)
        ↓
   Respuesta estructurada + trazabilidad de fuentes
        ↓
   (Opcional) OdooMockClient.create_purchase_order()
```

## Ejemplos de consultas

```
¿Qué SKUs están en estado crítico de inventario?
Analiza el SKU ELEC-001 considerando el Cyber Monday próximo
¿Cómo afecta el pronóstico climático a la demanda de calefacción?
¿Cuántas unidades de Notebook debo pedir esta semana?
¿Qué pedidos requieren aprobación del gerente?
```

## Uso de IA declarado

Este proyecto utilizó Claude (Anthropic) como apoyo en la estructura del código y documentación. Referencia de citación: https://bibliotecas.duoc.cl/ia

---

*Retail S.A. es una empresa ficticia creada con fines académicos.*
