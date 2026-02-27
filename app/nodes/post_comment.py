from app.state import AgentState
from app.services.jira_mcp import add_comment


def post_comment_node(state: AgentState) -> AgentState:
    ticket_id = state.get("ticket_id", "")
    response = state.get("response", "")

    if not ticket_id or not response:
        print(f"[Jira] Skipping comment: ticket_id={ticket_id!r}, response_present={bool(response)}")
        return state

    try:
        add_comment(ticket_id, response)
        print(f"[Jira] Comment posted to {ticket_id}")
    except Exception as e:
        print(f"[Jira] Failed to post comment to {ticket_id}: {e}")

    return state