import redis
from app.config import settings


def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def ensure_group(client: redis.Redis):
    try:
        client.xgroup_create(
            settings.redis_stream,
            settings.redis_group,
            id="0",
            mkstream=True,
        )
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def read_events(client: redis.Redis) -> list[dict]:
    results = client.xreadgroup(
        groupname=settings.redis_group,
        consumername=settings.redis_consumer,
        streams={settings.redis_stream: ">"},
        count=1,
        block=5000,
    )

    if not results:
        return []

    events = []
    for stream_name, messages in results:
        for message_id, data in messages:
            events.append({"id": message_id, **data})
            client.xack(settings.redis_stream, settings.redis_group, message_id)

    return events