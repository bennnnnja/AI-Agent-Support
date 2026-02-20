from langgraph.graph import StateGraph, END
from app.state import AgentState
from app.nodes.ingest import ingest_event
from app.nodes.classify import classify_request
from app.nodes.generate import generate_response


def route_by_category(state: AgentState) -> str:
    category = state.get("category", "unclear")

    if category == "tech_support":
        return "generate_response"
    elif category == "off_topic":
        return "end"
    else:
        return "generate_response"


def build_graph():
    graph = StateGraph(AgentState)

    # Ноды
    graph.add_node("ingest_event", ingest_event)
    graph.add_node("classify_request", classify_request)
    graph.add_node("generate_response", generate_response)

    # Точка входа
    graph.set_entry_point("ingest_event")

    # Переходы
    graph.add_edge("ingest_event", "classify_request")

    # Ветвление по категории
    graph.add_conditional_edges("classify_request", route_by_category, {
        "generate_response": "generate_response",
        "end": END,
    })

    graph.add_edge("generate_response", END)

    return graph.compile()