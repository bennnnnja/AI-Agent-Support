import logging
from app.state import AgentState
from app.services.jira_mcp import add_comment, MCPError
from app.config import settings

logger = logging.getLogger(__name__)

_ESCALATION_REASON_MAP = {
    "forced_by_microservice": "Запрос требует участия специалиста",
    "attempt_limit": "Автоматические рекомендации не помогли решить проблему",
    "user_requested_human": "Пользователь запросил перевод на специалиста",
}


def post_comment_node(state: AgentState) -> AgentState:
    """
    Post generated response as a comment to Jira issue.
    """
    ticket_id = state.get("ticket_id", "")
    response = state.get("response", "")

    # Validation
    if not ticket_id:
        logger.warning("No ticket_id in state, cannot post comment")
        return state

    if not response:
        logger.warning(f"No response generated for {ticket_id}, skipping comment")
        return state

    # Trim response if too long (Jira comment limit is typically 32k chars)
    if len(response) > 30000:
        logger.warning(f"Response too long ({len(response)} chars), trimming for {ticket_id}")
        response = response[:29900] + "\n\n[... сообщение обрезано - слишком много символов]"

    try:
        logger.info(f"Posting comment to {ticket_id}")
        result = add_comment(ticket_id, response)

        if not result:
            logger.warning(f"MCP returned empty response for {ticket_id}")
            return {**state, "resolution": "warning_empty_mcp_response"}

        logger.info(f"Successfully posted comment to {ticket_id}")
        updated: dict = {**state, "resolution": "comment_posted"}
        # Move to "In Progress" only after first agent reply, and only if the ticket
        # is not already in a workflow-advanced state.
        current_status_lc = (state.get("issue_status") or "").strip().lower()
        target = (settings.status_in_progress or "").strip()
        logger.info(f"[post_comment] status_in_progress={target!r}")
        if (
            state.get("is_first_message")
            and target
            and current_status_lc != target.lower()
        ):
            updated["transition_to_status"] = target
        return updated
    except MCPError as e:
        logger.error(f"MCP error posting comment to {ticket_id}: {e}")
        return {**state, "resolution": f"error_posting_comment: {e}"}
    except Exception as e:
        logger.error(f"Failed to post comment to {ticket_id}: {e}", exc_info=True)
        return {**state, "resolution": f"error_posting_comment: {e}"}


def _format_escalation_reason(reason: str) -> str:
    """Преобразовать техническую причину эскалации в понятный пользователю текст."""
    if not reason:
        return "Требуется помощь специалиста"
 
    # Точное совпадение в маппинге
    if reason in _ESCALATION_REASON_MAP:
        return _ESCALATION_REASON_MAP[reason]
 
    # Причины вида "key=value"
    if reason.startswith("attempt_limit="):
        return "Автоматические рекомендации не помогли решить проблему"
    if reason.startswith("status="):
        return "Тикет передан в работу специалисту"
    if reason.startswith("support_comment="):
        return "Специалист уже подключился к решению вопроса"
 
    return "Требуется помощь специалиста"
 
 
def post_escalation_node(state: AgentState) -> AgentState:
    """Публикует пользовательское сообщение об эскалации в Jira."""
    ticket_id = state.get("ticket_id", "")
    reason = state.get("escalation_reason", "") or ""
 
    if not ticket_id:
        logger.warning("No ticket_id in state, cannot post escalation comment")
        return state
 
    user_reason = _format_escalation_reason(reason)
 
    message = settings.escalation_message_template.format(
        reason=user_reason,
        ticket_id=ticket_id,
    )
 
    try:
        logger.info(f"Posting escalation comment to {ticket_id} (reason={reason})")
        result = add_comment(ticket_id, message)

        if not result:
            logger.warning(f"MCP returned empty response for escalation on {ticket_id}")
            return {**state, "resolution": "escalation_posted_empty_mcp"}

        logger.info(f"Successfully posted escalation comment to {ticket_id}")
        updated: dict = {**state, "resolution": "escalation_posted"}
        target = (settings.status_escalated or "").strip()
        logger.info(f"[escalation] status_escalated={target!r} (len={len(target)})")
        if target:
            updated["transition_to_status"] = target
        new_assignee = (settings.escalation_assignee or "").strip()
        if new_assignee:
            updated["reassign_to"] = new_assignee
        return updated
    except MCPError as e:
        logger.error(f"MCP error posting escalation to {ticket_id}: {e}")
        return {**state, "resolution": f"error_posting_escalation: {e}"}
    except Exception as e:
        logger.error(f"Failed to post escalation to {ticket_id}: {e}", exc_info=True)
        return {**state, "resolution": f"error_posting_escalation: {e}"}


def post_resolution_node(state: AgentState) -> AgentState:
    """Post a closing comment when the user confirms the issue is resolved."""
    ticket_id = state.get("ticket_id", "")
    if not ticket_id:
        logger.warning("No ticket_id in state, cannot post resolution comment")
        return state

    message = settings.resolution_message_template

    try:
        logger.info(f"Posting resolution comment to {ticket_id}")
        result = add_comment(ticket_id, message)

        if not result:
            logger.warning(f"MCP returned empty response for resolution on {ticket_id}")
            return {**state, "resolution": "resolved_posted_empty_mcp"}

        logger.info(f"Successfully posted resolution comment to {ticket_id}")
        updated: dict = {**state, "resolution": "resolved_posted"}
        target = (settings.status_resolved or "").strip()
        logger.info(f"[resolution] status_resolved={target!r}")
        if target:
            updated["transition_to_status"] = target
        return updated
    except MCPError as e:
        logger.error(f"MCP error posting resolution to {ticket_id}: {e}")
        return {**state, "resolution": f"error_posting_resolution: {e}"}
    except Exception as e:
        logger.error(f"Failed to post resolution to {ticket_id}: {e}", exc_info=True)
        return {**state, "resolution": f"error_posting_resolution: {e}"}