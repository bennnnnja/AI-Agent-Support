from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream: str = "jira.events"
    redis_group: str = "agent-group"
    redis_consumer: str = "agent-1"

    # Ollama
    ollama_url: str = "http://localhost:11434/"
    ollama_model: str = "qwen3:8b"

    # RAG API (Knowledge Base) — login via POST /login (grant_type=password), then Bearer token for /query
    rag_api_url: str = "http://localhost:9621"
    rag_username: str = ""
    rag_api_key: str = ""

    # RAG behavior
    rag_modes: str = "hybrid,mix,local"
    rag_top_k: int = 10
    rag_response_type: str = "Multiple Paragraphs"
    rag_max_query_chars: int = 1500
    
    # Jira MCP
    jira_url: str = "http://localhost:8080"
    jira_token: str = ""

    # Agent
    bot_username: str = ""

    # Escalation / roles
    escalation_statuses: str = "In Progress,In Review,Escalated,Waiting for support"
    support_usernames: str = ""  # CSV list of support usernames (optional)
    max_self_help_attempts: int = 3

    @property
    def escalation_status_set(self) -> set[str]:
        return {
            s.strip().lower()
            for s in self.escalation_statuses.split(",")
            if s.strip()
        }

    @property
    def support_username_set(self) -> set[str]:
        return {s.strip() for s in self.support_usernames.split(",") if s.strip()}

    @property
    def rag_mode_list(self) -> list[str]:
        modes = [m.strip() for m in self.rag_modes.split(",") if m.strip()]
        return modes or ["hybrid"]


settings = Settings()
