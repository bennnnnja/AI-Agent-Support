"""Unit tests for app.services.state_store backed by fakeredis."""
import time

import fakeredis
import pytest

from app.services.state_store import StateStore


@pytest.fixture
def store():
    return StateStore(fakeredis.FakeRedis(decode_responses=True), cooldown_seconds=5)


class TestTerminalStates:
    def test_not_escalated_by_default(self, store):
        assert store.is_escalated("TEST-1") is False

    def test_mark_and_check_escalated(self, store):
        store.mark_escalated("TEST-1")
        assert store.is_escalated("TEST-1") is True

    def test_mark_escalated_isolated_per_ticket(self, store):
        store.mark_escalated("TEST-1")
        assert store.is_escalated("TEST-2") is False

    def test_mark_and_check_resolved(self, store):
        store.mark_resolved("TEST-1")
        assert store.is_resolved("TEST-1") is True

    def test_escalated_and_resolved_are_independent(self, store):
        store.mark_escalated("TEST-1")
        assert store.is_resolved("TEST-1") is False

    def test_mark_escalated_idempotent(self, store):
        store.mark_escalated("TEST-1")
        store.mark_escalated("TEST-1")
        assert store.is_escalated("TEST-1") is True


class TestCooldown:
    def test_no_cooldown_by_default(self, store):
        assert store.is_in_cooldown("TEST-1") is False

    def test_set_cooldown_then_active(self, store):
        store.set_cooldown("TEST-1")
        assert store.is_in_cooldown("TEST-1") is True

    def test_cooldown_isolated_per_ticket(self, store):
        store.set_cooldown("TEST-1")
        assert store.is_in_cooldown("TEST-2") is False

    def test_cooldown_expires(self, store):
        store.set_cooldown("TEST-1", seconds=1)  # ttl = 1+5 = 6, but...
        # Use very short ttl by direct override:
        store._r.set("agent:cooldown:TEST-2", "1", ex=1)
        time.sleep(1.2)
        assert store.is_in_cooldown("TEST-2") is False


class TestBotEcho:
    def test_no_echo_by_default(self, store):
        assert store.is_echo_body("TEST-1", "anything") is False

    def test_record_and_match(self, store):
        store.record_posted_comment("TEST-1", "Hello world")
        assert store.is_echo_body("TEST-1", "Hello world") is True

    def test_no_false_positive(self, store):
        store.record_posted_comment("TEST-1", "Bot response A")
        assert store.is_echo_body("TEST-1", "Different user message") is False

    def test_isolated_per_ticket(self, store):
        store.record_posted_comment("TEST-1", "Reply")
        assert store.is_echo_body("TEST-2", "Reply") is False

    def test_empty_body_is_noop(self, store):
        store.record_posted_comment("TEST-1", "")
        assert store.is_echo_body("TEST-1", "") is False

    def test_whitespace_normalised(self, store):
        store.record_posted_comment("TEST-1", "  Hello  ")
        assert store.is_echo_body("TEST-1", "  Hello  ") is True
