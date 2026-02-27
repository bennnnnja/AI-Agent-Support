from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream: str = "jira.events"
    redis_group: str = "agent-group"
    redis_consumer: str = "agent-1"

    # Ollama
    ollama_url: str = "http://10.60.18.220:11434/"
    ollama_model: str = "qwen3:8b"

    # RAG API
    rag_api_url: str = "http://10.10.10.5:9621"
    rag_username: str = ""
    rag_password: str = ""

    # Jira
    jira_url: str = "http://10.60.18.220:30280"
    jira_token: str = ""


    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
