import logging
import os
from pathlib import Path
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from nexo.config import MODEL_EMBEDDINGS

logger = logging.getLogger(__name__)
DB_PATH = os.getenv("NEXO_MEMORY_PATH", str(Path(__file__).resolve().parents[2] / "nexo_data_db"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")


def obtener_embeddings():
    # Usamos un modelo local de Ollama para convertir texto en vectores
    return OllamaEmbeddings(
        model=MODEL_EMBEDDINGS,
        base_url=OLLAMA_HOST,
        client_kwargs={"timeout": 30},
    )


def guardar_en_memoria(texto: str) -> bool:
    """Guarda un resumen del trabajo en la base de datos."""
    try:
        embeddings = obtener_embeddings()
        vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
        vectorstore.add_texts([texto])
        logger.info("Memory document stored")
        return True
    except Exception as e:
        logger.warning("Memory persistence failed: %s", e)
        return False


def buscar_en_memoria(consulta: str, cantidad: int = 2) -> str:
    """Busca en la base de datos experiencias pasadas similares."""
    try:
        embeddings = obtener_embeddings()
        vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)
        if vectorstore._collection.count() == 0:
            return ""
        resultados = vectorstore.similarity_search(consulta, k=cantidad)

        if not resultados:
            return "No hay experiencias previas en la memoria."

        texto_recuperado = "\n".join([doc.page_content for doc in resultados])
        return texto_recuperado
    except Exception as e:
        logger.warning("Memory search failed: %s", e)
        return ""
