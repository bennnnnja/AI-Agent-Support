#!/usr/bin/env python3
"""
Diagnostic script to check what's in Redis Stream events.
Helps understand the payload format from webhook gateway.
"""

import json
import logging
from app.config import settings
from app.services.redis_consumer import get_redis_client

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def inspect_redis_events():
    """Read and inspect events from Redis Stream."""
    client = get_redis_client()
    
    logger.info(f"Reading from stream: {settings.redis_stream}")
    logger.info(f"Group: {settings.redis_group}")
    logger.info("=" * 60)
    
    # Read last 5 events (without consuming them)
    events = client.xrevrange(settings.redis_stream, count=5)
    
    if not events:
        logger.warning("No events found in stream")
        return
    
    logger.info(f"Found {len(events)} recent events:\n")
    
    for i, (event_id, data) in enumerate(events, 1):
        logger.info(f"Event #{i} (ID: {event_id.decode() if isinstance(event_id, bytes) else event_id}):")
        
        # Decode bytes if needed
        decoded_data = {}
        for key, value in data.items():
            k = key.decode() if isinstance(key, bytes) else key
            v = value.decode() if isinstance(value, bytes) else value
            decoded_data[k] = v
            logger.info(f"  {k}: {v[:100] if len(str(v)) > 100 else v}")
        
        logger.info("")
        
        # Try to parse payload if it's JSON
        if "payload" in decoded_data:
            try:
                payload = json.loads(decoded_data["payload"])
                logger.info(f"  Parsed payload:")
                for k, v in payload.items():
                    logger.info(f"    {k}: {str(v)[:100]}")
            except json.JSONDecodeError:
                logger.warning(f"  Payload is not valid JSON")
        
        logger.info("-" * 60)


if __name__ == "__main__":
    inspect_redis_events()
