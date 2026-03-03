"""Tests for nodes/post_comment.post_comment_node — Jira comment posting."""
import pytest
from unittest.mock import patch
from app.services.jira_mcp import MCPError
from app.nodes.post_comment import post_comment_node


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
