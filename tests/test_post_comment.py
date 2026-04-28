"""Tests for nodes/post_comment.post_comment_node — Jira comment posting."""
import pytest
from unittest.mock import patch
from app.services.jira_mcp import MCPError
from app.nodes.post_comment import post_comment_node, post_escalation_node, post_resolution_node


@pytest.fixture
def comment_state():
    return {
        "ticket_id": "TEST-1",
        "response": "Попробуйте перезагрузить принтер.",
        "resolution": None,
    }


class TestPostCommentNode:
    @patch("app.nodes.post_comment.add_comment")
    def test_successful_post(self, mock_add, comment_state):
        mock_add.return_value = "Comment added successfully"
        result = post_comment_node(comment_state)
        assert result["resolution"] == "comment_posted"
        mock_add.assert_called_once_with("TEST-1", "Попробуйте перезагрузить принтер.")

    def test_no_ticket_id(self):
        state = {"ticket_id": "", "response": "answer", "resolution": None}
        result = post_comment_node(state)
        assert result["resolution"] is None  # unchanged

    def test_missing_ticket_id(self):
        state = {"response": "answer", "resolution": None}
        result = post_comment_node(state)
        assert result["resolution"] is None

    def test_no_response(self):
        state = {"ticket_id": "TEST-1", "response": "", "resolution": None}
        result = post_comment_node(state)
        assert result["resolution"] is None

    def test_missing_response(self):
        state = {"ticket_id": "TEST-1", "resolution": None}
        result = post_comment_node(state)
        assert result["resolution"] is None

    @patch("app.nodes.post_comment.add_comment")
    def test_long_response_trimmed(self, mock_add, comment_state):
        mock_add.return_value = "OK"
        comment_state["response"] = "A" * 35000
        result = post_comment_node(comment_state)

        posted_text = mock_add.call_args[0][1]
        assert len(posted_text) < 31000
        assert "обрезано" in posted_text

    @patch("app.nodes.post_comment.add_comment")
    def test_mcp_error(self, mock_add, comment_state):
        mock_add.side_effect = MCPError("Jira API returned 403")
        result = post_comment_node(comment_state)
        assert "error_posting_comment" in result["resolution"]
        assert "403" in result["resolution"]

    @patch("app.nodes.post_comment.add_comment")
    def test_generic_exception(self, mock_add, comment_state):
        mock_add.side_effect = RuntimeError("Connection lost")
        result = post_comment_node(comment_state)
        assert "error_posting_comment" in result["resolution"]

    @patch("app.nodes.post_comment.add_comment")
    def test_empty_mcp_response(self, mock_add, comment_state):
        mock_add.return_value = ""
        result = post_comment_node(comment_state)
        assert result["resolution"] == "warning_empty_mcp_response"

    @patch("app.nodes.post_comment.add_comment")
    def test_none_mcp_response(self, mock_add, comment_state):
        mock_add.return_value = None
        result = post_comment_node(comment_state)
        assert result["resolution"] == "warning_empty_mcp_response"

    @patch("app.nodes.post_comment.add_comment")
    def test_response_exactly_at_limit_not_trimmed(self, mock_add, comment_state):
        mock_add.return_value = "OK"
        comment_state["response"] = "A" * 30000
        post_comment_node(comment_state)
        posted_text = mock_add.call_args[0][1]
        assert posted_text == "A" * 30000  # not trimmed


class TestPostCommentTransition:
    """First-message replies must schedule an In Progress transition."""

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_first_message_schedules_in_progress(self, mock_settings, mock_add):
        mock_settings.status_in_progress = "In Progress"
        mock_add.return_value = "ok"
        state = {
            "ticket_id": "T-1",
            "response": "answer",
            "is_first_message": True,
            "issue_status": "Open",
            "resolution": None,
        }
        result = post_comment_node(state)
        assert result["transition_to_status"] == "In Progress"
        assert result["resolution"] == "comment_posted"

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_non_first_message_does_not_transition(self, mock_settings, mock_add):
        mock_settings.status_in_progress = "In Progress"
        mock_add.return_value = "ok"
        state = {
            "ticket_id": "T-1",
            "response": "answer",
            "is_first_message": False,
            "issue_status": "Open",
            "resolution": None,
        }
        result = post_comment_node(state)
        assert "transition_to_status" not in result

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_already_in_progress_not_retransitioned(self, mock_settings, mock_add):
        mock_settings.status_in_progress = "In Progress"
        mock_add.return_value = "ok"
        state = {
            "ticket_id": "T-1",
            "response": "answer",
            "is_first_message": True,
            "issue_status": "in progress",  # case-insensitive match
            "resolution": None,
        }
        result = post_comment_node(state)
        assert "transition_to_status" not in result

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_empty_status_in_progress_disables_transition(self, mock_settings, mock_add):
        mock_settings.status_in_progress = ""
        mock_add.return_value = "ok"
        state = {
            "ticket_id": "T-1",
            "response": "answer",
            "is_first_message": True,
            "issue_status": "Open",
            "resolution": None,
        }
        result = post_comment_node(state)
        assert "transition_to_status" not in result


class TestPostEscalationTransition:
    """Escalation posts must schedule escalated-status + reassignment."""

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_escalation_sets_transition_and_reassign(self, mock_settings, mock_add):
        mock_settings.status_escalated = "Escalated"
        mock_settings.escalation_assignee = "support_user"
        mock_settings.escalation_message_template = (
            "Передано. Причина: {reason}. Тикет: {ticket_id}"
        )
        mock_add.return_value = "ok"
        state = {
            "ticket_id": "T-7",
            "escalation_reason": "user_requested_human",
            "resolution": None,
        }
        result = post_escalation_node(state)
        assert result["transition_to_status"] == "Escalated"
        assert result["reassign_to"] == "support_user"
        assert result["resolution"] == "escalation_posted"

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_escalation_without_assignee(self, mock_settings, mock_add):
        mock_settings.status_escalated = "Escalated"
        mock_settings.escalation_assignee = ""
        mock_settings.escalation_message_template = "{reason} {ticket_id}"
        mock_add.return_value = "ok"
        state = {"ticket_id": "T-8", "escalation_reason": "attempt_limit=3"}
        result = post_escalation_node(state)
        assert result["transition_to_status"] == "Escalated"
        assert "reassign_to" not in result

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_escalation_without_status_only_reassigns(self, mock_settings, mock_add):
        mock_settings.status_escalated = ""
        mock_settings.escalation_assignee = "support_user"
        mock_settings.escalation_message_template = "{reason} {ticket_id}"
        mock_add.return_value = "ok"
        state = {"ticket_id": "T-9", "escalation_reason": ""}
        result = post_escalation_node(state)
        assert "transition_to_status" not in result
        assert result["reassign_to"] == "support_user"


class TestPostResolutionNode:
    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_successful_resolution(self, mock_settings, mock_add):
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_settings.status_resolved = "Done"
        mock_add.return_value = "ok"
        state = {"ticket_id": "T-50", "resolution": None}
        result = post_resolution_node(state)
        assert result["resolution"] == "resolved_posted"
        assert result["transition_to_status"] == "Done"
        mock_add.assert_called_once_with("T-50", "Рад помочь!")

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_resolution_without_status(self, mock_settings, mock_add):
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_settings.status_resolved = ""
        mock_add.return_value = "ok"
        state = {"ticket_id": "T-51", "resolution": None}
        result = post_resolution_node(state)
        assert result["resolution"] == "resolved_posted"
        assert "transition_to_status" not in result

    def test_no_ticket_id(self):
        state = {"ticket_id": "", "resolution": None}
        result = post_resolution_node(state)
        assert result["resolution"] is None

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_mcp_error(self, mock_settings, mock_add):
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_settings.status_resolved = "Done"
        mock_add.side_effect = MCPError("Jira API 500")
        state = {"ticket_id": "T-52", "resolution": None}
        result = post_resolution_node(state)
        assert "error_posting_resolution" in result["resolution"]

    @patch("app.nodes.post_comment.add_comment")
    @patch("app.nodes.post_comment.settings")
    def test_empty_mcp_response(self, mock_settings, mock_add):
        mock_settings.resolution_message_template = "Рад помочь!"
        mock_settings.status_resolved = "Done"
        mock_add.return_value = ""
        state = {"ticket_id": "T-53", "resolution": None}
        result = post_resolution_node(state)
        assert result["resolution"] == "resolved_posted_empty_mcp"
