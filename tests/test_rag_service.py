"""Tests for services/rag — RAG API (LightRAG login + /query) integration."""
from unittest.mock import patch, MagicMock
import httpx

from app.services.rag import search_knowledge


def _mock_post_ok(json_value):
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    return resp


@patch("app.services.rag._get_rag_token", return_value="fake-token")
class TestSearchKnowledge:
    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_successful_search_single_response(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10
        mock_client_cls.return_value.__enter__.return_value.post.return_value = _mock_post_ok(
            {"response": "Relevant documentation text"}
        )
        results = search_knowledge("printer issue")
        assert results == ["Relevant documentation text"]

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_no_context_response_filtered(self, mock_settings, mock_client_cls, mock_get_token):
        """Technical 'no context' message from RAG should not be treated as a valid result."""
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10
        mock_client_cls.return_value.__enter__.return_value.post.return_value = _mock_post_ok(
            {"response": "No relevant context found for the query."}
        )
        results = search_knowledge("printer issue")
        assert results == []

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_successful_search_results_list(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10
        mock_client_cls.return_value.__enter__.return_value.post.return_value = _mock_post_ok(
            {"results": ["Snippet one", "Snippet two"]}
        )
        results = search_knowledge("test query")
        assert results == ["Snippet one", "Snippet two"]

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_http_error_returns_empty(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock(status_code=404)
        )
        results = search_knowledge("test")
        assert results == []

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_timeout_returns_empty(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")
        results = search_knowledge("test")
        assert results == []

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_empty_response(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10
        mock_client_cls.return_value.__enter__.return_value.post.return_value = _mock_post_ok({"response": ""})
        results = search_knowledge("test")
        assert results == []

    def test_empty_query_returns_empty(self, mock_get_token):
        results = search_knowledge("")
        assert results == []

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_query_url_includes_api_prefix(self, mock_settings, mock_client_cls, mock_get_token):
        """When rag_api_prefix is set, /query URL must include it (no double slash)."""
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid"]
        mock_settings.rag_api_prefix = "/api"
        mock_settings.rag_timeout_budget = 10

        client = mock_client_cls.return_value.__enter__.return_value
        client.post.return_value = _mock_post_ok({"response": "ok doc"})

        results = search_knowledge("printer issue")
        assert results == ["ok doc"]

        call_url = client.post.call_args[0][0]
        assert call_url == "http://rag:9621/api/query"

    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_mode_cascade_uses_second_mode_on_empty(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_api_key = "sk-key"
        mock_settings.rag_response_type = "Multiple Paragraphs"
        mock_settings.rag_top_k = 10
        mock_settings.rag_mode_list = ["hybrid", "local"]
        mock_settings.rag_api_prefix = ""
        mock_settings.rag_timeout_budget = 10

        client = mock_client_cls.return_value.__enter__.return_value
        client.post.side_effect = [
            _mock_post_ok({"response": "No relevant context found for the query."}),
            _mock_post_ok({"response": "Found on local"}),
        ]

        results = search_knowledge("printer issue")
        assert results == ["Found on local"]
