import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

CHROMA_DIR = "./chroma_db"
DATA_FILE  = "./data/inventario.txt"


def get_retriever():
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("GITHUB_TOKEN"),
        openai_api_base=os.getenv("OPENAI_EMBEDDINGS_URL"),
    )

    if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        print("[RAG] Cargando índice vectorial existente...")
        vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    else:
        print("[RAG] Construyendo índice vectorial desde cero...")
        documentos  = TextLoader(DATA_FILE, encoding="utf-8").load()
        fragmentos  = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(documentos)
        vectorstore = Chroma.from_documents(documents=fragmentos, embedding=embeddings, persist_directory=CHROMA_DIR)
        print(f"[RAG] {len(fragmentos)} fragmentos indexados.")

    return vectorstore.as_retriever(search_kwargs={"k": 4})
