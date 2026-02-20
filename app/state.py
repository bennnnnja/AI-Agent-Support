from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Входные данные
    ticket_id: str
    user_message: str
    is_first_message: bool

    # История из Jira
    conversation_history: list[dict]

    # Классификация
    category: str | None

    # RAG
    rag_results: list[str]

    # Генерация
    response: str | None

    # Цикл обратной связи
    attempt_count: int
    resolution: str | None