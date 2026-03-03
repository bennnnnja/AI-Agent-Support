"""Tests for graph.route_by_category — routing logic."""
import pytest
from app.graph import route_by_category


class TestRouteByCategory:
    def test_tech_support(self):
        assert route_by_category({"category": "tech_support"}) == "search_knowledge"

    def test_off_topic(self):
        assert route_by_category({"category": "off_topic"}) == "end"

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
