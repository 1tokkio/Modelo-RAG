# Informe Técnico EP2: Agente Funcional con Arquitectura RAG

## Caso Organizacional — Retail S.A., Región de Los Lagos

**Asignatura:** ISY0101 — Ingeniería de Soluciones con IA  
**Institución:** DuocUC  
**Año:** 2025

---

## 1. Diseño e Implementación del Agente Funcional (IE1, IE2)

### 1.1 Contexto organizacional

Retail S.A. es una empresa de comercio cuya operación depende fuertemente de una gestión eficiente del inventario, ya que trabaja con categorías de productos sensibles a factores externos como el clima, la estacionalidad y las tendencias de mercado. El equipo de adquisiciones actualmente toma decisiones de reabastecimiento de forma manual, cruzando datos de ventas, stock mínimo y condiciones del proveedor sin una herramienta centralizada.

El problema principal es que los tiempos de respuesta ante quiebres de stock son elevados, y las decisiones de compra no siempre consideran variables externas relevantes (como una ola de frío que aumenta la demanda de estufas, o un Cyber Monday que dispara la venta de electrónica). Esto genera tanto pérdidas por venta pérdida como costos de sobrestock en productos de baja rotación.

### 1.2 Propuesta de solución

Se propone un agente de inteligencia artificial basado en arquitectura **RAG (Retrieval-Augmented Generation)** que centraliza la información de inventario, historial de ventas, políticas de compra y contexto externo en una base de conocimiento consultable. En la EP2, el sistema evoluciona de un pipeline RAG estático a un **agente funcional ReAct** (Reasoning + Acting) capaz de razonar autónomamente sobre qué herramienta invocar según la consulta recibida, manteniendo coherencia entre sesiones mediante memoria de corto y largo plazo.

El agente no reemplaza al equipo humano, sino que le entrega información procesada y fundamentada para tomar decisiones más rápidas y mejor respaldadas.

| Función | Descripción | Destinatario |
|---|---|---|
| Consulta libre | Análisis general de inventario y tendencias | Jefe de adquisiciones |
| Alerta de SKU | Diagnóstico de estado crítico/normal por producto | Bodega y compras |
| Generación de pedido | Recomendación de orden de compra con proveedor y cantidad | Compras y finanzas |
| Registro en memoria | Persistencia de decisiones para continuidad entre sesiones | Sistema interno |

### 1.3 Herramientas configuradas en el agente (IE1)

El agente dispone de cuatro herramientas (`@tool`) implementadas en `agent.py` que ejecuta con autonomía según su razonamiento:

```python
@tool
def consultar_inventario(pregunta: str) -> str:
    """Consulta libre sobre el estado del inventario."""
    return _recuperar(pregunta)

@tool
def analizar_sku(sku: str) -> str:
    """Recupera información de un SKU e incluye historial de decisiones previas."""
    contexto = _recuperar(f"inventario stock ventas {sku}")
    historial = recuperar_historial_sku(sku)
    return f"{contexto}\n\n--- Memoria previa ---\n{historial}"

@tool
def recomendar_pedido(entrada: str) -> str:
    """Genera recomendación de orden de compra con política 30d × 1.2 − stock."""
    return _recuperar(f"pedido reorden proveedor lead time demanda {entrada}")

@tool
def registrar_alerta(entrada: str) -> str:
    """Registra una decisión en la memoria de largo plazo (JSON persistente)."""
    ...
```

El agente decide autónomamente el orden y combinación de herramientas a invocar sin instrucciones explícitas del usuario para cada paso.

### 1.4 Framework implementado (IE2)

Se utiliza **LangChain Agents** con el patrón ReAct, integrado mediante `create_react_agent` y `AgentExecutor`. La elección responde a:

- **Escalabilidad:** LangChain permite agregar nuevas tools sin modificar el núcleo del agente; basta con decorar una función con `@tool`.
- **Compatibilidad técnica:** integración nativa con ChromaDB (vectorstore), OpenAIEmbeddings (embeddings), ChatOpenAI (LLM) y los módulos de memoria de la misma librería.
- **Ecosistema activo:** framework con mayor adopción en producción para aplicaciones RAG, documentación extensa y soporte de la comunidad (Chase, 2022).

### 1.5 Objetivos del proyecto

- Reducir el tiempo de detección de quiebres de stock críticos mediante alertas automáticas.
- Estandarizar las recomendaciones de reabastecimiento aplicando las políticas internas (margen de seguridad del 20%, umbral de aprobación de $5.000.000 CLP).
- Incorporar variables externas (clima, eventos comerciales, tendencias de mercado) en el análisis de demanda.
- Proveer trazabilidad en las recomendaciones, indicando siempre la fuente de datos utilizada.
- Mantener coherencia entre sesiones mediante memoria de corto y largo plazo.

---

## 2. Configuración de Memoria y Recuperación de Contexto (IE3, IE4)

### 2.1 Memoria de corto plazo (IE3)

Se implementa mediante `ConversationBufferMemory` de LangChain, que almacena el historial completo de mensajes en RAM durante la sesión activa del servidor. Esta memoria se inyecta automáticamente en cada invocación del agente a través de la clave `chat_history`, permitiéndole referenciar intercambios anteriores sin que el usuario deba repetir el contexto.

```python
memoria_corto_plazo = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
)
```

El `AgentExecutor` recibe esta instancia en su parámetro `memory`, lo que garantiza que el historial sea visible en cada ciclo Thought–Action–Observation del agente.

### 2.2 Memoria de largo plazo (IE3)

Persiste en `data/memoria_largo_plazo.json`, estructurada por SKU con timestamps ISO 8601. Cuando el agente analiza un SKU, la herramienta `analizar_sku` consulta esta memoria para incorporar alertas previas en su razonamiento. Cuando detecta una condición crítica, `registrar_alerta` escribe la nueva decisión:

```json
{
  "ELEC-001": [
    {
      "timestamp": "2025-06-01T14:32:00",
      "estado": "CRÍTICO",
      "accion": "Pedir 50 unidades a TechDistrib"
    }
  ]
}
```

La función `recuperar_historial_sku(sku)` retorna las últimas 5 entradas para ese SKU, limitando el contexto inyectado al agente y evitando saturar la ventana de tokens.

### 2.3 Recuperación de contexto semántico (IE4)

El pipeline de indexación en `rag.py` sigue los siguientes pasos:

```
inventario.txt
      │
[RecursiveCharacterTextSplitter]
  chunk_size=500, overlap=50
      │
[Embeddings: text-embedding-3-small via GitHub Models]
      │
[ChromaDB — Vector Store persistente en ./chroma_db/]
      │
[Retriever: top-4 chunks por similitud semántica]
```

El tamaño de chunk de 500 caracteres se eligió para capturar secciones temáticas completas (ej. toda la información de un SKU) sin exceder el contexto útil del modelo. El overlap de 50 caracteres evita que información relevante quede cortada en el límite entre chunks.

Cuando llega una consulta, el retriever convierte la pregunta en un vector de embedding y busca los 4 chunks más cercanos en ChromaDB por similitud coseno. Estos chunks son inyectados como contexto en el prompt antes de enviarlo al LLM. La vectorización mediante `text-embedding-3-small` produce representaciones de alta dimensión que capturan similitud semántica: una consulta como "productos bajo mínimo" recuperará el chunk de ELEC-001 aunque este no contenga exactamente esa frase, porque el espacio vectorial coloca conceptos relacionados cerca. Esto supera las limitaciones del matching por palabras clave que usan sistemas legacy de gestión de inventario.

**Fuentes de datos internas** (`data/inventario.txt`):
- Catálogo de productos: 6 SKUs con nombre, categoría, proveedor, plazo de entrega y precio unitario.
- Niveles de stock actuales y puntos de reorden definidos por producto.
- Historial de ventas de los últimos 3 meses (oct.–dic.) con clasificación de tendencia.
- Políticas de compra: fórmula de cálculo de reorden, margen de seguridad, umbrales de aprobación y priorización por categoría.

**Fuentes de datos externas** (incorporadas en el mismo archivo de conocimiento):
- **Clima regional:** Pronóstico para Los Lagos con alerta de frente frío (impacto en calefacción y ropa de abrigo).
- **Calendario comercial:** Cyber Monday (+85% en electrónica), Navidad, Año Nuevo.
- **Tendencias de mercado:** Búsquedas en e-commerce ("Smart TV ofertas" +120%, "Estufas pellet" -30%).

### 2.4 Mecanismos de control de coherencia

**a) Temperatura baja (0.1):** El modelo GPT-4o-mini se configura con temperatura 0.1 en todos los endpoints. Esto reduce la variabilidad en las respuestas y prioriza la recuperación factual sobre la creatividad generativa. El uso de 0.1 en lugar de 0 (determinístico absoluto) responde a que algunos LLM exhiben comportamientos degenerados con temperatura exactamente cero, repitiendo tokens o colapsando la diversidad léxica. 0.1 mantiene la consistencia funcional preservando la fluidez del lenguaje generado.

**b) Instrucción explícita de no suponer:** Los prompts incluyen la instrucción "si los datos no son suficientes, indícalo claramente en lugar de suponer". Esto fue validado durante pruebas con preguntas sobre productos no incluidos en el catálogo: el modelo responde indicando que no dispone de esa información en lugar de inventar datos.

---

## 3. Planificación y Toma de Decisiones (IE5, IE6)

### 3.1 Esquema de planificación ReAct (IE5)

El agente implementa el patrón **ReAct** (Yao et al., 2023), que intercala ciclos de razonamiento y acción para secuenciar tareas según prioridades:

```
Consulta usuario
      │
      ▼
  [Thought]  El agente razona qué herramienta necesita
      │        y en qué orden ejecutarla
      ▼
  [Action]   Invoca la herramienta elegida con parámetros correctos
      │
      ▼
  [Observation]  Recibe el resultado de la herramienta
      │
      ▼
  ¿Se necesita más información? ──Sí──► vuelve a [Thought]
      │
      No
      ▼
  [Final Answer]  Devuelve respuesta al usuario
```

Este esquema permite al agente **secuenciar múltiples pasos** en una sola consulta. Para una orden de compra, por ejemplo: (1) analiza el SKU recuperando memoria previa, (2) consulta datos de demanda y proveedor, (3) calcula la cantidad según política interna, y (4) registra la decisión. El parámetro `max_iterations=6` limita los ciclos para evitar bucles infinitos en casos ambiguos.

### 3.2 Toma de decisiones adaptativa — ejemplos (IE6)

El script `demo.py` ejecuta tres escenarios que evidencian la adaptabilidad del agente ante condiciones cambiantes:

**Escenario A — Identificación de riesgo (estado NORMAL):**

*Consulta:* "¿Cuáles son los productos con stock más bajo en el inventario?"

El agente invoca `consultar_inventario` con la pregunta, recupera los chunks relevantes de ChromaDB y retorna un listado priorizado. **Decisión adaptativa:** no invoca `registrar_alerta` porque ningún producto supera el umbral crítico en esta consulta general. El ciclo termina en una sola iteración Thought→Action→Observation.

**Escenario B — Alerta con registro en memoria (estado CRÍTICO):**

*Consulta:* "Analiza el SKU ELEC-001: revisa su stock actual versus el mínimo requerido. Si está en estado CRÍTICO o ALERTA, registra la alerta en memoria."

El agente ejecuta dos tools en secuencia: primero `analizar_sku` para obtener contexto (stock=8, mínimo=15, tendencia creciente, Cyber Monday próximo), y luego `registrar_alerta` porque el razonamiento concluye estado CRÍTICO. **Comportamiento adaptativo:** si el stock fuera normal (ej. 25 unidades), el segundo tool call no ocurriría.

*Respuesta generada (evidencia del sistema):*
```
ESTADO: CRÍTICO
ANÁLISIS: El stock actual (8 unidades) está por debajo del mínimo requerido (15 unidades).
La tendencia de ventas es creciente (+18% mensual) y se proyecta un aumento adicional
por Cyber Monday. La demanda estimada para los próximos 30 días supera las 25 unidades.
ACCIÓN RECOMENDADA: Generar orden de compra inmediata a TechDistrib.
FUENTE: Tabla de inventario actual, historial de ventas oct–nov, calendario comercial.
```

**Escenario C — Decisión informada por memoria previa:**

*Consulta:* "Necesito generar una orden de compra para el SKU ELEC-001 con stock actual de 8 unidades. Considera cualquier alerta previa registrada."

El agente recupera en `analizar_sku` el historial del Escenario B desde `memoria_largo_plazo.json` e incorpora ese contexto en su recomendación de cantidad a pedir, ajustando la urgencia. **Sin la memoria de largo plazo**, esta segunda consulta sería procesada de forma idéntica a la primera; **con ella**, el agente sabe que ya existe una alerta activa y puede priorizar la velocidad de respuesta sobre otros criterios.

---

## 4. Arquitectura del Sistema (IE7, IE8)

### 4.1 Diagrama de orquestación

```
┌─────────────────────────────────────────────────────────────┐
│                    USUARIO FINAL                            │
│              (Equipo de Adquisiciones)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP Request (JSON)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 CAPA DE PRESENTACIÓN                        │
│           frontend.html (HTML5 + JavaScript)                │
└──────────────────────┬──────────────────────────────────────┘
                       │ fetch() POST
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 API REST — FastAPI                           │
│        /consulta    /alerta    /pedido    /historial        │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│          AGENTE REACT (LangChain) — agent.py                │
│                                                             │
│   [Thought] → [Action] → [Observation] → [Final Answer]     │
│                                                             │
│   Tools disponibles:                                        │
│   ├── consultar_inventario(pregunta)                        │
│   ├── analizar_sku(sku)                                     │
│   ├── recomendar_pedido(sku, stock_actual)                  │
│   └── registrar_alerta(sku, estado, accion)                 │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────────────┐    ┌─────────────────────────────┐
│  MÓDULO DE RECUPERACIÓN  │    │       MÓDULO DE MEMORIA     │
│       (rag.py)           │    │        (memoria.py)         │
│                          │    │                             │
│ Consulta → [Embedding]   │    │ Corto plazo:                │
│     ↓                    │    │ ConversationBufferMemory     │
│ [ChromaDB semántico]     │    │ (RAM, sesión activa)        │
│     ↓                    │    │                             │
│ [Top-4 chunks]           │    │ Largo plazo:                │
│                          │    │ memoria_largo_plazo.json    │
│ Base de conocimiento:    │    │ (disco, persistente)        │
│ inventario.txt → chroma_db   │                             │
└──────────────────────────┘    └─────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                 MÓDULO DE GENERACIÓN                        │
│    GPT-4o-mini (temperatura: 0.1) via GitHub Models API     │
│    ChatOpenAI → langchain_openai                            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Tabla de componentes

| Componente | Tecnología | Función |
|---|---|---|
| API Framework | FastAPI + Uvicorn | Exposición de endpoints REST |
| Agente | LangChain ReAct Agent | Orquestación autónoma de tools |
| Tools | LangChain `@tool` (×4) | Funciones ejecutables por el agente |
| Pipeline RAG | LangChain + ChromaDB | Recuperación semántica de contexto |
| Base de conocimiento | Archivo TXT estructurado | Fuente única de verdad |
| Vector Store | ChromaDB (local) | Índice semántico persistente |
| Modelo de embeddings | text-embedding-3-small | Vectorización de texto |
| Modelo generativo | GPT-4o-mini | Generación de respuestas |
| Memoria corto plazo | ConversationBufferMemory | Historial de sesión en RAM |
| Memoria largo plazo | JSON en disco | Decisiones persistentes por SKU |
| Frontend | HTML5 + JavaScript | Interfaz de usuario |

### 4.3 Prompts de sistema

**Prompt de consulta general:**
```
Eres un asistente especializado en gestión de inventario para Retail S.A.
Tu función es analizar la información disponible y responder preguntas del equipo de adquisiciones.
Usa únicamente la información proporcionada en el contexto. Si los datos no son suficientes,
indícalo claramente en lugar de suponer. Responde en español, de forma clara y estructurada.

Contexto: {context}
Pregunta: {question}
```

**Prompt de alerta de inventario:**
```
Eres un especialista en control de inventario. Analiza el estado del producto indicado
y determina si requiere reabastecimiento urgente.

Responde con el siguiente formato obligatorio:
ESTADO: [CRÍTICO / ALERTA / NORMAL]
ANÁLISIS: [Explica el nivel de stock vs mínimo requerido y tendencia de ventas]
ACCIÓN RECOMENDADA: [Qué debe hacer el equipo de compras]
FUENTE: [Datos utilizados del contexto]

Contexto: {context}
Producto a analizar: {sku}
```

**Prompt de generación de pedido:**
```
Eres un agente de compras de Retail S.A. Tu tarea es generar una recomendación de orden de compra.
Aplica la siguiente política de la empresa:
- Calcula la demanda proyectada a 30 días en base al historial.
- Agrega un margen de seguridad del 20%.
- Resta el stock actual para obtener la cantidad a pedir.
- Si el costo estimado supera $5.000.000 CLP, marca el pedido como "REQUIERE APROBACIÓN GERENCIAL".

Formato de respuesta:
CANTIDAD SUGERIDA: [unidades]
PROVEEDOR RECOMENDADO: [nombre y contacto]
FECHA LÍMITE DE PEDIDO: [considerando plazo de entrega del proveedor]
COSTO ESTIMADO: [en CLP]
REQUIERE APROBACIÓN: [Sí / No]
JUSTIFICACIÓN: [Resumen del análisis]
```

La estructura fija de respuesta es una decisión técnica relevante: al forzar campos con etiquetas conocidas (`ESTADO:`, `ANÁLISIS:`, etc.), el output puede ser parseado programáticamente por sistemas downstream (ERP, correo de aprobación) sin procesamiento adicional.

### 4.4 Justificación de componentes (IE8)

**RAG sobre fine-tuning:** El conocimiento relevante para Retail S.A. (niveles de stock, precios, proveedores) cambia con frecuencia; con RAG basta con actualizar el archivo de texto y eliminar `chroma_db/`, mientras que el fine-tuning requeriría reentrenar el modelo con cada cambio. Además, RAG ofrece trazabilidad inherente: la respuesta puede citar su fuente, lo que es fundamental para auditoría en procesos de compra.

**ChromaDB local vs. servicio en la nube:** Para un prototipo de esta escala (6 SKUs, ~2.200 caracteres de base de conocimiento), un servicio externo añadiría latencia de red y costos operativos sin beneficio real. El índice local carga en milisegundos y no requiere autenticación adicional. Decisión revisable si la base de conocimiento crece o se requiere acceso concurrente desde múltiples instancias.

**Políticas de negocio en el prompt:** Las políticas (margen del 20%, umbral de $5M CLP, fórmula de demanda proyectada) están en el system prompt y no en el código Python. Esto permite que el equipo de negocios las revise y ajuste sin intervención del equipo técnico: un cambio en el margen de seguridad solo requiere editar el texto del prompt, no redeployar el backend.

**Temperatura 0.1:** En sistemas de soporte a decisiones de negocio, la variabilidad en las respuestas es un problema: si el mismo SKU con el mismo stock genera recomendaciones distintas en consultas consecutivas, el usuario pierde confianza en la herramienta. La temperatura baja asegura consistencia, comportándose más como una regla de negocio que como una opinión.

**Tres endpoints especializados:** Los tres flujos tienen outputs con estructura radicalmente distinta: consulta libre retorna texto analítico, alerta retorna estado categórico, y pedido retorna datos operacionales (cantidad, proveedor, fecha). Separar los endpoints permite aplicar system prompts distintos y eventualmente conectar cada uno a sistemas diferentes (bodega, ERP, correo de aprobación).

**Memoria dual:** La combinación de `ConversationBufferMemory` (corto plazo) y JSON persistente (largo plazo) cubre dos necesidades distintas: mantener coherencia dentro de una sesión de trabajo (corto plazo) y preservar el historial de decisiones entre sesiones y reinicios del servidor (largo plazo). Un sistema de solo una capa perdería uno de los dos atributos.

---

## 5. Especificaciones Técnicas y Validación (IE9, IE10)

### 5.1 Especificaciones técnicas del sistema

| Parámetro | Valor |
|---|---|
| Framework API | FastAPI + Uvicorn |
| Framework agente | LangChain ReAct (`create_react_agent`) |
| Modelo generativo | GPT-4o-mini (GitHub Models) |
| Modelo de embeddings | text-embedding-3-small |
| Vector Store | ChromaDB (persistencia local) |
| Tamaño de chunk | 500 caracteres, overlap 50 |
| Chunks recuperados (k) | 4 |
| Temperatura LLM | 0.1 |
| Máximo iteraciones agente | 6 |
| Idioma de respuesta | Español |
| Umbral aprobación compra | $5.000.000 CLP |
| Margen de seguridad stock | 20% sobre demanda proyectada |
| Horizonte proyección demanda | 30 días |

### 5.2 Catálogo de productos gestionados

| SKU | Producto | Categoría | Stock Actual | Stock Mínimo | Estado |
|---|---|---|---|---|---|
| ELEC-001 | Smart TV 55" | Electrónica | 8 | 15 | CRÍTICO |
| ELEC-002 | Notebook Core i5 | Electrónica | 3 | 10 | CRÍTICO |
| HOGAR-001 | Estufa Pellet 15kW | Hogar | 22 | 8 | NORMAL |
| HOGAR-002 | Refrigerador 350L | Hogar | 12 | 10 | ALERTA |
| VEST-001 | Parka Impermeable | Vestuario | 35 | 20 | NORMAL |
| HERR-001 | Generador Bencina 2500W | Herramientas | 7 | 5 | NORMAL |

### 5.3 Red de proveedores

| Proveedor | Plazo entrega | Categoría | Descuento por volumen |
|---|---|---|---|
| TechDistrib | 10 días | Electrónica | 5% en pedidos ≥20 unidades |
| CalorSur | 15 días | Hogar/Calefacción | Sin descuento |
| FríoAndes | 14 días | Hogar/Refrigeración | Sin descuento |
| ModaChile | 21 días | Vestuario | Sin información |
| PowerTools | 12 días | Herramientas | Sin información |

### 5.4 Validación del sistema

Durante las pruebas del prototipo se verificaron los siguientes escenarios:

- **Consulta de stock crítico:** El sistema identifica correctamente ELEC-001 y ELEC-002 al preguntar "¿qué productos necesitan reabastecimiento urgente?".
- **Alerta con tendencia creciente:** Al consultar por ELEC-001, el agente incorpora la tendencia de ventas creciente y el contexto de Cyber Monday para justificar urgencia adicional, y registra la alerta en `memoria_largo_plazo.json`.
- **Pedido con aprobación requerida:** Al generar un pedido de Smart TV con stock 8, el cálculo (demanda 30 días + 20% buffer − stock actual) produce una cantidad cuyo costo supera $5M, activando correctamente el flag de aprobación gerencial.
- **Consulta fuera de catálogo:** Al preguntar por un producto no existente, el modelo responde que no dispone de esa información en el contexto, sin inventar datos.
- **Continuidad de memoria:** Una segunda consulta sobre ELEC-001 recupera la alerta previa del JSON y la incorpora en la respuesta, demostrando la continuidad de largo plazo.
- **Historial de sesión:** El endpoint `GET /historial` retorna correctamente el historial de conversación de la sesión activa y el contenido completo de la memoria de largo plazo.

### 5.5 Fundamento técnico y respaldo en evidencias

La arquitectura RAG implementada sigue el paradigma descrito en el paper original de Lewis et al. (2020), donde se demuestra que la combinación de un retriever denso con un generador de secuencias reduce sustancialmente las alucinaciones del modelo en dominios de conocimiento acotado. En este caso, el dominio acotado es el inventario y las políticas de compra de Retail S.A.

La incorporación del patrón ReAct (Yao et al., 2023) agrega la dimensión de planificación y toma de decisiones multietapa: en lugar de ejecutar un pipeline lineal fijo, el agente puede encadenar herramientas de forma dinámica según el estado observado en cada iteración. Esto es especialmente relevante para el flujo de pedido, que requiere recuperar contexto semántico, calcular según política y registrar la decisión en un solo intercambio con el usuario.

La persistencia del índice vectorial en ChromaDB implica que el costo computacional de generar embeddings para toda la base de conocimiento se paga una sola vez; las consultas subsiguientes acceden al índice en disco sin regenerar representaciones vectoriales, lo que reduce la latencia de respuesta a milisegundos en la fase de recuperación.

---

## 6. Referencias

Chase, H. (2022). *LangChain* [Software]. GitHub. https://github.com/langchain-ai/langchain

Chroma. (2024). *ChromaDB Documentation*. https://docs.trychroma.com

LangChain. (2024). *LangChain Python Documentation*. https://python.langchain.com

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *arXiv preprint arXiv:2005.11401*. https://arxiv.org/abs/2005.11401

Microsoft. (2024). *GitHub Models*. https://github.com/marketplace/models

OpenAI. (2024). *OpenAI API Reference*. https://platform.openai.com/docs/api-reference

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). ReAct: Synergizing Reasoning and Acting in Language Models. *arXiv preprint arXiv:2210.03629*. https://arxiv.org/abs/2210.03629

---

*Documento elaborado como parte del desarrollo del proyecto de agente IA con arquitectura RAG para la asignatura ISY0101 — DuocUC 2025.*

---

## 7. EP3 — Observabilidad, Seguridad y Calidad de Servicio

### 7.1 Métricas de rendimiento implementadas (IE1)

En la tercera entrega se implementó un módulo de observabilidad completo (`observability.py`) que instrumenta todas las llamadas a la API sin modificar la lógica de negocio. Las métricas recopiladas son:

| Métrica | Descripción | Archivo |
|---|---|---|
| Latencia total (ms) | Tiempo end-to-end de cada request | `data/metricas.json` |
| Latencia RAG (ms) | Tiempo exclusivo de recuperación semántica en ChromaDB | `data/metricas.json` |
| Latencia LLM (ms) | Tiempo exclusivo de inferencia en GPT-4o-mini | `data/metricas.json` |
| Tokens estimados | Estimación por fórmula `(len(pregunta) + len(respuesta)) / 4` | `data/metricas.json` |
| RAM (MB) | Consumo del proceso en cada llamada (psutil) | `data/metricas.json` |
| CPU (%) | Uso de CPU del proceso en cada llamada (psutil) | `data/metricas.json` |
| Tasa de éxito (%) | Porcentaje de respuestas sin error | `data/metricas.json` |

El desglose RAG/LLM es especialmente relevante para identificar el cuello de botella real: si la latencia alta está en ChromaDB (RAG) conviene reducir `k` o actualizar el índice; si está en el LLM conviene evaluar caché de respuestas frecuentes. Sin esta separación, ambos problemas son indistinguibles desde el tiempo total.

**Percentiles calculados:** P50, P95 y P99 sobre el historial de latencias. El P95 representa el peor caso que experimenta el 95% de los usuarios, y es el indicador más usado en SLOs de producción (Service Level Objectives). Un sistema con P50=800ms y P99=4200ms tiene latencia aceptable en promedio pero degradación severa en cargas o consultas complejas.

```python
def _percentil(valores: list, p: int) -> float:
    ordenado = sorted(valores)
    idx = int(len(ordenado) * p / 100)
    return round(ordenado[min(idx, len(ordenado) - 1)], 2)
```

### 7.2 Sistema de logging estructurado (IE2)

Se implementó logging de doble capa:

**Capa 1 — Eventos JSONL** (`data/agent_events.jsonl`): Cada llamada genera una línea JSON con los campos `timestamp`, `endpoint`, `latencia_ms`, `latencia_rag_ms`, `latencia_llm_ms`, `tokens_estimados`, `exito`, `error`, `anomalia` y `nivel`. El formato JSONL (una línea por evento) permite procesar el archivo con herramientas de streaming (`grep`, `jq`, pandas) sin cargarlo completo en memoria, algo importante cuando el archivo crece con el uso continuo.

**Capa 2 — Log de auditoría** (`data/audit.log`): Registra eventos de seguridad con formato `[timestamp] IP=x ACCION=y detalle`. Actualmente se registran los bloqueos por rate limit, con extensibilidad a otros eventos de seguridad.

**Niveles de log asignados automáticamente:**
- `INFO` → request exitoso dentro de parámetros normales
- `WARNING` → request exitoso pero con latencia anómala (>2× promedio)
- `ERROR` → request fallido (excepción en LLM o RAG)

### 7.3 Detección de anomalías (IE3)

El sistema detecta automáticamente consultas anómalas comparando la latencia de cada request contra el promedio histórico:

```python
lat_media = sum(datos["latencias_ms"]) / len(datos["latencias_ms"])
es_anomalia = latencia_total_ms > lat_media * 2 and len(datos["latencias_ms"]) > 5
```

El umbral de 2× el promedio (con mínimo de 5 muestras para estabilizar la media) identifica requests que demoran el doble de lo habitual, señal de sobrecarga de la API externa, consultas con prompts inusualmente largos o degradación transitoria del servicio. En el dashboard, estos eventos se visualizan como puntos rojos en el gráfico de latencia.

El endpoint `GET /analisis` consolida los patrones detectados y genera recomendaciones automáticas:

```json
{
  "total_anomalias": 3,
  "umbral_anomalia_ms": 4200.0,
  "endpoint_mas_lento": "pedido",
  "hora_pico": "14:00",
  "patrones_detectados": [
    "3 consultas con latencia > 2× el promedio detectadas.",
    "Endpoint más lento: /pedido (3100 ms promedio)."
  ],
  "recomendaciones": [
    "El LLM representa >75% de la latencia. Evaluar caché de respuestas frecuentes."
  ]
}
```

### 7.4 Análisis de logs — hallazgos observados

Durante las pruebas de validación se observaron los siguientes patrones:

| Observación | Causa identificada | Acción tomada |
|---|---|---|
| Latencia `/pedido` ~40% mayor que `/consulta` | El prompt de pedido es más largo y detallado | Documentado; optimización pendiente |
| P95 ≈ 3× P50 | GitHub Models presenta cola en hora pico | Recomendación de caché generada automáticamente |
| RAG representa ~10-15% de la latencia total | ChromaDB local con índice pequeño es muy eficiente | Sin acción requerida |
| LLM representa ~85% de la latencia total | Latencia de red a Azure Inference endpoint | Informa decisión de evaluar caché en EP4 |

### 7.5 Protocolos de seguridad implementados (IE4)

El módulo `security.py` implementa cuatro capas de protección:

**a) Validación de entrada (`validar_input`):**
- Rechazo de entradas vacías o superiores a 1.000 caracteres.
- Detección de patrones peligrosos mediante regex: SQL injection (`DROP TABLE`, `DELETE FROM`), XSS (`<script>`), ejecución de código (`eval(`, `exec(`), y caracteres de shell (`;`, `|`, `&`, `` ` ``).
- Respuesta: HTTP 400 con mensaje descriptivo; no se loguea la entrada maliciosa en el JSONL de eventos para evitar almacenar payloads de ataque.

**b) Validación de SKU (`validar_sku`):**
- Formato estricto: `^[A-Z]{2,10}-\d{3,6}$` (ej. `ELEC-001`, `HOGAR-002`).
- Normalización automática a mayúsculas antes de validar.
- Previene path traversal y parámetros malformados en los endpoints de alerta y pedido.

**c) Rate limiting (`verificar_rate_limit`):**
- Ventana deslizante de 60 segundos por IP.
- Máximo 20 solicitudes por ventana.
- Al superar el límite: HTTP 429 + registro en `data/audit.log` con IP, acción y conteo.
- Integración con observabilidad: `registrar_audit(ip, "RATE_LIMIT_BLOQUEADO", ...)`.

**d) Sanitización de respuestas (`sanitizar_respuesta`):**
- Eliminación de datos sensibles del output del LLM mediante patrones regex:
  - Números de tarjeta (16 dígitos con separadores opcionales)
  - Correos electrónicos
  - RUT chileno (`12345678-9`)
- Reemplazados por `[DATO PROTEGIDO]`.
- Esta capa protege ante "jailbreaks" indirectos donde el LLM podría repetir datos sensibles del contexto de entrenamiento.

### 7.6 Medición de consistencia entre respuestas (IE5)

El endpoint `POST /test-consistencia` implementa una prueba de consistencia automática: envía la misma consulta al LLM tres veces con temperatura 0.1 y mide la similitud entre los pares de respuestas usando el índice de Jaccard sobre el vocabulario:

```
Jaccard(A, B) = |palabras(A) ∩ palabras(B)| / |palabras(A) ∪ palabras(B)|
```

**Escala de evaluación:**
- `ALTA`: similitud promedio ≥ 70%
- `MEDIA`: similitud promedio ≥ 40%
- `BAJA`: similitud promedio < 40%

La elección de Jaccard sobre métricas más sofisticadas (BLEU, cosine similarity de embeddings) responde a la eficiencia computacional: el test puede ejecutarse sin llamadas adicionales al modelo de embeddings. La limitación es que Jaccard es sensible al orden de palabras y no captura paráfrasis semánticas; sin embargo, es suficiente para detectar inestabilidad severa (respuestas radicalmente distintas) que es la señal más importante en un sistema de soporte a decisiones.

Con temperatura 0.1, las pruebas realizadas muestran consistencia ALTA en consultas de stock (el contexto factual del inventario domina sobre la variabilidad del modelo) y consistencia MEDIA en consultas abiertas de análisis de tendencias (más espacio para variación estilística).

### 7.7 Dashboard de observabilidad

El frontend ERP-style (`frontend.html`) incorpora una sección de observabilidad en tiempo real con auto-refresh cada 30 segundos. Componentes del dashboard:

| Widget | Datos | Fuente |
|---|---|---|
| KPIs (4 tarjetas) | Total consultas, tasa éxito, latencia promedio, tokens | `GET /metricas` |
| Percentiles (P50/P95/P99) | Distribución de latencia histórica | `GET /metricas` |
| Gráfico latencia total | Línea temporal con puntos rojos en anomalías | `GET /metricas` + `GET /eventos` |
| Gráfico RAG vs LLM | Barras apiladas comparando las dos fases | `GET /metricas` |
| Gráfico por endpoint | Barras con conteo de consultas por ruta | `GET /metricas` |
| Gráfico éxito/error | Donut con proporción de respuestas exitosas | `GET /metricas` |
| Página Análisis | Patrones detectados y recomendaciones | `GET /analisis` |
| Tabla de Logs | Últimos 50 eventos con nivel, RAG, LLM, anomalía | `GET /eventos` |
| Test de Consistencia | Formulario interactivo con resultado Jaccard | `POST /test-consistencia` |

La visualización de puntos rojos en anomalías permite al operador identificar visualmente qué consultas específicas presentaron degradación, sin necesidad de leer el archivo JSONL.

### 7.8 Mejoras propuestas con respaldo cuantitativo

Las recomendaciones automáticas generadas por `GET /analisis` se basan en umbrales definidos a partir de los datos observados:

| Condición detectada | Umbral | Recomendación generada |
|---|---|---|
| LLM > 3× RAG en latencia | avg_llm > avg_rag × 3 | Evaluar caché de respuestas frecuentes |
| RAG elevado | avg_rag > 500ms | Reducir k=4 a k=2 o usar índice HNSW |
| Tasa de error alta | errores / total > 10% | Revisar validación SKUs y conectividad |
| Múltiples anomalías | anomalías > 3 | Implementar circuit breaker y timeout |

Estas recomendaciones son propuestas concretas de ingeniería con justificación técnica, no alertas genéricas. El circuit breaker, por ejemplo, evitaría que un LLM degradado bloquee el servidor completo al limitar la espera máxima y retornar respuestas de fallback.

---

## 8. Referencias Adicionales (EP3)

Juneja, P., & Mitra, T. (2022). Auditing E-Commerce Platforms for Algorithmically Curated Vaccine Misinformation. *CHI Conference on Human Factors in Computing Systems*. (Metodología de auditoría de sistemas automatizados.)

Microsoft Azure. (2024). *Azure AI Inference API — GitHub Models*. https://github.com/marketplace/models

psutil contributors. (2024). *psutil Documentation*. https://psutil.readthedocs.io

Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly Media. (Cap. 1: Reliability, Scalability, Maintainability — fundamento de los percentiles P95/P99 como SLO.)

---

*EP3 agregado al informe técnico base EP2 — ISY0101 · DuocUC · 2025.*
