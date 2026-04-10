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
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_added_from_bot_is_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "comment_added") is False

    @patch("app.main.settings")
    def test_comment_from_user_passes(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "Telegram"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_comment_from_admin_passes(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "Administrator"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_comment_without_author_filtered_when_bot_set(self, mock_settings):
        """Comment with no author is filtered when bot_username is set (prevents loop)."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_with_empty_author_filtered_when_bot_set(self, mock_settings):
        """Comment with empty author is filtered when bot_username is set."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": ""}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_bot_username_empty_allows_all_comments(self, mock_settings):
        """If bot_username is not configured, all comments pass through."""
        mock_settings.bot_username = ""
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_bot_filter_exact_match_only(self, mock_settings):
        """Should not filter partial matches."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "AgentSmith"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_bot_filter_case_sensitive(self, mock_settings):
        """Bot detection is case-sensitive."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "agent"}
        assert _validate_event(payload, "comment_created") is True

    @patch("app.main.settings")
    def test_issue_created_ignores_bot_check(self, mock_settings):
        """issue_created events should not check author."""
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "Agent"}
        assert _validate_event(payload, "issue_created") is True

    @patch("app.main.settings")
    def test_comment_from_support_is_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = {"Admin"}
        payload = {"issue_key": "TEST-1", "author": "Admin"}
        assert _validate_event(payload, "comment_created") is False

    @patch("app.main.settings")
    def test_comment_with_non_user_role_is_filtered(self, mock_settings):
        mock_settings.bot_username = "Agent"
        mock_settings.support_username_set = set()
        payload = {"issue_key": "TEST-1", "author": "Telegram", "role": "support"}
        assert _validate_event(payload, "comment_created") is False
