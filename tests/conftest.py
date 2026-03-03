import pytest
from unittest.mock import MagicMock


@pytest.fixture
def base_state():
    """Minimal valid AgentState for testing."""
    return {
        "ticket_id": "TEST-1",
        "user_message": "Принтер не печатает",
        "is_first_message": True,
        "conversation_history": [],
        "category": None,
        "rag_results": [],
        "response": None,
        "resolution": None,
    }


@pytest.fixture
def mock_llm_response():
    """Factory for mock LLM responses."""
    def _make(content: str):
        resp = MagicMock()
        resp.content = content
        return resp
    return _make


@pytest.fixture
def sample_jira_issue():
    """A realistic JiraIssue dict as returned by _parse_jira_response."""
    return {
        "issue_key": "TEST-42",
        "summary": "Принтер HP не печатает",
        "description": "После обновления драйверов принтер перестал печатать.",
        "status": "Open",
        "assignee": "Admin",
        "priority": "High",
        "created": "2026-01-15T10:00:00Z",
        "updated": "2026-01-15T12:00:00Z",
        "comments": [
            {"author": "Telegram", "body": "Помогите пожалуйста", "created": "2026-01-15T10:05:00Z"},
            {"author": "Agent", "body": "Попробуйте перезагрузить.", "created": "2026-01-15T10:06:00Z"},
        ],
    }
