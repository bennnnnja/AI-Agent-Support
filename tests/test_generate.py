"""Tests for nodes/generate — response generation and formatting helpers."""
import pytest
from unittest.mock import patch, MagicMock
from app.nodes.generate import (
    generate_response,
    _format_conversation_history,
    _format_rag_results,
)


class TestFormatConversationHistory:
    def test_empty_list(self):
        assert _format_conversation_history([]) == "Нет предыдущей переписки"

    def test_single_entry(self):
        history = [{"role": "user", "author": "Telegram", "body": "Help me"}]
        result = _format_conversation_history(history)
        assert "[USER] Telegram: Help me" in result

    def test_multiple_entries(self):
        history = [
            {"role": "user", "author": "Telegram", "body": "Problem"},
            {"role": "assistant", "author": "Agent", "body": "Try restarting"},
            {"role": "user", "author": "Telegram", "body": "Still broken"},
        ]
        result = _format_conversation_history(history)
        lines = result.split("\n")
        assert len(lines) == 3
        assert "[USER] Telegram: Problem" in lines[0]
        assert "[ASSISTANT] Agent: Try restarting" in lines[1]
        assert "[USER] Telegram: Still broken" in lines[2]

    def test_missing_author(self):
        history = [{"role": "user", "author": "", "body": "Anonymous msg"}]
        result = _format_conversation_history(history)
        assert "[USER]" in result

    def test_missing_fields(self):
        history = [{}]
        result = _format_conversation_history(history)
        assert "[USER]" in result  # default role is "user"


class TestFormatRagResults:
    def test_empty_list(self):
        assert _format_rag_results([]) == "Документация не найдена"

    def test_single_result(self):
        result = _format_rag_results(["Some documentation text"])
        assert result == "Some documentation text"

    def test_multiple_results(self):
        result = _format_rag_results(["Doc 1", "Doc 2", "Doc 3"])
        assert result == "Doc 1\n---\nDoc 2\n---\nDoc 3"


class TestGenerateResponse:
    @patch("app.nodes.generate.get_llm")
    def test_normal_generation(self, mock_get_llm, base_state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response(
            "Попробуйте перезагрузить принтер."
        )
        base_state["rag_results"] = ["Инструкция: перезагрузите принтер"]
        base_state["category"] = "tech_support"

        result = generate_response(base_state)
        assert result["response"] == "Попробуйте перезагрузить принтер."

    @patch("app.nodes.generate.get_llm")
    def test_llm_exception_returns_fallback(self, mock_get_llm, base_state):
        mock_get_llm.return_value.invoke.side_effect = Exception("Ollama timeout")

        result = generate_response(base_state)
        assert result["response"] == "Ошибка при генерации ответа"

    @patch("app.nodes.generate.get_llm")
    def test_prompt_includes_issue_context(self, mock_get_llm, base_state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("ok")
        base_state["issue_status"] = "In Progress"
        base_state["issue_priority"] = "Critical"
        base_state["issue_assignee"] = "Admin"

        generate_response(base_state)
        prompt = mock_get_llm.return_value.invoke.call_args[0][0]
        assert "In Progress" in prompt
        assert "Critical" in prompt
        assert "Admin" in prompt

    @patch("app.nodes.generate.get_llm")
    def test_prompt_includes_rag_results(self, mock_get_llm, base_state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("ok")
        base_state["rag_results"] = ["Инструкция по принтеру HP"]

        generate_response(base_state)
        prompt = mock_get_llm.return_value.invoke.call_args[0][0]
        assert "Инструкция по принтеру HP" in prompt

    @patch("app.nodes.generate.get_llm")
    def test_no_rag_results_shows_placeholder(self, mock_get_llm, base_state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("ok")
        base_state["rag_results"] = []

        generate_response(base_state)
        prompt = mock_get_llm.return_value.invoke.call_args[0][0]
        assert "Документация не найдена" in prompt

    @patch("app.nodes.generate.get_llm")
    def test_response_without_content_attr(self, mock_get_llm, base_state):
        """Handle LLM response that doesn't have .content attribute."""
        class FakeResponse:
            """LLM response without .content — str() fallback."""
            def __str__(self):
                return "Fallback string response"

        mock_get_llm.return_value.invoke.return_value = FakeResponse()

        result = generate_response(base_state)
        assert "Fallback string response" in result["response"]

    @patch("app.nodes.generate.get_llm")
    def test_preserves_state_fields(self, mock_get_llm, base_state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("answer")
        result = generate_response(base_state)
        assert result["ticket_id"] == "TEST-1"
        assert result["user_message"] == "Принтер не печатает"
