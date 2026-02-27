import logging
from app.state import AgentState
from app.services.rag import search_knowledge

logger = logging.getLogger(__name__)


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

    query = " ".join(query_parts)

    if not query:
        logger.warning("No query content for knowledge search")
        return {**state, "rag_results": []}

    try:
        logger.info(f"Searching knowledge base (query len={len(query)})")
        results = search_knowledge(query)

        if results:
            logger.info(f"Found {len(results)} RAG results")
            logger.debug(f"Results preview: {str(results)[:200]}")
        else:
            logger.warning("No RAG results found for query")

        return {**state, "rag_results": results}

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}", exc_info=True)
        return {**state, "rag_results": []}