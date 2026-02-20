from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream: str = "support-stream"
    redis_group: str = "agent-group"
    redis_consumer: str = "agent-1"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # RAG API
    rag_api_url: str = "http://localhost:8001"

    model_config = {"env_file": ".env"}


settings = Settings()
