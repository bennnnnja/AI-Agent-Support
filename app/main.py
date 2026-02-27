import json
import logging
from app.config import settings
from app.services.redis_consumer import get_redis_client, ensure_group, read_events
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


def _validate_event(event: dict) -> bool:
    """Validate that event has required fields and should be processed."""
    issue_key = event.get("issue_key") or _parse_event_payload(event).get("issue_key")
    event_type = event.get("event_type")

    if not issue_key:
        logger.warning("Event missing issue_key, skipping")
        return False

    if not event_type:
        logger.warning("Event missing event_type, skipping")
        return False

    # IMPORTANT: Ignore events from the bot itself to prevent infinite loops
    # Check if this is a comment event and if it's from the bot
    if event_type in ("comment_added", "comment_created"):
        # TEMPORARY: Block ALL comment events while we debug the filter
        # TODO: Remove this block once comment filter is working properly
        logger.warning(f"[FILTER] BLOCKING comment_* event entirely (temporary debug measure)")
        return False

    return True


def main():
    print(f"Starting agent | stream={settings.redis_stream}")

    client = get_redis_client()
    ensure_group(client)
    graph = build_graph()

    print("Listening for events...")

    while True:
        events = read_events(client)
        for event in events:
            # DEBUG: Log raw event structure
            logger.debug(f"Raw event from Redis: {event}")

            # Validate event has required fields
            if not _validate_event(event):
                continue

            payload = _parse_event_payload(event)
            event_type = event.get("event_type")
            issue_key = payload.get("issue_key") or event.get("issue_key", "")

            logger.info(f"Processing {event_type} for {issue_key}")

            # Determine message based on event type
            if event_type == "issue_created":
                # Try to get summary from payload, will be loaded in ingest_event if missing
                user_message = payload.get("summary") or ""
                is_first_message = True
            elif event_type in ("comment_created", "issue_updated"):
                # Prefer comment body, fallback to summary
                user_message = payload.get("body") or payload.get("summary") or ""
                is_first_message = False
            else:
                logger.warning(f"Unknown event type: {event_type}, using summary as message")
                user_message = payload.get("summary") or ""
                is_first_message = False

            # DON'T skip if user_message is empty - ingest_event will load it from Jira
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
                "attempt_count": 0,
                "resolution": None,
            }

            try:
                logger.info(f"Invoking graph for {issue_key}")
                result = graph.invoke(initial_state)

                logger.info(f"Result for {issue_key}:")
                logger.info(f"  Category: {result.get('category')}")
                response = result.get('response', '')
                if response:
                    logger.info(f"  Response: {response[:100]}")
                else:
                    logger.warning(f"  Response: (empty or None)")
            except Exception as e:
                logger.error(f"Graph execution failed for {issue_key}: {e}", exc_info=True)


if __name__ == "__main__":
    main()