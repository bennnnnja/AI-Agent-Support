import logging
from app.state import AgentState
from app.services.jira_mcp import add_comment, MCPError

logger = logging.getLogger(__name__)


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
