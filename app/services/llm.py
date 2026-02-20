from langchain_ollama import ChatOllama
from app.config import settings


def get_llm() -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
        temperature=0.3,
    )