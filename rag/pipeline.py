"""
rag/pipeline.py
---------------
Pipeline RAG completo para RetailSur S.A.
Flujo:
  1. Carga documentos (internos + externos) → loader.py
  2. Genera embeddings con OpenAI text-embedding-3-small
  3. Indexa en ChromaDB (persistente en ./chroma_db)
  4. Retriever: búsqueda semántica top-k=5
  5. Chain: contexto recuperado → LLM GPT-4o → respuesta estructurada
"""

import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document

from rag.loader import load_all_documents
from rag.prompts import SYSTEM_PROMPT, NATURAL_QUERY_PROMPT


CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "retailsur_inventory"


class RetailSurRAGPipeline:
    """
    Pipeline RAG para el agente de gestión de inventario de RetailSur S.A.

    Uso:
        pipeline = RetailSurRAGPipeline()
        pipeline.build()          # Indexa los documentos en ChromaDB
        response = pipeline.query("¿Cuál es el estado del SKU ELEC-001?")
    """

    def __init__(self, openai_api_key: str = None):
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Se requiere OPENAI_API_KEY. Configúrala en .env o como variable de entorno."
            )

        # Modelo de embeddings: text-embedding-3-small (más eficiente y económico)
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=self.api_key
        )

        # LLM principal: GPT-4o con temperatura baja para consistencia en recomendaciones
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1,          # Baja temperatura: respuestas más deterministas
            openai_api_key=self.api_key,
            max_tokens=1500
        )

        self.vectorstore = None
        self.retriever = None
        self.chain = None

    def build(self, force_rebuild: bool = False) -> None:
        """
        Construye o carga el índice vectorial en ChromaDB.

        Args:
            force_rebuild: Si True, elimina el índice existente y reconstruye desde cero.
                           Útil cuando los datos del ERP se actualizan.
        """
        if os.path.exists(CHROMA_PERSIST_DIR) and not force_rebuild:
            print("[RAG] Cargando índice ChromaDB existente...")
            self.vectorstore = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=CHROMA_PERSIST_DIR
            )
            count = self.vectorstore._collection.count()
            print(f"[RAG] Índice cargado: {count} vectores")
        else:
            print("[RAG] Construyendo índice ChromaDB desde cero...")
            documents = load_all_documents()

            self.vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                collection_name=COLLECTION_NAME,
                persist_directory=CHROMA_PERSIST_DIR
            )
            print(f"[RAG] Índice construido: {len(documents)} documentos indexados")

        # Retriever: búsqueda semántica, top-5 documentos más relevantes
        # MMR (Maximal Marginal Relevance) reduce redundancia en resultados
        self.retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 5,           # Retornar top 5 documentos
                "fetch_k": 20,    # Candidatos a evaluar antes de MMR
                "lambda_mult": 0.7 # Balance relevancia vs. diversidad
            }
        )

        # Prompt template para la chain
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template=(
                f"{SYSTEM_PROMPT}\n\n"
                "**Contexto recuperado del sistema:**\n{context}\n\n"
                "**Consulta:** {question}\n\n"
                "**Respuesta:**"
            )
        )

        # Chain RetrievalQA: retriever → prompt → LLM
        self.chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",          # Concatena todos los docs recuperados
            retriever=self.retriever,
            return_source_documents=True, # Incluye fuentes para trazabilidad
            chain_type_kwargs={"prompt": prompt_template}
        )
        print("[RAG] Pipeline listo.")

    def query(self, question: str, verbose: bool = True) -> dict:
        """
        Ejecuta una consulta en lenguaje natural contra el pipeline RAG.

        Args:
            question: Pregunta del usuario en lenguaje natural
            verbose: Si True, imprime las fuentes recuperadas

        Returns:
            dict con 'answer' (str) y 'sources' (list de metadatos)
        """
        if not self.chain:
            raise RuntimeError("El pipeline no está inicializado. Llama a build() primero.")

        result = self.chain.invoke({"query": question})

        sources = []
        for doc in result.get("source_documents", []):
            sources.append({
                "fuente": doc.metadata.get("source", "desconocida"),
                "tipo": doc.metadata.get("tipo", "N/A"),
                "sku": doc.metadata.get("sku", "N/A"),
                "fragmento": doc.page_content[:120] + "..."
            })

        if verbose:
            print(f"\n{'='*60}")
            print(f"CONSULTA: {question}")
            print(f"{'='*60}")
            print(f"\nRESPUESTA:\n{result['result']}")
            print(f"\n--- FUENTES RECUPERADAS ({len(sources)}) ---")
            for i, src in enumerate(sources, 1):
                print(f"  [{i}] {src['fuente']} | {src['tipo']} | SKU: {src['sku']}")
            print(f"{'='*60}\n")

        return {
            "answer": result["result"],
            "sources": sources,
            "question": question
        }

    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        """
        Búsqueda de similitud directa (sin LLM). Útil para debug del retriever.
        """
        if not self.vectorstore:
            raise RuntimeError("Vectorstore no inicializado. Llama a build() primero.")
        return self.vectorstore.similarity_search(query, k=k)

    def add_documents(self, documents: list[Document]) -> None:
        """
        Agrega documentos nuevos al índice sin reconstruirlo.
        Útil para actualizaciones incrementales del ERP.
        """
        if not self.vectorstore:
            raise RuntimeError("Vectorstore no inicializado. Llama a build() primero.")
        self.vectorstore.add_documents(documents)
        print(f"[RAG] {len(documents)} documentos agregados al índice.")


# --- Test rápido ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    pipeline = RetailSurRAGPipeline()
    pipeline.build()

    # Consultas de prueba
    test_queries = [
        "¿Qué SKUs están en estado crítico de inventario?",
        "¿Debo pedir más Smart TV considerando el Cyber Monday?",
        "¿Cuál es la situación del SKU ELEC-001?",
    ]

    for q in test_queries:
        pipeline.query(q)
