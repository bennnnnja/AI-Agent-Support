import json
import logging
from app.config import settings
from app.services.redis_consumer import get_redis_client, ensure_group, read_events, ack_event
from app.graph import build_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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

    # Filter out bot's own comment events to prevent infinite loops
    if event_type in ("comment_added", "comment_created"):
        comment_author = payload.get("author", "")
        if settings.bot_username and comment_author == settings.bot_username:
            logger.info(f"[FILTER] Ignoring comment from bot ({comment_author}) on {issue_key}")
            return False

    return True


def main():
    logger.info(f"Starting agent | stream={settings.redis_stream}")

    client = get_redis_client()
    ensure_group(client)
    graph = build_graph()

    logger.info("Listening for events...")

    while True:
        events = read_events(client)
        for message_id, raw_event in events:
            logger.debug(f"Raw event from Redis: {raw_event}")

            # Parse payload once
            payload = _parse_event_payload(raw_event)
            event_type = raw_event.get("event_type", "")
            issue_key = payload.get("issue_key") or raw_event.get("issue_key", "")
            payload["issue_key"] = issue_key  # ensure issue_key is in payload

            # Validate event
            if not _validate_event(payload, event_type):
                ack_event(client, message_id)
                continue

            logger.info(f"Processing {event_type} for {issue_key}")

            # Determine message based on event type
            if event_type == "issue_created":
                user_message = payload.get("summary") or ""
                is_first_message = True
            elif event_type in ("comment_created", "issue_updated"):
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
                "category": None,
                "rag_results": [],
                "response": None,
                "resolution": None,
            }

            try:
                logger.info(f"Invoking graph for {issue_key}")
                result = graph.invoke(initial_state)

                logger.info(f"Result for {issue_key}:")
                logger.info(f"  Category: {result.get('category')}")
                logger.info(f"  Response: {result.get('response', 'None')[:100]}")
                ack_event(client, message_id)
            except Exception as e:
                logger.error(f"Graph execution failed for {issue_key}: {e}", exc_info=True)
                # Do NOT ack — event stays in pending list for reprocessing


if __name__ == "__main__":
    main()