from langgraph.graph import StateGraph, END
from app.state import AgentState
from app.nodes.ingest import ingest_event
from app.nodes.classify import classify_request
from app.nodes.search_knowledge import search_knowledge_node
from app.nodes.generate import generate_response
from app.nodes.post_comment import post_comment_node


def handle_off_topic(state: AgentState) -> AgentState:
    """Handle off-topic requests by setting a default response."""
    return {
        **state,
        "response": "Это обращение не относится к технической поддержке. Пожалуйста, обратитесь в соответствующий отдел.",
        "resolution": "off_topic"
    }


def route_by_category(state: AgentState) -> str:
    category = state.get("category", "unclear")

    if category == "tech_support":
        return "search_knowledge"
    elif category == "off_topic":
        return "off_topic"
    else:
        return "search_knowledge"


def build_graph():
    graph = StateGraph(AgentState)

    # Ноды
    graph.add_node("ingest_event", ingest_event)
    graph.add_node("classify_request", classify_request)
    graph.add_node("search_knowledge", search_knowledge_node)
    graph.add_node("generate_response", generate_response)
    graph.add_node("off_topic", handle_off_topic)
    graph.add_node("post_comment", post_comment_node)

    # Точка входа
    graph.set_entry_point("ingest_event")

    # Переходы
    graph.add_edge("ingest_event", "classify_request")

    # Ветвление по категории
    graph.add_conditional_edges("classify_request", route_by_category, {
        "search_knowledge": "search_knowledge",
        "off_topic": "off_topic",
    })

    # Маршруты
    graph.add_edge("search_knowledge", "generate_response")
    graph.add_edge("generate_response", "post_comment")
    graph.add_edge("off_topic", "post_comment")
    graph.add_edge("post_comment", END)

    return graph.compile()