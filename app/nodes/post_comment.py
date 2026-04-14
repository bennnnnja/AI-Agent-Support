import logging
from app.state import AgentState
from app.services.jira_mcp import add_comment, MCPError
from app.config import settings

logger = logging.getLogger(__name__)

_ESCALATION_REASON_MAP = {
    "forced_by_microservice": "Запрос требует участия специалиста",
    "attempt_limit": "Автоматические рекомендации не помогли решить проблему",
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
        return {**state, "resolution": "comment_posted"}
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
        return {**state, "resolution": "escalation_posted"}
    except MCPError as e:
        logger.error(f"MCP error posting escalation to {ticket_id}: {e}")
        return {**state, "resolution": f"error_posting_escalation: {e}"}
    except Exception as e:
        logger.error(f"Failed to post escalation to {ticket_id}: {e}", exc_info=True)
        return {**state, "resolution": f"error_posting_escalation: {e}"}