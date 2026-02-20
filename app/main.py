from app.config import settings
from app.services.redis_consumer import get_redis_client, ensure_group, read_events


def main():
    print(f"Starting agent | stream={settings.redis_stream}")

    client = get_redis_client()
    ensure_group(client)

    print("Listening for events...")

    while True:
        events = read_events(client)
        for event in events:
            print(f"Got event: {event}")


if __name__ == "__main__":
    main()