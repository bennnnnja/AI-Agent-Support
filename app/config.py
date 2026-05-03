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
    rag_timeout_budget: int = 10
    
    # Jira MCP
    jira_url: str = "http://localhost:8080"
    jira_token: str = ""

    # Agent
    bot_username: str = ""
    # Optional prefix marker used to detect bot's own comments by body content
    # (useful when webhook doesn't forward the author field).
    bot_comment_marker: str = ""

    # Escalation / roles
    escalation_statuses: str = "Escalated,Waiting for support"
    support_usernames: str = ""  # CSV list of support usernames (optional)
    max_self_help_attempts: int = 3
    escalation_message_template: str = (
        "Ваше обращение передано специалисту технической поддержки.\n\n"
        "Причина: {reason}\n"
        "Номер обращения: {ticket_id}\n\n"
        "Специалист свяжется с вами в ближайшее время."
    )

    resolution_message_template: str = (
        "Рад помочь! Если будут ещё вопросы — обращайтесь."
    )

    # Jira workflow — status transitions (leave empty to disable a given transition)
    status_in_progress: str = ""   # e.g. "В работе" / "In Progress"
    status_resolved: str = ""      # e.g. "Готово" / "Done"
    status_escalated: str = ""     # e.g. "Эскалировано" / "Escalated"
    # Username to reassign the ticket to when escalating (empty = keep current assignee)
    escalation_assignee: str = ""

    @property
    def escalation_status_set(self) -> set[str]:
        return {
            s.strip().lower()
            for s in self.escalation_statuses.split(",")
            if s.strip()
        }

    @property
    def support_username_set(self) -> set[str]:
        # Lowercased to allow case-insensitive matching at call sites.
        return {s.strip().lower() for s in self.support_usernames.split(",") if s.strip()}

    @property
    def rag_mode_list(self) -> list[str]:
        modes = [m.strip() for m in self.rag_modes.split(",") if m.strip()]
        return modes or ["hybrid"]


settings = Settings()
