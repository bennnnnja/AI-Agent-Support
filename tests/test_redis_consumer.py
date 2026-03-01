"""Tests for services/redis_consumer — Redis Stream operations."""
import pytest
from unittest.mock import MagicMock, patch
import redis


class TestReadEvents:
    @patch("app.services.redis_consumer.settings")
    def test_empty_results(self, mock_settings):
        mock_settings.redis_group = "grp"
        mock_settings.redis_consumer = "c1"
        mock_settings.redis_stream = "stream"

        client = MagicMock()
        client.xreadgroup.return_value = None

        from app.services.redis_consumer import read_events
        result = read_events(client)
        assert result == []

    @patch("app.services.redis_consumer.settings")
    def test_returns_tuples(self, mock_settings):
        mock_settings.redis_group = "grp"
        mock_settings.redis_consumer = "c1"
        mock_settings.redis_stream = "stream"

        client = MagicMock()
        client.xreadgroup.return_value = [
            ("stream", [
                ("msg-1", {"event_type": "issue_created", "issue_key": "T-1"}),
                ("msg-2", {"event_type": "comment_created", "issue_key": "T-2"}),
            ])
        ]

        from app.services.redis_consumer import read_events
        result = read_events(client)
        assert len(result) == 2
        assert result[0] == ("msg-1", {"event_type": "issue_created", "issue_key": "T-1"})
        assert result[1] == ("msg-2", {"event_type": "comment_created", "issue_key": "T-2"})

    @patch("app.services.redis_consumer.settings")
    def test_no_xack_called(self, mock_settings):
        """read_events should NOT call xack — that's the caller's job."""
        mock_settings.redis_group = "grp"
        mock_settings.redis_consumer = "c1"
        mock_settings.redis_stream = "stream"

        client = MagicMock()
        client.xreadgroup.return_value = [
            ("stream", [("msg-1", {"data": "x"})])
        ]

        from app.services.redis_consumer import read_events
        read_events(client)
        client.xack.assert_not_called()


class TestAckEvent:
    @patch("app.services.redis_consumer.settings")
    def test_ack_calls_xack(self, mock_settings):
        mock_settings.redis_stream = "my-stream"
        mock_settings.redis_group = "my-group"

        client = MagicMock()

        from app.services.redis_consumer import ack_event
        ack_event(client, "msg-123")
        client.xack.assert_called_once_with("my-stream", "my-group", "msg-123")


class TestEnsureGroup:
    @patch("app.services.redis_consumer.settings")
    def test_busygroup_ignored(self, mock_settings):
        mock_settings.redis_stream = "s"
        mock_settings.redis_group = "g"

        client = MagicMock()
        client.xgroup_create.side_effect = redis.exceptions.ResponseError("BUSYGROUP Consumer Group name already exists")

        from app.services.redis_consumer import ensure_group
        ensure_group(client)  # should not raise

    @patch("app.services.redis_consumer.settings")
    def test_other_error_raised(self, mock_settings):
        mock_settings.redis_stream = "s"
        mock_settings.redis_group = "g"

        client = MagicMock()
        client.xgroup_create.side_effect = redis.exceptions.ResponseError("ERR something else")

        from app.services.redis_consumer import ensure_group
        with pytest.raises(redis.exceptions.ResponseError):
            ensure_group(client)
