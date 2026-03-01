"""Tests for services/rag — RAG API integration."""
import pytest
from unittest.mock import patch, MagicMock
import httpx


class TestGetToken:
    @patch("app.services.rag.settings")
    @patch("app.services.rag.httpx.Client")
    def test_successful_login(self, mock_client_cls, mock_settings):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_settings.rag_username = "user"
        mock_settings.rag_api_key = "pass"

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "tok123"}
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        from app.services.rag import _get_token
        token = _get_token()
        assert token == "tok123"


class TestSearchKnowledge:
    @patch("app.services.rag._get_token")
    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_successful_search(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_get_token.return_value = "tok"

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Relevant documentation text"}
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        from app.services.rag import search_knowledge
        results = search_knowledge("printer issue")
        assert results == ["Relevant documentation text"]

    @patch("app.services.rag._get_token")
    @patch("app.services.rag.settings")
    def test_login_failure_returns_empty(self, mock_settings, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_get_token.side_effect = Exception("Login failed")

        from app.services.rag import search_knowledge
        results = search_knowledge("test")
        assert results == []

    @patch("app.services.rag._get_token")
    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_timeout_returns_empty(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_get_token.return_value = "tok"

        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")

        from app.services.rag import search_knowledge
        results = search_knowledge("test")
        assert results == []

    @patch("app.services.rag._get_token")
    @patch("app.services.rag.httpx.Client")
    @patch("app.services.rag.settings")
    def test_empty_response(self, mock_settings, mock_client_cls, mock_get_token):
        mock_settings.rag_api_url = "http://rag:9621"
        mock_get_token.return_value = "tok"

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": ""}
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        from app.services.rag import search_knowledge
        results = search_knowledge("test")
        assert results == []
