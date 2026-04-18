"""Tests for main._validate_event — event validation and bot comment filtering."""
import pytest
from unittest.mock import patch
from app.main import _validate_event


class TestValidateEvent:
    """Test event validation logic."""

    def test_valid_issue_created(self):
        payload = {"issue_key": "TEST-1"}
        assert _validate_event(payload, "issue_created") is True

    def test_valid_issue_updated(self):
        payload = {"issue_key": "TEST-1"}
        assert _validate_event(payload, "issue_updated") is True

    def test_missing_issue_key(self):
        payload = {"summary": "no key here"}
        assert _validate_event(payload, "issue_created") is False

    def test_empty_issue_key(self):
        payload = {"issue_key": ""}
        assert _validate_event(payload, "issue_created") is False

    def test_missing_event_type(self):
        payload = {"issue_key": "TEST-1"}
        assert _validate_event(payload, "") is False

    def test_none_event_type(self):
        payload = {"issue_key": "TEST-1"}
        assert _validate_event(payload, None) is False


class TestBotCommentFiltering:
    """Test bot's own comment detection to prevent infinite loops."""

    @patch("app.main.settings")
    def test_comment_from_bot_is_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_added_from_bot_is_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "comment_added") is False

    @patch("app.main.settings")
    def test_comment_from_user_passes(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Telegram"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_comment_from_admin_passes(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Administrator"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_comment_without_author_with_user_body_passes(self, mock_settings):
        """Comment with no author is ALLOWED if body does not look like bot output.

        This is the primary regression fix — the webhook gateway often strips
        author metadata, and user follow-ups must still be processed.
        """
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано специалисту"
        payload = {"issue_key": "TEST-1", "body": "не помогло, проблема осталась"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_comment_without_author_with_bot_like_body_filtered(self, mock_settings):
        """Comment with no author and bot-like body (escalation prefix) is filtered."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано специалисту технической поддержки."
        payload = {
            "issue_key": "TEST-1",
            "body": "Ваше обращение передано специалисту технической поддержки.\n\nПричина: ...",
        }
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_without_author_with_custom_marker_filtered(self, mock_settings):
        """Custom bot_comment_marker should filter bot-like comments."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = "[bot]"
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "body": "[bot] Автоматический ответ..."}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_empty_author_empty_body_passes(self, mock_settings):
        """Edge case: empty body and empty author — still allowed (we'll enrich via Jira)."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": ""}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_bot_username_empty_allows_all_comments(self, mock_settings):
        """If bot_username is not configured, all comments pass through."""
        mock_settings.bot_username = ""
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_bot_filter_exact_match_only(self, mock_settings):
        """Should not filter partial matches."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "AgentSmith"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_bot_filter_case_insensitive(self, mock_settings):
        """Bot detection is case-insensitive (fix for 'agent' vs 'Agent' mismatch)."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "agent"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_bot_filter_case_insensitive_uppercase(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "AGENT"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_issue_created_ignores_bot_check(self, mock_settings):
        """issue_created events should not check author."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "issue_created") is True

    @patch("app.main.settings")
    def test_comment_from_support_is_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        # support_username_set is lowercased at config level
        mock_settings.support_username_set = {"admin"}
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Admin"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_from_support_case_insensitive(self, mock_settings):
        """Support username match is case-insensitive."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = {"support_user"}
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "SUPPORT_USER"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_with_non_user_role_is_filtered(self, mock_settings):
        """When author is missing, a non-user role still filters the event."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "role": "support"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_with_non_user_source_is_filtered(self, mock_settings):
        """When author is missing, a non-user source still filters the event."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "source": "jira-automation"}
        assert _validate_event(payload, "comment_created") is False


class TestIssueUpdatedFiltering:
    """Test issue_updated event filtering."""

    @patch("app.main.settings")
    def test_update_from_bot_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "issue_updated") is False

    @patch("app.main.settings")
    def test_update_from_bot_case_insensitive(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "agent"}
        assert _validate_event(payload, "issue_updated") is False

    @patch("app.main.settings")
    def test_update_from_support_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = {"admin"}
        mock_settings.bot_comment_marker = ""
        mock_settings.escalation_message_template = "Ваше обращение передано"
        payload = {"issue_key": "TEST-1", "author": "Admin"}
        assert _validate_event(payload, "issue_updated") is False
