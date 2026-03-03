"""Tests for nodes/search_knowledge.search_knowledge_node."""
import pytest
from unittest.mock import patch
from app.nodes.search_knowledge import search_knowledge_node


class TestSearchKnowledgeNode:
    @patch("app.nodes.search_knowledge.search_knowledge")
    def test_normal_search(self, mock_search):
        mock_search.return_value = ["Doc about printers"]
        state = {"user_message": "принтер не печатает", "issue_description": ""}
        result = search_knowledge_node(state)
        assert result["rag_results"] == ["Doc about printers"]
        mock_search.assert_called_once()

    @patch("app.nodes.search_knowledge.search_knowledge")
    def test_query_combines_message_and_description(self, mock_search):
        mock_search.return_value = ["result"]
        state = {"user_message": "printer broken", "issue_description": "HP LaserJet"}
        search_knowledge_node(state)
        query = mock_search.call_args[0][0]
        assert "printer broken" in query
        assert "HP LaserJet" in query

    def test_empty_query_returns_empty(self):
        state = {"user_message": "", "issue_description": ""}
        result = search_knowledge_node(state)
        assert result["rag_results"] == []

    @patch("app.nodes.search_knowledge.search_knowledge")
    def test_rag_exception_returns_empty(self, mock_search):
        mock_search.side_effect = Exception("RAG service down")
        state = {"user_message": "help", "issue_description": ""}
        result = search_knowledge_node(state)
        assert result["rag_results"] == []

    @patch("app.nodes.search_knowledge.search_knowledge")
    def test_rag_returns_none(self, mock_search):
        mock_search.return_value = None
        state = {"user_message": "help", "issue_description": ""}
        result = search_knowledge_node(state)
        # None results logged as warning
        assert result["rag_results"] is None

    @patch("app.nodes.search_knowledge.search_knowledge")
    def test_preserves_state(self, mock_search):
        mock_search.return_value = ["doc"]
        state = {"user_message": "test", "issue_description": "", "ticket_id": "X-1", "category": "tech"}
        result = search_knowledge_node(state)
        assert result["ticket_id"] == "X-1"
        assert result["category"] == "tech"
