"""Tests for nodes/classify.classify_request — LLM classification."""
import pytest
from unittest.mock import patch, MagicMock
from app.nodes.classify import classify_request, _is_conversation_followup


@pytest.fixture
def state():
    return {
        "ticket_id": "TEST-1",
        "user_message": "Принтер не печатает",
        "category": None,
    }


@pytest.fixture
def state_no_keywords():
    """State with a message that does NOT match any rule-based keyword."""
    return {
        "ticket_id": "TEST-1",
        "user_message": "Какая погода сегодня?",
        "category": None,
        "conversation_history": [],
    }


class TestRuleBasedClassify:
    def test_tech_keyword_match(self, state):
        result = classify_request(state)
        assert result["category"] == "tech_support"

    def test_no_keyword_falls_through(self):
        state = {"user_message": "Какая погода?", "category": None, "conversation_history": []}
        # Without LLM mock this would fail — but we just verify the rule doesn't fire
        with patch("app.nodes.classify.get_llm") as mock_llm:
            mock_resp = MagicMock()
            mock_resp.content = "off_topic"
            mock_llm.return_value.invoke.return_value = mock_resp
            result = classify_request(state)
            assert result["category"] == "off_topic"
            mock_llm.return_value.invoke.assert_called_once()


class TestLLMClassify:
    @patch("app.nodes.classify.get_llm")
    def test_tech_support(self, mock_get_llm, state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("tech_support")
        result = classify_request(state)
        assert result["category"] == "tech_support"

    @patch("app.nodes.classify.get_llm")
    def test_off_topic(self, mock_get_llm, state_no_keywords, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("off_topic")
        result = classify_request(state_no_keywords)
        assert result["category"] == "off_topic"

    @patch("app.nodes.classify.get_llm")
    def test_unclear(self, mock_get_llm, state_no_keywords, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("unclear")
        result = classify_request(state_no_keywords)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_invalid_category_defaults_to_unclear(self, mock_get_llm, state_no_keywords, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("random_garbage")
        result = classify_request(state_no_keywords)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_strips_whitespace(self, mock_get_llm, state_no_keywords, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("  tech_support \n")
        result = classify_request(state_no_keywords)
        assert result["category"] == "tech_support"

    @patch("app.nodes.classify.get_llm")
    def test_case_insensitive(self, mock_get_llm, state_no_keywords, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("Tech_Support")
        result = classify_request(state_no_keywords)
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
    def test_llm_exception_returns_unclear(self, mock_get_llm, state_no_keywords):
        mock_get_llm.return_value.invoke.side_effect = Exception("Connection refused")
        result = classify_request(state_no_keywords)
        assert result["category"] == "unclear"

    @patch("app.nodes.classify.get_llm")
    def test_message_truncated_to_500_chars(self, mock_get_llm, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("tech_support")
        long_msg = "x" * 1000
        state = {"user_message": long_msg, "category": None, "conversation_history": []}
        classify_request(state)

        call_args = mock_get_llm.return_value.invoke.call_args[0][0]
        assert "x" * 501 not in call_args

    @patch("app.nodes.classify.get_llm")
    def test_preserves_other_state_fields(self, mock_get_llm, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("tech_support")
        state = {
            "user_message": "Какой курс доллара?",
            "ticket_id": "X-1",
            "category": None,
            "response": "old",
            "conversation_history": [],
        }
        result = classify_request(state)
        assert result["ticket_id"] == "X-1"
        assert result["response"] == "old"


class TestConversationFollowup:
    """Follow-ups in an existing conversation with bot replies → tech_support."""

    def test_followup_detected(self):
        state = {
            "user_message": "не помогло",
            "category": None,
            "conversation_history": [
                {"role": "user", "body": "Принтер не печатает"},
                {"role": "assistant", "body": "Попробуйте перезагрузить."},
                {"role": "user", "body": "не помогло"},
            ],
        }
        result = classify_request(state)
        assert result["category"] == "tech_support"

    def test_followup_with_vague_message(self):
        state = {
            "user_message": "ок",
            "category": None,
            "conversation_history": [
                {"role": "user", "body": "Монитор мигает"},
                {"role": "assistant", "body": "Проверьте кабель."},
                {"role": "user", "body": "ок"},
            ],
        }
        result = classify_request(state)
        assert result["category"] == "tech_support"

    def test_no_followup_without_assistant(self):
        """First message without prior bot replies is NOT a follow-up."""
        assert not _is_conversation_followup({
            "conversation_history": [
                {"role": "user", "body": "Привет"},
            ],
        })

    def test_no_followup_empty_history(self):
        assert not _is_conversation_followup({
            "conversation_history": [],
        })

    def test_no_followup_no_history_key(self):
        assert not _is_conversation_followup({})

    def test_is_followup_with_assistant(self):
        assert _is_conversation_followup({
            "conversation_history": [
                {"role": "user", "body": "Проблема"},
                {"role": "assistant", "body": "Ответ"},
            ],
        })
