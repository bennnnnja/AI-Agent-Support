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
    def test_rag_only_response_without_llm_call(self, mock_get_llm, base_state):
        """If RAG returned results, response should be built directly from them and LLM must not be invoked."""
        base_state["rag_results"] = ["Инструкция: перезагрузите принтер", "Дополнительный шаг"]

        result = generate_response(base_state)

        # LLM не должен вызываться в RAG-only режиме
        mock_get_llm.assert_not_called()
        # Ответ — это форматированный текст из RAG
        assert "Инструкция: перезагрузите принтер" in result["response"]
        assert "Дополнительный шаг" in result["response"]

    @patch("app.nodes.generate.get_llm")
    def test_fallback_llm_used_when_no_rag(self, mock_get_llm, base_state, mock_llm_response):
        """When RAG has no results, use fallback LLM with safe generic advice."""
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("Общие шаги диагностики.")
        base_state["rag_results"] = []

        result = generate_response(base_state)

        assert result["response"] == "Общие шаги диагностики."
        prompt = mock_get_llm.return_value.invoke.call_args[0][0]
        # Проверяем, что в промпте есть контекст задачи и вопрос пользователя
        assert base_state["user_message"] in prompt
        assert "Статус:" in prompt

    @patch("app.nodes.generate.get_llm")
    def test_llm_exception_returns_fallback(self, mock_get_llm, base_state):
        """If fallback LLM fails, return explicit error message."""
        mock_get_llm.return_value.invoke.side_effect = Exception("Ollama timeout")
        base_state["rag_results"] = []

        result = generate_response(base_state)
        assert result["response"] == "Ошибка при генерации ответа"

    @patch("app.nodes.generate.get_llm")
    def test_fallback_prompt_includes_issue_context(self, mock_get_llm, base_state, mock_llm_response):
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("ok")
        base_state["rag_results"] = []
        base_state["issue_status"] = "In Progress"
        base_state["issue_priority"] = "Critical"
        base_state["issue_assignee"] = "Admin"

        generate_response(base_state)
        prompt = mock_get_llm.return_value.invoke.call_args[0][0]
        assert "In Progress" in prompt
        assert "Critical" in prompt
        assert "Admin" in prompt

    @patch("app.nodes.generate.get_llm")
    def test_response_without_content_attr_in_fallback(self, mock_get_llm, base_state):
        """Handle LLM response that doesn't have .content attribute in fallback mode."""

        class FakeResponse:
            """LLM response without .content — str() fallback."""

            def __str__(self):
                return "Fallback string response"

        mock_get_llm.return_value.invoke.return_value = FakeResponse()
        base_state["rag_results"] = []

        result = generate_response(base_state)
        assert "Fallback string response" in result["response"]

    @patch("app.nodes.generate.get_llm")
    def test_preserves_state_fields(self, mock_get_llm, base_state, mock_llm_response):
        """generate_response should not mutate existing state fields."""
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("answer")
        base_state["rag_results"] = []
        result = generate_response(base_state)
        assert result["ticket_id"] == "TEST-1"
        assert result["user_message"] == "Принтер не печатает"

    def test_off_topic_returns_canned_response(self, base_state):
        base_state["category"] = "off_topic"
        result = generate_response(base_state)
        assert "не относится к технической поддержке" in result["response"]

    @patch("app.nodes.generate.get_llm")
    def test_off_topic_skips_llm(self, mock_get_llm, base_state):
        base_state["category"] = "off_topic"
        generate_response(base_state)
        mock_get_llm.assert_not_called()


class TestRagSynthesis:
    """Опциональный LLM-синтез поверх найденных RAG-результатов."""

    @patch("app.nodes.generate.settings")
    @patch("app.nodes.generate.get_llm")
    def test_rag_synthesis_uses_llm_when_flag_on(
        self, mock_get_llm, mock_settings, base_state, mock_llm_response
    ):
        mock_settings.rag_use_llm_synthesis = True
        mock_get_llm.return_value.invoke.return_value = mock_llm_response("Синтезированный ответ.")
        base_state["rag_results"] = ["raw doc 1", "raw doc 2"]
        base_state["issue_status"] = "Open"
        base_state["issue_priority"] = "High"

        result = generate_response(base_state)

        mock_get_llm.return_value.invoke.assert_called_once()
        prompt = mock_get_llm.return_value.invoke.call_args[0][0]
        # GENERATE_PROMPT включает блок ДОКУМЕНТАЦИЯ с raw rag-выводом
        assert "raw doc 1" in prompt
        assert "raw doc 2" in prompt
        assert "Open" in prompt
        assert result["response"] == "Синтезированный ответ."

    @patch("app.nodes.generate.settings")
    @patch("app.nodes.generate.get_llm")
    def test_rag_synthesis_fallback_on_llm_error(
        self, mock_get_llm, mock_settings, base_state
    ):
        """Если LLM падает — возвращаем сырой RAG (graceful fallback)."""
        mock_settings.rag_use_llm_synthesis = True
        mock_get_llm.return_value.invoke.side_effect = Exception("Ollama timeout")
        base_state["rag_results"] = ["Инструкция: перезагрузите принтер"]

        result = generate_response(base_state)
        assert "Инструкция: перезагрузите принтер" in result["response"]

    @patch("app.nodes.generate.settings")
    @patch("app.nodes.generate.get_llm")
    def test_rag_synthesis_skipped_when_flag_off(
        self, mock_get_llm, mock_settings, base_state
    ):
        """С флагом False (default) сохраняется текущее поведение — LLM не вызывается."""
        mock_settings.rag_use_llm_synthesis = False
        base_state["rag_results"] = ["Сырой RAG результат"]

        result = generate_response(base_state)
        mock_get_llm.assert_not_called()
        assert "Сырой RAG результат" in result["response"]
