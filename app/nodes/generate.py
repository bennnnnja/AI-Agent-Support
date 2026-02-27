import logging
from app.state import AgentState
from app.services.llm import get_llm

logger = logging.getLogger(__name__)


GENERATE_PROMPT = """Ты — специалист технической поддержки. Отвечай СТРОГО на основе предоставленной документации.

ВАЖНЫЕ ПРАВИЛА:
- Используй ТОЛЬКО информацию из раздела "Документация" ниже
- Если в документации нет ответа на вопрос, так и скажи: "В документации нет информации по данному вопросу"
- НЕ придумывай инструкции от себя
- Давай пошаговые инструкции из документации
- Будь вежливым и кратким

ИНФОРМАЦИЯ О ЗАДАЧЕ:
Статус: {issue_status}
Приоритет: {issue_priority}
Назначено: {issue_assignee}

ДОКУМЕНТАЦИЯ:
{rag_results}

ИСТОРИЯ ПЕРЕПИСКИ:
{conversation_history}

ТЕКУЩИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{user_message}

ОТВЕТ (на основе документации):"""


def _format_conversation_history(history: list[dict]) -> str:
    """Format conversation history for prompt."""
    if not history:
        return "Нет предыдущей переписки"

    lines = []
    for msg in history:
        author = msg.get("author", "Unknown")
        body = msg.get("body", "")
        role = msg.get("role", "user")

        # Format with role indicator
        prefix = f"[{role.upper()}] {author}" if author else f"[{role.upper()}]"
        lines.append(f"{prefix}: {body}")

    return "\n".join(lines)


def _format_rag_results(rag_results: list[str]) -> str:
    """Format RAG results for prompt."""
    if not rag_results:
        return "Документация не найдена"

    return "\n---\n".join(rag_results)


def generate_response(state: AgentState) -> AgentState:
    """Generate response based on RAG results and conversation context."""
    llm = get_llm()

    # Format history
    history_text = _format_conversation_history(state.get("conversation_history", []))

    # Format RAG
    rag_text = _format_rag_results(state.get("rag_results", []))

    # Get issue context
    issue_status = state.get("issue_status", "Unknown")
    issue_priority = state.get("issue_priority", "Unknown")
    issue_assignee = state.get("issue_assignee", "Unassigned")
    user_message = state.get("user_message", "")

    # Build prompt
    prompt = GENERATE_PROMPT.format(
        issue_status=issue_status,
        issue_priority=issue_priority,
        issue_assignee=issue_assignee,
        conversation_history=history_text,
        rag_results=rag_text,
        user_message=user_message,
    )

    logger.debug(f"Generating response with prompt length: {len(prompt)}")

    try:
        response = llm.invoke(prompt)
        response_text = response.content.strip() if hasattr(response, "content") else str(response).strip()
        logger.info(f"Generated response: {response_text[:100]}")
        return {**state, "response": response_text}
    except Exception as e:
        logger.error(f"Failed to generate response: {e}", exc_info=True)
        return {**state, "response": "Ошибка при генерации ответа"}