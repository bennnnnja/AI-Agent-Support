from functools import lru_cache

from langchain_ollama import ChatOllama
from app.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
        temperature=0.3,
        timeout=120,
    )
