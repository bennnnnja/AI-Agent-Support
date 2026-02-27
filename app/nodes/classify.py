import logging
from app.state import AgentState
from app.services.llm import get_llm

logger = logging.getLogger(__name__)


CLASSIFY_PROMPT = """Ты — классификатор запросов в техподдержку.

Определи категорию обращения пользователя. Ответь ОДНИМ словом:
- tech_support — техническая проблема с оборудованием (принтер, сканер и т.д.)
- off_topic — не относится к техподдержке
- unclear — непонятно, нужно уточнение

Сообщение пользователя: {user_message}

Категория:"""


def classify_request(state: AgentState) -> AgentState:
    """Classify the request into categories."""
    user_message = state.get("user_message", "")
    if not user_message:
        logger.warning("No user_message for classification")
        return {**state, "category": "unclear"}

    llm = get_llm()

    try:
        prompt = CLASSIFY_PROMPT.format(user_message=user_message[:500])  # Limit to 500 chars
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