from app.state import AgentState
from app.services.llm import get_llm


GENERATE_PROMPT = """Ты — специалист технической поддержки. Помоги пользователю решить проблему.

Правила:
- Давай конкретные пошаговые инструкции
- Используй простой язык без технического жаргона
- Если есть результаты из базы знаний, опирайся на них
- Будь вежливым и кратким

История переписки:
{conversation_history}

Результаты из базы знаний:
{rag_results}

Сообщение пользователя: {user_message}

Ответ:"""


def generate_response(state: AgentState) -> AgentState:
    llm = get_llm()

    history = state.get("conversation_history", [])
    history_text = "\n".join(
        f"{msg.get('author', '?')}: {msg.get('text', '')}"
        for msg in history
    ) or "Нет предыдущей переписки"

    rag = state.get("rag_results", [])
    rag_text = "\n".join(rag) or "Нет данных из базы знаний"

    prompt = GENERATE_PROMPT.format(
        conversation_history=history_text,
        rag_results=rag_text,
        user_message=state["user_message"],
    )

    response = llm.invoke(prompt)

    return {**state, "response": response.content.strip()}