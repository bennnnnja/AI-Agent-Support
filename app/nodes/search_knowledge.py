import logging
from app.state import AgentState
from app.services.rag import search_knowledge

logger = logging.getLogger(__name__)

# Fallback generic troubleshooting advice for printers
GENERIC_PRINTER_HELP = """
**Общие рекомендации для устранения проблем с принтером:**

1. **Перезагрузка устройства**
   - Выключите принтер на 30 секунд
   - Перезагрузите компьютер
   - Включите принтер заново

2. **Проверка подключения**
   - Убедитесь что кабель питания подключен
   - Проверьте соединение USB/сетевого кабеля
   - Попробуйте другой кабель если возможно

3. **Проверка драйверов**
   - Переустановите драйверы принтера
   - Удалите принтер из системы и добавьте заново
   - Посетите сайт производителя для скачивания актуальных драйверов

4. **Очистка и обслуживание**
   - Очистите принтер от пыли
   - Проверьте наличие посторонних предметов
   - Замените картридж если необходимо

Если проблема не решена - пожалуйста, обратитесь к специалисту технической поддержки с описанием проблемы и моделью устройства.
"""


def search_knowledge_node(state: AgentState) -> AgentState:
    """Search knowledge base for relevant documentation."""
    user_message = state.get("user_message", "")
    issue_description = state.get("issue_description", "")

    # Build search query from user message and/or issue description
    query_parts = []
    if user_message:
        query_parts.append(user_message)
    if issue_description:
        query_parts.append(issue_description)

    full_query = " ".join(query_parts)

    if not full_query:
        logger.warning("No query content for knowledge search")
        return {**state, "rag_results": []}

    try:
        logger.info(f"Searching knowledge base (full query len={len(full_query)})")

        # First try with full query
        results = search_knowledge(full_query)

        # If no results, try with shortened query (just first sentence)
        if not results or (len(results) > 0 and "No relevant context" in results[0]):
            logger.warning(f"Full query returned no relevant context, trying shortened version")
            # Extract just first sentence or first ~50 chars
            short_query = full_query.split(',')[0].split('.')[0].strip()
            if short_query and short_query != full_query:
                logger.info(f"Retrying with shortened query: {short_query[:80]}")
                results = search_knowledge(short_query)

        # If still no results, use generic fallback advice
        if not results or (len(results) > 0 and "No relevant context" in results[0]):
            logger.warning(f"RAG found no relevant documentation, using generic fallback advice")
            # Use generic printer troubleshooting advice when RAG has no results
            results = [GENERIC_PRINTER_HELP]

        if results:
            logger.info(f"Found {len(results)} RAG results")
            logger.debug(f"Results preview: {str(results)[:200]}")
        else:
            logger.warning("No RAG results found for query")

        return {**state, "rag_results": results}

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}", exc_info=True)
        return {**state, "rag_results": []}