from app.state import AgentState
from app.services.jira_mcp import get_issue


def ingest_event(state: AgentState) -> AgentState:
    ticket_id = state.get("ticket_id", "")
    if not ticket_id:
        return state

    try:
        issue_text = get_issue(ticket_id)
        if issue_text:
            return {**state, "user_message": issue_text}
    except Exception as e:
        print(f"[Jira] Failed to fetch issue {ticket_id}: {e}")

    return state