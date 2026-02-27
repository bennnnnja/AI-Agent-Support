import json
from app.config import settings
from app.services.redis_consumer import get_redis_client, ensure_group, read_events
from app.graph import build_graph


def main():
    print(f"Starting agent | stream={settings.redis_stream}")

    client = get_redis_client()
    ensure_group(client)
    graph = build_graph()

    print("Listening for events...")

    while True:
        events = read_events(client)
        for event in events:
            print(f"\n--- New event: {event.get('issue_key')} ---")

            payload = event.get("payload", "{}")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}

            is_first_message = event.get("event_type") == "issue_created"
            if is_first_message:
                user_message = payload.get("issue_summary", "")
            else:
                user_message = payload.get("comment_body") or payload.get("issue_summary", "")


            initial_state = {
                "ticket_id": payload.get("issue_key") or event.get("issue_key", ""),
                "user_message": user_message,
                "is_first_message": is_first_message,
                "conversation_history": [],
                "category": None,
                "rag_results": [],
                "response": None,
                "attempt_count": 0,
                "resolution": None,
            }

            result = graph.invoke(initial_state)

            print(f"Category: {result.get('category')}")
            print(f"Response: {result.get('response')}")
            print("---")


if __name__ == "__main__":
    main()