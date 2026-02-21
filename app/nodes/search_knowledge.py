from app.state import AgentState
from app.services.rag import search_knowledge


def search_knowledge_node(state: AgentState) -> AgentState:
    query = state.get("user_message", "")
    results = search_knowledge(query)
    print(f"[RAG] Query: {query}")
    print(f"[RAG] Results: {results[:200] if results else 'EMPTY'}...")
    return {**state, "rag_results": results}