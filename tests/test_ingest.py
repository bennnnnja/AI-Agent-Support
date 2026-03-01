"""Tests for nodes/ingest.ingest_event — Jira issue loading and conversation history."""
import pytest
from unittest.mock import patch


class TestIngestEvent:
    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_normal_case_populates_state(self, mock_settings, mock_get_issue, base_state, sample_jira_issue):
        mock_settings.bot_username = "Agent"
        mock_get_issue.return_value = sample_jira_issue

        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)

        assert result["issue_summary"] == "Принтер HP не печатает"
        assert result["issue_description"] == "После обновления драйверов принтер перестал печатать."
        assert result["issue_status"] == "Open"
        assert result["issue_assignee"] == "Admin"
        assert result["issue_priority"] == "High"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_bot_comment_gets_assistant_role(self, mock_settings, mock_get_issue, base_state, sample_jira_issue):
        mock_settings.bot_username = "Agent"
        mock_get_issue.return_value = sample_jira_issue

        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)

        history = result["conversation_history"]
        # description entry + 2 comments = 3
        assert len(history) == 3
        # First is description (role=user)
        assert history[0]["role"] == "user"
        assert history[0]["author"] == "Reporter"
        # Comment from Telegram = user
        assert history[1]["role"] == "user"
        assert history[1]["author"] == "Telegram"
        # Comment from Agent = assistant
        assert history[2]["role"] == "assistant"
        assert history[2]["author"] == "Agent"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_empty_user_message_filled_from_summary(self, mock_settings, mock_get_issue, sample_jira_issue):
        mock_settings.bot_username = "Agent"
        mock_get_issue.return_value = sample_jira_issue

        state = {
            "ticket_id": "TEST-42",
            "user_message": "",
            "is_first_message": True,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        # Should be enriched with summary + description (since summary alone is <10 chars? No, it's longer)
        assert "Принтер HP не печатает" in result["user_message"]

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_short_message_enriched_with_description(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_get_issue.return_value = {
            "issue_key": "T-1",
            "summary": "Bug",
            "description": "Detailed description of the bug",
            "status": "", "assignee": "", "priority": "",
            "created": "", "updated": "",
        }

        state = {
            "ticket_id": "T-1",
            "user_message": "Bug",  # len=3, <10
            "is_first_message": True,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert "Detailed description" in result["user_message"]

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_get_issue_returns_empty_dict(self, mock_settings, mock_get_issue, base_state):
        mock_settings.bot_username = "Agent"
        mock_get_issue.return_value = {}

        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)
        # State should be returned unchanged
        assert result is base_state

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_get_issue_raises_exception(self, mock_settings, mock_get_issue, base_state):
        mock_settings.bot_username = "Agent"
        mock_get_issue.side_effect = Exception("MCP server down")

        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)
        assert result is base_state

    def test_no_ticket_id_returns_state(self, base_state):
        base_state["ticket_id"] = ""
        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)
        assert result is base_state

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_no_description_no_description_entry(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_get_issue.return_value = {
            "issue_key": "T-1",
            "summary": "Short summary here",
            "description": "",
            "status": "", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [{"author": "Telegram", "body": "Help", "created": ""}],
        }

        state = {"ticket_id": "T-1", "user_message": "Short summary here",
                 "is_first_message": True, "conversation_history": []}

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        # No description entry, only 1 comment
        assert len(result["conversation_history"]) == 1
        assert result["conversation_history"][0]["author"] == "Telegram"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_bot_username_empty_all_comments_are_user(self, mock_settings, mock_get_issue, sample_jira_issue):
        mock_settings.bot_username = ""
        mock_get_issue.return_value = sample_jira_issue

        state = {"ticket_id": "TEST-42", "user_message": "test",
                 "is_first_message": True, "conversation_history": []}

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        # With empty bot_username, all comments should be "user" role
        for entry in result["conversation_history"]:
            assert entry["role"] == "user"
