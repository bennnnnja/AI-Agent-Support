import logging
from app.state import AgentState
from app.services.llm import get_llm

logger = logging.getLogger(__name__)

_DUPLICATE_THRESHOLD = 0.7
 
_NEGATIVE_PATTERNS = [
    "не помогло", "не работает", "не получилось",
    "пробовал", "уже делал", "то же самое", "всё равно",
    "все равно", "ничего не изменилось", "та же проблема",
    "не помогает", "опять", "снова",
]

# Исторический промпт для режима "только по документации" оставляем,
# но в текущей версии он не используется: при наличии RAG-результатов
# ответ формируется напрямую из них без участия второй LLM.
GENERATE_PROMPT = """Ты — специалист технической поддержки. Отвечай СТРОГО на основе предоставленной документации.

ВАЖНЫЕ ПРАВИЛА:
- Используй ТОЛЬКО информацию из раздела "Документация" ниже
- Если в документации нет ответа на вопрос, так и скажи: "В документации нет информации по данному вопросу. Заявка будет передана специалисту."
- НЕ придумывай инструкции от себя
- НЕ проси уточняющие детали - используй имеющуюся информацию
- Давай пошаговые инструкции из документации
- Будь вежливым и кратким
- Отвечай на русском языке

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


FALLBACK_PROMPT = """Ты — специалист технической поддержки.

У ТЕБЯ НЕТ доступной технической документации, поэтому:
- не придумывай несуществующих настроек и кнопок;
- давай только общие и безопасные шаги диагностики;
- не предлагай действий, которые могут повредить оборудование или данные;
- если без профильного специалиста не обойтись, обязательно это подчеркни.

Используй информацию о задаче и историю переписки ниже.

ИНФОРМАЦИЯ О ЗАДАЧЕ:
Статус: {issue_status}
Приоритет: {issue_priority}
Назначено: {issue_assignee}

ИСТОРИЯ ПЕРЕПИСКИ:
{conversation_history}

ТЕКУЩИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{user_message}

Сформулируй краткий, понятный пользователю ответ с шагами, что он может сделать прямо сейчас.
Отвечай на русском языке."""

RETRY_FALLBACK_PROMPT = """Ты — специалист технической поддержки.
 
У ТЕБЯ НЕТ доступной технической документации, поэтому:
- не придумывай несуществующих настроек и кнопок;
- давай только общие и безопасные шаги диагностики;
- не предлагай действий, которые могут повредить оборудование или данные;
- если без профильного специалиста не обойтись, обязательно это подчеркни.
 
ИНФОРМАЦИЯ О ЗАДАЧЕ:
Статус: {issue_status}
Приоритет: {issue_priority}
Назначено: {issue_assignee}
 
ИСТОРИЯ ПЕРЕПИСКИ:
{conversation_history}
 
РАНЕЕ ПРЕДЛОЖЕННЫЕ ШАГИ:
{previous_steps}
 
ВАЖНО: Пользователь указал что предыдущие рекомендации НЕ помогли.
Предложи ДРУГИЕ шаги диагностики, которых нет в списке выше.
Не повторяй уже предложенные решения.
 
ТЕКУЩИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{user_message}
 
Сформулируй краткий, понятный пользователю ответ с НОВЫМИ шагами, что он может сделать прямо сейчас.
Отвечай на русском языке."""


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

def _extract_previous_steps(history: list[dict]) -> str:
    """Извлечь предыдущие ответы ассистента из истории."""
    steps = []
    for msg in history or []:
        if (msg.get("role") or "").strip().lower() == "assistant":
            body = (msg.get("body") or "").strip()
            if body:
                steps.append(body)
    if not steps:
        return "Нет ранее предложенных шагов"
    return "\n---\n".join(steps)
 
 
def _detect_negative_feedback(user_message: str) -> bool:
    """Определить, указывает ли пользователь что предыдущие шаги не помогли."""
    text = (user_message or "").lower()
    return any(pattern in text for pattern in _NEGATIVE_PATTERNS)
 
 
def _similarity(a: str, b: str) -> float:
    """Jaccard similarity на множествах слов."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)
 
 
def _get_last_assistant_response(history: list[dict]) -> str:
    """Получить последний ответ ассистента из истории."""
    for msg in reversed(history or []):
        if (msg.get("role") or "").strip().lower() == "assistant":
            return (msg.get("body") or "").strip()
    return ""
 
 
def _apply_similarity_guard(response: str, history: list[dict]) -> str:
    """Добавить дисклеймер если ответ слишком похож на предыдущий."""
    last_response = _get_last_assistant_response(history)
    if last_response and _similarity(response, last_response) > _DUPLICATE_THRESHOLD:
        logger.info("[GENERATE] Duplicate response detected (similarity > %.1f), adding disclaimer", _DUPLICATE_THRESHOLD)
        return (
            response
            + "\n\n---\nЕсли предыдущие рекомендации не помогли, "
            "рекомендуем обратиться к специалисту для детальной диагностики."
        )
    return response
 
 


def _format_rag_results(rag_results: list[str]) -> str:
    """Format RAG results for prompt."""
    if not rag_results:
        return "Документация не найдена"

    return "\n---\n".join(rag_results)


def generate_response(state: AgentState) -> AgentState:
    """Generate response using RAG as primary source and LLM as fallback."""

    conversation_history = state.get("conversation_history", [])

    # 1) Если есть результаты из RAG — используем их напрямую без вызова LLM
    rag_results = state.get("rag_results", [])
    logger.debug(f"[GENERATE] RAG results count: {len(rag_results)}")
    if rag_results:
        for i, result in enumerate(rag_results):
            logger.debug(f"[GENERATE] RAG result {i}: {result[:200]}")
        rag_text = _format_rag_results(rag_results)
        rag_text = _apply_similarity_guard(rag_text, conversation_history)
        logger.info("[GENERATE] Using RAG-only response with %d result(s)", len(rag_results))
        return {**state, "response": rag_text}

    # 2) RAG ничего не вернул — включаем fallback через LLM
    llm = get_llm()

    # Format history
    history_text = _format_conversation_history(conversation_history)

    # Get issue context
    issue_status = state.get("issue_status", "Unknown")
    issue_priority = state.get("issue_priority", "Unknown")
    issue_assignee = state.get("issue_assignee", "Unassigned")
    user_message = state.get("user_message", "")

    # Выбираем промпт: если пользователь говорит "не помогло" — используем RETRY
    if _detect_negative_feedback(user_message) and _extract_previous_steps(conversation_history) != "Нет ранее предложенных шагов":
        previous_steps = _extract_previous_steps(conversation_history)
        prompt = RETRY_FALLBACK_PROMPT.format(
            issue_status=issue_status,
            issue_priority=issue_priority,
            issue_assignee=issue_assignee,
            conversation_history=history_text,
            previous_steps=previous_steps,
            user_message=user_message,
        )
        logger.info("[GENERATE] Using RETRY prompt (negative feedback detected)")
    else:
        prompt = FALLBACK_PROMPT.format(
            issue_status=issue_status,
            issue_priority=issue_priority,
            issue_assignee=issue_assignee,
            conversation_history=history_text,
            user_message=user_message,
        )

    logger.debug(f"Generating response with prompt length: {len(prompt)}")

    try:
        response = llm.invoke(prompt)
        response_text = response.content.strip() if hasattr(response, "content") else str(response).strip()
        response_text = _apply_similarity_guard(response_text, conversation_history)
        logger.info(f"Generated response: {response_text[:100]}")
        return {**state, "response": response_text}
    except Exception as e:
        logger.error(f"Failed to generate response: {e}", exc_info=True)
        return {**state, "response": "Ошибка при генерации ответа"}