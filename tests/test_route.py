"""Tests for graph.route_by_category — routing logic."""
import pytest
from app.graph import route_by_category, route_after_ingest


class TestRouteByCategory:
    def test_tech_support(self):
        assert route_by_category({"category": "tech_support"}) == "search_knowledge"

    def test_off_topic(self):
        assert route_by_category({"category": "off_topic"}) == "generate_response"

    def test_unclear_goes_to_search(self):
        assert route_by_category({"category": "unclear"}) == "search_knowledge"

    def test_none_category(self):
        assert route_by_category({"category": None}) == "search_knowledge"

    def test_missing_category(self):
        assert route_by_category({}) == "search_knowledge"

    def test_empty_string_category(self):
        assert route_by_category({"category": ""}) == "search_knowledge"

    def test_unknown_category(self):
        assert route_by_category({"category": "billing"}) == "search_knowledge"


class TestRouteAfterIngest:
    def test_escalated_true_goes_to_escalate(self):
        assert route_after_ingest({"escalated": True}) == "escalate"

    def test_escalated_false_goes_to_classify(self):
        assert route_after_ingest({"escalated": False}) == "classify"

    def test_missing_escalated_goes_to_classify(self):
        assert route_after_ingest({}) == "classify"

    def test_skip_true_goes_to_skip(self):
        # skip takes precedence over escalation
        assert route_after_ingest({"skip": True, "escalated": True}) == "skip"

    def test_skip_true_no_escalation(self):
        assert route_after_ingest({"skip": True}) == "skip"
