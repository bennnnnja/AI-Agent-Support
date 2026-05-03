import logging
from app.state import AgentState
from app.services.llm import get_llm

logger = logging.getLogger(__name__)

# Ключевые слова для быстрой rule-based классификации без вызова LLM
_TECH_KEYWORDS = {
    "принтер", "сканер", "картридж", "мфу", "копир",
    "не печатает", "не сканирует", "замятие", "бумага застряла",
    "тонер", "драйвер", "печать", "ксерокс", "факс",
    "монитор", "клавиатура", "мышь", "мышка", "компьютер",
    "ноутбук", "не включается", "зависает", "перезагружается",
    "синий экран", "ошибка", "не работает", "сломался", "сломалась",
    "wifi", "интернет", "сеть", "роутер", "vpn",
    "пароль", "не могу войти", "заблокирован",
}


CLASSIFY_PROMPT = """Ты — классификатор запросов в техподдержку.

Определи категорию обращения пользователя. Ответь ОДНИМ словом:
- tech_support — техническая проблема с оборудованием (принтер, сканер и т.д.)
- off_topic — не относится к техподдержке
- unclear — непонятно, нужно уточнение

Сообщение пользователя: {user_message}

Категория:"""

def _rule_based_classify(message: str) -> str | None:
    """Быстрая классификация по ключевым словам. Возвращает категорию или None."""
    text = message.lower()
    for keyword in _TECH_KEYWORDS:
        if keyword in text:
            return "tech_support"
    return None


def _is_conversation_followup(state: AgentState) -> bool:
    """Return True if the conversation already has bot responses (ongoing tech dialog)."""
    history = state.get("conversation_history") or []
    return any(
        (msg.get("role") or "").strip().lower() == "assistant"
        for msg in history
    )


def classify_request(state: AgentState) -> AgentState:
    """Classify the request into categories."""
    user_message = state.get("user_message", "")
    if not user_message:
        logger.warning("No user_message for classification")
        return {**state, "category": "unclear"}

    # Sprint 3: только лог. Эскалация по приоритету решается в ingest_event
    # через payload-флаги force_escalation/super_priority/needs_human (см. app/main.py).
    priority_raw = (state.get("issue_priority") or "").strip().lower()
    if priority_raw in {"critical", "blocker", "highest"}:
        logger.info(
            "[classify] High priority detected: %s (ticket=%s)",
            priority_raw, state.get("ticket_id"),
        )

    # Rule-based shortcut для очевидных тех-кейсов
    rule_category = _rule_based_classify(user_message)
    if rule_category:
        logger.info(f"[classify] Rule-based shortcut: {rule_category} (keyword match)")
        return {**state, "category": rule_category}

    # Follow-up in an existing conversation — treat as tech_support continuation
    if _is_conversation_followup(state):
        logger.info("[classify] Follow-up in existing conversation → tech_support")
        return {**state, "category": "tech_support"}

    llm = get_llm()

    try:
        prompt = CLASSIFY_PROMPT.format(user_message=user_message[:500])
        logger.debug(f"Classifying message (len={len(user_message)})")

        response = llm.invoke(prompt)
        category = response.content.strip().lower()

        # Validate classification result
        if category not in ("tech_support", "off_topic", "unclear"):
            logger.warning(f"Invalid category '{category}', defaulting to 'unclear'")
            category = "unclear"

        logger.info(f"Classified as: {category}")
        return {**state, "category": category}

    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        return {**state, "category": "unclear"}