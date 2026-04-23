from langgraph.graph import StateGraph, END
from app.state import AgentState
from app.nodes.ingest import ingest_event
from app.nodes.classify import classify_request
from app.nodes.search_knowledge import search_knowledge_node
from app.nodes.generate import generate_response
from app.nodes.post_comment import post_comment_node, post_escalation_node
from app.nodes.transition import transition_node


def route_after_ingest(state: AgentState) -> str:
    if state.get("skip"):
        return "skip"
    return "escalate" if state.get("escalated") else "classify"



def route_by_category(state: AgentState) -> str:
    category = state.get("category", "unclear")

    if category == "tech_support":
        return "search_knowledge"
    elif category == "off_topic":
        return "generate_response"
    else:
        return "search_knowledge"


def build_graph():
    graph = StateGraph(AgentState)

    # Ноды
    graph.add_node("ingest_event", ingest_event)
    graph.add_node("classify_request", classify_request)
    graph.add_node("search_knowledge", search_knowledge_node)
    graph.add_node("generate_response", generate_response)
    graph.add_node("post_comment", post_comment_node)
    graph.add_node("post_escalation_comment", post_escalation_node)
    graph.add_node("transition_status", transition_node)

    # Точка входа
    graph.set_entry_point("ingest_event")

    # Переходы
    graph.add_conditional_edges("ingest_event", route_after_ingest,
    {
        "classify": "classify_request",
        "escalate": "post_escalation_comment",
        "skip": END,
    })

    # Ветвление по категории
    graph.add_conditional_edges("classify_request", route_by_category, {
        "search_knowledge": "search_knowledge",
        "generate_response": "generate_response",
    })

    graph.add_edge("search_knowledge", "generate_response")
    graph.add_edge("generate_response", "post_comment")
    graph.add_edge("post_comment", "transition_status")
    graph.add_edge("post_escalation_comment", "transition_status")
    graph.add_edge("transition_status", END)

    return graph.compile()