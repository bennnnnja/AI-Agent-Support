import logging
from app.state import AgentState
from app.services.jira_mcp import transition_issue, assign_issue, MCPError

logger = logging.getLogger(__name__)


def transition_node(state: AgentState) -> AgentState:
    """Transition the Jira issue to a new status and/or reassign it.

    Reads `transition_to_status` and `reassign_to` from state. No-op if both are empty.
    Failures are logged but do not break the pipeline — the comment has already been posted.
    """
    ticket_id = state.get("ticket_id", "")
    target_status = (state.get("transition_to_status") or "").strip()
    new_assignee = (state.get("reassign_to") or "").strip()
    resolution = state.get("resolution") or ""

    if not ticket_id:
        return state

    notes: list[str] = []

    if target_status:
        try:
            transition_issue(ticket_id, target_status)
            notes.append(f"transitioned:{target_status}")
            logger.info(f"[transition] {ticket_id} -> status={target_status}")
        except MCPError as e:
            logger.error(f"[transition] Failed to set status for {ticket_id}: {e}")
            notes.append(f"transition_failed:{target_status}")
        except Exception as e:
            logger.error(f"[transition] Unexpected error for {ticket_id}: {e}", exc_info=True)
            notes.append(f"transition_error:{target_status}")

    if new_assignee:
        try:
            assign_issue(ticket_id, new_assignee)
            notes.append(f"assigned:{new_assignee}")
            logger.info(f"[transition] {ticket_id} -> assignee={new_assignee}")
        except MCPError as e:
            logger.error(f"[transition] Failed to assign {ticket_id}: {e}")
            notes.append(f"assign_failed:{new_assignee}")
        except Exception as e:
            logger.error(f"[transition] Unexpected assign error for {ticket_id}: {e}", exc_info=True)
            notes.append(f"assign_error:{new_assignee}")

    if not notes:
        return state

    combined = "+".join([resolution] + notes) if resolution else "+".join(notes)
    return {**state, "resolution": combined}
