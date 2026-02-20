from app.state import AgentState
from app.services.llm import get_llm


CLASSIFY_PROMPT = """Ты — классификатор запросов в техподдержку.

Определи категорию обращения пользователя. Ответь ОДНИМ словом:
- tech_support — техническая проблема с оборудованием (принтер, сканер и т.д.)
- off_topic — не относится к техподдержке
- unclear — непонятно, нужно уточнение

Сообщение пользователя: {user_message}

Категория:"""


def classify_request(state: AgentState) -> AgentState:
    llm = get_llm()
    prompt = CLASSIFY_PROMPT.format(user_message=state["user_message"])
    response = llm.invoke(prompt)

    category = response.content.strip().lower()

    if category not in ("tech_support", "off_topic", "unclear"):
        category = "unclear"

    return {**state, "category": category}