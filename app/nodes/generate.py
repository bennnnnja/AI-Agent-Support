from app.state import AgentState
from app.services.llm import get_llm


GENERATE_PROMPT = """Ты — специалист технической поддержки. Отвечай СТРОГО на основе предоставленной документации.

ВАЖНЫЕ ПРАВИЛА:
- Используй ТОЛЬКО информацию из раздела "Документация" ниже
- Если в документации нет ответа на вопрос, так и скажи: "В документации нет информации по данному вопросу"
- НЕ придумывай инструкции от себя
- Давай пошаговые инструкции из документации
- Будь вежливым и кратким

Документация:
{rag_results}

История переписки:
{conversation_history}

Сообщение пользователя: {user_message}

Ответ на основе документации:"""


def generate_response(state: AgentState) -> AgentState:
    llm = get_llm()

    history = state.get("conversation_history", [])
    history_text = "\n".join(
        f"{msg.get('author', '?')}: {msg.get('text', '')}"
        for msg in history
    ) or "Нет предыдущей переписки"

    rag = state.get("rag_results", [])
    rag_text = "\n".join(rag) or "Документация не найдена"

    prompt = GENERATE_PROMPT.format(
        conversation_history=history_text,
        rag_results=rag_text,
        user_message=state["user_message"],
    )

    response = llm.invoke(prompt)

    return {**state, "response": response.content.strip()}