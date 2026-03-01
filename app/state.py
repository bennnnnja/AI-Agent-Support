from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Входные данные
    ticket_id: str
    user_message: str
    is_first_message: bool

    # Информация о задаче из Jira
    issue_summary: str
    issue_description: str
    issue_status: str
    issue_assignee: str
    issue_priority: str

    # История из Jira
    conversation_history: list[dict]

    # Классификация
    category: str | None

    # RAG
    rag_results: list[str]

    # Генерация
    response: str | None

    # Результат
    resolution: str | None