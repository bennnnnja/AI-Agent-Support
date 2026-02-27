import logging
from app.state import AgentState
from app.services.jira_mcp import get_issue

logger = logging.getLogger(__name__)


def ingest_event(state: AgentState) -> AgentState:
    """
    Fetch issue details from Jira and populate state with issue info and comments history.
    This is critical for getting summary and description when webhook only sends issue_key.
    """
    ticket_id = state.get("ticket_id", "")
    if not ticket_id:
        logger.warning("No ticket_id in state, skipping ingestion")
        return state

    try:
        logger.info(f"[ingest] Fetching issue details for {ticket_id}")
        issue = get_issue(ticket_id, comment_limit=10)

        if not issue:
            logger.warning(f"[ingest] get_issue returned empty dict for {ticket_id}")
            logger.warning(f"[ingest] ⚠️ Check if MCP Atlassian server is running: uvx mcp-atlassian")
            return state

        logger.info(f"[ingest] Loaded issue data: key={issue.get('issue_key')}, summary={issue.get('summary', 'N/A')[:50]}")

        # Build conversation history from comments
        conversation_history = []

        # Add issue description as initial context
        if issue.get("description"):
            conversation_history.append({
                "role": "user",
                "author": "Reporter",
                "body": issue.get("description", ""),
                "created": issue.get("created", "")
            })

        # Add comments as conversation
        for comment in issue.get("comments", []):
            conversation_history.append({
                "role": "assistant" if "bot" in comment.get("author", "").lower() else "user",
                "author": comment.get("author", "Unknown"),
                "body": comment.get("body", ""),
                "created": comment.get("created", "")
            })

        logger.info(f"[ingest] Built conversation history with {len(conversation_history)} entries")

        # Update state with issue details
        updated_state = {
            **state,
            "issue_summary": issue.get("summary", ""),
            "issue_description": issue.get("description", ""),
            "issue_status": issue.get("status", ""),
            "issue_assignee": issue.get("assignee", ""),
            "issue_priority": issue.get("priority", ""),
            "conversation_history": conversation_history,
        }

        # CRITICAL: If user_message is empty, use summary from loaded issue
        if not state.get("user_message") and issue.get("summary"):
            logger.info(f"[ingest] Filling user_message from issue summary (was empty)")
            updated_state["user_message"] = issue.get("summary", "")
        
        # Also use description if we have it and message is still short
        if len((updated_state.get("user_message") or "")) < 10 and issue.get("description"):
            logger.info(f"[ingest] Enriching message with issue description")
            updated_state["user_message"] = f"{issue.get('summary', '')}\n\n{issue.get('description', '')}"

        return updated_state

    except Exception as e:
        logger.error(f"[ingest] Failed to fetch issue {ticket_id}: {e}", exc_info=True)
        if "Unknown tool" in str(e):
            logger.error(f"[ingest] ⚠️ MCP Atlassian server is not running!")
            logger.error(f"[ingest] Fix: Run 'uvx mcp-atlassian' in another terminal")
        return state