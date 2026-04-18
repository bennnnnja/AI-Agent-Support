import logging
from app.state import AgentState
from app.services.jira_mcp import get_issue
from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_assignee(value) -> str:
    """Normalize assignee from Jira payload to a comparable username/display name."""
    if not value:
        return ""
    if isinstance(value, dict):
        # Jira payloads often provide assignee as an object
        candidate = (
            value.get("name")
            or value.get("display_name")
            or value.get("displayName")
            or value.get("accountId")
            or ""
        )
    else:
        candidate = str(value)
    assignee = candidate.strip()
    if assignee.lower() in {"", "none", "null", "unassigned"}:
        return ""
    return assignee


def _count_agent_attempts(conversation_history: list[dict]) -> int:
    attempts = 0
    for msg in conversation_history or []:
        role = (msg.get("role") or "").strip().lower()
        if role == "assistant":
            attempts += 1
    return attempts


def _extract_latest_user_message(conversation_history: list[dict]) -> str:
    for msg in reversed(conversation_history or []):
        role = (msg.get("role") or "").strip().lower()
        body = (msg.get("body") or "").strip()
        if role == "user" and body:
            return body
    return ""


def _is_escalated(
    issue_status: str,
    issue_assignee,
    conversation_history: list[dict],
    force_escalation: bool,
    attempt_count: int,
) -> tuple[bool, str]:
    status_norm = (issue_status or "").strip().lower()
    _ = _normalize_assignee(issue_assignee)

    if force_escalation:
        return True, "forced_by_microservice"

    if status_norm and status_norm in settings.escalation_status_set:
        return True, f"status={issue_status}"

    for msg in conversation_history or []:
        if (msg.get("role") or "").strip().lower() == "support":
            author = msg.get("author") or ""
            return True, f"support_comment={author}"

    if attempt_count >= settings.max_self_help_attempts:
        return True, f"attempt_limit={attempt_count}"

    return False, ""


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
        bot_username_lc = (settings.bot_username or "").lower()
        support_set_lc = settings.support_username_set  # already lowercased
        for comment in issue.get("comments", []):
            author = comment.get("author", "") or ""
            author_lc = author.lower()
            if bot_username_lc and author_lc == bot_username_lc:
                role = "assistant"
            elif author_lc in support_set_lc:
                role = "support"
            else:
                role = "user"
            conversation_history.append({
                "role": role,
                "author": comment.get("author", "Unknown"),
                "body": comment.get("body", ""),
                "created": comment.get("created", "")
            })

        logger.info(f"[ingest] Built conversation history with {len(conversation_history)} entries")

        # Guard against processing an echo of our own last comment.
        # The webhook gateway may strip author metadata, so _validate_event
        # lets the event through — here we have full Jira context and can tell.
        if conversation_history and not state.get("is_first_message"):
            last_msg = conversation_history[-1]
            if last_msg.get("role") == "assistant":
                logger.info(
                    f"[ingest] Latest comment is from bot, skipping re-processing for {ticket_id}"
                )
                return {
                    **state,
                    "conversation_history": conversation_history,
                    "resolution": "skipped_bot_echo",
                    "escalated": False,
                    "skip": True,
                }

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

        attempt_count = _count_agent_attempts(conversation_history)
        updated_state["attempt_count"] = attempt_count

        escalated, reason = _is_escalated(
            updated_state.get("issue_status", ""),
            updated_state.get("issue_assignee", ""),
            conversation_history,
            bool(updated_state.get("force_escalation")),
            attempt_count,
        )
        updated_state["escalated"] = escalated
        updated_state["escalation_reason"] = reason or None
        if escalated:
            updated_state["resolution"] = "skipped_escalated"
            logger.info(f"[ESCALATED] {ticket_id} reason={reason}")

        # If current event has no explicit message, prefer the latest user comment from history.
        # This is important for comment events where webhook payload may omit "body".
        if not state.get("user_message"):
            latest_user_msg = _extract_latest_user_message(conversation_history)
            if latest_user_msg:
                logger.info("[ingest] Filling user_message from latest user comment (payload was empty)")
                updated_state["user_message"] = latest_user_msg
            elif issue.get("summary"):
                logger.info("[ingest] Filling user_message from issue summary (was empty)")
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