"""Unit tests for sidekick_tools.py (push, get_file_tools, other_tools)."""
import pytest
from unittest.mock import patch, MagicMock

from sidekick_tools import push, get_file_tools, other_tools


class TestPush:
    """Tests for push(): send push notification via Pushover."""

    @patch("sidekick_tools.requests.post")
    def test_returns_success(self, mock_post):
        mock_post.return_value = MagicMock()
        result = push("Hello")
        assert result == "success"

    @patch("sidekick_tools.requests.post")
    def test_calls_post_with_message(self, mock_post):
        push("Test message")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["data"]["message"] == "Test message"


class TestGetFileTools:
    """Tests for get_file_tools(): file toolkit scoped to sandbox/."""

    def test_returns_list(self):
        tools = get_file_tools()
        assert isinstance(tools, list)

    def test_returns_tools_with_names(self):
        tools = get_file_tools()
        names = [t.name for t in tools]
        # FileManagementToolkit typically provides read_file, write_file, list_dir, etc.
        assert len(names) >= 1
        assert all(isinstance(n, str) for n in names)


class TestOtherTools:
    """Tests for other_tools(): build file, search, Wikipedia, push, REPL tools."""

    @pytest.mark.asyncio
    async def test_returns_list(self):
        tools = await other_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_contains_push_and_search_tools(self):
        tools = await other_tools()
        names = [t.name for t in tools]
        assert "send_push_notification" in names
        assert "search" in names

    @pytest.mark.asyncio
    async def test_contains_file_tools(self):
        tools = await other_tools()
        names = [t.name for t in tools]
        # File toolkit adds multiple tools (list_dir, read_file, write_file, etc.)
        file_tool_names = [n for n in names if n not in ("send_push_notification", "search", "python_repl") and "wikipedia" not in n.lower()]
        assert len(file_tool_names) >= 1
