from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream: str = "jira.events"
    redis_group: str = "agent-group"
    redis_consumer: str = "agent-1"

    # Ollama
    ollama_url: str = "http://localhost:11434/"
    ollama_model: str = "qwen3:8b"

    # RAG API
    rag_api_url: str = "http://localhost:9621"
    rag_username: str = ""
    rag_api_key: str = ""

    # Jira
    jira_url: str = "http://localhost:8080"
    jira_token: str = ""

    # Bot identity (for filtering bot's own comments)
    bot_username: str = ""


    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
