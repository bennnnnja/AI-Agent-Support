"""Tests for jira_mcp._parse_jira_response — Jira response parsing (3 formats)."""
import json
import pytest
from app.services.jira_mcp import _parse_jira_response


class TestEmptyAndInvalidInput:
    def test_empty_string(self):
        assert _parse_jira_response("") == {}

    def test_none_input(self):
        assert _parse_jira_response(None) == {}

    def test_whitespace_only(self):
        assert _parse_jira_response("   \n  ") == {}

    def test_json_array_returns_empty(self):
        assert _parse_jira_response("[1, 2, 3]") == {}

    def test_json_number_returns_empty(self):
        assert _parse_jira_response("42") == {}


class TestPlainTextFormat:
    """Non-JSON responses treated as description text."""

    def test_plain_text(self):
        result = _parse_jira_response("This is a markdown response about the issue.")
        assert result["description"] == "This is a markdown response about the issue."
        assert result["issue_key"] == ""
        assert result["summary"] == ""

    def test_markdown_text(self):
        md = "# Issue Details\n\n- Status: Open\n- Priority: High"
        result = _parse_jira_response(md)
        assert result["description"] == md


class TestRawJiraApiFormat:
    """Raw Jira API format with 'fields' nesting."""

    def test_basic_fields(self):
        data = {
            "key": "TEST-42",
            "fields": {
                "summary": "Printer broken",
                "description": "It doesn't print",
                "status": {"name": "Open"},
                "assignee": {"displayName": "Admin"},
                "priority": {"name": "High"},
                "created": "2026-01-01T00:00:00Z",
                "updated": "2026-01-02T00:00:00Z",
            }
        }
        result = _parse_jira_response(json.dumps(data))
        assert result["issue_key"] == "TEST-42"
        assert result["summary"] == "Printer broken"
        assert result["description"] == "It doesn't print"
        assert result["status"] == "Open"
        assert result["assignee"] == "Admin"
        assert result["priority"] == "High"

    def test_with_comments(self):
        data = {
            "key": "TEST-10",
            "fields": {
                "summary": "Test",
                "description": "",
                "status": {"name": "Done"},
                "assignee": None,
                "priority": {"name": "Low"},
                "comment": {
                    "comments": [
                        {
                            "author": {"displayName": "Telegram"},
                            "body": "Help me",
                            "created": "2026-01-01T10:00:00Z",
                        },
                        {
                            "author": {"displayName": "Agent"},
                            "body": "Sure, try restarting.",
                            "created": "2026-01-01T10:05:00Z",
                        },
                    ]
                },
                "created": "",
                "updated": "",
            }
        }
        result = _parse_jira_response(json.dumps(data))
        assert len(result["comments"]) == 2
        assert result["comments"][0]["author"] == "Telegram"
        assert result["comments"][0]["body"] == "Help me"
        assert result["comments"][1]["author"] == "Agent"

    def test_status_as_string(self):
        data = {
            "key": "TEST-1",
            "fields": {"summary": "X", "description": "", "status": "Open",
                       "assignee": "Bob", "priority": "High",
                       "created": "", "updated": ""}
        }
        result = _parse_jira_response(json.dumps(data))
        assert result["status"] == "Open"
        assert result["assignee"] == "Bob"
        assert result["priority"] == "High"

    def test_no_comments(self):
        data = {
            "key": "TEST-1",
            "fields": {"summary": "X", "description": "", "status": {"name": "Open"},
                       "assignee": {"displayName": "A"}, "priority": {"name": "Low"},
                       "created": "", "updated": ""}
        }
        result = _parse_jira_response(json.dumps(data))
        assert "comments" not in result

    def test_none_assignee(self):
        """Jira returns None for unassigned issues."""
        data = {
            "key": "TEST-1",
            "fields": {"summary": "X", "description": "", "status": {"name": "Open"},
                       "assignee": None, "priority": {"name": "Low"},
                       "created": "", "updated": ""}
        }
        result = _parse_jira_response(json.dumps(data))
        assert result["assignee"] == "None"


class TestSimplifiedMcpFormat:
    """Flat dict format from mcp-atlassian."""

    def test_basic_flat(self):
        data = {
            "key": "TEST-5",
            "summary": "Scanner issue",
            "description": "Scanner won't scan",
            "status": "In Progress",
            "assignee": "Tech",
            "priority": "Medium",
            "created": "2026-02-01T00:00:00Z",
            "updated": "2026-02-02T00:00:00Z",
        }
        result = _parse_jira_response(json.dumps(data))
        assert result["issue_key"] == "TEST-5"
        assert result["summary"] == "Scanner issue"
        assert result["status"] == "In Progress"

    def test_issue_key_field(self):
        """Uses 'issue_key' if 'key' is missing."""
        data = {"issue_key": "PROJ-99", "summary": "X", "description": ""}
        result = _parse_jira_response(json.dumps(data))
        assert result["issue_key"] == "PROJ-99"

    def test_with_flat_comments(self):
        data = {
            "key": "TEST-7",
            "summary": "Q",
            "description": "",
            "comments": [
                {"author": "User1", "body": "Problem here", "created": "2026-01-01T00:00:00Z"},
                {"author": "Agent", "text": "Answer", "created": "2026-01-01T01:00:00Z"},
            ]
        }
        result = _parse_jira_response(json.dumps(data))
        assert len(result["comments"]) == 2
        assert result["comments"][0]["body"] == "Problem here"
        # "text" field used as fallback for body
        assert result["comments"][1]["body"] == "Answer"

    def test_no_comments(self):
        data = {"key": "TEST-1", "summary": "X", "description": ""}
        result = _parse_jira_response(json.dumps(data))
        assert "comments" not in result

    def test_comments_not_list(self):
        """If comments field is not a list, should be ignored."""
        data = {"key": "TEST-1", "summary": "X", "description": "", "comments": "invalid"}
        result = _parse_jira_response(json.dumps(data))
        assert "comments" not in result

    def test_comment_not_dict(self):
        """Non-dict items in comments list should be skipped."""
        data = {"key": "TEST-1", "summary": "X", "description": "",
                "comments": ["not a dict", {"author": "A", "body": "B", "created": ""}]}
        result = _parse_jira_response(json.dumps(data))
        assert len(result["comments"]) == 1
        assert result["comments"][0]["author"] == "A"
