"""Tests for nodes/transition.transition_node — Jira status transitions + assignment."""
import pytest
from unittest.mock import patch

from app.nodes.transition import transition_node
from app.services.jira_mcp import MCPError


class TestTransitionNode:

    def test_noop_without_ticket_id(self):
        state = {"transition_to_status": "In Progress"}
        assert transition_node(state) is state

    def test_noop_without_targets(self):
        state = {"ticket_id": "T-1", "resolution": "comment_posted"}
        assert transition_node(state) is state

    @patch("app.nodes.transition.transition_issue")
    def test_transitions_status_only(self, mock_transition):
        mock_transition.return_value = "ok"
        state = {
            "ticket_id": "T-1",
            "transition_to_status": "In Progress",
            "resolution": "comment_posted",
        }
        result = transition_node(state)
        mock_transition.assert_called_once_with("T-1", "In Progress")
        assert "comment_posted" in result["resolution"]
        assert "transitioned:In Progress" in result["resolution"]

    @patch("app.nodes.transition.assign_issue")
    @patch("app.nodes.transition.transition_issue")
    def test_transitions_status_and_assigns(self, mock_transition, mock_assign):
        mock_transition.return_value = "ok"
        mock_assign.return_value = "ok"
        state = {
            "ticket_id": "T-2",
            "transition_to_status": "Escalated",
            "reassign_to": "support_user",
            "resolution": "escalation_posted",
        }
        result = transition_node(state)
        mock_transition.assert_called_once_with("T-2", "Escalated")
        mock_assign.assert_called_once_with("T-2", "support_user")
        assert "transitioned:Escalated" in result["resolution"]
        assert "assigned:support_user" in result["resolution"]

    @patch("app.nodes.transition.assign_issue")
    @patch("app.nodes.transition.transition_issue")
    def test_assignment_only(self, mock_transition, mock_assign):
        mock_assign.return_value = "ok"
        state = {"ticket_id": "T-3", "reassign_to": "support_user"}
        result = transition_node(state)
        mock_transition.assert_not_called()
        mock_assign.assert_called_once_with("T-3", "support_user")
        assert "assigned:support_user" in result["resolution"]

    @patch("app.nodes.transition.transition_issue")
    def test_transition_failure_does_not_break_pipeline(self, mock_transition):
        mock_transition.side_effect = MCPError("transition not allowed")
        state = {
            "ticket_id": "T-4",
            "transition_to_status": "Done",
            "resolution": "comment_posted",
        }
        result = transition_node(state)
        assert "transition_failed:Done" in result["resolution"]
        # Prior resolution is preserved
        assert "comment_posted" in result["resolution"]

    @patch("app.nodes.transition.assign_issue")
    @patch("app.nodes.transition.transition_issue")
    def test_assign_failure_does_not_break_pipeline(self, mock_transition, mock_assign):
        mock_transition.return_value = "ok"
        mock_assign.side_effect = MCPError("user not found")
        state = {
            "ticket_id": "T-5",
            "transition_to_status": "Escalated",
            "reassign_to": "missing_user",
        }
        result = transition_node(state)
        assert "transitioned:Escalated" in result["resolution"]
        assert "assign_failed:missing_user" in result["resolution"]

    @patch("app.nodes.transition.transition_issue")
    def test_whitespace_treated_as_empty(self, mock_transition):
        state = {
            "ticket_id": "T-6",
            "transition_to_status": "   ",
            "reassign_to": "",
        }
        assert transition_node(state) is state
        mock_transition.assert_not_called()
