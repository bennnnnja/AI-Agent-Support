"""Tests for graph.build_graph — graph construction."""
import pytest
from app.graph import build_graph


class TestBuildGraph:
    def test_graph_builds_without_error(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        graph = build_graph()
        # CompiledGraph has .nodes dict
        node_names = set(graph.nodes.keys())
        expected = {"ingest_event", "classify_request", "search_knowledge",
                    "generate_response", "post_comment",
                    "post_escalation_comment", "post_resolution_comment",
                    "transition_status"}
        assert expected.issubset(node_names)
