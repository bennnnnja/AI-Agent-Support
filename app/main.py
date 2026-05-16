import concurrent.futures
import json
import logging
import os
import signal

from app.config import settings
from app.services.redis_consumer import get_redis_client, ensure_group, read_events, ack_event
from app.services.state_store import get_state_store
from app.graph import build_graph
from app.health import start_health_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Graceful shutdown flag — set by SIGINT/SIGTERM handlers, checked by main loop.
_shutdown_requested: bool = False


def _request_shutdown(signum, _frame):
    """Signal handler: ask the main loop to exit cleanly after current iteration."""
    global _shutdown_requested
    logger.info("[SHUTDOWN] Received signal %s — finishing current iteration...", signum)
    _shutdown_requested = True


_REQUIRED_MCP_TOOLS = {
    "jira_get_issue",
    "jira_add_comment",
    "jira_get_transitions",
    "jira_transition_issue",
    "jira_update_issue",
}


def _check_mcp_tools_available() -> None:
    """Best-effort startup check that critical Jira MCP tools are available.

    Bounded by MCP_STARTUP_TIMEOUT (default 10s) so a hung MCP subprocess
    cannot stall the entire agent startup.
    """
    timeout = float(os.environ.get("MCP_STARTUP_TIMEOUT", "10"))
    try:
        from app.services.jira_mcp import list_tools
    except Exception as e:
        logger.warning("[MCP] Could not import list_tools: %s", e)
        return

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(list_tools)
    try:
        tools = set(future.result(timeout=timeout))
    except concurrent.futures.TimeoutError:
        logger.warning(
            "[MCP] Startup tools check timed out after %ss — continuing without verification",
            timeout,
        )
        ex.shutdown(wait=False, cancel_futures=True)
        return
    except Exception as e:
        logger.warning("[MCP] Failed to list tools at startup: %s", e)
        ex.shutdown(wait=False, cancel_futures=True)
        return
    ex.shutdown(wait=False)

    missing = _REQUIRED_MCP_TOOLS - tools
    if missing:
        logger.warning("[MCP] Missing critical Jira tools: %s", sorted(missing))
    else:
        logger.info("[MCP] All required Jira tools available (%d total)", len(tools))


def _record_posted_comment(ticket_id: str, body: str) -> None:
    """Compatibility wrapper: forward to state_store."""
    get_state_store().record_posted_comment(ticket_id, body)


def _is_echo_body(ticket_id: str, body: str) -> bool:
    """Compatibility wrapper: forward to state_store."""
    return get_state_store().is_echo_body(ticket_id, body)


ENRICHED_STAGE = "prioritized"


def _is_enriched_event(raw_event: dict) -> bool:
    """True only for events enriched by priority-service.

    Same-stream-back topology: gateway writes RAW events (no stage marker)
    and priority-service writes ENRICHED events back to the same stream with
    top-level stage="prioritized". Without this gate every ticket is processed
    twice — once on the RAW copy, once on the ENRICHED copy.
    """
    return raw_event.get("stage") == ENRICHED_STAGE


def _parse_event_payload(event: dict) -> dict:
    """Parse and validate event payload from Redis."""
    payload = event.get("payload", "{}")

    # If payload is already a dict, return it
    if isinstance(payload, dict):
        return payload

    # Try to parse as JSON string
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse payload JSON: {e}")
            logger.debug(f"Raw payload: {payload[:300]}")
            return {}

    logger.warning(f"Unexpected payload type: {type(payload)}")
    return {}


def _looks_like_bot_comment(body: str) -> bool:
    """Detect bot's own comments by body content.

    Used as a fallback when the webhook payload doesn't include the author field.
    Matches against the escalation template prefix and an optional configurable marker.
    """
    if not body:
        return False
    markers: list[str] = []
    # First line of the escalation template is a stable, distinctive prefix.
    esc_first_line = settings.escalation_message_template.split("\n")[0].strip()
    if esc_first_line:
        markers.append(esc_first_line[:40])
    if settings.bot_comment_marker:
        markers.append(settings.bot_comment_marker)
    return any(body.startswith(m) for m in markers if m)


def _validate_event(payload: dict, event_type: str) -> bool:
    """Validate that event has required fields and should be processed.

    Args:
        payload: Already-parsed event payload.
        event_type: Event type string from Redis fields.
    """
    issue_key = payload.get("issue_key")

    if not issue_key:
        logger.warning("Event missing issue_key, skipping")
        return False

    if not event_type:
        logger.warning("Event missing event_type, skipping")
        return False

    # Block all events for tickets already in an escalated/in-progress workflow state.
    # Support is working the ticket — the agent must step away entirely.
    payload_status = (payload.get("status") or "").strip().lower()
    if payload_status and payload_status in settings.escalation_status_set:
        logger.info(f"[FILTER] Skipping event for escalated ticket {issue_key} (status={payload_status})")
        return False

    user_like_roles = {"user", "admin", "administrator", "telegram", "customer"}
    user_like_sources = {"telegram", "web", "portal", "customer"}

    bot_username_lc = (settings.bot_username or "").lower()
    support_set_lc = settings.support_username_set  # already lowercased in config

    # Filter out bot's own comment events to prevent infinite loops
    if event_type in ("comment_added", "comment_created"):
        comment_author = (payload.get("author") or "").strip()
        comment_author_lc = comment_author.lower()
        role = (payload.get("role") or "").strip().lower()
        source = (payload.get("source") or "").strip().lower()

        if bot_username_lc and comment_author_lc == bot_username_lc:
            logger.info(f"[FILTER] Ignoring comment from bot ({comment_author}) on {issue_key}")
            return False

        # If author is missing, fall back to body-based bot detection.
        # This is the common case when the webhook gateway strips metadata.
        if not comment_author:
            comment_body = (payload.get("body") or "").strip()
            if _looks_like_bot_comment(comment_body):
                logger.info(f"[FILTER] Ignoring bot-like comment (body match) on {issue_key}")
                return False
            if _is_echo_body(issue_key, comment_body):
                logger.info(f"[FILTER] Ignoring echo comment (body-hash match) on {issue_key}")
                return False
            # Role/source, if present, still must indicate a user.
            if role and role not in user_like_roles:
                logger.info(f"[FILTER] Skipping comment role={role} on {issue_key}")
                return False
            if source and source not in user_like_sources:
                logger.info(f"[FILTER] Skipping comment source={source} on {issue_key}")
                return False
            logger.info(f"[FILTER] Allowing comment with no author on {issue_key} (assuming user)")

        # Skip comments from support users (if configured)
        if comment_author_lc and comment_author_lc in support_set_lc:
            logger.info(f"[FILTER] Skipping comment from support {comment_author} on {issue_key}")
            return False

    # Minimal filter for issue_updated: if author exists and is not a user, skip (prevents reacting to support automation)
    if event_type == "issue_updated":
        author = (payload.get("author") or "").strip()
        author_lc = author.lower()
        role = (payload.get("role") or "").strip().lower()
        source = (payload.get("source") or "").strip().lower()
        if author_lc and bot_username_lc and author_lc == bot_username_lc:
            logger.info(f"[FILTER] Skipping issue_updated from bot ({author}) on {issue_key}")
            return False
        if author_lc and author_lc in support_set_lc:
            logger.info(f"[FILTER] Skipping issue_updated from support {author} on {issue_key}")
            return False
        if role and role not in user_like_roles:
            logger.info(f"[FILTER] Skipping issue_updated role={role} on {issue_key}")
            return False
        if source and source not in user_like_sources:
            logger.info(f"[FILTER] Skipping issue_updated source={source} on {issue_key}")
            return False

    return True


def main():
    logger.info(f"Starting agent | stream={settings.redis_stream}")
    logger.info(
        "[CONFIG] status_in_progress=%r  status_resolved=%r  status_escalated=%r  "
        "escalation_assignee=%r  bot_username=%r",
        settings.status_in_progress,
        settings.status_resolved,
        settings.status_escalated,
        settings.escalation_assignee,
        settings.bot_username,
    )

    client = get_redis_client()
    ensure_group(client)
    graph = build_graph()
    store = get_state_store()

    # Hardening: liveness probe + signal-based graceful shutdown + MCP availability check.
    start_health_server()
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    _check_mcp_tools_available()

    logger.info("Listening for events...")

    while not _shutdown_requested:
        events = read_events(client)
        for message_id, raw_event in events:
            if _shutdown_requested:
                logger.info("[SHUTDOWN] Stopping mid-batch; %s left unacked for next consumer", message_id)
                break
            logger.debug(f"Raw event from Redis: {raw_event}")

            # Same-stream-back topology: gateway writes RAW events, priority-service
            # writes ENRICHED events (stage=prioritized) back to the same stream.
            # Only enriched events are actionable; ack-and-skip the RAW copies,
            # otherwise every ticket would be processed twice.
            if not _is_enriched_event(raw_event):
                logger.info(
                    "[STAGE] Skipping non-enriched event %s (stage=%r)",
                    message_id, raw_event.get("stage", ""),
                )
                ack_event(client, message_id)
                continue

            # Parse payload once
            payload = _parse_event_payload(raw_event)
            event_type = raw_event.get("event_type", "")
            issue_key = payload.get("issue_key") or raw_event.get("issue_key", "")
            payload["issue_key"] = issue_key  # ensure issue_key is in payload

            # Terminal state: ticket already escalated or resolved — agent must not respond
            if store.is_escalated(issue_key):
                logger.info(f"[TERMINAL] Skipping {event_type} for {issue_key} (already escalated)")
                ack_event(client, message_id)
                continue
            if store.is_resolved(issue_key):
                logger.info(f"[TERMINAL] Skipping {event_type} for {issue_key} (already resolved)")
                ack_event(client, message_id)
                continue

            # Per-ticket cooldown: prevent re-processing the same ticket too soon
            if event_type != "issue_created" and store.is_in_cooldown(issue_key):
                logger.info(
                    f"[COOLDOWN] Skipping {event_type} for {issue_key} "
                    f"(<{store.cooldown_seconds}s since last processed)"
                )
                ack_event(client, message_id)
                continue

            # Validate event
            if not _validate_event(payload, event_type):
                ack_event(client, message_id)
                continue

            logger.info(f"Processing {event_type} for {issue_key}")

            # Determine message based on event type (body = new comment text for dialogue)
            if event_type == "issue_created":
                user_message = payload.get("summary") or ""
                is_first_message = True
            elif event_type in ("comment_created", "comment_added", "issue_updated"):
                user_message = payload.get("body") or payload.get("summary") or ""
                is_first_message = False
            else:
                logger.warning(f"Unknown event type: {event_type}, using summary as message")
                user_message = payload.get("summary") or ""
                is_first_message = False

            if not user_message:
                logger.debug(f"No message in payload for {issue_key}, will load from Jira in ingest_event")

            initial_state = {
                "ticket_id": issue_key,
                "user_message": user_message,
                "is_first_message": is_first_message,
                "conversation_history": [],
                "attempt_count": 0,
                # External classifier/microservice can force escalation via payload
                "force_escalation": bool(
                    payload.get("force_escalation")
                    or payload.get("super_priority")
                    or payload.get("needs_human")
                ),
                "category": None,
                "rag_results": [],
                "response": None,
                "resolution": None,
            }

            try:
                logger.info(f"Invoking graph for {issue_key}")
                result = graph.invoke(initial_state)

                logger.info(f"Result for {issue_key}:")
                logger.info(f"Category: {result.get('category')}")
                response_preview = result.get("response")
                if isinstance(response_preview, str):
                    response_preview = response_preview[:100]
                else:
                    response_preview = "None"
                logger.info(f"Response: {response_preview}")
                logger.info(
                    "[METRICS] ticket=%s classification=%s rag_hits=%d rag_latency_ms=%d "
                    "attempt_count=%d escalated=%s escalation_reason=%s resolution=%s",
                    issue_key,
                    result.get("category"),
                    len(result.get("rag_results", [])),
                    result.get("rag_latency_ms", 0),
                    result.get("attempt_count", 0),
                    result.get("escalated", False),
                    result.get("escalation_reason"),
                    result.get("resolution"),
                )

                store.set_cooldown(issue_key)

                resolution = result.get("resolution") or ""
                if resolution == "escalation_posted":
                    store.mark_escalated(issue_key)
                elif resolution == "resolved_posted":
                    store.mark_resolved(issue_key)

                if resolution in ("comment_posted", "escalation_posted", "resolved_posted"):
                    response_body = result.get("response") or ""
                    store.record_posted_comment(issue_key, response_body)

                ack_event(client, message_id)
            except Exception as e:
                logger.error(f"Graph execution failed for {issue_key}: {e}", exc_info=True)
                # Do NOT ack — event stays in pending list for reprocessing

    logger.info("[SHUTDOWN] Loop exited cleanly")


if __name__ == "__main__":
    main()
