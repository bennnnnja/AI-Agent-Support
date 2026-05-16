"""Tests for the same-stream-back stage gate (_is_enriched_event).

Topology: gateway writes RAW events (no stage), priority-service writes
ENRICHED events back with top-level stage="prioritized". The agent must
process only enriched events; raw copies are ack-and-skipped.
"""
from app.main import _is_enriched_event, ENRICHED_STAGE


def test_enriched_event_is_processed():
    raw_event = {
        "stage": "prioritized",
        "event_type": "issue_created",
        "payload": '{"issue_key": "SUP-1"}',
    }
    assert _is_enriched_event(raw_event) is True


def test_raw_event_without_stage_is_skipped():
    raw_event = {
        "event_type": "issue_created",
        "payload": '{"issue_key": "SUP-1"}',
    }
    assert _is_enriched_event(raw_event) is False


def test_empty_stage_is_skipped():
    assert _is_enriched_event({"stage": "", "event_type": "issue_created"}) is False


def test_other_stage_value_is_skipped():
    assert _is_enriched_event({"stage": "raw"}) is False
    assert _is_enriched_event({"stage": "summarized"}) is False


def test_stage_constant_value():
    assert ENRICHED_STAGE == "prioritized"
