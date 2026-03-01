"""Tests for nodes/classify.classify_request — LLM classification."""
import pytest
from unittest.mock import patch, MagicMock
from app.nodes.classify import classify_request


@pytest.fixture
def state():
    return {
        "ticket_id": "TEST-1",
        "user_message": "Принтер не печатает",
        "category": None,
    }


class TestClassifyRequest:
    @patch("app.nodes.classify.get_llm")
    def test_tech_support(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("tech_support")
        result = classify_request(state)
        assert result["category"] == "tech_support"

    @patch("app.nodes.classify.get_llm")
    def test_off_topic(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("off_topic")
        result = classify_request(state)
        assert result["category"] == "off_topic"

    @patch("app.nodes.classify.get_llm")
    def test_unclear(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("unclear")
        result = classify_request(state)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_invalid_category_defaults_to_unclear(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("random_garbage")
        result = classify_request(state)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_strips_whitespace(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("  tech_support \n")
        result = classify_request(state)
        assert result["category"] == "tech_support"

    @patch("app.nodes.classify.get_llm")
    def test_case_insensitive(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("Tech_Support")
        result = classify_request(state)
        assert result["category"] == "tech_support"

    def test_empty_message_returns_unclear(self):
        state = {"user_message": "", "category": None}
        result = classify_request(state)
        assert result["category"] == "unclear"

    def test_missing_message_returns_unclear(self):
        state = {"category": None}
        result = classify_request(state)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_llm_exception_returns_unclear(self, mock_get_llm, state):
        mock_get_llm.return_value.invoke.side_effect = Exception("Connection refused")
        result = classify_request(state)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_message_truncated_to_500_chars(self, mock_get_llm, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("tech_support")
        long_msg = "x" * 1000
        state = {"user_message": long_msg, "category": None}
        classify_request(state)

        # Check that the prompt passed to LLM contains truncated message
        call_args = mock_get_llm.return_value.invoke.call_args[0][0]
        # The message in the prompt should be at most 500 chars of the user's text
        assert "x" * 501 not in call_args

    @patch("app.nodes.classify.get_llm")
    def test_preserves_other_state_fields(self, mock_get_llm, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("tech_support")
        state = {"user_message": "test", "ticket_id": "X-1", "category": None, "response": "old"}
        result = classify_request(state)
        assert result["ticket_id"] == "X-1"
        assert result["response"] == "old"
