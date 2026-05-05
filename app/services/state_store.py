"""Redis-backed state for terminal tickets, cooldowns, and bot-echo bodies.

Survives agent restarts so the agent never re-escalates or double-comments
on the same ticket after a redeploy/crash. All keys carry TTLs to bound growth.

Keys:
  agent:terminal:escalated   SET   members = ticket ids; TTL refreshed on add
  agent:terminal:resolved    SET   members = ticket ids; TTL refreshed on add
  agent:cooldown:{ticket}    STR   exists => still in cooldown; TTL = cooldown+5
  agent:bot_echo:{ticket}    SET   members = md5 hashes of recent bot bodies
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

import redis as redis_mod

logger = logging.getLogger(__name__)

ESCALATED_KEY = "agent:terminal:escalated"
RESOLVED_KEY = "agent:terminal:resolved"
TERMINAL_TTL_SECONDS = 7 * 24 * 3600  # 7 days
ECHO_TTL_SECONDS = 3600  # 1 hour


def _body_hash(body: str) -> str:
    return hashlib.md5(body.strip()[:500].encode()).hexdigest()


class StateStore:
    def __init__(self, client: redis_mod.Redis, cooldown_seconds: int = 5):
        self._r = client
        self._cooldown_seconds = cooldown_seconds

    @property
    def cooldown_seconds(self) -> int:
        return self._cooldown_seconds

    # Terminal states
    def is_escalated(self, ticket: str) -> bool:
        return bool(self._r.sismember(ESCALATED_KEY, ticket))

    def mark_escalated(self, ticket: str) -> None:
        self._r.sadd(ESCALATED_KEY, ticket)
        self._r.expire(ESCALATED_KEY, TERMINAL_TTL_SECONDS)

    def is_resolved(self, ticket: str) -> bool:
        return bool(self._r.sismember(RESOLVED_KEY, ticket))

    def mark_resolved(self, ticket: str) -> None:
        self._r.sadd(RESOLVED_KEY, ticket)
        self._r.expire(RESOLVED_KEY, TERMINAL_TTL_SECONDS)

    # Cooldown (anti-flood per ticket)
    def is_in_cooldown(self, ticket: str) -> bool:
        return bool(self._r.exists(f"agent:cooldown:{ticket}"))

    def set_cooldown(self, ticket: str, seconds: Optional[int] = None) -> None:
        base = seconds if seconds is not None else self._cooldown_seconds
        ttl = max(int(base) + 5, 1)  # buffer guards against clock skew between workers
        self._r.set(f"agent:cooldown:{ticket}", "1", ex=ttl)

    # Bot-echo body detection
    def record_posted_comment(self, ticket: str, body: str) -> None:
        if not body:
            return
        key = f"agent:bot_echo:{ticket}"
        self._r.sadd(key, _body_hash(body))
        self._r.expire(key, ECHO_TTL_SECONDS)

    def is_echo_body(self, ticket: str, body: str) -> bool:
        if not body:
            return False
        return bool(self._r.sismember(f"agent:bot_echo:{ticket}", _body_hash(body)))


_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    """Lazily build a singleton backed by the real Redis client."""
    global _state_store
    if _state_store is None:
        from app.services.redis_consumer import get_redis_client
        cooldown = int(os.environ.get("COOLDOWN_SECONDS", "5"))
        _state_store = StateStore(get_redis_client(), cooldown_seconds=cooldown)
    return _state_store


def set_state_store(store: Optional[StateStore]) -> None:
    """Test hook: inject (or reset) the singleton."""
    global _state_store
    _state_store = store
