"""Tests for MCP account name auto-detection."""
import json
import pytest
import app.services.jira_mcp as jira_mcp


@pytest.fixture(autouse=True)
def reset_mcp_account_name():
    """Reset global state before each test."""
    jira_mcp._mcp_account_name = ""
    yield
    jira_mcp._mcp_account_name = ""


class TestTryDetectMcpUsername:

    def test_detects_display_name_from_dict(self):
        response = json.dumps({"id": "1", "author": {"displayName": "Admin", "name": "admin"}, "body": "Hi"})
        jira_mcp._try_detect_mcp_username(response)
        assert jira_mcp.get_mcp_account_name() == "admin"  # displayName "Admin" lowercased

    def test_detects_name_fallback(self):
        response = json.dumps({"id": "1", "author": {"name": "svc-bot"}, "body": "Hi"})
        jira_mcp._try_detect_mcp_username(response)
        assert jira_mcp.get_mcp_account_name() == "svc-bot"

    def test_detects_string_author(self):
        response = json.dumps({"id": "1", "author": "Administrator", "body": "Hi"})
        jira_mcp._try_detect_mcp_username(response)
        assert jira_mcp.get_mcp_account_name() == "administrator"

    def test_does_not_overwrite_once_set(self):
        jira_mcp._mcp_account_name = "first"
        response = json.dumps({"id": "1", "author": "second", "body": "Hi"})
        jira_mcp._try_detect_mcp_username(response)
        assert jira_mcp.get_mcp_account_name() == "first"

    def test_handles_invalid_json(self):
        jira_mcp._try_detect_mcp_username("not json")
        assert jira_mcp.get_mcp_account_name() == ""

    def test_handles_no_author(self):
        response = json.dumps({"id": "1", "body": "Hi"})
        jira_mcp._try_detect_mcp_username(response)
        assert jira_mcp.get_mcp_account_name() == ""

    def test_handles_empty_author_dict(self):
        response = json.dumps({"id": "1", "author": {}, "body": "Hi"})
        jira_mcp._try_detect_mcp_username(response)
        assert jira_mcp.get_mcp_account_name() == ""
