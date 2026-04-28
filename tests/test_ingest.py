"""Tests for nodes/ingest.ingest_event — Jira issue loading and conversation history."""
import pytest
from unittest.mock import patch
import app.services.jira_mcp as jira_mcp
from app.nodes.ingest import (
    _positive_resolution_detected,
    _already_escalated_in_history,
    _already_resolved_in_history,
)


class TestIngestEvent:
    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_normal_case_populates_state(self, mock_settings, mock_get_issue, base_state, sample_jira_issue):
        mock_settings.bot_username = "Agent"
        # support_username_set is lowercased at config level; business rule
        # is escalation is tied to support role/usernames, not any assignee.
        mock_settings.support_username_set = {"support"}
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = sample_jira_issue

        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)

        assert result["issue_summary"] == "Принтер HP не печатает"
        assert result["issue_description"] == "После обновления драйверов принтер перестал печатать."
        assert result["issue_status"] == "Open"
        assert result["issue_assignee"] == "Admin"
        assert result["issue_priority"] == "High"
        assert result["escalated"] is False

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_bot_comment_gets_assistant_role(self, mock_settings, mock_get_issue, base_state, sample_jira_issue):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
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
        """When there are no user-side entries in history, empty user_message falls back to issue summary."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        # No description (so no Reporter entry) and only a bot comment — forces the summary fallback path.
        issue_summary_only = {
            **sample_jira_issue,
            "description": "",
            "comments": [
                {"author": "Agent", "body": "Попробуйте перезагрузить.", "created": ""},
            ],
        }
        mock_get_issue.return_value = issue_summary_only

        state = {
            "ticket_id": "TEST-42",
            "user_message": "",
            "is_first_message": True,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert "Принтер HP не печатает" in result["user_message"]

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_empty_user_message_prefers_latest_user_comment(self, mock_settings, mock_get_issue, sample_jira_issue):
        """When user comments exist, empty user_message is filled from the latest one (not summary)."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = sample_jira_issue

        state = {
            "ticket_id": "TEST-42",
            "user_message": "",
            "is_first_message": False,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        # Latest user comment is "Помогите пожалуйста" from Telegram.
        # Note: is_first_message=False triggers echo guard because last comment is from bot — so
        # use is_first_message=True to skip the echo guard for this assertion.
        state2 = {**state, "is_first_message": True}
        result2 = ingest_event(state2)
        assert "Помогите пожалуйста" in result2["user_message"]

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_short_message_enriched_with_description(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
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
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_get_issue.return_value = {}

        from app.nodes.ingest import ingest_event
        result = ingest_event(base_state)
        # State should be returned unchanged
        assert result is base_state

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_get_issue_raises_exception(self, mock_settings, mock_get_issue, base_state):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
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
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
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
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = sample_jira_issue

        state = {"ticket_id": "TEST-42", "user_message": "test",
                 "is_first_message": True, "conversation_history": []}

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        # With empty bot_username, all comments should be "user" role
        for entry in result["conversation_history"]:
            assert entry["role"] == "user"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_mcp_account_name_gets_assistant_role(self, mock_settings, mock_get_issue):
        """Comments from the auto-detected MCP account should get assistant role."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"

        jira_mcp._mcp_account_name = "admin"
        mock_get_issue.return_value = {
            "issue_key": "T-3",
            "summary": "Help",
            "description": "Desc",
            "status": "Open",
            "assignee": "",
            "priority": "",
            "created": "",
            "updated": "",
            "comments": [
                {"author": "Telegram", "body": "Help me", "created": ""},
                {"author": "Admin", "body": "Bot response via MCP", "created": ""},
            ],
        }

        from app.nodes.ingest import ingest_event
        state = {"ticket_id": "T-3", "user_message": "Help", "is_first_message": True, "conversation_history": []}
        result = ingest_event(state)

        # Description + 2 comments = 3 entries
        assert len(result["conversation_history"]) == 3
        assert result["conversation_history"][1]["role"] == "user"
        assert result["conversation_history"][2]["role"] == "assistant"

        jira_mcp._mcp_account_name = ""

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_explicit_escalation_request_from_user_message(self, mock_settings, mock_get_issue):
        """User typing 'переведи на специалиста' must trigger immediate escalation."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-100", "summary": "Printer", "description": "",
            "status": "Open", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [],
        }

        state = {
            "ticket_id": "T-100",
            "user_message": "переведи на специалиста",
            "is_first_message": False,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result["escalated"] is True
        assert result["escalation_reason"] == "user_requested_human"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_explicit_escalation_request_from_comment_history(self, mock_settings, mock_get_issue):
        """Escalation phrase in the latest user comment triggers escalation."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 10  # high so attempt_limit is not the reason
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-101", "summary": "Printer", "description": "",
            "status": "Open", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [
                {"author": "Telegram", "body": "Нужен живой человек", "created": ""},
            ],
        }

        state = {
            "ticket_id": "T-101",
            "user_message": "",
            "is_first_message": False,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result["escalated"] is True
        assert result["escalation_reason"] == "user_requested_human"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_no_escalation_phrase_not_triggered(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 10
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-102", "summary": "Printer", "description": "",
            "status": "Open", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [
                {"author": "Telegram", "body": "Не могу распечатать", "created": ""},
            ],
        }

        state = {
            "ticket_id": "T-102",
            "user_message": "Не могу распечатать",
            "is_first_message": False,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result.get("escalated") is False

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_escalation_request_case_insensitive(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 10
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-103", "summary": "Printer", "description": "",
            "status": "Open", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [],
        }

        state = {
            "ticket_id": "T-103",
            "user_message": "ПЕРЕВЕДИ НА СПЕЦИАЛИСТА пожалуйста",
            "is_first_message": True,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result["escalated"] is True
        assert result["escalation_reason"] == "user_requested_human"

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_support_comment_gets_support_role(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        # support_username_set stored lowercased; match works case-insensitively
        mock_settings.support_username_set = {"admin"}
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-2",
            "summary": "Help",
            "description": "",
            "status": "Open",
            "assignee": "",
            "priority": "",
            "created": "",
            "updated": "",
            "comments": [{"author": "Admin", "body": "Берём в работу", "created": ""}],
        }

        from app.nodes.ingest import ingest_event
        state = {"ticket_id": "T-2", "user_message": "Help", "is_first_message": True, "conversation_history": []}
        result = ingest_event(state)
        assert result["conversation_history"][0]["role"] == "support"


class TestPositiveResolutionDetected:
    def test_pomoglo(self):
        assert _positive_resolution_detected("помогло") is True

    def test_spasibo_pomoglo(self):
        assert _positive_resolution_detected("спасибо, помогло!") is True

    def test_zarabotalo(self):
        assert _positive_resolution_detected("Всё заработало, спасибо") is True

    def test_mozhno_zakryt(self):
        assert _positive_resolution_detected("можно закрыть") is True

    def test_vopros_reshen(self):
        assert _positive_resolution_detected("вопрос решён") is True

    def test_not_triggered_by_unrelated(self):
        assert _positive_resolution_detected("принтер не работает") is False

    def test_empty_string(self):
        assert _positive_resolution_detected("") is False

    def test_none(self):
        assert _positive_resolution_detected(None) is False

    def test_case_insensitive(self):
        assert _positive_resolution_detected("ПОМОГЛО") is True


class TestAlreadyEscalatedInHistory:
    @patch("app.nodes.ingest.settings")
    def test_detects_escalation_message(self, mock_settings):
        mock_settings.escalation_message_template = (
            "Ваше обращение передано специалисту технической поддержки.\n\n"
            "Причина: {reason}\nНомер обращения: {ticket_id}"
        )
        history = [
            {"role": "user", "author": "Telegram", "body": "Help"},
            {"role": "assistant", "author": "Agent",
             "body": "Ваше обращение передано специалисту технической поддержки.\n\nПричина: test\nНомер обращения: T-1"},
        ]
        assert _already_escalated_in_history(history) is True

    @patch("app.nodes.ingest.settings")
    def test_no_escalation_message(self, mock_settings):
        mock_settings.escalation_message_template = "Ваше обращение передано\n{reason}\n{ticket_id}"
        history = [
            {"role": "user", "author": "Telegram", "body": "Help"},
            {"role": "assistant", "author": "Agent", "body": "Попробуйте перезагрузить."},
        ]
        assert _already_escalated_in_history(history) is False

    @patch("app.nodes.ingest.settings")
    def test_empty_history(self, mock_settings):
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        assert _already_escalated_in_history([]) is False

    @patch("app.nodes.ingest.settings")
    def test_user_message_with_same_text_ignored(self, mock_settings):
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        history = [
            {"role": "user", "author": "Telegram", "body": "Передано кому-то"},
        ]
        assert _already_escalated_in_history(history) is False


class TestAlreadyResolvedInHistory:
    @patch("app.nodes.ingest.settings")
    def test_detects_resolution_message(self, mock_settings):
        mock_settings.resolution_message_template = "Рад помочь! Если будут ещё вопросы — обращайтесь."
        history = [
            {"role": "user", "author": "Telegram", "body": "помогло"},
            {"role": "assistant", "author": "Agent",
             "body": "Рад помочь! Если будут ещё вопросы — обращайтесь."},
        ]
        assert _already_resolved_in_history(history) is True

    @patch("app.nodes.ingest.settings")
    def test_no_resolution_message(self, mock_settings):
        mock_settings.resolution_message_template = "Рад помочь!"
        history = [
            {"role": "assistant", "author": "Agent", "body": "Попробуйте перезагрузить."},
        ]
        assert _already_resolved_in_history(history) is False

    @patch("app.nodes.ingest.settings")
    def test_empty_history(self, mock_settings):
        mock_settings.resolution_message_template = "Рад помочь!"
        assert _already_resolved_in_history([]) is False


class TestIngestResolution:
    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_positive_feedback_sets_resolved(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-200", "summary": "Printer", "description": "",
            "status": "In Progress", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [
                {"author": "Telegram", "body": "Не печатает", "created": ""},
                {"author": "Agent", "body": "Перезагрузите.", "created": ""},
                {"author": "Telegram", "body": "помогло, спасибо", "created": ""},
            ],
        }

        state = {
            "ticket_id": "T-200",
            "user_message": "помогло, спасибо",
            "is_first_message": False,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result.get("resolved") is True

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_positive_feedback_not_triggered_on_first_message(self, mock_settings, mock_get_issue):
        """'помогло' on a fresh ticket (no bot replies yet) should NOT resolve."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = "Передано\n{reason}\n{ticket_id}"
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-201", "summary": "помогло", "description": "",
            "status": "Open", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [],
        }

        state = {
            "ticket_id": "T-201",
            "user_message": "помогло",
            "is_first_message": True,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result.get("resolved") is not True

    @patch("app.nodes.ingest.get_issue")
    @patch("app.nodes.ingest.settings")
    def test_already_escalated_skips(self, mock_settings, mock_get_issue):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.escalation_status_set = set()
        mock_settings.max_self_help_attempts = 3
        mock_settings.escalation_message_template = (
            "Ваше обращение передано специалисту технической поддержки.\n\n"
            "Причина: {reason}\nНомер: {ticket_id}"
        )
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_get_issue.return_value = {
            "issue_key": "T-300", "summary": "Printer", "description": "",
            "status": "Open", "assignee": "", "priority": "",
            "created": "", "updated": "",
            "comments": [
                {"author": "Telegram", "body": "Не работает", "created": ""},
                {"author": "Agent", "body": "Ваше обращение передано специалисту технической поддержки.\n\nПричина: test\nНомер: T-300", "created": ""},
                {"author": "Telegram", "body": "Ты тут?", "created": ""},
            ],
        }

        state = {
            "ticket_id": "T-300",
            "user_message": "Ты тут?",
            "is_first_message": False,
            "conversation_history": [],
        }

        from app.nodes.ingest import ingest_event
        result = ingest_event(state)
        assert result.get("skip") is True
        assert result.get("resolution") == "skipped_already_escalated"
