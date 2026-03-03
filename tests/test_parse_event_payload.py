"""Tests for main._parse_event_payload — Redis event payload parsing."""
import json
import pytest
from app.main import _parse_event_payload


class TestParseEventPayload:
    def test_json_string_payload(self):
        event = {"payload": '{"issue_key": "TEST-1", "summary": "Bug"}'}
        result = _parse_event_payload(event)
        assert result == {"issue_key": "TEST-1", "summary": "Bug"}

    def test_dict_payload_passthrough(self):
        payload = {"issue_key": "TEST-2", "body": "Hello"}
        event = {"payload": payload}
        result = _parse_event_payload(event)
        assert result is payload  # same object, no copy

    def test_invalid_json_returns_empty(self):
        event = {"payload": "not json at all {{{"}
        result = _parse_event_payload(event)
        assert result == {}

    def test_empty_string_payload(self):
        event = {"payload": ""}
        result = _parse_event_payload(event)
        assert result == {}

    def test_missing_payload_key(self):
        event = {"event_type": "issue_created"}
        result = _parse_event_payload(event)
        # default is "{}" which parses to empty dict
        assert result == {}

    def test_payload_default_empty_json(self):
        """When payload key is absent, default '{}' should parse to empty dict."""
        result = _parse_event_payload({})
        assert result == {}

    def test_unexpected_type_int(self):
        event = {"payload": 42}
        result = _parse_event_payload(event)
        assert result == {}

    def test_unexpected_type_list(self):
        event = {"payload": [1, 2, 3]}
        result = _parse_event_payload(event)
        assert result == {}

    def test_nested_json_payload(self):
        inner = {"issue_key": "TEST-5", "comments": [{"author": "User", "body": "Hi"}]}
        event = {"payload": json.dumps(inner)}
        result = _parse_event_payload(event)
        assert result == inner

    def test_whitespace_only_json(self):
        event = {"payload": "   "}
        result = _parse_event_payload(event)
        assert result == {}
